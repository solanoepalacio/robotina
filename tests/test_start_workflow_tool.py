"""Tests for agent/tools/start_workflow.py — StartWorkflowTool (WF-04, QUEUE-01)."""
import os
import pytest
from sqlalchemy import text

from robotina.db import SessionLocal
from robotina.queue.models import WorkflowRun, WorkflowRunStep, WorkflowStatus, WorkflowStepStatus
from robotina.agent.tools.start_workflow import StartWorkflowTool
from langchain_core.tools import BaseTool


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


def test_start_workflow_tool_is_basetool_subclass():
    """StartWorkflowTool inherits from langchain_core.tools.BaseTool."""
    assert issubclass(StartWorkflowTool, BaseTool)


@pytest.mark.integration
def test_start_workflow_tool_creates_workflow_run(wf_db_session, redis_conn):
    """WF-04: StartWorkflowTool._run creates a WorkflowRun record."""
    tool = StartWorkflowTool()
    shared_context = {"household_id": "h1"}

    run_id = tool._run("hello-world-2step", shared_context)

    assert run_id is not None
    run = wf_db_session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    assert run is not None
    assert run.workflow_type == "hello-world-2step"
    assert run.household_id == "h1"


@pytest.mark.integration
def test_start_workflow_tool_creates_all_pending_steps(wf_db_session, redis_conn):
    """WF-04: StartWorkflowTool._run creates all WorkflowRunStep records with PENDING status."""
    tool = StartWorkflowTool()
    shared_context = {"household_id": "h1"}

    run_id = tool._run("hello-world-2step", shared_context)

    steps = (
        wf_db_session.query(WorkflowRunStep)
        .filter(WorkflowRunStep.workflow_run_id == run_id)
        .order_by(WorkflowRunStep.step_order)
        .all()
    )
    assert len(steps) == 2
    assert all(s.status == WorkflowStepStatus.PENDING for s in steps)
    assert steps[0].step_key == "step1"
    assert steps[1].step_key == "step2"


@pytest.mark.integration
def test_start_workflow_tool_enqueues_first_step(wf_db_session, redis_conn):
    """WF-04: StartWorkflowTool._run enqueues the first step job to agent-tasks queue."""
    from rq import Queue

    tool = StartWorkflowTool()
    shared_context = {"household_id": "h1"}

    run_id = tool._run("hello-world-2step", shared_context)

    # First step should have a task_job_id (the enqueued RQ job ID)
    first_step = (
        wf_db_session.query(WorkflowRunStep)
        .filter(WorkflowRunStep.workflow_run_id == run_id)
        .order_by(WorkflowRunStep.step_order)
        .first()
    )
    assert first_step.task_job_id is not None

    # The job should be in the queue
    queue = Queue("agent-tasks", connection=redis_conn)
    job = queue.fetch_job(first_step.task_job_id)
    assert job is not None


@pytest.mark.integration
def test_start_workflow_tool_returns_workflow_run_id(wf_db_session, redis_conn):
    """WF-04: StartWorkflowTool._run returns the workflow_run_id string."""
    tool = StartWorkflowTool()
    shared_context = {"household_id": "h1"}

    run_id = tool._run("hello-world-2step", shared_context)

    assert isinstance(run_id, str)
    assert len(run_id) > 0
    # Should be a valid UUID-like string
    run = wf_db_session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    assert run is not None
