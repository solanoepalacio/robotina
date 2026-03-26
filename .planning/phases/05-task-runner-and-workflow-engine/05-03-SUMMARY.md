---
phase: 05-task-runner-and-workflow-engine
plan: "03"
subsystem: queue
tags: [workflow-engine, sqlalchemy, rq, tdd, lifecycle, state-machine]

# Dependency graph
requires:
  - phase: 05-task-runner-and-workflow-engine
    plan: "02"
    provides: WORKFLOW_REGISTRY, WorkflowDefinition, WorkflowStepDef with build_input callables
  - phase: 02-database-models-and-queue-layer
    provides: WorkflowRun, WorkflowRunStep, WorkflowStatus, WorkflowStepStatus ORM models
provides:
  - start_workflow(workflow_type, shared_context, household_id, queue, session) -> str
  - on_step_start(job_id, session) — marks step RUNNING, no-op for direct tasks
  - on_step_complete(job_id, output, session, queue) — writes artifact, advances or marks DONE
  - on_step_failed(job_id, session) — marks FAILED, cancels PENDING siblings, marks run FAILED
affects:
  - 05-04-PLAN.md (StartWorkflowTool calls start_workflow; run_task() calls on_step_start/complete/failed)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Workflow lifecycle functions accept session argument for testability without live DB (D-11)"
    - "Pre-assign job_id before Postgres commit to guarantee no lost jobs (D-07 transactional advancement)"
    - "SQLAlchemy mock pattern: query().filter().first() chained via MagicMock with side_effect list"
    - "Lazy imports inside functions (from robotina.queue.models import ...) to avoid circular imports"

key-files:
  created:
    - src/robotina/queue/workflow_runner.py
  modified:
    - tests/test_workflow_runner.py

key-decisions:
  - "Queue is injected into workflow_runner functions (not hardcoded) — fully testable without RQ server"
  - "on_step_start returns None silently when job_id has no matching WorkflowRunStep (direct task path)"
  - "accumulated_artifacts built by querying all DONE steps for the workflow_run_id after flush"
  - "on_step_complete uses session.flush() before querying DONE steps to include just-completed step"
  - "result_ttl=-1 and failure_ttl=-1 on all enqueue calls in both start_workflow and on_step_complete"

patterns-established:
  - "TDD RED-GREEN for workflow lifecycle: write all 11 unit tests first, verify they fail (ModuleNotFoundError), then implement"
  - "Mock SQLAlchemy session with side_effect list for multiple .first() calls across one test"

requirements-completed:
  - WF-04
  - WF-05
  - WF-06
  - WF-07
  - WF-08
  - WF-09

# Metrics
duration: 5min
completed: 2026-03-26
---

# Phase 5 Plan 03: Workflow Runner Summary

**Workflow execution state machine with four lifecycle functions (start_workflow, on_step_start, on_step_complete, on_step_failed) — all 11 unit tests pass, queue injected, pre-assigned job IDs for transactional advancement**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-26T22:11:42Z
- **Completed:** 2026-03-26T22:18:00Z
- **Tasks:** 1 (TDD: RED + GREEN commits)
- **Files modified:** 2

## Accomplishments
- Created `src/robotina/queue/workflow_runner.py` with all four lifecycle functions
- `start_workflow`: creates WorkflowRun + all WorkflowRunStep records (PENDING), enqueues first step with pre-assigned UUID job_id before commit (D-07)
- `on_step_start`: marks step RUNNING + records started_at; returns None silently for direct tasks (job_id not in any WorkflowRunStep)
- `on_step_complete`: serializes output via model_dump(mode='json'), marks step DONE, builds accumulated_artifacts from all DONE steps, enqueues next PENDING step or marks WorkflowRun DONE
- `on_step_failed`: marks step FAILED, cancels all PENDING siblings, marks WorkflowRun FAILED
- Converted all 11 pytest.skip() stubs in test_workflow_runner.py to passing assertions
- Full suite: 90 passed, 7 skipped, 0 errors — no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): add failing tests for workflow_runner lifecycle** - `a28acae` (test)
2. **Task 1 (GREEN): implement workflow_runner.py** - `28016de` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/robotina/queue/workflow_runner.py` - Workflow execution state machine with 4 lifecycle functions
- `tests/test_workflow_runner.py` - 11 unit test stubs converted to real assertions (all passing)

## Decisions Made
- Queue is injected into all functions (not hardcoded as `Queue("agent-tasks")`) — keeps module testable without live Redis
- `session.flush()` called before querying DONE steps so the just-completed step is visible in the same transaction
- `accumulated_artifacts` built from a fresh query of all DONE steps after flush (not from in-memory tracking)
- Lazy imports inside each function to avoid circular import issues between queue and agent modules

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `workflow_runner.py` exports all 4 functions — ready for Plan 04 (StartWorkflowTool + run_task() wiring)
- `start_workflow` and `on_step_complete` both use pre-assigned job_id pattern (D-07 confirmed)
- 2 integration stubs in test_workflow_runner.py remain SKIPPED — filled by Plan 04 once run_task() is wired

## Known Stubs

None — all 11 unit tests are passing with real assertions. The 2 integration stubs are intentional SKIPPED markers for Plan 04 to fill.

## Self-Check: PASSED

- FOUND: src/robotina/queue/workflow_runner.py
- FOUND: tests/test_workflow_runner.py (11 unit tests passing, 2 integration SKIPPED)
- FOUND commit: a28acae (RED phase tests)
- FOUND commit: 28016de (GREEN phase implementation)

---
*Phase: 05-task-runner-and-workflow-engine*
*Completed: 2026-03-26*
