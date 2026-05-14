"""Unit tests for robotina.agent.tools._catalog_match.

Covers:
- NFKD direct-match shortcut (no LLM call)
- Single batched LLM call for unmatched remainder
- Hallucinated-name filter (LLM returns a name not in input)
- Hallucinated-id filter (LLM returns a catalog_id not in catalog)
- catalog_id=None → unmatched envelope

The matcher backend is mocked at ``robotina.agent.tools._catalog_match.make_backend``
so no real LLM is invoked.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from robotina.agent.tools._catalog_match import (
    SemanticMatchEntry,
    SemanticMatchResult,
    _normalize,
    resolve_catalog,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_backend(structured_result: SemanticMatchResult):
    """Build a (backend mock, runnable mock) pair that returns ``structured_result``.

    Returns a tuple usable with ``patch`` as ``side_effect=lambda cfg: backend``.
    """
    runnable = MagicMock()
    runnable.with_retry.return_value = runnable
    runnable.invoke.return_value = structured_result

    model = MagicMock()
    model.with_structured_output.return_value = runnable

    backend = MagicMock()
    # Make isinstance(backend.model, ChatOllama) return False (use a plain Mock).
    backend.model = model
    return backend, runnable, model


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------

def test_normalize_basic_casefold():
    assert _normalize("Cebolla") == _normalize("cebolla") == "cebolla"


def test_normalize_strips_accents_and_uppercases():
    assert _normalize("CEBOLLÁ") == "cebolla"


def test_normalize_n_tilde_drops_to_n():
    assert _normalize("ñoqui") == "noqui"


def test_normalize_strips_whitespace():
    assert _normalize("  pasta  ") == "pasta"


# ---------------------------------------------------------------------------
# Direct-match shortcut (no LLM call)
# ---------------------------------------------------------------------------

def test_resolve_catalog_empty_names_returns_empty_envelope():
    assert resolve_catalog("food", [{"id": "u1", "name": "Cebolla"}], []) == {
        "matched": [],
        "unmatched": [],
    }


def test_resolve_catalog_direct_match_skips_llm():
    """Direct NFKD match must NOT invoke the matcher LLM."""
    catalog = [{"id": "u1", "name": "Cebolla"}]
    with patch("robotina.llm.make_backend") as mb:
        result = resolve_catalog("food", catalog, ["CEBOLLA"])
    assert mb.call_count == 0  # no backend constructed
    assert result == {"matched": [{"name": "CEBOLLA", "id": "u1"}], "unmatched": []}


def test_resolve_catalog_nfkd_accent_strip_matches():
    catalog = [{"id": "u1", "name": "Cebolla"}]
    with patch("robotina.llm.make_backend") as mb:
        result = resolve_catalog("food", catalog, ["cebollá"])
    assert mb.call_count == 0
    assert result == {"matched": [{"name": "cebollá", "id": "u1"}], "unmatched": []}


# ---------------------------------------------------------------------------
# Semantic fallback (batched LLM call)
# ---------------------------------------------------------------------------

def test_resolve_catalog_semantic_fallback_invokes_llm_once_with_all_unmatched():
    catalog = [{"id": "u1", "name": "Cebolla"}, {"id": "u2", "name": "Papa"}]
    structured = SemanticMatchResult(matches=[
        SemanticMatchEntry(name="patata", catalog_id="u2"),
        SemanticMatchEntry(name="ricoton", catalog_id=None),
    ])
    backend, runnable, model = _patch_backend(structured)

    with patch("robotina.llm.make_backend", return_value=backend), \
         patch("robotina.agent.agents.get_agent_config") as gac:
        gac.return_value.model_config = {"provider": "stub"}
        gac.return_value.prompt_path = "src/robotina/agent/prompts/validate-catalog/V001.md"
        result = resolve_catalog("food", catalog, ["patata", "ricoton"])

    # Exactly one matcher invocation.
    assert runnable.invoke.call_count == 1
    # The full unmatched-names list was passed in one message.
    user_msg = runnable.invoke.call_args.args[0][1].content
    assert "patata" in user_msg
    assert "ricoton" in user_msg

    assert {"name": "patata", "id": "u2"} in result["matched"]
    assert {"name": "ricoton", "id": None} in result["unmatched"]


def test_resolve_catalog_unmatched_null_propagates():
    catalog = [{"id": "u1", "name": "Cebolla"}]
    structured = SemanticMatchResult(matches=[
        SemanticMatchEntry(name="zanahoria", catalog_id=None),
    ])
    backend, *_ = _patch_backend(structured)

    with patch("robotina.llm.make_backend", return_value=backend), \
         patch("robotina.agent.agents.get_agent_config") as gac:
        gac.return_value.model_config = {"provider": "stub"}
        gac.return_value.prompt_path = "src/robotina/agent/prompts/validate-catalog/V001.md"
        result = resolve_catalog("food", catalog, ["zanahoria"])

    assert result == {"matched": [], "unmatched": [{"name": "zanahoria", "id": None}]}


# ---------------------------------------------------------------------------
# Defensive filters
# ---------------------------------------------------------------------------

def test_resolve_catalog_drops_hallucinated_names():
    """LLM returns a name that wasn't in the input list — must be discarded."""
    catalog = [{"id": "u1", "name": "Cebolla"}, {"id": "u2", "name": "Papa"}]
    structured = SemanticMatchResult(matches=[
        SemanticMatchEntry(name="not-in-input", catalog_id="u1"),
        SemanticMatchEntry(name="patata", catalog_id="u2"),
    ])
    backend, *_ = _patch_backend(structured)

    with patch("robotina.llm.make_backend", return_value=backend), \
         patch("robotina.agent.agents.get_agent_config") as gac:
        gac.return_value.model_config = {"provider": "stub"}
        gac.return_value.prompt_path = "src/robotina/agent/prompts/validate-catalog/V001.md"
        result = resolve_catalog("food", catalog, ["patata"])

    # Hallucinated name dropped; real match preserved.
    assert {"name": "patata", "id": "u2"} in result["matched"]
    assert all(m["name"] != "not-in-input" for m in result["matched"])


def test_resolve_catalog_drops_hallucinated_catalog_id():
    """LLM returns a catalog_id that isn't in the catalog — treat name as unmatched."""
    catalog = [{"id": "u1", "name": "Cebolla"}]
    structured = SemanticMatchResult(matches=[
        SemanticMatchEntry(name="patata", catalog_id="bogus-id"),
    ])
    backend, *_ = _patch_backend(structured)

    with patch("robotina.llm.make_backend", return_value=backend), \
         patch("robotina.agent.agents.get_agent_config") as gac:
        gac.return_value.model_config = {"provider": "stub"}
        gac.return_value.prompt_path = "src/robotina/agent/prompts/validate-catalog/V001.md"
        result = resolve_catalog("food", catalog, ["patata"])

    assert result["matched"] == []
    assert {"name": "patata", "id": None} in result["unmatched"]


def test_resolve_catalog_unaddressed_name_becomes_unmatched():
    """If the LLM doesn't return an entry for an input name, that name is unmatched."""
    catalog = [{"id": "u1", "name": "Cebolla"}]
    structured = SemanticMatchResult(matches=[])  # LLM skipped everything
    backend, *_ = _patch_backend(structured)

    with patch("robotina.llm.make_backend", return_value=backend), \
         patch("robotina.agent.agents.get_agent_config") as gac:
        gac.return_value.model_config = {"provider": "stub"}
        gac.return_value.prompt_path = "src/robotina/agent/prompts/validate-catalog/V001.md"
        result = resolve_catalog("food", catalog, ["zanahoria", "ajo"])

    assert {"name": "zanahoria", "id": None} in result["unmatched"]
    assert {"name": "ajo", "id": None} in result["unmatched"]
    assert result["matched"] == []


# ---------------------------------------------------------------------------
# AGENT_REGISTRY wiring
# ---------------------------------------------------------------------------

def test_validate_catalog_agent_config_loadable():
    from robotina.agent.agents import get_agent_config
    c = get_agent_config("validate-catalog")
    assert c.prompt_path.endswith("validate-catalog/V001.md")
    assert c.response_format_model is SemanticMatchResult
    assert c.tools == []
