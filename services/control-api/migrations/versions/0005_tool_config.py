"""add config column to tools

Revision ID: 0005
Revises: 0004
Create Date: 2026-01-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tools",
        sa.Column(
            "config",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("tools", "config")
