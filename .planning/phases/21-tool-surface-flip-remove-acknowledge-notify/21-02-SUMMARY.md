---
phase: 21-tool-surface-flip-remove-acknowledge-notify
plan: 02
subsystem: agent/tools
tags: [tools, terminate, return-direct, pitfall-4, d-02]
requires: []
provides:
  - "TerminateTool — no-arg LangChain BaseTool with return_direct=True"
  - "TerminateArgs — empty Pydantic v2 args schema with extra=forbid"
affects: []
tech-stack:
  added: []
  patterns:
    - "return_direct=True for engine-enforced termination (PITFALL 4)"
    - "Pydantic v2 BaseModel with ConfigDict(extra='forbid') as args_schema"
key-files:
  created:
    - src/robotina/agent/tools/terminate.py
    - tests/unit/test_terminate_tool.py
  modified: []
decisions:
  - "D-02 (TerminateTool shape): no-arg BaseTool, return_direct=True, _run returns 'turn-terminated' sentinel ignored by engine"
  - "Args schema uses extra='forbid' so the no-arg contract is enforced by Pydantic, not just documented"
metrics:
  duration: "~3m"
  completed: 2026-05-19
  tasks: 2
  files: 2
---

# Phase 21 Plan 02: TerminateTool Summary

Added `TerminateTool`, a no-argument LangChain `BaseTool` with `return_direct=True` that gives the agent loop an explicit, engine-enforced termination point (PITFALL 4 mitigation) without coupling termination to any per-turn context.

## What Was Built

- **`src/robotina/agent/tools/terminate.py`** — `TerminateTool` (BaseTool subclass) and `TerminateArgs` (empty Pydantic v2 model with `extra="forbid"`).
  - `name = "terminate"`
  - `return_direct: bool = True` — load-bearing flag; `langchain.agents.create_agent` terminates the graph immediately after the tool runs.
  - `_run` returns the sentinel string `"turn-terminated"`. The engine never surfaces this to the model; it exists only so middleware tracing does not log `None`.
  - No constructor-injected fields. Termination is context-free.
- **`tests/unit/test_terminate_tool.py`** — 5 unit tests pinning the contract:
  - constructs with no args
  - `return_direct is True`
  - `name == "terminate"`
  - `_run()` returns a non-empty string
  - `TerminateArgs(foo="bar")` raises `pydantic.ValidationError`

## Why

Without an explicit `terminate()` tool flagged `return_direct=True`, the LLM can emit trailing free-text after its last real tool call — exactly the PITFALL 4 failure mode the phase is mitigating. Making termination a tool call (rather than a prompt-level convention) gives us a machine-checkable turn boundary. `return_direct=True` is the engine-level lever that actually enforces it; `Command(goto=END)` from a tool does NOT short-circuit the prebuilt graph (verified empirically in prior phases — see `src/robotina/agent/tools/queue.py` notes).

## Commits

| Task | Description                              | Commit  |
| ---- | ---------------------------------------- | ------- |
| 1    | feat(21-02): add TerminateTool           | e3a3ae6 |
| 2    | test(21-02): add unit tests for TerminateTool | 3576bbe |

## Verification

- `grep -c "class TerminateTool" src/robotina/agent/tools/terminate.py` → 1
- `grep -c "return_direct.*True" src/robotina/agent/tools/terminate.py` → 4
- `grep -cE 'name.*=.*"terminate"' src/robotina/agent/tools/terminate.py` → 1
- `uv run python -c "from robotina.agent.tools.terminate import TerminateTool; t=TerminateTool(); assert t.return_direct is True and t.name=='terminate' and t._run()"` → exit 0 (prints `OK terminate True turn-terminated`)
- `uv run pytest tests/ -k terminate_tool -q` → `5 passed, 274 deselected`

## Deviations from Plan

None — plan executed exactly as written. The implementation in `terminate.py` matches the code sketch in `<action>` verbatim aside from docstring expansion and a `from __future__ import annotations` for forward-compat with the `type[BaseModel]` annotation. The "no other file edits" success criterion is satisfied; no registry, agent, or middleware changes were made (those are for later plans in this phase).

## Decisions Made

- **D-02 (interface shape)** — kept verbatim from the plan: empty `TerminateArgs`, `return_direct=True`, string sentinel return.
- **Pydantic enforcement of no-arg contract** — used `ConfigDict(extra="forbid")` on `TerminateArgs` so the "takes no arguments" promise in the tool's description is enforced at schema-validation time, not just at the prose level. Tested explicitly via `test_terminate_tool_rejects_extra_args`.

## Known Stubs

None.

## Threat Flags

None — the tool is a pure no-op signal with no I/O, no network, no state.

## Self-Check: PASSED

- `src/robotina/agent/tools/terminate.py` → FOUND
- `tests/unit/test_terminate_tool.py` → FOUND
- Commit `e3a3ae6` → FOUND in `git log --all`
- Commit `3576bbe` → FOUND in `git log --all`
