from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from exception_ops.domain.enums import (
    AIRecordKind,
    AIRecordStatus,
    ApprovalDecisionType,
    ApprovalState,
    AuditEventType,
    ExecutionAction,
    ExecutionRecordStatus,
    ExecutionState,
    ExceptionStatus,
    ExceptionType,
    RiskLevel,
    WorkflowLifecycleState,
)


JsonObject = dict[str, Any]


@dataclass(slots=True)
class ExceptionCase:
    case_id: str
    exception_type: ExceptionType
    status: ExceptionStatus
    risk_level: RiskLevel
    summary: str
    source_system: str
    external_reference: str | None
    raw_context_json: JsonObject
    temporal_workflow_id: str | None
    temporal_run_id: str | None
    workflow_lifecycle_state: WorkflowLifecycleState
    approval_state: ApprovalState
    execution_state: ExecutionState
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class AuditEvent:
    event_id: str
    case_id: str
    event_type: AuditEventType
    actor: str
    payload_json: JsonObject
    created_at: datetime


@dataclass(slots=True)
class AIRecord:
    record_id: str
    case_id: str
    record_kind: AIRecordKind
    status: AIRecordStatus
    provider: str
    model: str
    prompt_version: str
    payload_json: JsonObject | None
    failure_json: JsonObject | None
    created_at: datetime


@dataclass(slots=True)
class ApprovalDecision:
    decision_id: str
    case_id: str
    decision: ApprovalDecisionType
    actor: str
    reason: str
    decided_at: datetime


@dataclass(slots=True)
class ApprovalSignal:
    decision_id: str
    decision: ApprovalDecisionType
    actor: str
    reason: str


@dataclass(slots=True)
class ExecutionRecord:
    execution_id: str
    case_id: str
    action_name: ExecutionAction
    initiated_by: str
    status: ExecutionRecordStatus
    request_payload_json: JsonObject
    result_payload_json: JsonObject | None
    failure_payload_json: JsonObject | None
    started_at: datetime
    completed_at: datetime | None
