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
