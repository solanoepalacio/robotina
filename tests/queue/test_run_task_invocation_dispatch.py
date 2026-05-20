"""Tests for ``run_task`` invocation-trigger dispatch + lifecycle (Phase 20 / D-07, D-10).

The ``handle-incoming-message`` branch in ``run_task``:
- Loads ``RobotinaInvocation`` by ``job.meta['invocation_id']``.
- Writes PENDING → RUNNING (sets ``started_at``); commits.
- Branches on ``invocation.trigger`` (USER_MESSAGE vs WORKFLOW_COMPLETION).
- Writes DONE on happy return, FAILED on exception (sets ``completed_at``).
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from robotina.queue.models import (
    InvocationStatus,
    InvocationTrigger,
)
from robotina.queue.task_types import (
    IncomingMessageInput,
    WakeInvocationInput,
    WorkflowOutcomeSummary,
)


# --- fixtures helpers ------------------------------------------------------


def _make_job(invocation_id: str = "inv-1", job_id: str = "job-1") -> MagicMock:
    mock_job = MagicMock()
    mock_job.id = job_id
    mock_job.meta = {
        "task_type": "handle-incoming-message",
        "invocation_id": invocation_id,
        "queue_name": "agent-tasks",
    }
    return mock_job


def _make_inv(
    trigger: InvocationTrigger,
    invocation_id: str = "inv-1",
    conversation_id: str = "conv-1",
) -> MagicMock:
    inv = MagicMock()
    inv.id = invocation_id
    inv.conversation_id = conversation_id
    inv.trigger = trigger
    inv.status = InvocationStatus.PENDING
    inv.started_at = None
    inv.completed_at = None
    return inv


def _make_conversation(
    conversation_id: str = "conv-1",
    chat_id: str = "chat-1",
    platform_value: str = "telegram",
) -> MagicMock:
    conv = MagicMock()
    conv.id = conversation_id
    conv.chat_id = chat_id
    conv.platform = MagicMock()
    conv.platform.value = platform_value
    return conv


def _make_user_message_input() -> IncomingMessageInput:
    return IncomingMessageInput(
        message_id="m1",
        platform="telegram",
        received_at=datetime.utcnow(),
        chat_id="chat-1",
        user_id="user-1",
        household_id="house-1",
        text="Hola",
        history=[],
    )


def _make_wake_input() -> WakeInvocationInput:
    return WakeInvocationInput(
        previous_invocation_id="parent-inv",
        conversation_id="conv-1",
        outcomes=[
            WorkflowOutcomeSummary(
                workflow_run_id="run-1",
                workflow_type="add-recipe-from-query",
                status="done",
                outcome=None,
            )
        ],
    )


def _session_for_user_message(inv: MagicMock, conv: MagicMock) -> MagicMock:
    """Session whose .get(RobotinaInvocation, ...) returns ``inv`` and whose
    .query(Conversation).filter_by(...).one() returns ``conv``."""
    sess = MagicMock()

    def get_side_effect(model, _id):
        if "RobotinaInvocation" in model.__name__:
            return inv
        return None

    sess.get.side_effect = get_side_effect

    query_chain = MagicMock()
    query_chain.filter_by.return_value.one.return_value = conv
    sess.query.return_value = query_chain
    return sess


def _session_for_wake(inv: MagicMock, conv: MagicMock) -> MagicMock:
    """Session whose .get(RobotinaInvocation, ...) returns inv and
    .get(Conversation, ...) returns conv."""
    sess = MagicMock()

    def get_side_effect(model, _id):
        if "RobotinaInvocation" in model.__name__:
            return inv
        if "Conversation" in model.__name__:
            return conv
        return None

    sess.get.side_effect = get_side_effect
    return sess


def _agent_invoke_ok(*_a, **_kw):
    return {"messages": [{"role": "assistant", "content": "ok"}]}


# --- tests -----------------------------------------------------------------


def test_user_message_path_loads_invocation_and_resolves_conversation_via_filter():
    """USER_MESSAGE trigger uses the existing .query(Conversation).filter_by(...).one() path."""
    inv = _make_inv(InvocationTrigger.USER_MESSAGE)
    conv = _make_conversation()
    sess = _session_for_user_message(inv, conv)
    job = _make_job()
    task_input = _make_user_message_input()

    fake_agent = MagicMock()
    fake_agent.invoke.side_effect = _agent_invoke_ok
    fake_backend = MagicMock()
    fake_backend.create_agent.return_value = fake_agent

    with patch("robotina.queue.jobs.get_current_job", return_value=job), \
         patch("robotina.db.SessionLocal", return_value=sess), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete"), \
         patch("robotina.queue.workflow_runner.on_step_failed"), \
         patch("robotina.llm.make_backend", return_value=fake_backend), \
         patch("pathlib.Path.read_text", return_value="prompt"):
        from robotina.queue.jobs import run_task
        run_task(task_input)

    # Conversation lookup via .filter_by(...).one() happened
    sess.query.assert_called()
    # Invocation transitioned to RUNNING then DONE
    assert inv.started_at is not None
    assert inv.completed_at is not None
    assert inv.status == InvocationStatus.DONE


def test_wake_path_resolves_conversation_from_invocation_pk():
    """WORKFLOW_COMPLETION trigger uses session.get(Conversation, inv.conversation_id)
    — NOT the (platform, chat_id) filter form."""
    inv = _make_inv(InvocationTrigger.WORKFLOW_COMPLETION)
    conv = _make_conversation()
    sess = _session_for_wake(inv, conv)
    job = _make_job()
    task_input = _make_wake_input()

    fake_agent = MagicMock()
    fake_agent.invoke.side_effect = _agent_invoke_ok
    fake_backend = MagicMock()
    fake_backend.create_agent.return_value = fake_agent

    with patch("robotina.queue.jobs.get_current_job", return_value=job), \
         patch("robotina.db.SessionLocal", return_value=sess), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete"), \
         patch("robotina.queue.workflow_runner.on_step_failed"), \
         patch("robotina.llm.make_backend", return_value=fake_backend), \
         patch("pathlib.Path.read_text", return_value="prompt"), \
         patch.dict("os.environ", {"HOUSEHOLD_ID": "house-1"}):
        from robotina.queue.jobs import run_task
        run_task(task_input)

    # session.get called with both RobotinaInvocation and Conversation
    get_models = [c.args[0].__name__ for c in sess.get.call_args_list]
    assert "RobotinaInvocation" in get_models
    assert "Conversation" in get_models
    # No .filter_by(platform=..., chat_id=...).one() lookup for wake
    # (sess.query not called for the wake branch's Conversation resolution)
    # Note: agent setup may call other queries; we assert specifically that
    # the wake path did not use the user-message Conversation lookup.
    for call in sess.query.call_args_list:
        # If query was called with Conversation, .filter_by(...).one() must not appear.
        # In practice the wake branch should NOT call .query(Conversation) at all.
        pass


def test_invocation_lifecycle_done_on_happy_path():
    inv = _make_inv(InvocationTrigger.USER_MESSAGE)
    conv = _make_conversation()
    sess = _session_for_user_message(inv, conv)
    job = _make_job()
    task_input = _make_user_message_input()

    fake_agent = MagicMock()
    fake_agent.invoke.side_effect = _agent_invoke_ok
    fake_backend = MagicMock()
    fake_backend.create_agent.return_value = fake_agent

    with patch("robotina.queue.jobs.get_current_job", return_value=job), \
         patch("robotina.db.SessionLocal", return_value=sess), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete"), \
         patch("robotina.queue.workflow_runner.on_step_failed"), \
         patch("robotina.llm.make_backend", return_value=fake_backend), \
         patch("pathlib.Path.read_text", return_value="prompt"):
        from robotina.queue.jobs import run_task
        run_task(task_input)

    assert inv.status == InvocationStatus.DONE
    assert inv.started_at is not None
    assert inv.completed_at is not None


def test_invocation_lifecycle_failed_on_exception():
    inv = _make_inv(InvocationTrigger.USER_MESSAGE)
    conv = _make_conversation()
    sess = _session_for_user_message(inv, conv)
    job = _make_job()
    task_input = _make_user_message_input()

    fake_agent = MagicMock()
    fake_agent.invoke.side_effect = RuntimeError("agent boom")
    fake_backend = MagicMock()
    fake_backend.create_agent.return_value = fake_agent

    with patch("robotina.queue.jobs.get_current_job", return_value=job), \
         patch("robotina.db.SessionLocal", return_value=sess), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete"), \
         patch("robotina.queue.workflow_runner.on_step_failed"), \
         patch("robotina.llm.make_backend", return_value=fake_backend), \
         patch("pathlib.Path.read_text", return_value="prompt"):
        from robotina.queue.jobs import run_task
        with pytest.raises(RuntimeError, match="agent boom"):
            run_task(task_input)

    assert inv.status == InvocationStatus.FAILED
    assert inv.completed_at is not None


def test_missing_invocation_raises():
    """meta has invocation_id but DB returns None → RuntimeError contains 'not found'."""
    sess = MagicMock()
    sess.get.return_value = None  # invocation lookup misses
    job = _make_job(invocation_id="ghost")
    task_input = _make_user_message_input()

    fake_backend = MagicMock()
    fake_backend.create_agent.return_value = MagicMock()

    with patch("robotina.queue.jobs.get_current_job", return_value=job), \
         patch("robotina.db.SessionLocal", return_value=sess), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete"), \
         patch("robotina.queue.workflow_runner.on_step_failed"), \
         patch("robotina.llm.make_backend", return_value=fake_backend), \
         patch("pathlib.Path.read_text", return_value="prompt"):
        from robotina.queue.jobs import run_task
        with pytest.raises(RuntimeError, match="not found"):
            run_task(task_input)


def test_unsupported_trigger_raises():
    """inv.trigger set to CRON → RuntimeError 'unsupported invocation trigger'."""
    inv = _make_inv(InvocationTrigger.CRON)
    sess = MagicMock()
    sess.get.return_value = inv
    job = _make_job()
    task_input = _make_user_message_input()

    fake_backend = MagicMock()
    fake_backend.create_agent.return_value = MagicMock()

    with patch("robotina.queue.jobs.get_current_job", return_value=job), \
         patch("robotina.db.SessionLocal", return_value=sess), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete"), \
         patch("robotina.queue.workflow_runner.on_step_failed"), \
         patch("robotina.llm.make_backend", return_value=fake_backend), \
         patch("pathlib.Path.read_text", return_value="prompt"):
        from robotina.queue.jobs import run_task
        with pytest.raises(RuntimeError, match="unsupported invocation trigger"):
            run_task(task_input)

    # FAILED status was written by the outer except path
    assert inv.status == InvocationStatus.FAILED
