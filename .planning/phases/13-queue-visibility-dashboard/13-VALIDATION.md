---
phase: 13
slug: queue-visibility-dashboard
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-14
updated: 2026-05-14
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Updated by the planner after PLAN.md files were created so per-task IDs are concrete.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio 1.x (already installed) |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest -q tests/dashboard/ -m "not integration"` |
| **Full suite command** | `uv run pytest -q` |
| **Integration subset** | `uv run pytest -q -m integration` |
| **Estimated runtime** | ~30 seconds (full); ~5 seconds (dashboard non-integration only) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q tests/dashboard/ -m "not integration"` (and `tests/test_workflow_runner.py` for Plan 13-01 commits)
- **After every plan wave:** Run `uv run pytest -q` (full suite, both markers)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Concrete task IDs are now assigned. Each SPEC AC maps to exactly one automated test or one human-checkpoint observation. AC#5, AC#8 (visual portion), and AC#9 (browser-observable portion) are gated by the manual checkpoint in Plan 13-03 Task 3.2.

| AC# (SPEC) | Requirement | Plan | Task | Wave | Test Type | Automated Command | Status |
|-----|-------------|------|------|------|-----------|-------------------|--------|
| 1 | DASH-01 | 13-01 | 1.1 | 1 | integration + unit | `uv run pytest -m integration tests/test_workflow_runner.py::test_migration_0005_upgrades_and_downgrades -x && uv run pytest tests/test_workflow_runner.py::test_workflow_run_step_model_has_new_columns -x` | ⬜ pending |
| 2 | DASH-02 | 13-01 | 1.2 | 1 | integration | `uv run pytest -m integration tests/test_workflow_runner.py -k "step_input" -x` | ⬜ pending |
| 3 | DASH-03 | 13-01 | 1.2 | 1 | integration | `uv run pytest -m integration tests/test_workflow_runner.py::test_failure_reason_set_with_exception_format_and_single_line -x` | ⬜ pending |
| 4 | DASH-04 | 13-02 | 2.1 + 2.2 | 2 | unit + smoke | `uv run pytest tests/dashboard/test_app_starts.py -x` + boot smoke (verification block in 13-02) | ⬜ pending |
| 5 | DASH-09 | 13-03 | 3.1 + 3.2 | 3 | smoke + checkpoint | `docker compose config --services \| grep -c '^dashboard$'` + manual `docker compose up dashboard` + checkpoint | ⬜ pending |
| 6 | DASH-05 | 13-02 | 2.2 | 2 | unit + integration | `uv run pytest tests/dashboard/test_list_view.py -x` | ⬜ pending |
| 7 | DASH-06 | 13-02 | 2.2 | 2 | unit + integration | `uv run pytest tests/dashboard/test_detail_view.py -x` | ⬜ pending |
| 8 (markup) | DASH-07 | 13-02 | 2.2 | 2 | integration | `uv run pytest tests/dashboard/test_detail_view.py::test_failed_vs_cancelled_badges -x` | ⬜ pending |
| 8 (visual) | DASH-07 | 13-03 | 3.2 | 3 | checkpoint | manual browser eyeball — visual gate B1 | ⬜ pending |
| 9 (markup) | DASH-08 | 13-02 | 2.2 | 2 | integration | `uv run pytest tests/dashboard/test_polling_halt.py -x` | ⬜ pending |
| 9 (browser) | DASH-08 | 13-03 | 3.2 | 3 | checkpoint | manual DevTools observation — visual gates B2 + B3 | ⬜ pending |
| 10 | DASH-08 | 13-02 | 2.1 + 2.2 | 2 | unit | `uv run pytest tests/dashboard/test_independence.py -x` | ⬜ pending |
| 11 | DASH-08 | 13-02 | 2.2 | 2 | unit | `uv run pytest tests/dashboard/test_no_auth.py -x` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Plan 13-02 Task 2.1 IS the Wave 0 step for the dashboard module:

- [ ] `pyproject.toml`: `jinja2>=3.1` added to dependencies (RESEARCH.md confirmed sole missing dep)
- [ ] `src/robotina/dashboard/__init__.py`: package marker with `main()` entry, no forbidden imports
- [ ] `src/robotina/dashboard/static/htmx.min.js` + `htmx.version.txt`: HTMX 2.0.10 vendored with SHA-256
- [ ] `tests/dashboard/__init__.py`: package marker
- [ ] `tests/dashboard/conftest.py`: `client` (httpx AsyncClient via ASGITransport), `db_session` (ID-scoped cleanup per RESEARCH Pitfall 7), `make_failed_cascade_run` helper
- [ ] `tests/dashboard/test_independence.py`: grep gate (SPEC AC #10) + inward-only audit — passes from Wave 0 onwards
- [ ] `tests/dashboard/test_app_starts.py`: failing RED until Task 2.2 lands `app.py`

*Existing infrastructure (already installed): pytest + pytest-asyncio + httpx + SQLAlchemy 2.x + Alembic + FastAPI + uvicorn + python-dotenv. Only Jinja2 + HTMX (vendored) are new.*

---

## Manual-Only Verifications (Plan 13-03 Task 3.2)

All three discharged by the same checkpoint task:

| Behavior | Requirement (SPEC) | Why Manual | Where Discharged |
|----------|--------------------|------------|------------------|
| Visual distinction between FAILED and CANCELLED badges renders correctly in a real browser | Req 8 (AC #8) | Pixel-level visual differentiation can be unit-asserted via class strings, but the actual visual readability requires a browser eyeball | Plan 13-03 Task 3.2 visual gate B1 |
| Polling cadence and halt are perceptible in the network tab | Req 9 (AC #9) | Browser DevTools observation; the automated test asserts the markup contract but not human-perceptible cadence | Plan 13-03 Task 3.2 visual gates B2 + B3 |
| `docker-compose up dashboard` brings service up alongside agent stack | Req 6 (AC #5) | Compose orchestration depends on host networking + image build; CI-flaky to automate | Plan 13-03 Task 3.1 automated curl + Task 3.2 visual gate (cross-confirmation) |

---

## Validation Sign-Off

- [x] All 11 SPEC acceptance criteria have an automated or manual verification commitment
- [x] Sampling continuity: dashboard tests run on every commit; full suite on every wave
- [x] Wave 0 covers Jinja2 dependency + test scaffolding + independence grep gate (Plan 13-02 Task 2.1)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter after planner assigned concrete task IDs

**Approval:** approved (planner refined per-task IDs and flipped `nyquist_compliant: true`).
