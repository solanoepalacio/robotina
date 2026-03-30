"""Integration tests for SQLAlchemy models and Alembic migration (WF-01).

Requires: docker compose up (live Postgres).
Run: uv run pytest tests/test_db_models.py -x
"""
import pytest
from sqlalchemy import inspect, text


@pytest.mark.integration
def test_models_importable():
    """All four model classes must be importable without error."""
    from robotina.gateway.models import Conversation, StoredMessage, Platform, MessageRole
    from robotina.queue.models import WorkflowRun, WorkflowRunStep, WorkflowStatus, WorkflowStepStatus
    assert Conversation.__tablename__ == "conversations"
    assert StoredMessage.__tablename__ == "stored_messages"
    assert WorkflowRun.__tablename__ == "workflow_runs"
    assert WorkflowRunStep.__tablename__ == "workflow_run_steps"


@pytest.mark.integration
def test_migration_creates_all_tables():
    """uv run migrate must create all four tables in Postgres (requires live Postgres)."""
    import subprocess, sys
    result = subprocess.run(
        ["uv", "run", "migrate"],
        capture_output=True, text=True,
        cwd=str(__import__('pathlib').Path(__file__).parent.parent),
    )
    assert result.returncode == 0, (
        f"Migration failed.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


@pytest.mark.integration
def test_all_tables_exist_in_postgres():
    """All four tables must exist in Postgres after migration."""
    from robotina.db import _get_engine; engine = _get_engine()
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    required = {"conversations", "stored_messages", "workflow_runs", "workflow_run_steps"}
    missing = required - tables
    assert not missing, f"Tables missing from Postgres: {missing}"


@pytest.mark.integration
def test_conversation_unique_constraint():
    """Conversation must have a unique constraint on (platform, chat_id)."""
    from robotina.db import _get_engine; engine = _get_engine()
    insp = inspect(engine)
    unique_constraints = insp.get_unique_constraints("conversations")
    constraint_columns = [set(uc["column_names"]) for uc in unique_constraints]
    assert {"platform", "chat_id"} in constraint_columns, (
        f"UniqueConstraint on (platform, chat_id) not found. Got: {constraint_columns}"
    )


@pytest.mark.integration
def test_workflow_run_step_unique_constraint():
    """WorkflowRunStep must have unique constraint on (workflow_run_id, step_key)."""
    from robotina.db import _get_engine; engine = _get_engine()
    insp = inspect(engine)
    unique_constraints = insp.get_unique_constraints("workflow_run_steps")
    constraint_columns = [set(uc["column_names"]) for uc in unique_constraints]
    assert {"workflow_run_id", "step_key"} in constraint_columns, (
        f"UniqueConstraint on (workflow_run_id, step_key) not found. Got: {constraint_columns}"
    )
