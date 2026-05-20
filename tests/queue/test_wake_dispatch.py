"""Wake-helper unit tests + D-18 integration test.

The 9 unit tests at the top use the real Postgres ``db_session`` fixture
(integration-friendly: the helper performs RAW SQL UPDATE-RETURNING which
won't run on a mocked session). The final test
``test_on_step_complete_dispatches_wake_end_to_end`` is marked
``@pytest.mark.integration`` because it drives ``on_step_complete`` rather
than the helper directly, exercising the full wiring chain from
Plan 20-03 Task 3.2.
"""
from __future__ import annotations

import pytest

from sqlalchemy import text

from robotina.gateway.models import Conversation
from robotina.queue import workflow_runner
from robotina.queue.workflow_runner import _check_and_dispatch_wake
from robotina.queue.models import (
    InvocationStatus,
    InvocationTrigger,
    RobotinaInvocation,
    WorkflowRun,
    WorkflowRunStep,
    WorkflowStatus,
    WorkflowStepStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _cleanup_workflow_tables(db_session):
    """Clean workflow_run_steps + workflow_runs before AND after each test.

    The standard conftest db_session cleanup only handles
    robotina_invocations + stored_messages + conversations, but this test
    file inserts workflow_runs that FK-reference conversations. Clean those
    here so the conversation DELETE in the conftest finalizer succeeds.
    """
    db_session.execute(text("DELETE FROM workflow_run_steps"))
    db_session.execute(text("DELETE FROM workflow_runs"))
    db_session.commit()
    yield
    db_session.execute(text("DELETE FROM workflow_run_steps"))
    db_session.execute(text("DELETE FROM workflow_runs"))
    db_session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeQueue:
    name = "agent-tasks"

    def __init__(self):
        self.enqueued: list[tuple[tuple, dict]] = []

    def enqueue(self, *args, **kwargs):
        self.enqueued.append((args, kwargs))


def _make_conversation(session) -> Conversation:
    conv = Conversation(platform="telegram", chat_id="c-wake",
                        household_id="test-household")
    session.add(conv)
    session.flush()
    return conv


def _make_parent_invocation(session, conv_id: str) -> RobotinaInvocation:
    inv = RobotinaInvocation(
        conversation_id=conv_id,
        trigger=InvocationTrigger.USER_MESSAGE,
        status=InvocationStatus.RUNNING,
    )
    session.add(inv)
    session.flush()
    return inv


def _make_run(
    session,
    *,
    conv_id: str,
    parent_inv_id: str,
    status: WorkflowStatus = WorkflowStatus.DONE,
    outcome: dict | None = None,
    workflow_type: str = "add-recipe",
) -> WorkflowRun:
    run = WorkflowRun(
        workflow_type=workflow_type,
        household_id="test-household",
        conversation_id=conv_id,
        triggered_by_invocation_id=parent_inv_id,
        status=status,
        shared_context={},
        outcome=outcome,
    )
    session.add(run)
    session.flush()
    return run


# ---------------------------------------------------------------------------
# Unit tests for _check_and_dispatch_wake (D-17)
# ---------------------------------------------------------------------------


def test_wake_fires_on_single_done_workflow(db_session):
    """Single DONE workflow → wake fires; rq_job_id is pre-assigned (D-17)."""
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)
    _make_run(session, conv_id=conv.id, parent_inv_id=parent.id,
              status=WorkflowStatus.DONE)

    fake_queue = FakeQueue()
    _check_and_dispatch_wake(parent.id, session, fake_queue)
    session.commit()

    # Parent has wake_dispatched_at set.
    session.refresh(parent)
    assert parent.wake_dispatched_at is not None

    # Exactly one new WORKFLOW_COMPLETION invocation row.
    wake_rows = (session.query(RobotinaInvocation)
                 .filter_by(trigger=InvocationTrigger.WORKFLOW_COMPLETION).all())
    assert len(wake_rows) == 1
    saved_inv = wake_rows[0]
    assert saved_inv.trigger_ref_id == parent.id
    assert saved_inv.conversation_id == conv.id
    assert saved_inv.status == InvocationStatus.PENDING

    # Invariant A (D-17): rq_job_id is set on the row before commit.
    assert saved_inv.rq_job_id is not None
    # Invariant B (D-17): the row's rq_job_id matches the enqueued job's id —
    # confirms pre-assignment (Pitfall 11), not post-assignment.
    enqueued_kwargs = fake_queue.enqueued[0][1]
    assert saved_inv.rq_job_id == enqueued_kwargs["job_id"]

    # Enqueue meta carries new invocation_id.
    assert enqueued_kwargs["meta"]["invocation_id"] == saved_inv.id
    assert enqueued_kwargs["meta"]["task_type"] == "handle-incoming-message"
    assert enqueued_kwargs["result_ttl"] == -1
    assert enqueued_kwargs["failure_ttl"] == -1


def test_wake_fires_when_all_three_done(db_session):
    """3 sibling DONE workflows → exactly one wake invocation."""
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)
    for _ in range(3):
        _make_run(session, conv_id=conv.id, parent_inv_id=parent.id,
                  status=WorkflowStatus.DONE)

    fake_queue = FakeQueue()
    _check_and_dispatch_wake(parent.id, session, fake_queue)
    session.commit()

    wake_rows = (session.query(RobotinaInvocation)
                 .filter_by(trigger=InvocationTrigger.WORKFLOW_COMPLETION).all())
    assert len(wake_rows) == 1
    assert len(fake_queue.enqueued) == 1


def test_wake_skips_on_partial(db_session):
    """2 DONE + 1 PENDING → no wake."""
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)
    _make_run(session, conv_id=conv.id, parent_inv_id=parent.id,
              status=WorkflowStatus.DONE)
    _make_run(session, conv_id=conv.id, parent_inv_id=parent.id,
              status=WorkflowStatus.DONE)
    _make_run(session, conv_id=conv.id, parent_inv_id=parent.id,
              status=WorkflowStatus.PENDING)

    fake_queue = FakeQueue()
    _check_and_dispatch_wake(parent.id, session, fake_queue)
    session.commit()

    wake_rows = (session.query(RobotinaInvocation)
                 .filter_by(trigger=InvocationTrigger.WORKFLOW_COMPLETION).all())
    assert wake_rows == []
    assert fake_queue.enqueued == []
    session.refresh(parent)
    assert parent.wake_dispatched_at is None


def test_wake_fires_on_failed(db_session):
    """Single FAILED workflow → wake still fires (parity with DONE)."""
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)
    _make_run(session, conv_id=conv.id, parent_inv_id=parent.id,
              status=WorkflowStatus.FAILED)

    fake_queue = FakeQueue()
    _check_and_dispatch_wake(parent.id, session, fake_queue)
    session.commit()

    wake_rows = (session.query(RobotinaInvocation)
                 .filter_by(trigger=InvocationTrigger.WORKFLOW_COMPLETION).all())
    assert len(wake_rows) == 1
    assert len(fake_queue.enqueued) == 1


def test_wake_idempotent(db_session):
    """Two consecutive calls → only ONE new invocation (UPDATE-RETURNING 0-rows
    second time around).
    """
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)
    _make_run(session, conv_id=conv.id, parent_inv_id=parent.id,
              status=WorkflowStatus.DONE)

    fake_queue = FakeQueue()
    _check_and_dispatch_wake(parent.id, session, fake_queue)
    session.commit()
    _check_and_dispatch_wake(parent.id, session, fake_queue)
    session.commit()

    wake_rows = (session.query(RobotinaInvocation)
                 .filter_by(trigger=InvocationTrigger.WORKFLOW_COMPLETION).all())
    assert len(wake_rows) == 1
    assert len(fake_queue.enqueued) == 1


def test_wake_queue_none_skips_enqueue(db_session):
    """queue=None → row inserted with rq_job_id + wake_dispatched_at; no enqueue.
    Reconciler will pick it up on next boot (D-11).
    """
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)
    _make_run(session, conv_id=conv.id, parent_inv_id=parent.id,
              status=WorkflowStatus.DONE)

    _check_and_dispatch_wake(parent.id, session, None)
    session.commit()

    session.refresh(parent)
    assert parent.wake_dispatched_at is not None
    wake_rows = (session.query(RobotinaInvocation)
                 .filter_by(trigger=InvocationTrigger.WORKFLOW_COMPLETION).all())
    assert len(wake_rows) == 1
    assert wake_rows[0].rq_job_id is not None


def test_wake_outcomes_passed_to_enqueue(db_session):
    """Outcome JSON is validated via AddRecipeOutcome and passed in the
    WakeInvocationInput payload.
    """
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)
    _make_run(
        session,
        conv_id=conv.id,
        parent_inv_id=parent.id,
        status=WorkflowStatus.DONE,
        outcome={
            "status": "success",
            "recipe_id": "abc-123",
            "recipe_name": "Lentejas",
            "recipe_slug": "lentejas",
            "image_present": False,
        },
    )

    fake_queue = FakeQueue()
    _check_and_dispatch_wake(parent.id, session, fake_queue)
    session.commit()

    args, _ = fake_queue.enqueued[0]
    # args[0] is the dotted path; args[1] is the WakeInvocationInput payload.
    wake_input = args[1]
    assert wake_input.previous_invocation_id == parent.id
    assert wake_input.conversation_id == conv.id
    assert len(wake_input.outcomes) == 1
    assert wake_input.outcomes[0].outcome is not None
    assert wake_input.outcomes[0].outcome.recipe_name == "Lentejas"
    assert wake_input.outcomes[0].status == "done"


def test_wake_invocation_id_none_returns(db_session):
    """Helper called with invocation_id=None → no DB writes, no enqueue."""
    session = db_session
    fake_queue = FakeQueue()

    _check_and_dispatch_wake(None, session, fake_queue)
    session.commit()

    wake_rows = (session.query(RobotinaInvocation)
                 .filter_by(trigger=InvocationTrigger.WORKFLOW_COMPLETION).all())
    assert wake_rows == []
    assert fake_queue.enqueued == []


def test_wake_no_siblings_returns(db_session):
    """Real invocation_id but zero linked WorkflowRuns → no enqueue."""
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)
    # No WorkflowRuns inserted.

    fake_queue = FakeQueue()
    _check_and_dispatch_wake(parent.id, session, fake_queue)
    session.commit()

    wake_rows = (session.query(RobotinaInvocation)
                 .filter_by(trigger=InvocationTrigger.WORKFLOW_COMPLETION).all())
    assert wake_rows == []
    assert fake_queue.enqueued == []
    session.refresh(parent)
    assert parent.wake_dispatched_at is None


# ---------------------------------------------------------------------------
# D-18 integration test — drives on_step_complete end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_on_step_complete_dispatches_wake_end_to_end(db_session):
    """D-18: real-Postgres test that on_step_complete drives the wake chain.

    Catches wiring bugs that pure unit tests of _check_and_dispatch_wake
    cannot see (e.g., helper not called from the final-step branch, commit
    ordering, status-flip visibility to the helper's sibling SELECT).
    """
    session = db_session

    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)

    run = WorkflowRun(
        workflow_type="add-recipe",
        household_id="test-household",
        conversation_id=conv.id,
        triggered_by_invocation_id=parent.id,
        status=WorkflowStatus.RUNNING,
        shared_context={},
    )
    session.add(run)
    session.flush()

    # Final step (no PENDING successor) — drives the final-DONE branch in
    # on_step_complete that calls the wake helper.
    step = WorkflowRunStep(
        workflow_run_id=run.id,
        step_key="finalize-outcome",
        step_order=0,
        task_type="finalize-outcome",
        status=WorkflowStepStatus.RUNNING,
        task_job_id="job-final-int",
    )
    session.add(step)
    session.commit()

    assert parent.wake_dispatched_at is None

    fake_queue = FakeQueue()

    # Drive the wiring under test. on_step_complete commits internally.
    workflow_runner.on_step_complete(
        job_id="job-final-int",
        output={"result": "ok"},
        session=session,
        queue=fake_queue,
    )

    # Re-fetch state from DB to bypass session identity-map caching.
    session.expire_all()
    parent_after = session.get(RobotinaInvocation, parent.id)
    run_after = session.get(WorkflowRun, run.id)

    assert parent_after.wake_dispatched_at is not None
    assert run_after.status == WorkflowStatus.DONE

    wake_rows = (session.query(RobotinaInvocation)
                 .filter_by(trigger=InvocationTrigger.WORKFLOW_COMPLETION,
                            trigger_ref_id=parent.id)
                 .all())
    assert len(wake_rows) == 1
    new_inv = wake_rows[0]
    assert new_inv.rq_job_id is not None
    assert new_inv.status == InvocationStatus.PENDING
    assert len(fake_queue.enqueued) == 1
    enqueued_kwargs = fake_queue.enqueued[0][1]
    assert enqueued_kwargs["job_id"] == new_inv.rq_job_id
