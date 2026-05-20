"""Phase 23 D-08: wake-helper fallback read tests.

Verifies that ``_check_and_dispatch_wake`` populates
``WorkflowOutcomeSummary.recipe_query`` from BOTH
``shared_context["recipe_query"]`` (Phase 22) and
``shared_context["recipe_url"]`` (Phase 23) — the latter as a fallback so the
wake reply can surface URL-pointed workflow outcomes.

These tests reuse the DB-backed fixtures from ``test_wake_dispatch.py``'s
pattern (real Postgres ``db_session``, raw SQL UPDATE-RETURNING semantics
mean a mocked session won't work here).
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from robotina.gateway.models import Conversation
from robotina.queue.workflow_runner import _check_and_dispatch_wake
from robotina.queue.models import (
    InvocationStatus,
    InvocationTrigger,
    RobotinaInvocation,
    WorkflowRun,
    WorkflowStatus,
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


class _FakeQueue:
    name = "agent-tasks"

    def __init__(self):
        self.enqueued: list[tuple[tuple, dict]] = []

    def enqueue(self, *args, **kwargs):
        self.enqueued.append((args, kwargs))


def _make_conversation(session) -> Conversation:
    conv = Conversation(
        platform="telegram", chat_id="c-wake-url",
        household_id="test-household",
    )
    session.add(conv)
    session.flush()
    return conv


def _make_parent(session, conv_id: str) -> RobotinaInvocation:
    inv = RobotinaInvocation(
        conversation_id=conv_id,
        trigger=InvocationTrigger.USER_MESSAGE,
        status=InvocationStatus.RUNNING,
    )
    session.add(inv)
    session.flush()
    return inv


def _make_run(session, *, conv_id, parent_inv_id, shared_context, workflow_type):
    run = WorkflowRun(
        workflow_type=workflow_type,
        household_id="test-household",
        conversation_id=conv_id,
        triggered_by_invocation_id=parent_inv_id,
        status=WorkflowStatus.DONE,
        shared_context=shared_context,
        outcome=None,
    )
    session.add(run)
    session.flush()
    return run


def test_wake_helper_falls_back_to_recipe_url_when_recipe_query_missing(db_session):
    """Phase 23 D-08: shared_context has only ``recipe_url`` (no
    ``recipe_query``) — the helper must surface the URL as
    ``WorkflowOutcomeSummary.recipe_query`` so V006/V007's wake-reply
    rules can render it."""
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent(session, conv.id)
    _make_run(
        session,
        conv_id=conv.id,
        parent_inv_id=parent.id,
        shared_context={"recipe_url": "https://example.com/recipe-x"},
        workflow_type="add-recipe-from-url",
    )

    queue = _FakeQueue()
    _check_and_dispatch_wake(parent.id, session, queue)
    session.commit()

    assert len(queue.enqueued) == 1
    args, _kwargs = queue.enqueued[0]
    # Second positional argument is the WakeInvocationInput.
    wake_input = args[1]
    assert len(wake_input.outcomes) == 1
    assert wake_input.outcomes[0].recipe_query == "https://example.com/recipe-x"


def test_wake_helper_prefers_recipe_query_when_both_present(db_session):
    """Phase 23 D-08: ``recipe_query`` takes precedence over
    ``recipe_url`` when both somehow appear in the same shared_context.
    The ``or`` short-circuits on the first truthy value."""
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent(session, conv.id)
    _make_run(
        session,
        conv_id=conv.id,
        parent_inv_id=parent.id,
        shared_context={
            "recipe_query": "lentejas",
            "recipe_url": "https://example.com/x",
        },
        workflow_type="add-recipe-from-query",
    )

    queue = _FakeQueue()
    _check_and_dispatch_wake(parent.id, session, queue)
    session.commit()

    assert len(queue.enqueued) == 1
    wake_input = queue.enqueued[0][0][1]
    assert wake_input.outcomes[0].recipe_query == "lentejas"


def test_wake_helper_recipe_query_none_when_neither_present(db_session):
    """Sanity: empty shared_context yields ``recipe_query=None``."""
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent(session, conv.id)
    _make_run(
        session,
        conv_id=conv.id,
        parent_inv_id=parent.id,
        shared_context={},
        workflow_type="add-recipe-from-query",
    )

    queue = _FakeQueue()
    _check_and_dispatch_wake(parent.id, session, queue)
    session.commit()

    assert len(queue.enqueued) == 1
    wake_input = queue.enqueued[0][0][1]
    assert wake_input.outcomes[0].recipe_query is None
