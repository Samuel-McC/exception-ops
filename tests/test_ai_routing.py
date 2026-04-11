from __future__ import annotations

from datetime import datetime, timezone

from exception_ops.ai.routing import (
    PLANNING_PROMPT_VERSION,
    TRIAGE_PROMPT_VERSION,
    get_fallback_target,
    route_classification,
    route_remediation,
)
from exception_ops.ai.schemas import ClassificationOutput
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


def _build_case(
    *,
    exception_type: ExceptionType = ExceptionType.PROVIDER_FAILURE,
    risk_level: RiskLevel = RiskLevel.LOW,
    summary: str = "Provider timeout returned 502 during reconciliation",
) -> ExceptionCase:
    now = datetime.now(timezone.utc)
    return ExceptionCase(
        case_id="case-1",
        exception_type=exception_type,
        status=ExceptionStatus.INGESTED,
        risk_level=risk_level,
        summary=summary,
        source_system="payments",
        external_reference="txn-1",
        raw_context_json={"attempt": 1},
        temporal_workflow_id="exception-resolution-case-1",
        temporal_run_id="run-case-1",
        workflow_lifecycle_state=WorkflowLifecycleState.STARTED,
        approval_state=ApprovalState.PENDING_POLICY,
        execution_state=ExecutionState.PENDING,
        created_at=now,
        updated_at=now,
    )


def _build_failed_evidence() -> EvidenceRecord:
    now = datetime.now(timezone.utc)
    return EvidenceRecord(
        evidence_id="evidence-1",
        case_id="case-1",
        source_type=EvidenceSourceType.INTERNAL_REFERENCE_LOOKUP,
        source_name="related_internal_lookup",
        adapter_name="mock",
        status=EvidenceStatus.FAILED,
        payload_json=None,
        summary_text="Failed bounded lookup.",
        provenance_json={"reference_id": "txn-1", "request": "related_internal_lookup"},
        failure_json={"type": "mock_failure", "message": "lookup failed"},
        collected_at=now,
    )


def test_classification_route_uses_v1_compatible_global_defaults() -> None:
    decision = route_classification(_build_case())

    assert decision.path_name == "triage"
    assert decision.provider == "mock"
    assert decision.model == "mock-heuristic-v1"
    assert decision.prompt_version == TRIAGE_PROMPT_VERSION
    assert decision.compatibility_mode is True


def test_remediation_route_escalates_on_confidence_and_evidence_signals() -> None:
    settings.ai_planner_provider = "mock"
    settings.ai_planner_model = "mock-planner-v2"
    settings.ai_planner_escalation_provider = "mock"
    settings.ai_planner_escalation_model = "mock-planner-strong-v2"

    decision = route_remediation(
        _build_case(risk_level=RiskLevel.MEDIUM, exception_type=ExceptionType.UNKNOWN),
        [_build_failed_evidence()],
        ClassificationOutput(
            normalized_exception_type=ExceptionType.UNKNOWN,
            confidence=0.4,
            risk_level_suggestion=RiskLevel.MEDIUM,
            reasoning_summary="Low confidence triage.",
            missing_information=["supporting_evidence"],
        ),
    )

    assert decision.path_name == "planner_escalated"
    assert decision.model == "mock-planner-strong-v2"
    assert decision.prompt_version == PLANNING_PROMPT_VERSION
    assert decision.escalation_requested is True
    assert decision.escalated is True
    assert "triage_confidence_below_threshold" in decision.routing_factors
    assert "evidence_collection_incomplete" in decision.routing_factors


def test_global_fallback_target_is_optional_and_explicit() -> None:
    assert get_fallback_target() is None

    settings.ai_fallback_provider = "mock"
    settings.ai_fallback_model = "mock-fallback-v1"

    assert get_fallback_target() == ("mock", "mock-fallback-v1")
