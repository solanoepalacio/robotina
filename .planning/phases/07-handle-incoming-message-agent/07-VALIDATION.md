---
phase: 7
slug: handle-incoming-message-agent
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-27
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/unit/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 0 | ROBOT-02 | unit | `uv run pytest tests/unit/test_household_manager_api_tool.py -v 2>&1 \| tail -20` | ❌ W0 | ⬜ pending |
| 7-01-02 | 01 | 0 | ROBOT-03 | unit | `uv run pytest tests/unit/test_queue_tool.py -v 2>&1 \| tail -20` | ❌ W0 | ⬜ pending |
| 7-02-01 | 02 | 1 | ROBOT-02 | unit | `uv run pytest tests/unit/test_household_manager_api_tool.py -v 2>&1 \| tail -20` | ❌ W0 | ⬜ pending |
| 7-02-02 | 02 | 1 | ROBOT-03 | unit | `uv run pytest tests/unit/test_queue_tool.py tests/unit/test_household_manager_api_tool.py -v 2>&1 \| tail -20` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_household_manager_api_tool.py` — stubs for ROBOT-02 (Plan 01, Task 1)
- [ ] `tests/unit/test_queue_tool.py` — stubs for ROBOT-03 (Plan 01, Task 2)

*Wave 0 is Plan 01. Wave 0 files are created during Plan 01 execution — not pre-existing.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `household-manager` skill no longer contains auth instructions | ROBOT-07 | File content inspection — no runtime behavior | Read `robotina/skills/household-manager/shared.md`; confirm no Authentication section and no 401/403 rows in error table |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
