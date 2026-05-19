"""workflow_runs: add conversation_id (FK, NOT NULL) and outcome (JSON, nullable)

Phase 17 / ARCH-01 + D-01 + D-06: closes the Conversation FK loop on
WorkflowRun and lands the unused nullable outcome JSON column (slot for
Phase 20's AddRecipeOutcome). Single revision — the deploy runbook (D-08)
pre-cleans workflow_runs + workflow_run_steps before this migration runs,
so there is no backfill ceremony. If the table is non-empty at upgrade
time, Postgres will fail loudly on the NOT NULL constraint — that is the
intended signal that the operator skipped the runbook.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-18
"""
import sqlalchemy as sa
from alembic import op

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'workflow_runs',
        sa.Column(
            'conversation_id',
            sa.String(),
            sa.ForeignKey('conversations.id'),
            nullable=False,
        ),
    )
    op.add_column(
        'workflow_runs',
        sa.Column('outcome', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('workflow_runs', 'outcome')
    op.drop_column('workflow_runs', 'conversation_id')
