"""Tests for the deterministic ``finalize-outcome`` task branch (Phase 20 / D-01).

The branch is agent-less: it reads the FinalizeOutcomeInput, composes an
AddRecipeOutcome, writes it to WorkflowRun.outcome, calls on_step_complete,
and returns the outcome dict. No LLM, no skills, no prompt.
"""
from unittest.mock import MagicMock, patch

import pytest

from robotina.queue.task_types import FinalizeOutcomeInput


def _make_job(job_id: str = "job-fo-1") -> MagicMock:
    mock_job = MagicMock()
    mock_job.id = job_id
    mock_job.meta = {"task_type": "finalize-outcome", "queue_name": "agent-tasks"}
    return mock_job


def _make_session_with_run(run_id: str = "run-1", step_id: str = "step-1") -> MagicMock:
    """Build a mock session that returns a WorkflowRunStep for the job lookup,
    then a WorkflowRun for the run lookup. Records writes on `.outcome`.
    """
    mock_step = MagicMock()
    mock_step.workflow_run_id = run_id

    mock_run = MagicMock()
    mock_run.id = run_id
    mock_run.outcome = None

    # session.query(X).filter(...).first() returns step then run in order
    query_results = [mock_step, mock_run]

    def query_side_effect(model):
        # Return a chain whose .filter(...).first() pops from query_results
        chain = MagicMock()
        chain.filter.return_value.first.side_effect = lambda: query_results.pop(0)
        return chain

    mock_session = MagicMock()
    mock_session.query.side_effect = query_side_effect
    mock_session._mock_run = mock_run
    mock_session._mock_step = mock_step
    return mock_session


def _patches(mock_job, mock_session):
    """Common patch stack for finalize-outcome tests."""
    return [
        patch("robotina.queue.jobs.get_current_job", return_value=mock_job),
        patch("robotina.db.SessionLocal", return_value=mock_session),
        patch("robotina.queue.workflow_runner.on_step_start"),
    ]


def test_finalize_outcome_success_writes_outcome():
    """Given a load artifact with recipe_id, composes a success outcome and
    writes it to WorkflowRun.outcome."""
    mock_job = _make_job()
    mock_session = _make_session_with_run()

    task_input = FinalizeOutcomeInput(
        metadata={"name": "Lentejas"},
        load={"recipe_id": "abc", "recipe_name": "Lentejas", "recipe_slug": "lentejas"},
    )

    with patch("robotina.queue.jobs.get_current_job", return_value=mock_job), \
         patch("robotina.db.SessionLocal", return_value=mock_session), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete") as mock_complete, \
         patch("robotina.queue.workflow_runner.on_step_failed"):
        from robotina.queue.jobs import run_task
        result = run_task(task_input)

    assert result["status"] == "success"
    assert result["recipe_id"] == "abc"
    assert result["recipe_name"] == "Lentejas"
    assert result["recipe_slug"] == "lentejas"
    assert result["image_present"] is False
    # WorkflowRun.outcome assignment
    assert mock_session._mock_run.outcome == result
    assert mock_complete.called


def test_finalize_outcome_failure_when_no_load():
    """No load artifact → status=failure with default failure_reason."""
    mock_job = _make_job()
    mock_session = _make_session_with_run()

    task_input = FinalizeOutcomeInput(metadata={"name": "X"}, load=None)

    with patch("robotina.queue.jobs.get_current_job", return_value=mock_job), \
         patch("robotina.db.SessionLocal", return_value=mock_session), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete"), \
         patch("robotina.queue.workflow_runner.on_step_failed"):
        from robotina.queue.jobs import run_task
        result = run_task(task_input)

    assert result["status"] == "failure"
    assert "without a load artifact" in result["failure_reason"]


def test_finalize_outcome_calls_on_step_complete():
    """Branch invokes workflow_runner.on_step_complete with (job.id, artifact, session, queue)."""
    mock_job = _make_job(job_id="job-fo-complete")
    mock_session = _make_session_with_run()

    task_input = FinalizeOutcomeInput(
        load={"recipe_id": "x", "recipe_name": "Y", "recipe_slug": "y"},
    )

    with patch("robotina.queue.jobs.get_current_job", return_value=mock_job), \
         patch("robotina.db.SessionLocal", return_value=mock_session), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete") as mock_complete, \
         patch("robotina.queue.workflow_runner.on_step_failed"):
        from robotina.queue.jobs import run_task
        run_task(task_input)

    mock_complete.assert_called_once()
    args = mock_complete.call_args.args
    assert args[0] == "job-fo-complete"
    assert args[1]["status"] == "success"


def test_finalize_outcome_propagates_failure_reason():
    """Explicit failure_reason on input is preserved when load is absent."""
    mock_job = _make_job()
    mock_session = _make_session_with_run()

    task_input = FinalizeOutcomeInput(load=None, failure_reason="explicit")

    with patch("robotina.queue.jobs.get_current_job", return_value=mock_job), \
         patch("robotina.db.SessionLocal", return_value=mock_session), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete"), \
         patch("robotina.queue.workflow_runner.on_step_failed"):
        from robotina.queue.jobs import run_task
        result = run_task(task_input)

    assert result["status"] == "failure"
    assert result["failure_reason"] == "explicit"


def test_finalize_outcome_image_present_is_false():
    """image_present is always False until the recipe-image milestone."""
    mock_job = _make_job()
    mock_session = _make_session_with_run()

    task_input = FinalizeOutcomeInput(
        load={"recipe_id": "r", "recipe_name": "R", "recipe_slug": "r"},
    )

    with patch("robotina.queue.jobs.get_current_job", return_value=mock_job), \
         patch("robotina.db.SessionLocal", return_value=mock_session), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete"), \
         patch("robotina.queue.workflow_runner.on_step_failed"):
        from robotina.queue.jobs import run_task
        result = run_task(task_input)

    assert result["status"] == "success"
    assert result["image_present"] is False


def test_finalize_outcome_exception_calls_on_step_failed():
    """If outcome composition raises, on_step_failed is called with exc kwarg and the
    exception re-raised."""
    mock_job = _make_job()
    mock_session = _make_session_with_run()

    task_input = FinalizeOutcomeInput(
        load={"recipe_id": "r", "recipe_name": "R", "recipe_slug": "r"},
    )

    # Force AddRecipeOutcome to raise on construction
    with patch("robotina.queue.jobs.get_current_job", return_value=mock_job), \
         patch("robotina.db.SessionLocal", return_value=mock_session), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete"), \
         patch("robotina.queue.workflow_runner.on_step_failed") as mock_failed, \
         patch("robotina.queue.task_types.AddRecipeOutcome", side_effect=RuntimeError("boom")):
        from robotina.queue.jobs import run_task
        with pytest.raises(RuntimeError, match="boom"):
            run_task(task_input)

    mock_failed.assert_called_once()
    # `exc` is a kwarg
    assert isinstance(mock_failed.call_args.kwargs.get("exc"), RuntimeError)
