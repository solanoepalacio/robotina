"""Add PENDING status to workflowstatus enum

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TYPE workflowstatus ADD VALUE IF NOT EXISTS 'pending' BEFORE 'running'"))


def downgrade() -> None:
    # Postgres cannot remove enum values without recreating the type.
    # Downgrade is intentionally a no-op — reverting requires manual intervention.
    pass
