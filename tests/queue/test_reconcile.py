"""Reconciler tests (D-21 / WAKE-05).

Covers:
- Orphan rows (status=PENDING, wake_dispatched_at set, rq_job_id set, no live RQ
  job) → re-enqueued with the same job_id.
- Non-orphan (RQ job exists) → no-op.
- Non-WAKE trigger row in candidate set → skipped (defensive).
- Non-PENDING status → not selected.
- Empty state → returns 0, no enqueue.
- Per-row exception → logged and loop continues with the next row.
- Outcomes rebuild: sibling WorkflowRuns are folded into WakeInvocationInput.outcomes.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text

from robotina.gateway.models import Conversation
from robotina.queue.models import (
    InvocationStatus,
    InvocationTrigger,
    RobotinaInvocation,
    WorkflowRun,
    WorkflowStatus,
)
from robotina.queue.reconcile import reconcile_invocations


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _cleanup_workflow_tables(db_session):
    """Clean workflow_runs before AND after each test so the conftest
    conversation DELETE finalizer succeeds (workflow_runs FK -> conversations)."""
    db_session.execute(text("DELETE FROM workflow_run_steps"))
    db_session.execute(text("DELETE FROM workflow_runs"))
    db_session.commit()
    yield
    db_session.execute(text("DELETE FROM workflow_run_steps"))
    db_session.execute(text("DELETE FROM workflow_runs"))
    db_session.commit()


class FakeQueue:
    name = "agent-tasks"

    def __init__(self):
        self.connection = MagicMock()
        self.enqueued: list[tuple[tuple, dict]] = []

    def enqueue(self, *args, **kwargs):
        self.enqueued.append((args, kwargs))


def _make_conversation(session) -> Conversation:
    conv = Conversation(platform="telegram", chat_id="c-recon",
                        household_id="test-household")
    session.add(conv)
    session.flush()
    return conv


def _make_parent_invocation(session, conv_id: str) -> RobotinaInvocation:
    inv = RobotinaInvocation(
        conversation_id=conv_id,
        trigger=InvocationTrigger.USER_MESSAGE,
        status=InvocationStatus.DONE,
    )
    session.add(inv)
    session.flush()
    return inv


def _make_orphan_wake_invocation(
    session,
    *,
    conv_id: str,
    parent_inv_id: str,
    rq_job_id: str = "rqX",
    status: InvocationStatus = InvocationStatus.PENDING,
    trigger: InvocationTrigger = InvocationTrigger.WORKFLOW_COMPLETION,
    wake_dispatched: bool = True,
) -> RobotinaInvocation:
    from datetime import datetime
    inv = RobotinaInvocation(
        conversation_id=conv_id,
        trigger=trigger,
        trigger_ref_id=parent_inv_id,
        rq_job_id=rq_job_id,
        status=status,
        wake_dispatched_at=datetime.utcnow() if wake_dispatched else None,
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
# Tests
# ---------------------------------------------------------------------------


def test_reconcile_reenqueues_orphan(db_session):
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)
    _make_run(session, conv_id=conv.id, parent_inv_id=parent.id,
              status=WorkflowStatus.DONE)
    orphan = _make_orphan_wake_invocation(
        session, conv_id=conv.id, parent_inv_id=parent.id, rq_job_id="rqX",
    )
    session.commit()

    fake_queue = FakeQueue()
    with patch("robotina.queue.reconcile.Job.exists", return_value=False):
        result = reconcile_invocations(session, fake_queue)

    assert result == 1
    assert len(fake_queue.enqueued) == 1
    args, kwargs = fake_queue.enqueued[0]
    assert kwargs["job_id"] == "rqX"
    assert kwargs["meta"]["invocation_id"] == orphan.id
    assert kwargs["meta"]["task_type"] == "handle-incoming-message"
    assert kwargs["result_ttl"] == -1
    assert kwargs["failure_ttl"] == -1


def test_reconcile_skips_live_job(db_session):
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)
    _make_run(session, conv_id=conv.id, parent_inv_id=parent.id,
              status=WorkflowStatus.DONE)
    _make_orphan_wake_invocation(
        session, conv_id=conv.id, parent_inv_id=parent.id, rq_job_id="rqLive",
    )
    session.commit()

    fake_queue = FakeQueue()
    with patch("robotina.queue.reconcile.Job.exists", return_value=True):
        result = reconcile_invocations(session, fake_queue)

    assert result == 0
    assert fake_queue.enqueued == []


def test_reconcile_skips_non_wake_trigger(db_session):
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)
    # Use USER_MESSAGE trigger with the orphan-state column combination.
    # trigger_ref_id need not point at parent — defensive path.
    _make_orphan_wake_invocation(
        session, conv_id=conv.id, parent_inv_id=parent.id, rq_job_id="rqU",
        trigger=InvocationTrigger.USER_MESSAGE,
    )
    session.commit()

    fake_queue = FakeQueue()
    with patch("robotina.queue.reconcile.Job.exists", return_value=False):
        result = reconcile_invocations(session, fake_queue)

    assert result == 0
    assert fake_queue.enqueued == []


def test_reconcile_skips_non_pending(db_session):
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)
    _make_orphan_wake_invocation(
        session, conv_id=conv.id, parent_inv_id=parent.id, rq_job_id="rqD",
        status=InvocationStatus.DONE,
    )
    session.commit()

    fake_queue = FakeQueue()
    with patch("robotina.queue.reconcile.Job.exists", return_value=False) as mock_exists:
        result = reconcile_invocations(session, fake_queue)

    assert result == 0
    assert fake_queue.enqueued == []
    # Job.exists must not have been called — the SQL filter excluded the row.
    mock_exists.assert_not_called()


def test_reconcile_empty_state(db_session):
    session = db_session
    fake_queue = FakeQueue()
    with patch("robotina.queue.reconcile.Job.exists", return_value=False):
        result = reconcile_invocations(session, fake_queue)
    assert result == 0
    assert fake_queue.enqueued == []


def test_reconcile_continues_on_row_error(db_session):
    session = db_session
    conv = _make_conversation(session)
    # Two distinct parents so the UniqueConstraint(trigger_ref_id, trigger)
    # doesn't reject the second WORKFLOW_COMPLETION row.
    parent_a = _make_parent_invocation(session, conv.id)
    parent_b = _make_parent_invocation(session, conv.id)
    _make_run(session, conv_id=conv.id, parent_inv_id=parent_a.id,
              status=WorkflowStatus.DONE)
    _make_run(session, conv_id=conv.id, parent_inv_id=parent_b.id,
              status=WorkflowStatus.DONE)
    _make_orphan_wake_invocation(
        session, conv_id=conv.id, parent_inv_id=parent_a.id, rq_job_id="rq1",
    )
    _make_orphan_wake_invocation(
        session, conv_id=conv.id, parent_inv_id=parent_b.id, rq_job_id="rq2",
    )
    session.commit()

    fake_queue = FakeQueue()
    call_count = {"n": 0}

    def flaky_exists(job_id, connection=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("redis hiccup")
        return False  # second row → orphan → re-enqueue

    with patch("robotina.queue.reconcile.Job.exists", side_effect=flaky_exists):
        result = reconcile_invocations(session, fake_queue)

    assert result == 1
    assert len(fake_queue.enqueued) == 1


def test_reconcile_rebuilds_outcomes(db_session):
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)
    _make_run(
        session, conv_id=conv.id, parent_inv_id=parent.id,
        status=WorkflowStatus.DONE,
        outcome={
            "status": "success",
            "recipe_id": "abc",
            "recipe_name": "X",
            "recipe_slug": "x",
            "image_present": False,
        },
    )
    _make_run(
        session, conv_id=conv.id, parent_inv_id=parent.id,
        status=WorkflowStatus.FAILED,
        outcome=None,
    )
    _make_orphan_wake_invocation(
        session, conv_id=conv.id, parent_inv_id=parent.id, rq_job_id="rqOut",
    )
    session.commit()

    fake_queue = FakeQueue()
    with patch("robotina.queue.reconcile.Job.exists", return_value=False):
        result = reconcile_invocations(session, fake_queue)

    assert result == 1
    args, _ = fake_queue.enqueued[0]
    wake_input = args[1]
    assert wake_input.previous_invocation_id == parent.id
    assert wake_input.conversation_id == conv.id
    assert len(wake_input.outcomes) == 2
    # Order is not guaranteed; find success vs failed.
    success = next(o for o in wake_input.outcomes if o.status == "done")
    failed = next(o for o in wake_input.outcomes if o.status == "failed")
    assert success.outcome is not None
    assert success.outcome.recipe_name == "X"
    assert failed.outcome is None
