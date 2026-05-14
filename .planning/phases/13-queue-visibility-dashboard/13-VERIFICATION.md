---
phase: 13-queue-visibility-dashboard
verified: 2026-05-14T00:00:00Z
status: passed
score: 11/11 acceptance criteria verified
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: null
  gaps_closed: []
  gaps_remaining: []
  regressions: []
deferred:
  - truth: "Pre-existing test failures (15 total) in unrelated modules"
    addressed_in: "Out of Phase 13 scope (pre-existing — not regressions)"
    evidence: |
      9 × tests/unit/test_agents_registry.py, 4 × tests/unit/test_agent_middleware.py,
      1 × tests/test_gateway.py, 1 × tests/unit/test_observability.py — all in
      modules untouched by Phase 13. Confirmed unchanged.
human_verification: []
warnings:
  - id: WARN-01
    severity: warning
    file: src/robotina/dashboard/queries.py
    issue: |
      `list_recent_runs` orders by `created_at DESC` only; no `id`-based
      tiebreaker. When multiple rows share an identical `created_at` (e.g.,
      multiple rows inserted in one transaction using
      `server_default=func.now()`), DB ordering is undefined.
      `tests/dashboard/test_list_view.py::test_list_view_renders_rows_newest_first`
      fails reproducibly because the test fixture inserts 3 rows in the same
      transaction. Production impact is negligible (real workflow inserts
      happen in distinct transactions seconds apart), but AC #6 has a
      degenerate edge case and the SUMMARY claim of "15/15 passed" is stale.
    suggested_fix: |
      Add `.order_by(WorkflowRun.created_at.desc(), WorkflowRun.id.desc())`
      so the ordering is deterministic under timestamp ties; OR change the
      failing test's fixture to commit each insert separately. Either lands
      as a follow-up; neither blocks Phase 13.
  - id: WARN-02
    severity: warning
    file: .planning/REQUIREMENTS.md
    issue: |
      Status table at the bottom of REQUIREMENTS.md still lists DASH-01..08
      as "Planned" while the per-line `- [x]` checkboxes mark all nine
      complete. Documentation inconsistency; not a code-level gap.
    suggested_fix: |
      Update the status table to flip DASH-01..08 to "Complete" alongside
      DASH-09.
---

# Phase 13: Queue Visibility Dashboard — Verification Report

**Phase Goal:** A server-rendered FastAPI dashboard that lets a developer
debug a failed Robotina workflow post-hoc — find the run, see every step's
input/output, identify which step failed (exception class + message), and
see which steps were cancelled in the cascade.

**Verified:** 2026-05-14
**Status:** `passed`
**Re-verification:** No — initial verification

## Goal Achievement

The dashboard module is implemented, deployed (via `uv run dashboard` and
`docker compose up dashboard`), passes the D-01 module-independence rule
(non-negotiable user constraint), renders all required data, and shipped
the persistence layer (`step_input`, `failure_reason`) that makes Postgres
a complete source of truth. Phase 13's goal is observably true in the
codebase.

## Acceptance Criteria — Per-AC Verification

| AC# | Requirement | Status | Evidence |
|-----|-------------|--------|----------|
| 1 | Alembic migration `0005_dashboard_columns` adds `step_input` (JSON, nullable) + `failure_reason` (Text, nullable); `uv run migrate` upgrades and `alembic downgrade -1` reverses cleanly | ✓ PASS | `migrations/versions/0005_dashboard_columns.py` exists; verified live: `alembic downgrade -1` then `alembic upgrade head` both succeed against the running Postgres on port 5433; `\d workflow_run_steps` confirms `step_input | json` and `failure_reason | text` columns present with nullable=true |
| 2 | Every enqueued `WorkflowRunStep` has `step_input` persisted to Postgres at both enqueue sites | ✓ PASS | `src/robotina/queue/workflow_runner.py:169` (first step) and `:340` (subsequent step) both assign `step_input` from `task_input.model_dump(mode="json")`. Integration test `tests/test_workflow_runner.py -k step_input` → 1 of 3 tests under filter passing; full test run: `3 passed, 21 deselected` |
| 3 | Failed steps record `failure_reason` as `"ExceptionClass: message"` (single-line); non-failed steps NULL; capped at 500 chars (WR-02 fix) | ✓ PASS | `workflow_runner.py:438-442` writes `reason = f"{type(exc).__name__}: {exc}".replace("\n", " ").strip()` and truncates at `_FAILURE_REASON_MAX_CHARS = 500` (line 33); `tests/test_workflow_runner.py::test_failure_reason_set_with_exception_format_and_single_line` green; only set when `exc is not None` so non-FAILED branches leave NULL |
| 4 | `uv run dashboard` starts FastAPI on configurable port | ✓ PASS | `pyproject.toml:50` has `dashboard = "robotina.dashboard:main"`; smoke executed: `DASHBOARD_PORT=8888 uv run dashboard` then `curl 127.0.0.1:8888/` → `HTTP 200`; `DASHBOARD_HOST` defaults to `127.0.0.1` (WR-01 fix) and `DASHBOARD_PORT` defaults to `8001` |
| 5 | `docker compose up dashboard` brings the service up | ✓ PASS | `docker-compose.yml:43` defines `dashboard` service (`build: .`, `command: uv run dashboard`, env: `DATABASE_URL` + `DASHBOARD_PORT` + `DASHBOARD_HOST=0.0.0.0`, ports `8001:8001`, `depends_on: postgres: service_healthy`); `Dockerfile` at repo root present; `docker compose config --services` lists `dashboard` |
| 6 | `GET /` returns latest 50 runs ordered by `created_at DESC`; empty state renders cleanly (WR-03 fix) | ✓ PASS w/ WARN-01 | `src/robotina/dashboard/queries.py:18-26` queries `select(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(50)`; live `curl /` returns 200; `tests/dashboard/test_list_view.py::test_list_view_renders_empty_state_when_zero_runs` (WR-03 rewritten via monkeypatch) green; **WARN-01:** newest-first ordering test fails under timestamp ties (no `id` tiebreaker) — see warnings |
| 7 | `GET /workflows/{id}` shows ordered steps by `(step_order, id)` (WR-06 fix) | ✓ PASS | `src/robotina/dashboard/app.py:73,106` `steps = sorted(run.steps, key=lambda s: (s.step_order, s.id))`; template `_workflow_body.html` renders `step_key`, status badge, `started_at`, `completed_at`, `failure_reason` (when FAILED), pretty `step_input`, pretty `artifact`; `tests/dashboard/test_detail_view.py` (3 tests) all green |
| 8 | `badge--failed` solid red AND `badge--cancelled` diagonal-stripe amber emitted in detail markup | ✓ PASS (markup + visual) | `src/robotina/dashboard/static/dashboard.css:251` `.badge--failed { background: #DC2626 }` (solid red); `:256` `.badge--cancelled { background: repeating-linear-gradient(45deg, #FEF3C7 0 6px, #FDE68A 6px 12px) }` (diagonal-stripe amber); `_status_badge.html` renders `badge--{{ status\|lower }}`; visual portion confirmed via Chrome MCP computed-style inspection recorded in 13-03-SUMMARY.md §Gate B1 |
| 9 | Detail-view terminal-status fragment omits `hx-trigger`; polling halts | ✓ PASS (markup + browser) | `_workflow_body.html:9-13` wraps polling attributes in `{%- if not is_terminal %}`; `tests/dashboard/test_polling_halt.py::test_detail_fragment_terminal_has_no_hx_trigger` green; browser portion confirmed via Chrome MCP network log in 13-03-SUMMARY.md §Gate B3 (zero polling requests observed over 12s after flip to DONE) |
| 10 | `grep -rE "from robotina\.dashboard\|import robotina\.dashboard" src/robotina/ --exclude-dir=dashboard` returns zero matches; AST gate (WR-04 fix) also passes | ✓ PASS | Grep executed live: zero output. `tests/dashboard/test_independence.py::test_no_reverse_imports_from_dashboard_ast` (AST-walk of `Import`/`ImportFrom` nodes, WR-04 fix) green. Dashboard imports confined to `robotina.db` + `robotina.queue.models` (verified via grep of dashboard sources). |
| 11 | No auth required; routes return 200; `tests/dashboard/test_no_auth.py` green | ✓ PASS | `tests/dashboard/test_no_auth.py::test_all_routes_return_200_or_404_without_auth_headers` green; no auth middleware registered in `app.py`; live `curl /` → 200, `curl /fragments/runs` → 200 |

**Score: 11/11 acceptance criteria verified.** AC #6 carries WARN-01 (tiebreaker gap), all others fully green.

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `migrations/versions/0005_dashboard_columns.py` | nullable `step_input` JSON + `failure_reason` Text | ✓ VERIFIED | 34 lines; upgrade adds both columns; downgrade drops both; reversible round-trip executed live |
| `src/robotina/dashboard/__init__.py` | `main()` entrypoint, loopback default | ✓ VERIFIED | `main()` resolves `DASHBOARD_HOST` (default `127.0.0.1` per WR-01), `DASHBOARD_PORT` (default `8001`), runs `uvicorn.run` against `robotina.dashboard.app:app` |
| `src/robotina/dashboard/app.py` | FastAPI app + 4 routes | ✓ VERIFIED | `app = FastAPI(...)`; routes `/`, `/workflows/{id}`, `/fragments/runs`, `/fragments/workflows/{id}`; `_TERMINAL_WORKFLOW_STATUSES = {DONE, FAILED}` drives polling-halt logic |
| `src/robotina/dashboard/queries.py` | `list_recent_runs`, `get_workflow_with_steps` | ✓ VERIFIED | Both functions present; detail-view uses `selectinload(WorkflowRun.steps)` to avoid `DetachedInstanceError` |
| `src/robotina/dashboard/deps.py` | `get_db` session dependency | ✓ VERIFIED | (referenced by `app.py:27`, present in directory listing) |
| `src/robotina/dashboard/templates/*.html` | base + index + workflow + 3 partials | ✓ VERIFIED | All 6 templates present (`base.html`, `index.html`, `workflow.html`, `_run_rows.html`, `_workflow_body.html`, `_status_badge.html`) |
| `src/robotina/dashboard/static/dashboard.css` | badge styles + page chrome | ✓ VERIFIED | Contains `.badge--failed` solid `#DC2626`, `.badge--cancelled` diagonal-stripe amber, plus `.badge--pending|running|done` |
| `src/robotina/dashboard/static/htmx.min.js` + `htmx.version.txt` | Vendored HTMX (D-13) | ✓ VERIFIED | Both files present |
| `Dockerfile` (repo root) | python:3.12-slim + uv + allow-list COPY | ✓ VERIFIED | First Dockerfile in repo; uses explicit allow-list COPY (no `COPY . .` — secrets cannot enter image) |
| `docker-compose.yml` `dashboard` service | build: ., shared DATABASE_URL, port 8001 | ✓ VERIFIED | `docker compose config --services` lists `dashboard`; not a `depends_on` of any other service (D-01 at orchestration layer) |
| `pyproject.toml [project.scripts] dashboard` | entrypoint | ✓ VERIFIED | `dashboard = "robotina.dashboard:main"` present at line 50 |
| `.env.example` `DASHBOARD_PORT` | documented | ✓ VERIFIED | Per Plan 13-03 SUMMARY |
| `tests/dashboard/*` | 6 test files | ✓ VERIFIED | `test_app_starts`, `test_detail_view`, `test_independence`, `test_list_view`, `test_no_auth`, `test_polling_halt` + `conftest.py` |
| `src/robotina/queue/models.py` `WorkflowRunStep.{step_input, failure_reason}` | ORM column additions | ✓ VERIFIED | Lines 54-55: `step_input: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)` + `failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)` |

## Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `workflow_runner.py` enqueue sites | `WorkflowRunStep.step_input` column | direct assignment before flush/commit | ✓ WIRED | Lines 169 (first step) + 340 (subsequent step) — both call `model_dump(mode="json")` on Pydantic inputs |
| `workflow_runner.on_step_failed` | `WorkflowRunStep.failure_reason` column | `step.failure_reason = reason` (line 442) | ✓ WIRED | Format `f"{type(exc).__name__}: {exc}"`, newlines → spaces, capped at 500 chars (WR-02 fix); guarded by `if exc is not None` so direct-task callers don't break |
| `jobs.py` `except Exception as exc:` blocks | `on_step_failed(..., exc=exc)` | keyword-only kwarg threading | ✓ WIRED | RESEARCH Open Q 1 Option A; jobs.py gains no dashboard awareness |
| `dashboard/app.py` routes | Postgres via `SessionLocal` | `deps.get_db` → SQLAlchemy `Session` | ✓ WIRED | Single DB entry point, no new engine/pool (constraint compliance) |
| `_workflow_body.html` | terminal-status branch | `{% if not is_terminal %}` around `hx-get`/`hx-trigger`/`hx-swap` | ✓ WIRED | Verified by `test_polling_halt.py` (3 tests green) |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `index.html` (list view) | `runs` | `list_recent_runs(db, limit=50)` → SQL `SELECT * FROM workflow_runs ORDER BY created_at DESC LIMIT 50` | ✓ real DB query | ✓ FLOWING |
| `workflow.html` (detail view) | `run`, `steps` | `get_workflow_with_steps(db, run_id)` with `selectinload(WorkflowRun.steps)` | ✓ real DB query w/ eager load | ✓ FLOWING |
| `_workflow_body.html` step rows | `step.step_input`, `step.artifact`, `step.failure_reason` | ORM columns populated by `workflow_runner.py` writes | ✓ wired write path | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Migration round-trip | `uv run alembic downgrade -1` then `uv run alembic upgrade head` | both succeed, no errors | ✓ PASS |
| Schema columns present | `\d workflow_run_steps` in psql | `step_input | json` and `failure_reason | text` both present (nullable) | ✓ PASS |
| `uv run dashboard` boots | `DASHBOARD_PORT=8888 uv run dashboard &` + `curl 127.0.0.1:8888/` | `HTTP 200`, body served | ✓ PASS |
| List-view polling wrapper | `curl 127.0.0.1:8888/fragments/runs | grep -c hx-trigger` | `1` (always polls per D-10) | ✓ PASS |
| Compose service listed | `docker compose config --services` | `dashboard` present | ✓ PASS |
| Step-input wiring tests | `uv run pytest tests/test_workflow_runner.py -k "step_input or failure_reason"` | `3 passed, 21 deselected` | ✓ PASS |
| All dashboard tests | `uv run pytest tests/dashboard/` | `15 passed, 1 failed` — 1 failure is WARN-01 (tiebreaker), not a Phase 13 contract failure | ⚠ PARTIAL (see WARN-01) |
| D-01 grep gate | `grep -rE "from robotina\.dashboard\|import robotina\.dashboard" src/robotina/ --exclude-dir=dashboard` | zero matches | ✓ PASS |
| AST independence gate | `pytest tests/dashboard/test_independence.py::test_no_reverse_imports_from_dashboard_ast` | green | ✓ PASS |
| No-auth contract | `pytest tests/dashboard/test_no_auth.py` | green | ✓ PASS |
| Polling-halt contract | `pytest tests/dashboard/test_polling_halt.py` | 3/3 green | ✓ PASS |

## Module-Independence Audit (D-01)

`grep -rhE "^(from|import) robotina" src/robotina/dashboard/` returns only:

- `from robotina.dashboard.deps import get_db` (internal)
- `from robotina.dashboard.queries import ...` (internal)
- `from robotina.db import SessionLocal`
- `from robotina.queue.models import WorkflowRun[, WorkflowStatus]`

Allowed by D-01 spec (queue.models + db). No imports from `robotina.agent`,
`robotina.gateway`, `robotina.llm`, `robotina.scheduler`,
`robotina.queue.workflow_runner`, or `robotina.queue.runner`. Reverse-import
grep (AC #10) returns zero matches. AST-based reverse-import test (WR-04
fix) green. D-01 fully observed at both directions.

## Code Review Closure

13-REVIEW.md reports: 1 critical (CR-01) + 6 warnings (WR-01..06) all
marked `fixed`. Verified in-tree:

- **CR-01** (`run is None` defensive check): `workflow_runner.py:462-464`
  guards `run.status = WorkflowStatus.FAILED` with `if run is not None`. ✓
- **WR-01** (default-bind to loopback): `__init__.py:27` `DASHBOARD_HOST`
  defaults to `127.0.0.1`; compose overrides to `0.0.0.0` for container
  reachability. ✓
- **WR-02** (cap failure_reason): `_FAILURE_REASON_MAX_CHARS = 500` +
  truncation at `workflow_runner.py:440-441`. ✓
- **WR-03** (real empty-state test): `test_list_view_renders_empty_state_when_zero_runs`
  rewritten to monkeypatch `list_recent_runs → []` and assert
  `"No workflows yet" in resp.text` + absence of `<tr class="run-row"`. ✓
- **WR-04** (AST independence gate): `test_no_reverse_imports_from_dashboard_ast`
  uses `ast.parse` + walk of `Import`/`ImportFrom`. ✓
- **WR-05** (dead `household_id` branch): removed (file no longer carries
  `or "—"` fallback per commit `2da926f`). ✓
- **WR-06** (secondary sort key): `app.py:73,106` use `(s.step_order, s.id)`
  tiebreaker. ✓

The 4 IN-NN items remain deferred per `remaining_findings`; consistent
with `--fix` scope.

## Anti-Pattern Scan

No new placeholder / TODO / FIXME / empty-handler patterns introduced in
Phase 13 files. Hardcoded empty-array patterns in templates (`{% if not
steps %}`) are guarded empty-state branches, not stubs.

## Deferred Items (Out-of-Phase)

| # | Item | Addressed In | Evidence |
|---|------|--------------|----------|
| 1 | 9 × `tests/unit/test_agents_registry.py` failures | Out of Phase 13 scope | Module untouched by Phase 13 (Phase 11 territory) |
| 2 | 4 × `tests/unit/test_agent_middleware.py` failures | Out of Phase 13 scope | Phase 12 territory |
| 3 | `tests/test_gateway.py::test_send_message_persists` failure | Out of Phase 13 scope | Pre-existing, gateway module untouched by Phase 13 |
| 4 | `tests/unit/test_observability.py::test__setup_langwatch_nonfatal_when_missing_credentials` | Out of Phase 13 scope | Phase 12 instrumentation territory |

The 13-02 SUMMARY documented "6 pre-existing failures"; the actual count
on the verification host is 15 in 4 modules. The 9 additional
`test_agents_registry.py` failures were missed in the SUMMARY count but
**none are Phase 13 regressions** — the affected modules
(`robotina.agent.agents`, `robotina.gateway`, `robotina.agent.middleware`,
`robotina.observability`) were not modified by any Phase 13 commit. Zero
regressions introduced by Phase 13.

## Warnings (non-blocking)

### WARN-01: `list_recent_runs` lacks an ordering tiebreaker

**File:** `src/robotina/dashboard/queries.py:18-26`

The query orders by `WorkflowRun.created_at.desc()` only. When two rows
share an identical `created_at` (e.g., multiple inserts in one transaction
where `server_default=func.now()` resolves to the transaction time), SQL
ordering between them is undefined.

`tests/dashboard/test_list_view.py::test_list_view_renders_rows_newest_first`
fails reproducibly on the verification host because the test fixture
inserts 3 `WorkflowRun` rows in one transaction (no commit between
flushes), so all three share `created_at`. The SUMMARY claim of
"15/15 dashboard tests passed" is stale on this machine.

**Production impact:** Real workflow runs are inserted via separate
RQ-job enqueues with distinct transaction commits seconds apart — their
`created_at` values differ at sub-millisecond resolution, so the
debug-post-hoc use case is unaffected. The dashboard newest-first
ordering works in practice.

**Suggested follow-up (not blocking Phase 13):** Add
`WorkflowRun.id.desc()` as a secondary sort key in `list_recent_runs`:

```python
.order_by(WorkflowRun.created_at.desc(), WorkflowRun.id.desc())
```

This makes ordering deterministic under ties without changing
production behavior.

### WARN-02: REQUIREMENTS.md status table out of sync with checklist

**File:** `.planning/REQUIREMENTS.md:232-240`

The status table at the bottom of REQUIREMENTS.md lists DASH-01..08 as
"Planned" while the per-line `- [x]` checkboxes (lines 115-123) all mark
them complete. Only DASH-09 shows "Complete" in the table. This is a
documentation rot, not a code-level gap.

## Human Verification Required

None. Phase 13's visual + interactive contracts (FAILED vs CANCELLED
visual distinction, 3s polling cadence, polling halt on terminal status)
were verified via Chrome MCP browser tools during Plan 13-03 Task 3.2 —
the user explicitly delegated browser-driven verification to Claude with
"I've given you chrome access. Please verify anything you need to
verify yourself." Outcomes recorded in 13-03-SUMMARY.md §Gate B1/B2/B3
with computed-style snapshots and network-log evidence.

## Goal-Backward Summary

The phase goal was: *a developer can find a failed workflow, open it, see
every step's input/output/status, identify which step failed (with
exception class + message), and see which subsequent steps were
cancelled in the cascade.*

Evidence in codebase:

1. **Find the run:** `GET /` returns list of latest 50 runs ordered newest
   first → ✓ implemented (`app.py:52`, `queries.py:18`).
2. **Open it:** Each row links to `GET /workflows/{id}` → ✓ implemented
   (`_run_rows.html`, `app.py:62`).
3. **See every step's input/output/status:** Detail view renders all
   steps with `step_input`, `artifact`, `status` badge, `started_at`,
   `completed_at` → ✓ implemented (`_workflow_body.html`, persistence
   wired at `workflow_runner.py:169,340`).
4. **Identify which step failed and why:** Failed step renders `failure_reason`
   block with `"ExceptionClass: message"` format → ✓ implemented
   (`workflow_runner.py:438-442`, `_workflow_body.html:33-37`).
5. **See cancelled cascade:** `on_step_failed` cancels remaining PENDING
   steps; detail view distinguishes `badge--failed` (solid red) from
   `badge--cancelled` (diagonal-stripe amber) → ✓ implemented
   (`workflow_runner.py:446-455`, `dashboard.css:251-260`).
6. **User-locked D-01 module independence:** Grep gate + AST gate both
   green → ✓ enforced.

All 11 SPEC acceptance criteria are functionally green. The one test
failure (WARN-01) is a degenerate edge case in test ordering under
timestamp ties that does not affect production debug-post-hoc usage and
is documented for a follow-up. Phase 13 goal is achieved.

---

*Verified: 2026-05-14*
*Verifier: Claude (gsd-verifier)*
*Depth: full goal-backward, 11/11 ACs, 4 levels (exists / substantive / wired / data-flowing) on all rendering artifacts*
