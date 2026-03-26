"""Tests for queue/workflow_runner.py — workflow lifecycle (WF-04 through WF-09).

Unit tests: mocked session + queue (D-13).
Integration tests: real Redis + Postgres via fixtures (D-12).
"""
import os
import uuid

import pytest
from sqlalchemy import text
from unittest.mock import MagicMock, call
from datetime import datetime, timezone

from robotina.db import SessionLocal
from robotina.queue.models import WorkflowRun, WorkflowRunStep, WorkflowStatus, WorkflowStepStatus
from robotina.queue.task_types import RecipeResearchInput, RecipeLoadInput
from robotina.queue.workflow_runner import start_workflow


# ---------------------------------------------------------------------------
# Helper: build a mock session whose query().filter().first() returns obj
# ---------------------------------------------------------------------------

def make_session_returning(obj):
    """Return a mock session whose query().filter().first() returns obj."""
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.all.return_value = [] if obj is None else [obj]
    mock_query.first.return_value = obj
    session = MagicMock()
    session.query.return_value = mock_query
    return session


def make_step(
    step_key="step1",
    task_type="hello-world",
    task_job_id="test-job-id",
    status=WorkflowStepStatus.PENDING,
    workflow_run_id="run-123",
    artifact=None,
):
    step = MagicMock()
    step.step_key = step_key
    step.task_type = task_type
    step.task_job_id = task_job_id
    step.status = status
    step.workflow_run_id = workflow_run_id
    step.artifact = artifact
    step.started_at = None
    step.completed_at = None
    return step


def make_run(workflow_type="hello-world-2step", status=WorkflowStatus.RUNNING, shared_context=None):
    run = MagicMock()
    run.workflow_type = workflow_type
    run.status = status
    run.shared_context = shared_context or {}
    return run


# ---------------------------------------------------------------------------
# Unit tests (mocked session + queue) — D-13
# ---------------------------------------------------------------------------

def test_on_step_start_marks_step_running():
    """WF-05: on_step_start sets WorkflowRunStep.status=RUNNING and records started_at."""
    from robotina.queue.workflow_runner import on_step_start

    step = make_step(status=WorkflowStepStatus.PENDING)
    session = make_session_returning(step)

    on_step_start("test-job-id", session)

    assert step.status == WorkflowStepStatus.RUNNING
    assert step.started_at is not None
    session.commit.assert_called_once()


def test_on_step_start_no_op_when_step_not_found():
    """D-06: on_step_start is a no-op when no WorkflowRunStep has task_job_id matching the job_id (direct task)."""
    from robotina.queue.workflow_runner import on_step_start

    session = make_session_returning(None)

    result = on_step_start("nonexistent-job", session)

    assert result is None
    session.commit.assert_not_called()


def test_on_step_complete_writes_artifact():
    """WF-06: on_step_complete writes step output to WorkflowRunStep.artifact as JSON-serializable dict."""
    from robotina.queue.workflow_runner import on_step_complete

    step = make_step(step_key="research", status=WorkflowStepStatus.RUNNING)
    run = make_run(shared_context={"household_id": "hh-1"})

    # Build a session that returns: step on first query, [] for done_steps, run for the run, None for next_step
    session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    # side_effect for multiple .first() calls: step, run, None (next step)
    query_mock.first.side_effect = [step, run, None]
    # For done_steps .all() returns empty list (no prior done steps)
    query_mock.all.return_value = [step]
    session.query.return_value = query_mock

    queue = MagicMock()

    # Use a Pydantic model as output
    output = RecipeResearchInput(query="spaghetti", household_id="hh-1")
    on_step_complete("test-job-id", output, session, queue)

    assert isinstance(step.artifact, dict)
    assert step.artifact == output.model_dump(mode="json")


def test_on_step_complete_marks_step_done():
    """WF-06: on_step_complete marks WorkflowRunStep.status=DONE and records completed_at."""
    from robotina.queue.workflow_runner import on_step_complete

    step = make_step(step_key="step1", status=WorkflowStepStatus.RUNNING)
    run = make_run()

    session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    query_mock.first.side_effect = [step, run, None]
    query_mock.all.return_value = [step]
    session.query.return_value = query_mock

    queue = MagicMock()
    output = {"result": "done"}

    on_step_complete("test-job-id", output, session, queue)

    assert step.status == WorkflowStepStatus.DONE
    assert step.completed_at is not None


def test_on_step_complete_enqueues_next_step():
    """WF-06: on_step_complete enqueues the next PENDING step with a pre-assigned job_id."""
    from robotina.queue.workflow_runner import on_step_complete

    step = make_step(step_key="step1", status=WorkflowStepStatus.RUNNING)
    next_step = make_step(step_key="step2", task_type="hello-world", task_job_id=None)
    run = make_run(workflow_type="hello-world-2step", shared_context={"household_id": "hh-1"})

    session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    # first() returns: step (step lookup), run (run lookup), next_step (next PENDING step)
    query_mock.first.side_effect = [step, run, next_step]
    query_mock.all.return_value = [step]
    session.query.return_value = query_mock

    queue = MagicMock()
    output = {"result": "step1_done"}

    on_step_complete("test-job-id", output, session, queue)

    assert queue.enqueue.called
    call_kwargs = queue.enqueue.call_args
    # Verify result_ttl and failure_ttl are -1 (locked)
    assert call_kwargs.kwargs.get("result_ttl") == -1
    assert call_kwargs.kwargs.get("failure_ttl") == -1
    # Verify next_step.task_job_id was assigned
    assert next_step.task_job_id is not None
    session.commit.assert_called()


def test_on_step_complete_marks_workflow_done_when_final_step():
    """WF-07: on_step_complete marks WorkflowRun.status=DONE when no PENDING steps remain."""
    from robotina.queue.workflow_runner import on_step_complete

    step = make_step(step_key="step2", status=WorkflowStepStatus.RUNNING)
    run = make_run(workflow_type="hello-world-2step", shared_context={})

    session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    # first() returns: step, run, None (no next step)
    query_mock.first.side_effect = [step, run, None]
    query_mock.all.return_value = [step]
    session.query.return_value = query_mock

    queue = MagicMock()
    output = {"result": "final"}

    on_step_complete("test-job-id", output, session, queue)

    assert run.status == WorkflowStatus.DONE
    queue.enqueue.assert_not_called()


def test_on_step_failed_marks_step_failed():
    """WF-08: on_step_failed marks the failed WorkflowRunStep.status=FAILED."""
    from robotina.queue.workflow_runner import on_step_failed

    step = make_step(status=WorkflowStepStatus.RUNNING)
    run = make_run()

    session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.first.side_effect = [step, run]
    query_mock.all.return_value = []
    session.query.return_value = query_mock

    on_step_failed("test-job-id", session)

    assert step.status == WorkflowStepStatus.FAILED


def test_on_step_failed_cancels_pending_steps():
    """WF-08: on_step_failed sets all remaining PENDING steps to CANCELLED."""
    from robotina.queue.workflow_runner import on_step_failed

    step = make_step(step_key="step1", status=WorkflowStepStatus.RUNNING)
    pending_step = make_step(step_key="step2", status=WorkflowStepStatus.PENDING)
    run = make_run()

    session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.first.side_effect = [step, run]
    query_mock.all.return_value = [pending_step]
    session.query.return_value = query_mock

    on_step_failed("test-job-id", session)

    assert pending_step.status == WorkflowStepStatus.CANCELLED


def test_on_step_failed_marks_workflow_failed():
    """WF-08: on_step_failed marks WorkflowRun.status=FAILED."""
    from robotina.queue.workflow_runner import on_step_failed

    step = make_step(status=WorkflowStepStatus.RUNNING)
    run = make_run(status=WorkflowStatus.RUNNING)

    session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.first.side_effect = [step, run]
    query_mock.all.return_value = []
    session.query.return_value = query_mock

    on_step_failed("test-job-id", session)

    assert run.status == WorkflowStatus.FAILED
    session.commit.assert_called_once()


def test_reply_context_not_in_recipe_research_input():
    """WF-09: RecipeResearchInput has no reply_context field (enforced at model level)."""
    assert "reply_context" not in RecipeResearchInput.model_fields


def test_reply_context_not_in_recipe_load_input():
    """WF-09: RecipeLoadInput has no reply_context field (enforced at model level)."""
    assert "reply_context" not in RecipeLoadInput.model_fields


# ---------------------------------------------------------------------------
# Integration tests — require live Redis + Postgres (D-12)
# ---------------------------------------------------------------------------


@pytest.fixture
def wf_db_session():
    """Live Postgres session that cleans workflow tables after each test."""
    with SessionLocal() as session:
        try:
            yield session
        finally:
            session.execute(text("DELETE FROM workflow_run_steps"))
            session.execute(text("DELETE FROM workflow_runs"))
            session.commit()


@pytest.mark.integration
def test_hello_world_2step_workflow_happy_path(wf_db_session, redis_conn):
    """WF-04 through WF-07: hello-world-2step runs both steps, WorkflowRun ends DONE."""
    import uuid
    from rq import Queue
    from robotina.queue.runner import LoggingWorker

    queue = Queue(f"test-wf-{uuid.uuid4().hex[:8]}", connection=redis_conn)
    shared_context = {"household_id": "test-household", "test_run": True}

    # start_workflow creates WorkflowRun + steps + enqueues step1
    run_id = start_workflow(
        workflow_type="hello-world-2step",
        shared_context=shared_context,
        household_id="test-household",
        queue=queue,
        session=wf_db_session,
    )
    assert run_id is not None

    # Verify initial state: 2 PENDING steps, first has task_job_id set
    steps = (
        wf_db_session.query(WorkflowRunStep)
        .filter(WorkflowRunStep.workflow_run_id == run_id)
        .order_by(WorkflowRunStep.step_order)
        .all()
    )
    assert len(steps) == 2
    assert steps[0].step_key == "step1"
    assert steps[0].status == WorkflowStepStatus.PENDING
    assert steps[0].task_job_id is not None
    assert steps[1].step_key == "step2"
    assert steps[1].status == WorkflowStepStatus.PENDING
    assert steps[1].task_job_id is None

    # Run the worker with agent mocked — avoids real LLM calls, tests state transitions only
    from unittest.mock import MagicMock, patch
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {"messages": [], "result": "ok"}
    mock_backend = MagicMock()
    mock_backend.create_agent.return_value = mock_agent
    with patch("robotina.llm.make_backend", return_value=mock_backend):
        worker = LoggingWorker([queue], connection=redis_conn)
        worker.work(burst=True)

    # Refresh session to see committed state
    wf_db_session.expire_all()

    steps_after = (
        wf_db_session.query(WorkflowRunStep)
        .filter(WorkflowRunStep.workflow_run_id == run_id)
        .order_by(WorkflowRunStep.step_order)
        .all()
    )
    assert steps_after[0].status == WorkflowStepStatus.DONE
    assert steps_after[0].artifact is not None
    assert steps_after[1].status == WorkflowStepStatus.DONE
    assert steps_after[1].artifact is not None

    run = wf_db_session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    assert run.status == WorkflowStatus.DONE


@pytest.mark.integration
def test_hello_world_2step_workflow_failure_path(wf_db_session, redis_conn):
    """WF-08: step1 failure marks step1 FAILED, step2 CANCELLED, WorkflowRun FAILED."""
    import uuid
    from unittest.mock import patch
    from rq import Queue
    from robotina.queue.runner import LoggingWorker

    queue = Queue(f"test-wf-{uuid.uuid4().hex[:8]}", connection=redis_conn)
    shared_context = {"household_id": "test-household", "test_run": True}

    run_id = start_workflow(
        workflow_type="hello-world-2step",
        shared_context=shared_context,
        household_id="test-household",
        queue=queue,
        session=wf_db_session,
    )

    # Make get_agent_config raise so the agent execution fails
    with patch("robotina.agent.agents.get_agent_config", side_effect=RuntimeError("forced failure")):
        worker = LoggingWorker([queue], connection=redis_conn)
        worker.work(burst=True)

    wf_db_session.expire_all()

    steps_after = (
        wf_db_session.query(WorkflowRunStep)
        .filter(WorkflowRunStep.workflow_run_id == run_id)
        .order_by(WorkflowRunStep.step_order)
        .all()
    )

    # step1 should be FAILED, step2 should be CANCELLED
    assert steps_after[0].step_key == "step1"
    assert steps_after[0].status == WorkflowStepStatus.FAILED

    assert steps_after[1].step_key == "step2"
    assert steps_after[1].status == WorkflowStepStatus.CANCELLED

    run = wf_db_session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    assert run.status == WorkflowStatus.FAILED
