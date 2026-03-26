---
phase: 04-llm-module-and-agent-infrastructure
plan: "06"
subsystem: agent
tags: [python, langchain, langwatch, rq, pytest, tdd, prompts, otel]

# Dependency graph
requires:
  - phase: 04-llm-module-and-agent-infrastructure
    provides: run_task() universal job function (04-04), SkillSet + ReadSkillTool (04-05), LLM adapters (04-01), agents.py registry (04-02)
provides:
  - hello-world prompt file at canonical path src/robotina/agent/prompts/hello-world/V001.md
  - complete prompt unit tests (test_prompts.py) with real assertions
  - Phase 4 pipeline verified end-to-end: prompt file loaded by run_task(), LangWatch traces reach dashboard, agent logs fire in work-horse
affects:
  - Phase 5: workflow integration wraps run_task()
  - Phase 6: hello-world entry must be removed from agents.py when send-notification added

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Versioned prompt files at src/robotina/agent/prompts/<task-type>/V001.md"
    - "TDD: test stubs replaced with real assertions, then implementation created"
    - "Skill index appended to prompt_text in run_task() before create_agent() call"
    - "LangWatch initialized in work-horse subprocess (perform_job), not parent process, to avoid BatchSpanProcessor thread death on fork"
    - "LangChainTracer callback passed via RunnableConfig — explicit tracing per LangWatch 0.17.0 docs, not LangChainInstrumentor"
    - "logging.basicConfig(INFO) called in work-horse so logger.info() calls are not silently dropped"

key-files:
  created:
    - src/robotina/agent/prompts/hello-world/V001.md
  modified:
    - tests/unit/test_prompts.py
    - src/robotina/queue/jobs.py
    - src/robotina/queue/runner.py
    - src/robotina/agent/agents.py
    - tests/unit/test_agent_runner.py
    - tests/unit/test_observability.py

key-decisions:
  - "Prompt path is relative to CWD (project root) — tests must run from project root via uv run pytest"
  - "test_skill_index_appended_to_prompt patches AGENT_REGISTRY in-process to inject a fake skill, then restores original — avoids filesystem side effects"
  - "LangWatch must be initialized in the work-horse (perform_job), not in main() — BatchSpanProcessor background thread dies on fork, causing silent trace drops"
  - "LangChainInstrumentor dropped; explicit LangChainTracer callback used in run_task() via RunnableConfig — per LangWatch 0.17.0 recommended pattern"
  - "on_llm_start renamed to on_chat_model_start in AgentLoggingHandler — LangChain routes chat model events to on_chat_model_start, not on_llm_start"

patterns-established:
  - "Prompt versioning: src/robotina/agent/prompts/<task-type>/V<NNN>.md format"
  - "Unit test for skill appended: patch make_backend + SkillSet + build_read_skill_tool; inject registry entry with fake skill; assert system_prompt arg contains skill content"
  - "Work-horse LangWatch init: reset Client._reset_instance() + OTel Once guard before langwatch.setup() to clear inherited fork state"

requirements-completed: [AGENT-08, AGENT-11]

# Metrics
duration: ~19h (includes human checkpoint verification)
completed: 2026-03-26
---

# Phase 04 Plan 06: Hello-World Prompt and End-to-End Pipeline Verification Summary

**Hello-world prompt V001.md, full Phase 4 unit suite (31 tests), and manual E2E verification confirmed — LangWatch traces reach dashboard; work-horse logging fixed for both trace and log visibility**

## Performance

- **Duration:** ~19 hours (includes human checkpoint verification window)
- **Started:** 2026-03-26T00:08:43Z
- **Completed:** 2026-03-26T19:33:20Z
- **Tasks:** 3 of 3 complete (Tasks 1-2 automated + TDD; Task 3 human-verify approved)
- **Files modified:** 6

## Accomplishments

- Created `src/robotina/agent/prompts/hello-world/V001.md` with Phase 4 Placeholder content
- Replaced all stub tests in `test_prompts.py` with real assertions verifying prompt file existence, AgentConfig path, and skill index appended to prompt
- Confirmed full unit suite (31 tests) and all integration tests (42 tests) pass with 0 failures
- Human-verified: worker starts cleanly, hello-world job enqueued and processed, LangWatch traces visible in dashboard, agent log lines fire in worker console
- Fixed LangWatch work-horse integration: traces now reach LangWatch by initializing in the forked subprocess instead of the parent process
- Fixed AgentLoggingHandler: renamed `on_llm_start` to `on_chat_model_start` so log lines fire for chat models
- Adopted explicit `LangChainTracer` callback approach (LangWatch 0.17.0 docs) — dropped `LangChainInstrumentor`

## Task Commits

Each task was committed atomically:

1. **TDD RED — test_prompts.py failing tests** - `a72c49f` (test)
2. **TDD GREEN — hello-world/V001.md prompt file** - `211db2a` (feat)
3. **Task 2 verification — full test suite pass** - `09a16bc` (chore)
4. **Task 3 checkpoint reached (pre-verification state)** - `5e7038b` (docs)
5. **Post-checkpoint fixes — LangWatch work-horse + logging** - `58584bc` (fix)

_Note: Task 1 used TDD: RED commit (a72c49f) then GREEN commit (211db2a). No refactor needed._

## Files Created/Modified

- `src/robotina/agent/prompts/hello-world/V001.md` - Phase 4 placeholder system prompt for hello-world task type
- `tests/unit/test_prompts.py` - Real assertions replacing pytest.skip() stubs (3 tests: file exists, config path loads, skill index appended)
- `src/robotina/queue/runner.py` - LangWatch moved from main() to perform_job() (work-horse); explicit reset of singleton + OTel Once guard before re-init; logging.basicConfig(INFO) in work-horse
- `src/robotina/queue/jobs.py` - on_llm_start renamed to on_chat_model_start; explicit langwatch.trace() + LangChainTracer() in run_task(); graceful ImportError fallback
- `src/robotina/agent/agents.py` - hello-world model updated to gpt-oss:20b (local test model)
- `tests/unit/test_agent_runner.py` - Updated test name and call to match on_chat_model_start
- `tests/unit/test_observability.py` - Updated test names and imports to match renamed _setup_langwatch_in_workhorse

## Decisions Made

- Prompt path is relative to CWD (project root) — verified against `run_task()` implementation in `jobs.py` which uses `Path(config.prompt_path).read_text()`
- `test_skill_index_appended_to_prompt` mutates `AGENT_REGISTRY` in-process to inject a fake skill (with `try/finally` restore) — cleanest approach without filesystem side effects
- LangWatch must be initialized in the work-horse (perform_job), not in main() — BatchSpanProcessor background thread dies on fork; child inherits a provider with a dead export thread causing silent trace drops
- Explicit `LangChainTracer` callback passed via `RunnableConfig` to `agent.invoke()` — drops LangChainInstrumentor auto-instrumentation approach per LangWatch 0.17.0 docs
- `on_chat_model_start` replaces `on_llm_start` in AgentLoggingHandler — LangChain routes chat model events to on_chat_model_start, not on_llm_start

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] LangWatch trace drops due to BatchSpanProcessor thread death on fork**
- **Found during:** Task 3 (manual E2E verification)
- **Issue:** `langwatch.setup()` called in main process. After `os.fork()`, the child work-horse inherits a `TracerProvider` whose `BatchSpanProcessor` export thread is dead — all spans are silently dropped, no traces reach LangWatch dashboard
- **Fix:** Moved LangWatch initialization to `perform_job()` (work-horse subprocess). Added `Client._reset_instance()` and reset of OTel `_TRACER_PROVIDER_SET_ONCE` to clear inherited singleton state before re-init. Dropped `LangChainInstrumentor`; adopted explicit `LangChainTracer()` callback per LangWatch 0.17.0 docs
- **Files modified:** `src/robotina/queue/runner.py`, `src/robotina/queue/jobs.py`, `tests/unit/test_observability.py`
- **Verification:** Traces visible in LangWatch dashboard during manual E2E run
- **Committed in:** `58584bc`

**2. [Rule 1 - Bug] AgentLoggingHandler log lines silently dropped in work-horse**
- **Found during:** Task 3 (manual E2E verification)
- **Issue:** `logger.info()` calls silently suppressed — Python's last-resort handler only outputs WARNING+. Work-horse subprocess had no basicConfig call, so INFO-level messages from `AgentLoggingHandler` were dropped
- **Fix:** Added `logging.basicConfig(level=logging.INFO)` at the start of `perform_job()` before any logging calls
- **Files modified:** `src/robotina/queue/runner.py`
- **Verification:** Log lines visible in worker console during manual E2E run
- **Committed in:** `58584bc`

**3. [Rule 1 - Bug] on_llm_start never fires for chat models**
- **Found during:** Task 3 (manual E2E verification)
- **Issue:** `AgentLoggingHandler.on_llm_start` defined but never called — LangChain routes events from chat models to `on_chat_model_start`, not `on_llm_start`. LLM stream start log line never appeared
- **Fix:** Renamed `on_llm_start` to `on_chat_model_start` with matching signature (`messages: list` instead of `prompts: list`)
- **Files modified:** `src/robotina/queue/jobs.py`, `tests/unit/test_agent_runner.py`
- **Verification:** "LLM stream start" log line appears in worker console during E2E run
- **Committed in:** `58584bc`

---

**Total deviations:** 3 auto-fixed (3 bugs found during manual E2E verification)
**Impact on plan:** All three bugs were silent failures invisible to unit tests — only surfaced during live E2E run with real subprocess forking and LangChain chat model invocation. All fixes necessary for correctness. No scope creep.

## Issues Encountered

- LangWatch SDK docs divergence: the plan referenced `LangChainInstrumentor` as the tracing approach, but LangWatch 0.17.0 docs recommend explicit `LangChainTracer` callback via `RunnableConfig`. Adopted the documented 0.17.0 approach.

## User Setup Required

None — external services (LangWatch, Ollama) were configured by the user before the manual checkpoint. No additional setup required for Phase 5.

## Known Stubs

None — the hello-world prompt is a Phase 4 placeholder by design (documented in CONTEXT.md D-06 and in the prompt file itself): "This agent is a placeholder. It will be removed in Phase 6 when the send-notification agent is added." This is intentional and self-documented.

## Next Phase Readiness

Phase 4 is fully complete. Phase 5 (workflow registry + task-runner advancement) can begin:

- All 31 Phase 4 unit tests pass (0 failures, 0 errors)
- Full integration test suite green (42 tests)
- Hello-world prompt provides end-to-end pipeline proof
- LangWatch traces confirmed reaching dashboard
- Work-horse logging confirmed firing (both INFO logs and LangWatch spans)
- run_task() universal job function ready to be wrapped by Phase 5 workflow advancement logic

---
*Phase: 04-llm-module-and-agent-infrastructure*
*Completed: 2026-03-26*
