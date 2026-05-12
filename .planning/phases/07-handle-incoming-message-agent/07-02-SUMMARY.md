---
phase: 07-handle-incoming-message-agent
plan: 02
subsystem: agent
tags: [langchain, httpx, rq, redis, tools, household-manager-api, queue]

# Dependency graph
requires:
  - phase: 07-01
    provides: test stubs for HouseholdManagerApiTool and QueueTool (SKIPPED)
  - phase: 06-send-notification-agent
    provides: SendNotificationTool pattern for per-job constructor injection via BaseTool
  - phase: 02-database-models-and-queue-layer
    provides: SendNotificationInput Pydantic model in robotina.queue.task_types
provides:
  - HouseholdManagerApiTool: generic httpx-based REST client with hard 401/403 auth-error semantics
  - QueueTool: RQ enqueue tool for send-notification follow-up tasks, enqueues at back of queue
affects:
  - 07-03 (agent assembly — both tools injected into agent per-job)
  - 07-04 (experiment — QueueTool mocked to capture reply text)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - asyncio.run() bridge: _run() calls asyncio.run(_call()) to bridge sync BaseTool to async httpx — safe in RQ subprocess (no event loop running)
    - Module-level imports for mockability: Redis/Queue imported at module top-level, not inside _run(), so patch() works correctly in unit tests
    - Per-job constructor injection: both tools receive per-request context (household_id, chat_id, user_id, platform) at construction inside run_task()

key-files:
  created:
    - src/robotina/agent/tools/household_manager_api.py
    - src/robotina/agent/tools/queue.py
  modified:
    - tests/unit/test_household_manager_api_tool.py
    - tests/unit/test_queue_tool.py

key-decisions:
  - "household_id stored at construction but NOT auto-injected into request URLs in Phase 7 — agent passes it in path/query where API requires it (D-02 scope deferral)"
  - "QueueTool enqueues at BACK of queue (no at_front=True) — gateway uses at_front because it originates outside the worker; follow-up tasks must not preempt waiting jobs (Pitfall 5)"
  - "Redis/Queue imports moved to module level in queue.py — lazy imports inside _run() make patch() target non-existent and break mocking"

patterns-established:
  - "Tool imports for mockability: RQ/Redis and similar injectable deps must be at module top-level, not inside _run()"
  - "Test headers extraction: use call_kwargs.kwargs.get('headers', {}) — operator precedence in ternary expression can silently return {} when headers are in kwargs"

requirements-completed: [ROBOT-02, ROBOT-03]

# Metrics
duration: 3min
completed: 2026-03-27
---

# Phase 7 Plan 02: HouseholdManagerApiTool and QueueTool Summary

**HouseholdManagerApiTool (httpx + asyncio.run bridge, hard 401/403 RuntimeError) and QueueTool (RQ enqueue-at-back, send-notification meta) — 11 unit tests passing, 0 skipped**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-27T20:18:19Z
- **Completed:** 2026-03-27T20:21:07Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Implemented HouseholdManagerApiTool: generic HTTP client that injects Bearer token, raises RuntimeError on 401/403, returns error dict on other non-2xx, returns parsed JSON on 2xx
- Implemented QueueTool: enqueues send-notification follow-up task to agent-tasks queue at back (no at_front=True), returns job.id string
- Replaced all 11 SKIPPED test stubs with passing implementations — full unit suite now 49 tests, all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement HouseholdManagerApiTool** - `a909201` (feat)
2. **Task 2: Implement QueueTool** - `db83e29` (feat)

**Plan metadata:** (docs commit — follows this summary)

## Files Created/Modified

- `src/robotina/agent/tools/household_manager_api.py` - HouseholdManagerApiTool: generic httpx client with auth injection and hard error semantics
- `src/robotina/agent/tools/queue.py` - QueueTool: RQ enqueue to agent-tasks queue at back of queue
- `tests/unit/test_household_manager_api_tool.py` - 7 tests (construction, bearer token injection, 401/403 RuntimeError, non-2xx error dict, 2xx JSON, household_id not in _run signature)
- `tests/unit/test_queue_tool.py` - 4 tests (construction, correct meta/ttl, enqueue-at-back, job.id return)

## Decisions Made

- household_id injection into request paths/params is deferred to a future phase. self.household_id is stored at construction for when skill files (recipes_get.md etc.) make endpoint patterns clear; in Phase 7 the agent includes household_id in path/query it passes.
- QueueTool must NOT use at_front=True — this was a critical Pitfall 5 in the plan. Gateway uses at_front because it pushes from outside the worker; agent follow-up tasks must queue behind pending work.
- Redis/Queue moved to module-level imports for correct mock patching behavior in tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed bearer-token test assertion: operator precedence in ternary silently returned `{}`**
- **Found during:** Task 1 (test run — `test_household_manager_api_tool_injects_bearer_token` FAILED)
- **Issue:** Plan-provided test expression `headers = call_kwargs.kwargs.get("headers") or call_kwargs.args[2] if len(call_kwargs.args) > 2 else {}` parses as `(... or ...) if len(call_kwargs.args) > 2 else {}` — since request args are all kwargs, `len(call_kwargs.args)` is 0, and the entire expression evaluates to `{}`.
- **Fix:** Simplified to `headers = call_kwargs.kwargs.get("headers", {})` — direct extraction with safe default.
- **Files modified:** tests/unit/test_household_manager_api_tool.py
- **Verification:** test now PASSED
- **Committed in:** a909201 (Task 1 commit)

**2. [Rule 1 - Bug] Moved Redis/Queue imports to module level in queue.py for patch() compatibility**
- **Found during:** Task 2 (test run — 3 tests FAILED with `AttributeError: module does not have attribute 'Queue'`)
- **Issue:** Plan specified Redis/Queue as lazy imports inside `_run()`. `unittest.mock.patch("robotina.agent.tools.queue.Queue", ...)` requires the attribute to exist at module level; lazy imports create no module-level binding.
- **Fix:** Moved `from redis import Redis` and `from rq import Queue` to module-level imports; removed from inside `_run()`.
- **Files modified:** src/robotina/agent/tools/queue.py
- **Verification:** All 4 QueueTool tests PASSED
- **Committed in:** db83e29 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both fixes necessary for test correctness. No scope creep — tool behavior unchanged.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Both tools ready for injection in run_task() in Plan 07-03 (agent assembly)
- HouseholdManagerApiTool: `HouseholdManagerApiTool(household_id=task_input.household_id)`
- QueueTool: `QueueTool(chat_id=task_input.chat_id, user_id=task_input.user_id, platform=task_input.platform)`
- Full unit suite at 49 tests, all passing — no regressions

## Known Stubs

None - all functionality is fully implemented and wired.

## Self-Check: PASSED

All created files found on disk. All task commits verified in git history.

---
*Phase: 07-handle-incoming-message-agent*
*Completed: 2026-03-27*
