# Decision: Migrate from `langgraph.prebuilt.create_react_agent` to `langchain.agents.create_agent`

## Context

The `LLMBackend.create_agent()` method in `src/robotina/llm/__init__.py` previously
wrapped `create_react_agent` from `langgraph.prebuilt`. This API is deprecated in
LangGraph V1.0 — calling it emits `LangGraphDeprecatedSinceV10`, and the
deprecation decorator (`langgraph/prebuilt/chat_agent_executor.py:274-308`)
points to `langchain.agents.create_agent` as the replacement.

The repo's `uv.lock` already pinned `langchain 1.2.13` and `langchain-core 1.2.22`,
so the new factory was already available in the venv. AGENT-11/D-03 (Phase 4
decision) explicitly deferred the migration to a "future phase" — Phase 10 was
that phase.

Two near-term phases also depend on this:
- Phase 11 needs `response_format=...` on the factory (only on `create_agent`).
- Phase 12 needs `middleware=[...]` on the factory (only on `create_agent`).

## What `create_react_agent` actually buys us

- It works today. Strict behavior we rely on (`return_direct=True`,
  `{"messages": [...]}` state shape, strict-args→ToolMessage(status='error'),
  callback delivery via `RunnableConfig`) is intact in `langgraph 1.1.3`.
- It was already wired into 5 source files and 4 test files with parity tests.

## Why those benefits don't apply here

- `langchain.agents.create_agent` provides byte-for-byte parity for every
  behavior the project relies on. Verified empirically against `langchain 1.2.13`
  on 2026-05-12 (return_direct short-circuit, system_prompt SystemMessage
  prepending, strict-args ToolMessage, callbacks via RunnableConfig — all
  identical).
- Staying on `create_react_agent` blocks Phases 11 and 12 from accessing
  `response_format=` and `middleware=`, which are the planned mitigations for
  the canelones-de-choclo parse failure class.
- Eventual removal in LangGraph V2.0 forces the migration anyway.

## Proposed change

1. Replace the import in `src/robotina/llm/__init__.py` from
   `from langgraph.prebuilt import create_react_agent` to
   `from langchain.agents import create_agent as _create_agent`. The alias
   prevents self-recursion with the protocol method of the same name.
2. Switch the three adapter call sites (`OllamaBackend`, `AnthropicBackend`,
   `OpenAIBackend`) from `create_react_agent(model=..., tools=..., prompt=...)`
   to `_create_agent(model=..., tools=..., system_prompt=...)`.
3. Update the four test files that construct real agent graphs
   (`test_llm_backend.py`, `test_queue_tool.py`, `test_start_workflow_tool.py`,
   `test_household_manager_api_tool.py`) to import and call `create_agent`.
4. Rename three tests for grep-discoverability: `..._short_circuits_create_react_agent`
   → `..._short_circuits_create_agent` (×2);
   `test_create_react_agent_used_not_agent_executor` →
   `test_create_agent_used_not_agent_executor` and invert its source-grep
   assertions to lock the migration direction.
5. Sweep stale comments/docstrings in 5 source files and 2 experiment files
   that mention `create_react_agent` or `langgraph.prebuilt`.
6. Update CLAUDE.md, PROJECT.md (Key Decisions), REQUIREMENTS.md (add
   AGENT-12, mark AGENT-11 superseded), and STATE.md (rewrite line 128).

## Files to change

- `src/robotina/llm/__init__.py` — import + 3 adapter call sites + Protocol
  docstring
- `tests/unit/test_llm_backend.py` — patch target rename, source-grep test
  inversion, per-adapter test docstrings
- `tests/unit/test_queue_tool.py` — import + factory call + test rename +
  module docstring
- `tests/unit/test_start_workflow_tool.py` — import + factory call + test
  rename + module docstring
- `tests/unit/test_household_manager_api_tool.py` — import + factory call (no
  test rename — name is behavior-based)
- `src/robotina/queue/jobs.py`,
  `src/robotina/queue/workflow_runner.py`,
  `src/robotina/agent/tools/queue.py`,
  `src/robotina/agent/tools/start_workflow.py`,
  `tests/test_workflow_runner.py`,
  `experiments/recipe_research.py`,
  `experiments/recipe_load.py` — comment/docstring sweep
- `CLAUDE.md` — 4 table-row edits (Core Technologies, Alternatives Considered,
  What NOT to Use, Confidence Notes)
- `.planning/REQUIREMENTS.md` — add AGENT-12, mark AGENT-11 superseded, add
  AGENT-12 to traceability
- `.planning/STATE.md` — rewrite line 128 decision log entry
- `.planning/PROJECT.md` — add row to Key Decisions table

## Risk

Low. The migration is a 1:1 API rename with empirically verified behavior parity.
Total functional diff is ~18 LOC plus ~20 LOC of doc/comment hygiene. Rollback
is a single `git revert` per affected commit; no data, no env vars, no lockfile
bumps. The only interaction-level risk is LangWatch trace delivery under the
new factory — covered by the end-to-end add-recipe checkpoint in Plan 03.
