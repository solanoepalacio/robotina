---
phase: 12-middleware-based-agent-instrumentation
plan: 01
subsystem: observability
tags: [middleware, langchain, langchain-1.x, observability, logging, agents]

# Dependency graph
requires:
  - phase: 10-langchain-1-x-agent-api-migration
    provides: langchain.agents.create_agent factory + _create_agent alias in robotina.llm
  - phase: 11-structured-agent-output-via-response-format
    provides: kwargs-literal placement convention in LLMBackend.create_agent (response_format precedent)
provides:
  - robotina.agent.middleware module with three @wrap_model_call / @after_model / @wrap_tool_call singletons
  - middleware=[...] kwarg wired through all three LLMBackend.create_agent methods (Ollama / Anthropic / OpenAI)
  - Six unit tests at tests/unit/test_agent_middleware.py covering the four legacy log lines + 200-char truncation + handler.call_count == 1
  - Three middleware-presence tests appended to tests/unit/test_llm_backend.py (one per backend, by-identity assertion)
affects:
  - phase 12-02 (atomically removes AgentLoggingHandler + jobs.py wiring + the three legacy callback tests in test_agent_runner.py)
  - any future agent observability work (token budget, prompt-injection filter, dynamic prompt) — middleware is the recommended seam

# Tech tracking
tech-stack:
  added: []          # nothing new at the package level — langchain 1.2.13 / langgraph 1.1.3 / langwatch 0.17.0 already pinned
  patterns:
    - "Module-level @wrap_model_call / @after_model / @wrap_tool_call decorator singletons (each is an AgentMiddleware INSTANCE, not a class — passed by name without parens)"
    - "Mirror-edit convention: same kwargs-literal change applied identically to OllamaBackend / AnthropicBackend / OpenAIBackend (middleware is provider-agnostic)"
    - "Bound-method invocation pattern for testing middleware in isolation (log_around_model_call.wrap_model_call(request, handler)) — no full create_agent graph required"
    - "AGENT-13 / Phase 12 inline audit-trail marker carried at the introduction point (import in llm/__init__.py + import block in middleware.py)"

key-files:
  created:
    - src/robotina/agent/middleware.py
    - tests/unit/test_agent_middleware.py
    - .planning/phases/12-middleware-based-agent-instrumentation/12-01-SUMMARY.md
  modified:
    - src/robotina/llm/__init__.py
    - tests/unit/test_llm_backend.py

key-decisions:
  - "Used the wrap_model_call form for LLM start logging (not before_model) because before_model lacks access to the model object — wrap_model_call gives type(request.model).__name__ for byte-for-byte parity with the legacy 'LLM stream start | model=%s' line."
  - "Three middleware singletons composed as a list, not a single multi-hook AgentMiddleware subclass — stateless logging needs no shared instance state, and the function-decorator form is the LangChain example shape."
  - "Middleware list is identical across all three LLMBackend adapters (provider-agnostic) — placed in the kwargs literal immediately after system_prompt and before the response_format conditional, mirroring the Phase 11 placement convention."
  - "Plan 12-02 will atomically remove AgentLoggingHandler. This plan deliberately leaves the legacy callback in place to allow coexistence + a clean wave boundary (new path landed and proven green BEFORE old path is removed)."
  - "200-char truncation invariant preserved byte-for-byte: str(args)[:200] and str(result.content)[:200] — same V5/V7 ASVS log-injection / log-bloat boundary as the legacy callback."

patterns-established:
  - "Pattern A: Three function-decorator AgentMiddleware singletons (log_around_model_call / log_after_model / log_wrap_tool_call) exported from a single robotina.agent.middleware module with no import-time side effects beyond the singleton constructions"
  - "Pattern B: Direct bound-method invocation for middleware unit tests — log_xxx.wrap_model_call(request, handler) / log_xxx.after_model(state, runtime) / log_xxx.wrap_tool_call(request, handler) — sidesteps needing a real agent graph"
  - "Pattern C: Coexistence wave boundary — Plan A (12-01) lands the new path additively, Plan B (12-02) flips test fixtures and removes the legacy path atomically. Documented in the plan tasks and via the STATE.md decisions log."

requirements-completed:
  - OBS-06

# Metrics
duration: 4min
completed: 2026-05-14
---

# Phase 12 Plan 01: Middleware-Based Agent Instrumentation Summary

**LangChain 1.x agent middleware module + provider-agnostic wiring through all three LLMBackend.create_agent methods, preserving the four legacy log lines byte-for-byte alongside the still-present AgentLoggingHandler (Plan 12-02 removes it).**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-14T00:51:53Z
- **Completed:** 2026-05-14T00:55:12Z (approx — see commit timestamps)
- **Tasks:** 2 (both TDD, 4 commits total: RED → GREEN for each task)
- **Files created:** 2 (middleware module + middleware tests)
- **Files modified:** 2 (llm/__init__.py + test_llm_backend.py)

## Accomplishments

- **`robotina.agent.middleware` module created.** Three module-level `AgentMiddleware` singletons (`log_around_model_call`, `log_after_model`, `log_wrap_tool_call`) built via the LangChain 1.x decorators. Module import is side-effect-free beyond the three instance constructions — verified by `import` smoke check (`AgentMiddleware` appears in the MRO, no log output, no env reads). Confirmed import-side-effect-free posture via existing `test_backend_instantiated_per_job_not_module_level` still passing after wiring.
- **Four legacy log-line format strings preserved byte-for-byte**:
  - `LLM stream start | model=<ChatClassName>` (was `on_chat_model_start`)
  - `Thinking | <reasoning_content>` (was the reasoning_content branch of `on_llm_end`)
  - `Tool call | tool=<name> input=<args>` truncated to 200 chars (was `on_tool_start`)
  - `Tool result | output=<content>` truncated to 200 chars (was `on_tool_end`)
- **Middleware wired into all three backends.** `OllamaBackend.create_agent`, `AnthropicBackend.create_agent`, and `OpenAIBackend.create_agent` each pass the same `middleware=[log_around_model_call, log_after_model, log_wrap_tool_call]` list to `_create_agent`. Three new tests assert the wiring by identity for each backend.
- **Coexistence proof: 24/24 unit tests green.** The legacy `test_agent_logging_handler_*` tests at `test_agent_runner.py:152-176` still pass — `AgentLoggingHandler` and its `jobs.py` wiring are intentionally left in place for Plan 12-02 to remove atomically in Wave 2.

## Task Commits

Each task was TDD-committed atomically:

1. **Task 1.1 RED: failing middleware tests** — `4dc3413` (`test(12-01): add failing tests for create_agent middleware (OBS-06)`)
2. **Task 1.1 GREEN: middleware module** — `6303ab6` (`feat(12-01): add agent middleware module (OBS-06)`)
3. **Task 1.2 RED: backend middleware-presence tests** — `c07a3d6` (`test(12-01): assert middleware wired into all 3 backends (OBS-06)`)
4. **Task 1.2 GREEN: backend wiring** — `92b8bde` (`feat(12-01): wire middleware into LLMBackend.create_agent in all 3 backends (OBS-06)`)

**Plan metadata commit** — to be created next (`docs(12-01): complete middleware-based agent instrumentation plan 01`).

## Files Created/Modified

### Created
- `src/robotina/agent/middleware.py` (112 lines) — three `AgentMiddleware` singletons. Carries the `# AGENT-13 / Phase 12` audit-trail marker on the imports. Module docstring documents the stateless-module rule (Pitfall 4 from RESEARCH.md) and the OBS-06 / V5+V7 ASVS truncation invariant.
- `tests/unit/test_agent_middleware.py` (178 lines) — six pytest cases using `caplog.at_level(logging.INFO, logger="robotina.agent.middleware")` + function-local imports + `MagicMock` request/state/handler.

### Modified
- `src/robotina/llm/__init__.py` — added module-top `from robotina.agent.middleware import (...)` block, added `"middleware": [...]` key to all three `kwargs` literals, and extended the `LLMBackend.create_agent` Protocol docstring with a one-sentence note pointing to `robotina.agent.middleware` (preserves the existing AGENT-12 / Phase 11 mentions intact).
- `tests/unit/test_llm_backend.py` — appended three new tests (`test_ollama_create_agent_passes_middleware_to_factory`, `test_anthropic_…`, `test_openai_…`) that patch `robotina.llm._create_agent` and assert the captured kwargs contain `middleware=[log_around_model_call, log_after_model, log_wrap_tool_call]` by identity, in order, with length 3.

## Decisions Made

None beyond those already captured in `key-decisions` above and in PATTERNS.md / RESEARCH.md. The plan was paste-ready and executed exactly as specified — both files prescribed concrete code bodies and they landed verbatim aside from preserving the existing `# AGENT-12` style and adding the new `# AGENT-13 / Phase 12` marker.

## Deviations from Plan

None — plan executed exactly as written.

The plan offered two optional embellishments that were both adopted because they paid for themselves with no extra scope:
1. The recommended new `test_*_create_agent_passes_middleware_to_factory` tests (Task 1.2 RED step, optional but recommended) were added. These give explicit identity-pin coverage on the wiring contract; without them the only assertion that `middleware=[…]` got passed would be the implicit assertion that the middleware module's log lines appear during a full graph run — too indirect for a fast unit test layer.
2. Both TDD RED commits were created as separate commits (per plan instruction). Net commit count: 4 (test → feat × 2), matching the TDD-task convention.

## Confirmation of Plan-Level Contracts

- **Byte-for-byte log line preservation.** Verified by reading `src/robotina/agent/middleware.py` against `src/robotina/agent/callbacks.py`:
  - `"LLM stream start | model=%s"` — both files (callbacks.py line 25; middleware.py line 63)
  - `"Thinking | %s"` — both files (callbacks.py line 33; middleware.py line 84)
  - `"Tool call | tool=%s input=%s"` — both files (callbacks.py lines 36–40; middleware.py line 102)
  - `"Tool result | output=%s"` — both files (callbacks.py line 43; middleware.py line 107)
  - 200-char truncation: `str(args)[:200]` and `str(result.content)[:200]` mirror `str(input_str)[:200]` and `str(output)[:200]` in the legacy callback.
- **Module is import-side-effect-free** beyond the three `AgentMiddleware` instance constructions. Confirmed via:
  - `uv run python -c "import robotina.agent.middleware as m; print(type(m.log_around_model_call).__mro__)"` returns the MRO with `AgentMiddleware` present and emits no log output.
  - The existing `test_backend_instantiated_per_job_not_module_level` test continues to pass after the new middleware import was added to `src/robotina/llm/__init__.py` — proves no `ChatOllama` / `ChatAnthropic` / `ChatOpenAI` instantiation leaked into module-import time via the middleware path.
- **Legacy AgentLoggingHandler remains wired in `src/robotina/queue/jobs.py`.** Untouched in this plan by design. `git diff` on `src/robotina/queue/jobs.py` shows zero changes. Plan 12-02 owns its removal.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| (none) | — | No new security surface introduced. The 200-char truncation invariant from the legacy callback (V5/V7 ASVS log-injection / log-bloat mitigation) is preserved byte-for-byte and is covered by the dedicated regression test `test_log_wrap_tool_call_truncates_output_to_200_chars`. No new network endpoints, auth paths, file access, or schema changes. |

## Issues Encountered

None.

## Next Phase Readiness

- **Plan 12-02 can proceed.** It atomically removes:
  - `src/robotina/agent/callbacks.py` (the legacy `AgentLoggingHandler` class)
  - the import + two callback wirings in `src/robotina/queue/jobs.py` (lines 23, 195, 201)
  - the docstring step-7 mention of `AgentLoggingHandler` in `jobs.py`
  - the three legacy callback tests in `tests/unit/test_agent_runner.py` (lines 152–176, 325–340)
  - the third bullet (`AGENT-10: AgentLoggingHandler…`) in the test_agent_runner.py module docstring
- All test data needed by Plan 12-02 is now in place: `tests/unit/test_agent_middleware.py` is green and provides the replacement coverage for the three tests Plan 12-02 will delete.
- LangWatch trace fidelity remains unchanged in this plan (the LangChainTracer callback is untouched). Plan 12-02 will keep it that way — the diff there is also subtractive only (remove AgentLoggingHandler() from `callbacks=[...]`, never empty the list).

## Self-Check: PASSED

Verified all claimed artifacts exist and all claimed commits are reachable.

**Files claimed:**
- `src/robotina/agent/middleware.py` — FOUND (112 lines)
- `tests/unit/test_agent_middleware.py` — FOUND (178 lines)
- `src/robotina/llm/__init__.py` modifications — FOUND (24 inserted lines on commit `92b8bde`)
- `tests/unit/test_llm_backend.py` modifications — FOUND (104 inserted lines on commit `c07a3d6`)

**Commits claimed:**
- `4dc3413` — FOUND on `use-new-agent-version` (RED tests for middleware module)
- `6303ab6` — FOUND on `use-new-agent-version` (middleware module)
- `c07a3d6` — FOUND on `use-new-agent-version` (RED tests for backend wiring)
- `92b8bde` — FOUND on `use-new-agent-version` (backend wiring)

**Verification commands run:**
- `uv run pytest tests/unit/test_agent_middleware.py tests/unit/test_llm_backend.py tests/unit/test_agent_runner.py -x` → 24 passed
- `uv run python -c "import robotina.agent.middleware as m; print(type(m.log_around_model_call).__mro__)"` → returns MRO with `AgentMiddleware` present, no log output, no env reads, no network activity

---
*Phase: 12-middleware-based-agent-instrumentation*
*Completed: 2026-05-14*
