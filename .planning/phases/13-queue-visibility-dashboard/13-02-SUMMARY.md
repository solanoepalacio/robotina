---
phase: 13
plan: 02
subsystem: dashboard / fastapi
tags: [dashboard, fastapi, jinja2, htmx, independence, tdd]
dependency_graph:
  requires:
    - Plan 13-01 (step_input + failure_reason columns on workflow_run_steps)
  provides:
    - robotina.dashboard.app FastAPI instance with 4 routes
    - robotina.dashboard.queries (list_recent_runs, get_workflow_with_steps)
    - tests/dashboard/test_independence.py — load-bearing D-01 grep gate
  affects:
    - Plan 13-03 will add the docker-compose service entry for staging deployment
tech_stack:
  added:
    - jinja2>=3.1 (3.1.6 installed) — server-side templating
    - HTMX 2.0.10 vendored at src/robotina/dashboard/static/htmx.min.js
      (SHA-256 71ea67185bfa8c98c39d31717c6fce5d852370fcdfd129db4543774d3145c0de)
  patterns:
    - FastAPI + Jinja2Templates with Path(__file__).parent-relative template
      directory (CWD-independent — works under uv run and pytest)
    - sqlalchemy.orm.selectinload(WorkflowRun.steps) for detail view
      (RESEARCH Pitfall 4 — prevents DetachedInstanceError)
    - In-Python sort by step_order (RESEARCH Pitfall 5 — relationship has
      no order_by)
    - HTMX outerHTML swap with attribute-absent hx-trigger for polling halt
      (D-09 — the load-bearing AC #9 markup contract)
    - httpx.ASGITransport in pytest fixtures (no live uvicorn needed)
    - ID-scoped DB cleanup in conftest (RESEARCH Pitfall 7 — never
      bulk-delete workflow_run_steps)
key_files:
  created:
    - src/robotina/dashboard/__init__.py
    - src/robotina/dashboard/app.py
    - src/robotina/dashboard/deps.py
    - src/robotina/dashboard/queries.py
    - src/robotina/dashboard/templates/base.html
    - src/robotina/dashboard/templates/index.html
    - src/robotina/dashboard/templates/workflow.html
    - src/robotina/dashboard/templates/_run_rows.html
    - src/robotina/dashboard/templates/_workflow_body.html
    - src/robotina/dashboard/templates/_status_badge.html
    - src/robotina/dashboard/static/dashboard.css
    - src/robotina/dashboard/static/htmx.min.js
    - src/robotina/dashboard/static/htmx.version.txt
    - tests/dashboard/__init__.py
    - tests/dashboard/conftest.py
    - tests/dashboard/test_independence.py
    - tests/dashboard/test_app_starts.py
    - tests/dashboard/test_list_view.py
    - tests/dashboard/test_detail_view.py
    - tests/dashboard/test_polling_halt.py
    - tests/dashboard/test_no_auth.py
  modified:
    - pyproject.toml (jinja2>=3.1 dep + dashboard script entry)
    - .env.example (DASHBOARD_PORT=8001)
decisions:
  - "Phase 13-02: HTMX vendored at 2.0.10 with SHA-256 audit trail in htmx.version.txt; no CDN runtime per D-13"
  - "Phase 13-02: Polling-halt implemented as attribute-absent re-render on the wrapper element with hx-swap='outerHTML' — the wrapper itself gets replaced and the new one carries no hx-trigger, so HTMX's per-element timer ends naturally (D-09 / RESEARCH Pitfall 3)"
  - "Phase 13-02: D-01 independence enforced by tests/dashboard/test_independence.py (grep + inward-only audit) — runs as a normal pytest assertion, cannot be silently bypassed"
  - "Phase 13-02: Template + static directories resolved via Path(__file__).parent (NOT string paths relative to CWD) — fixes fragility under pytest collection and uv run dashboard from arbitrary directories"
metrics:
  duration: "~6min"
  completed_date: "2026-05-14"
  commits: 3
  tasks: 2
  files_modified: 2
  files_created: 21
---

# Phase 13 Plan 02: Queue Visibility Dashboard — FastAPI Module Summary

**One-liner:** Built `src/robotina/dashboard/` as a fully independent FastAPI + Jinja2 + vendored-HTMX read-only debugger over the persistence layer landed in Plan 13-01 — four routes, six templates, hand-written CSS, polling-halt by attribute-absent re-render, and a grep gate that guarantees no other `robotina.*` module ever imports from the dashboard.

## What Landed

### Module structure (independent — D-01 grep gate green)

```
src/robotina/dashboard/
├── __init__.py              # main() — loads .env, runs uvicorn on DASHBOARD_PORT (default 8001)
├── app.py                   # FastAPI() + 4 routes + /static mount
├── deps.py                  # get_db() yield-dep wrapping the existing SessionLocal()
├── queries.py               # list_recent_runs(50); get_workflow_with_steps(id) + selectinload
├── templates/
│   ├── base.html            # <html lang="en"> + sticky page header + static asset links
│   ├── index.html           # extends base; empty-state ↔ <table> branch
│   ├── workflow.html        # extends base; header card + included body partial
│   ├── _run_rows.html       # polling target — always has hx-trigger="every 10s" (D-10)
│   ├── _workflow_body.html  # polling target — omits hx-trigger when terminal (D-09)
│   └── _status_badge.html   # macro: <span class="badge badge--{lower}">
└── static/
    ├── dashboard.css        # hand-written, no Tailwind / no Pico; all CSS tokens on :root
    ├── htmx.min.js          # vendored HTMX 2.0.10
    └── htmx.version.txt     # 2.0.10 + SHA-256 71ea67…c0de (audit trail)
```

### HTMX vendoring (audit trail per UI-SPEC §Registry Safety)

- **Version:** `2.0.10`
- **SHA-256:** `71ea67185bfa8c98c39d31717c6fce5d852370fcdfd129db4543774d3145c0de`
- **Recorded in:** `src/robotina/dashboard/static/htmx.version.txt` (two-line file: version on line 1, sha256sum output on line 2).
- **Source:** `https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js` (downloaded once at vendoring time; served at `/static/htmx.min.js` from disk in production).

### Independence (D-01 — USER-LOCKED) — verified green

```bash
grep -rE "from robotina\.dashboard|import robotina\.dashboard" src/robotina/ --exclude-dir=dashboard
# exit 1 — zero matches
```

Dashboard inward imports verified by `test_dashboard_imports_only_allowed_robotina_modules` (forbidden-prefix audit on every `.py` under `src/robotina/dashboard/`). Allowed `robotina.*` imports inside dashboard:

- `robotina.db.SessionLocal` (DB session factory — only DB entry)
- `robotina.queue.models.{WorkflowRun, WorkflowStatus}` (ORM rows)
- `robotina.dashboard.*` (intra-package — fine)

No other `robotina.*` imports. The dashboard is NOT registered in `src/robotina/all.py` (independence rule); it is launched independently via `uv run dashboard` or its compose service (the latter is Plan 13-03 territory).

## Three Commits Landed (RED-GREEN sequence)

| #   | Hash      | Subject                                                                                          |
| --- | --------- | ------------------------------------------------------------------------------------------------ |
| 1   | `e555426` | test(13-02): scaffold tests/dashboard + vendor htmx 2.0.10 + add jinja2 dep (DASH-04)            |
| 2   | `301b41b` | test(13-02): failing dashboard route + template tests (DASH-05..DASH-08)                         |
| 3   | `6da1c97` | feat(13-02): dashboard module — FastAPI app + 6 templates + CSS + 4 routes (DASH-04..DASH-08)    |

Commit 1 is the Wave-0 scaffold (Task 2.1 — independence gate green from the start; app_starts RED). Commit 2 adds the remaining 13 RED tests (Task 2.2 test-first phase). Commit 3 is the GREEN implementation that turns all 13 + the 2 from commit 1 to PASS.

## Tests

### Added (this plan) — 15 tests across 6 files

| Test file                                              | Tests | Markers                                          | Purpose                                                                                                |
| ------------------------------------------------------ | ----- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| `tests/dashboard/test_independence.py`                 | 2     | unit                                             | SPEC AC #10 grep gate + D-01 inward-only import audit                                                  |
| `tests/dashboard/test_app_starts.py`                   | 1     | unit                                             | DASH-04 / SPEC AC #4 — FastAPI app object imports cleanly                                              |
| `tests/dashboard/test_list_view.py`                    | 5     | mixed (2 unit, 3 `@integration`)                 | SPEC AC #6 — empty state, newest-first ordering, link to detail, fragments/runs partial                |
| `tests/dashboard/test_detail_view.py`                  | 3     | mixed (1 unit, 2 `@integration`)                 | SPEC AC #7 + AC #8 — 404 on miss, failed-cascade renders ordered steps, FAILED-vs-CANCELLED badges     |
| `tests/dashboard/test_polling_halt.py`                 | 3     | `@integration`                                   | SPEC AC #9 / D-09 — terminal fragment has NO hx-trigger; running has every 3s; list always every 10s   |
| `tests/dashboard/test_no_auth.py`                      | 1     | unit                                             | SPEC AC #11 — no 401/403 on any route                                                                  |

### Test results

```
DATABASE_URL=postgresql://robotina:robotina@localhost:5433/robotina

uv run pytest tests/dashboard/ -m "not integration"   → 7 passed
uv run pytest tests/dashboard/ -m integration         → 8 passed
uv run pytest tests/dashboard/                        → 15 passed total
uv run pytest tests/                                  → 196 passed, 6 failed
```

The 6 failures are pre-existing and documented in Plan 13-01's SUMMARY.md under "Deferred Issues" — they reproduce against the pre-plan state and are unrelated to this plan:

- `tests/test_gateway.py::test_send_message_persists`
- 4 × `tests/unit/test_agent_middleware.py::test_log_*`
- `tests/unit/test_observability.py::test__setup_langwatch_nonfatal_when_missing_credentials`

Zero regressions introduced by Plan 13-02.

### Manual smoke via ASGI transport (verification block in plan)

```python
DATABASE_URL=... uv run python -c "<see plan §verification>"
```

Result:
- `list_status: 200`
- `detail_404_status: 404`
- `runs_fragment_status: 200`
- `has_hx_trigger_10s: True`

## Acceptance Criteria (SPEC §"Acceptance Criteria")

- [x] **AC #4** `uv run dashboard` starts the FastAPI app and serves on a configurable port (default 8001 from `DASHBOARD_PORT`). Verified: `uv run python -c "from robotina.dashboard import main; print(main)"` resolves the callable; the `[project.scripts]` entry is present; `app` object imports cleanly per `test_app_object_exists`.
- [ ] **AC #5** `docker-compose up dashboard` brings the dashboard service up. **Deferred to Plan 13-03** (compose service entry + Dockerfile + manual deployment smoke).
- [x] **AC #6** `GET /` returns HTML listing the latest 50 workflow runs ordered by `created_at DESC`. Verified by `test_list_view_renders_rows_newest_first` (newest-first ordering) and `test_index_template_renders_empty_state_directly` (empty state).
- [x] **AC #7** `GET /workflows/{id}` returns HTML with workflow header + ordered steps showing input/output/failure/timestamps. Verified by `test_detail_view_renders_failed_cascade` (DONE → FAILED → CANCELLED → CANCELLED in `step_order`).
- [x] **AC #8** On a deliberately-failed workflow, the detail view renders distinct badges. Verified: both `badge--failed` and `badge--cancelled` class strings appear in the response and are styled distinctly (solid red vs. diagonal-stripe amber per UI-SPEC §Color).
- [x] **AC #9** List view polls every 10s; detail view every 3s; polling halts on terminal status. Verified by `test_detail_fragment_terminal_has_no_hx_trigger` (the load-bearing assertion `'hx-trigger' not in response.text`), `test_detail_fragment_running_has_hx_trigger`, and `test_list_fragment_always_has_hx_trigger`.
- [x] **AC #10** Grep gate returns zero matches. Verified by `test_no_reverse_imports_from_dashboard` and a manual `grep` run.
- [x] **AC #11** No authentication required on any route. Verified by `test_all_routes_return_200_or_404_without_auth_headers` (asserts `status_code not in (401, 403)`).

## Deviations from Plan

### 1. [Rule 1 — Bug] Template + static dirs resolved via `Path(__file__).parent`, not string CWD paths

- **Found during:** Task 2.2 Step 3 (writing `app.py`).
- **Issue:** RESEARCH §"Code Examples / Example 1" set `Jinja2Templates(directory="src/robotina/dashboard/templates")` as a string relative to CWD. That string would resolve incorrectly under `uv run dashboard` invoked from a parent directory AND under pytest (which sets CWD to the repo root only by convention, not by guarantee).
- **Fix:** Use `_HERE = Path(__file__).parent` and pass `str(_HERE / "templates")` to `Jinja2Templates` and `str(_HERE / "static")` to `StaticFiles`. This is the adaptation explicitly called out in the plan `<behavior>` block; documented here for the record.
- **Files modified:** `src/robotina/dashboard/app.py`.
- **Commit:** `6da1c97`.

### 2. [Rule 2 — Missing critical functionality] `DASHBOARD_PORT` added to `.env.example`

- **Found during:** Pre-commit checklist.
- **Issue:** Plan 13-02 introduces a new env var (`DASHBOARD_PORT`, read in `dashboard.__init__.main()`). User memory directive `feedback_env_example.md` ("Always update .env.example") makes adding it a correctness requirement.
- **Fix:** Appended `DASHBOARD_PORT=8001` to `.env.example` under a new `# Dashboard (Phase 13+)` section.
- **Files modified:** `.env.example`.
- **Commit:** `6da1c97` (bundled with the GREEN implementation).

No other deviations. The plan's blueprints (RESEARCH §"Code Examples" + UI-SPEC §"Component Contracts") were followed verbatim apart from the two items above.

## Notes Preserved for Plan 13-03

- The dashboard FastAPI app is fully self-contained; mounting into compose only requires reading `DATABASE_URL` (already in the same env as gateway/agent) and exposing port 8001.
- The dashboard does NOT depend on Redis. It reads exclusively from Postgres via `SessionLocal()`. The compose service should NOT add a `depends_on: redis` clause.
- `htmx.min.js` and `dashboard.css` are served from `/static` by `StaticFiles` — no separate static-asset server needed in the compose stack.
- The plan's success criterion #9 (`uv run dashboard` end-to-end boot smoke) was deferred to Plan 13-03's manual deployment smoke step because the staging compose stack is the realistic environment for it.

## Threat Flags

None — Plan 13-02 introduces only the surface defined in the SPEC `<threat_model>` (T-13-01 through T-13-06). All STRIDE-mapped threats either accept (T-13-01, T-13-05) or mitigate (T-13-02 via `HTTPException(404)`, T-13-03 via Jinja2 autoescape + never `|safe` on user data, T-13-04 via 50-row cap + polling halt, T-13-06 via SHA-256 audit trail) — implemented as specified.

## Self-Check

- **Files claimed to exist:** All 21 files in `key_files.created` verified via `ls`; all 2 modified files in `key_files.modified` verified via `git diff --stat HEAD~3..HEAD`.
- **Commit hashes claimed:** `e555426`, `301b41b`, `6da1c97` — all present in `git log --oneline -5`.
- **Tests claimed green:** `uv run pytest tests/dashboard/` reports 15/15 passed.
- **Independence grep gate:** `grep -rE "from robotina\\.dashboard|import robotina\\.dashboard" src/robotina/ --exclude-dir=dashboard` returns exit code 1 (zero matches).
- **HTMX SHA-256 claimed:** Matches the second line of `htmx.version.txt`.

## Self-Check: PASSED
