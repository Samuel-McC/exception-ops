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


class ExecutionAction(StrEnum):
    RETRY_PROVIDER_AFTER_VALIDATION = "retry_provider_after_validation"
    REQUEST_MISSING_DOCUMENT = "request_missing_document"
    REVIEW_DUPLICATE_RECORDS = "review_duplicate_records"
    REVIEW_PAYOUT_RECONCILIATION = "review_payout_reconciliation"
    MANUAL_TRIAGE = "manual_triage"


class ExecutionState(StrEnum):
    PENDING = "pending"
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class ExecutionRecordStatus(StrEnum):
    PENDING = "pending"
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AIRecordKind(StrEnum):
    CLASSIFICATION = "classification"
    REMEDIATION = "remediation"


class AIRecordStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class EvidenceSourceType(StrEnum):
    COLLECTION_ATTEMPT = "collection_attempt"
    CASE_PAYLOAD_SNAPSHOT = "case_payload_snapshot"
    PROVIDER_RESPONSE_SNAPSHOT = "provider_response_snapshot"
    DOCUMENT_METADATA = "document_metadata"
    INTERNAL_REFERENCE_LOOKUP = "internal_reference_lookup"
    PRIOR_EXECUTION_SNAPSHOT = "prior_execution_snapshot"


class EvidenceStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
