"""Add additive AI routing, usage, and trace metadata for V2 Phase 1.

Revision ID: 0004_v2_phase1_ai_routing_metadata
Revises: 0003_phase7_evidence_records
Create Date: 2026-04-11 12:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0004_v2_phase1_ai_routing_metadata"
down_revision = "0003_phase7_evidence_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ai_records") as batch_op:
        batch_op.add_column(sa.Column("route_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("usage_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("trace_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ai_records") as batch_op:
        batch_op.drop_column("trace_json")
        batch_op.drop_column("usage_json")
        batch_op.drop_column("route_json")
