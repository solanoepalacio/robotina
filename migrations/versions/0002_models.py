"""models: Conversation, StoredMessage, WorkflowRun, WorkflowRunStep

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-25
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create native PostgreSQL ENUM types; skip if already exists (idempotent via pg_type check)
    conn = op.get_bind()
    conn.execute(sa.text(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'platform') "
        "THEN CREATE TYPE platform AS ENUM ('telegram'); END IF; END $$"
    ))
    conn.execute(sa.text(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'messagerole') "
        "THEN CREATE TYPE messagerole AS ENUM ('user', 'assistant'); END IF; END $$"
    ))
    conn.execute(sa.text(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'workflowstatus') "
        "THEN CREATE TYPE workflowstatus AS ENUM ('running', 'done', 'failed'); END IF; END $$"
    ))
    conn.execute(sa.text(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'workflowstepstatus') "
        "THEN CREATE TYPE workflowstepstatus AS ENUM ('pending', 'running', 'done', 'failed', 'cancelled'); END IF; END $$"
    ))

    # Use postgresql.ENUM with create_type=False so op.create_table does not attempt to re-create types
    platform_col_type = PgEnum('telegram', name='platform', create_type=False)
    messagerole_col_type = PgEnum('user', 'assistant', name='messagerole', create_type=False)
    workflowstatus_col_type = PgEnum('running', 'done', 'failed', name='workflowstatus', create_type=False)
    workflowstepstatus_col_type = PgEnum(
        'pending', 'running', 'done', 'failed', 'cancelled',
        name='workflowstepstatus', create_type=False
    )

    op.create_table(
        'conversations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('platform', platform_col_type, nullable=False),
        sa.Column('chat_id', sa.String(), nullable=False),
        sa.Column('household_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('platform', 'chat_id'),
    )

    op.create_table(
        'stored_messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('platform_message_id', sa.String(), nullable=False),
        sa.Column('role', messagerole_col_type, nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('platform_message_id'),
    )

    op.create_table(
        'workflow_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workflow_type', sa.String(), nullable=False),
        sa.Column('household_id', sa.String(), nullable=False),
        sa.Column('status', workflowstatus_col_type, nullable=False),
        sa.Column('shared_context', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'workflow_run_steps',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workflow_run_id', sa.String(), nullable=False),
        sa.Column('step_key', sa.String(), nullable=False),
        sa.Column('task_type', sa.String(), nullable=False),
        sa.Column('task_job_id', sa.String(), nullable=True),
        sa.Column('status', workflowstepstatus_col_type, nullable=False),
        sa.Column('artifact', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['workflow_run_id'], ['workflow_runs.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workflow_run_id', 'step_key'),
    )


def downgrade() -> None:
    op.drop_table('workflow_run_steps')
    op.drop_table('workflow_runs')
    op.drop_table('stored_messages')
    op.drop_table('conversations')
    conn = op.get_bind()
    conn.execute(sa.text("DROP TYPE IF EXISTS workflowstepstatus"))
    conn.execute(sa.text("DROP TYPE IF EXISTS workflowstatus"))
    conn.execute(sa.text("DROP TYPE IF EXISTS messagerole"))
    conn.execute(sa.text("DROP TYPE IF EXISTS platform"))
