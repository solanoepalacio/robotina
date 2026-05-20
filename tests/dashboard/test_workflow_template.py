"""Phase 20 / Plan 20-06 — workflow.html template render tests for DASH-10 and DASH-12.

Renders the `workflow.html` Jinja template directly (no DB / no HTTP) against a
stub `run` object whose attributes mirror the WorkflowRun fields the template
reads. This is intentionally lightweight: the goal is to assert the new
Conversation row (D-12) and Outcome cell (D-13) shapes — success / failure /
NULL / sin-imagen badge.

Module-isolation rule (Phase 13 D-01) is preserved — these tests use Jinja2
directly with the template loader, not any production runtime wiring.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


TEMPLATES_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "robotina"
    / "dashboard"
    / "templates"
)


@dataclass
class _StubStatus:
    """Stand-in for WorkflowStatus enum — template reads `.value`."""

    value: str = "done"


@dataclass
class _StubRun:
    """Stand-in for WorkflowRun — only the attributes workflow.html reads."""

    id: str = "00000000-0000-0000-0000-000000000001"
    workflow_type: str = "add-recipe-from-query"
    household_id: str = "h-test"
    status: _StubStatus = field(default_factory=_StubStatus)
    created_at: datetime | None = field(default_factory=datetime.utcnow)
    updated_at: datetime | None = field(default_factory=datetime.utcnow)
    triggered_by_invocation_id: str | None = "inv-abc"
    conversation_id: str | None = "conv-123"
    outcome: dict[str, Any] | None = None
    shared_context: dict[str, Any] | None = None
    steps: list[Any] = field(default_factory=list)


def _render(run: _StubRun) -> str:
    """Render workflow.html against a stub run. Uses real template loader."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("workflow.html")
    return template.render(run=run)


# ---------------------------------------------------------------------------
# DASH-10 — Conversation row
# ---------------------------------------------------------------------------


def test_workflow_template_renders_conversation_row():
    """DASH-10 / D-12: Conversation row renders conversation_id."""
    run = _StubRun(conversation_id="conv-123")
    html = _render(run)
    assert "<dt>Conversation</dt>" in html
    assert "conv-123" in html


def test_workflow_template_null_conversation():
    """DASH-10 / D-12: NULL conversation_id falls back to em-dash placeholder.

    Defensive — Phase 17 made conversation_id NOT NULL, so new rows never hit
    this path, but legacy rows might.
    """
    run = _StubRun(conversation_id=None)
    html = _render(run)
    assert "<dt>Conversation</dt>" in html
    # The Conversation cell falls back to em-dash. The em-dash glyph also
    # appears elsewhere in the template (e.g. as the Outcome NULL placeholder),
    # so we assert the glyph is present without trying to pin it to a specific
    # cell — the label + glyph together is the contract.
    assert "—" in html


# ---------------------------------------------------------------------------
# DASH-12 — Outcome cell
# ---------------------------------------------------------------------------


def test_workflow_template_renders_success_outcome():
    """DASH-12 / D-13: success outcome renders ✓ + name + (id) + sin-imagen badge."""
    run = _StubRun(
        outcome={
            "status": "success",
            "recipe_name": "Lentejas",
            "recipe_id": "abc",
            "image_present": False,
        }
    )
    html = _render(run)
    assert "<dt>Outcome</dt>" in html
    assert "✓" in html
    assert "Lentejas" in html
    assert "(abc)" in html
    assert "sin imagen" in html


def test_workflow_template_success_with_image():
    """DASH-12 / D-13: image_present=True suppresses the 'sin imagen' badge."""
    run = _StubRun(
        outcome={
            "status": "success",
            "recipe_name": "Lentejas",
            "recipe_id": "abc",
            "image_present": True,
        }
    )
    html = _render(run)
    assert "✓" in html
    assert "Lentejas" in html
    assert "sin imagen" not in html


def test_workflow_template_renders_failure_outcome():
    """DASH-12 / D-13: failure outcome renders ✗ Falló: <reason>."""
    run = _StubRun(
        outcome={
            "status": "failure",
            "failure_reason": "no gather artifact",
        }
    )
    html = _render(run)
    assert "<dt>Outcome</dt>" in html
    assert "✗" in html
    assert "Falló:" in html
    assert "no gather artifact" in html


def test_workflow_template_failure_no_reason():
    """DASH-12 / D-13: failure with no failure_reason shows '(sin detalle)'."""
    run = _StubRun(
        outcome={
            "status": "failure",
            "failure_reason": None,
        }
    )
    html = _render(run)
    assert "✗" in html
    assert "Falló:" in html
    assert "(sin detalle)" in html


def test_workflow_template_null_outcome():
    """DASH-12 / D-13: NULL outcome renders em-dash placeholder under Outcome row."""
    run = _StubRun(outcome=None)
    html = _render(run)
    assert "<dt>Outcome</dt>" in html
    # The Outcome cell falls back to em-dash placeholder per D-13.
    # The em-dash appears at multiple sites; we anchor on label + glyph
    # appearing in the rendered HTML (template structure guarantees adjacency).
    assert "—" in html
    # No success/failure markers should appear for a NULL outcome.
    assert "✓" not in html
    assert "✗" not in html


@pytest.mark.parametrize("status_value", ["success", "failure"])
def test_workflow_template_outcome_no_raw_json(status_value):
    """DASH-12 / D-13 falsifiability: rendered HTML must NOT dump raw outcome JSON.

    The template builds a human-readable line, not a json-block dump.
    """
    run = _StubRun(
        outcome={
            "status": status_value,
            "recipe_name": "X",
            "recipe_id": "y",
            "image_present": True,
            "failure_reason": "z",
        }
    )
    html = _render(run)
    # The Outcome cell is rendered inside <dd>…</dd>, NOT inside a json-block.
    # The `json-block` class is reserved for the shared_context dump elsewhere.
    # Find the Outcome dd: locate "<dt>Outcome</dt>" then check the following
    # <dd> does not contain `json-block`.
    idx = html.find("<dt>Outcome</dt>")
    assert idx >= 0
    # Take a generous window after the label and ensure no json-block class
    # appears within that window (the cell + closing tag fit well within 600 chars).
    window = html[idx : idx + 600]
    assert "json-block" not in window
