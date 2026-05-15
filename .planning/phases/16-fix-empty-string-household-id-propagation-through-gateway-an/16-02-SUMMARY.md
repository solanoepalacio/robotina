---
phase: 16-fix-empty-string-household-id-propagation-through-gateway-an
plan: 02
subsystem: queue
tags: [pydantic, validation, python, queue, wave-1, green-state]

# Dependency graph
requires:
  - phase: 16-fix-empty-string-household-id-propagation-through-gateway-an
    plan: 01
    provides: 21 parametrized RED-state Pydantic stubs in tests/unit/test_household_id_validation.py
provides:
  - "NonEmptyHouseholdId = Annotated[str, Field(min_length=1, pattern=r'\\S')] alias in src/robotina/queue/task_types.py"
  - "household_id: NonEmptyHouseholdId annotation on all 7 task-input models (IncomingMessageInput, RecipeResearchInput, RecipeResearchGatherInput, RecipeResearchInstructionsInput, RecipeResearchIngredientsInput, RecipeResearchMetadataInput, RecipeLoadInput)"
affects: [16-03, 16-04, 16-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pydantic v2 Annotated[str, Field(...)] type alias for cross-model constraint reuse — single source of truth for non-empty + non-whitespace household_id"
    - "pattern=r'\\S' combined with min_length=1 to reject both empty string AND whitespace-only strings in a single declarative constraint (resolves RESEARCH Open Question 4)"

key-files:
  created: []
  modified:
    - src/robotina/queue/task_types.py

key-decisions:
  - "Used Annotated type alias over inline Field(...) — applied across 7 models, single point of change, single grep target, cleaner Pydantic model bodies (per CONTEXT.md 'Claude's Discretion' clause)"
  - "pattern=r'\\S' (at least one non-whitespace char) chosen to close the whitespace-only leak that bare min_length=1 leaves open — satisfies test_household_id_rejects_whitespace without requiring a separate strip-then-check validator"
  - "Scope held to task-input models only — RecipeData, SendNotificationInput, AcknowledgeAddRecipeInput, and DB models (Conversation, WorkflowRun) intentionally NOT modified per RESEARCH.md Affected Files Inventory"

patterns-established:
  - "Phase 16 defensive-validation tier complete for the Pydantic layer: REQ-HID-2 belt-and-suspenders enforcement satisfied. Any future caller bypassing the gateway boot guard (plan 16-05) still hits ValidationError at task-input construction."

requirements-completed: [REQ-HID-2]

# Metrics
duration: ~3min
completed: 2026-05-15
---

# Phase 16 Plan 02: Pydantic NonEmptyHouseholdId on 7 task-input models Summary

One-liner: Centralized `NonEmptyHouseholdId = Annotated[str, Field(min_length=1, pattern=r"\S")]` alias applied to all 7 task-input Pydantic models in `src/robotina/queue/task_types.py`, flipping 21 Wave 0 RED tests to GREEN with zero regression.

## What Changed

**Single file modified:** `src/robotina/queue/task_types.py`

Three edits applied:

1. **Imports updated** (line 33-35):
   - `from typing import Literal` → `from typing import Annotated, Literal`
   - `from pydantic import BaseModel` → `from pydantic import BaseModel, Field`

2. **`NonEmptyHouseholdId` alias defined** immediately after imports, before the `# Shared models` block, with a Phase 16 / REQ-HID-2 comment header explaining the dual constraint (`min_length=1` for empty rejection, `pattern=r"\S"` for whitespace-only rejection) and a forward reference to the deferred ambient-context refactor.

3. **Type annotation flipped from `str` to `NonEmptyHouseholdId`** on these 7 task-input models:

   | Model | Field |
   |-------|-------|
   | `IncomingMessageInput` | `household_id` (preserved trailing `# populated by the gateway from env var` comment) |
   | `RecipeResearchInput` | `household_id` |
   | `RecipeResearchGatherInput` | `household_id` |
   | `RecipeResearchInstructionsInput` | `household_id` |
   | `RecipeResearchIngredientsInput` | `household_id` |
   | `RecipeResearchMetadataInput` | `household_id` |
   | `RecipeLoadInput` | `household_id` |

**Intentionally NOT modified** (per RESEARCH.md Affected Files Inventory):
- `RecipeData` (no `household_id` field — it's the artifact, not a task input)
- `SendNotificationInput` / `SendNotificationOutput` (no `household_id` field)
- `AcknowledgeAddRecipeInput` (no top-level `household_id` — recipient context flows through `reply_context`)
- All `*Output` models (output-only, never carry household_id from caller)
- DB models in `src/robotina/queue/models.py` (out of scope per CONTEXT.md — no schema migration in Phase 16)

## Test Transition

**Before (Wave 0 baseline):** 14 tests in `tests/unit/test_household_id_validation.py::test_household_id_rejects_empty` and `::test_household_id_rejects_whitespace` parametrized over 7 models — all RED (`DID NOT RAISE <class 'pydantic_core._pydantic_core.ValidationError'>`).

**After (Wave 1):** 21/21 cases GREEN — `uv run pytest tests/unit/test_household_id_validation.py tests/test_task_types.py -x -q` → `39 passed in 0.02s`.

Breakdown:
- 7 × `test_household_id_rejects_empty` → PASS (was 7 fails)
- 7 × `test_household_id_rejects_whitespace` → PASS (was 7 fails)
- 7 × `test_household_id_accepts_valid` → PASS (was already passing — regression guard)
- 18 × pre-existing `tests/test_task_types.py` cases → PASS (zero regression; every existing fixture uses non-empty IDs like `"h1"`, `"hh-1"`)

## Acceptance Criteria Verification

All 7 plan-level acceptance criteria pass:

| AC | Check | Result |
|----|-------|--------|
| 1 | `grep -c "^from typing import Annotated, Literal$" src/robotina/queue/task_types.py` returns `1` | PASS |
| 2 | `grep -c "^from pydantic import BaseModel, Field$" src/robotina/queue/task_types.py` returns `1` | PASS |
| 3 | `grep -c "^NonEmptyHouseholdId = Annotated\[$" src/robotina/queue/task_types.py` returns `1` | PASS |
| 4 | `grep -cE "^\s+household_id: NonEmptyHouseholdId" src/robotina/queue/task_types.py` returns `7` | PASS |
| 5 | `grep -cE "^\s+household_id: str\b" src/robotina/queue/task_types.py` returns `0` | PASS |
| 6 | `uv run pytest tests/unit/test_household_id_validation.py -x -q` exits 0 | PASS (21/21) |
| 7 | `uv run pytest tests/test_task_types.py -x -q` exits 0 | PASS (18/18) |

## Decisions Made

1. **`Annotated` alias over inline `Field`** — applied across 7 models, having one named type alias gives a single grep target and a single point of change for any future constraint tightening. Discretionary per CONTEXT.md.

2. **`pattern=r"\S"` for whitespace rejection** — `min_length=1` alone accepts `"   "` (verified during Wave 0 RED state). The Wave 0 test `test_household_id_rejects_whitespace` explicitly requires whitespace rejection. `pattern=r"\S"` (regex "must contain at least one non-whitespace character") is the minimum-surface fix and avoids introducing a `strip()`-then-check validator. Resolves RESEARCH.md Open Question 4 at the Pydantic layer rather than relying solely on the gateway entrypoint guard (plan 16-05).

3. **Trailing comment preservation** — kept the `# populated by the gateway from env var` comment on `IncomingMessageInput.household_id` for future readers; the type-only change shouldn't bury that context.

## Deviations from Plan

None — plan executed exactly as written. No Rule 1/2/3 auto-fixes, no Rule 4 architectural escalation.

## Coordination Notes (Wave 1 parallel execution)

Plans 16-04, 16-05, 16-06 ran concurrently. My file ownership (`src/robotina/queue/task_types.py`) was non-overlapping and my commit landed cleanly alongside their commits to `src/robotina/gateway/__init__.py`, `src/robotina/gateway/send.py`, `src/robotina/queue/workflow_runner.py`, `tests/test_workflow_runner.py`, and `.env.example`. Staged only the owned file at commit time per coordination contract.

## Commits

- `e2be388` — `feat(16-02): add NonEmptyHouseholdId alias and apply to 7 task-input models`

## Self-Check: PASSED

- File modified exists: `src/robotina/queue/task_types.py` — FOUND
- Commit exists: `e2be388` — FOUND in `git log`
- Wave 0 Pydantic tests now GREEN: 21/21
- Regression suite passes: 18/18 in `tests/test_task_types.py`
- `grep household_id: str` returns 0 (conversion complete)
- `grep NonEmptyHouseholdId` returns 8 (1 alias definition + 7 model usages — matches `>= 8` plan requirement)
