---
phase: 20-wake-rule-outcome-plumbing
plan: 05
subsystem: queue/reconcile
tags: [wake-rule, reconciler, pitfall-11, crash-recovery, WAKE-05]
dependency_graph:
  requires: [20-03, 20-04]
  provides: ["startup reconciler for stranded wake invocations"]
  affects: ["src/robotina/queue/runner.py"]
tech_stack:
  added: []
  patterns: ["RQ Job.exists liveness probe", "per-row try/except resilience loop"]
key_files:
  created:
    - src/robotina/queue/reconcile.py
    - tests/queue/test_reconcile.py
    - .planning/phases/20-wake-rule-outcome-plumbing/20-05-SUMMARY.md
  modified:
    - src/robotina/queue/runner.py
decisions:
  - "Reconciler lives in src/robotina/queue/reconcile.py (D-11) — separate module, called from task-runner boot before worker.work()"
  - "Reconciler is WAKE-only — defensive skip for USER_MESSAGE rows (D-11 / Pitfall 11)"
  - "Per-row try/except so individual row failures (transient Redis errors, malformed outcome JSON) don't abort the whole loop"
  - "Outcomes rebuilt from sibling WorkflowRun rows on every reconcile call — deterministic from committed state, no extra column needed (CONTEXT D-11 option B)"
metrics:
  duration_min: 5
  tasks_completed: 3
  completed_date: 2026-05-19
---

# Phase 20 Plan 05: Startup reconciler for stranded wake invocations — Summary

Startup-time reconciler module that closes the AOF-can't-replay-RQ-enqueue gap (Pitfall 11): scans `RobotinaInvocation` rows committed with a pre-assigned `rq_job_id` but never enqueued (because the task-runner crashed between Postgres commit and `queue.enqueue`), probes RQ via `Job.exists`, and re-enqueues missing jobs with the same `rq_job_id` (RQ deduplicates on job_id, so a race-win second enqueue is safe).

## What was built

**New module** `src/robotina/queue/reconcile.py` with `reconcile_invocations(session, queue) -> int`:
- SELECTs `RobotinaInvocation` rows where `status='pending' AND wake_dispatched_at IS NOT NULL AND rq_job_id IS NOT NULL`
- For each row: probes `Job.exists(row.rq_job_id, connection=queue.connection)`; if False → rebuilds `WakeInvocationInput` from sibling `WorkflowRun` rows (joined via `trigger_ref_id`), enqueues with `job_id=row.rq_job_id` and the standard wake-job meta envelope
- Defensive skip for non-WORKFLOW_COMPLETION trigger rows (shouldn't exist, logged if encountered)
- Per-row `try/except` — individual failures don't abort the loop
- Returns count of re-enqueued rows; logs result either way

**Boot wiring in `src/robotina/queue/runner.py::main`**: opens `SessionLocal()`, calls `reconcile_invocations(session, queue)` between the `LoggingWorker` construction and `worker.work()`, wrapped in `try/except` so a reconciler failure does not block worker startup.

**Tests** in `tests/queue/test_reconcile.py` (7 tests, all passing):
- `test_reconcile_reenqueues_orphan` — happy path
- `test_reconcile_skips_live_job` — `Job.exists=True` → no-op
- `test_reconcile_skips_non_wake_trigger` — defensive USER_MESSAGE skip
- `test_reconcile_skips_non_pending` — SQL filter excludes DONE/FAILED/RUNNING rows
- `test_reconcile_empty_state` — zero candidates → returns 0
- `test_reconcile_continues_on_row_error` — exception in row #1 does not block row #2
- `test_reconcile_rebuilds_outcomes` — multi-sibling `WorkflowOutcomeSummary` rebuild

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 5.1 | 5cf195b | feat(20-05): add startup reconciler for stranded wake invocations |
| 5.2 | db6d208 | feat(20-05): wire startup reconciler into task-runner boot |
| 5.3 | b744c2b | test(20-05): add reconciler unit tests |

## Verification

- `uv run python -c "from robotina.queue.reconcile import reconcile_invocations; print('OK')"` → OK
- `uv run python -c "from robotina.queue.runner import main; print('OK')"` → OK
- `grep -c "reconcile_invocations" src/robotina/queue/runner.py` → 2
- `grep -c "Job.exists" src/robotina/queue/reconcile.py` → 1
- `uv run pytest tests/queue/test_reconcile.py -q` → 7 passed
- Broader `tests/queue/ tests/unit/`: 170 passed, 9 pre-existing failures in `tests/unit/test_agents_registry.py` (verified unrelated via `git stash` baseline check — failures exist on main without this plan's changes; deferred to phase-cleanup work)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test bug] UniqueConstraint collision in error-resilience test**
- **Found during:** Task 5.3 (test execution)
- **Issue:** `test_reconcile_continues_on_row_error` originally created two `WORKFLOW_COMPLETION` orphans under the same parent invocation. The Phase 18 `UniqueConstraint("trigger_ref_id", "trigger")` rejected the second insert.
- **Fix:** Use two distinct parent invocations (`parent_a`, `parent_b`), one orphan each. Same semantic test (first row's `Job.exists` raises → second row should still be reconciled), now compatible with the live schema.
- **Files modified:** tests/queue/test_reconcile.py
- **Commit:** b744c2b (single test commit, fix included)

### Out of Scope (deferred)

**Pre-existing failures in `tests/unit/test_agents_registry.py` (9 tests)** — confirmed pre-existing via `git stash` baseline check before commit. Not caused by this plan; not in plan 20-05 scope. Logged here for the verifier; resolution belongs to whichever phase last touched the agents registry config.

## Self-Check

- [x] `src/robotina/queue/reconcile.py` — FOUND
- [x] `src/robotina/queue/runner.py` reconciler call — FOUND (`grep -c "reconcile_invocations"` = 2)
- [x] `tests/queue/test_reconcile.py` — FOUND
- [x] Commit 5cf195b — FOUND in git log
- [x] Commit db6d208 — FOUND in git log
- [x] Commit b744c2b — FOUND in git log
- [x] `uv run pytest tests/queue/test_reconcile.py -q` — 7 passed

## Self-Check: PASSED
