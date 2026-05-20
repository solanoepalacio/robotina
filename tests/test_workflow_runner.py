"""Tests for queue/workflow_runner.py — workflow lifecycle (WF-04 through WF-09).

Unit tests: mocked session + queue (D-13).
"""
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from robotina.queue.models import WorkflowStatus, WorkflowStepStatus
from robotina.queue.task_types import RecipeResearchInput, RecipeLoadInput


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


def make_run(workflow_type="add-recipe", status=WorkflowStatus.PENDING, shared_context=None):
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

    # Phase 21 D-06: use add-recipe gather -> instructions transition.
    # instructions' build_input reads RecipeData(**artifacts['gather']).
    step = make_step(step_key="gather", task_type="recipe-research-gather",
                     status=WorkflowStepStatus.RUNNING)
    step.artifact = {"name": "spaghetti"}
    next_step = make_step(
        step_key="instructions", task_type="recipe-research-instructions",
        task_job_id=None,
    )
    run = make_run(
        workflow_type="add-recipe",
        shared_context={
            "household_id": "hh-1",
            "recipe_query": "spaghetti",
            "reply_context": {
                "platform": "telegram",
                "chat_id": "c1",
                "user_id": "u1",
            },
        },
    )

    session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    # first() returns: step (step lookup), run (run lookup), next_step (next PENDING step)
    query_mock.first.side_effect = [step, run, next_step]
    query_mock.all.return_value = [step]
    session.query.return_value = query_mock

    queue = MagicMock()
    # Output IS the artifact for this non-structured step. instructions'
    # build_input reads RecipeData(**artifacts['gather']) so the artifact
    # must be a valid RecipeData dump (only `name` is required).
    output = {"name": "spaghetti"}

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

    step = make_step(step_key="finalize-outcome", status=WorkflowStepStatus.RUNNING)
    run = make_run(workflow_type="add-recipe", shared_context={})

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


def test_extract_task_output_handles_return_direct_toolmessage():
    """Phase 07.1: when a return_direct=True terminal tool short-circuits the prebuilt
    langchain.agents.create_agent graph, the agent's final state has a ToolMessage as the last
    message — not a JSON-emitting AIMessage. _extract_task_output must surface the
    tool's return string instead of attempting (and failing) to JSON-parse the empty
    tool-call AIMessage that precedes it.
    """
    from robotina.queue.workflow_runner import _extract_task_output

    tool_msg = MagicMock()
    tool_msg.type = "tool"
    tool_msg.content = "Reply queued. job_id=abc"

    ai_msg = MagicMock()
    ai_msg.type = "ai"
    # Anthropic tool-use AIMessage: content is a list of blocks, no text block.
    ai_msg.content = [{"type": "tool_use", "name": "queue", "input": {"text": "..."}}]

    human_msg = MagicMock()
    human_msg.type = "human"
    human_msg.content = "user request"

    result = {"messages": [human_msg, ai_msg, tool_msg]}

    assert _extract_task_output(result, expects_structured=False) == {"tool_message": "Reply queued. job_id=abc"}


class _Toy(BaseModel):
    """Tiny Pydantic model used in structured-response branch tests (Phase 11)."""
    x: int
    y: str


def test_extract_returns_model_dump_when_structured_response_present():
    """WF-10: when expects_structured=True and result['structured_response'] is a
    Pydantic instance, _extract_task_output returns its model_dump(mode='json')."""
    from robotina.queue.workflow_runner import _extract_task_output

    result = {
        "messages": [],  # content irrelevant on structured path
        "structured_response": _Toy(x=1, y="hi"),
    }
    assert _extract_task_output(result, expects_structured=True) == {"x": 1, "y": "hi"}


def test_extract_raises_when_structured_expected_but_missing():
    """WF-10: when expects_structured=True and structured_response is None,
    _extract_task_output raises ValueError. No silent free-text fallback."""
    from robotina.queue.workflow_runner import _extract_task_output

    result = {"messages": [], "structured_response": None}
    with pytest.raises(ValueError, match="structured_response missing"):
        _extract_task_output(result, expects_structured=True)


def test_extract_raises_when_structured_expected_but_key_absent():
    """WF-10: when expects_structured=True and the 'structured_response' key
    is entirely absent, _extract_task_output also raises ValueError."""
    from robotina.queue.workflow_runner import _extract_task_output

    result = {"messages": []}
    with pytest.raises(ValueError, match="structured_response missing"):
        _extract_task_output(result, expects_structured=True)


def test_extract_raises_when_not_structured_and_no_tool_message():
    """WF-10: when expects_structured=False AND the last message is NOT a
    ToolMessage (no return_direct short-circuit), _extract_task_output
    raises ValueError. The legacy free-text JSON parse ladder is gone —
    non-structured agents that don't terminate via return_direct are a bug.
    """
    from robotina.queue.workflow_runner import _extract_task_output

    ai_msg = MagicMock()
    ai_msg.type = "ai"
    ai_msg.content = "some prose"
    result = {"messages": [ai_msg]}
    with pytest.raises(ValueError, match="no terminal ToolMessage"):
        _extract_task_output(result, expects_structured=False)


def test_on_step_complete_advances_after_return_direct_tool():
    """Phase 21 regression: when an agent terminates via a return_direct=True
    tool (e.g. TerminateTool), the final message is a ToolMessage. Before
    Phase 11's _extract_task_output fix, this caused ValueError on the
    empty tool-call AIMessage and the workflow halted.

    Drives on_step_complete with the return_direct shape on a non-structured
    final step (no next step) and asserts the step is DONE, the artifact
    is the {"tool_message": ...} fallback dict, and the workflow flips to
    DONE.

    (Previously regressed the legacy ack agent; that agent + its
    legacy queue tool are gone, so we test the same shape using a stubbed
    non-structured agent config and a final-step scenario to avoid
    coupling to the add-recipe step list.)
    """
    from robotina.queue.workflow_runner import on_step_complete

    step = make_step(step_key="finalize-outcome", task_type="finalize-outcome",
                     status=WorkflowStepStatus.RUNNING)
    run = make_run(workflow_type="add-recipe", shared_context={})

    session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    # first() returns: step (lookup), run (lookup), None (no next PENDING step)
    query_mock.first.side_effect = [step, run, None]
    query_mock.all.return_value = [step]
    session.query.return_value = query_mock

    queue = MagicMock()

    # Mirror what langchain.agents.create_agent leaves in state when a
    # return_direct=True tool runs: the tool-call AIMessage's content is a
    # list of tool_use blocks, and the final message is the ToolMessage.
    human_msg = MagicMock()
    human_msg.type = "human"
    human_msg.content = "Buscá la receta"

    ai_msg = MagicMock()
    ai_msg.type = "ai"
    ai_msg.content = [{"type": "tool_use", "name": "terminate", "input": {}}]

    tool_msg = MagicMock()
    tool_msg.type = "tool"
    tool_msg.content = "turn-terminated"

    output = {"messages": [human_msg, ai_msg, tool_msg]}

    # Force the non-structured path by stubbing get_agent_config.
    from unittest.mock import patch
    from robotina.agent.agents import AgentConfig
    fake_cfg = AgentConfig(task_type="x", model_config={}, prompt_path="p",
                           response_format_model=None)
    with patch("robotina.agent.agents.get_agent_config", return_value=fake_cfg):
        on_step_complete("test-job-id", output, session, queue)

    assert step.status == WorkflowStepStatus.DONE
    assert step.artifact == {"tool_message": "turn-terminated"}
    # Final step: workflow flips to DONE, no next-step enqueue.
    assert run.status == WorkflowStatus.DONE
    queue.enqueue.assert_not_called()


def test_reply_context_not_in_recipe_research_input():
    """WF-09: RecipeResearchInput has no reply_context field (enforced at model level)."""
    assert "reply_context" not in RecipeResearchInput.model_fields


def test_recipe_load_input_has_reply_context():
    """Phase 15 supersedes WF-09 for RecipeLoadInput.

    The accumulating-artifact contract collapses every downstream Recipe*Input
    to ``{recipe, reply_context, household_id}``; reply_context is threaded
    via ``build_input`` from ``shared_context``. ``RecipeResearchInput`` (the
    legacy single-shot task) is unchanged and still omits reply_context.
    """
    assert "reply_context" in RecipeLoadInput.model_fields


# ---------------------------------------------------------------------------
# Integration tests for hello-world-2step removed in Phase 6 cleanup —
# the workflow itself was removed from WORKFLOW_REGISTRY (see
# src/robotina/agent/workflows.py:11). End-to-end coverage of the workflow
# runner now lives in add-recipe integration tests.
# ---------------------------------------------------------------------------


def test_on_step_failed_logs_and_swallows_wake_helper_exception(caplog, monkeypatch):
    """Phase 21 D-08: when the wake helper raises, on_step_failed logs the
    exception and re-stamps the workflow FAILED in a fresh transaction —
    but DOES NOT enqueue any fallback send-notification. The Phase-20
    best-effort apology block is gone (wake-respond path supersedes it).

    Replaces the Phase-20 dead-letter fallback tests.
    """
    import logging
    from robotina.queue import workflow_runner
    from robotina.queue.workflow_runner import on_step_failed

    step = make_step(status=WorkflowStepStatus.RUNNING, workflow_run_id="run-xyz")
    run = make_run(
        workflow_type="add-recipe",
        status=WorkflowStatus.RUNNING,
        shared_context={
            "reply_context": {
                "platform": "telegram",
                "chat_id": "c1",
                "user_id": "u1",
            },
        },
    )

    session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    # Two pre-commit lookups (step + run); then the except branch re-fetches
    # step, pending list (all()), and run again — provide enough side_effect
    # entries.
    query_mock.first.side_effect = [step, run, step, run]
    query_mock.all.return_value = []
    session.query.return_value = query_mock

    queue = MagicMock()

    def _raise(*a, **kw):
        raise RuntimeError("simulated wake failure")
    monkeypatch.setattr(workflow_runner, "_check_and_dispatch_wake", _raise)

    with caplog.at_level(logging.ERROR, logger="robotina.queue.workflow_runner"):
        on_step_failed("test-job-id", session, queue)

    # Phase 21 D-08: NO fallback enqueue, regardless of reply_context.
    queue.enqueue.assert_not_called()
    # The exception was logged.
    assert any(
        "Wake dispatch failed in on_step_failed" in rec.getMessage()
        and "run-xyz" in rec.getMessage()
        for rec in caplog.records
    ), f"Expected wake-failure log mentioning run-xyz; got: {[r.getMessage() for r in caplog.records]}"
    # Workflow is still committed FAILED on the recovery path.
    session.commit.assert_called()


def test_on_step_failed_no_enqueue_when_reply_context_missing(monkeypatch):
    """Phase 21 D-08: even when shared_context lacks reply_context AND the
    wake helper raises, on_step_failed does NOT enqueue anything (the
    Phase-20 dead-letter block is gone).
    """
    from robotina.queue import workflow_runner
    from robotina.queue.workflow_runner import on_step_failed

    step = make_step(status=WorkflowStepStatus.RUNNING, workflow_run_id="run-abc")
    run = make_run(
        workflow_type="scheduled-thing",
        status=WorkflowStatus.RUNNING,
        shared_context={},  # no reply_context
    )

    session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.first.side_effect = [step, run, step, run]
    query_mock.all.return_value = []
    session.query.return_value = query_mock

    queue = MagicMock()

    def _raise(*a, **kw):
        raise RuntimeError("simulated wake failure")
    monkeypatch.setattr(workflow_runner, "_check_and_dispatch_wake", _raise)

    on_step_failed("test-job-id", session, queue)

    queue.enqueue.assert_not_called()


# ---------------------------------------------------------------------------
# Phase 13 / Plan 13-01: dashboard persistence columns
# ---------------------------------------------------------------------------


def test_workflow_run_step_model_has_new_columns():
    """DASH-01: WorkflowRunStep has step_input (JSON, nullable) and failure_reason
    (Text, nullable) columns added in migration 0005. Pure in-memory model
    inspection — no DB connection required."""
    from robotina.queue.models import WorkflowRunStep

    cols = WorkflowRunStep.__table__.columns
    assert "step_input" in cols, "step_input column missing on WorkflowRunStep"
    assert "failure_reason" in cols, "failure_reason column missing on WorkflowRunStep"
    # step_input is JSON-typed (python_type is dict)
    assert cols["step_input"].type.python_type is dict
    # both columns are nullable (migration safety: no full-table rewrite)
    assert cols["step_input"].nullable is True
    assert cols["failure_reason"].nullable is True


@pytest.mark.integration
def test_migration_0005_upgrades_and_downgrades():
    """DASH-01 AC #1: migration 0005 adds step_input + failure_reason as nullable
    columns; alembic downgrade -1 reverses cleanly; subsequent upgrade re-adds them.
    Touches the live test Postgres."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from robotina.db import SessionLocal

    cfg = Config("alembic.ini")

    # Upgrade explicitly to 0005 — isolates this test from later revisions
    # (Phase 17's 0006 and Phase 18's 0007 shift head; downgrade -1 from
    # head would test the wrong boundary). Pin both endpoints so the test
    # scope stays 0004<->0005 regardless of where head lives.
    command.upgrade(cfg, "0005")

    session = SessionLocal()
    try:
        rows = session.execute(
            text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = 'workflow_run_steps' "
                "AND column_name IN ('step_input', 'failure_reason')"
            )
        ).all()
        by_name = {r[0]: (r[1], r[2]) for r in rows}
        assert "step_input" in by_name, f"step_input missing after upgrade; columns: {by_name}"
        assert "failure_reason" in by_name, f"failure_reason missing after upgrade; columns: {by_name}"
        assert by_name["step_input"][0] == "json"
        assert by_name["failure_reason"][0] == "text"
        assert by_name["step_input"][1] == "YES"
        assert by_name["failure_reason"][1] == "YES"
    finally:
        session.close()

    # Downgrade to 0004: revert 0005. Both columns should be gone.
    command.downgrade(cfg, "0004")

    session = SessionLocal()
    try:
        rows = session.execute(
            text(
                "SELECT column_name "
                "FROM information_schema.columns "
                "WHERE table_name = 'workflow_run_steps' "
                "AND column_name IN ('step_input', 'failure_reason')"
            )
        ).all()
        names = {r[0] for r in rows}
        assert "step_input" not in names, "step_input still present after downgrade"
        assert "failure_reason" not in names, "failure_reason still present after downgrade"
    finally:
        session.close()

    # Re-apply so the DB is back at head for subsequent tests in the session.
    command.upgrade(cfg, "head")


# ---------------------------------------------------------------------------
# Phase 13 / Plan 13-01: workflow_runner wiring for step_input + failure_reason
# ---------------------------------------------------------------------------
# Note: these tests use the same mocked-session pattern as the existing
# WF-06/WF-08 tests above (e.g. test_on_step_complete_enqueues_next_step).
# The wiring being tested is purely "before .commit(), the code assigns
# step.step_input / step.failure_reason on the step instance" — directly
# observable on the MagicMock step object without a real Postgres session.
# Driving these via queue_workflow + live DB would add fixture surface area
# without strengthening the wiring assertions (Rule 3 deviation, scope-bounded).


def test_step_input_persisted_on_first_enqueue():
    """DASH-02: queue_workflow assigns step.step_input on the first step before
    queue.enqueue and session.commit. The value is the build_input output
    serialized via .model_dump(mode='json') when the input is a Pydantic model
    (mirrors the existing artifact serialization pattern at workflow_runner.py
    ~line 274-279).
    """
    from robotina.queue.workflow_runner import queue_workflow

    # Capture every step added to the session so we can find the first step
    # by step_key after queue_workflow returns.
    added_steps: list = []
    flushed_runs: list = []

    session = MagicMock()

    def _add(obj):
        # WorkflowRun is added first (no step_key), then steps.
        if hasattr(obj, "step_key") and obj.step_key:
            added_steps.append(obj)
        else:
            flushed_runs.append(obj)

    session.add.side_effect = _add
    # session.flush is a no-op for the mock; queue.enqueue is fully mocked.

    queue = MagicMock()
    queue.name = "agent-tasks"

    shared_context = {
        "household_id": "hh-1",
        "recipe_query": "spaghetti",
        "reply_context": {
            "platform": "telegram",
            "chat_id": "c1",
            "user_id": "u1",
        },
    }

    queue_workflow(
        workflow_type="add-recipe",
        shared_context=shared_context,
        household_id="hh-1",
        conversation_id="conv-1",
        triggered_by_invocation_id="inv-1",
        queue=queue,
        session=session,
    )

    # Phase 21 D-06: first step is "gather" (legacy acknowledge step deleted).
    gather_step = next(s for s in added_steps if s.step_key == "gather")
    # step_input was assigned BEFORE queue.enqueue (so the dashboard can read it).
    assert gather_step.step_input is not None, (
        "step_input not set on the first enqueued step"
    )
    # RecipeResearchGatherInput shape: query + reply_context + household_id.
    assert isinstance(gather_step.step_input, dict)
    assert gather_step.step_input.get("query") == "spaghetti"
    assert gather_step.step_input.get("household_id") == "hh-1"
    assert gather_step.step_input.get("reply_context") == shared_context["reply_context"]
    # queue.enqueue actually called
    assert queue.enqueue.called


def test_step_input_persisted_on_subsequent_enqueue():
    """DASH-02: on_step_complete assigns next_step.step_input before enqueue +
    commit, using the same Pydantic-aware serialization pattern as the
    first-step site.
    """
    from robotina.queue.workflow_runner import on_step_complete

    # Phase 21 D-06: gather -> instructions transition. instructions'
    # build_input reads RecipeData(**artifacts['gather']).
    step = make_step(step_key="gather", task_type="recipe-research-gather",
                     status=WorkflowStepStatus.RUNNING)
    step.artifact = {"name": "spaghetti"}
    next_step = make_step(
        step_key="instructions", task_type="recipe-research-instructions",
        task_job_id=None,
    )
    # Explicit attribute so the assertion against None has a distinguishable
    # baseline (vs MagicMock's auto-created attribute behavior).
    next_step.step_input = None

    run = make_run(
        workflow_type="add-recipe",
        shared_context={
            "household_id": "hh-1",
            "recipe_query": "spaghetti",
            "reply_context": {
                "platform": "telegram",
                "chat_id": "c1",
                "user_id": "u1",
            },
        },
    )

    session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    query_mock.first.side_effect = [step, run, next_step]
    query_mock.all.return_value = [step]
    session.query.return_value = query_mock

    queue = MagicMock()
    # Use a plain-dict artifact so _extract_task_output takes the
    # non-structured branch (output is not {"messages": ...} so it falls to
    # the elif isinstance(output, dict) path).
    output = {"name": "spaghetti"}

    on_step_complete("test-job-id", output, session, queue)

    assert next_step.step_input is not None, (
        "step_input not set on the next enqueued step"
    )
    assert isinstance(next_step.step_input, dict)
    # RecipeResearchInstructionsInput shape: recipe + reply_context + household_id.
    assert next_step.step_input.get("recipe", {}).get("name") == "spaghetti"
    assert next_step.step_input.get("household_id") == "hh-1"
    assert queue.enqueue.called


def test_failure_reason_set_with_exception_format_and_single_line():
    """DASH-03: on_step_failed, when called with exc=<Exception>, sets
    step.failure_reason to f'{type(exc).__name__}: {exc}' with embedded
    newlines collapsed to spaces and trailing whitespace stripped
    (RESEARCH Pitfall 2). When called WITHOUT exc=, leaves failure_reason
    untouched (backward compat for the legacy direct-task callers).
    """
    from robotina.queue.workflow_runner import on_step_failed

    # --- case 1: with exc=, multi-line message -> single line ---
    step = make_step(status=WorkflowStepStatus.RUNNING)
    step.failure_reason = None  # explicit baseline
    pending_step = make_step(step_key="step2", status=WorkflowStepStatus.PENDING)
    pending_step.failure_reason = None
    run = make_run(status=WorkflowStatus.RUNNING)

    session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.first.side_effect = [step, run]
    query_mock.all.return_value = [pending_step]
    session.query.return_value = query_mock

    on_step_failed(
        "test-job-id",
        session,
        queue=None,
        exc=ValueError("multi\nline\nmessage"),
    )

    assert step.status == WorkflowStepStatus.FAILED
    assert step.failure_reason == "ValueError: multi line message", (
        f"unexpected failure_reason format: {step.failure_reason!r}"
    )
    # Cancelled sibling step retains NULL failure_reason (SPEC AC #3).
    assert pending_step.status == WorkflowStepStatus.CANCELLED
    assert pending_step.failure_reason is None

    # --- case 2: without exc= (legacy caller / direct task) -> leaves NULL ---
    step2 = make_step(status=WorkflowStepStatus.RUNNING)
    step2.failure_reason = None
    run2 = make_run(status=WorkflowStatus.RUNNING)

    session2 = MagicMock()
    query_mock2 = MagicMock()
    query_mock2.filter.return_value = query_mock2
    query_mock2.first.side_effect = [step2, run2]
    query_mock2.all.return_value = []
    session2.query.return_value = query_mock2

    on_step_failed("test-job-id", session2)  # no exc, no queue

    assert step2.status == WorkflowStepStatus.FAILED
    assert step2.failure_reason is None, (
        "legacy caller (no exc=) must leave failure_reason untouched (NULL)"
    )


# ---------------------------------------------------------------------------
# Phase 16 — REQ-HID-4: queue_workflow rejects empty household_id BEFORE any
# DB write
# ---------------------------------------------------------------------------

def test_queue_workflow_rejects_empty_household_id():
    """queue_workflow with household_id='' raises ValueError and does NOT write to DB (REQ-HID-4)."""
    from unittest.mock import MagicMock
    import pytest

    from robotina.queue.workflow_runner import queue_workflow

    mock_session = MagicMock()
    mock_queue = MagicMock()

    with pytest.raises(ValueError) as exc_info:
        queue_workflow(
            workflow_type="add-recipe",
            shared_context={"reply_context": {"platform": "telegram", "chat_id": "c1", "user_id": "u1"}},
            household_id="",
            conversation_id="conv-1",
            triggered_by_invocation_id="inv-1",
            queue=mock_queue,
            session=mock_session,
        )

    assert "household_id" in str(exc_info.value)
    # Critical: NO DB writes happened — the guard ran before session.add / session.flush
    mock_session.add.assert_not_called()
    mock_session.flush.assert_not_called()
    mock_session.commit.assert_not_called()
    mock_queue.enqueue.assert_not_called()


def test_queue_workflow_rejects_whitespace_household_id():
    """queue_workflow with household_id='   ' raises ValueError and does NOT write to DB."""
    from unittest.mock import MagicMock
    import pytest

    from robotina.queue.workflow_runner import queue_workflow

    mock_session = MagicMock()
    mock_queue = MagicMock()

    with pytest.raises(ValueError) as exc_info:
        queue_workflow(
            workflow_type="add-recipe",
            shared_context={"reply_context": {"platform": "telegram", "chat_id": "c1", "user_id": "u1"}},
            household_id="   ",
            conversation_id="conv-1",
            triggered_by_invocation_id="inv-1",
            queue=mock_queue,
            session=mock_session,
        )

    assert "household_id" in str(exc_info.value)
    mock_session.add.assert_not_called()
    mock_queue.enqueue.assert_not_called()


# ---------------------------------------------------------------------------
# Phase 17 / ARCH-01: Conversation FK + outcome column
# ---------------------------------------------------------------------------
# Wave 0 RED-state lock tests. These tests encode the Phase 17 contracts BEFORE
# the source changes. Each test below FAILS at commit time of this plan and
# turns GREEN as the relevant wave lands:
#   - schema-introspection tests  -> GREEN after Wave 1 (Plan 17-02)
#   - signature/ctor/lookup tests -> GREEN after Wave 2 (Plan 17-03)
#   - ARCH-05 regression guard    -> GREEN after Wave 2 and STAYS green forever


def test_workflow_run_has_conversation_id_column():
    """ARCH-01: WorkflowRun has conversation_id (String, NOT NULL, FK to conversations.id) added in migration 0006.

    Pure in-memory model inspection — no DB connection required.
    """
    from robotina.queue.models import WorkflowRun

    cols = WorkflowRun.__table__.columns
    assert "conversation_id" in cols, "conversation_id column missing on WorkflowRun"
    assert cols["conversation_id"].type.python_type is str
    assert cols["conversation_id"].nullable is False, "conversation_id must be NOT NULL (D-01)"
    fks = list(cols["conversation_id"].foreign_keys)
    assert len(fks) >= 1, "conversation_id must declare at least one ForeignKey"
    assert any("conversations.id" in str(fk.target_fullname) for fk in fks), (
        f"conversation_id FK target must be conversations.id; got {[str(fk.target_fullname) for fk in fks]}"
    )


def test_workflow_run_has_outcome_column():
    """D-06: WorkflowRun has outcome (JSON, nullable) — slot for Phase 20 AddRecipeOutcome."""
    from robotina.queue.models import WorkflowRun

    cols = WorkflowRun.__table__.columns
    assert "outcome" in cols, "outcome column missing on WorkflowRun"
    assert cols["outcome"].type.python_type is dict
    assert cols["outcome"].nullable is True


@pytest.mark.integration
def test_migration_0006_upgrades_and_downgrades():
    """ARCH-01 AC: migration 0006 adds conversation_id (varchar NOT NULL, FK to
    conversations.id) and outcome (json, NULL) on workflow_runs. alembic downgrade
    -1 reverses cleanly; subsequent upgrade re-adds them. Touches the live test
    Postgres.
    """
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from robotina.db import SessionLocal

    cfg = Config("alembic.ini")

    # Upgrade explicitly to 0006 — this isolates the test from later revisions
    # (e.g. Phase 18's 0007 shifts ``head``; downgrade -1 from head would test
    # the wrong boundary). Targeting 0006 + downgrade to 0005 keeps this test
    # scoped to the 0005<->0006 transition regardless of where head lives.
    command.upgrade(cfg, "0006")

    session = SessionLocal()
    try:
        rows = session.execute(
            text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = 'workflow_runs' "
                "AND column_name IN ('conversation_id', 'outcome')"
            )
        ).all()
        by_name = {r[0]: (r[1], r[2]) for r in rows}
        assert "conversation_id" in by_name, f"conversation_id missing after upgrade; columns: {by_name}"
        assert "outcome" in by_name, f"outcome missing after upgrade; columns: {by_name}"
        assert by_name["conversation_id"][0] == "character varying"
        assert by_name["conversation_id"][1] == "NO"
        assert by_name["outcome"][0] == "json"
        assert by_name["outcome"][1] == "YES"
    finally:
        session.close()

    # Downgrade to 0005: revert 0006. Both columns should be gone.
    command.downgrade(cfg, "0005")

    session = SessionLocal()
    try:
        rows = session.execute(
            text(
                "SELECT column_name "
                "FROM information_schema.columns "
                "WHERE table_name = 'workflow_runs' "
                "AND column_name IN ('conversation_id', 'outcome')"
            )
        ).all()
        names = {r[0] for r in rows}
        assert "conversation_id" not in names, "conversation_id still present after downgrade"
        assert "outcome" not in names, "outcome still present after downgrade"
    finally:
        session.close()

    # Re-apply so the DB is back at head for subsequent tests in the session.
    command.upgrade(cfg, "head")


def test_queue_workflow_persists_conversation_id():
    """ARCH-01: queue_workflow assigns conversation_id on the WorkflowRun before commit."""
    from robotina.queue.workflow_runner import queue_workflow

    added_runs: list = []
    added_steps: list = []
    session = MagicMock()

    def _add(obj):
        if hasattr(obj, "step_key") and obj.step_key:
            added_steps.append(obj)
        else:
            added_runs.append(obj)

    session.add.side_effect = _add
    queue = MagicMock()
    queue.name = "agent-tasks"

    shared_context = {
        "household_id": "hh-1",
        "recipe_query": "spaghetti",
        "reply_context": {"platform": "telegram", "chat_id": "c1", "user_id": "u1"},
    }

    queue_workflow(
        workflow_type="add-recipe",
        shared_context=shared_context,
        household_id="hh-1",
        conversation_id="conv-1",
        triggered_by_invocation_id="inv-1",
        queue=queue,
        session=session,
    )

    assert len(added_runs) == 1, f"expected 1 WorkflowRun added, got {added_runs}"
    assert added_runs[0].conversation_id == "conv-1"


def test_queue_workflow_requires_conversation_id():
    """D-05: queue_workflow signature gains required conversation_id arg (no default).

    Missing arg = TypeError at call time (no Python-level guard — FK + .one() upstream
    cover the invariant).
    """
    from unittest.mock import MagicMock
    import pytest

    from robotina.queue.workflow_runner import queue_workflow

    mock_session = MagicMock()
    mock_queue = MagicMock()

    with pytest.raises(TypeError) as exc_info:
        queue_workflow(
            workflow_type="add-recipe",
            shared_context={"reply_context": {"platform": "telegram", "chat_id": "c1", "user_id": "u1"}},
            household_id="hh-1",
            queue=mock_queue,
            session=mock_session,
        )
    assert "conversation_id" in str(exc_info.value)


def test_shared_context_reply_context_still_written():
    """ARCH-05 deprecation window: StartWorkflowTool must continue to write reply_context
    into shared_context (workflow steps' build_input read it).
    This test guards against premature removal of reply_context writes.

    Phase 21 D-08: the legacy dead-letter block that also read
    shared_context.reply_context is gone, but the workflow-step
    consumers (gather/instructions/ingredients/metadata/load
    build_input lambdas) still rely on it, so the write must stay.

    Plan 21-03 reshaped StartWorkflowTool._run to take a typed
    AddRecipeQueryInput; this test now passes that shape.
    """
    from unittest.mock import MagicMock, patch
    from robotina.agent.tools.start_workflow import StartWorkflowTool
    from robotina.queue.task_types import AddRecipeQueryInput

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram",
        household_id="hh-1", conversation_id="conv-1",
        invocation_id="inv-test",  # Phase 18 D-13: required ctor field
    )

    captured = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return "wf-run-id-1"

    with patch("robotina.queue.workflow_runner.queue_workflow", side_effect=_capture):
        with patch("robotina.db.SessionLocal", return_value=MagicMock()):
            with patch("rq.Queue"), patch("redis.Redis"):
                tool._run(
                    workflow_type="add-recipe",
                    input=AddRecipeQueryInput(value="carbonara"),
                )

    assert "shared_context" in captured
    rc = captured["shared_context"].get("reply_context")
    assert rc == {"platform": "telegram", "chat_id": "c1", "user_id": "u1"}, (
        f"reply_context must still be written into shared_context (ARCH-05 deprecation window); got {rc!r}"
    )


# ---------------------------------------------------------------------------
# Phase 18 / ARCH-02 + ARCH-03 — RED tests (Wave 0)
# ---------------------------------------------------------------------------
# Will be GREEN after Wave 2 lands the queue_workflow signature change.


def test_queue_workflow_requires_triggered_by_invocation_id():
    """D-14: queue_workflow signature gains REQUIRED triggered_by_invocation_id arg
    (no default, no fallback). Calling without it must raise TypeError. Mirrors the
    Phase 17 conversation_id required-arg test (lines 991-1013)."""
    from unittest.mock import MagicMock
    from robotina.queue.workflow_runner import queue_workflow

    shared_context = {
        "household_id": "hh-1",
        "recipe_query": "lentejas",
        "reply_context": {"platform": "telegram", "chat_id": "c1", "user_id": "u1"},
    }
    with pytest.raises(TypeError):
        queue_workflow(
            workflow_type="add-recipe",
            shared_context=shared_context,
            household_id="hh-1",
            conversation_id="conv-1",
            # triggered_by_invocation_id intentionally omitted — must TypeError
            queue=MagicMock(),
            session=MagicMock(),
        )


def test_queue_workflow_persists_triggered_by_invocation_id():
    """D-23: queue_workflow assigns triggered_by_invocation_id on the WorkflowRun
    row before commit. Mirrors Phase 17 test_queue_workflow_persists_conversation_id
    (lines 954-988)."""
    from robotina.queue.workflow_runner import queue_workflow

    added_runs: list = []
    added_steps: list = []

    def _add(obj):
        if hasattr(obj, "step_key") and obj.step_key:
            added_steps.append(obj)
        else:
            added_runs.append(obj)

    session = MagicMock()
    session.add.side_effect = _add
    queue = MagicMock()
    queue.name = "agent-tasks"

    shared_context = {
        "household_id": "hh-1",
        "recipe_query": "lentejas",
        "reply_context": {"platform": "telegram", "chat_id": "c1", "user_id": "u1"},
    }

    queue_workflow(
        workflow_type="add-recipe",
        shared_context=shared_context,
        household_id="hh-1",
        conversation_id="conv-1",
        triggered_by_invocation_id="inv-1",
        queue=queue,
        session=session,
    )

    assert len(added_runs) == 1
    assert added_runs[0].triggered_by_invocation_id == "inv-1"
    assert added_runs[0].conversation_id == "conv-1"  # Phase 17 still wired


@pytest.mark.integration
def test_migration_0007_upgrades_and_downgrades():
    """D-23: 0007_robotina_invocations upgrade creates the table + the new FK
    column; downgrade removes both. Mirrors Phase 17 test_migration_0006_*
    (lines 893-948)."""
    import importlib.util

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect, text

    from robotina.db import SessionLocal

    # Import the migration module by file path (Alembic versions aren't a package)
    # to lock the revision identifiers — this part runs even without DB access.
    spec = importlib.util.spec_from_file_location(
        "m0007", "migrations/versions/0007_robotina_invocations.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.revision == "0007"
    assert mod.down_revision == "0006"

    cfg = Config("alembic.ini")

    # Ensure DB is at head (0007) — starting precondition AND upgrade-path exercise.
    command.upgrade(cfg, "head")

    session = SessionLocal()
    try:
        conn = session.connection()
        insp = inspect(conn)

        # Table exists.
        assert insp.has_table("robotina_invocations"), (
            "robotina_invocations table missing after upgrade"
        )

        # FK column exists and is nullable.
        wf_cols = {c["name"]: c for c in insp.get_columns("workflow_runs")}
        assert "triggered_by_invocation_id" in wf_cols, (
            f"triggered_by_invocation_id missing after upgrade; columns: {list(wf_cols)}"
        )
        assert wf_cols["triggered_by_invocation_id"]["nullable"] is True, (
            "D-02: triggered_by_invocation_id must be NULLABLE"
        )

        # Named unique constraint exists with the expected column set (order-insensitive).
        uniques = insp.get_unique_constraints("robotina_invocations")
        matching = [
            u for u in uniques
            if u["name"] == "ux_invocation_workflow_completion_once"
            and set(u["column_names"]) == {"trigger_ref_id", "trigger"}
        ]
        assert len(matching) == 1, (
            f"D-08: expected ux_invocation_workflow_completion_once constraint; got {uniques}"
        )

        # Confirm ENUM types are present in pg_type.
        types = {
            r[0] for r in conn.execute(
                text("SELECT typname FROM pg_type WHERE typname IN ('invocationtrigger', 'invocationstatus')")
            ).all()
        }
        assert types == {"invocationtrigger", "invocationstatus"}, (
            f"expected both enum types created; got {types}"
        )
    finally:
        session.close()

    # Downgrade -1: revert 0007 -> 0006. Table + FK column should be gone.
    command.downgrade(cfg, "-1")

    session = SessionLocal()
    try:
        conn = session.connection()
        insp = inspect(conn)
        assert not insp.has_table("robotina_invocations"), (
            "robotina_invocations still present after downgrade"
        )
        wf_cols = {c["name"] for c in insp.get_columns("workflow_runs")}
        assert "triggered_by_invocation_id" not in wf_cols, (
            "triggered_by_invocation_id still present on workflow_runs after downgrade"
        )
    finally:
        session.close()

    # Re-apply so the DB is back at head for subsequent tests in the session.
    command.upgrade(cfg, "head")
