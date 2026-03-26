---
phase: 05-task-runner-and-workflow-engine
plan: "02"
subsystem: agent
tags: [pydantic, workflow-registry, langchain, tdd, workflows]

# Dependency graph
requires:
  - phase: 02-database-models-and-queue-layer
    provides: RecipeResearchInput, RecipeLoadInput, SendNotificationInput, RecipeData in task_types.py
  - phase: 05-task-runner-and-workflow-engine
    plan: "01"
    provides: Wave 0 test stubs in tests/test_workflows.py (9 stubs to convert)
provides:
  - WorkflowStepDef Pydantic BaseModel (step_key, task_type, build_input Callable)
  - WorkflowDefinition Pydantic BaseModel (workflow_type, steps list)
  - WORKFLOW_REGISTRY dict with add-recipe (3 steps) and hello-world-2step (2 steps)
affects:
  - 05-03-PLAN.md (workflow_runner.py reads WORKFLOW_REGISTRY to look up WorkflowDefinition)
  - 05-04-PLAN.md (StartWorkflowTool calls workflow_runner.start_workflow which uses WORKFLOW_REGISTRY)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pydantic ConfigDict(arbitrary_types_allowed=True) required for Callable fields in BaseModel"
    - "build_input lambda receives (shared_context: dict, accumulated_artifacts: dict) — accumulated_artifacts values are plain dicts (model_dump output), not Pydantic models"
    - "RecipeData must be reconstructed from artifacts dict: RecipeData(**artifacts['research']['recipe'])"

key-files:
  created:
    - src/robotina/agent/workflows.py
  modified:
    - tests/test_workflows.py

key-decisions:
  - "build_input lambdas for add-recipe implemented verbatim per spec (05-CONTEXT.md D-02, D-03)"
  - "RecipeData(**artifacts['research']['recipe']) reconstructs RecipeData from JSON-serialized dict in load step"
  - "hello-world-2step registered per D-04 — Phase 5 test scaffolding, removed in Phase 6 with hello-world agent config"
  - "reply_context only in notify step build_input, not in research or load — enforces WorkflowRun.shared_context isolation"

patterns-established:
  - "Workflow registry pattern: Pydantic models with ConfigDict(arbitrary_types_allowed=True) for Callable fields"
  - "TDD RED-GREEN for Wave 0 stubs: convert pytest.skip() stubs to real assertions, then create implementation"

requirements-completed:
  - WF-02
  - WF-03
  - WF-09

# Metrics
duration: 3min
completed: 2026-03-26
---

# Phase 5 Plan 02: Workflow Registry Summary

**WorkflowStepDef/WorkflowDefinition Pydantic models and WORKFLOW_REGISTRY with add-recipe (research/load/notify) and hello-world-2step test workflow**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-26T22:06:53Z
- **Completed:** 2026-03-26T22:09:16Z
- **Tasks:** 1 (TDD: RED + GREEN commits)
- **Files modified:** 2

## Accomplishments
- Created `src/robotina/agent/workflows.py` with WorkflowStepDef, WorkflowDefinition, and WORKFLOW_REGISTRY
- Implemented add-recipe workflow verbatim from spec: research (recipe-research) -> load (recipe-load) -> notify (send-notification) with correct build_input lambdas including RecipeData reconstruction from artifacts dict
- Implemented hello-world-2step test workflow with step1 and step2 for Phase 5 integration testing
- Converted all 9 pytest.skip() stubs in test_workflows.py to passing assertions
- Full suite: 82 passed, 18 skipped, 0 errors — no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): add failing tests for workflows registry** - `411599e` (test)
2. **Task 1 (GREEN): implement workflows.py** - `6196439` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/robotina/agent/workflows.py` - WorkflowStepDef, WorkflowDefinition, WORKFLOW_REGISTRY with add-recipe and hello-world-2step
- `tests/test_workflows.py` - 9 stubs converted to real assertions (all passing)

## Decisions Made
- Pydantic `ConfigDict(arbitrary_types_allowed=True)` required on both WorkflowStepDef and WorkflowDefinition since Callable is not a standard Pydantic type
- `build_input` for the load step uses `RecipeData(**artifacts["research"]["recipe"])` — artifacts store model_dump(mode='json') output so recipe is a plain dict that must be reconstructed
- `reply_context` is absent from research and load step build_inputs — lives only in the notify step via `**ctx["reply_context"]` — enforces the architectural constraint from PROJECT.md

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `workflows.py` exports WorkflowStepDef, WorkflowDefinition, WORKFLOW_REGISTRY — ready for Plan 03 (workflow_runner.py)
- `WORKFLOW_REGISTRY["hello-world-2step"]` available for Plan 03 integration tests
- `WORKFLOW_REGISTRY["add-recipe"]` available for Plan 03/04 end-to-end verification

## Known Stubs

None - all 9 test_workflows.py tests are passing with real assertions. No stubs remain.

## Self-Check: PASSED

- FOUND: src/robotina/agent/workflows.py
- FOUND: tests/test_workflows.py (9 tests passing)
- FOUND commit: 411599e (RED phase test)
- FOUND commit: 6196439 (GREEN phase implementation)

---
*Phase: 05-task-runner-and-workflow-engine*
*Completed: 2026-03-26*
