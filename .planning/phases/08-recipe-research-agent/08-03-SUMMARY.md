---
phase: 08-recipe-research-agent
plan: 03
subsystem: agent
tags: [langchain, agent-registry, run-task, tool-injection, recipe-research]

# Dependency graph
requires:
  - phase: 08-recipe-research-agent plan 01
    provides: 4 I/O model pairs, updated add-recipe workflow
  - phase: 08-recipe-research-agent plan 02
    provides: WebSearchTool, recipe-research skill, 4 prompts
provides:
  - 4 AgentConfig entries in AGENT_REGISTRY for recipe-research sub-tasks
  - run_task() tool injection for recipe-research-gather (WebSearchTool) and recipe-research-ingredients (HouseholdManagerApiTool)
affects: [08-recipe-research-agent plan 04, 09-recipe-load-agent]

# Tech tracking
tech-stack:
  added: []
  patterns: [shared-skill-across-multiple-agents, selective-tool-injection-per-subtask]

key-files:
  created: []
  modified:
    - src/robotina/agent/agents.py
    - src/robotina/queue/jobs.py
    - tests/unit/test_agents_registry.py
    - tests/unit/test_prompts.py
    - tests/unit/test_skills.py

key-decisions:
  - "recipe-research-instructions and recipe-research-metadata need no elif blocks -- they only use the generic read-skill tool injection"
  - "WebSearchTool() takes no constructor args (TAVILY_API_KEY read at execution time); HouseholdManagerApiTool needs household_id from task_input"

patterns-established:
  - "Shared skill directory: multiple agent configs referencing the same skill (recipe-research) with sub-files loaded on demand"
  - "Selective tool injection: only sub-tasks that need external tools get elif blocks; others rely on generic read-skill"

requirements-completed: [RRECIPE-01, RRECIPE-02, RRECIPE-05]

# Metrics
duration: 3min
completed: 2026-03-30
---

# Phase 8 Plan 3: Agent Registry & Tool Injection Summary

**4 recipe-research sub-task AgentConfigs wired into AGENT_REGISTRY with selective WebSearchTool and HouseholdManagerApiTool injection in run_task()**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-30T17:39:42Z
- **Completed:** 2026-03-30T17:43:20Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- 4 AgentConfig entries added to AGENT_REGISTRY: recipe-research-gather, recipe-research-instructions, recipe-research-ingredients, recipe-research-metadata
- run_task() elif blocks added for WebSearchTool (gather) and HouseholdManagerApiTool (ingredients) injection
- 10 new unit tests: 4 registry, 4 prompt file existence, 2 skill structure tests
- Full unit test suite passes (74 tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add 4 AgentConfig entries to AGENT_REGISTRY** - `40780cd` (feat)
2. **Task 2: Add run_task() elif blocks for tool injection + prompt and skill tests** - `c60e9e8` (feat)

## Files Created/Modified
- `src/robotina/agent/agents.py` - Added 4 recipe-research AgentConfig entries with correct prompt paths, skill refs, and api_key_env
- `src/robotina/queue/jobs.py` - Added 2 elif blocks for recipe-research-gather (WebSearchTool) and recipe-research-ingredients (HouseholdManagerApiTool)
- `tests/unit/test_agents_registry.py` - 4 new tests verifying registry entries
- `tests/unit/test_prompts.py` - 4 new tests verifying prompt V001.md files exist and are non-empty
- `tests/unit/test_skills.py` - 2 new tests verifying recipe-research skill index and sub-files

## Decisions Made
- recipe-research-instructions and recipe-research-metadata do not get elif blocks in run_task() -- they only use the generic read-skill tool which is already injected for all agents with skills configured
- WebSearchTool() constructor takes no arguments (TAVILY_API_KEY is read inside _run() at execution time), while HouseholdManagerApiTool requires household_id from task_input

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All agent infrastructure wired: registry entries, tool injection, prompts, skills
- Ready for Plan 04 (combined experiment script) which tests the full 4-step pipeline

## Self-Check: PASSED

All files found. All commits verified.

---
*Phase: 08-recipe-research-agent*
*Completed: 2026-03-30*
