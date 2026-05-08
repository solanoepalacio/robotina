"""Tests for QueueTool.

Covers ROBOT-03: Robotina agent has queue tool (enqueue a single follow-up
send-notification task directly). Tests mock RQ Queue — never touch real Redis.

Phase 07.1: QueueTool is terminal — _run returns Command(goto=END) so the
LangGraph state machine cannot loop after the tool succeeds.
"""
from unittest.mock import MagicMock, patch

from langgraph.graph import END


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
        tool._run("Here is your meal plan.", tool_call_id="tc-1")

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
        tool._run("reply text", tool_call_id="tc-1")

    call_kwargs = mock_queue.enqueue.call_args
    assert call_kwargs.kwargs.get("at_front") is True, (
        "QueueTool must use at_front=True — notification replies take priority"
    )


def test_queue_tool_returns_command_goto_end():
    """Phase 07.1: _run returns Command(goto=END) so the agent graph terminates
    immediately after the tool runs. Termination is engine-enforced, not
    prompt-requested."""
    from langchain_core.messages import ToolMessage
    from langgraph.types import Command

    from robotina.agent.tools.queue import QueueTool

    tool = QueueTool(chat_id="c1", user_id="u1", platform="telegram")

    mock_job = MagicMock()
    mock_job.id = "expected-job-id-999"
    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = mock_job

    with patch("robotina.agent.tools.queue.Queue", return_value=mock_queue), \
         patch("robotina.agent.tools.queue.Redis"):
        result = tool._run("some reply", tool_call_id="tc-call-1")

    assert isinstance(result, Command)
    assert result.goto == END
    messages = result.update["messages"]
    assert len(messages) == 1
    msg = messages[0]
    assert isinstance(msg, ToolMessage)
    assert msg.tool_call_id == "tc-call-1"
    assert msg.name == "queue"
    assert "expected-job-id-999" in msg.content


def test_queue_tool_description_no_prompt_level_stop_hack():
    """Phase 07.1: tool description should not contain the old prompt-level
    "do not call this tool again" hack — the engine guarantees termination
    via Command(goto=END) now."""
    from robotina.agent.tools.queue import QueueTool

    tool = QueueTool(chat_id="c1", user_id="u1", platform="telegram")
    assert "do not call" not in tool.description.lower()
    assert "task is done" not in tool.description.lower()
