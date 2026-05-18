---
phase: 260518-ksv-tighten-startworkflowtool-schema-flatten
plan: 01
subsystem: agent.tools
tags: [agent, tools, pydantic, schema-tightening, security]
dependency_graph:
  requires:
    - robotina.queue.task_types.NonEmptyHouseholdId
    - robotina.queue.workflow_runner.queue_workflow
    - WORKFLOW_REGISTRY (unchanged contract — "add-recipe" entry consumes
      shared_context["recipe_query"], shared_context["reply_context"],
      shared_context["household_id"])
  provides:
    - StartWorkflowArgs with flat {workflow_type: Literal["add-recipe"], recipe_query: str}
    - StartWorkflowTool._run(workflow_type, recipe_query) builds shared_context internally
  affects:
    - Phase 07 handle-incoming-message agent (LLM-facing tool schema surface)
tech_stack:
  added: []
  patterns:
    - "Literal narrowing on Pydantic args_schema → JSON-schema const (Pydantic v2
      emits `const: \"add-recipe\"` for a single-value Literal); LangChain
      `create_agent` tool-call path serializes this to the model."
    - "Structural defense over runtime defense: WR-02 identity-shadowing is
      eliminated by removing the dict surface, not by overwriting it inside _run."
key_files:
  created: []
  modified:
    - src/robotina/agent/tools/start_workflow.py
    - tests/unit/test_start_workflow_tool.py
decisions:
  - StartWorkflowArgs flattened — top-level recipe_query replaces shared_context dict surface
  - workflow_type constrained to Literal["add-recipe"]; hallucinations fail at args validation
  - shared_context dict constructed internally in _run; LLM has no schema surface to inject identity fields
  - No min_length=1 on recipe_query — out of scope; prior shared_context didn't validate it either
metrics:
  duration: ~5min
  completed: "2026-05-18"
requirements_completed:
  - QUICK-SW-01
  - QUICK-SW-02
  - QUICK-SW-03
---

# Quick Task 260518-ksv: Tighten StartWorkflowTool Schema (Flatten + Literal) Summary

**One-liner:** Flatten `StartWorkflowArgs` to top-level `recipe_query: str` and narrow `workflow_type` to `Literal["add-recipe"]`, eliminating the LLM-controlled `shared_context` dict surface and the WR-02 identity-shadowing attack vector structurally.

## What Changed

### `src/robotina/agent/tools/start_workflow.py`

- Added `from typing import Literal`.
- `StartWorkflowArgs` body replaced:
  - `workflow_type: str` → `workflow_type: Literal["add-recipe"]`.
  - `shared_context: dict` field **removed**; replaced by required top-level `recipe_query: str`.
  - `model_config = ConfigDict(extra="forbid")` retained — top-level identity-field injection (e.g. `household_id`, `reply_context`) now also rejected at args validation.
  - Docstring rewritten to enumerate the two structural guardrails.
- Tool `description` rewritten — no mention of `shared_context`. New JSON example: `{"workflow_type": "add-recipe", "recipe_query": "lentil soup"}`.
- Tool class docstring `Args (via _run)` block updated to describe `workflow_type` + `recipe_query`; mentions the internally-constructed shared_context dict.
- `_run(self, workflow_type: str, recipe_query: str) -> str` — new signature. Builds `shared_context` internally as `{"recipe_query": recipe_query, "reply_context": {platform, chat_id, user_id}, "household_id": self.household_id}` then calls `workflow_runner.queue_workflow(..., shared_context=shared_context, household_id=self.household_id, ...)` exactly as before.
- `_arun(self, workflow_type: str, recipe_query: str) -> str` — signature mirrors `_run` and delegates.
- `return_direct = True`, `args_schema = StartWorkflowArgs`, and the `NonEmptyHouseholdId` constructor field are **unchanged** — WR-02 / Phase 16 invariants preserved.
- Module-level `WR-02` comment block inside `_run` (re-asserting identity fields) was removed — no longer needed because the LLM no longer supplies a dict for the constructor to fight with.

### `tests/unit/test_start_workflow_tool.py`

- Five existing tests updated to pass `recipe_query=` instead of `shared_context=` (`returns_workflow_run_id_on_success`, `error_path_returns_string`, `auto_injects_reply_context`, `short_circuits_create_agent`, `args_schema_forbids_unknown_field`, `args_schema_allows_required_only`).
- `test_start_workflow_tool_description_no_prompt_level_stop_hack` — added assertion: `"shared_context" not in tool.description.lower()`.
- **New** `test_args_schema_rejects_top_level_household_id` — proves the new attack surface (LLM passing `household_id` or `reply_context` at the top level) is rejected by `extra='forbid'`. Replaces the implicit shadowing test that `auto_injects_reply_context` used to carry.
- **New** `test_args_schema_rejects_unknown_workflow_type` — proves `workflow_type="remove-recipe"` fails at args validation under the Literal, not at `WORKFLOW_REGISTRY` lookup.
- `auto_injects_reply_context` retained — still proves the constructor values flow into the internally-built dict.
- Six unchanged tests: `is_terminal_via_return_direct`, `description_no_prompt_level_stop_hack` (only one extra assertion), `args_schema_json_schema_forbids_extra`, `constructor_rejects_empty_household_id`, `constructor_requires_household_id_no_default`, `constructor_accepts_non_empty_household_id`.

## Commits

| Hash      | Type     | Subject                                                            |
| --------- | -------- | ------------------------------------------------------------------ |
| `c8541be` | refactor | flatten StartWorkflowTool args to top-level recipe_query           |
| `c792229` | test     | update StartWorkflowTool tests for flat schema                     |

## Verification

- `uv run pytest tests/unit/test_start_workflow_tool.py -v` → **14 passed in 0.31s** (12 prior + 2 new).
- `grep -nE "shared_context\s*[:=]" src/robotina/agent/tools/start_workflow.py` →
  only two matches, both inside `_run`: the internal dict construction (`shared_context: dict = {...}`) and the `workflow_runner.queue_workflow(shared_context=shared_context, ...)` call. The args schema and method signatures have **none**.
- `grep -n "shared_context" tests/unit/test_start_workflow_tool.py` → only the docstring/comment references, the captured-dict downstream-contract assertions (`captured["shared_context"]`, `shared = ...`), the new description guardrail (`assert "shared_context" not in tool.description.lower()`), and a docstring reference in the new top-level-rejection test. No test passes `shared_context=` as a kwarg or dict key to the tool.
- Smoke (Literal valid):
  `StartWorkflowArgs(workflow_type='add-recipe', recipe_query='x')` → OK.
- Smoke (Literal invalid):
  `StartWorkflowArgs(workflow_type='remove-recipe', recipe_query='x')` → `ValidationError` raised.
- `model_json_schema()` carries `additionalProperties: false`, `recipe_query` is a top-level required string, and `workflow_type` carries `const: "add-recipe"` (Pydantic v2's emission for a single-value `Literal`, equivalently acceptable to the plan's `enum: ["add-recipe"]`).

## Must-Haves — Truths

- LLM cannot omit `recipe_query` — `ValidationError` fires before `_run` if absent. ✓
- LLM cannot pass a `workflow_type` other than `'add-recipe'` — Literal narrows the JSON schema. ✓
- LLM cannot inject `household_id` / `reply_context` via tool args — `extra='forbid'` rejects them at the top level (the old shared_context dict surface is gone). ✓
- Constructor-injected `household_id` / `chat_id` / `user_id` / `platform` remain authoritative (WR-02 invariant preserved). ✓
- Happy-path tool call with `workflow_type='add-recipe'` + `recipe_query='...'` still returns the workflow_run_id string. ✓
- `return_direct=True` is unchanged — terminal-tool semantics intact. ✓
- `uv run pytest tests/unit/test_start_workflow_tool.py` passes (14/14). ✓

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `src/robotina/agent/tools/start_workflow.py` modified — verified (Task 1 commit).
- `tests/unit/test_start_workflow_tool.py` modified — verified (Task 2 commit).
- Commit `c8541be` — present in `git log`.
- Commit `c792229` — present in `git log`.
- Full test module passes under `uv run pytest tests/unit/test_start_workflow_tool.py -v`.
