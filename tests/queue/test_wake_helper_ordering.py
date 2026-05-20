"""Phase 22 Plan 01 Task 2 — D-06 ORDER BY + D-08 recipe_query in wake helper.

Asserts that `_check_and_dispatch_wake` surfaces sibling WorkflowRuns in
`created_at` ASC order (D-06 — best-available proxy for user-utterance order
under provider parallel tool calls) and threads each run's
`shared_context["recipe_query"]` onto the WorkflowOutcomeSummary (D-08) so the
wake-turn Robotina prompt has the data BATCH-03 / BATCH-04 need.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from robotina.queue.models import WorkflowStatus
from robotina.queue.workflow_runner import _check_and_dispatch_wake

# Reuse fixtures + helpers from the existing wake-dispatch test (do NOT redefine).
from tests.queue.test_wake_dispatch import (
    FakeQueue,
    _make_conversation,
    _make_parent_invocation,
    _make_run,
)


@pytest.fixture(autouse=True)
def _cleanup_workflow_tables(db_session):
    db_session.execute(text("DELETE FROM workflow_run_steps"))
    db_session.execute(text("DELETE FROM workflow_runs"))
    db_session.commit()
    yield
    db_session.execute(text("DELETE FROM workflow_run_steps"))
    db_session.execute(text("DELETE FROM workflow_runs"))
    db_session.commit()


def test_wake_helper_orders_outcomes_by_created_at_asc(db_session):
    """D-06: sibling runs surface in created_at ASC order in WakeInvocationInput.outcomes.

    D-08: each outcome carries recipe_query from WorkflowRun.shared_context.
    """
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)

    base = datetime.now(timezone.utc)
    names = ["canelones", "pollo", "arroz"]
    for i, name in enumerate(names):
        r = _make_run(
            session,
            conv_id=conv.id,
            parent_inv_id=parent.id,
            status=WorkflowStatus.DONE,
            outcome={
                "status": "success",
                "recipe_name": name.capitalize(),
                "recipe_slug": name,
            },
        )
        # Force created_at >= 10ms apart to avoid clock-tie flakes (Pitfall 1).
        r.created_at = base + timedelta(milliseconds=i * 10)
        r.shared_context = {"recipe_query": name}
    session.flush()

    fake_queue = FakeQueue()
    _check_and_dispatch_wake(parent.id, session, fake_queue)
    session.commit()

    assert len(fake_queue.enqueued) == 1, "wake should be enqueued exactly once"
    args, _ = fake_queue.enqueued[0]
    wake_input = args[1]

    observed_names = [o.outcome.recipe_name for o in wake_input.outcomes]
    assert observed_names == ["Canelones", "Pollo", "Arroz"], (
        f"outcomes not in created_at ASC order: {observed_names}"
    )

    observed_queries = [o.recipe_query for o in wake_input.outcomes]
    assert observed_queries == ["canelones", "pollo", "arroz"], (
        f"recipe_query not populated from shared_context: {observed_queries}"
    )


def test_wake_helper_handles_missing_recipe_query(db_session):
    """Pitfall 6: shared_context without recipe_query key -> recipe_query=None, no crash."""
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)

    r = _make_run(
        session,
        conv_id=conv.id,
        parent_inv_id=parent.id,
        status=WorkflowStatus.DONE,
        outcome={"status": "success", "recipe_name": "X", "recipe_slug": "x"},
    )
    r.shared_context = {}  # empty dict — no recipe_query
    session.flush()

    fake_queue = FakeQueue()
    _check_and_dispatch_wake(parent.id, session, fake_queue)
    session.commit()

    args, _ = fake_queue.enqueued[0]
    wake_input = args[1]
    assert wake_input.outcomes[0].recipe_query is None
