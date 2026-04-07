from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from exception_ops.domain.enums import (
    AIRecordKind,
    AIRecordStatus,
    AuditEventType,
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
