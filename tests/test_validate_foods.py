"""Tests for ValidateFoodsTool.

Mocks ``httpx.AsyncClient.get`` to short-circuit the household-manager catalog
fetch, and mocks the matcher backend so the LLM semantic fallback never
actually calls a model.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import os
import pytest
from pydantic import ValidationError

from robotina.agent.tools._catalog_match import SemanticMatchEntry, SemanticMatchResult
from robotina.agent.tools.validate_foods import ValidateFoodsTool


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
    """Build an `AsyncClient()` mock whose `.get()` returns ``response``."""
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=None)
    ctor = MagicMock(return_value=cm)
    return ctor


def _fake_backend(structured: SemanticMatchResult):
    runnable = MagicMock()
    runnable.with_retry.return_value = runnable
    runnable.invoke.return_value = structured
    model = MagicMock()
    model.with_structured_output.return_value = runnable
    backend = MagicMock()
    backend.model = model
    return backend


# ---------------------------------------------------------------------------
# Strict args_schema
# ---------------------------------------------------------------------------

def test_args_schema_rejects_extra_fields():
    """extra='forbid' makes hallucinated extra args raise ValidationError."""
    with pytest.raises(ValidationError):
        ValidateFoodsTool().invoke({"names": [], "extra_field": "x"})


# ---------------------------------------------------------------------------
# Happy path — direct match only (no LLM call needed)
# ---------------------------------------------------------------------------

def test_direct_match_returns_matched_envelope():
    catalog = [{"id": "u1", "name": "Cebolla"}]
    response = _fake_response(200, json_data=catalog)

    with patch("robotina.agent.tools.validate_foods.httpx.AsyncClient", _patched_async_client(response)):
        result = ValidateFoodsTool().invoke({"names": ["Cebolla"]})

    assert result == {"matched": [{"name": "Cebolla", "id": "u1"}], "unmatched": []}


def test_semantic_fallback_marks_unmatched():
    catalog = [{"id": "u1", "name": "Cebolla"}]
    response = _fake_response(200, json_data=catalog)
    structured = SemanticMatchResult(matches=[
        SemanticMatchEntry(name="ricotón", catalog_id=None),
    ])
    backend = _fake_backend(structured)

    with patch("robotina.agent.tools.validate_foods.httpx.AsyncClient", _patched_async_client(response)), \
         patch("robotina.llm.make_backend", return_value=backend), \
         patch("robotina.agent.agents.get_agent_config") as gac:
        gac.return_value.model_config = {"provider": "stub"}
        gac.return_value.prompt_path = "src/robotina/agent/prompts/validate-catalog/V001.md"
        result = ValidateFoodsTool().invoke({"names": ["Cebolla", "ricotón"]})

    assert {"name": "Cebolla", "id": "u1"} in result["matched"]
    assert {"name": "ricotón", "id": None} in result["unmatched"]


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

def test_http_401_raises_runtime_error():
    response = _fake_response(401, text="Unauthorized")
    with patch("robotina.agent.tools.validate_foods.httpx.AsyncClient", _patched_async_client(response)):
        with pytest.raises(RuntimeError, match="unrecoverable auth error"):
            ValidateFoodsTool().invoke({"names": ["x"]})


def test_http_403_raises_runtime_error():
    response = _fake_response(403, text="Forbidden")
    with patch("robotina.agent.tools.validate_foods.httpx.AsyncClient", _patched_async_client(response)):
        with pytest.raises(RuntimeError, match="unrecoverable auth error"):
            ValidateFoodsTool().invoke({"names": ["x"]})


def test_http_500_returns_error_dict():
    response = _fake_response(500, text="internal error")
    with patch("robotina.agent.tools.validate_foods.httpx.AsyncClient", _patched_async_client(response)):
        result = ValidateFoodsTool().invoke({"names": ["x"]})
    assert result == {"error": 500, "message": "internal error"}


# ---------------------------------------------------------------------------
# Per-job tool injection wiring (jobs.py invariant)
# ---------------------------------------------------------------------------

def test_tool_metadata():
    t = ValidateFoodsTool()
    assert t.name == "validate-foods"
    assert "household catalog" in t.description.lower()


def test_agent_registry_tools_for_ingredients_remain_empty():
    """The architecture invariant: AGENT_REGISTRY[*].tools is always []. Tool
    wiring lives in robotina.queue.jobs.run_task per-task_type branches.
    """
    from robotina.agent.agents import get_agent_config
    c = get_agent_config("recipe-research-ingredients")
    assert c.tools == []
