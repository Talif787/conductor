"""add run_view read model and widen the outbox index for the relay

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-11

Migration 0001 already created ix_run_events_unpublished on run_events(published).
The relay scans unpublished rows in occurred_at order, so this migration replaces
that single-column index with a composite (published, occurred_at) index rather
than creating a second index of the same name.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_view",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="normal"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_run_view_tenant_status", "run_view", ["tenant_id", "status"])
    # Replace the Phase 1 single-column outbox index with one that also covers
    # the relay's "unpublished, oldest first" ordering.
    op.drop_index("ix_run_events_unpublished", table_name="run_events")
    op.create_index(
        "ix_run_events_unpublished",
        "run_events",
        ["published", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_run_events_unpublished", table_name="run_events")
    op.create_index("ix_run_events_unpublished", "run_events", ["published"])
    op.drop_index("ix_run_view_tenant_status", table_name="run_view")
    op.drop_table("run_view")
