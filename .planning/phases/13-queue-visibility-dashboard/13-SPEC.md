# Phase 13: Queue Visibility Dashboard — Specification

**Created:** 2026-05-14
**Ambiguity score:** 0.10 (gate: ≤ 0.20)
**Requirements:** 9 locked

## Goal

A server-rendered FastAPI dashboard that lets a developer debug a failed Robotina workflow post-hoc — finding the run, seeing every step's input/output, and identifying which step failed (with the exception class + message) and which steps were cancelled in the cascade.

## Background

Today Robotina exposes queue state through `rq-dashboard` (eoranged/rq-dashboard, decision D-03 from Phase 01). That view is per-RQ-job and shows no workflow grouping, no per-step inputs/outputs, and no relationship between a failed step and the steps cancelled in its cascade. Failure reasons live only in RQ's `FailedJobRegistry`; step inputs are built at enqueue time and never persisted; step outputs (`WorkflowRunStep.artifact`) and statuses (`PENDING | RUNNING | DONE | FAILED | CANCELLED`) already live in Postgres but have no UI surface beyond `psql`.

The relevant data already exists in `WorkflowRun` and `WorkflowRunStep` (`src/robotina/queue/models.py:28`). Cancelled-step cascading already runs in `on_step_failed` (`src/robotina/queue/workflow_runner.py:371`). Two pieces are missing in Postgres: the **input** built per step and the **failure reason** when a step fails. Persisting those two makes Postgres a complete source of truth, after which a small Jinja+HTMX FastAPI app can drive the entire dashboard without touching Redis.

## Requirements

1. **Persist step input**: Every enqueued `WorkflowRunStep` has its input captured to Postgres.
   - Current: Step input is built at enqueue time by `next_step_def.build_input(...)` (workflow_runner.py:149, 300) and discarded — only the RQ job carries it
   - Target: A new `step_input` JSON column on `workflow_run_steps`, populated whenever a step is enqueued (both the first step and subsequent steps)
   - Acceptance: After running any workflow, `SELECT step_input FROM workflow_run_steps WHERE id = ...` returns a non-null JSON dict for every step

2. **Persist failure reason**: Failed steps record their exception in Postgres.
   - Current: Exception lives only in RQ's `FailedJobRegistry`; `WorkflowRunStep` has no error field
   - Target: A new `failure_reason` text column on `workflow_run_steps`, populated in `on_step_failed` with `f"{type(exc).__name__}: {exc}"`. No traceback (intentional — keep it one-line)
   - Acceptance: A workflow with an intentionally-failing step has `failure_reason` populated; `failure_reason` is null on `DONE` / `PENDING` / `RUNNING` / `CANCELLED` steps

3. **Alembic migration**: Schema changes ship as a reviewable migration.
   - Current: No migration exists for the two new columns
   - Target: A new revision in `alembic/versions/` that adds both columns as nullable, with backfill left null for historical rows
   - Acceptance: `uv run migrate` upgrades from the prior head to the new head without error on a freshly-restored production-shaped database; `alembic downgrade -1` reverses cleanly

4. **Dashboard module**: Dashboard code lives in its own module.
   - Current: No dashboard module exists
   - Target: `src/robotina/dashboard/` containing the FastAPI app, Jinja2 templates, and any HTMX assets
   - Acceptance: `ls src/robotina/dashboard/` shows the FastAPI app entrypoint and a `templates/` directory; the app starts cleanly under `python -m robotina.dashboard` or equivalent

5. **One-way dependency boundary**: No other Robotina module depends on the dashboard.
   - Current: N/A (module does not exist)
   - Target: Imports flow `robotina.dashboard → robotina.queue` (and DB layer), never the reverse
   - Acceptance: `grep -rE "from robotina\.dashboard|import robotina\.dashboard" src/robotina/ --exclude-dir=dashboard` returns zero matches

6. **uv run shortcut + docker-compose service**: Dashboard launches both ways.
   - Current: No launch shortcut, no compose service
   - Target: A `dashboard` script in `[project.scripts]` (e.g. `dashboard = "robotina.dashboard:main"`); a `dashboard` service entry in `docker-compose.yml` reading the same `DATABASE_URL` as the agent
   - Acceptance: `uv run dashboard` starts the server on a configurable port (default e.g. 8001); `docker-compose up dashboard` brings the service up alongside `postgres`

7. **List view**: Latest workflow runs, newest first.
   - Current: No UI exists
   - Target: `GET /` renders HTML showing the latest 50 `WorkflowRun` rows (id, workflow_type, household_id, status badge, created_at), ordered by `created_at DESC`. Each row links to the detail view
   - Acceptance: With ≥50 workflow runs in the database, `GET /` returns 200 with exactly 50 run rows in the correct order; with <50 runs, returns all of them; with 0 runs, returns an empty-state message

8. **Detail view**: Workflow plus ordered steps with inputs, outputs, and failure context.
   - Current: No UI exists
   - Target: `GET /workflows/{id}` renders HTML showing the `WorkflowRun` header (type, household, status, shared_context) plus its `WorkflowRunStep` rows ordered by `step_order` ASC. Each step shows: `step_key`, `status`, `step_input` (pretty-printed JSON), `artifact` (pretty-printed JSON, if any), `failure_reason` (if any), `started_at`, `completed_at`. Cancelled and failed steps are visually distinct (different badge / colour class)
   - Acceptance: For a workflow whose 2nd step failed and steps 3–4 cancelled, the detail view shows: step 1 `DONE` with input+artifact, step 2 `FAILED` with input+failure_reason (no artifact), steps 3–4 `CANCELLED` with input only — and the cancelled and failed badges render in clearly different visual styles

9. **HTMX polling**: Active views refresh themselves.
   - Current: N/A
   - Target: List page polls `GET /` (or a fragment of it) every 10s via `hx-trigger="every 10s"`; detail page polls every 3s. Polling stops when a workflow is in a terminal status (`DONE` or `FAILED`) to avoid pointless requests
   - Acceptance: Watching a workflow run in the browser shows step statuses transition `PENDING → RUNNING → DONE` without manual reload, within 3s of the underlying Postgres state changing; after the workflow reaches `DONE` or `FAILED`, no further polling requests appear in the network tab

## Boundaries

**In scope:**
- Alembic migration adding `step_input` (JSON, nullable) and `failure_reason` (Text, nullable) to `workflow_run_steps`
- Wiring in `src/robotina/queue/workflow_runner.py` to populate `step_input` at enqueue time and `failure_reason` in `on_step_failed`
- New `src/robotina/dashboard/` module: FastAPI app, Jinja2 templates, optional small HTMX include
- Read-only list view (`GET /`) and detail view (`GET /workflows/{id}`)
- `uv run dashboard` script entry in `pyproject.toml`
- `dashboard` service in `docker-compose.yml` for the containerized staging env
- Visual distinction between `FAILED` and `CANCELLED` step states
- HTMX `hx-trigger` polling on both views, stopping at terminal status

**Out of scope:**
- Authentication / authorization — internal dev+staging only; no real users; revisit when the dashboard is exposed beyond the compose network
- Retry / cancel / requeue actions — read-only by decision; debug-post-hoc workflow does not require write operations from the UI
- Filtering, search, pagination beyond "latest 50" — risk of over-building before real usage; can be added when the 50-row limit becomes painful
- Metrics / analytics / charts (throughput, p95, error-rate trends) — this is a debugger, not an observability dashboard; LangWatch and OTel already cover that lane
- Reading from Redis — Postgres is the source of truth by Phase 13 design; RQ job state is not required for the supported views
- Worker-crash reconciliation (stuck `RUNNING` rows from SIGKILLed workers) — explicitly deferred as premature optimization
- Spanish UI / household-member access — dev-and-staging-only; family-facing dashboard is a future, separate phase
- Per-step `duration_ms` denormalized column — derivable from `started_at`/`completed_at`; marginal value
- Raw LLM output column (pre-structured-output text) — Phase 11 already eliminated the parse-failure class that motivated it
- React / Vite / any JS build toolchain — keeps the Python-only repo Python-only
- WebSockets / SSE — HTMX polling is sufficient at concurrency=1 worker scale

## Constraints

- **Tech stack:** FastAPI (already in stack for scheduler API), Jinja2, HTMX. No other frontend dependencies. No node, no Vite, no React.
- **Data source:** Postgres only. The dashboard MUST NOT import from `rq`, `redis`, or the queue's RQ-facing modules for read paths. (The wiring change to `workflow_runner.py` to persist `step_input`/`failure_reason` is the only Phase 13 code that touches non-dashboard modules.)
- **Dependency direction:** `robotina.dashboard` may import from `robotina.queue.models`, `robotina.db`, and `robotina.queue.task_types`. No module under `robotina.*` outside `dashboard/` may import from `robotina.dashboard`. This is enforced by grep, not by hope.
- **DB access:** Uses the existing `SessionLocal()` factory in `src/robotina/db.py:24`. No new engine, no new connection pool.
- **failure_reason format:** Exactly `f"{type(exc).__name__}: {exc}"`. No traceback, no chained exceptions, no formatting beyond the colon-separator. Keeps the UI single-line and the column small.
- **Polling cadence:** 10s list / 3s detail, both via `hx-trigger="every Xs"`. Polling must stop when the visible workflow is in a terminal status.
- **Migration safety:** New columns must be nullable so the migration is non-blocking for the running worker; historical rows backfill to NULL.

## Acceptance Criteria

- [ ] Alembic migration adds `step_input` (JSON, nullable) and `failure_reason` (Text, nullable) to `workflow_run_steps`; `uv run migrate` upgrades and `alembic downgrade -1` reverses cleanly
- [ ] After running any complete workflow, every `WorkflowRunStep` row has `step_input` populated as JSON (no nulls except on legacy rows)
- [ ] A workflow with an intentionally-failing step has `failure_reason` populated as `"ExceptionClass: message"`; non-failed steps have `failure_reason = NULL`
- [ ] `uv run dashboard` starts the FastAPI app and serves on a configurable port
- [ ] `docker-compose up dashboard` brings the dashboard service up alongside the agent stack, using the same `DATABASE_URL`
- [ ] `GET /` returns HTML listing the latest 50 workflow runs ordered by `created_at DESC`; each row links to its detail view
- [ ] `GET /workflows/{id}` returns HTML with the workflow header and an ordered list of steps showing `step_key`, `status`, `step_input` (pretty JSON), `artifact` (pretty JSON if present), `failure_reason` (if present), `started_at`, `completed_at`
- [ ] On a deliberately-failed workflow, the detail view renders the failed step and its cancelled-cascade steps with visually distinct badges/colours
- [ ] List view auto-refreshes every 10s via HTMX; detail view every 3s; polling halts once the visible workflow reaches `DONE` or `FAILED`
- [ ] `grep -rE "from robotina\.dashboard|import robotina\.dashboard" src/robotina/ --exclude-dir=dashboard` returns zero matches
- [ ] No authentication is required to reach any dashboard route (matches internal-only deployment context)

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                                              |
|--------------------|-------|------|--------|--------------------------------------------------------------------|
| Goal Clarity       | 0.92  | 0.75 | ✓      | Debug-post-hoc framing locked; deployment shape (dev+staging) clear |
| Boundary Clarity   | 0.95  | 0.70 | ✓      | Read-only; explicit out-of-scope list; one-way dep direction       |
| Constraint Clarity | 0.85  | 0.65 | ✓      | Jinja+HTMX, Postgres-only, no JS build, dep-grep enforcement       |
| Acceptance Criteria| 0.85  | 0.70 | ✓      | 11 falsifiable pass/fail checks                                    |
| **Ambiguity**      | 0.10  | ≤0.20| ✓      |                                                                    |

## Interview Log

| Round | Perspective              | Question summary                                            | Decision locked                                                                                  |
|-------|--------------------------|-------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| 0     | (Pre-interview)          | Investigation: data sources for grouped queue visibility    | Persist step_input + failure_reason; drive dashboard entirely from Postgres (skip Redis)         |
| 1     | Researcher               | Audience & deployment / UI tech / primary use case          | Local dev + staging container; Jinja2 + HTMX server-rendered; debug-failures-post-hoc focus      |
| 2     | Simplifier + Boundary    | Read vs write / list view shape / extra persistence beyond two columns | Read-only; latest 50 flat list newest first; step_input + failure_reason only (no extras) |
| 3     | Seed Closer              | Failure detail granularity / refresh cadence / lock AC      | Exception class+message only (no traceback); 10s list / 3s detail HTMX polling; AC locked + one-way dependency boundary added as explicit constraint |

---

*Phase: 13-queue-visibility-dashboard*
*Spec created: 2026-05-14*
*Next step: /gsd-discuss-phase 13 — implementation decisions (template layout, status badge styling, polling-halt mechanic, migration ordering vs workflow_runner.py change)*
