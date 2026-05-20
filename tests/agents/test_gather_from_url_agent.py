"""Phase 23 D-20 / URL-02 + URL-04: gather-from-url agent integration tests.

Drives the real ``langchain.agents.create_agent`` factory with a stubbed
``BaseChatModel`` (``FakeMessagesListChatModel``) so BOTH branches of the
V001 prompt are exercised end-to-end:

  1. ``test_gather_from_url_passes_through_scraped_recipe`` — when
     ``FetchAndScrapeTool`` returns a ``scraped_recipe`` payload, the agent
     emits a ``RecipeData`` whose fields mirror the scraper output verbatim.

  2. ``test_gather_from_url_extracts_from_html_text`` — URL-04 LLM-fallback
     path. When the tool returns ``scraped_recipe=None`` and ``html_text``
     populated, the stubbed model is scripted to emit a fresh ``RecipeData``
     derived from the page text. This is the load-bearing assertion that
     URL-04 is covered by a real automated test, not a grep-only contract.

The stubbed model uses the exact pattern proven in
``tests/unit/test_household_manager_api_tool.py`` (``CountingModel``
subclass + ``bind_tools(self)`` no-op). ``ToolStrategy(RecipeData)``
registers the schema as a synthetic structured-output tool named
``"RecipeData"`` (Phase 11 RESEARCH.md, Pitfall 1); the script emits a
tool_call to ``fetch-and-scrape`` first, then a tool_call named
``"RecipeData"`` carrying the final structured payload.

The ``response_format`` parameter is passed via ``ToolStrategy`` (matches
the Ollama path used in production by ``LLMBackend.create_agent``).
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage, HumanMessage

from robotina.agent.agents import AGENT_REGISTRY
from robotina.agent.tools.fetch_and_scrape import FetchAndScrapeTool
from robotina.queue.task_types import RecipeData


# ---------------------------------------------------------------------------
# Stub LLM — proven pattern from tests/unit/test_household_manager_api_tool.py.
# FakeMessagesListChatModel cannot bind tools natively; ``bind_tools`` returns
# self so the canned responses pass through unchanged.
# ---------------------------------------------------------------------------


class _StubChatModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def _v001_prompt() -> str:
    """Load the real V001 prompt body — URL-04 mandates the agent runs with
    the production prompt, not a stub."""
    cfg = AGENT_REGISTRY["gather-from-url"]
    return Path(cfg.prompt_path).read_text()


def _build_agent(model: _StubChatModel):
    """Build the gather-from-url agent with the real V001 prompt + tool +
    ``ToolStrategy(RecipeData)`` — same shape as ``OllamaBackend.create_agent``
    in production (``LLMBackend.create_agent`` in src/robotina/llm/__init__.py)."""
    return create_agent(
        model=model,
        tools=[FetchAndScrapeTool()],
        system_prompt=_v001_prompt(),
        response_format=ToolStrategy(RecipeData),
    )


# ---------------------------------------------------------------------------
# Branch 1: scraped_recipe pass-through
# ---------------------------------------------------------------------------


def test_gather_from_url_passes_through_scraped_recipe():
    scraped = {
        "name": "Canelones rellenos",
        "ingredients": [
            {"food_name": "harina", "unit_name": "g", "quantity": 500.0},
            {"food_name": "ricota", "unit_name": "g", "quantity": 250.0},
        ],
        "steps": [
            {"body": "Mezclar la masa.", "title": None},
            {"body": "Hornear 30 min.", "title": None},
        ],
        "source_url": "https://example.test/recetas/canelones",
    }
    tool_payload = {
        "source_url": "https://example.test/recetas/canelones",
        "scraped_recipe": scraped,
        "html_text": None,
    }

    fetch_tool_call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "fetch-and-scrape",
                "args": {"url": "https://example.test/recetas/canelones"},
                "id": "tc-fetch-1",
                "type": "tool_call",
            }
        ],
    )
    # Structured-output tool name = schema class name ("RecipeData"), per
    # ToolStrategy.
    structured_response = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "RecipeData",
                "args": scraped,
                "id": "tc-structured-1",
                "type": "tool_call",
            }
        ],
    )

    model = _StubChatModel(responses=[fetch_tool_call, structured_response])
    agent = _build_agent(model)

    with patch.object(
        FetchAndScrapeTool, "_run", return_value=json.dumps(tool_payload)
    ) as mock_run:
        result = agent.invoke(
            {
                "messages": [
                    HumanMessage(content="https://example.test/recetas/canelones")
                ]
            }
        )

    # Tool invoked exactly once (V001 prompt rule "exactly once").
    assert mock_run.call_count == 1, (
        f"fetch-and-scrape must be called exactly once; got {mock_run.call_count}"
    )

    sr = result["structured_response"]
    assert isinstance(sr, RecipeData), (
        f"structured_response is {type(sr).__name__}, expected RecipeData"
    )
    assert sr.name == "Canelones rellenos"
    assert len(sr.ingredients) == 2
    assert sr.ingredients[0].food_name == "harina"
    assert len(sr.steps) == 2
    assert sr.source_url == "https://example.test/recetas/canelones"


# ---------------------------------------------------------------------------
# Branch 2: html_text LLM-fallback extraction — URL-04 mandatory coverage
# ---------------------------------------------------------------------------


def test_gather_from_url_extracts_from_html_text():
    """URL-04: when scraped_recipe is None and html_text is populated, the
    agent must emit a RecipeData extracted from html_text via the LLM. The
    stubbed model simulates that extraction by emitting a structured-output
    tool_call whose args are derived from the page text in the tool result.

    This is the load-bearing URL-04 assertion. No pytest.skip, no grep
    fallback — the agent is driven through the html_text branch end-to-end
    by a stubbed BaseChatModel.
    """
    html_text = (
        "Lasaña de verduras\n\n"
        "Ingredientes:\n"
        "- 6 láminas de pasta\n"
        "- 200 g de espinaca\n"
        "- 1 cebolla\n\n"
        "Preparación:\n"
        "1. Saltear la cebolla y la espinaca.\n"
        "2. Armar capas y hornear 25 minutos.\n"
    )
    tool_payload = {
        "source_url": "https://example.test/recetas/lasagna-verduras",
        "scraped_recipe": None,
        "html_text": html_text,
    }
    extracted = {
        "name": "Lasaña de verduras",
        "ingredients": [
            {"food_name": "pasta", "unit_name": "lámina", "quantity": 6.0},
            {"food_name": "espinaca", "unit_name": "g", "quantity": 200.0},
            {"food_name": "cebolla", "unit_name": None, "quantity": 1.0},
        ],
        "steps": [
            {"body": "Saltear la cebolla y la espinaca.", "title": None},
            {"body": "Armar capas y hornear 25 minutos.", "title": None},
        ],
        "source_url": "https://example.test/recetas/lasagna-verduras",
    }

    fetch_tool_call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "fetch-and-scrape",
                "args": {"url": "https://example.test/recetas/lasagna-verduras"},
                "id": "tc-fetch-2",
                "type": "tool_call",
            }
        ],
    )
    structured_response = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "RecipeData",
                "args": extracted,
                "id": "tc-structured-2",
                "type": "tool_call",
            }
        ],
    )

    model = _StubChatModel(responses=[fetch_tool_call, structured_response])
    agent = _build_agent(model)

    with patch.object(
        FetchAndScrapeTool, "_run", return_value=json.dumps(tool_payload)
    ) as mock_run:
        result = agent.invoke(
            {
                "messages": [
                    HumanMessage(
                        content="https://example.test/recetas/lasagna-verduras"
                    )
                ]
            }
        )

    assert mock_run.call_count == 1, (
        f"fetch-and-scrape must be called exactly once; got {mock_run.call_count}"
    )

    sr = result["structured_response"]
    assert isinstance(sr, RecipeData), (
        f"structured_response is {type(sr).__name__}, expected RecipeData"
    )
    # URL-04 required fields: name + ≥2 ingredients + ≥1 step + source_url
    assert sr.name == "Lasaña de verduras"
    assert len(sr.ingredients) >= 2, (
        f"URL-04 mandates ≥2 ingredients; got {len(sr.ingredients)}"
    )
    assert len(sr.steps) >= 1, (
        f"URL-04 mandates ≥1 step; got {len(sr.steps)}"
    )
    assert sr.source_url == "https://example.test/recetas/lasagna-verduras"
