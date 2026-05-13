"""Tests for QueueTool.

Covers ROBOT-03: Robotina agent has queue tool (enqueue a single follow-up
send-notification task directly). Tests mock RQ Queue — never touch real Redis.

Phase 07.1 + AGENT-12: QueueTool is terminal via ``return_direct=True``. The
``langchain.agents.create_agent`` graph terminates immediately after the tool
runs, with no further LLM invocation. (``Command(goto=END)`` from a tool does NOT
short-circuit the prebuilt graph in langgraph 1.1.x — empirically verified —
hence this approach.)
"""
from unittest.mock import MagicMock, patch


def test_queue_tool_construction():
    """ROBOT-03: QueueTool can be constructed with chat_id, user_id, platform."""
    from robotina.agent.tools.queue import QueueTool
    tool = QueueTool(chat_id="c1", user_id="u1", platform="telegram")
    assert tool.chat_id == "c1"
    assert tool.user_id == "u1"
    assert tool.platform == "telegram"
    assert tool.name == "queue"


def test_queue_tool_is_terminal_via_return_direct():
    """Phase 07.1: return_direct=True makes the agent graph terminate after
    the tool runs. This is the engine-enforced termination promised by Plan 03."""
    from robotina.agent.tools.queue import QueueTool

    tool = QueueTool(chat_id="c1", user_id="u1", platform="telegram")
    assert tool.return_direct is True


def test_queue_tool_enqueues_send_notification_with_correct_meta():
    """ROBOT-03: _run(text) enqueues 'robotina.queue.jobs.run_task' with
    meta={'task_type': 'send-notification'}, result_ttl=-1, failure_ttl=-1."""
    from robotina.agent.tools.queue import QueueTool

    tool = QueueTool(chat_id="chat-42", user_id="user-7", platform="telegram")

    mock_job = MagicMock()
    mock_job.id = "job-uuid-123"
    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = mock_job

    with patch("robotina.agent.tools.queue.Queue", return_value=mock_queue), \
         patch("robotina.agent.tools.queue.Redis"):
        result = tool._run("Here is your meal plan.")

    call_kwargs = mock_queue.enqueue.call_args
    assert call_kwargs.args[0] == "robotina.queue.jobs.run_task"
    assert call_kwargs.kwargs.get("result_ttl") == -1
    assert call_kwargs.kwargs.get("failure_ttl") == -1
    assert call_kwargs.kwargs.get("meta") == {"task_type": "send-notification"}
    assert "job-uuid-123" in result


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
    assert call_kwargs.kwargs.get("at_front") is True


def test_queue_tool_short_circuits_create_agent():
    """Phase 07.1 / AGENT-12 regression: drive the QueueTool through a real
    ``langchain.agents.create_agent`` with a stub model that ALWAYS tries to
    emit a tool call. If the engine truly terminates after the tool runs, the
    model is invoked exactly once. If not, the model is invoked twice (or
    more).

    This is the test that should fail loudly if anything in our termination
    setup regresses (e.g. ``return_direct`` removed, factory swapped for one
    that doesn't honor it)."""
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain.agents import create_agent

    from robotina.agent.tools.queue import QueueTool

    tool = QueueTool(chat_id="c1", user_id="u1", platform="telegram")

    mock_job = MagicMock()
    mock_job.id = "j-1"
    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = mock_job

    call_count = {"n": 0}

    class CountingModel(FakeMessagesListChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            call_count["n"] += 1
            return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

        def bind_tools(self, tools, **kwargs):
            return self  # tools already encoded in preset responses

    first_call = AIMessage(
        content="",
        tool_calls=[{"name": "queue", "args": {"text": "hola"}, "id": "tc-1", "type": "tool_call"}],
    )
    second_call = AIMessage(
        content="if engine did not terminate, this proves it",
        tool_calls=[],
    )
    model = CountingModel(responses=[first_call, second_call])

    with patch("robotina.agent.tools.queue.Queue", return_value=mock_queue), \
         patch("robotina.agent.tools.queue.Redis"):
        agent = create_agent(model=model, tools=[tool])
        agent.invoke({"messages": [HumanMessage(content="please reply")]})

    assert call_count["n"] == 1, (
        f"Expected exactly 1 LLM call (engine terminates after terminal tool); "
        f"got {call_count['n']}. return_direct may have regressed."
    )


def test_queue_tool_description_no_prompt_level_stop_hack():
    """Phase 07.1: tool description should not contain the old prompt-level
    "do not call this tool again" hack — engine guarantees termination."""
    from robotina.agent.tools.queue import QueueTool

    tool = QueueTool(chat_id="c1", user_id="u1", platform="telegram")
    assert "do not call" not in tool.description.lower()
    assert "task is done" not in tool.description.lower()
