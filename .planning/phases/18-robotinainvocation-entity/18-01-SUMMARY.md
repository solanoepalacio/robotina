---
phase: 18
plan: 01
subsystem: tests
tags: [wave-0, red-state, lock-tests, robotina-invocation]
requires:
  - Phase 17 complete (Conversation FK + WorkflowOutcome stub already in place)
provides:
  - RED-state lock tests for ARCH-02 (RobotinaInvocation entity)
  - RED-state lock tests for ARCH-03 (WorkflowRun.triggered_by_invocation_id FK)
  - RED-state lock tests for ARCH-04 (AddRecipeOutcome Pydantic shape)
  - RED-state lock tests for DASH-13 (detail-view triggered_by rendering)
  - Shared invocation_factory fixture
affects:
  - tests/test_queue_models.py
  - tests/test_task_types.py
  - tests/test_workflow_runner.py
  - tests/test_gateway.py
  - tests/unit/test_start_workflow_tool.py
  - tests/dashboard/test_detail_view.py
  - tests/conftest.py
tech-stack:
  added: []
  patterns:
    - "Wave 0 RED-state lock tests (collection succeeds; tests fail; deletion of Phase 17 WorkflowOutcome stub)"
    - "Pre-commit ctor-grep gate: every StartWorkflowTool(...) call carries invocation_id="
    - "Shared pytest fixture (invocation_factory) for cross-module test reuse"
key-files:
  created: []
  modified:
    - tests/test_queue_models.py
    - tests/test_task_types.py
    - tests/test_workflow_runner.py
    - tests/test_gateway.py
    - tests/unit/test_start_workflow_tool.py
    - tests/dashboard/test_detail_view.py
    - tests/conftest.py
decisions:
  - "Bulk-updated test_workflow_runner.py:1029 ctor (outside plan's stated file list) to keep the cross-file pre-commit grep gate green — Rule 2 deviation, see Deviations section."
  - "test_migration_0007_upgrades_and_downgrades body intentionally calls pytest.skip() — Wave 0 only locks the import contract (file path + revision identifiers); Wave 1 fills in the live DB round-trip body once 0007 migration file exists."
metrics:
  duration: ~5min
  completed: 2026-05-19
requirements: [ARCH-02, ARCH-03, ARCH-04, DASH-13]
requirements_addressed: [ARCH-02, ARCH-03, ARCH-04, DASH-13]
---

# Phase 18 Plan 01: Wave 0 RED-State Lock Tests Summary

Wave 0 lock-test step landed: every Phase 18 contract (new entity + columns, signature args, gateway insert, dedup-no-orphan, dashboard rendering, AddRecipeOutcome shape) is encoded as an executable test in source. Suite collects cleanly; new tests are RED — exactly the Wave-0 success signal. Phase 17's `test_workflow_outcome_stub` deleted; load-bearing `test_duplicate_message_no_orphan_invocation` committed.

## What Was Built

### Task 1.1 — Schema + outcome + signature RED tests (commit `43769cb`)

**`tests/test_queue_models.py`** — appended 5 introspection tests (all RED, expected):
- `test_invocation_trigger_enum_has_full_value_set` — D-06 (3 values upfront)
- `test_invocation_status_enum_has_full_value_set` — D-07 (4 values upfront)
- `test_robotina_invocation_model_has_required_columns` — D-04/D-05/D-10 (full Phase-20-ready schema)
- `test_robotina_invocation_has_unique_constraint_on_trigger_ref_and_trigger` — D-08 (wake-rule idempotency guard)
- `test_workflow_run_has_triggered_by_invocation_id_column` — ARCH-03 / D-02 (nullable FK)

**`tests/test_task_types.py`** — DELETED `test_workflow_outcome_stub` (Phase 17 stub) + preceding comment block; ADDED 6 RED tests:
- `test_add_recipe_outcome_success_round_trip` — D-17 (recipe_id/name/slug round-trip)
- `test_add_recipe_outcome_failure_round_trip` — D-17 (failure_reason variant)
- `test_add_recipe_outcome_rejects_unknown_fields` — D-17 (extra='forbid')
- `test_add_recipe_outcome_rejects_invalid_status` — D-17 (Literal status)
- `test_add_recipe_outcome_image_present_defaults_false` — D-17 (default False until Phase 24)
- `test_workflow_outcome_class_no_longer_exists` — D-18 (replacement, not supplement)

**`tests/test_workflow_runner.py`** — appended 3 RED tests:
- `test_queue_workflow_requires_triggered_by_invocation_id` — D-14 (TypeError gate, mirrors Phase 17 conversation_id pattern)
- `test_queue_workflow_persists_triggered_by_invocation_id` — D-23 (FK assignment on WorkflowRun row)
- `test_migration_0007_upgrades_and_downgrades` — D-23 (import contract; body skipped pending Wave 1 file)

### Task 1.2 — Ctor + gateway + dashboard RED tests + invocation_factory (commit `816d419`)

**`tests/conftest.py`** — appended `invocation_factory` fixture (RobotinaInvocation builder; default USER_MESSAGE + PENDING; used by gateway + dashboard tests).

**`tests/unit/test_start_workflow_tool.py`** — bulk-updated all 17 existing `StartWorkflowTool(...)` constructor sites with `invocation_id=_TEST_INV_ID`; defined `_TEST_INV_ID = "inv-test"` constant; appended 2 RED tests:
- `test_constructor_requires_invocation_id_no_default` — D-13 (pydantic ValidationError on missing field)
- `test_start_workflow_tool_propagates_invocation_id` — D-22 (invocation_id → queue_workflow.triggered_by_invocation_id)

**`tests/test_gateway.py`** — appended 2 RED tests (both `@pytest.mark.integration`):
- `test_user_message_creates_invocation` — D-11 + D-12 (RobotinaInvocation insert + meta['invocation_id'])
- `test_duplicate_message_no_orphan_invocation` — **load-bearing D-24 guard** (the single most important new test in Phase 18; duplicate platform_message_id MUST NOT create orphan invocation)

**`tests/dashboard/test_detail_view.py`** — appended 2 RED tests (both `@pytest.mark.integration` + `@pytest.mark.asyncio`):
- `test_detail_view_renders_triggered_by_invocation_id_when_set` — DASH-13 (UUID + label rendering)
- `test_detail_view_renders_em_dash_when_invocation_id_null` — DASH-13 / D-02 (em-dash placeholder for null FK)

## Constructor Update Count

| Metric | Count |
|---|---|
| `StartWorkflowTool(...)` ctor lines in `tests/unit/test_start_workflow_tool.py` BEFORE | 17 (per plan grep) |
| `StartWorkflowTool(...)` ctor lines AFTER (incl. 2 new RED-test ctors) | 19 actual calls |
| Of those, ctors passing `invocation_id=` | 18 (all except the deliberate-omission in `test_constructor_requires_invocation_id_no_default`) |
| Bonus: `tests/test_workflow_runner.py:1029` ctor also updated | +1 (Rule 2 — keeps cross-file grep gate green) |

## Pre-commit Grep Gate

Per plan acceptance criteria:
```bash
! grep -nE "StartWorkflowTool\([^)]*\)" tests/ -r | grep -v "invocation_id" | grep -v "^Binary" | grep -v "_TEST_INV_ID"
```
Verified: only docstring mentions (`StartWorkflowTool(household_id='')` in test descriptions) remain — no actual constructor call lacks `invocation_id=`.

## Verification

| Check | Result |
|---|---|
| `uv run pytest --collect-only -q` | 305 tests collected, exit 0 (no SyntaxError, no ImportError) |
| Task 1.1 new tests RED count | 14 / 14 failing (5 schema + 6 outcome + 3 signature/migration) |
| Task 1.2 new ctor + propagation tests RED | 2 / 2 failing |
| Existing 17 `StartWorkflowTool` tests post-bulk-update | 17 / 17 passing (regression-free) |
| `test_shared_context_reply_context_still_written` (test_workflow_runner.py:1029 updated) | passing |
| Integration tests (gateway/dashboard) | RED via import-time `ImportError` once integration markers run; collection passes because imports are inside function bodies (D-spec) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Cross-file grep gate completeness] Updated `tests/test_workflow_runner.py:1029` ctor**
- **Found during:** Task 1.2 (pre-commit grep gate scan)
- **Issue:** Plan's `<files>` list named only `tests/unit/test_start_workflow_tool.py` for the bulk ctor update, but `grep -rn "StartWorkflowTool(" tests/` revealed one additional call in `tests/test_workflow_runner.py::test_shared_context_reply_context_still_written` (line 1029). The plan's pre-commit grep gate (`grep -nE "StartWorkflowTool\([^)]*\)" tests/ -r | grep -v "invocation_id"`) scans the entire `tests/` tree — leaving this ctor unmodified would have broken the gate at commit time AND caused that test to TypeError once Wave 2 lands the required `invocation_id` arg.
- **Fix:** Added `invocation_id="inv-test",  # Phase 18 D-13: required ctor field` to the ctor call. The test asserts reply_context propagation (Phase 17 / ARCH-05 deprecation window); the extra kwarg is transparent to its goal.
- **Files modified:** `tests/test_workflow_runner.py`
- **Commit:** `816d419` (included with Task 1.2)

### None for Task 1.1

Plan executed exactly as written for Task 1.1.

## Threat Flags

None — Wave 0 introduces no new security-relevant surface (test-only changes; no source files touched).

## TDD Gate Compliance

This plan is `type: execute` (Wave 0 lock-test, not `type: tdd`). RED-state is the explicit success signal per the plan's `<objective>` — Waves 1/2/3 flip these tests GREEN.

Both commits use `test(...)` prefix, which is the correct conventional-commits type for test-only changes.

## Self-Check: PASSED

**Files created/modified — verified on disk:**
- `tests/test_queue_models.py` — FOUND (5 new tests appended)
- `tests/test_task_types.py` — FOUND (Phase 17 stub deleted, 6 new tests added)
- `tests/test_workflow_runner.py` — FOUND (3 new tests + 1 ctor updated)
- `tests/test_gateway.py` — FOUND (2 new tests appended)
- `tests/unit/test_start_workflow_tool.py` — FOUND (constant + 17 ctor updates + 2 new tests)
- `tests/dashboard/test_detail_view.py` — FOUND (2 new tests appended)
- `tests/conftest.py` — FOUND (invocation_factory fixture appended)

**Commits — verified in `git log`:**
- `43769cb` — `test(18-01): wave 0 RED-state schema + outcome + signature lock tests`
- `816d419` — `test(18-01): wave 0 RED-state ctor + gateway + dashboard lock tests`

## Known Stubs

None. RED-state tests reference symbols/columns that do not yet exist (RobotinaInvocation, InvocationTrigger/Status enums, AddRecipeOutcome, triggered_by_invocation_id column, migration 0007) — these are intentional Wave 0 lock-test failures, not stubs in the "rendering empty UI" sense.

## What's Next

Waves 1/2/3 (plans 18-02, 18-03, 18-04) land the source/schema/template changes that flip these tests GREEN. The grep targets in those plans' `<automated>` blocks point at the test names committed here.
