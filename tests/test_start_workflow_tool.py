"""Tests for agent/tools/start_workflow.py — StartWorkflowTool (WF-04, QUEUE-01)."""
import pytest


def test_start_workflow_tool_is_basetool_subclass():
    """StartWorkflowTool inherits from langchain_core.tools.BaseTool."""
    pytest.skip("not yet implemented")


def test_start_workflow_tool_creates_workflow_run(db_session, redis_conn):
    """WF-04: StartWorkflowTool._run creates a WorkflowRun record with RUNNING status."""
    pytest.skip("not yet implemented")


def test_start_workflow_tool_creates_all_pending_steps(db_session, redis_conn):
    """WF-04: StartWorkflowTool._run creates all WorkflowRunStep records with PENDING status."""
    pytest.skip("not yet implemented")


def test_start_workflow_tool_enqueues_first_step(db_session, redis_conn):
    """WF-04: StartWorkflowTool._run enqueues the first step job to agent-tasks queue."""
    pytest.skip("not yet implemented")


def test_start_workflow_tool_returns_workflow_run_id(db_session, redis_conn):
    """WF-04: StartWorkflowTool._run returns the workflow_run_id string."""
    pytest.skip("not yet implemented")
