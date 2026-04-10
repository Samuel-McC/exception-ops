"""Add bounded evidence persistence for Phase 7.

Revision ID: 0003_phase7_evidence_records
Revises: 0002_phase5_schema_alignment
Create Date: 2026-04-10 01:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_phase7_evidence_records"
down_revision = "0002_phase5_schema_alignment"
branch_labels = None
depends_on = None


evidence_source_type_enum = sa.Enum(
    "collection_attempt",
    "case_payload_snapshot",
    "provider_response_snapshot",
    "document_metadata",
    "internal_reference_lookup",
    "prior_execution_snapshot",
    name="evidence_source_type",
    native_enum=False,
)
evidence_status_enum = sa.Enum(
    "succeeded",
    "failed",
    name="evidence_status",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "evidence_records",
        sa.Column("evidence_id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("source_type", evidence_source_type_enum, nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("adapter_name", sa.String(length=255), nullable=False),
        sa.Column("status", evidence_status_enum, nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("failure_json", sa.JSON(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["exception_cases.case_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("evidence_id"),
    )
    op.create_index(op.f("ix_evidence_records_case_id"), "evidence_records", ["case_id"], unique=False)
    op.create_index(
        op.f("ix_evidence_records_collected_at"),
        "evidence_records",
        ["collected_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evidence_records_source_type"),
        "evidence_records",
        ["source_type"],
        unique=False,
    )
    op.create_index(op.f("ix_evidence_records_status"), "evidence_records", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_evidence_records_status"), table_name="evidence_records")
    op.drop_index(op.f("ix_evidence_records_source_type"), table_name="evidence_records")
    op.drop_index(op.f("ix_evidence_records_collected_at"), table_name="evidence_records")
    op.drop_index(op.f("ix_evidence_records_case_id"), table_name="evidence_records")
    op.drop_table("evidence_records")
