---
phase: 07-handle-incoming-message-agent
plan: "04"
subsystem: agent
tags: [langchain, langgraph, rq, redis, agents, tools, household-manager]

requires:
  - phase: 07-02
    provides: HouseholdManagerApiTool, QueueTool implemented
  - phase: 07-03
    provides: robotina/V001.md prompt, household-manager shared.md rewritten

provides:
  - handle-incoming-message entry in AGENT_REGISTRY with household-manager skill and robotina/V001.md prompt
  - run_task() elif block injecting HouseholdManagerApiTool, QueueTool, StartWorkflowTool for handle-incoming-message jobs
  - Unit test coverage for registry entry, tool injection, prompt existence, and shared.md auth removal

affects:
  - phase-08-recipe-research-agent
  - phase-09-recipe-load-agent

tech-stack:
  added: []
  patterns:
    - "elif task_type == 'handle-incoming-message' in run_task() extends the per-job tool injection dispatch chain"
    - "AgentConfig.tools stays empty; all runtime context is injected per-job via elif blocks"

key-files:
  created: []
  modified:
    - src/robotina/agent/agents.py
    - src/robotina/queue/jobs.py
    - tests/unit/test_agents_registry.py
    - tests/unit/test_agent_runner.py
    - tests/unit/test_prompts.py
    - tests/unit/test_skills.py

key-decisions:
  - "handle-incoming-message uses HANDLE_INCOMING_MESSAGE_API_TOKEN env var (same {TASK_TYPE}_API_TOKEN convention)"
  - "All three tools (HouseholdManagerApiTool, QueueTool, StartWorkflowTool) instantiated in elif block inside run_task() — never at module level (locked Phase 4 constraint)"

patterns-established:
  - "Extend elif chain in run_task() for each new task type requiring per-job tool injection"

requirements-completed:
  - ROBOT-01
  - ROBOT-04
  - ROBOT-05
  - ROBOT-06
  - ROBOT-07

duration: 2min
completed: 2026-03-27
---

# Phase 07 Plan 04: Register handle-incoming-message and Wire Tools Summary

**handle-incoming-message registered in AGENT_REGISTRY with household-manager skill and three tools (HouseholdManagerApiTool, QueueTool, StartWorkflowTool) injected per-job in run_task()**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-27T20:26:58Z
- **Completed:** 2026-03-27T20:28:29Z
- **Tasks:** 1 auto (+ 1 checkpoint auto-approved)
- **Files modified:** 6

## Accomplishments

- Added handle-incoming-message entry to AGENT_REGISTRY with `household-manager` skill, `robotina/V001.md` prompt path, and `HANDLE_INCOMING_MESSAGE_API_TOKEN` env var
- Added elif block in run_task() that injects HouseholdManagerApiTool, QueueTool, and StartWorkflowTool for handle-incoming-message jobs
- Extended 4 test files with 6 new unit tests covering ROBOT-01, ROBOT-05, ROBOT-06 requirements; full 55-test suite passes

## Task Commits

Each task was committed atomically:

1. **Task 1: Register handle-incoming-message in agents.py + wire run_task() + extend tests** - `c4e3620` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/robotina/agent/agents.py` - Added handle-incoming-message AgentConfig entry after send-notification
- `src/robotina/queue/jobs.py` - Added elif task_type == "handle-incoming-message" block with all 3 tool injections
- `tests/unit/test_agents_registry.py` - Added 2 new tests: registry entry and API token env var
- `tests/unit/test_agent_runner.py` - Added test_run_task_injects_all_three_tools_for_handle_incoming_message
- `tests/unit/test_prompts.py` - Added test_prompt_file_exists_for_robotina
- `tests/unit/test_skills.py` - Added 2 tests verifying shared.md has no auth section or 401/403 rows

## Decisions Made

- handle-incoming-message uses HANDLE_INCOMING_MESSAGE_API_TOKEN env var following the {TASK_TYPE}_API_TOKEN convention from Phase 4
- All three tools instantiated inside the elif block — consistent with the locked Phase 4 constraint (never at module level)

## Deviations from Plan

None - plan executed exactly as written. The shared.md and robotina/V001.md files were already in correct state from Plans 07-02 and 07-03.

## Issues Encountered

None - all tests passed on first run.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 7 complete: handle-incoming-message agent fully wired with all tools, prompt, and skill
- Phase 8 (recipe-research-agent) can proceed: the routing agent can now call start-workflow to initiate recipe research
- Phase 9 (recipe-load-agent) follows after Phase 8

## Self-Check: PASSED

- agents.py: FOUND, handle-incoming-message entry present
- jobs.py: FOUND, HouseholdManagerApiTool injection present
- SUMMARY.md: FOUND
- Commit c4e3620: FOUND

---
*Phase: 07-handle-incoming-message-agent*
*Completed: 2026-03-27*
