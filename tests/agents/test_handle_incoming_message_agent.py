"""Robotina V007 prompt-contract tests (Phase 23 plan 23-05).

Asserts that the handle-incoming-message agent is wired to the V007 prompt
and that V007 contains the URL-handling rules introduced by Phase 23
(D-05 URL detection, D-06 one start-workflow per URL, D-07 mixed routing).
Also asserts V006 is retained for rollback (D-25).
"""
from __future__ import annotations

import re
from pathlib import Path

from robotina.agent.agents import AGENT_REGISTRY


REPO_ROOT = Path(__file__).resolve().parents[2]
V007_PATH = REPO_ROOT / "src" / "robotina" / "agent" / "prompts" / "robotina" / "V007.md"
V006_PATH = REPO_ROOT / "src" / "robotina" / "agent" / "prompts" / "robotina" / "V006.md"


def _read_v007() -> str:
    return V007_PATH.read_text(encoding="utf-8")


def test_handle_incoming_message_prompt_path_is_v007():
    """Phase 23 D-05/D-06/D-07: agents.py points handle-incoming-message at V007.md."""
    cfg = AGENT_REGISTRY["handle-incoming-message"]
    assert cfg.prompt_path.endswith("V007.md"), (
        f"prompt_path is {cfg.prompt_path!r}, expected to end with V007.md"
    )


def test_v007_file_exists():
    """V007.md exists on disk."""
    assert V007_PATH.is_file(), f"missing V007 prompt at {V007_PATH}"


def test_v007_contains_url_handling_section():
    """V007 has a dedicated URL handling section (D-05/D-06/D-07)."""
    body = _read_v007()
    assert "URL handling" in body, "V007 missing 'URL handling' section heading"


def test_v007_contains_add_recipe_from_url_example():
    """V007 contains worked examples that use add-recipe-from-url variant."""
    body = _read_v007()
    assert "add-recipe-from-url" in body, "V007 missing add-recipe-from-url literal"


def test_v007_contains_add_recipe_from_query_example():
    """V007 retains the add-recipe-from-query variant for text-only recipes."""
    body = _read_v007()
    assert "add-recipe-from-query" in body, "V007 missing add-recipe-from-query literal"


def test_v007_drops_legacy_add_recipe_literal():
    """Phase 23 D-01: bare workflow_type="add-recipe" (no -from-suffix) must not appear.

    Matches the literal `"add-recipe"` followed by anything other than `-` (the
    suffix character of the new names). This catches both `workflow_type="add-recipe"`
    in JSON and any prose reference to the old name as a workflow_type value.
    """
    body = _read_v007()
    legacy_matches = re.findall(r'"add-recipe"(?!-)', body)
    assert legacy_matches == [], (
        f"V007 still references legacy bare 'add-recipe' workflow_type: {legacy_matches}"
    )


def test_v007_does_not_deflect_urls():
    """V007 must NOT contain the V006 URL-deflection line ('Todavía no manejo enlaces')."""
    body = _read_v007()
    assert "Todavía no manejo enlaces" not in body, (
        "V007 still deflects URLs; the URL-not-supported message must be removed"
    )


def test_v006_still_exists_for_rollback():
    """Phase 23 D-25: V006.md is retained in the prompts directory for rollback."""
    assert V006_PATH.is_file(), (
        f"V006.md missing at {V006_PATH} — Phase 23 D-25 requires retention for rollback"
    )
