"""Unit tests for StartWorkflowTool's terminal-tool behavior (Phase 07.1).

These tests mock the workflow_runner / DB / Redis layers so they don't need
infrastructure. End-to-end tests live in tests/test_start_workflow_tool.py.
"""
from unittest.mock import MagicMock, patch

from langchain_core.messages import ToolMessage
from langgraph.graph import END
from langgraph.types import Command


def test_start_workflow_tool_returns_command_goto_end_on_success():
    """Phase 07.1: happy path returns Command(goto=END) carrying a ToolMessage
    with the workflow_run_id."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )

    mock_session = MagicMock()
    mock_queue = MagicMock()
    expected_run_id = "run-abc-123"

    with (
        patch("robotina.db.SessionLocal", return_value=mock_session),
        patch("rq.Queue", return_value=mock_queue),
        patch("redis.Redis"),
        patch("robotina.queue.workflow_runner.queue_workflow", return_value=expected_run_id),
    ):
        result = tool._run(
            workflow_type="add-recipe",
            shared_context={"recipe_query": "carbonara"},
            tool_call_id="tc-sw-1",
        )

    assert isinstance(result, Command)
    assert result.goto == END
    messages = result.update["messages"]
    assert len(messages) == 1
    msg = messages[0]
    assert isinstance(msg, ToolMessage)
    assert msg.tool_call_id == "tc-sw-1"
    assert msg.name == "start-workflow"
    assert expected_run_id in msg.content


def test_start_workflow_tool_returns_command_goto_end_on_error():
    """Phase 07.1: error path ALSO returns Command(goto=END) — the agent must
    not loop on workflow-start failures."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )

    mock_session = MagicMock()
    mock_queue = MagicMock()

    with (
        patch("robotina.db.SessionLocal", return_value=mock_session),
        patch("rq.Queue", return_value=mock_queue),
        patch("redis.Redis"),
        patch(
            "robotina.queue.workflow_runner.queue_workflow",
            side_effect=ValueError("unknown workflow_type"),
        ),
    ):
        result = tool._run(
            workflow_type="nonexistent",
            shared_context={},
            tool_call_id="tc-sw-err",
        )

    assert isinstance(result, Command)
    assert result.goto == END
    msg = result.update["messages"][0]
    assert isinstance(msg, ToolMessage)
    assert "failed" in msg.content.lower() or "unknown" in msg.content.lower()


def test_start_workflow_tool_auto_injects_reply_context():
    """StartWorkflowTool auto-injects reply_context (chat_id/user_id/platform)
    and household_id into shared_context — the LLM never sees these fields."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="chat-42", user_id="user-7", platform="telegram", household_id="house-1"
    )

    mock_session = MagicMock()
    mock_queue = MagicMock()
    captured = {}

    def capture_queue_workflow(**kwargs):
        captured.update(kwargs)
        return "run-1"

    with (
        patch("robotina.db.SessionLocal", return_value=mock_session),
        patch("rq.Queue", return_value=mock_queue),
        patch("redis.Redis"),
        patch("robotina.queue.workflow_runner.queue_workflow", side_effect=capture_queue_workflow),
    ):
        tool._run(
            workflow_type="add-recipe",
            shared_context={"recipe_query": "pasta"},
            tool_call_id="tc-sw-inj",
        )

    shared = captured["shared_context"]
    assert shared["recipe_query"] == "pasta"
    assert shared["reply_context"] == {
        "platform": "telegram",
        "chat_id": "chat-42",
        "user_id": "user-7",
    }
    assert shared["household_id"] == "house-1"


def test_start_workflow_tool_invokes_with_simulated_tool_call_dict():
    """Phase 07.1 regression: same as the QueueTool test — verify .invoke()
    via a tool_call dict (the path LangGraph's ToolNode uses) injects
    tool_call_id correctly."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )

    mock_session = MagicMock()
    mock_queue = MagicMock()

    with (
        patch("robotina.db.SessionLocal", return_value=mock_session),
        patch("rq.Queue", return_value=mock_queue),
        patch("redis.Redis"),
        patch("robotina.queue.workflow_runner.queue_workflow", return_value="run-regr"),
    ):
        result = tool.invoke({
            "name": "start-workflow",
            "args": {
                "workflow_type": "add-recipe",
                "shared_context": {"recipe_query": "carbonara"},
            },
            "id": "tc-sw-regression",
            "type": "tool_call",
        })

    # When the tool returns a Command, .invoke() returns it directly.
    # Injection must have worked (no TypeError raised).
    assert isinstance(result, Command)
    inner_msg = result.update["messages"][0]
    assert inner_msg.tool_call_id == "tc-sw-regression"
    assert "run-regr" in inner_msg.content


def test_start_workflow_tool_description_no_prompt_level_stop_hack():
    """Phase 07.1: tool description should not contain the old prompt-level
    "do not call this tool again" hack."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )
    assert "do not call" not in tool.description.lower()
    assert "task is done" not in tool.description.lower()
