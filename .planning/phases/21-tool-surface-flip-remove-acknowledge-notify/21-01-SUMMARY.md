---
phase: 21-tool-surface-flip-remove-acknowledge-notify
plan: 01
subsystem: agent-tools
tags: [tools, respond, send-notification, non-terminal]
requires:
  - robotina.queue.task_types.SendNotificationInput
  - robotina.queue.task_types.NonEmptyHouseholdId
  - langchain_core.tools.BaseTool
provides:
  - RespondTool (non-terminal Spanish-replier)
affects:
  - (none — purely additive; QueueTool still in place until 21-04)
tech-stack:
  added: []
  patterns:
    - "Constructor-injected identity fields (chat_id/user_id/platform/household_id) shadowed from LLM via args_schema(extra=forbid)"
    - "at_front=True enqueue for user-facing replies (feedback_queue_at_front)"
    - "return_direct=False = non-terminal tool — Robotina can keep tool-calling in the same turn"
key-files:
  created:
    - src/robotina/agent/tools/respond.py
    - tests/unit/test_respond_tool.py
  modified: []
decisions:
  - "RespondTool uses str (not int) for chat_id/user_id — matches QueueTool and existing SendNotificationInput contract; deviates from plan's stated int typing"
  - "Implementation mirrors QueueTool enqueue call verbatim (same queue name, same kwargs, same task_type meta) — guarantees no behavior change vs. retired tool"
metrics:
  duration: ~5min
  completed: 2026-05-19
requirements: [TOOLS-02]
---

# Phase 21 Plan 01: RespondTool Summary

Added `RespondTool`, the non-terminal Spanish-replier tool that replaces the retired `QueueTool`. Enqueues a `send-notification` job at the front of the queue and returns the job_id, but unlike `QueueTool` does NOT terminate the agent turn — Robotina can chain `respond(...) → start-workflow(...) → terminate()` in one decision step.

## What Changed

- **Created** `src/robotina/agent/tools/respond.py`:
  - `class RespondTool(BaseTool)` with `name="respond"`, `return_direct=False`.
  - `args_schema=RespondArgs` (single field `text: str`, `extra="forbid"`).
  - Constructor-injected identity: `chat_id: str`, `user_id: str`, `platform: str`, `household_id: NonEmptyHouseholdId`.
  - `_run(text)` builds `SendNotificationInput(...)` and enqueues `robotina.queue.jobs.run_task` with `at_front=True`, `result_ttl=-1`, `failure_ttl=-1`, `meta={"task_type": "send-notification"}` — identical to QueueTool's enqueue call.
- **Created** `tests/unit/test_respond_tool.py` with 6 unit tests (construction, non-terminal flag, args schema accept/reject, enqueue contract, NonEmptyHouseholdId rejection).

## Verification

```
$ uv run pytest tests/unit/test_respond_tool.py -v
...
6 passed in 0.07s
```

Smoke check:
```
$ uv run python -c "from robotina.agent.tools.respond import RespondTool; t = RespondTool(chat_id='1', user_id='1', platform='telegram', household_id='hh-x'); assert t.return_direct is False and t.name == 'respond'"
OK
```

## Deviations from Plan

**1. [Rule 3 — type-mismatch fix] `chat_id` / `user_id` typed as `str`, not `int`**
- **Found during:** Task 1 — read of `src/robotina/agent/tools/queue.py` and `SendNotificationInput`.
- **Issue:** Plan's `<interfaces>` block declared `chat_id: int, user_id: int`. The actual codebase (QueueTool fields, `SendNotificationInput` fields) uses `str` throughout. Using `int` would break the contract with `SendNotificationInput(chat_id: str, user_id: str, ...)` at enqueue time.
- **Fix:** Used `str` for both, matching QueueTool exactly.
- **Files modified:** src/robotina/agent/tools/respond.py
- **Commit:** 7235a84

No other deviations — purely additive plan.

## TDD Gate Compliance

- RED: `f4fc1df` — `test(21-01)` commit, 6 failing tests with `ModuleNotFoundError`.
- GREEN: `7235a84` — `feat(21-01)` commit, all 6 tests pass.
- REFACTOR: not needed; implementation written minimally to match contract.

## Commits

| # | Hash | Type | Description |
|---|------|------|-------------|
| 1 | f4fc1df | test | add failing RespondTool unit tests (D-17) |
| 2 | 7235a84 | feat | add RespondTool (D-01) |

## Self-Check: PASSED

- [x] `src/robotina/agent/tools/respond.py` exists
- [x] `tests/unit/test_respond_tool.py` exists
- [x] Commits f4fc1df and 7235a84 present in `git log`
- [x] `class RespondTool` in respond.py
- [x] `return_direct: bool = False` set
- [x] `at_front=True` in enqueue call
- [x] `SendNotificationInput` imported and instantiated in `_run`
- [x] `uv run pytest tests/unit/test_respond_tool.py` passes (6/6)
