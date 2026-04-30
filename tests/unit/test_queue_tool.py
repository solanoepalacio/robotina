"""Tests for QueueTool.

Covers ROBOT-03: Robotina agent has queue tool (enqueue a single follow-up
send-notification task directly). Tests mock RQ Queue — never touch real Redis.
"""
import pytest
from unittest.mock import MagicMock, patch


def test_queue_tool_construction():
    """ROBOT-03: QueueTool can be constructed with chat_id, user_id, platform."""
    from robotina.agent.tools.queue import QueueTool
    tool = QueueTool(chat_id="c1", user_id="u1", platform="telegram")
    assert tool.chat_id == "c1"
    assert tool.user_id == "u1"
    assert tool.platform == "telegram"
    assert tool.name == "queue"


def test_queue_tool_enqueues_send_notification_with_correct_meta():
    """ROBOT-03: _run(text) enqueues 'robotina.queue.jobs.run_task' with meta={'task_type': 'send-notification'},
    result_ttl=-1, failure_ttl=-1."""
    from robotina.agent.tools.queue import QueueTool

    tool = QueueTool(chat_id="chat-42", user_id="user-7", platform="telegram")

    mock_job = MagicMock()
    mock_job.id = "job-uuid-123"

    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = mock_job

    with patch("robotina.agent.tools.queue.Queue", return_value=mock_queue), \
         patch("robotina.agent.tools.queue.Redis"):
        tool._run("Here is your meal plan.")

    call_kwargs = mock_queue.enqueue.call_args
    assert call_kwargs.args[0] == "robotina.queue.jobs.run_task"
    assert call_kwargs.kwargs.get("result_ttl") == -1
    assert call_kwargs.kwargs.get("failure_ttl") == -1
    assert call_kwargs.kwargs.get("meta") == {"task_type": "send-notification"}


def test_queue_tool_enqueues_at_front_of_queue():
    """ROBOT-03: _run() passes at_front=True — notification replies take priority."""
    from robotina.agent.tools.queue import QueueTool

    tool = QueueTool(chat_id="c1", user_id="u1", platform="telegram")

    mock_job = MagicMock()
    mock_job.id = "job-xyz"
    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = mock_job

    with patch("robotina.agent.tools.queue.Queue", return_value=mock_queue), \
         patch("robotina.agent.tools.queue.Redis"):
        tool._run("reply text")

    call_kwargs = mock_queue.enqueue.call_args
    assert call_kwargs.kwargs.get("at_front") is True, (
        "QueueTool must use at_front=True — notification replies take priority"
    )


def test_queue_tool_returns_stop_signal_with_job_id():
    """ROBOT-03: _run(text) returns a stop-signal string containing job.id.

    A bare UUID return caused the routing LLM to interpret the result as
    incomplete and re-call the tool, producing duplicate replies. The
    return value must (a) include the job_id and (b) explicitly tell the
    LLM not to call the tool again.
    """
    from robotina.agent.tools.queue import QueueTool

    tool = QueueTool(chat_id="c1", user_id="u1", platform="telegram")

    mock_job = MagicMock()
    mock_job.id = "expected-job-id-999"
    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = mock_job

    with patch("robotina.agent.tools.queue.Queue", return_value=mock_queue), \
         patch("robotina.agent.tools.queue.Redis"):
        result = tool._run("some reply")

    assert "expected-job-id-999" in result
    assert "do not call this tool again" in result.lower()
