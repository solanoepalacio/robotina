"""robotina_invocations: new table + nullable FK on workflow_runs

Phase 18 / ARCH-02 + ARCH-03 + D-01: single Alembic revision that:
  1. Creates the ``invocationtrigger`` and ``invocationstatus`` PostgreSQL
     ENUM types (idempotent guard, Phase 2 lesson).
  2. Creates the ``robotina_invocations`` table with the full Phase-20-ready
     column set (D-05) and the named UniqueConstraint
     ``ux_invocation_workflow_completion_once`` (D-08).
  3. Adds the NULLABLE FK column ``workflow_runs.triggered_by_invocation_id``
     pointing at ``robotina_invocations.id`` (D-02 — no backfill, no NOT NULL).

The Phase 18 deploy runbook is just ``docker compose stop task-runner`` →
``uv run migrate`` → restart. No TRUNCATE this phase (Phase 17 already cleaned
``workflow_runs`` once; D-02 explains why a second TRUNCATE would be ceremony
for nothing).

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-19
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent ENUM creation — Phase 2 lesson (migrations/versions/0002_models.py:17-44).
    conn = op.get_bind()
    conn.execute(sa.text(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'invocationtrigger') "
        "THEN CREATE TYPE invocationtrigger AS ENUM ('user_message', 'workflow_completion', 'cron'); END IF; END $$"
    ))
    conn.execute(sa.text(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'invocationstatus') "
        "THEN CREATE TYPE invocationstatus AS ENUM ('pending', 'running', 'done', 'failed'); END IF; END $$"
    ))

    # Use create_type=False so op.create_table does not attempt to re-create the type.
    invocationtrigger_col_type = PgEnum(
        'user_message', 'workflow_completion', 'cron',
        name='invocationtrigger', create_type=False,
    )
    invocationstatus_col_type = PgEnum(
        'pending', 'running', 'done', 'failed',
        name='invocationstatus', create_type=False,
    )

    op.create_table(
        'robotina_invocations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('trigger', invocationtrigger_col_type, nullable=False),
        sa.Column('trigger_ref_id', sa.String(), nullable=True),
        sa.Column('rq_job_id', sa.String(), nullable=True),
        sa.Column('status', invocationstatus_col_type, nullable=False),
        sa.Column('wake_dispatched_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'trigger_ref_id', 'trigger',
            name='ux_invocation_workflow_completion_once',
        ),
    )

    # Phase 18 / ARCH-03 / D-02 — nullable FK column (no backfill).
    op.add_column(
        'workflow_runs',
        sa.Column(
            'triggered_by_invocation_id',
            sa.String(),
            sa.ForeignKey('robotina_invocations.id'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # Reverse order: drop FK column first, then the new table, then the enums.
    op.drop_column('workflow_runs', 'triggered_by_invocation_id')
    op.drop_table('robotina_invocations')
    conn = op.get_bind()
    conn.execute(sa.text("DROP TYPE IF EXISTS invocationstatus"))
    conn.execute(sa.text("DROP TYPE IF EXISTS invocationtrigger"))
