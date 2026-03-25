---
phase: 1
slug: developer-tooling-and-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml (Wave 0 installs) |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | INFRA-01 | integration | `docker compose ps \| grep postgres` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | INFRA-01 | integration | `docker compose ps \| grep redis` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | INFRA-06 | unit | `grep "eoranged/rq-dashboard" docker-compose.yml` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | INFRA-02 | unit | `uv run pytest tests/test_pyproject.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | INFRA-05 | integration | `uv run migrate && echo OK` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 2 | INFRA-03 | integration | `uv run pytest tests/test_runner.py -x -q` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 2 | INFRA-04 | unit | `uv run pytest tests/test_pyproject.py::test_experiment_mains_importable -x -q` | ❌ W0 | ⬜ pending |
| 1-03-03 | 03 | 2 | INFRA-05 | unit | `uv run pytest tests/test_pyproject.py::test_alembic_config_valid -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — package marker
- [ ] `tests/conftest.py` — shared fixtures (docker compose health, db connection)
- [ ] `tests/test_pyproject.py` — validates pyproject.toml structure (scripts, packages)
- [ ] `pytest` and `pytest-asyncio` added to dev dependencies

*Wave 0 must be created before any implementation tasks run.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| RQ Dashboard UI accessible in browser | INFRA-06 | Browser required | Navigate to http://localhost:9181, verify jobs page loads |
| Redis AOF `appendfsync always` active | INFRA-01 | Requires docker exec into container | `docker exec robotina-redis redis-cli CONFIG GET appendfsync` → must return `always` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
