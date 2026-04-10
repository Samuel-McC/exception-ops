from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from exception_ops.domain.enums import (
    ApprovalState,
    EvidenceSourceType,
    ExecutionState,
    ExceptionStatus,
    ExceptionType,
    RiskLevel,
    WorkflowLifecycleState,
)
from exception_ops.domain.models import ExceptionCase
from exception_ops.evidence_adapters import MockEvidenceAdapter


def _build_case(*, raw_context_json: dict[str, object] | None = None) -> ExceptionCase:
    now = datetime.now(timezone.utc)
    return ExceptionCase(
        case_id="case-1",
        exception_type=ExceptionType.PROVIDER_FAILURE,
        status=ExceptionStatus.INGESTED,
        risk_level=RiskLevel.MEDIUM,
        summary="Provider timeout returned 502",
        source_system="payments",
        external_reference="txn-123",
        raw_context_json=raw_context_json or {"attempt": 1, "job_id": "job-1"},
        temporal_workflow_id="exception-resolution-case-1",
        temporal_run_id="run-case-1",
        workflow_lifecycle_state=WorkflowLifecycleState.STARTED,
        approval_state=ApprovalState.PENDING_POLICY,
        execution_state=ExecutionState.PENDING,
        created_at=now,
        updated_at=now,
    )


def test_mock_evidence_adapter_returns_bounded_evidence_items() -> None:
    result = asyncio.run(
        MockEvidenceAdapter().collect(
            exception_case=_build_case(),
            latest_execution_record=None,
        )
    )

    assert len(result.items) == 2
    assert result.items[0].source_type is EvidenceSourceType.CASE_PAYLOAD_SNAPSHOT
    assert result.items[1].source_type is EvidenceSourceType.PROVIDER_RESPONSE_SNAPSHOT


def test_mock_evidence_adapter_failure_flag_is_honest() -> None:
    with pytest.raises(RuntimeError, match="Mock evidence adapter failed"):
        asyncio.run(
            MockEvidenceAdapter().collect(
                exception_case=_build_case(raw_context_json={"force_evidence_failure": True}),
                latest_execution_record=None,
            )
        )
