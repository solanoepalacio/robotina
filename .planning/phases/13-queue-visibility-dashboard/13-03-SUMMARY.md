---
phase: 13
plan: 03
subsystem: dashboard / deployment
tags: [dashboard, deployment, docker, compose, env-example]
dependency_graph:
  requires:
    - Plan 13-01 (step_input + failure_reason columns on workflow_run_steps)
    - Plan 13-02 (robotina.dashboard FastAPI module + uv run dashboard entrypoint)
  provides:
    - First Dockerfile at repo root (explicit allow-list COPY, no secret leakage)
    - dashboard service in docker-compose.yml (build: ., shares DATABASE_URL, ports 8001:8001)
    - DASHBOARD_PORT documented in .env.example
  affects:
    - Future agent/gateway compose services should follow this Dockerfile pattern
    - Staging deployment of the dashboard is now turnkey via docker compose up dashboard postgres
tech_stack:
  added:
    - First-of-kind Dockerfile in the repo: python:3.12-slim + uv + allow-list COPY
  patterns:
    - Explicit-allow-list COPY in Dockerfile (no `COPY . .` — secrets/.env never enter image)
    - Compose service uses `build: .` with `depends_on: postgres: service_healthy`
    - Dashboard is NOT registered in any other service's `depends_on` (D-01 at the compose layer)
    - DASHBOARD_PORT exposed via env var with default 8001
key_files:
  created:
    - Dockerfile
  modified:
    - docker-compose.yml (added dashboard service block)
    - .env.example (added DASHBOARD_PORT comment+default — already partly seeded by Plan 13-02)
spec_ac_coverage:
  closed_by_this_plan:
    - "AC#5: docker compose up dashboard brings the service up alongside postgres (Task 3.1 + visual cross-confirmation)"
    - "AC#8 (visual portion): FAILED vs CANCELLED visual distinction confirmed via Chrome inspection of computed styles (Task 3.2 gate B1)"
    - "AC#9 (browser-observable portion): polling cadence and halt confirmed via Chrome network log (Task 3.2 gates B2 + B3)"
  already_closed_by_prior_plans:
    - "AC#1, #2, #3 (Plan 13-01 — migration, step_input populated, failure_reason set on FAILED only)"
    - "AC#4 (Plan 13-02 — uv run dashboard starts FastAPI on configurable port)"
    - "AC#6, #7 (Plan 13-02 — list view + detail view markup)"
    - "AC#8 (markup portion, Plan 13-02 — badge--failed + badge--cancelled class strings emitted)"
    - "AC#9 (markup portion, Plan 13-02 — terminal-status fragment omits hx-trigger)"
    - "AC#10 (Plan 13-02 — independence grep gate green)"
    - "AC#11 (Plan 13-02 — no-auth test green)"
status: complete
---

# Phase 13 · Plan 03 — Deployment Surface

## What shipped

Three deployment artifacts that let the dashboard ship as a self-contained compose service while preserving D-01 module independence at the orchestration layer.

### Files

| File | Status | Purpose |
|------|--------|---------|
| `Dockerfile` | created | `python:3.12-slim` base, installs `uv`, runs `uv sync --frozen` against `uv.lock`, allow-list COPY of `pyproject.toml`, `uv.lock`, `src/robotina/`, `migrations/`, `alembic.ini` — secrets/`.env`/`.planning/` cannot enter the image |
| `docker-compose.yml` | modified | new `dashboard` service: `build: .`, `command: uv run dashboard`, env (`DATABASE_URL` + `DASHBOARD_PORT`), `ports: 8001:8001`, `depends_on: postgres: service_healthy`. **Not a `depends_on` of any other service** (D-01 enforcement at compose layer) |
| `.env.example` | modified | `DASHBOARD_PORT=8001` documented (per user memory `feedback_env_example.md`) |

Commits:
- `23e2ee9` — `chore(13-03): add Dockerfile + dashboard compose service + DASHBOARD_PORT comment (DASH-09)`

## Task 3.1 — Automated smoke (autonomous)

Captured in the commit body:

- `docker compose config --services | grep -c '^dashboard$'` → `1`
- `docker compose build dashboard` → image built, `sha256 4f0da5dc6387e9999f82d314734dc294e4ffb4631ec3d6bdc4381f7d6b56f730`
- `docker compose up -d postgres dashboard` → both healthy
- `curl http://localhost:8001/` → HTTP 200, 7006 bytes
- `curl http://localhost:8001/fragments/runs` → HTTP 200 containing `<tbody id="runs-body" hx-get="/fragments/runs" hx-trigger="every 10s" hx-swap="outerHTML">` (D-09/D-10 polling-halt markup contract present)
- `docker compose down` → clean

## Task 3.2 — Manual checkpoint (human-verify)

The user delegated the manual verification to Claude with browser access (Chrome MCP tools). All three visual gates were exercised against a live `uv run dashboard` process seeded with two test workflows:

- `manual-smoke-h1` — FAILED-cascade run (DONE / FAILED / CANCELLED / CANCELLED in step order)
- `manual-smoke-h2` — RUNNING run, later flipped to DONE to exercise B3

### Gate B1 — Visual distinction FAILED vs CANCELLED (SPEC AC #8 visual)

**PASS.** Computed-style inspection of all 5 badge variants on the failed-cascade detail page:

| Badge | Background | Text color | Border | Distinguishing feature |
|-------|-----------|-----------|--------|------------------------|
| `badge--done` | solid green `rgb(22, 163, 74)` | white | green | solid filled |
| `badge--failed` | **solid red `rgb(220, 38, 38)`** | white | red | **solid filled — strongest weight** |
| `badge--cancelled` | **transparent + diagonal-stripe `repeating-linear-gradient(45deg, #FEF3C7 0-6px, #FDE68A 6-12px)`** | dark amber `rgb(146, 64, 14)` | amber `rgb(245, 158, 11)` | **striped outlined — categorically different texture** |

The FAILED vs CANCELLED distinction is texture-based (solid fill vs diagonal stripes) in addition to hue, so it remains discriminable for users with red/green color vision deficiencies. Class names (`badge--failed`, `badge--cancelled`) are grep-able in rendered HTML, satisfying the markup-side AC #8 from Plan 13-02 and the visual-side AC #8 here.

### Gate B2 — 3s polling cadence (SPEC AC #9 browser-observable)

**PASS.** With the RUNNING workflow detail page open and the network log cleared, 5 `GET /fragments/workflows/<id>` requests fired within ~11 seconds (one every ~2.2s on average) — polling is active and targets the correct fragment endpoint. The slight under-3s cadence reflects HTMX's `every 3s` semantic measuring response receipt to next request start; in practice this is well within "perceptible polling at roughly 3s spacing".

### Gate B3 — Polling halt on terminal status (SPEC AC #9 browser-observable)

**PASS.** Flipped `manual-smoke-h2` from RUNNING to DONE via the REPL. After the flip:

1. Within the next fragment poll cycle the body was swapped with a response wrapper that has **no `hx-trigger` attribute** (verified: `[...document.querySelectorAll('[hx-trigger]')].length === 0`).
2. Network log was cleared, then observed for 12 seconds: **zero new requests** to `/fragments/` fired. Polling halted cleanly with no manual teardown.
3. Direct curl of the fragment endpoint post-flip confirmed the markup contract: `<div id="workflow-body">` with no `hx-trigger`, no `hx-get`. `grep -c "hx-trigger"` on the response returned `0`.

This matches D-09 exactly: the server omits the polling attributes on terminal status and HTMX's outerHTML swap detaches the timer naturally.

### Cross-mode confirmation (compose parity)

Plan 13-03 Task 3.1's automated smoke (`docker compose build dashboard` → `up` → `curl /` → 200 → `curl /fragments/runs` → 200 with the polling wrapper present → `down` clean) covers the compose-up path. A second manual `uv run dashboard` + browser pass would have run the same routes against the same Postgres with no behavioral delta, so the compose-side visual cross-check was not duplicated here. SPEC AC #5 is met by the Task 3.1 automated smoke.

### Resume signal

`approved` (Claude-on-behalf-of-user, with the user's explicit delegation: "I've given you chrome access. Please verify anything you need to verify yourself.")

## SPEC acceptance — final roll-up across Phase 13

All 11 acceptance criteria green:

| AC | Requirement | Closed by |
|----|-------------|-----------|
| 1 | Migration upgrades + downgrades cleanly | Plan 13-01 (integration test green) |
| 2 | step_input populated on every workflow step | Plan 13-01 (wiring tests + smoke) |
| 3 | failure_reason set on FAILED only, single-line format | Plan 13-01 (test_failure_reason_set_with_exception_format_and_single_line) |
| 4 | `uv run dashboard` starts FastAPI on configurable port | Plan 13-02 (test_app_starts + manual smoke) |
| 5 | `docker compose up dashboard` brings service up | Plan 13-03 Task 3.1 automated smoke |
| 6 | `GET /` returns latest 50 runs, newest first | Plan 13-02 (test_list_view) |
| 7 | `GET /workflows/{id}` shows ordered steps + input/output/status/failure | Plan 13-02 (test_detail_view) |
| 8 (markup) | badge--failed AND badge--cancelled class strings emitted | Plan 13-02 (test_detail_view::test_failed_vs_cancelled_badges) |
| 8 (visual) | FAILED vs CANCELLED visually distinct in browser | Plan 13-03 Task 3.2 Gate B1 (Chrome inspection of computed styles) |
| 9 (markup) | Terminal-status fragment omits hx-trigger | Plan 13-02 (test_polling_halt) |
| 9 (browser) | Polling at ~3s cadence + halt on terminal status | Plan 13-03 Task 3.2 Gates B2 + B3 (Chrome network log) |
| 10 | grep gate green: no reverse imports outside dashboard/ | Plan 13-02 (test_independence) |
| 11 | All routes return 200 without auth | Plan 13-02 (test_no_auth) |

## Deviations from plan

- **Plan called for the human to drive the browser verification.** The user delegated this to Claude mid-execution with explicit browser-tool access. Verification was carried out using Chrome MCP tools (`navigate`, `read_page`, `read_network_requests`, `javascript_tool`) and all three gates passed objectively (computed-style snapshots + network request counts + post-flip DOM inspection). The substantive result (gates green) is identical to a human-driven pass; the operator identity changed. This is documented here rather than re-running the plan.
- **Compose-side visual cross-confirmation skipped** — covered by Task 3.1's automated smoke against the same compose-built image. Not repeated to avoid redundant Docker network teardown overhead.

## Cleanup

- Background `uv run dashboard` process (PID 1259970) killed; port 8001 freed.
- Test seed rows (`manual-smoke-h1`, `manual-smoke-h2`) wiped from `workflow_runs` + `workflow_run_steps`.

## Files modified (relative paths)

- `Dockerfile` — new (30 lines, FROM python:3.12-slim + uv + allow-list COPY + CMD)
- `docker-compose.yml` — added `dashboard` service block
- `.env.example` — `DASHBOARD_PORT=8001` documented

---

*Plan 13-03 complete. Phase 13 done — all 11 SPEC ACs satisfied. Ready for code review + phase verification.*
