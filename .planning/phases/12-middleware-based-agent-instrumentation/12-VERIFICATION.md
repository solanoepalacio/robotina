---
phase: 12-middleware-based-agent-instrumentation
verified: 2026-05-14T00:00:00Z
status: approved
score: 5/5 must-haves verified (SC#2 human smoke approved 2026-05-14)
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: n/a
  gaps_closed: []
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Smoke 1 — Production Telegram path"
    expected: |
      Run `docker compose up -d` (Postgres+Redis), then `uv run all` (gateway + agent worker).
      From the configured Telegram chat, send a household-question that exercises the routing
      agent (e.g. "what's on the meal plan today?"). In the agent-worker stdout, observe:
        - `LLM stream start | model=Chat<Ollama|Anthropic|OpenAI>` (per active overrides/*.json)
        - At least one `Tool call | tool=... input=...` line
        - A matching `Tool result | output=...` line
        - If Ollama with reasoning enabled, a `Thinking | ...` line
        - The reply is delivered back to the Telegram chat
      In the LangWatch dashboard (LANGWATCH_ENDPOINT), confirm a new trace appears with:
        - Model name
        - Tool-call spans
        - Agent-loop structure
        - Provider-exposed token usage (where applicable)
      No `LangGraphDeprecatedSinceV10` warnings in worker logs (Phase 10 parity).
    why_human: "LangWatch trace fidelity is verifiable only against the live dashboard. Static analysis cannot prove model name / tool-call spans / token usage render correctly in the trace UI; the worker/queue/gateway stack must actually run."
  - test: "Smoke 2 — Experiment path (LangWatch experiment collection)"
    expected: |
      Run `uv run experiments/recipe_research.py` (or `experiments.recipe_research` per pyproject
      scripts; `recipe_load` is also acceptable). Verify stdout contains the four log-line keys
      (`LLM stream start`, optional `Thinking`, `Tool call`, `Tool result`). Verify a new trace
      lands in the LangWatch experiment collection with prompt-version and model-config tags
      intact (OBS-04 carryover).
    why_human: "Experiment-run trace verification requires authenticated access to the LangWatch experiment dashboard and visual inspection of the prompt-version / model-config tags."
  - test: "Post-approval housekeeping (after both smokes pass)"
    expected: |
      User types "approved" (with trace IDs or screenshot paths). Then in a final commit:
        - `.planning/phases/12-middleware-based-agent-instrumentation/12-SUMMARY.md` →
          fill in the "Manual Smoke Approval" section with workflow_run_id, experiment
          timestamp, LangWatch trace IDs / screenshot paths, user-approval signature line.
        - `.planning/REQUIREMENTS.md` → OBS-06 flipped from `[ ]` to `[x]`;
          traceability row flipped from "In Progress" to "Complete".
        - `.planning/ROADMAP.md` → Phase 12 checkbox flipped to `[x]`; completion date
          added to the Progress table.
    why_human: "Final state flip is conditional on the user's approval of the smoke evidence; can only happen post-smoke."
---

# Phase 12: Middleware-Based Agent Instrumentation — Verification Report

**Phase Goal:** Migrate per-agent OTel/LangWatch instrumentation from `langchain_core.callbacks` to `create_agent` middleware (`@before_model`, `@after_model`, `@wrap_model_call`). LangWatch traces and existing per-tool / per-LLM log lines must remain intact.

**Verified:** 2026-05-13 (post-Plan 12-02 Tasks 2.1+2.2; pre Task 2.3 manual smoke)
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Success Criteria from ROADMAP)

| #   | Truth                                                                                                                                                                                                                                                       | Status                            | Evidence                                                                                                                                                                                                                                                                                                            |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Per-agent log lines (`LLM stream start`, `Thinking`, `Tool call`, `Tool result`) are emitted by middleware; legacy `AgentLoggingHandler` callback is removed; no remaining call site passes it to `create_agent`                                            | ✓ VERIFIED                        | `src/robotina/agent/middleware.py:62,84,102,107` emits the four log lines byte-for-byte. `src/robotina/agent/callbacks.py` deleted (no longer exists). `grep -r 'AgentLoggingHandler' src/` finds zero active code references — only comments in `jobs.py:23,196` and docstrings in `middleware.py`.                |
| 2   | LangWatch traces appear in the correct collection for ≥1 production run AND ≥1 experiment run, with model name, tool calls, and token usage intact                                                                                                          | ? HUMAN REQUIRED (Task 2.3 gate)  | `src/robotina/queue/jobs.py:199` keeps `callbacks=[langwatch.langchain.LangChainTracer()]` non-empty (subtractive diff). `test_run_task_passes_langwatch_tracer` (test_agent_runner.py:229) asserts class presence. **Live trace fidelity cannot be machine-verified** — requires the user to run both smoke flows. |
| 3   | `uv run pytest` is green; instrumentation tests assert middleware presence/ordering rather than callback registration                                                                                                                                       | ✓ VERIFIED (with documented drift) | Affected-file slice 23/23 PASSED: `tests/unit/test_agent_middleware.py` (6) + `tests/unit/test_llm_backend.py` (9) + `tests/unit/test_agent_runner.py` (8). Full unit suite: 92 passed / 1 failed; the lone failure is pre-existing Phase 11 V002/V003 prompt-version drift in `test_agents_registry.py`, documented in `deferred-items.md` and unrelated to Phase 12. |
| 4   | No `from langchain_core.callbacks` imports remain in `src/robotina/agent/` (except where LangWatch SDK / LangChain BaseChatModel contract requires them)                                                                                                    | ✓ VERIFIED                        | `Grep("from langchain_core.callbacks", path="src/robotina/agent/")` → empty. The one remaining import in `src/robotina/llm/__init__.py:23` (`CallbackManagerForLLMRun`, `AsyncCallbackManagerForLLMRun`) is documented in `12-SUMMARY.md` as the BaseChatModel-contract carve-out (required by `_RetryingChatOllama._generate/_agenerate` overrides).                |
| 5   | Phase summary documents the LangWatch + middleware interaction model (specifically: does LangWatch's OTel bridge pick up traces independent of callbacks, or is a shim needed)                                                                              | ✓ VERIFIED                        | `12-SUMMARY.md` lines 90–114 — "LangWatch + Middleware Interaction Model" section. Documents that `langwatch.langchain.LangChainTracer` inherits `BaseCallbackHandler` (langwatch 0.17.0, `langchain.py:110`); LangWatch has no callback-free path in this SDK version; therefore migration is subtractive (handler removed only) and no bridge layer was needed. |

**Score:** 4/5 truths fully verified by code/tests. **SC#2 is the documented human checkpoint (Task 2.3).**

### Required Artifacts

| Artifact                                                                                       | Expected                                                                              | Status      | Details                                                                                                                                                                                  |
| ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/robotina/agent/middleware.py`                                                             | Three `AgentMiddleware` singletons emitting the four legacy log lines                 | ✓ VERIFIED  | 113 lines. Exposes `log_around_model_call` (line 51), `log_after_model` (line 67), `log_wrap_tool_call` (line 88). Logger name `robotina.agent.middleware`. Truncation `[:200]` preserved. |
| `src/robotina/llm/__init__.py`                                                                 | All three backends pass `middleware=[...]` to `_create_agent`                         | ✓ VERIFIED  | Import at line 36 (AGENT-13 marker). `middleware: [...]` literal in all three kwargs dicts at lines 244, 293, 336. Identical list across Ollama/Anthropic/OpenAI.                          |
| `src/robotina/queue/jobs.py`                                                                   | No `from robotina.agent.callbacks import`; LangWatch tracer retained non-empty list   | ✓ VERIFIED  | Import removed. Line 199: `callbacks=[langwatch.langchain.LangChainTracer()]` (non-empty). ImportError branch (line 205) drops `config=` entirely as planned. Docstring step 7 updated.    |
| `src/robotina/agent/callbacks.py`                                                              | DELETED (file no longer exists)                                                       | ✓ VERIFIED  | `ls src/robotina/agent/callbacks.py` → no such file. Directory contents: `agents.py`, `middleware.py`, `workflows.py`, `prompts/`, `skills/`, `tools/`, `__init__.py`.                     |
| `tests/unit/test_agent_middleware.py`                                                          | Six tests covering four log lines + 200-char truncation + handler.call_count == 1     | ✓ VERIFIED  | 178 lines. All six tests present (lines 20, 47, 74, 97, 131, 151). All pass.                                                                                                              |
| `tests/unit/test_agent_runner.py`                                                              | Three legacy tests pruned; two new OBS-06 regression tests added; docstring updated   | ✓ VERIFIED  | Module docstring now references OBS-06 (lines 6–8). `test_run_task_passes_langwatch_tracer` (line 229) + `test_run_task_no_legacy_callback` (line 241) present. No `test_agent_logging_handler_*` tests remain. |
| `.planning/phases/12-middleware-based-agent-instrumentation/12-SUMMARY.md`                     | Phase summary documenting LangWatch interaction model (SC#5)                          | ✓ VERIFIED  | Created. Contains "LangChainTracer" keyword (frontmatter + body); LangWatch interaction model section explicit. Manual Smoke Approval section marked PENDING.                              |
| `.planning/REQUIREMENTS.md`                                                                    | OBS-06 entry added under Observability; traceability row added; `[ ]` until smoke approval | ✓ VERIFIED  | Line 111: `[ ] **OBS-06**: ...`. Line 219: traceability row `OBS-06 | Phase 12 | In Progress`. Last-updated note line 228 references Phase 12.                                            |

### Key Link Verification

| From                                                  | To                                                | Via                                                                       | Status   | Details                                                                                                                                                                                                                                                |
| ----------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `src/robotina/llm/__init__.py`                        | `src/robotina/agent/middleware.py`                | `from robotina.agent.middleware import (...)` at line 36                  | ✓ WIRED  | Module-top import alongside `_create_agent` alias on line 32. AGENT-13 / Phase 12 marker present.                                                                                                                                                       |
| `src/robotina/llm/__init__.py` (3 backends)           | `langchain.agents.create_agent` (via `_create_agent`) | kwargs dict literal `"middleware": [log_around_model_call, log_after_model, log_wrap_tool_call]` | ✓ WIRED  | Verified in OllamaBackend (line 244), AnthropicBackend (line 293), OpenAIBackend (line 336). Identical list across all three.                                                                                                                          |
| `src/robotina/queue/jobs.py` (try branch)             | `langwatch.langchain.LangChainTracer`             | `RunnableConfig(callbacks=[langwatch.langchain.LangChainTracer()])`       | ✓ WIRED  | Line 199. Subtractive diff verified — list still non-empty (RESEARCH Pitfall 1).                                                                                                                                                                        |
| `src/robotina/queue/jobs.py` (ImportError branch)     | (no callbacks)                                    | `config=` kwarg dropped entirely                                          | ✓ WIRED  | Lines 202–207. Middleware emits log lines without requiring a callback (per plan: "drop the `config=` kwarg entirely").                                                                                                                                |
| `tests/unit/test_agent_runner.py`                     | `src/robotina/queue/jobs.py` callbacks list       | `test_run_task_passes_langwatch_tracer` + `test_run_task_no_legacy_callback` | ✓ WIRED | Both regression tests pass (see automated check). Asserts presence of `LangChainTracer` class name and absence of `AgentLoggingHandler` class name in captured callbacks list. |

### Data-Flow Trace (Level 4)

| Artifact                                  | Data Variable                              | Source                                                | Produces Real Data    | Status     |
| ----------------------------------------- | ------------------------------------------ | ----------------------------------------------------- | --------------------- | ---------- |
| `src/robotina/agent/middleware.py`        | `request.model`, `state["messages"]`, `request.tool_call` | Populated by `langchain.agents.create_agent` graph runtime — middleware receives live ModelRequest / AgentState / ToolCallRequest objects at hook invocation | ✓ FLOWING (via graph) | ✓ VERIFIED |
| `src/robotina/queue/jobs.py` invoke       | `result` from `agent.invoke(...)`           | Real LangChain agent graph with live messages + callbacks list                                          | ✓ FLOWING             | ✓ VERIFIED |

Note: middleware is hook-style (data flows from the graph engine through each hook call, not from a state variable rendered in the file). The Level-4 concern (HOLLOW prop, hardcoded empty data) does not apply — middleware is pure function wiring.

### Behavioral Spot-Checks

| Behavior                                                                                                | Command                                                                                          | Result                       | Status     |
| ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------- | ---------- |
| Middleware module imports without side effects (no I/O, no env, no network)                             | (Documented in `12-01-SUMMARY.md`; verified at Plan 12-01 time via `uv run python -c "import robotina.agent.middleware as m; print(type(m.log_around_model_call).__mro__)"`) | `AgentMiddleware` in MRO, no log output observed | ✓ PASS     |
| Phase 12 grep gate (no `langchain_core.callbacks` imports in `src/robotina/agent/`)                     | `Grep("from langchain_core.callbacks", path="src/robotina/agent/")`                              | empty                        | ✓ PASS     |
| `AgentLoggingHandler` not referenced as active code anywhere in `src/`                                  | `Grep("AgentLoggingHandler", path="src/")`                                                       | Only inside `#` comments and docstrings (jobs.py:23,196; middleware.py:4,57,71,94) — no active imports or instantiations | ✓ PASS     |
| `robotina.agent.callbacks` module is no longer importable                                               | `python -c "import robotina.agent.callbacks"` (via `test_run_task_no_legacy_callback`)           | `ModuleNotFoundError`        | ✓ PASS     |
| Phase-12-touched unit tests are green                                                                   | `uv run pytest tests/unit/test_agent_middleware.py tests/unit/test_llm_backend.py tests/unit/test_agent_runner.py` | 23 passed in 0.95s           | ✓ PASS     |
| Full unit suite is green (modulo documented pre-existing drift)                                         | `uv run pytest tests/unit/`                                                                      | 92 passed, 1 failed (V002/V003 prompt drift in `test_agents_registry.py`, pre-existing Phase 11; logged in `deferred-items.md`) | ✓ PASS (drift quarantined) |
| Production smoke (Telegram → handle-incoming-message → queue → send-notification with LangWatch trace)  | Manual run by user                                                                               | n/a                          | ? SKIP (human) |
| Experiment smoke (`uv run experiments/recipe_research.py` with LangWatch trace in experiment collection)| Manual run by user                                                                               | n/a                          | ? SKIP (human) |

### Requirements Coverage

| Requirement | Source Plan | Description                                                                              | Status                | Evidence                                                                                                                                              |
| ----------- | ----------- | ---------------------------------------------------------------------------------------- | --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| OBS-06      | 12-01, 12-02 | Per-agent instrumentation via `create_agent` middleware; legacy `AgentLoggingHandler` removed; four log lines preserved; LangWatch traces unchanged | ⚠ PENDING APPROVAL    | Code/test work complete (SC#1, SC#3, SC#4, SC#5 verified). Per REQUIREMENTS.md line 228, OBS-06 flips to `[x]` only AFTER Task 2.3 manual smoke approval. |

### Anti-Patterns Found

| File                                            | Line | Pattern                                                | Severity | Impact                                                                                                                  |
| ----------------------------------------------- | ---- | ------------------------------------------------------ | -------- | ----------------------------------------------------------------------------------------------------------------------- |
| (none specific to Phase 12)                     | —    | —                                                      | —        | The Phase 12 diff is subtractive on a callback list + decorator wiring. No hardcoded empty data, no stub returns, no `console.log`/print, no placeholder strings. 200-char truncation preserved byte-for-byte (V5/V7 ASVS log-injection / log-bloat mitigation). |
| `tests/unit/test_agents_registry.py:163`         | 163  | Asserting `V002.md` while production code now uses `V003.md` | ℹ Info  | **Pre-existing Phase 11 drift, not Phase 12.** Documented in `12-02-PLAN.md` and `deferred-items.md`. Does not impact Phase 12 contracts.  |

### Human Verification Required

See `human_verification:` frontmatter above. Two smoke runs + post-approval housekeeping commit.

**Why the human gate exists (documented design):** the LangWatch SDK (`langwatch 0.17.0`) has no callback-free integration path — `LangChainTracer` inherits `BaseCallbackHandler`, and the auto-instrumentor alternative (`openinference-instrumentation-langchain`) also patches the callback bus. Therefore live trace fidelity is the only observable that proves SC#2; static analysis cannot reproduce it. This was anticipated in `12-02-PLAN.md` Task 2.3 (`<task type="checkpoint:human-verify" gate="blocking">`).

### Gaps Summary

There are **no machine-detectable gaps**. The full Phase 12 contract is implemented:

- New middleware module exists, exposes three `AgentMiddleware` singletons, emits the four legacy log lines byte-for-byte with the 200-char truncation invariant preserved.
- All three `LLMBackend.create_agent` methods (`OllamaBackend`, `AnthropicBackend`, `OpenAIBackend`) pass the same `middleware=[...]` list to `_create_agent`.
- Legacy `AgentLoggingHandler` is fully gone (file deleted, import removed, no active references in `src/`).
- LangWatch tracer wiring is retained in `src/robotina/queue/jobs.py:199` exactly as the plan prescribed (subtractive diff; non-empty callbacks list).
- Tests: 6 new middleware unit tests + 2 regression tests for jobs.py callbacks list. 23/23 affected-file slice green. 92/93 full unit suite (the one failure is documented pre-existing Phase 11 drift unrelated to Phase 12).
- Grep gate: zero `from langchain_core.callbacks` imports in `src/robotina/agent/`. The one remaining import in `src/robotina/llm/__init__.py` is the documented BaseChatModel-contract carve-out — required by `_RetryingChatOllama._generate/_agenerate` overrides, outside the SC#4 grep gate scope.
- Phase summary documents the LangWatch + middleware interaction model verbatim (SC#5): `LangChainTracer` is itself a `BaseCallbackHandler`, no bridge layer needed, migration is subtractive only.

**The one outstanding item is SC#2 — LangWatch trace fidelity on real production + experiment runs.** This is the documented blocking checkpoint (Task 2.3) and cannot be verified without the user running the smoke flows against the live LangWatch dashboard.

---

_Verified: 2026-05-13_
_Verifier: Claude (gsd-verifier)_
