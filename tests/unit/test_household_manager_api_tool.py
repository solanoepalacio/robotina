"""Tests for HouseholdManagerApiTool.

Covers ROBOT-02: Robotina agent has household-manager-api tool
(auth injected invisibly; 401/403 raise hard errors).
Tests mock httpx responses — never call the real household-manager API.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


def test_household_manager_api_tool_construction():
    """ROBOT-02: HouseholdManagerApiTool can be constructed with household_id."""
    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    tool = HouseholdManagerApiTool(household_id="hh-123")
    assert tool.household_id == "hh-123"
    assert tool.name == "household-manager-api"


def test_household_manager_api_tool_injects_bearer_token(monkeypatch):
    """ROBOT-02: _run() sets Authorization: Bearer <HOUSEHOLD_MANAGER_API_KEY> on every request."""
    monkeypatch.setenv("HOUSEHOLD_MANAGER_API_KEY", "test-token-abc")
    monkeypatch.setenv("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")

    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    tool = HouseholdManagerApiTool(household_id="hh-1")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.json.return_value = {"items": []}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.request = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        tool._run("GET", "/api/recipes")

    call_kwargs = mock_client.request.call_args
    headers = call_kwargs.kwargs.get("headers", {})
    assert headers.get("Authorization") == "Bearer test-token-abc"


def test_household_manager_api_tool_raises_runtime_error_on_401(monkeypatch):
    """ROBOT-02: _run() raises RuntimeError when response status is 401."""
    monkeypatch.setenv("HOUSEHOLD_MANAGER_API_KEY", "bad-token")
    monkeypatch.setenv("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")

    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    tool = HouseholdManagerApiTool(household_id="hh-1")

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.is_success = False
    mock_response.text = "Unauthorized"

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.request = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="unrecoverable auth error"):
            tool._run("GET", "/api/recipes")


def test_household_manager_api_tool_raises_runtime_error_on_403(monkeypatch):
    """ROBOT-02: _run() raises RuntimeError when response status is 403."""
    monkeypatch.setenv("HOUSEHOLD_MANAGER_API_KEY", "wrong-scope")
    monkeypatch.setenv("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")

    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    tool = HouseholdManagerApiTool(household_id="hh-1")

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.is_success = False
    mock_response.text = "Forbidden"

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.request = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="unrecoverable auth error"):
            tool._run("GET", "/api/recipes")


def test_household_manager_api_tool_returns_error_dict_for_other_non_2xx(monkeypatch):
    """ROBOT-02: _run() returns dict with 'error' and 'message' keys for non-401/403 non-2xx."""
    monkeypatch.setenv("HOUSEHOLD_MANAGER_API_KEY", "token")
    monkeypatch.setenv("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")

    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    tool = HouseholdManagerApiTool(household_id="hh-1")

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.is_success = False
    mock_response.text = "Not Found"

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.request = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = tool._run("GET", "/api/recipes/missing-id")

    assert isinstance(result, dict)
    assert result["error"] == 404
    assert "Not Found" in result["message"]


def test_household_manager_api_tool_returns_json_on_success(monkeypatch):
    """ROBOT-02: _run() returns parsed JSON dict on 2xx response."""
    monkeypatch.setenv("HOUSEHOLD_MANAGER_API_KEY", "token")
    monkeypatch.setenv("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")

    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    tool = HouseholdManagerApiTool(household_id="hh-1")

    expected = {"items": [{"id": "r1", "name": "Pasta"}], "total": 1}
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.json.return_value = expected

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.request = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = tool._run("GET", "/api/recipes")

    assert result == expected


def test_household_manager_api_tool_household_id_not_in_run_signature():
    """ROBOT-02: household_id is a constructor field only — _run() has no household_id param."""
    import inspect
    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    sig = inspect.signature(HouseholdManagerApiTool._run)
    assert "household_id" not in sig.parameters, (
        "household_id must NOT be a _run() parameter — it is constructor-only (D-02)"
    )


# ---------------------------------------------------------------------------
# Strict args-schema tests
#
# Goal: an LLM-emitted tool call carrying an unknown field (e.g. ``response``)
# must NOT crash the worker with ``TypeError``. The Pydantic ``args_schema``
# with ``extra='forbid'`` converts it into a ``ValidationError`` at
# ``tool.invoke()`` time, which langgraph's ``ToolNode`` turns into a
# ``ToolMessage(status="error")`` the agent can recover from on its next turn.
# ---------------------------------------------------------------------------


def test_args_schema_forbids_unknown_field(monkeypatch):
    """An unknown LLM-emitted argument key raises pydantic ValidationError
    (not TypeError) and the error message names the offending field."""
    monkeypatch.setenv("HOUSEHOLD_MANAGER_API_KEY", "token")
    monkeypatch.setenv("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")

    from pydantic import ValidationError

    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool

    tool = HouseholdManagerApiTool(household_id="hh-1")

    # Reproduces the staging payload that previously crashed the worker:
    # the LLM emitted an extra `response` field alongside the valid args.
    bad_args = {
        "method": "GET",
        "path": "/api/foods",
        "body": None,
        "query": None,
        "response": "200",
    }

    with pytest.raises(ValidationError) as exc_info:
        tool.invoke(bad_args)

    # The error must reference the offending field so the agent can self-correct.
    assert "response" in str(exc_info.value)


def test_args_schema_allows_optional_omitted(monkeypatch):
    """Omitting optional ``body``/``query`` still works under the strict schema."""
    monkeypatch.setenv("HOUSEHOLD_MANAGER_API_KEY", "test-token")
    monkeypatch.setenv("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")

    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool

    tool = HouseholdManagerApiTool(household_id="hh-1")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.json.return_value = {"items": []}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.request = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        # No body, no query — strict schema must NOT require them.
        result = tool.invoke({"method": "GET", "path": "/api/foods"})

    assert result == {"items": []}


def test_args_schema_json_schema_forbids_extra():
    """JSON schema for the args model reports ``additionalProperties: false``,
    which is Pydantic v2's representation of ``extra='forbid'``. This is what
    LLM tool-binding adapters serialize to the model."""
    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool

    tool = HouseholdManagerApiTool(household_id="x")
    schema = tool.args_schema.model_json_schema()
    assert schema.get("additionalProperties") is False


def test_extra_field_in_agent_loop_yields_tool_error_message(monkeypatch):
    """End-to-end proof: a tool call with an extra field, driven through a
    real ``create_react_agent``, produces a ``ToolMessage(status="error")``
    rather than letting a ``TypeError`` escape ``agent.invoke()``.

    This is the load-bearing assertion — it reproduces the failure mode that
    cancelled three pending workflow steps in production and confirms the fix
    surfaces the validation error to the agent loop instead.
    """
    monkeypatch.setenv("HOUSEHOLD_MANAGER_API_KEY", "token")

    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langgraph.prebuilt import create_react_agent

    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool

    class CountingModel(FakeMessagesListChatModel):
        # FakeMessagesListChatModel doesn't know how to bind tools. The
        # prebuilt react agent calls ``model.bind_tools(...)`` before use;
        # returning ``self`` keeps the canned-response behavior intact.
        def bind_tools(self, tools, **kwargs):
            return self

    bad_tool_call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "household-manager-api",
                "args": {
                    "method": "GET",
                    "path": "/api/foods",
                    "body": None,
                    "query": None,
                    "response": "200",  # hallucinated extra field
                },
                "id": "tc-bad",
                "type": "tool_call",
            }
        ],
    )
    final_reply = AIMessage(
        content="ok, I will retry without the extra field",
        tool_calls=[],
    )
    model = CountingModel(responses=[bad_tool_call, final_reply])
    tool = HouseholdManagerApiTool(household_id="hh-1")

    agent = create_react_agent(model=model, tools=[tool])

    # Must NOT raise TypeError — the validation error is wrapped by langgraph's
    # default ToolNode error handler into a ToolMessage instead.
    result = agent.invoke({"messages": [HumanMessage(content="get foods")]})

    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1, (
        f"expected exactly 1 ToolMessage, got {len(tool_messages)}"
    )
    tm = tool_messages[0]
    assert tm.status == "error", (
        f"expected ToolMessage(status='error'), got status={tm.status!r}"
    )
    content_lower = str(tm.content).lower()
    # The error content must reference the validation problem so the agent
    # can recover. Pydantic v2 phrases this as
    # "response: Extra inputs are not permitted".
    assert "response" in content_lower
    assert "extra" in content_lower or "not permitted" in content_lower
