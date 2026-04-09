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
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


class ApprovalState(StrEnum):
    PENDING_POLICY = "pending_policy"
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalDecisionType(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class AIRecordKind(StrEnum):
    CLASSIFICATION = "classification"
    REMEDIATION = "remediation"


class AIRecordStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
