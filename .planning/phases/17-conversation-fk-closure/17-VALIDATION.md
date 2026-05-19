---
phase: 17
slug: conversation-fk-closure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-18
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (pytest-asyncio for async) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/unit/test_start_workflow_tool.py tests/test_workflow_runner.py -x -q` |
| **Full suite command** | `uv run pytest -x` |
| **Estimated runtime** | ~30 seconds (quick), ~3 min (full) |

---

## Sampling Rate

- **After every task commit:** Run quick command for affected file
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Placeholder — planner will populate per-task entries from PLAN.md. Each PLAN task must declare `<automated>` with the exact pytest command to verify its acceptance criteria, OR depend on a Wave 0 stub fixture that establishes RED state for the new column / new arg.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD-W0 | 01 | 0 | ARCH-01 | — | N/A — schema additive | unit (RED stub) | `uv run pytest tests/test_workflow_runner.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_workflow_runner.py` — extend existing fixtures to thread `conversation_id` through every `queue_workflow(...)` call. Add a stub asserting `WorkflowRun.conversation_id` is set on the persisted row (FK integration).
- [ ] `tests/unit/test_start_workflow_tool.py` — extend ~15 `StartWorkflowTool(...)` constructor sites to pass a fake `conversation_id`. Add a stub asserting the tool propagates `self.conversation_id` into the mocked `queue_workflow` call.
- [ ] `tests/conftest.py` — if a shared Conversation fixture does not already exist, add one returning a stub Conversation row with valid `(platform, chat_id, id)` so `run_task` `.one()` lookup tests can use it.
- [ ] No new framework install — pytest + pytest-asyncio already present in `pyproject.toml`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Deploy runbook D-08 (stop workers → drain RQ → TRUNCATE → migrate → restart) | ARCH-01 | Cannot automate against a real prod DB from CI; requires operator action | Document in PLAN.md and final commit message. Operator follows runbook before applying 0006. |
| `.one()` raising `NoResultFound` in `run_task` halts the job loudly | D-04 | Verifiable in unit (mock session.query) but real "fail loud" behavior in prod is an operator observation | Smoke test on staging: enqueue a `handle-incoming-message` task with a chat_id that has no Conversation row → assert RQ job lands in failed state with `NoResultFound` in traceback. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (schema column existence, FK constraint, NOT NULL, signature mismatch RED state)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter once planner has populated the per-task table

**Approval:** pending
