---
phase: 20-wake-rule-outcome-plumbing
plan: 04
subsystem: queue + agent
tags: [wake-rule, invocation-lifecycle, dispatch, prompt]
requires: [20-01, 20-02]
provides:
  - "run_task dispatches handle-incoming-message on RobotinaInvocation.trigger"
  - "RobotinaInvocation lifecycle PENDING -> RUNNING -> DONE/FAILED with timestamps"
  - "V004 Robotina prompt with wake-context interpretation rule"
affects: [src/robotina/queue/jobs.py, src/robotina/agent/agents.py]
tech_added: []
patterns:
  - "trigger-based dispatch inside a stable task_type"
  - "defensive terminal-status helper invoked from outer try/except"
key_files:
  created:
    - "src/robotina/agent/prompts/robotina/V004.md"
    - "tests/queue/test_run_task_invocation_dispatch.py"
  modified:
    - "src/robotina/queue/jobs.py"
    - "src/robotina/agent/agents.py"
    - "tests/unit/test_agent_runner.py"
    - "tests/unit/test_agents_registry.py"
    - "tests/unit/test_prompts.py"
decisions:
  - "Wake branch uses conversation.chat_id as user_id placeholder (Conversation has no user_id column; V004 forbids queue/start-workflow on wake turns so the value is decorative)."
  - "Terminal status writes (DONE/FAILED + completed_at) live in a defensive helper invoked from the outer try/except. No _wake_branch_failed flag."
metrics:
  duration: "~30 minutes"
  completed: "2026-05-19"
---

# Phase 20 Plan 04: Trigger dispatch + invocation lifecycle + V004 prompt — Summary

run_task's handle-incoming-message branch now selects RobotinaInvocation by
job.meta['invocation_id'] and dispatches on inv.trigger (USER_MESSAGE vs
WORKFLOW_COMPLETION). The full invocation lifecycle (PENDING -> RUNNING -> DONE
or FAILED, with started_at and completed_at) is wired. V004 forks V003 with a
"Wake context" section that instructs the agent to emit assistant text (no tool
call) on wake turns; respond()/terminate() arrive in Phase 21.

## Tasks Executed

1. **Task 4.1 — V004 prompt** (commit `5f56038`). Forked
   `src/robotina/agent/prompts/robotina/V003.md` to V004 with a new "Wake
   context" section. V003 retained for rollback.
2. **Task 4.2 — agents.py points at V004** (commit `29bbc8e`). Single token
   swap on `AGENT_REGISTRY['handle-incoming-message'].prompt_path`.
3. **Task 4.3 — run_task dispatch + lifecycle + tests** (commit `e1f557f`).
   Refactored the handle-incoming-message branch, added a defensive
   `_write_invocation_terminal_status` helper for DONE/FAILED, created
   `tests/queue/test_run_task_invocation_dispatch.py` (6 tests, all pass), and
   updated 3 existing tests that mock the run_task session.

## Behavior Changes

| Surface | Before | After |
| --- | --- | --- |
| run_task handle-incoming-message branch | Only read `job.meta['invocation_id']` to construct StartWorkflowTool; existing tool-injection on the USER_MESSAGE shape only | Loads `RobotinaInvocation` from DB, writes RUNNING + started_at, branches tool injection on `inv.trigger`, writes DONE/FAILED + completed_at on terminal |
| RobotinaInvocation lifecycle | PENDING set by gateway; never updated | Full lifecycle: PENDING -> RUNNING -> DONE/FAILED with started_at/completed_at |
| Robotina prompt | V003 (no wake awareness) | V004 (V003 + Wake context section instructing assistant-text-only on wake turns) |
| Unsupported triggers (e.g. CRON) | N/A | Raise `RuntimeError("unsupported invocation trigger: ...")` |

## Deviations from Plan

### Rule 3 (Auto-fix blocking) — Conversation has no user_id column

The plan's wake branch action references `conversation.user_id`, but the
`Conversation` model in `src/robotina/gateway/models.py` exposes only
`platform`, `chat_id`, `household_id` — `user_id` lives transiently on
`IncomingMessageInput`, not on the DB row (group chats can have many users).

**Fix:** the wake branch uses `conversation.chat_id` as the `user_id` placeholder
for `QueueTool` and `StartWorkflowTool`. The choice is sound because V004
instructs the agent NOT to call those tools on wake turns; the placeholders
remain decorative until Phase 21 replaces the tool surface with `respond()` /
`terminate()`. Documented inline. **Commit:** `e1f557f`.

### Rule 1 (Auto-fix bug) — existing tests broke on trigger dispatch

Three pre-existing tests in `tests/unit/` (test_agent_runner, test_prompts,
test_agents_registry) failed after the refactor:

- `test_agent_runner.py` × 3 cases: mock_session.get returned a MagicMock whose
  `.trigger` was an unrecognized value, falling into the new `else` branch.
- `test_prompts.py` × 1 case: same root cause.
- `test_agents_registry.py` × 2 cases: pinned the prompt path to V003.md.

**Fix:** added `mock_session.get.return_value = <mock inv with USER_MESSAGE
trigger>` in each affected case, and bumped the prompt path assertions to
V004.md. All tests now green. **Commit:** `e1f557f`.

## Verification

Exit criteria from the task:

- `grep -c "inv\.trigger" src/robotina/queue/jobs.py` returns **3** (>= 2 required).
- `grep -c "InvocationStatus\." src/robotina/queue/jobs.py` returns **3** (>= 3 required: RUNNING, DONE, FAILED).
- `! grep -q "_wake_branch_failed" src/robotina/queue/jobs.py` — flag absent (exit 1).
- `test -f V003.md && test -f V004.md` — both present.
- `grep -c "V004" src/robotina/agent/agents.py` returns 4 (prompt path + comments).
- `uv run pytest tests/queue/test_run_task_invocation_dispatch.py -q` → **6 passed**.
- `uv run pytest tests/queue/ -q` → **20 passed**.
- `uv run pytest tests/unit/ tests/queue/ tests/dashboard/test_independence.py -q` → **165 passed**.

Pre-existing migration tests in `tests/test_workflow_runner.py` (`test_migration_0005..0007`) fail
because no live Postgres is available in this worktree; unrelated to plan 20-04.

## Self-Check: PASSED

- Files created (verified with `test -f`):
  - `src/robotina/agent/prompts/robotina/V004.md` — FOUND
  - `tests/queue/test_run_task_invocation_dispatch.py` — FOUND
  - `.planning/phases/20-wake-rule-outcome-plumbing/20-04-SUMMARY.md` — FOUND
- Commits (verified with `git log`):
  - `5f56038` — docs(20-04): add V004 Robotina prompt with wake-context section
  - `29bbc8e` — feat(20-04): point handle-incoming-message at V004 prompt
  - `e1f557f` — feat(20-04): dispatch run_task on invocation.trigger + lifecycle status
