from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from exception_ops.ai.schemas import ClassificationOutput
from exception_ops.ai.service import get_ai_service
from exception_ops.config import settings
from exception_ops.domain.enums import (
    ApprovalState,
    EvidenceSourceType,
    EvidenceStatus,
    ExecutionState,
    ExceptionStatus,
    ExceptionType,
    RiskLevel,
    WorkflowLifecycleState,
)
from exception_ops.domain.models import EvidenceRecord, ExceptionCase


def _build_case() -> ExceptionCase:
    now = datetime.now(timezone.utc)
    return ExceptionCase(
        case_id="case-1",
        exception_type=ExceptionType.PROVIDER_FAILURE,
        status=ExceptionStatus.INGESTED,
        risk_level=RiskLevel.MEDIUM,
        summary="Provider timeout returned 502 during payout reconciliation",
        source_system="payments",
        external_reference=None,
        raw_context_json={"job_id": "job-123"},
        temporal_workflow_id="exception-resolution-case-1",
        temporal_run_id="run-case-1",
        workflow_lifecycle_state=WorkflowLifecycleState.STARTED,
        approval_state=ApprovalState.PENDING_POLICY,
        execution_state=ExecutionState.PENDING,
        created_at=now,
        updated_at=now,
    )


def _build_evidence_record() -> EvidenceRecord:
    now = datetime.now(timezone.utc)
    return EvidenceRecord(
        evidence_id="evidence-1",
        case_id="case-1",
        source_type=EvidenceSourceType.CASE_PAYLOAD_SNAPSHOT,
        source_name="ingest_payload",
        adapter_name="mock",
        status=EvidenceStatus.SUCCEEDED,
        payload_json={"raw_context_json": {"job_id": "job-123"}},
        summary_text="Captured source exception payload from ingest.",
        provenance_json={"reference_id": "case-1", "request": "source_case_snapshot"},
        failure_json=None,
        collected_at=now,
    )


def test_mock_provider_returns_structured_classification() -> None:
    result = asyncio.run(get_ai_service().classify_exception(_build_case()))

    assert result.status.value == "succeeded"
    assert result.provider == "mock"
    assert result.model == "mock-heuristic-v1"
    assert result.prompt_version == "classification.v3.triage"
    assert result.payload_json is not None
    assert result.payload_json["normalized_exception_type"] == "provider_failure"
    assert "supporting_evidence" in result.payload_json["missing_information"]
    assert result.failure_json is None
    assert result.route_json is not None
    assert result.route_json["path_name"] == "triage"
    assert result.route_json["compatibility_mode"] is True
    assert result.usage_json is not None
    assert result.usage_json["total_tokens"] is not None
    assert result.trace_json is not None
    assert result.trace_json["model_path"] == "triage"


def test_mock_provider_returns_structured_remediation_plan() -> None:
    classification = ClassificationOutput(
        normalized_exception_type=ExceptionType.PROVIDER_FAILURE,
        confidence=0.88,
        risk_level_suggestion=RiskLevel.MEDIUM,
        reasoning_summary="Provider failures match the stored timeout summary.",
        missing_information=[],
    )

    result = asyncio.run(get_ai_service().generate_remediation_plan(_build_case(), classification))

    assert result.status.value == "succeeded"
    assert result.provider == "mock"
    assert result.prompt_version == "remediation.v3.plan"
    assert result.payload_json is not None
    assert result.payload_json["recommended_action"] == "retry_provider_after_validation"
    assert result.payload_json["requires_approval"] is True
    assert result.route_json is not None
    assert result.route_json["path_name"] == "planner_default"
    assert result.trace_json is not None
    assert result.trace_json["model_path"] == "planner_default"


def test_mock_provider_uses_evidence_as_additional_context() -> None:
    result = asyncio.run(
        get_ai_service().classify_exception(_build_case(), [_build_evidence_record()])
    )

    assert result.status.value == "succeeded"
    assert result.payload_json is not None
    assert "supporting_evidence" not in result.payload_json["missing_information"]
    assert "1 supporting evidence item" in result.payload_json["reasoning_summary"]


def test_task_specific_model_config_splits_triage_and_planning_paths() -> None:
    settings.ai_triage_provider = "mock"
    settings.ai_triage_model = "mock-triage-v2"
    settings.ai_planner_provider = "mock"
    settings.ai_planner_model = "mock-planner-v2"

    classification_result = asyncio.run(get_ai_service().classify_exception(_build_case()))
    planning_result = asyncio.run(
        get_ai_service().generate_remediation_plan(
            _build_case(),
            ClassificationOutput(
                normalized_exception_type=ExceptionType.PROVIDER_FAILURE,
                confidence=0.92,
                risk_level_suggestion=RiskLevel.LOW,
                reasoning_summary="Confident triage",
                missing_information=[],
            ),
        )
    )

    assert classification_result.model == "mock-triage-v2"
    assert classification_result.route_json is not None
    assert classification_result.route_json["selected_model"] == "mock-triage-v2"
    assert planning_result.model == "mock-planner-v2"
    assert planning_result.route_json is not None
    assert planning_result.route_json["selected_model"] == "mock-planner-v2"


def test_planner_escalation_is_visible_for_low_confidence_cases() -> None:
    settings.ai_planner_provider = "mock"
    settings.ai_planner_model = "mock-planner-v2"
    settings.ai_planner_escalation_provider = "mock"
    settings.ai_planner_escalation_model = "mock-planner-strong-v2"

    result = asyncio.run(
        get_ai_service().generate_remediation_plan(
            _build_case(),
            ClassificationOutput(
                normalized_exception_type=ExceptionType.UNKNOWN,
                confidence=0.42,
                risk_level_suggestion=RiskLevel.MEDIUM,
                reasoning_summary="Low confidence triage with missing context.",
                missing_information=["supporting_evidence"],
            ),
            [],
        )
    )

    assert result.status.value == "succeeded"
    assert result.model == "mock-planner-strong-v2"
    assert result.route_json is not None
    assert result.route_json["path_name"] == "planner_escalated"
    assert result.route_json["escalation_requested"] is True
    assert result.route_json["escalated"] is True
    assert "triage_confidence_below_threshold" in result.route_json["routing_factors"]
    assert result.trace_json is not None
    assert result.trace_json["escalation_occurred"] is True


def test_provider_fallback_is_visible_and_honest() -> None:
    settings.ai_provider = "openai"
    settings.ai_model = "gpt-5.4-mini"
    settings.openai_api_key = ""
    settings.ai_fallback_provider = "mock"
    settings.ai_fallback_model = "mock-fallback-v1"

    result = asyncio.run(get_ai_service().classify_exception(_build_case()))

    assert result.status.value == "succeeded"
    assert result.provider == "mock"
    assert result.model == "mock-fallback-v1"
    assert result.route_json is not None
    assert result.route_json["fallback_occurred"] is True
    assert len(result.route_json["attempts"]) == 2
    assert result.route_json["attempts"][0]["outcome"] == "failed"
    assert result.route_json["attempts"][1]["outcome"] == "succeeded"
    assert result.trace_json is not None
    assert result.trace_json["fallback_occurred"] is True


def test_openai_provider_configuration_failure_is_reported_honestly() -> None:
    settings.ai_provider = "openai"
    settings.ai_model = "gpt-5.4-mini"
    settings.openai_api_key = ""

    result = asyncio.run(get_ai_service().classify_exception(_build_case()))

    assert result.status.value == "failed"
    assert result.provider == "openai"
    assert result.model == "gpt-5.4-mini"
    assert result.route_json is not None
    assert result.route_json["fallback_occurred"] is False
    assert result.failure_json == {
        "type": "ProviderConfigurationError",
        "message": "OPENAI_API_KEY is required when AI_PROVIDER=openai",
    }
