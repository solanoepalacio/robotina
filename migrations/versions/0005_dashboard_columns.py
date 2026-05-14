"""workflow_run_steps: add step_input (JSON) and failure_reason (Text)

Phase 13 / Plan 13-01 (DASH-01): persistence layer for the queue visibility
dashboard. Both columns are nullable — historical rows backfill to NULL and
the running worker keeps working after the upgrade.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-14
"""
import sqlalchemy as sa
from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'workflow_run_steps',
        sa.Column('step_input', sa.JSON(), nullable=True),
    )
    op.add_column(
        'workflow_run_steps',
        sa.Column('failure_reason', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('workflow_run_steps', 'failure_reason')
    op.drop_column('workflow_run_steps', 'step_input')
