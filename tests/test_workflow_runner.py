"""Tests for queue/workflow_runner.py — workflow lifecycle (WF-04 through WF-09).

Unit tests: mocked session + queue (D-13).
Integration tests: real Redis + Postgres via fixtures (D-12).
"""
import pytest


# ---------------------------------------------------------------------------
# Unit tests (mocked session + queue) — D-13
# ---------------------------------------------------------------------------

def test_on_step_start_marks_step_running():
    """WF-05: on_step_start sets WorkflowRunStep.status=RUNNING and records started_at."""
    pytest.skip("not yet implemented")


def test_on_step_start_no_op_when_step_not_found():
    """D-06: on_step_start is a no-op when no WorkflowRunStep has task_job_id matching the job_id (direct task)."""
    pytest.skip("not yet implemented")


def test_on_step_complete_writes_artifact():
    """WF-06: on_step_complete writes step output to WorkflowRunStep.artifact as JSON-serializable dict."""
    pytest.skip("not yet implemented")


def test_on_step_complete_marks_step_done():
    """WF-06: on_step_complete marks WorkflowRunStep.status=DONE and records completed_at."""
    pytest.skip("not yet implemented")


def test_on_step_complete_enqueues_next_step():
    """WF-06: on_step_complete enqueues the next PENDING step with a pre-assigned job_id."""
    pytest.skip("not yet implemented")


def test_on_step_complete_marks_workflow_done_when_final_step():
    """WF-07: on_step_complete marks WorkflowRun.status=DONE when no PENDING steps remain."""
    pytest.skip("not yet implemented")


def test_on_step_failed_marks_step_failed():
    """WF-08: on_step_failed marks the failed WorkflowRunStep.status=FAILED."""
    pytest.skip("not yet implemented")


def test_on_step_failed_cancels_pending_steps():
    """WF-08: on_step_failed sets all remaining PENDING steps to CANCELLED."""
    pytest.skip("not yet implemented")


def test_on_step_failed_marks_workflow_failed():
    """WF-08: on_step_failed marks WorkflowRun.status=FAILED."""
    pytest.skip("not yet implemented")


def test_reply_context_not_in_recipe_research_input():
    """WF-09: RecipeResearchInput has no reply_context field (enforced at model level)."""
    pytest.skip("not yet implemented")


def test_reply_context_not_in_recipe_load_input():
    """WF-09: RecipeLoadInput has no reply_context field (enforced at model level)."""
    pytest.skip("not yet implemented")


# ---------------------------------------------------------------------------
# Integration tests — require live Redis + Postgres (D-12)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_hello_world_2step_workflow_happy_path(db_session, redis_conn):
    """WF-04 through WF-07: hello-world-2step workflow runs step1 PENDING->RUNNING->DONE,
    step2 PENDING->RUNNING->DONE, WorkflowRun transitions to DONE, artifacts populated."""
    pytest.skip("not yet implemented")


@pytest.mark.integration
def test_hello_world_2step_workflow_failure_path(db_session, redis_conn):
    """WF-08: step1 failure marks step1 FAILED, step2 CANCELLED, WorkflowRun FAILED."""
    pytest.skip("not yet implemented")
