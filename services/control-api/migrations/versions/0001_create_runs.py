"""create runs and run_events tables

Revision ID: 0001
Revises:
Create Date: 2026-01-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("workflow_id", sa.String(length=64), nullable=True),
        sa.Column("workflow_version", sa.String(length=32), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_runs_tenant_idempotency"),
    )
    op.create_index("ix_runs_tenant_created", "runs", ["tenant_id", "created_at"])
    op.create_index("ix_runs_tenant_status", "runs", ["tenant_id", "status"])

    op.create_table(
        "run_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_run_events_run", "run_events", ["run_id", "occurred_at"])
    op.create_index("ix_run_events_unpublished", "run_events", ["published"])


def downgrade() -> None:
    op.drop_index("ix_run_events_unpublished", table_name="run_events")
    op.drop_index("ix_run_events_run", table_name="run_events")
    op.drop_table("run_events")
    op.drop_index("ix_runs_tenant_status", table_name="runs")
    op.drop_index("ix_runs_tenant_created", table_name="runs")
    op.drop_table("runs")
