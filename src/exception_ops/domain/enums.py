from __future__ import annotations

from enum import StrEnum


class ExceptionType(StrEnum):
    PAYOUT_MISMATCH = "payout_mismatch"
    MISSING_DOCUMENT = "missing_document"
    DUPLICATE_RECORD_RISK = "duplicate_record_risk"
    PROVIDER_FAILURE = "provider_failure"
    UNKNOWN = "unknown"


class ExceptionStatus(StrEnum):
    INGESTED = "ingested"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AuditEventType(StrEnum):
    INGESTED = "ingested"


class WorkflowLifecycleState(StrEnum):
    NOT_STARTED = "not_started"
    STARTED = "started"
    START_FAILED = "start_failed"
