"""DASH-11 / D-22 — pin the dashboard task-type label map.

These tests render the `task_type_label` macro from
`src/robotina/dashboard/templates/_macros.html` directly via a Jinja
environment. The Jinja-direct path isolates the label logic from the
FastAPI route stack and the Postgres-backed `db_session` fixture, so
the macro contract is verified independently of integration plumbing
(Phase 13 D-01 module isolation also implies the label dict must be
testable without importing any non-dashboard Python module).

Coverage:
  - known task type → Spanish label (gather → "Búsqueda")
  - finalize-outcome → "Cierre del flujo" (multi-word value)
  - unknown task type → raw enum fallback (no KeyError, no empty string)
  - retired task type (acknowledge-add-recipe) → fallback path
    (asserts the legacy label is genuinely gone per 21-04)
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def _make_env() -> Environment:
    # Resolve the dashboard templates dir relative to the repo root so the
    # test is invariant to CWD (pytest discovery from any subdir).
    repo_root = Path(__file__).resolve().parents[2]
    templates_dir = repo_root / "src" / "robotina" / "dashboard" / "templates"
    return Environment(loader=FileSystemLoader(str(templates_dir)))


def _render(env: Environment, value: str) -> str:
    tpl = env.from_string(
        "{% from '_macros.html' import task_type_label %}"
        "{{ task_type_label('" + value + "') }}"
    )
    return tpl.render().strip()


def test_known_task_type_renders_spanish_label() -> None:
    env = _make_env()
    assert _render(env, "gather") == "Búsqueda"


def test_finalize_outcome_label() -> None:
    env = _make_env()
    assert _render(env, "finalize-outcome") == "Cierre del flujo"


def test_recipe_image_label() -> None:
    # Phase 24-09 D-21 — `recipe-image` step renders as "Imagen" so the
    # new workflow step surfaces in Spanish on the dashboard timeline.
    env = _make_env()
    assert _render(env, "recipe-image") == "Imagen"


def test_unknown_task_type_falls_back_to_raw() -> None:
    env = _make_env()
    assert _render(env, "unknown-task-xyz") == "unknown-task-xyz"


def test_acknowledge_legacy_falls_back_to_raw() -> None:
    # 21-04 retired acknowledge-add-recipe. If a legacy step row surfaces
    # it in the detail view, the macro must NOT have a Spanish label for
    # it — it must fall through so the regression is visible.
    env = _make_env()
    assert _render(env, "acknowledge-add-recipe") == "acknowledge-add-recipe"


def test_notify_legacy_falls_back_to_raw() -> None:
    # `notify` (the legacy STEP — distinct from the `send-notification`
    # task type that RespondTool still uses) was retired in 21-04.
    env = _make_env()
    assert _render(env, "notify") == "notify"
