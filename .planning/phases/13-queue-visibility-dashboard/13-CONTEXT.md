# Phase 13: Queue Visibility Dashboard - Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

A server-rendered FastAPI dashboard (Jinja2 + HTMX, Postgres-only) that lets a developer debug a failed Robotina workflow post-hoc: locate the run in a list, open it, see every step's input/output/status, identify which step failed (exception class + message), and see which subsequent steps were cancelled in the cascade. Read-only. Dev + staging only — no auth, no Spanish UI, no household-facing surface.

Two enabling persistence changes ship with this phase: `step_input` (JSON) and `failure_reason` (text) columns added to `workflow_run_steps`, populated by minimal wiring in `src/robotina/queue/workflow_runner.py` at enqueue time and inside `on_step_failed`.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**9 requirements are locked.** See `13-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `13-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):**
- Alembic migration adding `step_input` (JSON, nullable) and `failure_reason` (Text, nullable) to `workflow_run_steps`
- Wiring in `src/robotina/queue/workflow_runner.py` to populate `step_input` at enqueue time (both first step and subsequent steps) and `failure_reason` in `on_step_failed`, plus a two-line exception-threading edit in `src/robotina/queue/jobs.py` so the existing `as exc` object reaches `on_step_failed` via a new keyword-only `exc=` argument (Option A from RESEARCH Open Q 1; necessary because `on_step_failed` has no `exc` parameter today)
- New `src/robotina/dashboard/` module: FastAPI app, Jinja2 templates, optional small HTMX include
- Read-only list view (`GET /`) and detail view (`GET /workflows/{id}`)
- `uv run dashboard` script entry in `pyproject.toml`
- `dashboard` service in `docker-compose.yml` for the containerized staging env
- Visual distinction between `FAILED` and `CANCELLED` step states
- HTMX `hx-trigger` polling on both views, stopping at terminal status

**Out of scope (from SPEC.md):**
- Authentication / authorization
- Retry / cancel / requeue actions (read-only)
- Filtering, search, pagination beyond "latest 50"
- Metrics / analytics / charts (LangWatch + OTel own that lane)
- Reading from Redis (Postgres is source of truth)
- Worker-crash reconciliation for stuck `RUNNING` rows
- Spanish UI / household-member access
- Per-step `duration_ms` denormalized column
- Raw LLM output column
- React / Vite / any JS build toolchain
- WebSockets / SSE (HTMX polling is sufficient at concurrency=1)

</spec_lock>

<decisions>
## Implementation Decisions

### Module Independence (USER-LOCKED CONSTRAINT)
- **D-01:** The user explicitly delegated every implementation decision to Claude with one non-negotiable condition: **the `robotina.dashboard` module must be completely independent of the other Robotina modules.** This reinforces — and slightly tightens — SPEC.md constraint #2 ("Dependency direction"). Translated into actionable rules for the planner:
  - **Imports inward only.** The dashboard may import from `robotina.queue.models`, `robotina.db`, and `robotina.queue.task_types` (these are unavoidable to render real data) — and **nothing else** from `robotina.*`. No imports from `robotina.agent`, `robotina.gateway`, `robotina.llm`, `robotina.scheduler`, `robotina.queue.workflow_runner`, `robotina.queue.runner`.
  - **No reverse imports.** No module under `robotina.*` outside `src/robotina/dashboard/` may import from `robotina.dashboard`. Enforced by grep in CI (SPEC AC: `grep -rE "from robotina\.dashboard|import robotina\.dashboard" src/robotina/ --exclude-dir=dashboard` returns zero matches).
  - **No registration in `all.py`.** The dashboard is launched independently (`uv run dashboard` or its own compose service). It is NOT wired into `src/robotina/all.py` alongside agent/gateway. Running the agent stack must not start the dashboard.
  - **No shared FastAPI app object with the scheduler API.** When the scheduler HTTP API (a separate, future concern) needs FastAPI, it gets its own. The dashboard does not export `app` for anyone else to mount.
  - **Wiring change to `workflow_runner.py` is not a dependency on the dashboard.** Adding `step_input`/`failure_reason` writes is a queue-module change; the dashboard merely reads those columns. The dashboard does not depend on the wiring change to start — it would just show NULLs for legacy rows.

### Template Layout (Claude's discretion — defaults)
- **D-02:** Single `base.html` providing the page chrome (`<head>`, link to stylesheet, link to HTMX, header bar with project name, `{% block content %}{% endblock %}`).
- **D-03:** Two page templates: `index.html` extends `base.html` and renders the list view; `workflow.html` extends `base.html` and renders the detail view.
- **D-04:** Two partials extracted as Jinja macros for HTMX-friendly fragment swaps: `_run_rows.html` (the table rows for the list view, the polling target) and `_workflow_body.html` (the full detail body including step list, the polling target). The polling responses return ONLY the fragment, not the full page.
- **D-05:** A `_status_badge.html` macro takes a status string and renders the correct badge markup; both pages use it.
- **D-06:** Template directory: `src/robotina/dashboard/templates/`. Static directory: `src/robotina/dashboard/static/`.

### Status Badge Styling (Claude's discretion)
- **D-07:** Status badges are CSS pill chips with semantic colors. `FAILED` and `CANCELLED` are visually distinct as required by SPEC req 8:
  - `PENDING`  → gray, outlined
  - `RUNNING`  → blue, filled, subtle pulse animation (CSS `@keyframes`, no JS)
  - `DONE`     → green, filled
  - `FAILED`   → **red, filled, solid** — strong/heavy visual weight
  - `CANCELLED`→ **amber/orange, outlined with diagonal-stripe background** — clearly NOT red, clearly NOT a success — communicates "skipped due to upstream failure"
- **D-08:** A single utility class per state: `badge badge--pending` / `badge--running` / `badge--done` / `badge--failed` / `badge--cancelled`. Class names match status strings lowercased, so the macro is `<span class="badge badge--{{ status|lower }}">{{ status }}</span>`.

### HTMX Polling-Halt Mechanic (Claude's discretion)
- **D-09:** Polling is attached to the **fragment wrapper**, not the page. Server renders the wrapper with `hx-trigger` ONLY when the run/list is non-terminal. When the visible workflow reaches `DONE` or `FAILED`, the server emits the same wrapper element WITHOUT the `hx-trigger` attribute. HTMX swaps the new wrapper in; the new wrapper has no trigger; polling halts naturally. No JS, no special teardown.
- **D-10:** Cadence: list view 10s (`hx-trigger="every 10s"`), detail view 3s (`hx-trigger="every 3s"`). Polling is unconditional for the list view (there's always a chance a new run appears) — list polling does NOT halt. Polling halts on the **detail view only** when its workflow is in a terminal status.
- **D-11:** The polling URL for the list view returns `_run_rows.html`. The polling URL for the detail view returns `_workflow_body.html`. Both are served by dedicated routes (e.g., `GET /fragments/runs` and `GET /fragments/workflows/{id}`) so the full-page routes (`GET /` and `GET /workflows/{id}`) stay simple.

### CSS / Asset Delivery (Claude's discretion)
- **D-12:** Single hand-written `src/robotina/dashboard/static/dashboard.css`. No Tailwind, no Pico, no CDN runtime dependency. The dashboard works offline (staging containers should not require internet).
- **D-13:** HTMX is **vendored** at `src/robotina/dashboard/static/htmx.min.js` (pinned version recorded in a comment at top of the file). No CDN. Same offline rationale.
- **D-14:** Static files are served via FastAPI's `StaticFiles` mounted at `/static`.

### Migration + Wiring Ordering (Claude's discretion)
- **D-15:** Both changes ship in this phase but as **separate commits in the same PR**:
  1. Commit 1: Alembic migration + model column additions (`WorkflowRunStep.step_input`, `WorkflowRunStep.failure_reason`). Columns are nullable. Safe to deploy alone — running worker keeps working, all new columns stay NULL.
  2. Commit 2: Wiring change in `workflow_runner.py` to populate the columns at enqueue (line ~156 first step, line ~320 subsequent steps) and inside `on_step_failed` (line ~351).
  3. Commit 3+: Dashboard module, templates, static assets, pyproject script, compose service.
- **D-16:** `failure_reason` format is fixed by SPEC constraint: `f"{type(exc).__name__}: {exc}"` — no traceback, no chained exceptions.
- **D-17:** `step_input` is the dict returned by `next_step_def.build_input(...)` serialized as-is to the JSON column. The model column type uses the project's existing `JSON` import pattern from `src/robotina/queue/models.py`.

### Test Strategy (Claude's discretion)
- **D-18:** Tests live under `tests/dashboard/` (mirroring src layout). They use pytest + httpx `AsyncClient` against the FastAPI app via `ASGITransport` — no live server needed for HTTP tests.
- **D-19:** Tests that touch the DB use the existing integration-test pattern (real Postgres test DB, marked `@pytest.mark.integration`). Tests that only render templates from fixture model objects do NOT need the DB and are not marked integration.
- **D-20:** Minimum coverage: a happy-path test that creates a run with a failed-step + cancelled-cascade, hits `GET /workflows/{id}`, and asserts the HTML contains the `badge--failed` and `badge--cancelled` markers in the right rows; an empty-state test for `GET /` with zero runs; a halt-polling test that asserts the terminal-status detail response does NOT contain `hx-trigger`.
- **D-21:** Manual smoke step in the plan: start `uv run dashboard`, eyeball list + detail views, confirm polling cadence in the browser network tab, confirm polling halts after terminal status.

### pyproject + docker-compose (Claude's discretion)
- **D-22:** `pyproject.toml` gets `dashboard = "robotina.dashboard:main"` under `[project.scripts]`. The `main()` function lives in `src/robotina/dashboard/__init__.py` (or a `__main__.py`) and starts `uvicorn` programmatically with port from `DASHBOARD_PORT` env var (default `8001`).
- **D-23:** `docker-compose.yml` gets a `dashboard` service that mirrors how `gateway`/`agent` services are wired: same image (or same build context), reads `DATABASE_URL` from the same env, exposes port 8001 on the host, depends_on `postgres`. The dashboard service is **not** added as a dependency of `agent` or `gateway` (independence rule D-01).

### Claude's Discretion
The user delegated all areas to Claude's discretion **except** D-01 (module independence). Every D-02 through D-23 above is recorded as Claude's choice with explicit rationale so the planner and executor can act without re-asking. If the planner discovers a concrete reason to deviate from any D-NN above, that decision should be documented in the PLAN.md rather than re-litigated.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked Requirements
- `.planning/phases/13-queue-visibility-dashboard/13-SPEC.md` — Locked requirements (9), boundaries, constraints, acceptance criteria (11). MUST read before planning.

### Project Stack & Constraints
- `CLAUDE.md` §Technology Stack — Tech stack pinned (Python 3.12+, FastAPI ≥0.115, no JS build, uv run shortcuts); Pydantic v2 only; no Celery; no `aioredis`; HTMX/Jinja2 not yet introduced but compatible.
- `CLAUDE.md` §What NOT to Use — explicit anti-list: do not introduce React/Vite/node toolchain; do not use `requests` in async contexts (use `httpx`).
- `.planning/PROJECT.md` — Project mission and core value (debug + reliability lens).
- `.planning/REQUIREMENTS.md` — Milestone requirements; AGENT-12 reference (instrumentation context this phase complements).

### Code Touch Points
- `src/robotina/queue/models.py` (~line 28+ `class WorkflowRunStep`) — Where `step_input` and `failure_reason` columns are added. Existing JSON column pattern (`artifact: Mapped[Optional[dict]]`) is the template.
- `src/robotina/queue/workflow_runner.py:156` — First-step enqueue site; `task_input = first_step_def.build_input(...)`. Wiring point for `step_input`.
- `src/robotina/queue/workflow_runner.py:320` — Subsequent-step enqueue site; same shape. Wiring point for `step_input`.
- `src/robotina/queue/workflow_runner.py:351` — `on_step_failed(job_id, session, queue)`. Wiring point for `failure_reason`.
- `src/robotina/db.py:24` — `SessionLocal()` factory. The ONLY DB entry point the dashboard may use; no new engine, no new pool.
- `alembic/versions/` — Migration revisions directory. New revision adds the two nullable columns.
- `pyproject.toml` `[project.scripts]` — Pattern for `uv run` shortcuts; add `dashboard = "robotina.dashboard:main"` following the existing pattern.
- `docker-compose.yml` — Pattern for service entries; add `dashboard` service mirroring `gateway`/`agent` env wiring.

### Prior Phase Decisions Carried Forward
- `.planning/phases/01-developer-tooling-and-infrastructure/` — Decision D-03 (use `eoranged/rq-dashboard` for low-level RQ inspection). Phase 13 supplements, does NOT replace rq-dashboard; the two views co-exist (workflow-grouped view via Phase 13, raw RQ jobs view via rq-dashboard).
- `.planning/phases/12-middleware-based-agent-instrumentation/12-CONTEXT.md` — Phase 12 added agent-side instrumentation (LangWatch traces); Phase 13's failure_reason is the post-mortem **workflow-step** complement, not a duplicate of the trace data.
- `.planning/phases/11-structured-agent-output-via-response-format/` — Phase 11 eliminated the parse-failure class; the dashboard does NOT need a "raw LLM output" column (SPEC out-of-scope).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/robotina/db.py:24` `SessionLocal()` — the only DB session factory; the dashboard's request-scoped session dependency wraps this.
- `src/robotina/queue/models.py` `WorkflowRun`, `WorkflowRunStep` — already model the entire data shape the dashboard renders. JSON `artifact` column establishes the `Mapped[Optional[dict]]` pattern that `step_input` will reuse.
- Existing `pyproject.toml [project.scripts]` pattern (`agent`, `gateway`, `migrate`, `all`) — `dashboard` follows this verbatim.
- Existing `docker-compose.yml` `gateway` service entry — Same env-injection pattern works for `dashboard`.

### Established Patterns
- **No FastAPI in src/ yet.** `src/robotina/scheduler/__init__.py` is an empty stub. Phase 13 introduces the first real FastAPI app in the repo. That gives latitude on app-factory patterns — but it also means there is no prior FastAPI convention to mirror, so the dashboard sets its own clean pattern (app instance + `main()` entrypoint that calls `uvicorn.run`).
- **Alembic migrations** are present (`alembic/versions/`). Pattern: nullable columns + ALTER TABLE … ADD COLUMN. Downgrade reverses with DROP COLUMN.
- **Integration tests** marked via `@pytest.mark.integration` (configured in `pyproject.toml`). Dashboard DB tests follow suit.
- **Sequential single worker** (concurrency=1) — no race conditions to worry about in dashboard polling; the worker advances workflows one at a time and the dashboard reflects the latest committed state.

### Integration Points
- `workflow_runner.py` is the PRIMARY non-dashboard module modified in this phase (to populate `step_input`/`failure_reason`). Touch is surgical: add a kwarg to the existing session.add/commit dance at each of the 3 sites. A secondary two-line edit in `src/robotina/queue/jobs.py` threads the `as exc` object into `on_step_failed(..., exc=exc)` at the two `except Exception as exc:` blocks (send-notification branch ~line 109; generic branch ~line 217); this is mechanically required to reach the exception object since `on_step_failed` has no `exc` parameter today, and is the implementation of RESEARCH Open Q 1 Option A. `jobs.py` itself remains unaware of the dashboard.
- New migration revision attaches to the current Alembic head.
- New compose service shares the postgres dependency.

</code_context>

<specifics>
## Specific Ideas

- **User's framing of the constraint:** "completely independent of the other robotina modules" — this is the only non-discretionary requirement and is the spirit of D-01. Every planner/executor decision should be checked against this: "does this make the dashboard depend on anything other than queue.models, db, and queue.task_types?" If yes, rethink.
- **Visual goal for FAILED vs CANCELLED (SPEC req 8):** the diagonal-stripe background on `CANCELLED` is the recommended differentiator — it conveys "interrupted, not chosen" while red-filled `FAILED` conveys "this is the actual problem."

</specifics>

<deferred>
## Deferred Ideas

- **Filtering / search / pagination** — explicitly out of scope per SPEC. Add when the 50-row limit becomes painful.
- **Worker-crash reconciliation** for stuck `RUNNING` rows from SIGKILLed workers — explicitly out of scope per SPEC (premature optimization).
- **Spanish UI / household-facing dashboard** — out of scope; future phase if the dashboard moves beyond dev+staging.
- **Per-step `duration_ms`** denormalized column — derivable from `started_at`/`completed_at`; out of scope per SPEC.
- **WebSockets / SSE** — HTMX polling is sufficient at concurrency=1; revisit only if cadence becomes a bottleneck.
- **Auth / authorization** — out of scope; revisit when the dashboard is exposed beyond the compose network.
- **Retry / cancel / requeue actions** — out of scope; dashboard is read-only by design.

</deferred>

---

*Phase: 13-queue-visibility-dashboard*
*Context gathered: 2026-05-14*
