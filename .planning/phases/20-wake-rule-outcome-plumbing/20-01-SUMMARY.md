---
phase: 20-wake-rule-outcome-plumbing
plan: 01
subsystem: queue/task_types
tags: [pydantic-v2, wake-rule, contracts, additive]
requires: [phase-18 AddRecipeOutcome]
provides:
  - WakeInvocationInput task input model
  - WorkflowOutcomeSummary envelope
  - FinalizeOutcomeInput agentless-task input
affects:
  - src/robotina/queue/task_types.py (additive only)
tech_stack_added: []
tech_stack_patterns:
  - ConfigDict(extra="forbid") on all new models
  - Pydantic v2 model_dump(mode="json") round-trip
  - Spanish synthetic to_user_message() rendering (D-09)
key_files_created:
  - tests/queue/__init__.py
  - tests/queue/test_task_types_wake_models.py
key_files_modified:
  - src/robotina/queue/task_types.py
decisions:
  - "D-03 honored: FinalizeOutcomeInput has optional metadata/load/failure_reason; rejects extras"
  - "D-06 honored: WorkflowOutcomeSummary is thin envelope around AddRecipeOutcome | None"
  - "D-08 honored: WakeInvocationInput shape {previous_invocation_id, conversation_id, outcomes}"
  - "D-09 honored: to_user_message renders Spanish with ✓/✗ + Wake-trigger parenthetical"
metrics:
  duration: "~4 minutes"
  completed_date: "2026-05-19"
  tasks_completed: 2
  files_modified: 1
  files_created: 2
---

# Phase 20 Plan 01: Wake-input contracts Summary

Shipped the three Pydantic v2 contracts Phase 20 needs ahead of consumers: `WakeInvocationInput` (wake-job task input), `WorkflowOutcomeSummary` (per-WorkflowRun envelope), and `FinalizeOutcomeInput` (agentless `finalize-outcome` task input).

## What changed

- **`src/robotina/queue/task_types.py`**: appended three new model classes below `AddRecipeOutcome`. All three use `model_config = ConfigDict(extra="forbid")`. `WakeInvocationInput.to_user_message()` renders a Spanish synthetic user message per D-09 (✓/✗ per outcome, trailing "Wake-trigger; el usuario ya fue notificado." parenthetical).
- **`tests/queue/test_task_types_wake_models.py`** (new): 8 unit tests covering construction, round-trip through `model_dump(mode="json")` → `model_validate`, extra-field rejection on all three models, and the three to_user_message() branches (success / failure / empty-list).
- **`tests/queue/__init__.py`** (new): package marker so pytest collects the new test module.

## Decisions honored

| Decision | Application |
|----------|-------------|
| D-03 | `FinalizeOutcomeInput` has `metadata`, `load`, `failure_reason` — all optional dicts/strings, `extra="forbid"`. |
| D-06 | `WorkflowOutcomeSummary` is the minimum envelope (workflow_run_id, workflow_type, status, outcome); `AddRecipeOutcome | None` for the outcome slot, since FAILED workflows don't run `finalize-outcome`. |
| D-08 | `WakeInvocationInput` is `{previous_invocation_id, conversation_id, outcomes: list[WorkflowOutcomeSummary]}`. |
| D-09 | `to_user_message()` body is Spanish; the agent body prompt stays English (V004 work is a later plan). |

## Verification

- `uv run pytest tests/queue/test_task_types_wake_models.py -x -q` → 8 passed.
- `uv run pytest tests/queue/ -x -q` → 8 passed.
- `grep -n "class WakeInvocationInput\|class WorkflowOutcomeSummary\|class FinalizeOutcomeInput" src/robotina/queue/task_types.py` → 3 lines.
- Inline `uv run python -c "..."` smoke from the plan: `OK`.

## Deviations from Plan

**1. Worktree branch was behind main** — the agent worktree was created from a pre-Phase-18 commit, so `AddRecipeOutcome` (the import the new models depend on) was missing from this worktree's `task_types.py`. Resolved by `git merge main --no-edit` inside the worktree (fast-forwarding to include Phase 18 + Phase 19/20 planning artifacts). No conflicts. This is a setup-level deviation, not a plan-content deviation. Tracked here so the next executor knows the worktree base may need similar treatment.

Otherwise: plan executed verbatim. No Rule 1/2/3 auto-fixes were triggered.

## Commits

- `716bc50` — feat(20-01): add WakeInvocationInput / WorkflowOutcomeSummary / FinalizeOutcomeInput models
- `12ca097` — test(20-01): add unit tests for wake-input + finalize-outcome models

## Known Stubs

None. The three new models are pure data contracts; consumers land in waves 2–3 per the phase plan.

## Self-Check: PASSED

- src/robotina/queue/task_types.py — exists, contains all three classes (grep verified).
- tests/queue/test_task_types_wake_models.py — exists, 8 tests pass.
- Commits 716bc50 and 12ca097 — present in git log.
