---
phase: 13
slug: queue-visibility-dashboard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-14
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio 1.x (already installed) |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest -q tests/dashboard/ -m "not integration"` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~30 seconds (full); ~5 seconds (dashboard non-integration only) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q tests/dashboard/ -m "not integration"`
- **After every plan wave:** Run `uv run pytest -q` (full suite)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Concrete task IDs are assigned by the planner. This map seeds the verification commitments per SPEC AC.

| AC# | Plan | Wave | Requirement (SPEC) | Test Type | Automated Command | Status |
|-----|------|------|--------------------|-----------|-------------------|--------|
| 1 | 01 | 1 | Migration upgrade/downgrade adds `step_input` + `failure_reason` | integration | `uv run pytest -q -m integration tests/dashboard/test_migration.py` | ⬜ pending |
| 2 | 01 | 1 | After workflow run, every step row has `step_input` populated | integration | `uv run pytest -q -m integration tests/dashboard/test_persistence.py::test_step_input_populated` | ⬜ pending |
| 3 | 01 | 1 | Failed step has `failure_reason` as `"ExceptionClass: message"`; non-failed = NULL | integration | `uv run pytest -q -m integration tests/dashboard/test_persistence.py::test_failure_reason_only_on_failed` | ⬜ pending |
| 4 | 02 | 1 | `uv run dashboard` starts FastAPI on configurable port | manual | smoke: `uv run dashboard` + curl `http://localhost:8001/` returns 200 | ⬜ pending |
| 5 | 02 | 2 | `docker-compose up dashboard` brings service up sharing `DATABASE_URL` | manual | smoke: compose-up then `curl http://localhost:8001/` returns 200 | ⬜ pending |
| 6 | 02 | 1 | `GET /` returns latest 50 runs, newest first, each row links to detail | unit + integration | `uv run pytest -q tests/dashboard/test_list_view.py` | ⬜ pending |
| 7 | 02 | 1 | `GET /workflows/{id}` shows ordered steps with input/output/status/failure | unit + integration | `uv run pytest -q tests/dashboard/test_detail_view.py` | ⬜ pending |
| 8 | 02 | 1 | FAILED vs CANCELLED rendered visually distinct (grep-able class strings) | unit | `uv run pytest -q tests/dashboard/test_detail_view.py::test_failed_vs_cancelled_badges` | ⬜ pending |
| 9 | 02 | 1 | List polls 10s, detail polls 3s; detail halts on terminal status | unit | `uv run pytest -q tests/dashboard/test_polling_halt.py` | ⬜ pending |
| 10 | 02 | 2 | Grep enforcement: no `from robotina.dashboard` or `import robotina.dashboard` outside `src/robotina/dashboard/` | unit | `uv run pytest -q tests/dashboard/test_independence.py::test_no_reverse_imports` | ⬜ pending |
| 11 | 02 | 1 | All dashboard routes return 200 without auth (matches internal-only) | unit | `uv run pytest -q tests/dashboard/test_no_auth.py` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/dashboard/__init__.py` — package marker
- [ ] `tests/dashboard/conftest.py` — fixtures: `session_factory`, `app_client` (httpx AsyncClient via ASGITransport), `make_workflow_run` (helper to insert a `WorkflowRun` with N `WorkflowRunStep` rows including failure + cancelled cascade), DB cleanup-by-UUID helper (NOT bulk delete)
- [ ] `Jinja2 >= 3.1` added to `pyproject.toml` dependencies (only missing dep per RESEARCH.md)
- [ ] `tests/dashboard/test_independence.py::test_no_reverse_imports` — single grep-based test asserting the SPEC AC

*Existing infrastructure: pytest + pytest-asyncio + httpx + SQLAlchemy 2.x + Alembic + FastAPI are all already installed. Only Jinja2 + HTMX (vendored) are new.*

---

## Manual-Only Verifications

| Behavior | Requirement (SPEC) | Why Manual | Test Instructions |
|----------|--------------------|------------|-------------------|
| Visual distinction between FAILED and CANCELLED badges renders correctly in a real browser | Req 8 | Pixel-level visual differentiation can be unit-asserted via class strings, but the actual visual readability requires a browser eyeball | Start `uv run dashboard`, navigate to a workflow with a failed step + cancelled cascade, confirm at-a-glance FAILED (red) vs CANCELLED (amber stripes) discrimination |
| Polling cadence and halt are perceptible in the network tab | Req 9 | Browser dev tools observation; the automated test asserts the markup contract but not human-perceptible cadence | Start `uv run dashboard`, open a workflow detail page in browser with DevTools → Network, confirm `every 3s` GET on the fragment URL, confirm requests stop within ~3s of the workflow transitioning to DONE/FAILED |
| `docker-compose up dashboard` brings service up alongside agent stack | Req 6 | Compose orchestration depends on host networking + image build; CI-flaky to automate | Run `docker-compose up dashboard postgres`, curl `http://localhost:8001/` from host, confirm 200 |

---

## Validation Sign-Off

- [ ] All 11 SPEC acceptance criteria have an automated or manual verification commitment
- [ ] Sampling continuity: dashboard tests run on every commit; full suite on every wave
- [ ] Wave 0 covers Jinja2 dependency + test scaffolding + independence grep gate
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter after planner assigns concrete task IDs and updates this map

**Approval:** pending — planner will refine the per-task IDs and flip `nyquist_compliant: true` once mapping is complete.
