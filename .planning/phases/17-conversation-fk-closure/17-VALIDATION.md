---
phase: 17
slug: conversation-fk-closure
status: ready
nyquist_compliant: true
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

- **After every task commit:** Run the task's `<automated>` block (per-task verify commands listed below).
- **After every plan wave:** Run quick command for affected files.
- **Before `/gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 17-01-1 | 01 | 0 | ARCH-01 | — | N/A (schema additive) | unit (RED) | `uv run pytest tests/test_workflow_runner.py::test_workflow_run_has_conversation_id_column tests/test_workflow_runner.py::test_workflow_run_has_outcome_column tests/test_workflow_runner.py::test_queue_workflow_persists_conversation_id tests/test_workflow_runner.py::test_queue_workflow_requires_conversation_id -q` | ❌ W0 (will turn ✅ after Wave 2) | ⬜ pending |
| 17-01-2 | 01 | 0 | ARCH-01, ARCH-05 | — | ARCH-05 deprecation window preserved | unit (RED) | `uv run pytest tests/unit/test_start_workflow_tool.py::test_constructor_requires_conversation_id_no_default tests/unit/test_agent_runner.py::test_run_task_raises_when_conversation_missing tests/test_task_types.py::test_workflow_outcome_stub -q` | ❌ W0 (will turn ✅ after Wave 2) | ⬜ pending |
| 17-02-1 | 02 | 1 | ARCH-01 | — | FK NOT NULL enforced at DB layer | integration (schema introspection) | `uv run pytest tests/test_workflow_runner.py::test_workflow_run_has_conversation_id_column tests/test_workflow_runner.py::test_workflow_run_has_outcome_column -q` | ✅ after Task 1.1 (RED→GREEN) | ⬜ pending |
| 17-02-2 | 02 | 1 | ARCH-01 | — | ORM model in sync with schema | unit | `uv run pytest tests/test_workflow_runner.py::test_workflow_run_has_conversation_id_column tests/test_workflow_runner.py::test_workflow_run_has_outcome_column tests/test_workflow_runner.py::test_workflow_run_step_model_has_new_columns -q` | ✅ | ⬜ pending |
| 17-02-3 | 02 | 1 | ARCH-01 | — | WorkflowOutcome stub importable from canonical path | unit | `uv run pytest tests/test_task_types.py::test_workflow_outcome_stub -q` | ✅ | ⬜ pending |
| 17-03-1 | 03 | 2 | ARCH-01 | — | queue_workflow rejects missing conversation_id at signature boundary | unit | `uv run pytest tests/test_workflow_runner.py::test_queue_workflow_persists_conversation_id tests/test_workflow_runner.py::test_queue_workflow_requires_conversation_id -q` | ✅ | ⬜ pending |
| 17-03-2 | 03 | 2 | ARCH-01, ARCH-05 | — | StartWorkflowTool propagates conversation_id; reply_context write preserved | unit | `uv run pytest tests/unit/test_start_workflow_tool.py -q` | ✅ | ⬜ pending |
| 17-03-3 | 03 | 2 | ARCH-01 | — | run_task `.one()` lookup raises NoResultFound on missing Conversation (fail-loud) | unit | `uv run pytest tests/unit/test_agent_runner.py -q` | ✅ | ⬜ pending |
| 17-03-4 | 03 | 2 | ARCH-01 | — | Existing queue_workflow callers updated atomically (Pitfall 3) | unit | `uv run pytest tests/test_workflow_runner.py::test_step_input_persisted_on_first_enqueue tests/test_workflow_runner.py::test_queue_workflow_rejects_empty_household_id tests/test_workflow_runner.py::test_queue_workflow_rejects_whitespace_household_id -q` | ✅ | ⬜ pending |
| 17-04-1 | 04 | 3 | ARCH-01 | — | REQUIREMENTS.md + ROADMAP wording aligned with single-revision implementation | doc grep | `grep -c "single Alembic revision" .planning/REQUIREMENTS.md && grep -c "single Alembic revision 0006" .planning/ROADMAP.md` | ✅ | ⬜ pending |
| 17-04-2 | 04 | 3 | ARCH-01 | — | Deploy runbook discoverable in phase folder | doc presence | `test -f .planning/phases/17-conversation-fk-closure/17-RUNBOOK.md && grep -q "TRUNCATE workflow_runs" .planning/phases/17-conversation-fk-closure/17-RUNBOOK.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Wave 0 RED-then-GREEN flow:** Tasks 17-01-1 and 17-01-2 deliberately FAIL after Wave 0 (RED) because the columns / fields they assert don't yet exist. Wave 1 (schema + model + stub) flips the schema-introspection tests GREEN; Wave 2 (signatures + wire-up) flips the remaining ctor / lookup tests GREEN. The full suite is GREEN after Wave 2; Wave 3 lands only documentation (no code changes that could break tests).

---

## Wave 0 Requirements

- [x] `tests/test_workflow_runner.py` — extended fixtures thread `conversation_id` through every `queue_workflow(...)` call (Task 17-01-1).
- [x] `tests/unit/test_start_workflow_tool.py` — ~15 `StartWorkflowTool(...)` constructor sites updated with `conversation_id="conv-1"` (Task 17-01-2 + 17-03-2 bulk update).
- [x] `tests/conftest.py` — shared Conversation fixture (added or reused per existing patterns).
- [x] `tests/test_task_types.py` — WorkflowOutcome stub test stub (Task 17-01-2).
- [x] No new framework install — pytest + pytest-asyncio already in `pyproject.toml`.

*(Boxes are pre-checked because the plans schedule these as Wave 0 deliverables; `wave_0_complete` flips to true once the Wave 0 commit lands.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Deploy runbook D-08 (stop workers → drain RQ → TRUNCATE → migrate → restart) | ARCH-01 | Cannot automate against the live prod DB from CI; requires operator action | Operator follows `.planning/phases/17-conversation-fk-closure/17-RUNBOOK.md` against the live DB before flipping ARCH-01 to `[x]`. |
| `.one()` raising `NoResultFound` in production halts the job loudly | ARCH-01 (D-04) | Verifiable in unit (mock session.query) but real "fail loud" behavior requires staging | Smoke test on staging: enqueue a `handle-incoming-message` task with a chat_id that has no Conversation row → assert RQ job lands in failed state with `NoResultFound` in traceback. |
| Smoke test post-migration | ARCH-01 | Requires a live Telegram message round-trip | Send "hola" via Telegram, confirm a new `WorkflowRun` row exists with `conversation_id` matching the upserted Conversation row and `outcome` NULL. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every task in every plan has a `<automated>` block)
- [x] Wave 0 covers all MISSING references (column existence, FK constraint, NOT NULL, ctor field, signature mismatch RED state, WorkflowOutcome stub, ARCH-05 regression)
- [x] No watch-mode flags
- [x] Feedback latency < 30s (quick suite scope is two test files; full suite < 3 min)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-18
