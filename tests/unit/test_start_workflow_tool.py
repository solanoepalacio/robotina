"""Unit tests for StartWorkflowTool's terminal-tool behavior (Phase 07.1).

These tests mock the workflow_runner / DB / Redis layers so they don't need
infrastructure.

Phase 07.1 + AGENT-12: StartWorkflowTool is terminal via ``return_direct=True``.
The ``langchain.agents.create_agent`` graph terminates immediately after the
tool runs (both happy and error paths).
"""
from unittest.mock import MagicMock, patch


def test_start_workflow_tool_is_terminal_via_return_direct():
    """Phase 07.1: return_direct=True makes the agent graph terminate after
    the tool runs."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )
    assert tool.return_direct is True


def test_start_workflow_tool_returns_workflow_run_id_on_success():
    """Happy path returns a string carrying the workflow_run_id."""
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
        )

    assert isinstance(result, str)
    assert expected_run_id in result


def test_start_workflow_tool_error_path_returns_string():
    """Error path also returns a string (so the agent terminates via
    ``return_direct`` instead of looping on an exception)."""
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
        result = tool._run(workflow_type="nonexistent", shared_context={})

    assert isinstance(result, str)
    assert "failed" in result.lower() or "unknown" in result.lower()


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
        )

    shared = captured["shared_context"]
    assert shared["recipe_query"] == "pasta"
    assert shared["reply_context"] == {
        "platform": "telegram",
        "chat_id": "chat-42",
        "user_id": "user-7",
    }
    assert shared["household_id"] == "house-1"


def test_start_workflow_tool_short_circuits_create_agent():
    """Phase 07.1 / AGENT-12 regression: drive the StartWorkflowTool through a
    real ``langchain.agents.create_agent`` with a stub model that always tries
    to emit a tool call. The engine must terminate after the tool runs,
    regardless of what the model wants to do next."""
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain.agents import create_agent

    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )

    mock_session = MagicMock()
    mock_queue = MagicMock()

    call_count = {"n": 0}

    class CountingModel(FakeMessagesListChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            call_count["n"] += 1
            return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

        def bind_tools(self, tools, **kwargs):
            return self

    first_call = AIMessage(
        content="",
        tool_calls=[{
            "name": "start-workflow",
            "args": {"workflow_type": "add-recipe", "shared_context": {"recipe_query": "carbonara"}},
            "id": "tc-sw",
            "type": "tool_call",
        }],
    )
    second_call = AIMessage(content="should not happen", tool_calls=[])
    model = CountingModel(responses=[first_call, second_call])

    with (
        patch("robotina.db.SessionLocal", return_value=mock_session),
        patch("rq.Queue", return_value=mock_queue),
        patch("redis.Redis"),
        patch("robotina.queue.workflow_runner.queue_workflow", return_value="run-r"),
    ):
        agent = create_agent(model=model, tools=[tool])
        agent.invoke({"messages": [HumanMessage(content="add a recipe")]})

    assert call_count["n"] == 1, (
        f"Expected exactly 1 LLM call (engine terminates after terminal tool); "
        f"got {call_count['n']}. return_direct may have regressed."
    )


def test_start_workflow_tool_description_no_prompt_level_stop_hack():
    """Phase 07.1: tool description should not contain the old prompt-level
    "do not call this tool again" hack."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )
    assert "do not call" not in tool.description.lower()
    assert "task is done" not in tool.description.lower()


# ---------------------------------------------------------------------------
# Strict args-schema tests
#
# Same rationale as test_household_manager_api_tool::test_args_schema_*: an
# unknown LLM-emitted argument key must produce a ValidationError (not a
# TypeError) so langgraph's ToolNode can convert it into a ToolMessage the
# agent sees on its next turn.
# ---------------------------------------------------------------------------


def test_args_schema_forbids_unknown_field():
    """An unknown LLM-emitted argument key raises pydantic ValidationError
    (not TypeError) and the error message names the offending field."""
    import pytest
    from pydantic import ValidationError

    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )

    bad_args = {
        "workflow_type": "add-recipe",
        "shared_context": {"recipe_query": "carbonara"},
        "response": "200",  # hallucinated extra field
    }

    with pytest.raises(ValidationError) as exc_info:
        tool.invoke(bad_args)

    assert "response" in str(exc_info.value)


def test_args_schema_allows_required_only():
    """A minimal valid call (workflow_type + shared_context) still works
    under the strict schema — extra='forbid' must not break the happy path."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )

    mock_session = MagicMock()
    mock_queue = MagicMock()
    expected_run_id = "run-strict-1"

    with (
        patch("robotina.db.SessionLocal", return_value=mock_session),
        patch("rq.Queue", return_value=mock_queue),
        patch("redis.Redis"),
        patch(
            "robotina.queue.workflow_runner.queue_workflow",
            return_value=expected_run_id,
        ),
    ):
        result = tool.invoke(
            {
                "workflow_type": "add-recipe",
                "shared_context": {"recipe_query": "carbonara"},
            }
        )

    assert isinstance(result, str)
    assert expected_run_id in result


def test_args_schema_json_schema_forbids_extra():
    """JSON schema for the args model reports ``additionalProperties: false``."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )
    schema = tool.args_schema.model_json_schema()
    assert schema.get("additionalProperties") is False


# ---------------------------------------------------------------------------
# Phase 16 — REQ-HID-3: constructor rejects empty household_id; default removed
# ---------------------------------------------------------------------------

def test_constructor_rejects_empty_household_id():
    """StartWorkflowTool(household_id='') must raise ValidationError (REQ-HID-3)."""
    import pytest
    from pydantic import ValidationError

    from robotina.agent.tools.start_workflow import StartWorkflowTool

    with pytest.raises(ValidationError) as exc_info:
        StartWorkflowTool(chat_id="c1", user_id="u1", platform="telegram", household_id="")
    assert "household_id" in str(exc_info.value)


def test_constructor_requires_household_id_no_default():
    """StartWorkflowTool() without household_id must fail — proves '' default was removed (Pitfall 5)."""
    import pytest
    from pydantic import ValidationError

    from robotina.agent.tools.start_workflow import StartWorkflowTool

    with pytest.raises(ValidationError) as exc_info:
        StartWorkflowTool(chat_id="c1", user_id="u1", platform="telegram")
    assert "household_id" in str(exc_info.value)


def test_constructor_accepts_non_empty_household_id():
    """Regression guard: existing call site pattern still works."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )
    assert tool.household_id == "h1"
