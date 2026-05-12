---
phase: 5
slug: task-runner-and-workflow-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | WF-02 | unit | `uv run pytest tests/test_workflows.py -x -q` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | WF-03 | unit | `uv run pytest tests/test_workflows.py -x -q` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 2 | WF-04 | integration | `uv run pytest tests/test_workflow_runner.py -x -q` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 2 | WF-05 | integration | `uv run pytest tests/test_workflow_runner.py -x -q` | ❌ W0 | ⬜ pending |
| 05-02-03 | 02 | 2 | WF-06 | integration | `uv run pytest tests/test_workflow_runner.py -x -q` | ❌ W0 | ⬜ pending |
| 05-02-04 | 02 | 2 | WF-07 | integration | `uv run pytest tests/test_workflow_runner.py -x -q` | ❌ W0 | ⬜ pending |
| 05-02-05 | 02 | 2 | WF-08 | integration | `uv run pytest tests/test_workflow_runner.py -x -q` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 2 | WF-09 | integration | `uv run pytest tests/test_workflow_runner.py -x -q` | ❌ W0 | ⬜ pending |
| 05-04-01 | 04 | 3 | QUEUE-01 | integration | `uv run pytest tests/test_start_workflow_tool.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_workflows.py` — stubs for WF-02, WF-03
- [ ] `tests/test_workflow_runner.py` — stubs for WF-04, WF-05, WF-06, WF-07, WF-08, WF-09
- [ ] `tests/test_start_workflow_tool.py` — stubs for QUEUE-01

*Existing infrastructure (conftest.py, docker-compose, test_rq_integration.py) covers test harness setup.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end hello-world workflow visible in RQ dashboard | WF-02 | Requires running worker + rq-dashboard UI | Start worker, enqueue hello-world, open rq-dashboard at localhost:9181 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
