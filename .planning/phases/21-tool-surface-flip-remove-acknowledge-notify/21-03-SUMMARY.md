---
phase: 21-tool-surface-flip-remove-acknowledge-notify
plan: 03
subsystem: agent-tools
tags: [tool-surface, multi-call, return_direct, args_schema, refactor, TOOLS-01]
dependency_graph:
  requires:
    - StartWorkflowTool (Phase 07.1 terminal-tool surface — superseded by D-03)
    - NonEmptyHouseholdId (Phase 16)
  provides:
    - StartWorkflowTool (non-terminal multi-call surface — D-03)
    - AddRecipeQueryInput {value: str}
  affects:
    - tests/unit/test_start_workflow_tool.py (rewritten for new schema)
    - Future plan 21-04 (jobs.py tool injection — wire-compatible: constructor injection unchanged)
tech_stack:
  added: []
  patterns:
    - typed-input-models-co-located-in-task_types.py
    - extra=forbid-on-both-outer-and-inner-pydantic-schemas
key_files:
  created: []
  modified:
    - src/robotina/queue/task_types.py
    - src/robotina/agent/tools/start_workflow.py
    - tests/unit/test_start_workflow_tool.py
decisions:
  - "D-03 applied: StartWorkflowTool flipped to non-terminal (return_direct=False), args_schema now {workflow_type: Literal['add-recipe'], input: AddRecipeQueryInput}."
  - "Robustness pacifier: _run accepts both AddRecipeQueryInput instances AND raw dicts (validated on entry). Test paths and the LangChain ToolNode both work without surprise."
metrics:
  duration: ~12 minutes
  tasks_completed: 3
  files_modified: 3
  tests_passing: 20
  completed: 2026-05-19
---

# Phase 21 Plan 03: StartWorkflowTool Refactor Summary

Multi-call non-terminal surface for `StartWorkflowTool` via `return_direct=False` and a typed `{workflow_type, input: AddRecipeQueryInput}` args schema (D-03, TOOLS-01).

## What changed

### `src/robotina/queue/task_types.py`
- Added `AddRecipeQueryInput {value: str}` with `model_config = ConfigDict(extra="forbid")`, co-located with `RecipeResearchInput`.
- Added `ConfigDict` to the pydantic import.
- `AcknowledgeAddRecipeInput` left untouched (its deletion belongs to a later plan).

### `src/robotina/agent/tools/start_workflow.py`
- `StartWorkflowArgs.input: AddRecipeQueryInput` replaces the flat `recipe_query: str` field. Both outer args and inner input model use `extra="forbid"`.
- `StartWorkflowTool.return_direct = False` (was `True`).
- `_run(workflow_type, input)` unwraps `input.value` at entry and feeds the resulting `recipe_query` into the existing shared_context build path — the downstream `workflow_runner.queue_workflow` call is byte-identical to before.
- `_run` also accepts a raw `dict` for `input` (pydantic-validates on entry) so direct test calls and edge cases don't surprise. Production goes through the LangChain ToolNode which already coerces dicts to the args_schema before calling `_run`.
- Constructor-injected fields (`chat_id`, `user_id`, `platform`, `household_id` with `NonEmptyHouseholdId`) preserved verbatim — wire-compatible with the upcoming `jobs.py` tool-injection rewire in plan 21-04.
- Description rewritten to advertise multi-call surface in Spanish ("podes llamarme varias veces") and the `terminate()` handoff. The old Phase 07.1 "do not call this tool again" / "shared_context" hacks remain absent.
- Module + class docstrings reference D-03 for traceability (per the no-task-id-in-code memory: D-NN design refs are allowed; phase tags are not).

### `tests/unit/test_start_workflow_tool.py`
- Replaced the Phase 07.1 terminal-tool assertions with the D-03 non-terminal assertions:
  - `test_start_workflow_tool_is_non_terminal` — `return_direct is False`.
  - `test_start_workflow_tool_args_schema_uses_typed_input` — instantiates `StartWorkflowArgs(workflow_type='add-recipe', input={'value': 'lentejas'})`; asserts pydantic coerces to `AddRecipeQueryInput`.
  - `test_start_workflow_tool_rejects_flat_recipe_query` — the legacy flat field at the top level is rejected.
  - `test_start_workflow_tool_rejects_extra_fields` — outer `extra='forbid'` rejects unknown LLM-emitted keys.
  - `test_start_workflow_tool_inner_input_rejects_extra_fields` — inner `extra='forbid'` rejects unknown keys inside `input`.
  - `test_start_workflow_tool_run_unwraps_input` — `_run` puts `input.value` into `shared_context['recipe_query']`.
  - `test_start_workflow_tool_multi_call_independent` — two sequential `_run` calls produce two independent enqueues with the right values; no shared mutable state leaks (PITFALL 5 guard).
  - `test_start_workflow_tool_constructor_injection_unchanged` — chat_id/user_id/platform/household_id propagate to the instance.
  - `test_start_workflow_tool_description_advertises_multi_call` — Spanish multi-call language + `terminate` mentioned; old hack strings absent.
- Existing strict-schema guardrails kept and updated for the new shape: top-level identity-field rejection, Literal workflow_type narrowing, JSON-schema `additionalProperties: false`, empty/missing `household_id` rejection, regression for the legacy "do not call" / "shared_context" prompt hack.
- Total: 20 tests, all passing. Old `test_start_workflow_tool_short_circuits_create_agent` (which relied on `return_direct=True` short-circuit semantics) was removed — that engine-enforced behavior now lives with TerminateTool, which is delivered in a later plan.

## Verification

- `uv run pytest tests/unit/test_start_workflow_tool.py -v` → 20 passed.
- `uv run pytest tests/unit/ --deselect tests/unit/test_gateway_boot.py -q` → 137 passed (no regressions outside this plan's scope).
- `grep -c "return_direct.*True" src/robotina/agent/tools/start_workflow.py` → 0.
- `grep -c "return_direct.*False" src/robotina/agent/tools/start_workflow.py` → 4.
- `grep -c "input: AddRecipeQueryInput" src/robotina/agent/tools/start_workflow.py` → 4.
- `grep -c "recipe_query: str" src/robotina/agent/tools/start_workflow.py` → 0.
- `grep -c "class AddRecipeQueryInput" src/robotina/queue/task_types.py` → 1.
- `grep -c "class AcknowledgeAddRecipeInput" src/robotina/queue/task_types.py` → 1 (deletion belongs to a later plan).

## Commits

| Task | Type | Hash | Message |
|------|------|------|---------|
| 1 | feat | `7de25d9` | feat(21-03): add AddRecipeQueryInput to task_types |
| 2 | refactor | `68cff4a` | refactor(21-03): flip StartWorkflowTool to non-terminal multi-call surface |
| 3 | test | `47d7e3a` | test(21-03): update StartWorkflowTool tests for non-terminal multi-call surface |

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 — Bug] _run signature accepts both dict and AddRecipeQueryInput**
- **Found during:** Task 2 implementation (writing tests for Task 3).
- **Issue:** When tests call `_run` directly with `input=AddRecipeQueryInput(value=...)`, that works; but if a test or edge path passes `input={'value': '...'}` as a raw dict, the `.value` attribute access would raise AttributeError. The LangChain ToolNode does coerce, but direct `_run` calls don't.
- **Fix:** Added a small `isinstance(input, dict)` coercion at the top of `_run` that runs `AddRecipeQueryInput.model_validate(input)` when a dict is passed. The hot-path (LangChain ToolNode → already-validated model) is unchanged.
- **Files modified:** `src/robotina/agent/tools/start_workflow.py`.
- **Commit:** included in `68cff4a` (Task 2 commit).

**2. [Rule 1 — Bug] Acceptance criterion `grep -c "return_direct.*True" == 0` initially failed because the docstring referenced TerminateTool with `return_direct=True`**
- **Found during:** Task 2 post-implementation verification.
- **Issue:** Docstring mentions of `return_direct=True` (referring to the future TerminateTool) tripped the strict grep gate.
- **Fix:** Rewrote the two docstring references to use prose ("terminal flag set", "which sets the flag") instead of the literal `return_direct=True` token. Semantic meaning preserved.
- **Files modified:** `src/robotina/agent/tools/start_workflow.py`.
- **Commit:** included in `68cff4a` (Task 2 commit).

### Out of scope, deferred

- **`tests/unit/test_gateway_boot.py::test_main_exits_on_missing_household_id` failure** — pre-existing in the worktree; attempts to hit `api.telegram.org` and fails with `InvalidToken`. Not related to this plan's changes. Not fixed.
- **`tests/unit/test_agent_runner.py` line 382 references `task_input.recipe_query`** — that's the AcknowledgeAddRecipe agent path, which the next plan in this phase deletes. Not touched here.

## Threat Flags

None. The refactor narrows the LLM-controllable surface (typed `input: AddRecipeQueryInput` instead of free string), preserves all Phase 16 / 17 / 18 constructor-injected identity fields, and continues to reject top-level `household_id` / `reply_context` via `extra='forbid'`. The previously-removed WR-02 shadowing attack surface stays removed.

## Self-Check: PASSED

Verification commands run (all in `.claude/worktrees/agent-aad4cd269a48e0fe6`):

```
[ -f src/robotina/agent/tools/start_workflow.py ]  → FOUND
[ -f src/robotina/queue/task_types.py ]            → FOUND
[ -f tests/unit/test_start_workflow_tool.py ]      → FOUND
git log --oneline | grep 7de25d9                   → FOUND
git log --oneline | grep 68cff4a                   → FOUND
git log --oneline | grep 47d7e3a                   → FOUND
```
