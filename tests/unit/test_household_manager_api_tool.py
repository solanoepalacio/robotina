"""Tests for HouseholdManagerApiTool.

Covers ROBOT-02: Robotina agent has household-manager-api tool
(auth injected invisibly; 401/403 raise hard errors).
Tests mock httpx responses — never call the real household-manager API.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


def test_household_manager_api_tool_construction():
    """ROBOT-02: HouseholdManagerApiTool can be constructed with household_id."""
    pytest.skip("ROBOT-02: not yet implemented")


def test_household_manager_api_tool_injects_bearer_token():
    """ROBOT-02: _run() sets Authorization: Bearer <HOUSEHOLD_MANAGER_API_KEY> on every request."""
    pytest.skip("ROBOT-02: not yet implemented")


def test_household_manager_api_tool_raises_runtime_error_on_401():
    """ROBOT-02: _run() raises RuntimeError when response status is 401."""
    pytest.skip("ROBOT-02: not yet implemented")


def test_household_manager_api_tool_raises_runtime_error_on_403():
    """ROBOT-02: _run() raises RuntimeError when response status is 403."""
    pytest.skip("ROBOT-02: not yet implemented")


def test_household_manager_api_tool_returns_error_dict_for_other_non_2xx():
    """ROBOT-02: _run() returns dict with 'error' and 'message' keys for non-401/403 non-2xx."""
    pytest.skip("ROBOT-02: not yet implemented")


def test_household_manager_api_tool_returns_json_on_success():
    """ROBOT-02: _run() returns parsed JSON dict on 2xx response."""
    pytest.skip("ROBOT-02: not yet implemented")


def test_household_manager_api_tool_household_id_not_in_run_signature():
    """ROBOT-02: household_id is a constructor field only — _run() has no household_id param."""
    pytest.skip("ROBOT-02: not yet implemented")
