---
phase: quick-260509-ln9
plan: 01
subsystem: queue/workflow_runner
tags: [dead-letter, telegram, workflow, error-handling, notifications]
requires: []
provides: [dead-letter-notification-hook]
affects: [src/robotina/queue/workflow_runner.py, src/robotina/queue/jobs.py]
key-files:
  modified:
    - src/robotina/queue/workflow_runner.py
    - src/robotina/queue/jobs.py
    - tests/test_workflow_runner.py
decisions:
  - "Dead-letter hook is inline in on_step_failed (no separate module) — avoids premature abstraction per project convention."
  - "queue parameter defaults to None on on_step_failed so existing unit tests that don't pass a queue keep passing unchanged."
  - "reply_context validation requires non-empty platform/chat_id/user_id (truthy check, not just key presence) — empty strings count as missing."
  - "Errors from the dead-letter block are logged via logger.exception and swallowed — workflow is already FAILED, never cascade."
metrics:
  tasks_completed: 1
  files_modified: 3
  tests_added: 2
  tests_total: 15
  tests_passed: 15
  completed: 2026-05-09
---

# Quick Task 260509-ln9: Telegram Dead-Letter Notification on Terminal Failure — Summary

When a `WorkflowRun` is marked FAILED in `workflow_runner.on_step_failed`, the runner now enqueues a single `send-notification` job at the front of `agent-tasks` with a locked Spanish apology containing the failed workflow's type — closing the silent-failure gap that bounded retry (commit `f801814`) cannot cover.

## Commit

- **Hash:** `3aacd11`
- **Message:** `fix(quick-260509-ln9): dead-letter Telegram apology on terminal workflow failure`

## Files Modified

| File | Change |
|------|--------|
| `src/robotina/queue/workflow_runner.py` | `on_step_failed` signature gains optional `queue=None`; dead-letter hook appended after WorkflowRun-FAILED commit. Best-effort: try/except around the entire block; failure logs via `logger.exception` and swallows. |
| `src/robotina/queue/jobs.py` | Both `on_step_failed` call sites (line 108 in send-notification branch, line 203 in agent branch) now pass `_queue` as third argument. |
| `tests/test_workflow_runner.py` | Two new unit tests covering reply_context-present and reply_context-missing branches. |

## Tests Added

- `test_on_step_failed_enqueues_dead_letter_when_reply_context_present` — asserts exactly one enqueue with `at_front=True`, locked apology text including workflow_type in parens (`add-recipe`), `result_ttl=-1`, `failure_ttl=-1`, `meta={"task_type": "send-notification"}`, and a `SendNotificationInput` carrying the reply_context fields.
- `test_on_step_failed_skips_dead_letter_when_reply_context_missing` — asserts no enqueue and a WARN log mentioning `skipping dead-letter` and the `run_id`.

## Verification

```
$ uv run pytest tests/test_workflow_runner.py -x -v
============================== 15 passed in 0.03s ==============================
```

All 15 tests pass — 13 pre-existing (FAILED-marking, PENDING-cancellation, WorkflowRun-FAILED, ToolMessage extraction, etc.) plus the 2 new ones. No regressions.

Plan-level grep checks all PASS:
- `grep -n "on_step_failed" src/robotina/queue/jobs.py` → both callsites pass three args.
- `grep -n "Disculpá" src/robotina/queue/workflow_runner.py` → Argentine `Disculpá` present at line 413.
- `grep -n "at_front=True" src/robotina/queue/workflow_runner.py` → present at line 427 (project standing rule honored).

## End-to-End Telegram Verification

**Skipped.** Per BRIEF, end-to-end verification is optional and "if running this requires user action, skip and note in SUMMARY." The unit-test layer covers both branches (reply_context-present and missing) and the existing send-notification delivery path is exercised by other tests / production traffic, so the integration risk is low. The user can trigger a known-failing workflow on their dev environment if they want to confirm the apology lands in Telegram.

## Deviations from Plan

None. Plan executed exactly as written.

## Self-Check: PASSED

- File: `src/robotina/queue/workflow_runner.py` — FOUND, modified (signature + hook).
- File: `src/robotina/queue/jobs.py` — FOUND, modified (both callsites).
- File: `tests/test_workflow_runner.py` — FOUND, modified (2 new tests appended).
- Commit: `3aacd11` — FOUND in `git log`.
- All 15 unit tests in the target file pass on the freshly-committed worktree.
