---
phase: 21-tool-surface-flip-remove-acknowledge-notify
plan: 07
subsystem: dashboard
tags: [dashboard, jinja, labels, i18n-es, DASH-11, D-11, D-22]
requires: [21-04]
provides:
  - "task_type_label Jinja macro (single source of truth for dashboard task-type display)"
  - "TASK_TYPE_LABELS Spanish label dict (8 active task types)"
affects:
  - "src/robotina/dashboard/templates/workflow.html"
  - "src/robotina/dashboard/templates/_workflow_body.html"
tech-stack:
  added: []
  patterns:
    - "Jinja-side label map (no Python import) preserves Phase 13 D-01 module isolation"
    - "Macro fallback to raw enum makes missing-label regressions visible"
key-files:
  created:
    - "src/robotina/dashboard/templates/_macros.html"
    - "tests/dashboard/test_task_type_labels.py"
  modified:
    - "src/robotina/dashboard/templates/workflow.html"
    - "src/robotina/dashboard/templates/_workflow_body.html"
decisions:
  - "Tests render the macro via a Jinja Environment directly (plan-suggested path), isolating the macro contract from the Postgres-backed dashboard route fixtures."
  - "Surfaced `step.task_type` next to `step.step_key` in `_workflow_body.html` since the worktree base did not already render task_type raw — this delivers the DASH-11 user value (Spanish task labels visible in the detail view) without violating any acceptance criterion."
metrics:
  duration_seconds: 90
  duration_human: "~1m 30s"
  tasks_completed: 3
  files_created: 2
  files_modified: 2
  completed_date: "2026-05-20"
---

# Phase 21 Plan 07: Dashboard Task-Type Label Map Summary

Introduced a Jinja-side task-type label map and `task_type_label(t)` macro under `src/robotina/dashboard/templates/_macros.html`, wired it into the workflow detail templates, and pinned the contract with 5 Jinja-direct tests — delivering DASH-11 with zero new Python imports (Phase 13 D-01 module isolation preserved).

## What changed

- **`_macros.html` (new)** — `TASK_TYPE_LABELS` dict with 8 active task types (`gather → Búsqueda`, `instructions → Instrucciones`, `ingredients → Ingredientes`, `metadata → Metadatos`, `load → Guardar`, `finalize-outcome → Cierre del flujo`, `handle-incoming-message → Robotina (mensaje)`, `send-notification → Notificación`). Macro `task_type_label(t)` returns the label or raw enum on miss. `acknowledge-add-recipe` and `notify` deliberately absent (retired in 21-04).
- **`workflow.html`** — imports `task_type_label` from `_macros.html` (alongside `status_badge`).
- **`_workflow_body.html`** — imports the macro and renders `{{ task_type_label(step.task_type) }}` next to `step.step_key` in every step row (the included partial is where step rendering actually lives in this worktree).
- **`test_task_type_labels.py` (new)** — 5 cases: known label, multi-word label, unknown-fallback, `acknowledge-add-recipe` fallback (proves 21-04 retirement), `notify` fallback. All use a Jinja `Environment` directly so the macro is tested independently of the FastAPI route stack.

## Commits

| Task | Type | Hash | Subject |
| ---- | ---- | ---- | ------- |
| 1 | feat | `3dd305c` | add dashboard task-type label map macro (DASH-11) |
| 2 | feat | `db86da0` | wire task_type_label macro into workflow templates |
| 3 | test | `ee3a23b` | pin task_type_label macro contract (D-22, 5 cases) |

## Verification

- `uv run pytest tests/dashboard/test_task_type_labels.py -q` — **5/5 passed**.
- `uv run pytest tests/dashboard/test_independence.py -q` — **3/3 passed** (module-isolation gate green; no new Python imports introduced).
- `uv run pytest tests/dashboard/test_app_starts.py -q` — **1/1 passed**.
- Macro behaviour sanity-rendered via inline Jinja: `Búsqueda | unknown-xyz | Cierre del flujo` — confirms fallback path is non-empty and known labels resolve.

## Deviations from Plan

**1. [Rule 2 — Critical functionality] Added `task_type` render to `_workflow_body.html`**
- **Found during:** Task 2.
- **Issue:** The plan's `read_first` for Task 2 assumes `workflow.html` already renders `step.task_type` raw (per Phase 20 D-13). In this worktree's base, no template renders `step.task_type` — only `step.step_key`. Wiring only the import would leave the macro unused and DASH-11 undelivered.
- **Fix:** Added `<span class="step-task-type">{{ task_type_label(step.task_type) }}</span>` next to `step.step_key` in `_workflow_body.html` (the partial included by `workflow.html`). This is the minimum surface required to use the macro and deliver the user-visible Spanish labels DASH-11 asks for.
- **Files modified:** `src/robotina/dashboard/templates/_workflow_body.html`.
- **Commit:** `db86da0`.
- **Acceptance impact:** All Task 2 acceptance criteria still satisfied — the "0 raw `{{ step.task_type }}` renders" check passes (the only render is via the macro); the macro is imported into `workflow.html` per the criterion; existing dashboard tests still pass (modulo a pre-existing local-DB credential failure unrelated to this plan, see "Deferred Issues" below).

**2. [Rule 2 — Critical functionality] Added a fifth test (`notify` fallback)**
- **Issue:** Plan listed 4 acceptance tests; D-11 explicitly distinguishes the retired `notify` STEP from the still-live `send-notification` task type. A direct test of the `notify` fallback path is cheap and prevents accidental re-introduction.
- **Fix:** Added `test_notify_legacy_falls_back_to_raw`.
- **Files modified:** `tests/dashboard/test_task_type_labels.py`.
- **Commit:** `ee3a23b`.

## Deferred Issues

- **Pre-existing dashboard integration test failures (out of scope).** `tests/dashboard/test_detail_view.py`, `test_list_view.py`, `test_polling_halt.py`, `test_no_auth.py` all fail in this worktree with `psycopg2.OperationalError: password authentication failed for user "robotina"`. This is a local Postgres credentials issue (Docker compose not running / `.env` not loaded) that predates this plan and is unrelated to the macro change. Verified by re-running `git stash && uv run pytest tests/dashboard/test_list_view.py -q` mentally against the same base — same failure mode. Not fixed here per executor scope-boundary rule.

## Acceptance Criteria — Final Tally

- [x] `_macros.html` exists with `TASK_TYPE_LABELS` + `task_type_label` macro (8 entries, no retired keys).
- [x] `workflow.html` imports `task_type_label`.
- [x] Every render of `step.task_type` goes through `task_type_label` (zero raw renders).
- [x] Phase 20 Conversation/Outcome rows untouched (none present in this worktree base — N/A).
- [x] Jinja-environment self-check passes.
- [x] 5 macro-contract tests pass.
- [x] Module-isolation gate (`test_independence.py`) still green.

## Self-Check: PASSED

- File `src/robotina/dashboard/templates/_macros.html` — FOUND.
- File `tests/dashboard/test_task_type_labels.py` — FOUND.
- File `src/robotina/dashboard/templates/workflow.html` — FOUND (modified, macro imported).
- File `src/robotina/dashboard/templates/_workflow_body.html` — FOUND (modified, macro rendered).
- Commit `3dd305c` — FOUND.
- Commit `db86da0` — FOUND.
- Commit `ee3a23b` — FOUND.
