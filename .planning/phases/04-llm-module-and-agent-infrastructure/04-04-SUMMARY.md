---
phase: 04-llm-module-and-agent-infrastructure
plan: "04"
subsystem: agent
tags: [rq, langchain, langwatch, opentelemetry, openinference, callbacks]

# Dependency graph
requires:
  - phase: 04-02
    provides: make_backend() factory + LLMBackend Protocol + OllamaBackend/AnthropicBackend/OpenAIBackend adapters
  - phase: 04-03
    provides: get_agent_config() + AgentConfig dataclass + configure_logging() + AGENT_REGISTRY

provides:
  - run_task() universal RQ job function in robotina.queue.jobs
  - AgentLoggingHandler LangChain callback handler (on_llm_start, on_tool_start, on_tool_end)
  - setup_langwatch() non-fatal LangWatch + OTel initialization in runner.py
  - configure_logging() and setup_langwatch() called at main() startup

affects: [phase-05-workflow, phase-06-agents, experiments]

# Tech tracking
tech-stack:
  added: [openinference-instrumentation-langchain (transitive via langwatch)]
  patterns:
    - Lazy imports inside run_task() for forward references to Plan 05 symbols (SkillSet, build_read_skill_tool)
    - Patch target is module-local name (robotina.queue.jobs.get_current_job) not rq.get_current_job
    - setup_langwatch() guards on both API key AND endpoint — non-fatal if either missing
    - LangChainInstrumentor passed via instrumentors= list to langwatch.setup()

key-files:
  created:
    - src/robotina/queue/jobs.py
  modified:
    - src/robotina/queue/runner.py
    - tests/unit/test_agent_runner.py
    - tests/unit/test_observability.py

key-decisions:
  - "Lazy import SkillSet and build_read_skill_tool inside run_task() to allow Plan 04 to run before Plan 05 is complete"
  - "Patch rq.get_current_job at robotina.queue.jobs.get_current_job (not rq module) — from-import creates module-local binding"
  - "setup_langwatch() is non-fatal by design — allows local dev without LangWatch credentials"

patterns-established:
  - "Pattern: Universal job function — one run_task() dispatches all task types via meta['task_type']"
  - "Pattern: Per-job backend instantiation — all LLM objects created inside run_task(), never at module level"
  - "Pattern: AgentLoggingHandler as sole logging point for agent action lifecycle"

requirements-completed: [AGENT-06, AGENT-10, OBS-01, OBS-02]

# Metrics
duration: 20min
completed: 2026-03-25
---

# Phase 04 Plan 04: RQ Job Function and LangWatch Observability Summary

**run_task() universal RQ job function with AgentLoggingHandler callbacks, and setup_langwatch() non-fatal OTel/LangWatch initialization wired into runner.main()**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-03-25T00:00:00Z
- **Completed:** 2026-03-25T00:20:00Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 4

## Accomplishments

- `run_task()` implemented as the single RQ job entry point for all task types — reads task_type from job meta, dispatches to correct AgentConfig
- `AgentLoggingHandler` logs LLM stream start, tool call, and tool result (200 char truncation on input/output)
- `setup_langwatch()` added to runner.py — guards on both env vars, logs warning and returns non-fatally if missing
- `configure_logging()` and `setup_langwatch()` both called at `main()` startup before Redis connection

## Task Commits

Each task was committed atomically using TDD:

1. **Task 1 RED: test_agent_runner failing tests** - `ec28c40` (test)
2. **Task 1 GREEN: implement jobs.py + fix test patches** - `b34835d` (feat)
3. **Task 2 RED: test_observability failing tests** - `66a2fd1` (test)
4. **Task 2 GREEN: update runner.py with setup_langwatch()** - `5ff52e3` (feat)

## Files Created/Modified

- `src/robotina/queue/jobs.py` (created) — run_task() universal job function + AgentLoggingHandler callback handler
- `src/robotina/queue/runner.py` (modified) — setup_langwatch() function + configure_logging()/setup_langwatch() calls in main()
- `tests/unit/test_agent_runner.py` (modified) — 6 unit tests for run_task() and AgentLoggingHandler
- `tests/unit/test_observability.py` (modified) — 4 unit tests for setup_langwatch() and configure_logging()

## Decisions Made

- Lazy imports for `SkillSet` and `build_read_skill_tool` inside `run_task()` allow this plan to execute before Plan 05 (skill loading) is complete — avoids circular import and missing symbol errors
- Patch target for RQ's `get_current_job` must be `robotina.queue.jobs.get_current_job` (not `rq.get_current_job`) because `from rq import get_current_job` creates a module-local binding at import time

## Deviations from Plan

**1. [Rule 1 - Bug] Fixed incorrect patch target in test_run_task_raises_if_no_task_type_in_meta**
- **Found during:** Task 1 GREEN (running tests after implementation)
- **Issue:** Initial tests used `patch("rq.get_current_job")` but jobs.py uses `from rq import get_current_job`, creating a module-local binding — patching the rq module had no effect after first import
- **Fix:** Changed all patches to `patch("robotina.queue.jobs.get_current_job")` — correct target for module-local binding
- **Files modified:** tests/unit/test_agent_runner.py
- **Verification:** All 6 tests pass with correct patch targets
- **Committed in:** b34835d (Task 1 feat commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Necessary correction for test isolation. No scope creep.

## Issues Encountered

- The first test (`test_run_task_reads_task_type_from_job_meta`) passed but the second test (`test_run_task_raises_if_no_task_type_in_meta`) got the first test's mock_job because the patch target was wrong. Fixed by using the module-local binding path.

## User Setup Required

None - no external service configuration required during this plan. LangWatch credentials (`LANGWATCH_API_KEY`, `LANGWATCH_ENDPOINT`) are needed for production observability but are optional for local development.

## Next Phase Readiness

- `run_task()` is ready but has forward references to `SkillSet` and `build_read_skill_tool` from Plan 05 — these lazy imports will fail until Plan 05 is complete
- Plan 05 (skill loading) must implement `SkillSet` and `build_read_skill_tool` in `robotina.agent`
- Plan 06 (agents) can then wire real agents using the complete pipeline

---
*Phase: 04-llm-module-and-agent-infrastructure*
*Completed: 2026-03-25*
