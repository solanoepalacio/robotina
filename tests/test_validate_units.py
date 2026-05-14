"""Tests for ValidateUnitsTool. Mirrors test_validate_foods.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from robotina.agent.tools._catalog_match import SemanticMatchEntry, SemanticMatchResult
from robotina.agent.tools.validate_units import ValidateUnitsTool


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("HOUSEHOLD_MANAGER_API_KEY", "test-key")
    monkeypatch.setenv("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")


def _fake_response(status_code: int, json_data=None, text: str = ""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = json_data
    resp.text = text
    return resp


def _patched_async_client(response):
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=cm)


def _fake_backend(structured: SemanticMatchResult):
    runnable = MagicMock()
    runnable.with_retry.return_value = runnable
    runnable.invoke.return_value = structured
    model = MagicMock()
    model.with_structured_output.return_value = runnable
    backend = MagicMock()
    backend.model = model
    return backend


def test_args_schema_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ValidateUnitsTool().invoke({"names": [], "extra": 1})


def test_direct_match_returns_matched_envelope():
    catalog = [{"id": "u1", "name": "gramo"}]
    response = _fake_response(200, json_data=catalog)
    with patch("robotina.agent.tools.validate_units.httpx.AsyncClient", _patched_async_client(response)):
        result = ValidateUnitsTool().invoke({"names": ["Gramo"]})
    assert result == {"matched": [{"name": "Gramo", "id": "u1"}], "unmatched": []}


def test_semantic_fallback_marks_unmatched():
    catalog = [{"id": "u1", "name": "gramo"}]
    response = _fake_response(200, json_data=catalog)
    structured = SemanticMatchResult(matches=[
        SemanticMatchEntry(name="pellizco", catalog_id=None),
    ])
    backend = _fake_backend(structured)
    with patch("robotina.agent.tools.validate_units.httpx.AsyncClient", _patched_async_client(response)), \
         patch("robotina.llm.make_backend", return_value=backend), \
         patch("robotina.agent.agents.get_agent_config") as gac:
        gac.return_value.model_config = {"provider": "stub"}
        gac.return_value.prompt_path = "src/robotina/agent/prompts/validate-catalog/V001.md"
        result = ValidateUnitsTool().invoke({"names": ["pellizco"]})
    assert result == {"matched": [], "unmatched": [{"name": "pellizco", "id": None}]}


def test_http_401_raises_runtime_error():
    response = _fake_response(401, text="Unauthorized")
    with patch("robotina.agent.tools.validate_units.httpx.AsyncClient", _patched_async_client(response)):
        with pytest.raises(RuntimeError, match="unrecoverable auth error"):
            ValidateUnitsTool().invoke({"names": ["x"]})


def test_http_500_returns_error_dict():
    response = _fake_response(500, text="boom")
    with patch("robotina.agent.tools.validate_units.httpx.AsyncClient", _patched_async_client(response)):
        result = ValidateUnitsTool().invoke({"names": ["x"]})
    assert result == {"error": 500, "message": "boom"}


def test_tool_metadata():
    t = ValidateUnitsTool()
    assert t.name == "validate-units"
    assert "unit" in t.description.lower()
