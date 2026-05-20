"""Unit tests for StartWorkflowTool's multi-call non-terminal surface (D-03).

These tests mock the workflow_runner / DB / Redis layers so they don't need
infrastructure.

D-03 (tool-surface flip): StartWorkflowTool is non-terminal
(``return_direct=False``). Robotina's loop continues after each call so the
LLM can chain multiple start-workflow calls and then call ``terminate()``.
The args_schema now takes a typed ``input: AddRecipeQueryInput`` instead of
the legacy flat ``recipe_query: str`` field.
"""
from unittest.mock import MagicMock, patch


def test_start_workflow_tool_is_non_terminal():
    """D-03: return_direct=False makes the tool non-terminal (multi-call)."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )
    assert tool.return_direct is False


def test_start_workflow_tool_args_schema_uses_typed_input():
    """args_schema: {workflow_type: Literal['add-recipe'], input: AddRecipeQueryInput}."""
    from robotina.agent.tools.start_workflow import StartWorkflowArgs
    from robotina.queue.task_types import AddRecipeQueryInput

    args = StartWorkflowArgs(
        workflow_type="add-recipe",
        input={"value": "lentejas"},
    )
    assert args.workflow_type == "add-recipe"
    assert isinstance(args.input, AddRecipeQueryInput)
    assert args.input.value == "lentejas"


def test_start_workflow_tool_rejects_flat_recipe_query():
    """The legacy flat ``recipe_query`` field at the args_schema layer must be
    rejected by extra='forbid' on the outer schema."""
    import pytest
    from pydantic import ValidationError

    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )
    with pytest.raises(ValidationError) as exc_info:
        tool.invoke({"workflow_type": "add-recipe", "recipe_query": "lentejas"})
    msg = str(exc_info.value)
    # Either the missing 'input' field or the unknown 'recipe_query' field
    # (or both) must be flagged. Both indicate the flat schema is gone.
    assert "input" in msg or "recipe_query" in msg


def test_start_workflow_tool_rejects_extra_fields():
    """extra='forbid' rejects unknown top-level keys (e.g. an LLM hallucination)."""
    import pytest
    from pydantic import ValidationError

    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )
    with pytest.raises(ValidationError) as exc_info:
        tool.invoke(
            {
                "workflow_type": "add-recipe",
                "input": {"value": "lentejas"},
                "response": "200",  # hallucinated
            }
        )
    assert "response" in str(exc_info.value)


def test_start_workflow_tool_inner_input_rejects_extra_fields():
    """extra='forbid' on AddRecipeQueryInput rejects unknown inner keys."""
    import pytest
    from pydantic import ValidationError

    from robotina.queue.task_types import AddRecipeQueryInput

    with pytest.raises(ValidationError):
        AddRecipeQueryInput(value="x", extra="y")


def test_start_workflow_tool_run_unwraps_input():
    """_run unwraps input.value into the recipe_query forwarded to queue_workflow."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool
    from robotina.queue.task_types import AddRecipeQueryInput

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )

    mock_session = MagicMock()
    mock_queue = MagicMock()
    captured = {}

    def capture_queue_workflow(**kwargs):
        captured.update(kwargs)
        return "run-unwrap-1"

    with (
        patch("robotina.db.SessionLocal", return_value=mock_session),
        patch("rq.Queue", return_value=mock_queue),
        patch("redis.Redis"),
        patch(
            "robotina.queue.workflow_runner.queue_workflow",
            side_effect=capture_queue_workflow,
        ),
    ):
        result = tool._run(
            workflow_type="add-recipe",
            input=AddRecipeQueryInput(value="lentejas"),
        )

    assert "run-unwrap-1" in result
    assert captured["shared_context"]["recipe_query"] == "lentejas"


def test_start_workflow_tool_multi_call_independent():
    """Two sequential _run calls produce two independent enqueues (no shared
    mutable state leaks). PITFALL 5: invocation_id is the constant; per-call
    state must be local."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool
    from robotina.queue.task_types import AddRecipeQueryInput

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )

    mock_session = MagicMock()
    mock_queue = MagicMock()
    captured = []

    def capture_queue_workflow(**kwargs):
        captured.append(kwargs)
        return f"run-{len(captured)}"

    with (
        patch("robotina.db.SessionLocal", return_value=mock_session),
        patch("rq.Queue", return_value=mock_queue),
        patch("redis.Redis"),
        patch(
            "robotina.queue.workflow_runner.queue_workflow",
            side_effect=capture_queue_workflow,
        ),
    ):
        r1 = tool._run(workflow_type="add-recipe", input=AddRecipeQueryInput(value="lentejas"))
        r2 = tool._run(workflow_type="add-recipe", input=AddRecipeQueryInput(value="canelones"))

    assert "run-1" in r1
    assert "run-2" in r2
    assert len(captured) == 2
    assert captured[0]["shared_context"]["recipe_query"] == "lentejas"
    assert captured[1]["shared_context"]["recipe_query"] == "canelones"
    # Verify no cross-contamination of reply_context / household_id either
    assert captured[0]["shared_context"]["household_id"] == "h1"
    assert captured[1]["shared_context"]["household_id"] == "h1"


def test_start_workflow_tool_constructor_injection_unchanged():
    """Constructor-injected fields (chat_id/user_id/platform/household_id)
    propagate to the tool instance. D-03 explicitly preserves this pattern."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="chat-42",
        user_id="user-7",
        platform="telegram",
        household_id="house-1",
    )
    assert tool.chat_id == "chat-42"
    assert tool.user_id == "user-7"
    assert tool.platform == "telegram"
    assert tool.household_id == "house-1"


def test_start_workflow_tool_returns_workflow_run_id_on_success():
    """Happy path: _run returns a string carrying the workflow_run_id."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool
    from robotina.queue.task_types import AddRecipeQueryInput

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
            input=AddRecipeQueryInput(value="carbonara"),
        )

    assert isinstance(result, str)
    assert expected_run_id in result


def test_start_workflow_tool_error_path_returns_string():
    """Error path also returns a string (so the agent sees a ToolMessage with
    the failure and can react). With return_direct=False the LLM gets a
    chance to terminate cleanly via terminate()."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool
    from robotina.queue.task_types import AddRecipeQueryInput

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
            side_effect=ValueError("queue down"),
        ),
    ):
        result = tool._run(
            workflow_type="add-recipe",
            input=AddRecipeQueryInput(value="anything"),
        )

    assert isinstance(result, str)
    assert "failed" in result.lower() or "queue down" in result.lower()


def test_start_workflow_tool_auto_injects_reply_context():
    """StartWorkflowTool auto-injects reply_context (chat_id/user_id/platform)
    and household_id into shared_context — the LLM never sees these fields."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool
    from robotina.queue.task_types import AddRecipeQueryInput

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
            input=AddRecipeQueryInput(value="pasta"),
        )

    shared = captured["shared_context"]
    assert shared["recipe_query"] == "pasta"
    assert shared["reply_context"] == {
        "platform": "telegram",
        "chat_id": "chat-42",
        "user_id": "user-7",
    }
    assert shared["household_id"] == "house-1"


def test_start_workflow_tool_description_advertises_multi_call():
    """D-03: description tells the LLM the tool is multi-call and that
    terminate() ends the turn. Prior Phase 07.1 "do not call again" hack
    must not have crept back in."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )
    desc = tool.description.lower()
    # Old hack absent
    assert "do not call" not in desc
    assert "task is done" not in desc
    assert "shared_context" not in desc
    # New surface advertised
    assert "varias veces" in desc or "multi-call" in desc or "n flujos" in desc.lower()
    assert "terminate" in desc


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
        "input": {"value": "carbonara"},
        "response": "200",  # hallucinated extra field
    }

    with pytest.raises(ValidationError) as exc_info:
        tool.invoke(bad_args)

    assert "response" in str(exc_info.value)


def test_args_schema_allows_required_only():
    """A minimal valid call (workflow_type + input) still works under the
    strict schema — extra='forbid' must not break the happy path."""
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
                "input": {"value": "carbonara"},
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


# ---------------------------------------------------------------------------
# Flat-schema guardrails: top-level identity-field rejection and Literal narrowing
# ---------------------------------------------------------------------------


def test_args_schema_rejects_top_level_household_id():
    """The LLM cannot smuggle identity fields via the schema —
    extra='forbid' rejects top-level household_id / reply_context. The old
    WR-02 attack surface (LLM supplying these inside shared_context) is
    structurally eliminated; this test guards the replacement surface."""
    import pytest
    from pydantic import ValidationError

    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )

    for hostile_field, hostile_value in [
        ("household_id", "attacker-house"),
        ("reply_context", {"platform": "telegram", "chat_id": "evil", "user_id": "evil"}),
    ]:
        bad_args = {
            "workflow_type": "add-recipe",
            "input": {"value": "carbonara"},
            hostile_field: hostile_value,
        }
        with pytest.raises(ValidationError) as exc_info:
            tool.invoke(bad_args)
        assert hostile_field in str(exc_info.value)


def test_args_schema_rejects_unknown_workflow_type():
    """workflow_type is Literal['add-recipe']; any other value must fail at
    args validation, not at WORKFLOW_REGISTRY lookup."""
    import pytest
    from pydantic import ValidationError

    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )

    bad_args = {
        "workflow_type": "remove-recipe",  # not in the Literal
        "input": {"value": "carbonara"},
    }
    with pytest.raises(ValidationError) as exc_info:
        tool.invoke(bad_args)
    assert "workflow_type" in str(exc_info.value)
