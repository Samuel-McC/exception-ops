"""Phase 4 baseline schema.

Revision ID: 0001_phase4_baseline
Revises:
Create Date: 2026-04-10 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_phase4_baseline"
down_revision = None
branch_labels = None
depends_on = None


exception_type_enum = sa.Enum(
    "payout_mismatch",
    "missing_document",
    "duplicate_record_risk",
    "provider_failure",
    "unknown",
    name="exception_type",
    native_enum=False,
)
exception_status_enum = sa.Enum(
    "ingested",
    "in_review",
    "resolved",
    name="exception_status",
    native_enum=False,
)
risk_level_enum = sa.Enum(
    "low",
    "medium",
    "high",
    name="risk_level",
    native_enum=False,
)
workflow_lifecycle_state_enum = sa.Enum(
    "started",
    "completed",
    "failed",
    name="workflow_lifecycle_state",
    native_enum=False,
)
approval_state_enum = sa.Enum(
    "pending_policy",
    "not_required",
    "pending",
    "approved",
    "rejected",
    name="approval_state",
    native_enum=False,
)
audit_event_type_enum = sa.Enum(
    "ingested",
    name="audit_event_type",
    native_enum=False,
)
ai_record_kind_enum = sa.Enum(
    "classification",
    "remediation",
    name="ai_record_kind",
    native_enum=False,
)
ai_record_status_enum = sa.Enum(
    "succeeded",
    "failed",
    name="ai_record_status",
    native_enum=False,
)
approval_decision_type_enum = sa.Enum(
    "approved",
    "rejected",
    name="approval_decision_type",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "exception_cases",
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("exception_type", exception_type_enum, nullable=False),
        sa.Column("status", exception_status_enum, nullable=False),
        sa.Column("risk_level", risk_level_enum, nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_system", sa.String(length=255), nullable=False),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("raw_context_json", sa.JSON(), nullable=False),
        sa.Column("temporal_workflow_id", sa.String(length=255), nullable=True),
        sa.Column("temporal_run_id", sa.String(length=255), nullable=True),
        sa.Column("workflow_lifecycle_state", workflow_lifecycle_state_enum, nullable=False),
        sa.Column("approval_state", approval_state_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("case_id"),
        sa.UniqueConstraint("temporal_workflow_id"),
    )
    op.create_index(
        op.f("ix_exception_cases_created_at"),
        "exception_cases",
        ["created_at"],
        unique=False,
    )
    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", audit_event_type_enum, nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["exception_cases.case_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(op.f("ix_audit_events_case_id"), "audit_events", ["case_id"], unique=False)
    op.create_index(
        op.f("ix_audit_events_created_at"),
        "audit_events",
        ["created_at"],
        unique=False,
    )
    op.create_table(
        "ai_records",
        sa.Column("record_id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("record_kind", ai_record_kind_enum, nullable=False),
        sa.Column("status", ai_record_status_enum, nullable=False),
        sa.Column("provider", sa.String(length=255), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("prompt_version", sa.String(length=255), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("failure_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["exception_cases.case_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("record_id"),
    )
    op.create_index(op.f("ix_ai_records_case_id"), "ai_records", ["case_id"], unique=False)
    op.create_index(
        op.f("ix_ai_records_created_at"),
        "ai_records",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_records_record_kind"),
        "ai_records",
        ["record_kind"],
        unique=False,
    )
    op.create_table(
        "approval_decisions",
        sa.Column("decision_id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("decision", approval_decision_type_enum, nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["exception_cases.case_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("decision_id"),
    )
    op.create_index(
        op.f("ix_approval_decisions_case_id"),
        "approval_decisions",
        ["case_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_decisions_decided_at"),
        "approval_decisions",
        ["decided_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_decisions_decision"),
        "approval_decisions",
        ["decision"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_approval_decisions_decision"), table_name="approval_decisions")
    op.drop_index(op.f("ix_approval_decisions_decided_at"), table_name="approval_decisions")
    op.drop_index(op.f("ix_approval_decisions_case_id"), table_name="approval_decisions")
    op.drop_table("approval_decisions")
    op.drop_index(op.f("ix_ai_records_record_kind"), table_name="ai_records")
    op.drop_index(op.f("ix_ai_records_created_at"), table_name="ai_records")
    op.drop_index(op.f("ix_ai_records_case_id"), table_name="ai_records")
    op.drop_table("ai_records")
    op.drop_index(op.f("ix_audit_events_created_at"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_case_id"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index(op.f("ix_exception_cases_created_at"), table_name="exception_cases")
    op.drop_table("exception_cases")
