"""Align Alembic history with the current Phase 5 runtime schema.

Revision ID: 0002_phase5_schema_alignment
Revises: 0001_phase4_baseline
Create Date: 2026-04-10 00:30:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_phase5_schema_alignment"
down_revision = "0001_phase4_baseline"
branch_labels = None
depends_on = None


execution_state_enum = sa.Enum(
    "pending",
    "started",
    "succeeded",
    "failed",
    "skipped",
    name="execution_state",
    native_enum=False,
)
execution_action_enum = sa.Enum(
    "retry_provider_after_validation",
    "request_missing_document",
    "review_duplicate_records",
    "review_payout_reconciliation",
    "manual_triage",
    name="execution_action",
    native_enum=False,
)
execution_record_status_enum = sa.Enum(
    "pending",
    "started",
    "succeeded",
    "failed",
    name="execution_record_status",
    native_enum=False,
)


def upgrade() -> None:
    with op.batch_alter_table("exception_cases") as batch_op:
        batch_op.add_column(
            sa.Column(
                "execution_state",
                execution_state_enum,
                nullable=False,
                server_default="pending",
            )
        )

    op.create_table(
        "execution_records",
        sa.Column("execution_id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("action_name", execution_action_enum, nullable=False),
        sa.Column("initiated_by", sa.String(length=255), nullable=False),
        sa.Column("status", execution_record_status_enum, nullable=False),
        sa.Column("request_payload_json", sa.JSON(), nullable=False),
        sa.Column("result_payload_json", sa.JSON(), nullable=True),
        sa.Column("failure_payload_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["exception_cases.case_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("execution_id"),
    )
    op.create_index(op.f("ix_execution_records_action_name"), "execution_records", ["action_name"], unique=False)
    op.create_index(op.f("ix_execution_records_case_id"), "execution_records", ["case_id"], unique=False)
    op.create_index(
        op.f("ix_execution_records_started_at"),
        "execution_records",
        ["started_at"],
        unique=False,
    )
    op.create_index(op.f("ix_execution_records_status"), "execution_records", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_execution_records_status"), table_name="execution_records")
    op.drop_index(op.f("ix_execution_records_started_at"), table_name="execution_records")
    op.drop_index(op.f("ix_execution_records_case_id"), table_name="execution_records")
    op.drop_index(op.f("ix_execution_records_action_name"), table_name="execution_records")
    op.drop_table("execution_records")
    with op.batch_alter_table("exception_cases") as batch_op:
        batch_op.drop_column("execution_state")
