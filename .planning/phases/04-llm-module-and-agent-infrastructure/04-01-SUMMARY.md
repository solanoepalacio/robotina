---
phase: 04-llm-module-and-agent-infrastructure
plan: "01"
subsystem: testing
tags: [pytest, unit-tests, stubs, gateway, rq, wave-0]

# Dependency graph
requires:
  - phase: 03-gateway
    provides: gateway handler enqueue call and test patterns

provides:
  - tests/unit/ package with 30 stub tests covering all Phase 4 requirements (AGENT-01 through AGENT-11, OBS-01, OBS-02)
  - gateway handler corrected to enqueue robotina.queue.jobs.run_task (not handle_incoming_message)

affects:
  - 04-02-agents-registry
  - 04-03-agent-runner
  - 04-04-skills
  - 04-05-prompts
  - 04-06-observability

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "pytest.skip('not implemented') stub pattern for Wave 0 test existence (inherited from Phase 3)"
    - "tests/unit/ directory as package for unit tests separate from integration tests"

key-files:
  created:
    - tests/unit/__init__.py
    - tests/unit/test_llm_backend.py
    - tests/unit/test_agents_registry.py
    - tests/unit/test_agent_runner.py
    - tests/unit/test_skills.py
    - tests/unit/test_prompts.py
    - tests/unit/test_observability.py
  modified:
    - src/robotina/gateway/handler.py

key-decisions:
  - "Gateway enqueue string changed from 'robotina.queue.jobs.handle_incoming_message' to 'robotina.queue.jobs.run_task' — meta=task_type unchanged; run_task reads task_type from meta to dispatch to correct agent (D-09)"

patterns-established:
  - "Unit test stubs: import pytest, define functions with docstrings citing requirement IDs, call pytest.skip('not implemented')"
  - "tests/unit/ for unit tests (no live services), tests/ root for integration tests requiring docker compose"

requirements-completed:
  - AGENT-01
  - AGENT-02
  - AGENT-03
  - AGENT-04
  - AGENT-05
  - AGENT-06
  - AGENT-07
  - AGENT-08
  - AGENT-09
  - AGENT-10
  - AGENT-11
  - OBS-01
  - OBS-02

# Metrics
duration: 2min
completed: 2026-03-25
---

# Phase 4 Plan 01: Wave 0 Prerequisites — Unit Test Stubs and Gateway Fix Summary

**30 Nyquist-compliant stub tests in tests/unit/ covering AGENT-01 through AGENT-11 and OBS-01/OBS-02, plus gateway corrected to enqueue robotina.queue.jobs.run_task**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-25T23:54:14Z
- **Completed:** 2026-03-25T23:55:38Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Created `tests/unit/` package with 7 files (init + 6 test modules), 30 stub tests that collect and report SKIPPED (exit 0)
- Fixed gateway `q.enqueue()` string from placeholder `handle_incoming_message` to the real universal job function `run_task`; gateway tests pass without regression (6/6)
- Established coverage mapping: each stub docstring cites the requirement ID it will verify when implemented

## Task Commits

Each task was committed atomically:

1. **Task 1: Create unit test package and all stub files** - `7a13345` (feat)
2. **Task 2: Fix gateway enqueue string to run_task** - `9ce08a7` (fix)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `tests/unit/__init__.py` - Empty package marker enabling pytest collection of unit/ directory
- `tests/unit/test_llm_backend.py` - 6 stubs: LLMBackend Protocol, Ollama/Anthropic/OpenAI adapters, env token reading, create_react_agent assertion
- `tests/unit/test_agents_registry.py` - 6 stubs: get_agent_config, AgentConfig fields, env var name storage, AGENT_OVERRIDES_FILEPATH hot reload, unknown task type error
- `tests/unit/test_agent_runner.py` - 6 stubs: task_type from job meta, ValueError on missing meta, per-job backend instantiation, AgentLoggingHandler callbacks
- `tests/unit/test_skills.py` - 5 stubs: SkillSet index loading, read-skill valid path, path traversal blocking, absolute path blocking, unknown skill error
- `tests/unit/test_prompts.py` - 3 stubs: hello-world prompt file existence, prompt loading from AgentConfig path, skill index appended to prompt
- `tests/unit/test_observability.py` - 4 stubs: setup_langwatch nonfatal on missing creds, reads API key and endpoint from env, configure_logging per module
- `src/robotina/gateway/handler.py` - q.enqueue() string changed from handle_incoming_message to run_task; meta unchanged

## Decisions Made

- Gateway enqueue string updated to `robotina.queue.jobs.run_task` as planned in D-09. The `meta={"task_type": "handle-incoming-message"}` key remains unchanged — this is what `run_task` reads to know which agent to dispatch to.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Wave 0 prerequisites complete: all 30 unit stubs exist, collect cleanly, and skip
- Gateway enqueues the correct job function
- Plans 04-02 through 04-06 can now implement against these stubs (TDD green phase)
- No blockers for Phase 4 continuation

## Self-Check: PASSED

- FOUND: tests/unit/__init__.py
- FOUND: tests/unit/test_llm_backend.py
- FOUND: tests/unit/test_agents_registry.py
- FOUND: tests/unit/test_agent_runner.py
- FOUND: tests/unit/test_skills.py
- FOUND: tests/unit/test_prompts.py
- FOUND: tests/unit/test_observability.py
- FOUND commit: 7a13345 (feat: unit test stubs)
- FOUND commit: 9ce08a7 (fix: gateway run_task)

---
*Phase: 04-llm-module-and-agent-infrastructure*
*Completed: 2026-03-25*
