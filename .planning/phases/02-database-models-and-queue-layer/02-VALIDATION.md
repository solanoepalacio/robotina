---
phase: 2
slug: database-models-and-queue-layer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths=["tests"]`, `asyncio_mode="auto"` |
| **Quick run command** | `uv run pytest tests/ -x -q --ignore=tests/test_rq_integration.py --ignore=tests/test_db_models.py` |
| **Full suite command** | `uv run pytest tests/` |
| **Estimated runtime** | ~5 seconds (unit) / ~30 seconds (full with Docker) |

---

## Sampling Rate

- **After every task commit:** Run quick (unit-only, no Docker required)
- **After every plan wave:** Run full suite (requires Docker services up)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| QUEUE-01 | TBD | TBD | QUEUE-01 | manual | `docker compose exec redis redis-cli config get appendfsync` | ✅ docker-compose.yml | ⬜ pending |
| QUEUE-02 | TBD | TBD | QUEUE-02 | unit | `uv run pytest tests/test_queue_models.py::test_logging_worker_is_single_worker -x` | ❌ Wave 0 | ⬜ pending |
| QUEUE-03 | TBD | TBD | QUEUE-03 | unit | `uv run pytest tests/test_task_types.py -x` | ❌ Wave 0 | ⬜ pending |
| QUEUE-04 | TBD | TBD | QUEUE-04 | integration | `uv run pytest tests/test_rq_integration.py::test_job_retention -x` | ❌ Wave 0 | ⬜ pending |
| QUEUE-05 | TBD | TBD | QUEUE-05 | integration | `uv run pytest tests/test_rq_integration.py::test_failed_job_registry -x` | ❌ Wave 0 | ⬜ pending |
| QUEUE-06 | TBD | TBD | QUEUE-06 | integration | `uv run pytest tests/test_rq_integration.py::test_at_front_enqueue -x` | ❌ Wave 0 | ⬜ pending |
| QUEUE-07 | TBD | TBD | QUEUE-07 | unit | `uv run pytest tests/test_queue_models.py::test_logging_worker_emits_logs -x` | ❌ Wave 0 | ⬜ pending |
| WF-01 | TBD | TBD | WF-01 | integration | `uv run migrate && uv run pytest tests/test_db_models.py -x` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_task_types.py` — covers QUEUE-03 (all 8 model classes importable, pickle round-trips)
- [ ] `tests/test_queue_models.py` — covers QUEUE-02 (LoggingWorker structure), QUEUE-07 (log emission)
- [ ] `tests/test_rq_integration.py` — covers QUEUE-04, QUEUE-05, QUEUE-06 (requires live Redis; marked with `integration` pytest marker)
- [ ] `tests/test_db_models.py` — covers WF-01 (models importable, migration applies; requires live Postgres)
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` — add `markers = ["integration: requires Docker services"]`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Redis AOF `appendfsync always` active | QUEUE-01 | Requires running Docker service | `docker compose exec redis redis-cli config get appendfsync` → must return `always` |
| Alembic migration applies to fresh DB | WF-01 (partial) | Requires live Postgres | `docker compose up -d && uv run migrate` → must exit 0 with no errors |
