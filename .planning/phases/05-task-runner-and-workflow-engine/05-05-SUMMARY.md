---
phase: 05-task-runner-and-workflow-engine
plan: "05"
subsystem: database
tags: [sqlalchemy, alembic, postgres, rq, workflow, status-lifecycle]

requires:
  - phase: 05-task-runner-and-workflow-engine
    provides: WorkflowRun/WorkflowRunStep models, workflow_runner.py, start_workflow function, integration tests

provides:
  - WorkflowStatus.PENDING enum value in models.py
  - WorkflowRun created as PENDING (not RUNNING) at queue time
  - on_step_start transitions WorkflowRun PENDING->RUNNING when first step begins executing
  - queue_workflow function replacing start_workflow
  - Alembic migration 0004 adding 'pending' to workflowstatus Postgres enum

affects:
  - Phase 6+ agents that create workflows via StartWorkflowTool
  - Any monitoring/observability code reading WorkflowRun.status

tech-stack:
  added: []
  patterns:
    - "Status lifecycle: PENDING at creation, RUNNING when worker picks up first step, DONE/FAILED at completion"
    - "on_step_start performs dual update: step.status=RUNNING + run.status=RUNNING (if PENDING)"

key-files:
  created:
    - migrations/versions/0004_workflow_pending_status.py
  modified:
    - src/robotina/queue/models.py
    - src/robotina/queue/workflow_runner.py
    - src/robotina/agent/tools/start_workflow.py
    - tests/test_workflow_runner.py
    - tests/test_start_workflow_tool.py

key-decisions:
  - "queue_workflow (not start_workflow) is the canonical name for workflow initiation — reflects that it enqueues but doesn't execute"
  - "on_step_start is the single point of PENDING->RUNNING transition for WorkflowRun; no other code sets it to RUNNING"
  - "Migration 0004 uses ALTER TYPE ... ADD VALUE IF NOT EXISTS — idempotent, safe on Postgres 9.1+"

patterns-established:
  - "WorkflowRun status lifecycle: PENDING (created) -> RUNNING (first step starts) -> DONE/FAILED (all steps complete/fail)"

requirements-completed: [WF-02, WF-04]

duration: 3min
completed: 2026-03-27
---

# Phase 5 Plan 05: Workflow PENDING Status Gap Closure Summary

**WorkflowRun status lifecycle fixed: PENDING at creation via queue_workflow, RUNNING transition in on_step_start when worker picks up first step**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-27T00:04:49Z
- **Completed:** 2026-03-27T00:07:09Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- Added `WorkflowStatus.PENDING = "pending"` to the enum and changed `WorkflowRun.status` default to PENDING
- Created Alembic migration 0004 to ALTER TYPE workflowstatus ADD VALUE 'pending' BEFORE 'running'
- Renamed `start_workflow` to `queue_workflow` throughout; `on_step_start` now transitions the WorkflowRun from PENDING to RUNNING
- Updated all test call sites; added UAT assertion that WorkflowRun starts PENDING before worker executes
- 81 unit tests pass, 6 integration tests pass (including happy path showing PENDING->RUNNING->DONE lifecycle)

## Task Commits

1. **Task 1: Add PENDING to WorkflowStatus and create Alembic migration** - `5806ea6` (feat)
2. **Task 2: Rename start_workflow → queue_workflow and fix status lifecycle** - `6483923` (feat)
3. **Task 3: Update tests and run integration suite** - `db7efb7` (feat)

## Files Created/Modified
- `src/robotina/queue/models.py` - Added PENDING to WorkflowStatus enum; changed WorkflowRun.status default to PENDING
- `migrations/versions/0004_workflow_pending_status.py` - New migration: ALTER TYPE workflowstatus ADD VALUE 'pending'
- `src/robotina/queue/workflow_runner.py` - Renamed start_workflow->queue_workflow; on_step_start now sets run.status=RUNNING
- `src/robotina/agent/tools/start_workflow.py` - Updated call from start_workflow to queue_workflow
- `tests/test_workflow_runner.py` - Updated import, make_run default, call sites, added PENDING assertion in happy path
- `tests/test_start_workflow_tool.py` - Added PENDING status assertion in creates_workflow_run test

## Decisions Made
- `queue_workflow` naming reflects the semantic: the function enqueues the workflow but doesn't execute it
- `on_step_start` is the single authoritative point for PENDING→RUNNING on the WorkflowRun — matches real execution semantics
- Migration uses `ALTER TYPE ... ADD VALUE IF NOT EXISTS` for idempotent enum extension

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- WorkflowRun PENDING status gap closed; UAT test 5 passes (hello-world-2step happy path shows correct PENDING->RUNNING->DONE lifecycle)
- Phase 5 complete — all workflow engine requirements (WF-02 through WF-09) satisfied
- Phase 6 (agents: notification, Robotina routing, recipe research, recipe load) can proceed

## Self-Check: PASSED

- FOUND: src/robotina/queue/models.py
- FOUND: migrations/versions/0004_workflow_pending_status.py
- FOUND: src/robotina/queue/workflow_runner.py
- FOUND: .planning/phases/05-task-runner-and-workflow-engine/05-05-SUMMARY.md
- FOUND commit: 5806ea6 (Task 1)
- FOUND commit: 6483923 (Task 2)
- FOUND commit: db7efb7 (Task 3)

---
*Phase: 05-task-runner-and-workflow-engine*
*Completed: 2026-03-27*
