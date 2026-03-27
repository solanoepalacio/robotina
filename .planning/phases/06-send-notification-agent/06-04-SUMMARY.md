---
phase: 06-send-notification-agent
plan: "04"
subsystem: agent
tags: [langwatch, langchain, experiment, send-notification, markdownv2, tracing]

# Dependency graph
requires:
  - phase: 06-02
    provides: SendNotificationTool and send_notification job integration
  - phase: 06-03
    provides: format-telegram-message skill + send-notification/V001.md prompt

provides:
  - Full experiment script for send-notification agent (experiments/send_notification.py)
  - 4 representative D-06 test cases exercising MarkdownV2 escaping edge cases
  - LangWatch trace path identical to production run_task() with metadata pinning

affects: [07-robotina-agent, 08-recipe-research-agent, 09-recipe-load-agent]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Experiment scripts mock tool._run with patch.object to capture output without live services"
    - "langwatch.trace() context manager + trace.update(metadata={...}) for per-run metadata pinning"
    - "Same LangWatch instrumentation path in experiment as production (langwatch.trace + LangChainTracer callback)"

key-files:
  created: []
  modified:
    - experiments/send_notification.py

key-decisions:
  - "Experiment uses same LangWatch instrumentation path as run_task() (langwatch.trace + LangChainTracer callback) — OBS-03 requirement"
  - "SendNotificationTool._run mocked via patch.object to capture formatted output without TELEGRAM_BOT_TOKEN"
  - "4 D-06 test cases locked: baseline plain text, structured data, bullet list, special characters stress test"
  - "prompt_version='V001' and experiment='send-notification' pinned on every trace (D-07/OBS-04)"

patterns-established:
  - "Experiment pattern: build agent same way as run_task(), mock per-job tools, wrap each case in langwatch.trace()"

requirements-completed: [OBS-03, OBS-05]

# Metrics
duration: 1min
completed: "2026-03-27"
---

# Phase 6 Plan 04: Send Notification Experiment Summary

**Full experiment script running send-notification agent against 4 MarkdownV2 stress-test cases with LangWatch tracing identical to production**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-27T16:09:43Z
- **Completed:** 2026-03-27T16:10:56Z
- **Tasks:** 1 (+ 1 auto-approved checkpoint)
- **Files modified:** 1

## Accomplishments

- Replaced experiments/send_notification.py stub with full implementation
- 4 D-06 test cases covering the MarkdownV2 escaping spectrum (plain text, structured data, list formatting, special characters)
- LangWatch trace context manager active for each case with metadata pinning (prompt_version, model, provider, experiment, case_label)
- SendNotificationTool._run mocked via patch.object — no TELEGRAM_BOT_TOKEN required to run
- Per-case escaping heuristic check (unescaped periods in decimals, unescaped !)
- Formatted output summary printed after all 4 cases with PASS/WARN/ERROR status

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement experiments/send_notification.py** - `5bcfd8f` (feat)
2. **Task 2: Verify experiment runs and LangWatch trace appears** - auto-approved (checkpoint:human-verify, auto_advance=true)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `experiments/send_notification.py` - Full experiment implementation replacing Phase 6 stub

## Decisions Made

- SendNotificationTool._run mocked via `patch.object` inside a `with` block so only the 4 experiment cases use the mock; the tool instance is still real for tool schema/name resolution
- Escaping check is a heuristic only (regex on digit.digit pattern, presence of `!`) — not exhaustive; WARN not ERROR for potential escaping issues
- LangChainTracer callback passed directly in RunnableConfig (no AgentLoggingHandler in experiment — production uses both, experiment needs only LangWatch tracing)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- 3 pre-existing unit test failures in test_observability.py (ImportError for `_setup_langwatch_in_workhorse`) confirmed pre-existing before this plan (present in prior commit). Out of scope per deviation rules — logged to deferred items.

## User Setup Required

To run the experiment, set:
- `SEND_NOTIFICATION_API_TOKEN` — API token for the LLM (Ollama doesn't need a real token)
- `LANGWATCH_API_KEY` — from LangWatch project settings
- `LANGWATCH_ENDPOINT` — LangWatch endpoint URL (optional for cloud)

Then: `uv run experiments.send_notification`

## Next Phase Readiness

- Phase 6 (send-notification-agent) is complete — all 4 plans delivered
- Phase 7 (robotina-agent) can begin: handle-incoming-message agent, household-manager skill update, prompt, tools
- Pre-existing test_observability.py failures should be addressed before Phase 7 test work begins

## Self-Check: PASSED

- `experiments/send_notification.py` — FOUND
- `.planning/phases/06-send-notification-agent/06-04-SUMMARY.md` — FOUND
- Commit `5bcfd8f` — FOUND

---
*Phase: 06-send-notification-agent*
*Completed: 2026-03-27*
