# Phase 13: Queue Visibility Dashboard — Research

**Researched:** 2026-05-14
**Domain:** Server-rendered FastAPI + Jinja2 + HTMX read-only debugger over Postgres
**Confidence:** HIGH (every load-bearing fact verified against the installed `.venv` or official docs)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 (USER-LOCKED, non-negotiable): Module independence.**
`robotina.dashboard` MUST be completely independent of every other Robotina module. Translated to actionable rules:
- Imports inward ONLY from `robotina.queue.models`, `robotina.db`, `robotina.queue.task_types`. NOTHING else from `robotina.*` (no `robotina.agent`, `robotina.gateway`, `robotina.llm`, `robotina.scheduler`, `robotina.queue.workflow_runner`, `robotina.queue.runner`).
- No reverse imports — `grep -rE "from robotina\.dashboard|import robotina\.dashboard" src/robotina/ --exclude-dir=dashboard` MUST return zero matches.
- NOT wired into `src/robotina/all.py`. Running the agent stack must not start the dashboard.
- No shared FastAPI app object with any future scheduler API. The dashboard's `FastAPI` instance is private.
- The wiring change to `workflow_runner.py` (to write `step_input`/`failure_reason`) is a queue-module change, NOT a dependency of the dashboard. The dashboard reads those columns but can start before the wiring lands (it would just show NULLs).

**D-02 through D-23 (Claude-locked, starting points):** Template layout (single `base.html`, page templates `index.html` + `workflow.html`, partials `_run_rows.html` + `_workflow_body.html` + `_status_badge.html` macro); status badge styling (5 states with semantic colors, `FAILED` solid red + `CANCELLED` striped amber); HTMX polling-halt mechanic via attribute-absent re-render (D-09); cadence 10s list / 3s detail with list polling unconditional; vendored CSS + vendored HTMX (offline-capable); migration + wiring in separate commits (D-15); `failure_reason` format exactly `f"{type(exc).__name__}: {exc}"` (D-16); test strategy uses pytest + httpx `AsyncClient` via `ASGITransport` (D-18); minimum test coverage = failed-cascade happy-path + empty-state + halt-polling absence (D-20); `pyproject` script `dashboard = "robotina.dashboard:main"` (D-22); `docker-compose` service mirrors gateway env-wiring (D-23).

These D-NN are *starting points* — the planner may deviate with documented reasoning, but D-01 cannot be deviated from.

### Claude's Discretion

Everything except D-01 above is delegated to Claude. The planner can change the template file layout, the CSS approach, the test split, the polling URL paths, etc. — provided the SPEC's 11 acceptance criteria still pass and D-01 still holds.

### Deferred Ideas (OUT OF SCOPE)

- Filtering / search / pagination beyond "latest 50"
- Worker-crash reconciliation for stuck `RUNNING` rows
- Spanish UI / household-facing dashboard
- Per-step `duration_ms` denormalized column
- WebSockets / SSE
- Auth / authorization
- Retry / cancel / requeue actions
- React / Vite / any JS build toolchain
- Reading from Redis (Postgres is source of truth)
- Metrics / analytics / charts (LangWatch + OTel own that lane)
- Raw LLM output column (Phase 11 eliminated the parse-failure class)
- Dark theme

</user_constraints>

<phase_requirements>
## Phase Requirements

No formal REQ-IDs are assigned in `REQUIREMENTS.md` for Phase 13 — `13-SPEC.md`'s 9 requirements and 11 acceptance criteria are the authoritative checklist. Mapping:

| SPEC Req | Behavior | Research Support |
|----------|----------|------------------|
| Req 1 — Persist `step_input` | JSON column on `workflow_run_steps`, populated at enqueue | Existing `artifact: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)` pattern at `src/robotina/queue/models.py:51` is the template |
| Req 2 — Persist `failure_reason` | Text column on `workflow_run_steps`, populated in `on_step_failed` with `f"{type(exc).__name__}: {exc}"` | Touch point identified at `src/robotina/queue/workflow_runner.py:387-388` (the `step.status = WorkflowStepStatus.FAILED; session.flush()` block) |
| Req 3 — Alembic migration | New revision adding both nullable columns | Existing pattern in `migrations/versions/0003_step_order.py` is verbatim re-usable (op.add_column nullable + op.drop_column reverse) |
| Req 4 — Dashboard module | `src/robotina/dashboard/` with FastAPI app + templates | New module — no FastAPI app exists in `src/` yet (only stub at `src/robotina/scheduler/__init__.py`) |
| Req 5 — One-way dep boundary | grep gate; CI-enforceable | Verified the grep command returns zero matches on the current tree (no dashboard module exists yet, so this trivially passes — meaningful test is "still zero after the phase lands") |
| Req 6 — `uv run dashboard` + compose service | pyproject script + service entry | Pattern from existing `[project.scripts]` and `docker-compose.yml` (postgres + redis + rq-dashboard) is verbatim re-usable |
| Req 7 — List view `GET /` | 50 latest runs, newest first | SQLAlchemy 2.x `select(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(50)` |
| Req 8 — Detail view `GET /workflows/{id}` | header + ordered steps with input/output/failure | `WorkflowRun.steps` relationship already exists (back_populates); use `selectinload` to eager-load before session closes |
| Req 9 — HTMX polling | 10s list / 3s detail, halt at terminal | hx-trigger="every Xs" on a wrapper element; absent attribute on re-render = halt (verified pattern, see Pitfalls §3) |
</phase_requirements>

## Summary

Phase 13 is a small, contained, single-developer Python web app: 4 files of FastAPI/Jinja2 code, 6 Jinja templates, 1 hand-written CSS file, 1 vendored HTMX `.js`, 1 Alembic migration, 1 surgical wiring change in `workflow_runner.py` at three call sites, 1 pyproject script, 1 compose service entry. Every dependency the dashboard needs is already installed in the `.venv` except **Jinja2**, which is required and must be added to `pyproject.toml`.

The two technical patterns worth understanding deeply are: (a) **server-driven HTMX polling halt** — the wrapper element is re-rendered without `hx-trigger` when the workflow reaches a terminal status, and HTMX's `outerHTML` swap discards the old element and its timer entirely (verified against HTMX docs and the polling lifecycle); and (b) **SQLAlchemy 2.x detached-instance / session lifecycle** — the dashboard's request-scoped session must eagerly load the `WorkflowRun.steps` relationship via `selectinload` before the session closes, otherwise template rendering hits `DetachedInstanceError`.

**Primary recommendation:** Use installed FastAPI 0.135 + SQLAlchemy 2.0 + Alembic 1.18 + Uvicorn 0.42 + httpx 0.28 + Jinja2 3.1.6 (to add) + HTMX 2.0.10 (vendored). Render the polling fragment from a dedicated route (`/fragments/runs`, `/fragments/workflows/{id}`) that returns a `_partial.html` template — Starlette's `Jinja2Templates.TemplateResponse` does NOT support `block_name`, so block-selective rendering is not an option on this stack; use separate partial files (matches D-04 already).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Persist `step_input` JSON at enqueue | API / Backend (queue worker) | Database | Step input is built deterministically at enqueue; the worker writes it once and the column is read-only thereafter. Source of truth = Postgres. |
| Persist `failure_reason` in `on_step_failed` | API / Backend (queue worker) | Database | Exception serialization happens at the failure callsite in `workflow_runner.py`; column is read-only thereafter. |
| Alembic migration (add columns) | Database | — | Schema migration; reversible. Idempotent in the sense that the columns are nullable and historical rows backfill to NULL. |
| List view + detail view rendering | Frontend Server (SSR via FastAPI + Jinja2) | API / Backend (read-only DB query) | Server-rendered HTML; no client-side rendering. Browser does no business logic. |
| HTMX polling | Browser / Client (HTMX runtime) | Frontend Server (returns fragments) | The browser issues GETs on a timer; the server decides whether to embed the next `hx-trigger`. Halt logic lives in markup the server emits. |
| Status badge rendering | Frontend Server (Jinja2 macro) | — | Pure presentational. CSS class is server-rendered from the status enum value. |
| Static asset delivery (CSS, htmx.min.js) | Frontend Server (FastAPI `StaticFiles`) | — | No CDN; same FastAPI process serves both routes and static files. |
| Dashboard process lifecycle | OS / Compose | — | `uv run dashboard` for local; `docker-compose up dashboard` for staging. NOT a child of `agent` or `gateway`. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | `0.135.2` (installed; pin `>=0.115` per pyproject) | HTTP routes, request/response cycle, dependency injection | Already installed and in `pyproject.toml`. The only ASGI framework in the project. `[VERIFIED: .venv/bin/python -c "import fastapi; print(fastapi.__version__)" → 0.135.2]` |
| Starlette | `1.0.0` (transitive via FastAPI) | `Jinja2Templates`, `StaticFiles`, ASGI primitives | Transitive dep; `Jinja2Templates` and `StaticFiles` live in `fastapi.templating` / `fastapi.staticfiles` which re-export from Starlette. `[VERIFIED: import starlette → 1.0.0]` |
| Jinja2 | `>=3.1` (latest stable: **3.1.6**, released 2025-03-05) | Template engine | NOT installed yet — must be added to `pyproject.toml` `dependencies`. `Jinja2Templates` will raise `ImportError("jinja2 must be installed to use Jinja2Templates")` at import time if missing — verified against `.venv/lib/python3.12/site-packages/starlette/templating.py:28`. `[VERIFIED: PyPI release metadata 2025-03-05]` |
| HTMX | `2.0.10` (latest stable 2.x, released 2025; v1.x still supported with `htmx-1-compat` extension for IE11) | Client-side polling + outerHTML swap | Vendored at `src/robotina/dashboard/static/htmx.min.js`. Use v2.x (modern browsers; the dashboard is dev+staging only, no IE11 audience). `[VERIFIED: htmx.org/docs/#installing — current jsdelivr URL is `https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js`]` |
| SQLAlchemy | `2.0.48` (installed; pin `>=2.0` per pyproject) | ORM read queries | Already in use across the project. `Mapped[Optional[dict]]` syntax on the existing `artifact` column is the template for the two new columns. `[VERIFIED: import sqlalchemy → 2.0.48]` |
| Alembic | `1.18.4` (installed; pin `>=1.13` per pyproject) | Schema migration | Already in use. Migrations live in `migrations/versions/` (NOT `alembic/versions/` — the `script_location` in `alembic.ini` is `migrations`, not the default `alembic`). `[VERIFIED: import alembic → 1.18.4; cat alembic.ini → script_location = migrations]` |
| uvicorn | `0.42.0` (installed; pin `>=0.30` per pyproject) | ASGI server | The dashboard's `main()` calls `uvicorn.run(app, host=..., port=...)`. `[VERIFIED: import uvicorn → 0.42.0]` |
| Postgres | `15` (compose-pinned) | Source of truth for runs + steps | Existing service in `docker-compose.yml:3`. JSON column type works fine on Postgres 14+. `[VERIFIED: docker-compose.yml line 3 — image: postgres:15]` |
| Python | `3.12` (project pin `>=3.12,<3.13`) | Runtime | `[VERIFIED: pyproject.toml line 9]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | `0.28.1` (installed; pin `>=0.27` per pyproject) | Test client for FastAPI via `ASGITransport` | `httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")`. Signature verified: `ASGITransport.__init__(self, app, raise_app_exceptions=True, root_path='', client=('127.0.0.1', 123))`. `[VERIFIED: import httpx; from httpx import ASGITransport → module=httpx]` |
| pytest | `9.0.2` (installed) + `pytest-asyncio` `1.3.0` (installed) | Test runner; `asyncio_mode = "auto"` in pyproject lets `async def test_*` work without decorators | `[VERIFIED: tool.pytest.ini_options.asyncio_mode = "auto" in pyproject.toml]` |
| python-dotenv | already in pyproject | Loading `.env` at `main()` entry (mirrors gateway pattern) | `[VERIFIED: gateway/__init__.py:23 — load_dotenv() at the start of main()]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled CSS | Tailwind CSS / Pico.css | Both require either a build step (Tailwind) or a CDN dep (Pico). SPEC out-of-scope list forbids JS build toolchain; CDN runtime breaks the offline-staging rationale. Hand-rolled CSS wins by elimination. |
| Vendored HTMX | CDN HTMX (jsdelivr) | CDN works offline-during-development but staging containers should not require internet. Vendoring is explicit per D-13. |
| Separate `_partial.html` files | Starlette `block_name=` parameter for block-selective rendering | **Not available** on Starlette 1.0.0 — `TemplateResponse` signature verified to have NO `block_name` parameter (`.venv/.../starlette/templating.py:117-126`). Use separate partial files (matches D-04 anyway). |
| FastAPI sync routes | FastAPI async routes | The project uses sync SessionLocal() with psycopg2-binary. FastAPI runs sync route handlers in a thread pool, which is the correct fit for sync SQLAlchemy sessions. Async routes would require an async driver (asyncpg) which is explicitly NOT in this project per CLAUDE.md "What NOT to Use" reasoning (psycopg2-binary is the chosen driver). **Use sync `def` route handlers.** |
| `joinedload` for `steps` relationship | `selectinload` | For one-to-many, SQLAlchemy 2.x docs explicitly recommend `selectinload` as "generally the best loading strategy" — emits a second IN-clause SELECT instead of multiplying rows via JOIN. Use `selectinload`. |
| `JSON` SQLAlchemy column | `JSONB` (Postgres-specific) | Existing `artifact` column uses generic `sa.JSON` (verified: `models.py:51`). For consistency and portability, use `sa.JSON` for `step_input` too. JSONB performance benefits are irrelevant at this scale (dashboard reads, no indexed JSON queries). |

**Installation:**

```bash
# Add to pyproject.toml [project] dependencies:
#   "jinja2>=3.1"
# uv resolves and installs:
uv sync
# Vendor HTMX (one-time, committed to repo):
curl -fsSL https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js \
  -o src/robotina/dashboard/static/htmx.min.js
# Record the version and SHA-256 in a sibling file:
echo "2.0.10" > src/robotina/dashboard/static/htmx.version.txt
sha256sum src/robotina/dashboard/static/htmx.min.js >> src/robotina/dashboard/static/htmx.version.txt
```

**Version verification (live):**

`[VERIFIED: .venv/bin/python -c "import fastapi, sqlalchemy, alembic, uvicorn, httpx, pytest, pytest_asyncio; print(...)" → fastapi 0.135.2, sqlalchemy 2.0.48, alembic 1.18.4, uvicorn 0.42.0, httpx 0.28.1, pytest 9.0.2, pytest_asyncio 1.3.0]`

`[VERIFIED: PyPI metadata for jinja2 → 3.1.6 released 2025-03-05]`

`[VERIFIED: htmx.org/docs/#installing → 2.0.10 latest stable, vendoring URL `https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js`]`

## Architecture Patterns

### System Architecture Diagram

```
                  ┌────────────────────────────────┐
                  │  Developer's browser (HTMX 2)  │
                  └─────┬──────────────────────────┘
                        │ GET /           (10s polling on /fragments/runs)
                        │ GET /workflows/{id}  (3s polling on /fragments/workflows/{id})
                        ▼
        ┌──────────────────────────────────────────────────┐
        │  FastAPI app  (uvicorn, port DASHBOARD_PORT=8001) │
        │  ─────────────────────────────────────────────── │
        │  Routes:                                          │
        │    GET /                       → index.html       │
        │    GET /workflows/{id}         → workflow.html    │
        │    GET /fragments/runs         → _run_rows.html   │
        │    GET /fragments/workflows/{id} → _workflow_body │
        │    /static/*                   → StaticFiles      │
        │                                                   │
        │  Dependency: get_db()  yield SessionLocal()       │
        └──────┬───────────────────────────────────┬───────┘
               │                                   │
               │ SELECT (with selectinload(steps)) │ StaticFiles read
               ▼                                   ▼
        ┌──────────────┐                ┌─────────────────────┐
        │  Postgres 15 │                │ src/robotina/       │
        │              │                │ dashboard/static/   │
        │  workflow_   │                │   dashboard.css     │
        │    runs      │                │   htmx.min.js       │
        │  workflow_   │                │   htmx.version.txt  │
        │    run_steps │                └─────────────────────┘
        │   (incl new  │
        │    step_input│
        │    failure_  │ ◄─── populated by workflow_runner.py
        │    reason)   │       (queue module — NOT the dashboard)
        └──────────────┘
```

Data flow:
1. Browser requests `/` or `/workflows/{id}`. FastAPI route handler depends on `get_db()` (yield-style dep wrapping `SessionLocal()`).
2. Handler issues a single `select()` with `selectinload(WorkflowRun.steps)` (for detail) or just `select(WorkflowRun).order_by(created_at.desc()).limit(50)` (for list).
3. Handler returns `templates.TemplateResponse(request=request, name="...", context={...})`. The context includes the eagerly-loaded ORM rows; Jinja accesses `step.step_input`, `step.failure_reason`, `step.artifact`, etc. without triggering lazy loads (session is still open during render in the same request scope).
4. After response, `get_db()` cleanup closes the session.
5. HTMX in the browser fires the next polling GET against `/fragments/...`. The fragment route returns just the partial template's HTML (no `<html>`/`<body>`).
6. When workflow is terminal, the partial template emits the wrapper `<div id="workflow-body">` WITHOUT `hx-trigger`. HTMX's `hx-swap="outerHTML"` replaces the old wrapper (which had the timer) with this trigger-less wrapper. Polling halts naturally — no further timers fire because the old element no longer exists in the DOM.

### Recommended Project Structure

```
src/robotina/dashboard/
├── __init__.py              # exposes main(); maybe creates `app` at module level
├── __main__.py              # optional — supports `python -m robotina.dashboard`
├── app.py                   # FastAPI() instance + routes + StaticFiles mount
├── deps.py                  # get_db() yield-dep wrapping SessionLocal()
├── queries.py               # SELECT statements (list_recent_runs, get_workflow)
├── templates/
│   ├── base.html            # <head>, link to /static/dashboard.css + /static/htmx.min.js
│   ├── index.html           # extends base; renders list view
│   ├── workflow.html        # extends base; renders detail view
│   ├── _run_rows.html       # partial: <tbody> with row macros (polling target)
│   ├── _workflow_body.html  # partial: <div id="workflow-body"> with step list
│   └── _status_badge.html   # macro: status_badge(status)
└── static/
    ├── dashboard.css        # all CSS tokens + rules; ~150-250 lines
    ├── htmx.min.js          # vendored HTMX 2.0.10
    └── htmx.version.txt     # records pinned version + SHA-256
```

### Pattern 1: FastAPI + Jinja2Templates with sync DB session

```python
# Source: https://fastapi.tiangolo.com/advanced/templates/  [CITED]
#         https://fastapi.tiangolo.com/tutorial/sql-databases/  [CITED]
from typing import Annotated
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from robotina.db import SessionLocal
from robotina.queue.models import WorkflowRun, WorkflowStatus

app = FastAPI()
templates = Jinja2Templates(directory="src/robotina/dashboard/templates")
app.mount("/static", StaticFiles(directory="src/robotina/dashboard/static"), name="static")

def get_db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

DbDep = Annotated[Session, Depends(get_db)]

@app.get("/", response_class=HTMLResponse)
def list_view(request: Request, db: DbDep):
    runs = db.scalars(
        select(WorkflowRun)
        .order_by(WorkflowRun.created_at.desc())
        .limit(50)
    ).all()
    return templates.TemplateResponse(
        request=request, name="index.html", context={"runs": runs}
    )

@app.get("/workflows/{run_id}", response_class=HTMLResponse)
def detail_view(request: Request, run_id: str, db: DbDep):
    run = db.scalars(
        select(WorkflowRun)
        .where(WorkflowRun.id == run_id)
        .options(selectinload(WorkflowRun.steps))
    ).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Sort steps in Python by step_order (relationship is unordered by default)
    steps = sorted(run.steps, key=lambda s: s.step_order)
    is_terminal = run.status in (WorkflowStatus.DONE, WorkflowStatus.FAILED)
    return templates.TemplateResponse(
        request=request, name="workflow.html",
        context={"run": run, "steps": steps, "is_terminal": is_terminal},
    )
```

### Pattern 2: HTMX polling-halt via attribute-absent re-render

```html
<!-- Source: https://htmx.org/docs/  [VERIFIED behavior: WebFetch confirmed outerHTML replaces element entirely;
     new content lacking hx-trigger has no polling timer] -->

<!-- _workflow_body.html — RENDERED FOR NON-TERMINAL: -->
<div id="workflow-body"
     hx-get="/fragments/workflows/{{ run.id }}"
     hx-trigger="every 3s"
     hx-swap="outerHTML">
  ... step list ...
</div>

<!-- _workflow_body.html — RENDERED FOR TERMINAL (DONE/FAILED): -->
<div id="workflow-body">
  ... step list (no hx-trigger attribute) ...
</div>
```

Jinja conditional inside the partial:
```jinja
<div id="workflow-body"
     {% if not is_terminal %}hx-get="/fragments/workflows/{{ run.id }}"
     hx-trigger="every 3s"
     hx-swap="outerHTML"{% endif %}>
```

### Pattern 3: Pre-assigning `step_input` at enqueue sites

```python
# In src/robotina/queue/workflow_runner.py around line 156:
first_step, first_step_def = steps[0]
first_job_id = str(uuid.uuid4())
task_input = first_step_def.build_input(dict(shared_context), {})

# NEW — persist step_input to Postgres before commit
first_step.step_input = (
    task_input.model_dump(mode="json")  # if Pydantic
    if hasattr(task_input, "model_dump")
    else task_input  # if dict
)

queue.enqueue(...)
first_step.task_job_id = first_job_id
session.commit()
```

The same shape is repeated at line ~320 for `next_step`/`task_input`.

### Pattern 4: `failure_reason` serialization

```python
# In src/robotina/queue/workflow_runner.py around line 388:
step.status = WorkflowStepStatus.FAILED
# NEW: record the one-line exception summary.
# NOTE: this requires plumbing the exception through to on_step_failed.
# Currently on_step_failed takes (job_id, session, queue) — no exception arg.
# See "Common Pitfalls" §1 below for the wiring decision.
step.failure_reason = f"{type(exc).__name__}: {exc}"
session.flush()
```

### Pattern 5: pytest with httpx.ASGITransport (no live server)

```python
# Source: https://www.python-httpx.org/advanced/transports/  [CITED]
# Verified: from httpx import ASGITransport works in installed httpx 0.28.1
import pytest
import httpx
from robotina.dashboard.app import app

@pytest.mark.asyncio
async def test_list_view_empty(db_session):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/")
    assert r.status_code == 200
    assert "No workflows yet" in r.text
```

### Pattern 6: Alembic migration for two nullable columns

```python
# migrations/versions/0005_dashboard_columns.py
"""workflow_run_steps: add step_input (JSON) and failure_reason (Text)

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-14
"""
import sqlalchemy as sa
from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'workflow_run_steps',
        sa.Column('step_input', sa.JSON(), nullable=True),
    )
    op.add_column(
        'workflow_run_steps',
        sa.Column('failure_reason', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('workflow_run_steps', 'failure_reason')
    op.drop_column('workflow_run_steps', 'step_input')
```

### Anti-Patterns to Avoid

- **Don't pass the SQLAlchemy session out of the route handler scope.** Render the template *inside* the request scope, before `get_db()`'s `finally` block closes the session. Otherwise `DetachedInstanceError` when Jinja accesses `run.steps`.
- **Don't use lazy-load for `WorkflowRun.steps` in the detail view.** Use `selectinload(WorkflowRun.steps)`. Lazy load + closing session = error inside the template.
- **Don't share the Jinja2Templates instance across modules.** D-01 says no cross-module imports. Even though the dashboard's `templates` is harmless, treating it as private prevents future drift.
- **Don't mount the dashboard's FastAPI `app` into another module's app.** D-01: `app` stays private.
- **Don't put HTMX `hx-trigger` on the *page* element.** Put it on the fragment wrapper that the polling endpoint returns, so the wrapper can re-render itself trigger-less (D-09 polling-halt). Putting it on `<body>` or a parent element means the wrapper's trigger-less re-render won't halt the parent's timer.
- **Don't add a column with a non-NULL default and existing rows on a hot table.** Alembic `op.add_column` with `nullable=False` and `server_default=...` is a full table rewrite on some Postgres versions. SPEC mandates nullable, so this is already correct — call it out so the planner doesn't "improve" it.
- **Don't introduce a separate engine or sessionmaker** for the dashboard. D-01 + SPEC constraint both require reuse of `SessionLocal()`.
- **Don't write the dashboard CSS inline in a Jinja template.** Single `dashboard.css` per UI-SPEC D-12. Inline styles are not part of the contract.
- **Don't load HTMX from a CDN.** D-13: vendored only. The vendored file's first line must record the version + SHA-256 (UI-SPEC §"Registry Safety").

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML template inheritance + macros | String concatenation, f-strings, custom templating | **Jinja2** (already standard with FastAPI) | Jinja handles autoescape, macro args, block inheritance, `tojson` filter. Hand-rolled = XSS risk + broken nesting. |
| Pretty-printing JSON in templates | Custom recursive printer | `{{ obj | tojson(indent=2) }}` (Jinja2 built-in filter) | Built-in; handles None, datetime, nested dicts. UI-SPEC explicitly references this filter. |
| Polling lifecycle / teardown | JS setInterval + clearInterval + cleanup | **HTMX `hx-trigger="every Xs"` + outerHTML swap** | The trigger-less-re-render pattern means zero JS. HTMX manages timer lifecycle per-element automatically. |
| Static asset serving | Custom route that opens files | `app.mount("/static", StaticFiles(directory=...))` | Built-in, handles range requests, ETag, mime types. |
| Test client for ASGI | Spinning up uvicorn on a random port | `httpx.ASGITransport(app=app)` | No socket. Faster, deterministic. Already installed. |
| ASCII/Unicode-safe error serialization | Custom encoder for the exception → string | `f"{type(exc).__name__}: {exc}"` | SPEC fixes the format. Python's `str(exc)` handles unicode in the message; the column is `Text` not `Varchar`, so length is unbounded. Caveat: chained exceptions (see Pitfalls §2). |
| Schema migration | Hand-written `ALTER TABLE` SQL | **Alembic** (already configured) | Migrations live in `migrations/versions/`; the `env.py` already imports `robotina.queue.models` so `target_metadata = Base.metadata` is current. |
| One-to-many eager loading | `for run in runs: run.steps; ...` (n+1) | `select(...).options(selectinload(WorkflowRun.steps))` | Two queries total instead of 1+N. |
| Status enum → CSS class | If/else ladder | `<span class="badge badge--{{ status.value | lower }}">` (Jinja) | One macro, one expression. |

**Key insight:** Phase 13 is a *small* phase. Every "let me write a tiny helper" temptation has a one-liner already in the stack. The risk is over-engineering, not under-engineering.

## Runtime State Inventory

This is a *new module* phase, not a rename or refactor — but the migration touches an existing table with live data. Inventory:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `workflow_run_steps` table has existing rows (any prior workflow runs). New columns `step_input` and `failure_reason` MUST be nullable so historical rows backfill to NULL. SPEC constraint #7 makes this explicit. | Nullable columns + NULL backfill. No data migration script needed. |
| Live service config | None — dashboard reads from the same Postgres the worker uses, via the same `DATABASE_URL`. No new external service registration. | None. |
| OS-registered state | None — no Task Scheduler / systemd / pm2 registration. Dashboard is launched via `uv run` (dev) or compose `restart: unless-stopped` (staging, pattern mirroring gateway). | New compose service entry; no OS-level registration outside the container. |
| Secrets / env vars | New: `DASHBOARD_PORT` (optional, default 8001 per D-22). Existing: `DATABASE_URL` reused. No new secrets. | Add `DASHBOARD_PORT` to `.env.example` per user memory directive `feedback_env_example.md`. |
| Build artifacts / installed packages | `src/robotina.egg-info/` (if it exists) is stale after `pyproject.toml` change (new dep `jinja2`, new script `dashboard`). | After editing `pyproject.toml`, run `uv sync` to refresh the editable install. |

**The canonical question:** After every file lands, what runtime systems still have stale state? Answer: **only** the editable install of `robotina` if not re-synced after pyproject changes. `uv sync` resolves it.

## Common Pitfalls

### Pitfall 1: `on_step_failed` does not currently receive the exception

**What goes wrong:** SPEC req 2 says "populate `failure_reason` in `on_step_failed` with `f"{type(exc).__name__}: {exc}"`" — but the current `on_step_failed(job_id, session, queue=None)` signature (`workflow_runner.py:351`) takes NO exception argument. The exception lives in the caller — the RQ job exception handler, which is in `src/robotina/queue/jobs.py` or `runner.py` (not in the read window).

**Why it happens:** RQ's standard pattern is that the job function re-raises, and a hook on the queue records the failure. The current code path likely catches the exception in the job wrapper and calls `on_step_failed(job_id, session, queue)` without passing the exception.

**How to avoid:**
- **Option A (recommended):** Change `on_step_failed` signature to accept `exc: BaseException` and thread it through the caller. Update the one call site in `jobs.py` / `runner.py`. Update existing tests in `tests/test_workflow_runner.py` (the `on_step_failed` tests). This is a 1-line signature change + 1-line caller change + N test updates.
- **Option B:** Add a separate function `record_step_failure_reason(job_id, exc, session)` called immediately before `on_step_failed`. Pros: zero changes to existing tests. Cons: two functions to call in lockstep.

**Warning signs:** Plan task says "add `failure_reason` write in `on_step_failed`" without addressing where `exc` comes from. The planner MUST explicitly trace the call chain `jobs.run_task` (or equivalent) → `on_step_failed` to find or pass the exception. The planner should read `src/robotina/queue/jobs.py` and locate the `except` block that currently calls `on_step_failed`.

### Pitfall 2: Chained exceptions and the `failure_reason` format

**What goes wrong:** SPEC fixes the format as `f"{type(exc).__name__}: {exc}"` — but if `exc` is `ValueError("foo") raise from KeyError("bar")`, the `__cause__` is silently dropped. Worse, some exceptions like `LangChainException` override `__str__` to return multi-line content (full traceback-like detail), which breaks the "one-line" intent.

**Why it happens:** Python's `str(exc)` for nested or richly-formatted exceptions sometimes embeds newlines.

**How to avoid:**
- Use exactly the format SPEC mandates: `f"{type(exc).__name__}: {exc}"`. Do NOT add traceback handling, do NOT chase `__cause__`. SPEC is explicit.
- BUT: defensively replace newlines with spaces before persisting, so the UI single-line rendering doesn't break: `failure_reason = f"{type(exc).__name__}: {exc}".replace("\n", " ").strip()`. Document this in the plan as a "defensive single-line normalization" — it's NOT a deviation from SPEC (the format is unchanged), it's a sanitization of the `{exc}` portion.
- Column type is `sa.Text()` — no length limit on Postgres `TEXT`. No truncation needed at the DB layer.

**Warning signs:** A test runs a workflow with a deliberately-raised `Exception("multi\nline\nmessage")` and the dashboard shows the failure block stretching across three lines.

### Pitfall 3: HTMX polling-halt only works if BOTH conditions hold

**What goes wrong:** Polling continues even after the workflow reaches a terminal status (SPEC AC #9 fails).

**Why it happens:** Two subtle requirements must both hold:
1. The polling MUST be on the wrapper element (`<div id="workflow-body">`), NOT on a parent like `<main>` or `<body>`.
2. `hx-swap="outerHTML"` MUST be set, so the *wrapper itself* gets replaced, not its inner content. With `innerHTML` (the HTMX default), the wrapper element keeps its `hx-trigger` attribute, and polling continues forever.

**How to avoid:**
- Always set `hx-swap="outerHTML"` on the polling wrapper.
- Verify with the SPEC AC test: poll the detail view of a `DONE` workflow once, then watch the network tab — no further polls should appear.
- Verify the rendered HTML for terminal state has NO `hx-trigger` substring: `assert 'hx-trigger' not in response.text` for terminal-status detail responses (matches D-20).

**Warning signs:** Network tab shows repeated GETs to `/fragments/workflows/{id}` after the status is `DONE`.

**[VERIFIED: htmx.org docs — outerHTML "replaces the entire target element with the returned content"; new content lacking hx-trigger has no polling timer because HTMX timers are bound to specific DOM element instances]**

### Pitfall 4: `DetachedInstanceError` when Jinja accesses `run.steps`

**What goes wrong:** `run = db.scalars(select(WorkflowRun).where(...)).first()` returns a `WorkflowRun`; the template later does `{% for step in run.steps %}` and raises `sqlalchemy.orm.exc.DetachedInstanceError: Parent instance <WorkflowRun ...> is not bound to a Session`.

**Why it happens:** SQLAlchemy 2.x's `WorkflowRun.steps` relationship is `lazy="select"` by default. When Jinja accesses `run.steps`, the ORM tries to issue a SELECT — but if the session has already been closed by `get_db()`'s `finally` block, it fails.

**How to avoid:**
- **Eager-load** with `selectinload(WorkflowRun.steps)` in the SELECT.
- **OR** trigger access while the session is still open and store the loaded list in the context: `steps = list(run.steps)` BEFORE returning the `TemplateResponse`.
- The `selectinload` approach is cleaner because the SELECT is one round-trip vs. lazy-load issuing a follow-up.

**Warning signs:** First page load works (or fails immediately with `DetachedInstanceError`), depending on whether yield-dep cleanup runs before or after the template engine renders.

**[VERIFIED: SQLAlchemy 2.x docs — selectinload is the recommended one-to-many eager loader; lazy-load after session close raises DetachedInstanceError]**

### Pitfall 5: `WorkflowRun.steps` relationship is unordered

**What goes wrong:** Steps render in non-deterministic order — a workflow with steps `[research-gather, research-instructions, research-ingredients]` shows them shuffled.

**Why it happens:** The relationship `steps: Mapped[list["WorkflowRunStep"]] = relationship(back_populates="workflow_run")` in `models.py:37` has NO `order_by=` clause. The list reflects insertion / fetch order, which is not guaranteed.

**How to avoid:**
- In the dashboard's detail-view handler, sort in Python: `steps = sorted(run.steps, key=lambda s: s.step_order)`.
- **Or** pass `order_by` directly in the SELECT: `select(WorkflowRunStep).where(...).order_by(WorkflowRunStep.step_order)`. This is cleaner for the list-of-step view.
- Do NOT modify the model's relationship definition — that would affect every other consumer of `WorkflowRun.steps`. D-01 spirit: surgical change.

**Warning signs:** UI-SPEC test "for a workflow whose 2nd step failed and steps 3–4 cancelled, the detail view shows: step 1 DONE, step 2 FAILED, steps 3–4 CANCELLED" fails because the rendered order doesn't match `step_order`.

### Pitfall 6: `Pydantic input.model_dump(mode='json')` vs raw dict

**What goes wrong:** `step_input` JSON column gets a Python `datetime` object (not JSON-serializable) and the worker crashes at commit.

**Why it happens:** Some task types (`RecipeResearchInput`, `RecipeLoadInput`) are Pydantic BaseModels; others may be plain dicts. The Pydantic models contain `datetime` fields (`Message.sent_at: datetime` at `task_types.py:31`). `dict(model)` returns Python objects; `model.model_dump(mode='json')` serializes datetime → ISO string.

**How to avoid:**
- At each enqueue site, detect the type and call `model_dump(mode="json")` if Pydantic:
  ```python
  if hasattr(task_input, "model_dump"):
      step.step_input = task_input.model_dump(mode="json")
  else:
      step.step_input = task_input  # already a dict
  ```
- This mirrors the existing artifact handling at `workflow_runner.py:274-279` (`if hasattr(output, "model_dump"): artifact = output.model_dump(mode="json")`).

**Warning signs:** The worker logs `TypeError: Object of type datetime is not JSON serializable` on the first enqueue after the migration lands.

### Pitfall 7: Tests that flush the workflow_run_steps table interfere with the dashboard tests

**What goes wrong:** Running `tests/dashboard/test_*` alongside existing integration tests deletes rows mid-test.

**Why it happens:** `tests/conftest.py:11-22` defines a `db_session` fixture that DELETEs `stored_messages` and `conversations` after each test. If the dashboard fixture follows the same pattern but also DELETEs `workflow_run_steps`/`workflow_runs`, parallel test runs interfere.

**How to avoid:**
- Make the dashboard's DB fixture additive: insert test data with unique IDs (UUIDs), and clean up by ID-list rather than wholesale TABLE deletion.
- Pytest's `asyncio_mode = "auto"` (verified in `pyproject.toml:55`) means `async def test_*` runs without explicit decorators. Use sync handler tests (sync route + sync session) for most cases; reserve async tests for the `httpx.AsyncClient` ASGI client.

**Warning signs:** Tests pass in isolation, fail when run together. Or: existing `tests/test_workflow_runner.py` integration tests start failing after dashboard tests run.

### Pitfall 8: Alembic discovery path

**What goes wrong:** Planner writes the migration file to `alembic/versions/` (referenced in CONTEXT.md canonical_refs) — but the project's actual `script_location` is `migrations` (alembic.ini:8). The migration file is silently ignored.

**Why it happens:** CONTEXT.md says "`alembic/versions/`" but the live config says `migrations`.

**How to avoid:**
- The new migration goes in `migrations/versions/0005_dashboard_columns.py` (or whatever revision-naming convention extends the existing `0001_init`, `0002_models`, `0003_step_order`, `0004_workflow_pending_status` series).
- `down_revision = '0004'` (the current head).
- The planner MUST verify path before writing: `ls migrations/versions/` shows the actual location.

**Warning signs:** `uv run migrate` reports "Target database is not up to date" or "Revision XXXX not found" — usually means the file is in the wrong directory.

**[VERIFIED: cat alembic.ini → `script_location = migrations`; ls migrations/versions/ → 0001_init.py, 0002_models.py, 0003_step_order.py, 0004_workflow_pending_status.py]**

## Code Examples

### Example 1: Full `app.py` skeleton

```python
# Source: composed from FastAPI templates + dependencies docs  [CITED]
from typing import Annotated
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from robotina.db import SessionLocal
from robotina.queue.models import WorkflowRun, WorkflowStatus, WorkflowStepStatus

# Independence: no other robotina.* imports allowed.

_HERE = Path(__file__).parent
app = FastAPI(title="Robotina Queue Dashboard")
templates = Jinja2Templates(directory=str(_HERE / "templates"))
app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


DbDep = Annotated[Session, Depends(get_db)]
TERMINAL = {WorkflowStatus.DONE, WorkflowStatus.FAILED}


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: DbDep):
    runs = db.scalars(
        select(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(50)
    ).all()
    return templates.TemplateResponse(
        request=request, name="index.html", context={"runs": runs},
    )


@app.get("/workflows/{run_id}", response_class=HTMLResponse)
def detail(request: Request, run_id: str, db: DbDep):
    run = db.scalars(
        select(WorkflowRun)
        .where(WorkflowRun.id == run_id)
        .options(selectinload(WorkflowRun.steps))
    ).first()
    if run is None:
        raise HTTPException(404, detail=f"Workflow {run_id} not found")
    steps = sorted(run.steps, key=lambda s: s.step_order)
    return templates.TemplateResponse(
        request=request, name="workflow.html",
        context={
            "run": run,
            "steps": steps,
            "is_terminal": run.status in TERMINAL,
        },
    )


@app.get("/fragments/runs", response_class=HTMLResponse)
def fragment_runs(request: Request, db: DbDep):
    runs = db.scalars(
        select(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(50)
    ).all()
    return templates.TemplateResponse(
        request=request, name="_run_rows.html", context={"runs": runs},
    )


@app.get("/fragments/workflows/{run_id}", response_class=HTMLResponse)
def fragment_workflow(request: Request, run_id: str, db: DbDep):
    run = db.scalars(
        select(WorkflowRun)
        .where(WorkflowRun.id == run_id)
        .options(selectinload(WorkflowRun.steps))
    ).first()
    if run is None:
        raise HTTPException(404, detail=f"Workflow {run_id} not found")
    steps = sorted(run.steps, key=lambda s: s.step_order)
    return templates.TemplateResponse(
        request=request, name="_workflow_body.html",
        context={
            "run": run,
            "steps": steps,
            "is_terminal": run.status in TERMINAL,
        },
    )


def main() -> None:
    """Entry point for `uv run dashboard`."""
    import os
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv()
    port = int(os.environ.get("DASHBOARD_PORT", "8001"))
    uvicorn.run(
        "robotina.dashboard.app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        # No reload — staging container runs production-style
    )
```

### Example 2: Polling wrapper conditional in `_workflow_body.html`

```jinja
{# Source: composed from HTMX docs + D-09  #}
<div id="workflow-body"
     {% if not is_terminal %}
     hx-get="/fragments/workflows/{{ run.id }}"
     hx-trigger="every 3s"
     hx-swap="outerHTML"
     {% endif %}>
  {# ... step list rendering ... #}
  <section class="steps">
    {% for step in steps %}
      <article class="step-row" data-status="{{ step.status.value }}">
        <header>
          <span class="step-key">{{ step.step_key }}</span>
          {% from "_status_badge.html" import status_badge %}
          {{ status_badge(step.status.value.upper()) }}
          {% if step.started_at %}<span class="ts">Started: {{ step.started_at.isoformat() }}</span>{% endif %}
          {% if step.completed_at %}<span class="ts">Completed: {{ step.completed_at.isoformat() }}</span>{% endif %}
        </header>
        {% if step.failure_reason %}
          <div class="failure-block">
            <strong>Failure:</strong>
            <code>{{ step.failure_reason }}</code>
          </div>
        {% endif %}
        {% if step.step_input is not none %}
          <h3>Input</h3>
          <pre class="json-block">{{ step.step_input | tojson(indent=2) }}</pre>
        {% endif %}
        {% if step.artifact is not none %}
          <h3>Output</h3>
          <pre class="json-block">{{ step.artifact | tojson(indent=2) }}</pre>
        {% endif %}
      </article>
    {% endfor %}
  </section>
</div>
```

### Example 3: docker-compose service entry

```yaml
# docker-compose.yml — add this service entry alongside postgres / redis / rq-dashboard
  dashboard:
    build: .
    command: uv run dashboard
    environment:
      DATABASE_URL: postgresql://robotina:robotina@postgres:5432/robotina
      DASHBOARD_PORT: "8001"
    ports:
      - "8001:8001"
    depends_on:
      postgres:
        condition: service_healthy
    # Independence rule D-01: agent / gateway do NOT depend on this service.
```

### Example 4: Independence enforcement test

```python
# tests/dashboard/test_independence.py
import subprocess
from pathlib import Path


def test_no_reverse_imports_from_dashboard():
    """SPEC AC: zero reverse imports from robotina.dashboard."""
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            "grep", "-rE",
            r"from robotina\.dashboard|import robotina\.dashboard",
            str(repo_root / "src" / "robotina"),
            "--exclude-dir=dashboard",
        ],
        capture_output=True, text=True,
    )
    # grep exits 1 when no match. That's the success case.
    assert result.returncode == 1, (
        f"Found reverse imports from robotina.dashboard:\n{result.stdout}"
    )


def test_dashboard_does_not_import_forbidden_modules():
    """D-01 inward-only rule: dashboard imports only db, queue.models, queue.task_types."""
    repo_root = Path(__file__).resolve().parents[2]
    dashboard_dir = repo_root / "src" / "robotina" / "dashboard"
    forbidden_prefixes = [
        "from robotina.agent",
        "from robotina.gateway",
        "from robotina.llm",
        "from robotina.scheduler",
        "from robotina.queue.workflow_runner",
        "from robotina.queue.runner",
        "from robotina.queue.jobs",
        "from robotina.all",
        "import robotina.agent",
        "import robotina.gateway",
        "import robotina.llm",
        "import robotina.scheduler",
        "import robotina.queue.workflow_runner",
        "import robotina.queue.runner",
        "import robotina.queue.jobs",
        "import robotina.all",
    ]
    offenders = []
    for py_file in dashboard_dir.rglob("*.py"):
        text = py_file.read_text()
        for pat in forbidden_prefixes:
            if pat in text:
                offenders.append((py_file.relative_to(repo_root), pat))
    assert not offenders, f"Forbidden imports found: {offenders}"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Starlette `TestClient` (sync) for FastAPI tests | `httpx.AsyncClient(transport=ASGITransport(app=app))` | httpx 0.20+ exposed ASGITransport publicly; both still supported but ASGITransport is the async-native path | Use ASGITransport for parity with the project's `asyncio_mode = "auto"` test config |
| SQLAlchemy 1.x `Column(JSON)` declarative | SQLAlchemy 2.x `mapped_column(JSON)` with `Mapped[Optional[dict]]` typing | SQLAlchemy 2.0 (Jan 2023) | The new columns follow the existing 2.x pattern at `models.py:51` verbatim |
| HTMX 1.x (jQuery-compat era) | HTMX 2.0+ (modern-only, no IE11 by default) | 2024 | The dashboard is a modern-browser dev tool; HTMX 2.0.10 is appropriate. v1.x still maintained for IE11 needs (not relevant here). |
| `session.query(Model).filter(...).all()` legacy API | `session.scalars(select(Model).where(...)).all()` | SQLAlchemy 2.0 unified API | Use 2.x `select()` style in the dashboard. Existing project code still uses some 1.x-style `session.query` calls (see `workflow_runner.py:191-196`); the dashboard need not match — it's a new module and should set the better example. |

**Deprecated/outdated:**
- Using `Jinja2Templates(name="...")` (positional template arg) — Starlette 1.0 signature requires `request` as first arg (verified in source). Pass kwargs.
- HTMX 1.x as the default — use 2.0.10.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `on_step_failed` is called from a wrapper in `queue/jobs.py` that has access to the exception in scope | Pitfall 1 | If the call site is structured differently (e.g., RQ's `failure_callback` mechanism), the wiring change might require more re-architecture. Planner MUST read `src/robotina/queue/jobs.py` to confirm. |
| A2 | Pydantic input objects (`RecipeResearchInput`, `RecipeLoadInput`, etc.) have `.model_dump(mode='json')` and serialize without error to the JSON column | Pattern 3 | If any task type has a non-serializable field (e.g., raw bytes), the `step_input` column write will throw. Mitigation already in pattern: hasattr-check + fallback. |
| A3 | The existing `artifact` JSON column type is `sa.JSON` (generic, not `sa.dialects.postgresql.JSONB`) | Standard Stack alternatives | Verified by reading `models.py:6` (`from sqlalchemy import ... JSON, ...`) and `models.py:51` (`Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)`). HIGH confidence — but if the planner discovers a different column type in a more-recent migration, `step_input` should match. |
| A4 | The dashboard's compose service can use the same image as the agent/gateway (single Dockerfile in repo root, `build: .`) | Example 3 | If the project uses per-service Dockerfiles (e.g., `dashboard.Dockerfile`), the compose entry differs. Planner should look at how `gateway`/`agent` services are wired — if they aren't in compose yet, the dashboard becomes the first non-infra service entry. (Current compose has only postgres/redis/rq-dashboard — no agent/gateway services. The dashboard service might be the first.) |
| A5 | `uv sync` is sufficient to refresh the editable install after adding `jinja2` to pyproject | Runtime State Inventory | If the project uses a different uv invocation (e.g., `uv lock && uv sync`), the planner should match existing project documentation. |
| A6 | The `--exclude-dir=dashboard` flag in the SPEC grep AC is interpreted by `grep -r` correctly without requiring quoting in CI | Code Example 4 | Verified to work in bash invocation; if CI uses a different shell or grep variant, syntax may differ. |
| A7 | No FastAPI app currently runs at port 8001 in the staging compose environment | Example 3 | Standard staging port assignment; verify by checking if `8001` is used elsewhere. The default `DASHBOARD_PORT=8001` is from D-22. |

## Open Questions (RESOLVED)

1. **Exception propagation to `on_step_failed`** (resolves Pitfall 1). **RESOLVED:** Option A — extend `on_step_failed` signature with keyword-only `exc: BaseException | None = None`; `src/robotina/queue/jobs.py` threads `exc=exc` from its two `except Exception as exc:` blocks (send-notification branch ~line 109; generic branch ~line 217). Backward compatible (legacy positional callers unaffected). Implemented in **Plan 13-01 Task 1.2**.
   - What we know: `on_step_failed(job_id, session, queue=None)` currently has no `exc` parameter.
   - What's unclear: Whether the caller in `queue/jobs.py` (or `runner.py`) has the exception in scope, and whether the cleanest change is signature extension or a sibling function.
   - Recommendation: Planner reads `src/robotina/queue/jobs.py` to locate the failure path before writing the plan task. Use Option A (extend signature) unless the call site reveals a complication.

2. **Compose service: which image / build context?** **RESOLVED:** No Dockerfile exists in the repo today (verified by `ls` in plan-time codebase audit). **Plan 13-03 Task 3.1** creates the first one at repo root with an explicit allow-list `COPY` (no `COPY . .`) so secrets/`.env` cannot enter the image. The compose `dashboard` service uses `build: .` against this new Dockerfile and reads the same `DATABASE_URL` env as the rest of the stack.
   - What we know: docker-compose.yml has no `agent` or `gateway` services today — only infra (postgres, redis, rq-dashboard).
   - What's unclear: Does staging build a Dockerfile in repo root, or is there a `staging/` compose overlay elsewhere?
   - Recommendation: Plan task should treat the dashboard service as additive ("first non-infra service"). If a Dockerfile doesn't exist, the planner must either (a) defer the compose service entry to a follow-up (and document), or (b) include "create Dockerfile" as a sibling task. The user's memory `project_local_dev_setup.md` says staging is fully containerized, so a Dockerfile likely exists somewhere — verify.

3. **Test integration with existing `db_session` fixture.** **RESOLVED:** **Plan 13-02 Task 2.1** adds `tests/dashboard/conftest.py` with a `db_session` fixture whose teardown cleans **only the rows it inserted (by UUID)** — never bulk-deletes `workflow_runs` or `workflow_run_steps` (Pitfall 7). The fixture is package-scoped to `tests/dashboard/` so other suites are unaffected.
   - What we know: `tests/conftest.py:11-22` cleans `stored_messages` and `conversations` after each test. It does NOT touch `workflow_runs`/`workflow_run_steps`.
   - What's unclear: Whether `tests/test_workflow_runner.py` and `tests/test_queue_models.py` rely on a clean workflow tables state.
   - Recommendation: Planner should add a dashboard-specific fixture that cleans only the rows it inserted (by UUID), not the whole table. Run the new dashboard test file in isolation first to verify; then run the full suite.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.12 (project-pinned `>=3.12,<3.13`) | — |
| FastAPI | All HTTP routes | ✓ | 0.135.2 | — |
| Starlette | Jinja2Templates / StaticFiles | ✓ | 1.0.0 (transitive) | — |
| SQLAlchemy | Read queries | ✓ | 2.0.48 | — |
| Alembic | Migration | ✓ | 1.18.4 | — |
| uvicorn | ASGI server | ✓ | 0.42.0 | — |
| httpx | Test client (ASGITransport) | ✓ | 0.28.1 | — |
| pytest + pytest-asyncio | Test runner | ✓ | 9.0.2 / 1.3.0 | — |
| python-dotenv | `.env` loading at main() | ✓ | (already in pyproject) | — |
| psycopg2-binary | Postgres driver | ✓ | (already in pyproject) | — |
| **Jinja2** | Template engine | ✗ | — | **Must be added to pyproject `dependencies`** — no fallback (Jinja2Templates raises ImportError without it). Verified at `.venv/lib/python3.12/site-packages/starlette/templating.py:28`. |
| HTMX | Client-side polling | ✗ | — | **Vendored at install time** by downloading htmx.min.js 2.0.10 from jsdelivr (one-time, committed). No CDN, no fallback. |
| Postgres 15 | DB | (via compose) | 15 (compose-pinned) | — |
| uv | Package manager / runner | (assumed present) | — | — |
| docker / docker-compose | Compose service runner | (assumed for staging) | — | — |

**Missing dependencies with no fallback:** None blocking — Jinja2 install is a 1-line addition.

**Missing dependencies with fallback:** None — Jinja2 and HTMX are required at install/vendor time, not at runtime fallback time.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 (`asyncio_mode = "auto"`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (verified lines 53-58) |
| Quick run command | `uv run pytest tests/dashboard -x -q` |
| Full suite command | `uv run pytest -q` |
| Integration marker | `@pytest.mark.integration` (live Postgres + Redis) — defined in pyproject |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SPEC Req 1 | `step_input` populated at every enqueue | integration | `uv run pytest tests/test_workflow_runner.py::test_step_input_persisted_on_enqueue -x` | ❌ Wave 0 |
| SPEC Req 2 | `failure_reason` populated in `on_step_failed`; format `"Class: msg"` | unit | `uv run pytest tests/test_workflow_runner.py::test_failure_reason_set_on_failure -x` | ❌ Wave 0 |
| SPEC Req 3 | Alembic upgrade + downgrade reverses cleanly | integration | `uv run pytest tests/dashboard/test_migration.py -x -m integration` | ❌ Wave 0 |
| SPEC Req 4 | Dashboard module exists; app starts | unit | `uv run pytest tests/dashboard/test_app_starts.py -x` | ❌ Wave 0 |
| SPEC Req 5 | Independence grep returns zero | unit | `uv run pytest tests/dashboard/test_independence.py -x` | ❌ Wave 0 |
| SPEC Req 6 | `uv run dashboard` boot smoke; compose service comes up | manual | `uv run dashboard` + `docker-compose up dashboard` | manual smoke (D-21) |
| SPEC Req 7 | `GET /` returns 50 rows ordered desc; empty state at 0 | integration | `uv run pytest tests/dashboard/test_list_view.py -x -m integration` | ❌ Wave 0 |
| SPEC Req 8 | `GET /workflows/{id}` shows ordered steps + failed/cancelled badges | integration | `uv run pytest tests/dashboard/test_detail_view.py -x -m integration` | ❌ Wave 0 |
| SPEC Req 9 | Polling halts at terminal: terminal response lacks `hx-trigger` | unit | `uv run pytest tests/dashboard/test_polling_halt.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/dashboard -x -q` (skips integration unless `-m integration` passed; runs the unit tests fast)
- **Per wave merge:** `uv run pytest -q` (full suite including the existing test_workflow_runner / test_queue_models / test_rq_integration tests)
- **Phase gate:** Full suite green + `uv run pytest -m integration -q` green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/dashboard/__init__.py` — package marker
- [ ] `tests/dashboard/conftest.py` — shared fixtures (httpx AsyncClient, sample workflow/step factories)
- [ ] `tests/dashboard/test_app_starts.py` — import + `app` object exists
- [ ] `tests/dashboard/test_independence.py` — grep gate (SPEC AC #10)
- [ ] `tests/dashboard/test_list_view.py` — empty state + 50-row cap + ordering (SPEC Req 7)
- [ ] `tests/dashboard/test_detail_view.py` — failed step + cancelled cascade + badges (SPEC Req 8)
- [ ] `tests/dashboard/test_polling_halt.py` — terminal-status response has no `hx-trigger` (SPEC Req 9, D-20)
- [ ] `tests/dashboard/test_migration.py` — upgrade + downgrade against fresh DB (SPEC Req 3)
- [ ] Extend `tests/test_workflow_runner.py` with `test_step_input_persisted_on_enqueue` and `test_failure_reason_set_on_failure` (SPEC Reqs 1 + 2)
- [ ] Jinja2 dep install: `uv add jinja2` — required before any dashboard test imports the FastAPI app
- [ ] HTMX vendoring: `curl … > src/robotina/dashboard/static/htmx.min.js` — required before manual smoke (D-21)

## Sources

### Primary (HIGH confidence — verified in installed venv or on official docs)

- `[VERIFIED]` `.venv/bin/python -c "import fastapi, sqlalchemy, alembic, uvicorn, httpx, pytest, pytest_asyncio, starlette"` → versions confirmed: fastapi 0.135.2, starlette 1.0.0, sqlalchemy 2.0.48, alembic 1.18.4, uvicorn 0.42.0, httpx 0.28.1, pytest 9.0.2, pytest_asyncio 1.3.0
- `[VERIFIED]` `.venv/.../starlette/templating.py:117-156` — `TemplateResponse` signature has NO `block_name` parameter
- `[VERIFIED]` `.venv/.../starlette/templating.py:28` — Jinja2Templates raises `ImportError("jinja2 must be installed to use Jinja2Templates")` if jinja2 absent
- `[VERIFIED]` `httpx.ASGITransport.__init__` signature: `(app, raise_app_exceptions=True, root_path='', client=('127.0.0.1', 123))` from installed module
- `[VERIFIED]` `cat alembic.ini` → `script_location = migrations` (NOT `alembic`)
- `[VERIFIED]` `ls migrations/versions/` → 0001, 0002, 0003, 0004 currently present
- `[VERIFIED]` `src/robotina/queue/models.py:51` → `artifact: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)` — template for new columns
- `[VERIFIED]` `src/robotina/queue/workflow_runner.py:156, 320, 388` — three wiring touch points confirmed
- `[VERIFIED]` `src/robotina/db.py:24` — `SessionLocal()` factory exists
- `[VERIFIED]` `pyproject.toml:42-48` — `[project.scripts]` pattern (`agent`, `gateway`, `migrate`, `all`) — dashboard follows same shape
- `[VERIFIED]` `docker-compose.yml:1-42` — current services: postgres, redis, rq-dashboard; no agent/gateway services in compose today
- `[VERIFIED]` `tests/conftest.py:11-22` — existing `db_session` fixture cleans only gateway tables
- `[VERIFIED]` `pyproject.toml:55` — `asyncio_mode = "auto"`
- `[CITED]` https://fastapi.tiangolo.com/advanced/templates/ — Jinja2Templates + TemplateResponse + StaticFiles canonical patterns
- `[CITED]` https://fastapi.tiangolo.com/tutorial/sql-databases/ — `get_db` yield-dep canonical pattern
- `[CITED]` https://htmx.org/docs/ — `hx-trigger="every Xs"`, `hx-swap="outerHTML"`, post-swap `htmx.process()` re-evaluates the swapped element
- `[CITED]` https://htmx.org/docs/#installing — HTMX 2.0.10 latest stable; jsdelivr URL `https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js`; v1.x maintained for IE11 via `htmx-1-compat`
- `[CITED]` https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html — `selectinload` recommended for one-to-many; `DetachedInstanceError` after session.close on lazy-loaded relationship
- `[CITED]` https://www.python-httpx.org/advanced/transports/ — ASGITransport signature, lifespan caveat, `raise_app_exceptions=False` for inspecting 500s
- `[CITED]` https://pypi.org/pypi/jinja2/json — Jinja2 3.1.6 released 2025-03-05

### Secondary (MEDIUM confidence — single source, official but topic-specific)

- `[CITED]` https://alembic.sqlalchemy.org/en/latest/ops.html — `op.add_column` / `op.drop_column` pattern (nullable column add is non-blocking on Postgres in general; docs do not explicitly version-qualify for Postgres 15)

### Tertiary (LOW confidence — flagged for verification)

- HTMX v4 beta exists (release `v4.0.0-beta3` per GitHub releases page); the dashboard stays on **2.0.10 stable** — v4 beta is explicitly out of scope. Note that the WebFetch on the GitHub releases page partially failed; the 2.0.10 stable version is independently confirmed by htmx.org/docs/#installing.

## Project Constraints (from CLAUDE.md)

These directives constrain the plan:

1. **Tech stack pinned:** Python 3.12+, FastAPI ≥0.115, SQLAlchemy 2.x, Alembic ≥1.13, Pydantic v2 only, `uv run` shortcuts. No Celery, no aioredis, no `requests` in async contexts (use `httpx`).
2. **What NOT to Use** (from CLAUDE.md):
   - No React / Vite / node toolchain. Honoured by Jinja2 + HTMX choice.
   - No `requests` in async — irrelevant here (the dashboard does no outbound HTTP).
   - No Pydantic v1 — the new columns use plain dicts, no Pydantic touch.
   - No `AgentExecutor`, no `create_react_agent` — irrelevant (dashboard does no LLM calls).
3. **Sequential single worker (concurrency=1):** No race conditions in polling — the worker advances workflows one at a time, and the dashboard polls the latest committed state. No locking needed.
4. **`.env.example` discipline** (user memory `feedback_env_example.md`): `DASHBOARD_PORT` MUST be added to `.env.example` when introduced.
5. **GSD Workflow Enforcement**: This research was triggered by the GSD command flow; the planner must follow `/gsd-plan-phase` next.
6. **No quick-task tags in code** (user memory `feedback_no_task_id_in_code.md`): Plan tasks should NOT have the executor leave "Quick task NNNNNN-xxx" annotations in dashboard code/comments.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every package version verified live in `.venv` or against PyPI metadata
- Architecture: HIGH — all touch points read directly from source files; SQLAlchemy + FastAPI patterns verified against official docs
- Pitfalls: HIGH (1, 3, 4, 5, 8 verified empirically); MEDIUM (2 — chained exception handling is a reasoned hypothesis not directly tested); MEDIUM (6 — Pydantic JSON serialization pattern is mirrored from existing `artifact` handling); MEDIUM (7 — test fixture interaction is hypothetical until tests are written)
- HTMX polling-halt mechanic: HIGH — verified against official docs and the underlying DOM/outerHTML semantics

**Research date:** 2026-05-14
**Valid until:** 2026-06-13 (30 days; stable stack, no fast-moving deps in critical path)
