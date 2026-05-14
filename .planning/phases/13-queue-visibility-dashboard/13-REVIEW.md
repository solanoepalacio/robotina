---
phase: 13-queue-visibility-dashboard
reviewed: 2026-05-14T00:00:00Z
depth: standard
files_reviewed: 29
files_reviewed_list:
  - .env.example
  - Dockerfile
  - docker-compose.yml
  - migrations/versions/0005_dashboard_columns.py
  - pyproject.toml
  - src/robotina/dashboard/__init__.py
  - src/robotina/dashboard/app.py
  - src/robotina/dashboard/deps.py
  - src/robotina/dashboard/queries.py
  - src/robotina/dashboard/static/dashboard.css
  - src/robotina/dashboard/static/htmx.version.txt
  - src/robotina/dashboard/templates/_run_rows.html
  - src/robotina/dashboard/templates/_status_badge.html
  - src/robotina/dashboard/templates/_workflow_body.html
  - src/robotina/dashboard/templates/base.html
  - src/robotina/dashboard/templates/index.html
  - src/robotina/dashboard/templates/workflow.html
  - src/robotina/queue/jobs.py
  - src/robotina/queue/models.py
  - src/robotina/queue/workflow_runner.py
  - tests/dashboard/__init__.py
  - tests/dashboard/conftest.py
  - tests/dashboard/test_app_starts.py
  - tests/dashboard/test_detail_view.py
  - tests/dashboard/test_independence.py
  - tests/dashboard/test_list_view.py
  - tests/dashboard/test_no_auth.py
  - tests/dashboard/test_polling_halt.py
  - tests/test_workflow_runner.py
findings:
  critical: 1
  warning: 6
  info: 4
  total: 11
status: fixed
fixed_at: 2026-05-14T00:00:00Z
fixed_findings: [CR-01, WR-01, WR-02, WR-03, WR-04, WR-05, WR-06]
remaining_findings: [IN-01, IN-02, IN-03, IN-04]
remaining_note: info-only; out of default --fix scope
---

# Phase 13: Code Review Report

**Reviewed:** 2026-05-14
**Depth:** standard
**Files Reviewed:** 29
**Status:** issues_found

## Summary

The dashboard implementation cleanly observes the user-locked D-01 independence rule (verified by `test_independence.py` and confirmed by reading every file in `src/robotina/dashboard/` — only `robotina.db` and `robotina.queue.models` are imported). Jinja2 autoescape is on (FastAPI's `Jinja2Templates` enables it for `.html`), HTMX is vendored with a checksum matching the version file, and the polling-halt contract in `_workflow_body.html` correctly omits `hx-get`/`hx-trigger`/`hx-swap` when the workflow is terminal. The migration is non-blocking (nullable columns).

Concerns center on:
1. A pre-existing `NoneType` dereference in `on_step_failed` that the new code did not address while editing the same function.
2. The dashboard binds `0.0.0.0` unconditionally with no auth — fine for staging-on-VPN, dangerous on any reachable interface.
3. Several test correctness/quality issues that weaken the safety net the user is relying on.

## Critical Issues

### CR-01: `on_step_failed` dereferences `run` without nil check

**File:** `src/robotina/queue/workflow_runner.py:442-443`
**Issue:** The code fetches `run` and then immediately assigns `run.status = WorkflowStatus.FAILED` without checking for `None`. If a step exists but its parent `WorkflowRun` was deleted, archived, or was never present (FK is `nullable=False` so unusual, but possible via direct DB manipulation or future migrations), this raises `AttributeError: 'NoneType' object has no attribute 'status'` — which then gets re-raised through `run_task` and crashes the worker. The very next line (`run.shared_context`, line 459) is gated with `if run is not None`, demonstrating the author already knew `run` could be None; the FAILED assignment was missed. This is in code added/touched this phase (the `exc` parameter and dead-letter block are Phase 13 work).

**Fix:**
```python
run = session.query(WorkflowRun).filter(WorkflowRun.id == step.workflow_run_id).first()
if run is not None:
    run.status = WorkflowStatus.FAILED
session.commit()
```

## Warnings

### WR-01: Dashboard binds `0.0.0.0` by default with no auth

**File:** `src/robotina/dashboard/__init__.py:24`
**Issue:** `uvicorn.run(..., host="0.0.0.0", ...)` binds the dashboard to every interface on the host. Combined with the explicit "no auth — SPEC out of scope" stance, anyone who can reach the host on `DASHBOARD_PORT` (default 8001) can read every workflow's `shared_context` (which historically contains `reply_context` with Telegram `chat_id`/`user_id`), `step_input` (which can include recipe URLs, household identifiers), and `failure_reason` (which is `f"{type(exc).__name__}: {exc}"` and may include partial data depending on the exception). SPEC declares "dev+staging only", but the binary itself enforces nothing — a production-by-mistake run leaks data.

**Fix:** Default to `127.0.0.1` and require an explicit env var to bind publicly:
```python
host = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
uvicorn.run("robotina.dashboard.app:app", host=host, port=port, log_level="info")
```
Document in `.env.example` that `DASHBOARD_HOST=0.0.0.0` is required for compose.

### WR-02: `failure_reason` may leak sensitive exception detail

**File:** `src/robotina/queue/workflow_runner.py:423-426`, rendered at `src/robotina/dashboard/templates/_workflow_body.html:35`
**Issue:** D-16 fixes the format as `f"{type(exc).__name__}: {exc}"` but `str(exc)` for common exceptions can include the offending value verbatim — e.g., `KeyError: 'RECIPE_RESEARCH_API_TOKEN'` (env-var name), `httpx.HTTPStatusError` may include the request URL + headers in `.message`, Pydantic `ValidationError` dumps full input payloads. Combined with WR-01 (no auth, public bind), this widens the blast radius. Autoescape keeps it from being XSS, but the string itself is the leak.

**Fix:** Either truncate at a safe length (e.g., 200 chars), or whitelist exception classes whose `str()` is known safe, or scrub by regex. At minimum, document in SPEC/PLAN that `failure_reason` may contain secrets and the dashboard must therefore remain on a private network.

### WR-03: `test_list_view_returns_200_when_empty` does not actually test the empty state

**File:** `tests/dashboard/test_list_view.py:14-34`
**Issue:** The test's docstring claims it verifies the empty-state path, but the body only asserts `"Workflows" in resp.text` — that substring appears in both the populated table (`<h1>Workflows</h1>`) and the empty state. Because the test uses a shared DB and explicitly refuses to truncate (per Pitfall 7), it cannot actually force an empty-state render. The "empty state reachable" claim is unverified by this test — only the separate `test_index_template_renders_empty_state_directly` actually exercises it. The misnomer wastes the safety net.

**Fix:** Either delete the test (the template-only sibling is sufficient) or rename it to `test_list_view_returns_200` and remove the misleading docstring. Do NOT pretend it covers the empty-state acceptance.

### WR-04: `test_independence.py` import-grep is text-only and bypassable

**File:** `tests/dashboard/test_independence.py:32-60`
**Issue:** The forbidden-imports check uses substring matching on file text. False negatives:
- `from robotina .agent import ...` (extra space) — not caught.
- Imports done lazily via `importlib.import_module("robotina.agent.foo")` — not caught.
- Imports done via `__import__("robotina.agent")` — not caught.
- Re-exports through a third module (e.g. `from robotina.utils import x` where utils re-exports from agent) — not caught.

The user has flagged D-01 as user-locked. The test enforces the most common case but is not airtight.

**Fix:** Use AST-based analysis (`ast.parse` + walk `Import`/`ImportFrom` nodes) instead of substring scanning. Also assert at the *package* level by importing `robotina.dashboard` in a subprocess and asserting `sys.modules` keys do not include any forbidden prefix.

### WR-05: `_run_rows.html` falsy check on non-nullable `household_id`

**File:** `src/robotina/dashboard/templates/_run_rows.html:13`
**Issue:** `{% if not run.household_id %}muted{% endif %}` and the `or "—"` fallback both presume `household_id` can be empty. But `WorkflowRun.household_id` is `nullable=False` in `models.py:32`, and the only existing producer (`queue_workflow`) always passes a string. The template branch is dead and gives reviewers the false impression that null is possible. If a column constraint changes in the future this becomes silent (no test fails), but the larger issue is misleading reader expectations.

**Fix:** Either remove the `{% if not run.household_id %}muted{% endif %}` and `or "—"`, or change `WorkflowRun.household_id` to nullable. Pick one; the dead branch is rot.

### WR-06: Detail view does not handle missing `run.steps` collection ordering for ties

**File:** `src/robotina/dashboard/app.py:69`, `src/robotina/queue/workflow_runner.py:141-147`
**Issue:** `sorted(run.steps, key=lambda s: s.step_order)` is stable in Python, but `step_order` is assigned by enumeration of `workflow_def.steps` so within a single workflow_type the orders are unique. However the migration adds no uniqueness constraint on `(workflow_run_id, step_order)` — manual SQL edits or future code that reuses `step_order` would render the detail view in an undefined order with no diagnostic. A duplicate `step_order` would be a real bug if it ever happened.

**Fix:** Add a secondary sort key (e.g., `(s.step_order, s.step_key)`) so the rendering is deterministic even if `step_order` collides. Optionally add a `UniqueConstraint("workflow_run_id", "step_order")` in a follow-up migration.

## Info

### IN-01: Dockerfile uv version pin is open-ended

**File:** `Dockerfile:11`
**Issue:** `pip install --no-cache-dir 'uv>=0.4'` accepts any future uv release. `uv sync --frozen` consumes `uv.lock` so deps are reproducible, but uv itself is not. A breaking uv CLI change silently re-installs and breaks the image.

**Fix:** Pin a known-good upper bound (`'uv>=0.4,<1.0'`) or pin exactly (`'uv==<x.y.z>'`) and update intentionally.

### IN-02: Migration revision IDs are sequential strings

**File:** `migrations/versions/0005_dashboard_columns.py:14-15`
**Issue:** Alembic conventionally uses random hex revision IDs to avoid merge collisions when two branches both add `0006`. The project appears to use sequential IDs throughout, so this is consistent — flagging as info only. If two contributors merge plans simultaneously this will collide.

**Fix:** None required for this PR. Consider switching to hash-based revision IDs in a future infra phase.

### IN-03: `dashboard.css` color `#DC2626` duplicated between `.failure-block` and `.badge--failed`

**File:** `src/robotina/dashboard/static/dashboard.css:184, 253`
**Issue:** The red color `#DC2626` is hard-coded twice. UI-SPEC has color tokens as CSS custom properties for the neutral palette; the status colors are inlined. Future redesigns touching "the failure red" must edit two places.

**Fix:** Add `--color-failed: #DC2626;` (and analogous tokens for the other status colors) to `:root` and reference via `var(--color-failed)`.

### IN-04: `tests/dashboard/__init__.py` is empty

**File:** `tests/dashboard/__init__.py:1`
**Issue:** Empty `__init__.py` is fine, but pytest with default `rootdir` discovery and `testpaths = ["tests"]` does not need it. Harmless; flagging because it's redundant. (Some setups need it for namespace tests — verify there's a reason before removing.)

**Fix:** Leave as-is unless the team standardizes on no `__init__.py` in test directories.

---

_Reviewed: 2026-05-14_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
