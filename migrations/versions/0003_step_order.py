"""workflow_run_steps: add step_order column for deterministic step ordering

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-26
"""
import sqlalchemy as sa
from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'workflow_run_steps',
        sa.Column('step_order', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('workflow_run_steps', 'step_order')
