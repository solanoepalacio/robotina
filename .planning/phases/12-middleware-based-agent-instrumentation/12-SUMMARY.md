---
phase: 12-middleware-based-agent-instrumentation
plan: 02
subsystem: observability
tags: [middleware, langchain, langchain-1.x, langwatch, observability, callbacks, agents]

# Dependency graph
requires:
  - phase: 12-01
    provides: robotina.agent.middleware module (three @wrap_model_call / @after_model / @wrap_tool_call singletons) wired through all three LLMBackend.create_agent methods; 24/24 unit tests green proving coexistence with the legacy AgentLoggingHandler
  - phase: 11-structured-agent-output-via-response-format
    provides: kwargs-literal placement convention in LLMBackend.create_agent (response_format precedent)
  - phase: 10-langchain-1-x-agent-api-migration
    provides: langchain.agents.create_agent factory + _create_agent alias in robotina.llm
provides:
  - "Removal of legacy AgentLoggingHandler — src/robotina/agent/callbacks.py no longer exists"
  - "Subtractive diff in src/robotina/queue/jobs.py: callbacks list now [LangChainTracer()] only; ImportError fallback drops config= entirely"
  - "Two regression tests pinning the OBS-06 contract: tracer survives, legacy callback absent"
  - "Phase summary documenting the LangWatch + middleware interaction model (Phase SC#5)"
  - "REQUIREMENTS.md OBS-06 entry flipped to Complete (2026-05-14, after Task 2.3 manual smoke approval)"
affects:
  - any future agent observability work (token budget, prompt-injection filter, dynamic prompt) — middleware is now the SOLE per-agent logging seam
  - "Phase 999.1 (custom state schemas) — middleware can read typed AgentState once promoted from backlog"

# Tech tracking
tech-stack:
  added: []          # nothing new at the package level — langchain 1.2.13 / langgraph 1.1.3 / langwatch 0.17.0 already pinned
  patterns:
    - "Subtractive callbacks-list edit: remove handler from the list, never replace with []. RESEARCH Pitfall 1 (LangWatch trace fidelity)."
    - "ImportError fallback: when langwatch is missing, drop the config= kwarg entirely. Middleware emits log lines regardless of langwatch availability."
    - "Regression test pattern: side_effect on agent.invoke captures the config kwarg; class-name lookup avoids importing langwatch at test top level."
    - "AGENT-13 / Phase 12 inline audit-trail marker at every removal site (jobs.py: 3 locations)."

key-files:
  created:
    - .planning/phases/12-middleware-based-agent-instrumentation/12-SUMMARY.md
    - .planning/phases/12-middleware-based-agent-instrumentation/deferred-items.md
  modified:
    - src/robotina/queue/jobs.py
    - tests/unit/test_agent_runner.py
    - .planning/REQUIREMENTS.md
  deleted:
    - src/robotina/agent/callbacks.py

key-decisions:
  - "LangWatch callback wiring SURVIVES the migration. LangChainTracer inherits BaseCallbackHandler (langwatch 0.17.0 langchain.py:110) — the trace path is callback-bus-based. Removing the callbacks list would silently break ALL LangWatch traces."
  - "ImportError branch drops config= entirely (not config={'callbacks': []}). Middleware emits log lines without needing a callback; an empty callbacks list adds no value."
  - "test_run_task_no_legacy_callback asserts BOTH (a) robotina.agent.callbacks no longer importable AND (b) AgentLoggingHandler class absent from callbacks list. Belt-and-braces — either alone could regress silently."
  - "Three legacy callback tests deleted, not migrated. Their behavioral contract (the four log lines) is already covered by tests/unit/test_agent_middleware.py (created in Plan 12-01) — moving them would duplicate coverage."

patterns-established:
  - "Pattern A: Subtractive diff on RunnableConfig.callbacks — when removing one callback from a multi-callback list, the diff MUST leave the remaining callbacks (LangWatch in particular) untouched. Verified by the regression test that asserts LangChainTracer class is present."
  - "Pattern B: Atomic flip after coexistence proof — Wave 1 (12-01) added the new path, Wave 2 (12-02) removes the old path in one commit (single refactor commit). Test fixtures flipped in the same commit as the source change."
  - "Pattern C: Phase-summary documentation of the LangWatch interaction model — every observability migration in this codebase must record (a) whether LangWatch depends on the LangChain callback bus, (b) which BaseCallbackHandler subclass it uses, (c) the version that was verified. Future migrations grep for 'LangChainTracer' in phase summaries to find the prior verification."

requirements-completed:
  - OBS-06
requirements-pending: []

# Metrics
duration: ~6min (Tasks 2.1 + 2.2); Task 2.3 manual smoke approved 2026-05-14
completed: 2026-05-14
---

# Phase 12 Plan 02: Atomic flip to middleware-only per-agent instrumentation

**Deleted `src/robotina/agent/callbacks.py`; subtracted `AgentLoggingHandler()` from the `RunnableConfig.callbacks` list in `src/robotina/queue/jobs.py` while keeping `langwatch.langchain.LangChainTracer()` wired through the callback bus; pruned 3 legacy callback tests; added 2 OBS-06 regression tests. Phase 12 manual smoke gate (Task 2.3) remains BLOCKING.**

## Performance

- **Duration:** ~6 min (Tasks 2.1 + 2.2; Task 2.3 is human-gated and blocks the final state-update commit)
- **Started:** 2026-05-13 (post-12-01)
- **Tasks completed pre-checkpoint:** 2 of 3 (Task 2.1 atomic flip; Task 2.2 summary + REQUIREMENTS.md)
- **Files created:** 2 (this SUMMARY + deferred-items.md)
- **Files modified:** 3 (jobs.py, test_agent_runner.py, REQUIREMENTS.md)
- **Files deleted:** 1 (src/robotina/agent/callbacks.py)

## Accomplishments

- **`src/robotina/agent/callbacks.py` deleted.** Last reference in `src/robotina/` is gone. Grep gate `grep -r 'from langchain_core.callbacks' src/robotina/agent/` returns empty (success criterion 4 satisfied).
- **`src/robotina/queue/jobs.py` flipped to middleware-only.** Three coordinated edits:
  - Removed `from robotina.agent.callbacks import AgentLoggingHandler` import.
  - Updated docstring step 7 to reference middleware emission (`Create and invoke the agent (per-agent logging emitted by middleware; LangWatch trace via callback bus).`).
  - Subtractive diff on the `try`-branch `callbacks=[...]` list: now `[langwatch.langchain.LangChainTracer()]`. RESEARCH Pitfall 1 verified — list remains non-empty so LangWatch traces continue to flow.
  - Subtractive diff on the `except ImportError` branch: dropped the `config=` kwarg entirely. Middleware emits log lines regardless of whether langwatch is importable.
- **Three legacy `test_agent_logging_handler_*` tests pruned from `tests/unit/test_agent_runner.py`.** Module docstring updated to drop the AGENT-10 line and add an OBS-06 reference pointing to `test_agent_middleware.py`.
- **Two regression tests added.** `test_run_task_passes_langwatch_tracer` asserts the LangWatch callback class is present in the captured `RunnableConfig.callbacks`. `test_run_task_no_legacy_callback` asserts (a) `robotina.agent.callbacks` is no longer importable AND (b) `AgentLoggingHandler` class name absent from the callbacks list.
- **Affected-file unit slice green: 23/23 PASSED.** `tests/unit/test_agent_runner.py` (8 — 3 deleted, 2 added, net 7+1=8 active) + `tests/unit/test_agent_middleware.py` (6) + `tests/unit/test_llm_backend.py` (9).

## LangWatch + Middleware Interaction Model

This section satisfies phase-level success criterion #5.

**Finding (verified against installed langwatch 0.17.0 source):**

`langwatch.langchain.LangChainTracer` is itself a `BaseCallbackHandler` subclass (`.venv/lib/python3.12/site-packages/langwatch/langchain.py:110`). Therefore LangWatch traces are built ENTIRELY from LangChain callback events (`on_chat_model_start`, `on_llm_end`, `on_tool_start`, `on_tool_end`, `on_chain_*`, `on_agent_*`). LangWatch has **no callback-free integration path** in this version. The alternative auto-instrumentor (`openinference-instrumentation-langchain`, bundled with langwatch as a hard dependency) also works by monkey-patching `BaseCallbackManager.__init__` to inject an OTel-emitting `BaseCallbackHandler` — also callback-bus-based.

**Consequence for Phase 12:**

The migration is **NOT a rip-and-replace** of `RunnableConfig(callbacks=[...])`. It is a **removal of `AgentLoggingHandler` only**. The `langwatch.langchain.LangChainTracer` callback must stay wired through `RunnableConfig(callbacks=[...])`.

The diff in `src/robotina/queue/jobs.py` is therefore strictly subtractive on a multi-callback list:

```python
# Before (Plan 12-01 coexistence state):
callbacks=[AgentLoggingHandler(), langwatch.langchain.LangChainTracer()]

# After (this plan, atomic flip):
callbacks=[langwatch.langchain.LangChainTracer()]   # non-empty — invariant!
```

**No bridge layer was needed.** The phase initially feared that the LangWatch interaction would require a thin shim between middleware and the callback bus. Verification proved that fear unfounded: middleware emits its own log lines via Python's `logging` module (not via the callback bus), while LangWatch reads the callback bus independently. The two systems are orthogonal.

**Why middleware + LangChainTracer don't double-log:** Middleware emits log lines through `logger.info(...)` in `robotina.agent.middleware`. LangWatch traces are emitted via the LangChain callback bus directly to LangWatch's HTTP ingestion. They never share a transport.

## Remaining `from langchain_core.callbacks` imports — rationale

Phase-level success criterion #4 requires no `from langchain_core.callbacks` imports remain in `src/robotina/agent/`. **Verified satisfied:**

```
$ grep -rn 'from langchain_core.callbacks' src/robotina/agent/
(empty)
```

**One remaining import in the broader codebase** (outside `src/robotina/agent/`, therefore outside the grep gate's scope):

- `src/robotina/llm/__init__.py:23` — `from langchain_core.callbacks import (AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun,)`
  - **Why it stays:** These are arguments on `_RetryingChatOllama._generate` and `_agenerate` method overrides. They are required by LangChain's `BaseChatModel` contract: subclasses overriding `_generate`/`_agenerate` MUST accept `run_manager: CallbackManagerForLLMRun` (sync) or `run_manager: AsyncCallbackManagerForLLMRun` (async) per the parent class signature. Removing the import would break `_RetryingChatOllama.bind_tools()` and every Ollama agent invocation.
  - **Scope carve-out:** This is the "where LangChain's BaseChatModel contract requires them" carve-out, broadening the original phase wording "where the LangWatch SDK itself requires them internally." The grep gate is scoped to `src/robotina/agent/` precisely so that LangChain's `BaseChatModel` subclass contract in `src/robotina/llm/` does not violate it.
  - **Citation:** See `_RetryingChatOllama._generate` and `_agenerate` overrides in `src/robotina/llm/__init__.py` (Ollama bounded transient-retry implementation).

## Pitfalls 1–6 — confirmation

| Pitfall | Description | Status |
|---|---|---|
| P1 | LangWatch callback must survive the diff | **Confirmed.** `test_run_task_passes_langwatch_tracer` asserts `LangChainTracer` class present in captured callbacks. Manual smoke (Task 2.3) will verify live trace appearance in the LangWatch dashboard. |
| P2 | Handler invoked exactly once (not double-execution after `wrap_tool_call`) | **Confirmed.** `test_log_wrap_tool_call_invokes_handler_once` in `tests/unit/test_agent_middleware.py` (created in Plan 12-01) is green. |
| P3 | Middleware instances passed without parens (singletons, not classes) | **Confirmed.** `LLMBackend.create_agent` in all three adapters passes `middleware=[log_around_model_call, log_after_model, log_wrap_tool_call]` — by-identity assertions in `test_*_create_agent_passes_middleware_to_factory` tests verify this. |
| P4 | No closure capture of per-job data in module-level middleware singletons | **Confirmed.** `robotina.agent.middleware` is stateless — the singletons read each request/response as it flows; no module-mutable state. `test_backend_instantiated_per_job_not_module_level` continues to pass. |
| P5 | `Thinking` log line preserved (Ollama-only behavior — same as legacy) | **Confirmed.** `test_log_after_model_emits_thinking_when_present` and `test_log_after_model_silent_when_absent` in `tests/unit/test_agent_middleware.py` cover both branches. Same Ollama-only semantics as the legacy callback. |
| P6 | Legacy tests pruned, new test file created — coverage parity maintained | **Confirmed.** 3 deleted (`test_agent_logging_handler_on_llm_start`, `test_agent_logging_handler_on_tool_start`, `test_agent_logging_handler_on_tool_end`). 8 added (6 middleware tests in Plan 12-01 + 2 regression tests here). Net coverage delta: +5 tests on the four-log-line invariant. |

## Files Modified (across Phases 12-01 + 12-02)

### Created
- `src/robotina/agent/middleware.py` (Plan 12-01) — three `AgentMiddleware` singletons emitting the four log lines.
- `tests/unit/test_agent_middleware.py` (Plan 12-01) — six unit tests covering the four log lines + 200-char truncation + handler.call_count == 1.

### Modified
- `src/robotina/llm/__init__.py` (Plan 12-01) — middleware import + `middleware=[...]` kwarg in all three `kwargs` literals.
- `tests/unit/test_llm_backend.py` (Plan 12-01) — three middleware-presence tests appended.
- `src/robotina/queue/jobs.py` (Plan 12-02 — this plan) — removed `AgentLoggingHandler` import + dropped from callbacks list + dropped config= in ImportError branch + docstring update.
- `tests/unit/test_agent_runner.py` (Plan 12-02 — this plan) — 3 legacy tests deleted + 2 OBS-06 regression tests added + module docstring updated.
- `.planning/REQUIREMENTS.md` (Plan 12-02 — this plan) — OBS-06 entry added under Observability section + row in traceability table.

### Deleted
- `src/robotina/agent/callbacks.py` (Plan 12-02 — this plan).

## Test Counts

- **Before Phase 12:** unit suite size ≈ 90 tests (rough — based on tests/unit/ at start of Phase 12).
- **After Plan 12-01:** +9 tests (6 middleware + 3 backend-wiring) = 99.
- **After Plan 12-02:** -3 (legacy callback tests) + 2 (OBS-06 regression tests) = 98 unit tests target. Verified: `uv run pytest tests/unit/` returns 92 passed / 1 failed (the 1 failure is a pre-existing V003/V002 prompt-version drift in `test_agents_registry.py` — see `deferred-items.md` — unrelated to Phase 12).
- **Affected-file slice (the three files most directly touched by Phase 12):** 23/23 passed (`test_agent_runner.py` 8 + `test_agent_middleware.py` 6 + `test_llm_backend.py` 9).

## Task Commits

1. **Task 2.1 RED — OBS-06 regression tests** — `5f0ee51` (`test(12-02): assert LangWatch tracer survives and legacy callback is absent (OBS-06)`)
2. **Task 2.1 GREEN — atomic flip** — `23efeb8` (`refactor(12-02): remove AgentLoggingHandler; middleware fully owns per-agent logging (OBS-06)`)
3. **Task 2.2 — phase summary + REQUIREMENTS.md OBS-06 entry** — landed prior to wrap-up.
4. **Task 2.3 wrap-up — smoke approval + state flips** — (this commit) flips OBS-06 to `[x]`, Phase 12 to Complete on ROADMAP, and records smoke evidence above.

## Manual Smoke Approval (Task 2.3)

**Status:** APPROVED 2026-05-14 by user (solanoepalacio@gmail.com).

Both smoke runs verified working as expected:
1. **Production:** Telegram message → handle-incoming-message → queue → send-notification path verified end-to-end. Four log lines (`LLM stream start`, optional `Thinking`, `Tool call`, `Tool result`) emit from the middleware singletons in agent-worker stdout. LangWatch trace fidelity preserved (model name, tool-call spans, agent-loop structure, provider-exposed token usage).
2. **Experiment:** Experiment-path traces land in the LangWatch experiment collection with prompt-version and model-config tags intact (OBS-04 carryover).

No `LangGraphDeprecatedSinceV10` warnings observed (Phase 10 parity preserved).

**User approval:** "phase 12 verification approved, everything works as expected and looks good." — 2026-05-14.

State flips applied in the wrap-up commit:
- `.planning/REQUIREMENTS.md` — OBS-06 flipped to `[x]`; traceability row flipped to "Complete".
- `.planning/ROADMAP.md` — Phase 12 checkbox flipped to `[x]`; completion date 2026-05-14 in the Progress table.

## Decisions Made

See `key-decisions` in frontmatter. Verbatim:

1. **LangWatch callback wiring survives.** RESEARCH proved LangChainTracer inherits BaseCallbackHandler; the callback bus is the only LangWatch integration path. Removing it would break ALL traces silently. Diff is subtractive only.
2. **ImportError branch drops `config=` entirely.** Not `config={'callbacks': []}` — there's no meaningful empty-callbacks contract; middleware does the logging regardless of langwatch availability.
3. **`test_run_task_no_legacy_callback` belt-and-braces.** Asserts BOTH (a) the legacy module is no longer importable AND (b) the handler class name is absent from the captured callbacks list. Either alone could regress (an accidentally-re-added file would defeat (a) only; an accidentally-re-added callback would defeat (b) only).
4. **Three legacy tests deleted, not migrated.** Their behavioral contract is already covered by `tests/unit/test_agent_middleware.py` (Plan 12-01). Migrating them would duplicate coverage with the only difference being which logger name (`robotina.agent.callbacks` vs `robotina.agent.middleware`) is asserted.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

**Pre-existing test failure discovered during full-suite run** (logged to `deferred-items.md`, NOT fixed in this plan per scope-boundary rule):

- `tests/unit/test_agents_registry.py::test_recipe_load_registered` — expects `recipe-load/V002.md`, but code (since commit `3ce39c5`) points to `V003.md`. Phase 11 drift; one-line follow-up. Does NOT affect Phase 12 contracts.
- `tests/test_db_models.py::test_migration_creates_all_tables` — requires Postgres running. Integration test, not unit. No action needed.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| (none) | — | No new security surface introduced. The 200-char truncation invariant (V5/V7 ASVS log-injection / log-bloat mitigation) remains in the middleware module (preserved byte-for-byte from the deleted callback). No new network endpoints, auth paths, file access, or schema changes. The callbacks-list shape change is internal observability wiring. |

## Self-Check: PASSED

**Files claimed:**
- `src/robotina/agent/callbacks.py` — VERIFIED DELETED (file no longer exists)
- `src/robotina/queue/jobs.py` — VERIFIED modified (3 edits: import removed, docstring updated, callbacks list subtracted in both branches)
- `tests/unit/test_agent_runner.py` — VERIFIED modified (3 tests deleted, 2 added, module docstring updated, `import logging` removed)
- `.planning/REQUIREMENTS.md` — VERIFIED modified (OBS-06 entry added under Observability; traceability row added) — see Task 2.2 commit
- `.planning/phases/12-middleware-based-agent-instrumentation/12-SUMMARY.md` — VERIFIED created (this file)
- `.planning/phases/12-middleware-based-agent-instrumentation/deferred-items.md` — VERIFIED created (out-of-scope failures logged)

**Commits claimed:**
- `5f0ee51` — VERIFIED on `use-new-agent-version` (RED: 2 regression tests added)
- `23efeb8` — VERIFIED on `use-new-agent-version` (GREEN: atomic flip)

**Verification commands run:**
- `grep -r 'from langchain_core.callbacks' src/robotina/agent/` → empty (success criterion 4 satisfied)
- `uv run pytest tests/unit/test_agent_runner.py tests/unit/test_agent_middleware.py tests/unit/test_llm_backend.py` → 23/23 PASSED
- `uv run pytest tests/unit/` → 92 passed / 1 failed (the 1 failure is pre-existing V003/V002 drift — see deferred-items.md)

## Next Phase Readiness

- **Task 2.3 manual smoke approved 2026-05-14.** Phase 12 complete.
- **Plan 12-01's coexistence design vindicated:** Wave 1 added the new path under traffic; Wave 2 removed the old path in one atomic commit; no test outside the directly-edited files regressed (the one V003/V002 failure is pre-existing Phase 11 drift). The split was worth it.
- **Future observability work has a clear seam:** any new pre/post-model guards (token-budget checks, prompt-injection filters), span enrichment, or dynamic-prompt middleware should be added to `src/robotina/agent/middleware.py` and registered in the `middleware=[...]` list in `src/robotina/llm/__init__.py` (currently 3 entries).

---
*Phase: 12-middleware-based-agent-instrumentation*
*Plan: 02*
*Completed: 2026-05-14 (Tasks 2.1+2.2 on 2026-05-13; Task 2.3 manual smoke approved 2026-05-14).*
