"""Shared fixtures for tests/dashboard/.

Plan 13-02 — fixtures consumed by test_list_view, test_detail_view,
test_polling_halt, test_no_auth. The async `client` fixture uses
httpx.ASGITransport so HTTP tests don't need a live uvicorn server
(RESEARCH §Pattern 5). The sync `db_session` fixture inserts arrange-step
rows and cleans up by collected IDs only — never bulk-deletes
workflow_runs/workflow_run_steps (RESEARCH Pitfall 7).
"""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy.orm import Session

from robotina.db import SessionLocal
from robotina.queue.models import (
    WorkflowRun,
    WorkflowRunStep,
    WorkflowStatus,
    WorkflowStepStatus,
)


@pytest.fixture
async def client():
    """Async httpx client bound to the dashboard FastAPI app via ASGITransport.

    Imported lazily so test_independence + test_app_starts can collect
    without requiring app.py to exist yet (matters for Task 2.1 RED state).
    """
    from robotina.dashboard.app import app  # noqa: WPS433 — intentional lazy import

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def db_session():
    """Independent session for arrange-step inserts.

    Yields (session, inserted_run_ids). The caller appends to
    inserted_run_ids; teardown deletes ONLY those run_ids and their steps
    (RESEARCH Pitfall 7 — never bulk-delete the workflow tables).
    """
    inserted_run_ids: list[str] = []
    session: Session = SessionLocal()
    try:
        yield session, inserted_run_ids
    finally:
        for run_id in inserted_run_ids:
            session.query(WorkflowRunStep).filter(
                WorkflowRunStep.workflow_run_id == run_id
            ).delete()
            session.query(WorkflowRun).filter(WorkflowRun.id == run_id).delete()
        session.commit()
        session.close()


def make_failed_cascade_run(
    session: Session,
    household_id: str = "h-test",
) -> WorkflowRun:
    """Insert a WorkflowRun with 4 steps: DONE, FAILED, CANCELLED, CANCELLED.

    Caller is responsible for tracking the returned run.id in the
    db_session fixture's inserted_run_ids list.
    """
    run = WorkflowRun(
        workflow_type="add-recipe",
        household_id=household_id,
        status=WorkflowStatus.FAILED,
        shared_context={"reply_context": {"chat_id": 42}},
    )
    session.add(run)
    session.flush()
    steps_spec = [
        (
            "research",
            WorkflowStepStatus.DONE,
            {"recipe_url": "https://example.test/r"},
            {"recipe": {"name": "Test"}},
            None,
        ),
        (
            "load",
            WorkflowStepStatus.FAILED,
            {"recipe": {"name": "Test"}},
            None,
            "ValueError: ingredient not found",
        ),
        (
            "notify",
            WorkflowStepStatus.CANCELLED,
            {"message": "..."},
            None,
            None,
        ),
        (
            "post",
            WorkflowStepStatus.CANCELLED,
            {"message": "..."},
            None,
            None,
        ),
    ]
    for order, (key, status, step_input, artifact, fr) in enumerate(steps_spec):
        session.add(
            WorkflowRunStep(
                workflow_run_id=run.id,
                step_key=key,
                step_order=order,
                task_type=key,
                status=status,
                step_input=step_input,
                artifact=artifact,
                failure_reason=fr,
            )
        )
    session.commit()
    return run
