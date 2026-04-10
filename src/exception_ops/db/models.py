from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Enum as SqlEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from exception_ops.db import Base
from exception_ops.domain.enums import (
    AIRecordKind,
    AIRecordStatus,
    ApprovalDecisionType,
    ApprovalState,
    AuditEventType,
    EvidenceSourceType,
    EvidenceStatus,
    ExecutionAction,
    ExecutionRecordStatus,
    ExecutionState,
    ExceptionStatus,
    ExceptionType,
    RiskLevel,
    WorkflowLifecycleState,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExceptionCaseRecord(Base):
    __tablename__ = "exception_cases"

    case_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exception_type: Mapped[ExceptionType] = mapped_column(
        SqlEnum(ExceptionType, name="exception_type", native_enum=False),
        nullable=False,
    )
    status: Mapped[ExceptionStatus] = mapped_column(
        SqlEnum(ExceptionStatus, name="exception_status", native_enum=False),
        nullable=False,
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        SqlEnum(RiskLevel, name="risk_level", native_enum=False),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_system: Mapped[str] = mapped_column(String(255), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(255))
    raw_context_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    temporal_workflow_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    temporal_run_id: Mapped[str | None] = mapped_column(String(255))
    workflow_lifecycle_state: Mapped[WorkflowLifecycleState] = mapped_column(
        SqlEnum(WorkflowLifecycleState, name="workflow_lifecycle_state", native_enum=False),
        nullable=False,
        default=WorkflowLifecycleState.STARTED,
    )
    approval_state: Mapped[ApprovalState] = mapped_column(
        SqlEnum(ApprovalState, name="approval_state", native_enum=False),
        nullable=False,
        default=ApprovalState.PENDING_POLICY,
    )
    execution_state: Mapped[ExecutionState] = mapped_column(
        SqlEnum(ExecutionState, name="execution_state", native_enum=False),
        nullable=False,
        default=ExecutionState.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    audit_events: Mapped[list["AuditEventRecord"]] = relationship(
        back_populates="exception_case",
        cascade="all, delete-orphan",
        order_by="AuditEventRecord.created_at",
    )
    ai_records: Mapped[list["AIRecordRecord"]] = relationship(
        back_populates="exception_case",
        cascade="all, delete-orphan",
        order_by="AIRecordRecord.created_at",
    )
    approval_decisions: Mapped[list["ApprovalDecisionRecord"]] = relationship(
        back_populates="exception_case",
        cascade="all, delete-orphan",
        order_by="ApprovalDecisionRecord.decided_at.desc()",
    )
    evidence_records: Mapped[list["EvidenceRecordRecord"]] = relationship(
        back_populates="exception_case",
        cascade="all, delete-orphan",
        order_by="EvidenceRecordRecord.collected_at.desc()",
    )
    execution_records: Mapped[list["ExecutionRecordRecord"]] = relationship(
        back_populates="exception_case",
        cascade="all, delete-orphan",
        order_by="ExecutionRecordRecord.started_at.desc()",
    )


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("exception_cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[AuditEventType] = mapped_column(
        SqlEnum(AuditEventType, name="audit_event_type", native_enum=False),
        nullable=False,
    )
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    exception_case: Mapped[ExceptionCaseRecord] = relationship(back_populates="audit_events")


class AIRecordRecord(Base):
    __tablename__ = "ai_records"

    record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("exception_cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    record_kind: Mapped[AIRecordKind] = mapped_column(
        SqlEnum(AIRecordKind, name="ai_record_kind", native_enum=False),
        nullable=False,
        index=True,
    )
    status: Mapped[AIRecordStatus] = mapped_column(
        SqlEnum(AIRecordStatus, name="ai_record_status", native_enum=False),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    failure_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    exception_case: Mapped[ExceptionCaseRecord] = relationship(back_populates="ai_records")


class ApprovalDecisionRecord(Base):
    __tablename__ = "approval_decisions"

    decision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("exception_cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[ApprovalDecisionType] = mapped_column(
        SqlEnum(ApprovalDecisionType, name="approval_decision_type", native_enum=False),
        nullable=False,
        index=True,
    )
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    exception_case: Mapped[ExceptionCaseRecord] = relationship(back_populates="approval_decisions")


class EvidenceRecordRecord(Base):
    __tablename__ = "evidence_records"

    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("exception_cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[EvidenceSourceType] = mapped_column(
        SqlEnum(EvidenceSourceType, name="evidence_source_type", native_enum=False),
        nullable=False,
        index=True,
    )
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    adapter_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[EvidenceStatus] = mapped_column(
        SqlEnum(EvidenceStatus, name="evidence_status", native_enum=False),
        nullable=False,
        index=True,
    )
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    summary_text: Mapped[str | None] = mapped_column(Text)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    failure_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    exception_case: Mapped[ExceptionCaseRecord] = relationship(back_populates="evidence_records")


class ExecutionRecordRecord(Base):
    __tablename__ = "execution_records"

    execution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("exception_cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_name: Mapped[ExecutionAction] = mapped_column(
        SqlEnum(ExecutionAction, name="execution_action", native_enum=False),
        nullable=False,
        index=True,
    )
    initiated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ExecutionRecordStatus] = mapped_column(
        SqlEnum(ExecutionRecordStatus, name="execution_record_status", native_enum=False),
        nullable=False,
        index=True,
    )
    request_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    failure_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    exception_case: Mapped[ExceptionCaseRecord] = relationship(back_populates="execution_records")
