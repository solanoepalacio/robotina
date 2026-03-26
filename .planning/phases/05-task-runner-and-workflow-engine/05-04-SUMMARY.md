---
phase: 05-task-runner-and-workflow-engine
plan: 04
subsystem: queue
tags: [rq, workflow, langchain, sqlalchemy, basetool, integration-tests]

# Dependency graph
requires:
  - phase: 05-03
    provides: workflow_runner.py with on_step_start, on_step_complete, on_step_failed, start_workflow
  - phase: 04-llm-module-and-agent-infrastructure
    provides: run_task() in jobs.py, BaseTool pattern from ReadSkillTool

provides:
  - jobs.py with inline workflow hooks (on_step_start before agent, on_step_complete after, on_step_failed in except)
  - agent/tools/__init__.py — tools package
  - agent/tools/start_workflow.py — StartWorkflowTool BaseTool subclass
  - Integration tests for hello-world-2step happy path and failure path

affects:
  - phase-06-notification-agent
  - phase-07-handle-incoming-message-agent

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "workflow hooks are inline calls in run_task() — no new dispatcher function (D-08)"
    - "StartWorkflowTool is a BaseTool subclass creating its own DB session (D-10)"
    - "Integration tests use wf_db_session fixture with DELETE cleanup on workflow tables"
    - "Unit tests for run_task() must patch workflow_runner.on_step_start/complete/failed to avoid live DB"

key-files:
  created:
    - src/robotina/agent/tools/__init__.py
    - src/robotina/agent/tools/start_workflow.py
  modified:
    - src/robotina/queue/jobs.py
    - tests/test_workflow_runner.py
    - tests/test_start_workflow_tool.py
    - tests/unit/test_agent_runner.py
    - tests/unit/test_prompts.py

key-decisions:
  - "Workflow hooks are three inline calls in run_task() — not a dispatcher pattern (D-08 confirmed)"
  - "StartWorkflowTool reads household_id from shared_context dict parameter (D-10)"
  - "Existing unit tests that call run_task() need workflow_runner patches to avoid live DB queries"

patterns-established:
  - "Pattern: BaseTool subclasses that need DB access create their own session via SessionLocal() in a finally block"
  - "Pattern: Unit tests calling run_task() must patch robotina.db.SessionLocal and robotina.queue.workflow_runner.on_step_* functions"

requirements-completed: [WF-04, WF-05, WF-06, WF-07, WF-08, QUEUE-01]

# Metrics
duration: 6min
completed: 2026-03-26
---

# Phase 5 Plan 04: Workflow Engine Wiring Summary

**Workflow hooks wired into run_task() and StartWorkflowTool created — Phase 5 workflow engine fully connected with integration tests for hello-world-2step happy path and failure path**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-26T22:15:00Z
- **Completed:** 2026-03-26T22:21:00Z
- **Tasks:** 2 (+ 1 auto-approved checkpoint)
- **Files modified:** 7

## Accomplishments

- jobs.py: workflow_runner hooks (on_step_start, on_step_complete, on_step_failed) inline around agent execution
- StartWorkflowTool: BaseTool subclass wrapping workflow_runner.start_workflow(), creates own DB session
- Integration tests: hello-world-2step happy path (both steps DONE, WorkflowRun DONE) and failure path (step1 FAILED, step2 CANCELLED, WorkflowRun FAILED)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add workflow hooks to run_task() and create agent/tools/ package with StartWorkflowTool** - `d0c5048` (feat)
2. **Task 2: Fill in integration tests and run against live services** - `fbf07c2` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/robotina/queue/jobs.py` - Added workflow hooks: _session/queue setup, on_step_start before agent, on_step_complete after, on_step_failed in except, _session.close() in finally
- `src/robotina/agent/tools/__init__.py` - New tools package
- `src/robotina/agent/tools/start_workflow.py` - StartWorkflowTool: BaseTool subclass, _run creates workflow via workflow_runner.start_workflow()
- `tests/test_workflow_runner.py` - Filled in integration tests (wf_db_session fixture, happy path, failure path)
- `tests/test_start_workflow_tool.py` - 4 integration tests + is_basetool unit test
- `tests/unit/test_agent_runner.py` - Added patches for workflow_runner and SessionLocal in existing test
- `tests/unit/test_prompts.py` - Added patches for workflow_runner and SessionLocal in existing test

## Decisions Made

- Workflow hooks are three inline calls in run_task() — no dispatcher function (D-08 confirmed).
- StartWorkflowTool reads household_id from shared_context.get("household_id", "") — consistent with plan spec.
- Existing unit tests calling run_task() needed workflow_runner mock patches because the new DB session creation hits a real DB even in mocked contexts.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed unit tests broken by new workflow infrastructure in run_task()**
- **Found during:** Task 1 (jobs.py modification)
- **Issue:** test_run_task_reads_task_type_from_job_meta and test_skill_index_appended_to_prompt called run_task() without patching the new SessionLocal() and workflow_runner calls, causing SQLAlchemy ProgrammingError (MagicMock used as SQL parameter)
- **Fix:** Added patches for robotina.db.SessionLocal and robotina.queue.workflow_runner.on_step_start/complete/failed in both tests
- **Files modified:** tests/unit/test_agent_runner.py, tests/unit/test_prompts.py
- **Verification:** uv run pytest tests/ -k "not integration" passes (81 passed)
- **Committed in:** d0c5048 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Fix was necessary for test correctness. New infrastructure requires mocking in unit tests that invoke run_task().

## Issues Encountered

None beyond the auto-fixed unit test patches.

## Known Stubs

None — all integration tests contain real test code. The integration tests require live Redis + Postgres to run (marked @pytest.mark.integration).

## Next Phase Readiness

- Phase 5 workflow engine is fully wired: WORKFLOW_REGISTRY, workflow_runner, StartWorkflowTool, run_task() hooks
- Integration tests ready to run with `uv run pytest tests/ -v --timeout=60` against live Docker services
- Phase 6 (notification agent) can proceed: send-notification task type and agent needed

---
*Phase: 05-task-runner-and-workflow-engine*
*Completed: 2026-03-26*
