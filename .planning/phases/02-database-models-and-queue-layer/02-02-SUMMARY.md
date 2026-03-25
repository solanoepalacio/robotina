---
phase: 02-database-models-and-queue-layer
plan: 02
subsystem: queue
tags: [pydantic, pydantic-v2, rq, task-types, pickle, serialization]

# Dependency graph
requires:
  - phase: 02-database-models-and-queue-layer
    provides: queue package structure (src/robotina/queue/__init__.py, runner.py, models.py)

provides:
  - Centralized Pydantic v2 task I/O model module (src/robotina/queue/task_types.py)
  - 13 model classes: Message, ReplyContext, RecipeIngredient, RecipeStep, RecipeData,
    IncomingMessageInput, IncomingMessageOutput, RecipeResearchInput, RecipeResearchOutput,
    RecipeLoadInput, RecipeLoadOutput, SendNotificationInput, SendNotificationOutput
  - Verified pickle round-trip compatibility for all input models (RQ serialization)
  - Unit test suite for all models (tests/test_task_types.py, 9 tests, no Docker required)

affects:
  - 03-telegram-gateway (imports IncomingMessageInput, IncomingMessageOutput)
  - 04-agent-infrastructure (imports all task I/O models for agent typing)
  - 05-workflow-engine (imports RecipeResearchInput/Output, RecipeLoadInput/Output for workflow advancement)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Pydantic v2 BaseModel with list[...] and str | None syntax (no v1 style)
    - reply_context absent from intermediate task inputs (lives in WorkflowRun.shared_context)
    - model.model_dump(mode='json') required when storing to JSON column (not model.model_dump())

key-files:
  created:
    - src/robotina/queue/task_types.py
    - tests/test_task_types.py
  modified: []

key-decisions:
  - "All 13 task I/O model classes centralized in robotina.queue.task_types — single import point for queue, agents, and task runner"
  - "reply_context absent from RecipeResearchInput and RecipeLoadInput — it lives in WorkflowRun.shared_context, resolved by task runner in Phase 5"
  - "RecipeData uses human-readable food/unit names (food_name, unit_name strings) — recipe-load resolves them to IDs via household-manager API"

patterns-established:
  - "Pattern: All task I/O models import from robotina.queue.task_types — no per-agent model definitions"
  - "Pattern: Pydantic v2 exclusively — list[...], str | None, Literal[...] (no quotes) syntax throughout"
  - "Pattern: model.model_dump(mode='json') for JSON column storage; model.model_dump() returns Python objects (datetime not serializable)"

requirements-completed:
  - QUEUE-03

# Metrics
duration: 3min
completed: 2026-03-25
---

# Phase 02 Plan 02: Task I/O Models Summary

**13 Pydantic v2 task I/O model classes in robotina.queue.task_types with verified pickle round-trip compatibility for RQ serialization**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-25T20:54:57Z
- **Completed:** 2026-03-25T20:57:30Z
- **Tasks:** 1 (TDD: 2 commits — RED + GREEN)
- **Files modified:** 2

## Accomplishments

- Created `src/robotina/queue/task_types.py` with all 13 model classes verbatim from spec
- Enforced `reply_context` absence from `RecipeResearchInput` and `RecipeLoadInput` (lives in `WorkflowRun.shared_context`)
- All 9 unit tests pass without Docker — pure Python pickle round-trip verification

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `179a73a` (test)
2. **Task 1 GREEN: Implementation** - `202a39e` (feat)

_Note: TDD task with two commits (test RED → feat GREEN)_

## Files Created/Modified

- `src/robotina/queue/task_types.py` - 13 Pydantic v2 model classes (shared contract for queue, agents, task runner)
- `tests/test_task_types.py` - 9 unit tests: import check, field assertions, pickle round-trips

## Decisions Made

- All 13 task I/O models centralized in `robotina.queue.task_types` — single import for all downstream consumers
- `reply_context` absent from `RecipeResearchInput` and `RecipeLoadInput` — per spec and architectural decision: lives in `WorkflowRun.shared_context`, resolved by task runner
- `RecipeData` uses human-readable `food_name` and `unit_name` strings — recipe-load agent resolves to IDs via household-manager API

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `robotina.queue.task_types` is ready for import by Phase 3 (Telegram gateway enqueues `IncomingMessageInput`)
- Phase 4 (agent infrastructure) can import all 8 Input/Output model classes for agent typing
- Phase 5 (workflow engine) can import `RecipeResearchInput/Output` and `RecipeLoadInput/Output` for workflow step advancement

---
*Phase: 02-database-models-and-queue-layer*
*Completed: 2026-03-25*

## Self-Check: PASSED

- FOUND: src/robotina/queue/task_types.py
- FOUND: tests/test_task_types.py
- FOUND: .planning/phases/02-database-models-and-queue-layer/02-02-SUMMARY.md
- FOUND: commit 179a73a (test RED)
- FOUND: commit 202a39e (feat GREEN)
