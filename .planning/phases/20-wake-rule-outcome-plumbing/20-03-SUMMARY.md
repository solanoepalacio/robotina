---
phase: 20-wake-rule-outcome-plumbing
plan: 03
subsystem: queue/workflow_runner
tags: [wake-rule, idempotency, atomicity, D-04, D-05]
requires: [20-01, 20-02]
provides: [_check_and_dispatch_wake helper, on_step_complete wake wiring, on_step_failed wake wiring + dead-letter fallback gating]
affects: [src/robotina/queue/workflow_runner.py, tests/test_workflow_runner.py, tests/queue/test_wake_dispatch.py]
tech-stack:
  patterns: [UPDATE-RETURNING idempotency guard, pre-assigned rq_job_id, same-session atomic commit]
key-files:
  created:
    - tests/queue/test_wake_dispatch.py
  modified:
    - src/robotina/queue/workflow_runner.py
    - tests/test_workflow_runner.py
decisions:
  - "D-04 helper: _check_and_dispatch_wake added as single private helper at module scope; called from BOTH on_step_complete (final-DONE) AND on_step_failed (FAILED)"
  - "D-05 dead-letter: existing send-notification block preserved as fallback, gated on wake-helper exception — runs only when wake-enqueue raises"
  - "PITFALL 2 atomicity: removed the eager session.commit() at line 496 of on_step_failed; happy path now commits ONCE after the helper call so FAILED status + new invocation row land atomically"
  - "PITFALL 1 idempotency: UPDATE-RETURNING on wake_dispatched_at IS NULL guarantees single-fire across concurrent / repeated callers"
  - "PITFALL 11 transactional advancement: rq_job_id pre-assigned on the new RobotinaInvocation BEFORE enqueue; reconciler (Plan 20-05) closes the worker-crash-between-commit-and-enqueue gap"
metrics:
  tasks_completed: 4
  files_modified: 2
  files_created: 1
  tests_added: 10
---

# Phase 20 Plan 03: Wake-rule plumbing Summary

Wire the wake-rule control loop on top of Phase 18's dormant
`RobotinaInvocation` schema. Single helper, two call sites, three idempotency
layers; dead-letter preserved as fallback.

## What changed

### `src/robotina/queue/workflow_runner.py`

1. **Added `_check_and_dispatch_wake(invocation_id, session, queue)`** at
   module scope (immediately above `queue_workflow`).
   - Early-return when `invocation_id is None`.
   - Sibling SELECT on `WorkflowRun.triggered_by_invocation_id`; early-return
     when no siblings or any sibling is non-terminal.
   - `UPDATE robotina_invocations SET wake_dispatched_at = NOW() WHERE id = :iid
     AND wake_dispatched_at IS NULL RETURNING id` — idempotency guard.
   - `AddRecipeOutcome.model_validate(run.outcome)` per sibling; bundled into
     `WorkflowOutcomeSummary` entries.
   - Pre-assigns `rq_job_id = str(uuid.uuid4())` on the new
     `RobotinaInvocation(trigger=WORKFLOW_COMPLETION, ...)`; `session.add` +
     `session.flush` (NO commit — caller commits).
   - `queue.enqueue(...)` with `job_id=<pre>` + meta carrying
     `task_type=handle-incoming-message` + `invocation_id=new_inv.id`.
   - `queue=None` short-circuits after the flush, leaving the row for the
     startup reconciler.

2. **Wired `on_step_complete` final-DONE branch:** wake-helper call inserted
   between `run.status = WorkflowStatus.DONE` and the existing
   `session.commit()`. Status flip + new invocation row land atomically.

3. **Restructured `on_step_failed`:** removed the eager `session.commit()` at
   the old line 496. New shape:
   ```
   run.status = FAILED
   try:
       _check_and_dispatch_wake(...)
       session.commit()      # SINGLE commit on happy path (Pitfall 2)
       wake_branch_ok = True
   except Exception:
       session.rollback()
       # re-mark step FAILED + failure_reason + cancel pending + run FAILED
       session.commit()      # second commit ONLY on except path
   logger.error(...)
   if wake_branch_ok: return
   if queue is None: return
   # existing dead-letter send-notification body — unchanged
   ```
   - Dead-letter notify now runs **only** on wake-helper exception (D-05).
     On the happy path Phase 21+ will compose a reply via the new wake
     invocation.

### `tests/queue/test_wake_dispatch.py` (NEW — 10 tests)

D-17 unit tests (9) and the D-18 integration test (1):

| # | Test | Asserts |
|---|------|---------|
| 1 | `test_wake_fires_on_single_done_workflow` | wake row created with `rq_job_id` set AND matching `enqueued[0][1]["job_id"]` (two separate asserts) |
| 2 | `test_wake_fires_when_all_three_done` | 3 sibling DONE → exactly one wake invocation |
| 3 | `test_wake_skips_on_partial` | 2 DONE + 1 PENDING → no wake, no `wake_dispatched_at` |
| 4 | `test_wake_fires_on_failed` | FAILED workflow → wake fires (parity with DONE) |
| 5 | `test_wake_idempotent` | second helper call → only ONE invocation, ONE enqueue |
| 6 | `test_wake_queue_none_skips_enqueue` | row inserted + `wake_dispatched_at` set + `rq_job_id` set; enqueue NOT called |
| 7 | `test_wake_outcomes_passed_to_enqueue` | `AddRecipeOutcome.recipe_name == "Lentejas"` reached the `WakeInvocationInput` payload |
| 8 | `test_wake_invocation_id_none_returns` | `invocation_id=None` early-return; no DB or queue writes |
| 9 | `test_wake_no_siblings_returns` | valid invocation_id but zero linked WorkflowRuns → no enqueue, no `wake_dispatched_at` |
| 10 | `test_on_step_complete_dispatches_wake_end_to_end` (`@pytest.mark.integration`) | drives `on_step_complete` end-to-end on real Postgres |

An `autouse` fixture cleans `workflow_run_steps` + `workflow_runs` before and
after each test (the standard `db_session` finalizer only handles
invocations / stored_messages / conversations).

### `tests/test_workflow_runner.py`

Updated the two existing dead-letter tests
(`test_on_step_failed_enqueues_dead_letter_when_reply_context_present`,
`test_on_step_failed_skips_dead_letter_when_reply_context_missing`) to
`monkeypatch` `_check_and_dispatch_wake` to raise. Under the new D-05
fallback-only contract the dead-letter only runs on wake exception; the tests
explicitly model that scenario. Both tests pass; the four pre-existing
`side_effect` query slots were extended to four entries to cover the
except-branch refetches.

## Decisions Made

- **Same-session, no internal commit (D-04 / Pitfall 2).** The helper performs
  `session.add` + `session.flush` and returns. The caller commits ONCE; the
  status flip on `WorkflowRun` and the new invocation row land in one
  transaction. Test 1 exercises the atomic path; the new unit tests would not
  pass otherwise because the parent's `wake_dispatched_at` and the new row
  must be visible together after a single `session.commit()` in the test
  body.

- **`UPDATE-RETURNING` not `UPDATE ... RETURNING *`.** Returning just `id` is
  enough — the helper only needs `rowcount` ≥ 1 to know it owns the wake.
  Idempotency test (test 5) verifies the second call returns without inserting.

- **`AddRecipeOutcome.model_validate` defensive `try/except`.** A stored
  `outcome` JSON that fails validation logs a WARNING and proceeds with
  `outcome=None` on the `WorkflowOutcomeSummary` envelope. The wake still
  fires — losing the structured outcome on one sibling shouldn't block the
  whole wake.

- **Dead-letter except-branch re-marks step + cancelled-steps + run.** Rollback
  discards the in-session writes; the except branch refetches and re-marks
  in a fresh transaction so a wake failure still produces a visible FAILED
  workflow.

## Verification

| Check | Result |
|-------|--------|
| `grep -c "_check_and_dispatch_wake" src/robotina/queue/workflow_runner.py` | 3 (def + 2 call sites) |
| `grep -c "wake_dispatched_at IS NULL" src/robotina/queue/workflow_runner.py` | 2 (SQL literal + comment) |
| Single-commit invariant on `on_step_failed` happy path | confirmed by regex check in plan verify block |
| `pytest tests/queue/test_wake_dispatch.py` | 10/10 pass |
| `pytest tests/queue/` (all queue tests) | 24/24 pass |
| `pytest tests/test_workflow_runner.py -m "not integration"` | 32/32 pass |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Except-branch must re-mark step and cancelled steps, not just run**
- **Found during:** Task 3.2
- **Issue:** The plan's diff for the except branch only re-marked `run.status = FAILED`. Rollback discards the `step.status = FAILED`, `step.failure_reason`, and the cancelled-pending-steps writes too — so a wake-helper exception would leave the step in `RUNNING` state and pending steps un-cancelled, contradicting the visible-failure invariant.
- **Fix:** Refetch step + pending list inside the except branch and re-write all three buckets (step status + failure_reason, cancelled steps, run status) before the second commit.
- **Files modified:** `src/robotina/queue/workflow_runner.py`
- **Commit:** b1385e8

**2. [Rule 1 - Bug] Updated two dead-letter unit tests to reflect new D-05 fallback-only contract**
- **Found during:** Task 3.2 verification
- **Issue:** Pre-existing `test_on_step_failed_enqueues_dead_letter_when_reply_context_present` and `test_on_step_failed_skips_dead_letter_when_reply_context_missing` expected the dead-letter block to ALWAYS run on failure. Under D-05 the dead-letter is fallback-only, gated on wake-helper exception. Without the update both tests would fail.
- **Fix:** `monkeypatch.setattr(workflow_runner, "_check_and_dispatch_wake", _raise)` to force the wake exception path, plus extended `query_mock.first.side_effect` from 2 entries to 4 (step + run pre-commit; step + run refetch in except branch).
- **Files modified:** `tests/test_workflow_runner.py`
- **Commit:** b1385e8

**3. [Rule 3 - Blocking] Added autouse cleanup fixture for workflow tables**
- **Found during:** Task 3.3
- **Issue:** The conftest `db_session` finalizer only cleans `robotina_invocations`, `stored_messages`, and `conversations`. The new tests insert `workflow_runs` (FK to conversations) and `workflow_run_steps`. Without explicit cleanup the conversation DELETE in the conftest finalizer fails with a FK violation.
- **Fix:** Local `autouse` `_cleanup_workflow_tables` fixture in `test_wake_dispatch.py` that truncates both tables before AND after each test.
- **Files modified:** `tests/queue/test_wake_dispatch.py`
- **Commit:** 2cdde2c

**4. [Rule 3 - Blocking] `Conversation` constructor uses `household_id`, not `user_id`**
- **Found during:** Task 3.3 first test run
- **Issue:** The plan's sketch had `Conversation(platform="telegram", chat_id="...", user_id="...")` but the actual model has `household_id` (not `user_id`) and `user_id` is on `StoredMessage`, not `Conversation`.
- **Fix:** Use `Conversation(platform="telegram", chat_id="c-wake", household_id="test-household")` matching the real schema.
- **Files modified:** `tests/queue/test_wake_dispatch.py`
- **Commit:** 2cdde2c

No checkpoints reached. No architectural changes required.

## Pre-existing failures (NOT caused by this plan)

Confirmed via `git stash` test that the following failures exist on `main`
prior to plan 20-03 work:
- `tests/test_gateway.py::test_history_window`
- `tests/test_workflows.py::test_add_recipe_workflow_registered` (expects 7
  steps; plan 20-02 added `finalize-outcome` as the 8th)
- `tests/unit/test_agent_middleware.py` (4 tests)
- `tests/unit/test_observability.py::test__setup_langwatch_nonfatal_when_missing_credentials`

These are out-of-scope for plan 20-03. Logged here for tracking; not fixed.

## Commits

| Hash    | Type    | Summary                                                |
|---------|---------|--------------------------------------------------------|
| 36aff06 | feat    | add `_check_and_dispatch_wake` helper                  |
| b1385e8 | feat    | wire wake helper into `on_step_complete` + `on_step_failed` |
| 2cdde2c | test    | wake-helper unit tests + D-18 integration test        |

## Self-Check: PASSED

- `src/robotina/queue/workflow_runner.py` — exists, contains `_check_and_dispatch_wake` (3 refs)
- `tests/queue/test_wake_dispatch.py` — exists, 10 tests pass
- `tests/test_workflow_runner.py` — modified, 32 non-integration tests pass
- Commit `36aff06` — FOUND in `git log`
- Commit `b1385e8` — FOUND in `git log`
- Commit `2cdde2c` — FOUND in `git log`
