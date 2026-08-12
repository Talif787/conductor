"""add per-step and per-run LLM cost columns

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "run_executions",
        sa.Column("total_cost_usd", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "run_step_executions",
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("run_step_executions", "cost_usd")
    op.drop_column("run_executions", "total_cost_usd")
