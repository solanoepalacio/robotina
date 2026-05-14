# Phase 12: Middleware-Based Agent Instrumentation - Research

**Researched:** 2026-05-13
**Domain:** LangChain 1.x agent middleware + LangWatch tracing model
**Confidence:** HIGH (every load-bearing claim was verified by reading the installed source in `.venv/`)

## Summary

LangChain 1.x ships a real middleware API in `langchain.agents.middleware` that this phase can target directly. Five decorators are relevant: `@before_model`, `@after_model`, `@wrap_model_call`, `@wrap_tool_call`, plus `hook_config`. Each yields an `AgentMiddleware` instance that is passed as `middleware=[...]` to `langchain.agents.create_agent`. The decorators are first-class and present in the installed version (`langchain==1.2.13`).

**The LangWatch interaction model — answered.** LangWatch 0.17.0 (currently installed) integrates with LangChain via **`langwatch.langchain.LangChainTracer`**, which is itself a `BaseCallbackHandler` subclass. LangWatch traces are built ENTIRELY from LangChain callback events (`on_chat_model_start`, `on_llm_end`, `on_tool_start`, `on_tool_end`, `on_chain_*`, `on_agent_*`). Furthermore, LangWatch's "OTel auto-instrumentation" alternative — `openinference-instrumentation-langchain`, which it bundles as a hard dependency — works by **monkey-patching `BaseCallbackManager.__init__` to inject an OTel-emitting `BaseCallbackHandler`**. There is no callback-free LangWatch path in this version. Therefore Phase 12 is **not a rip-and-replace of `RunnableConfig(callbacks=[...])`** — it is a removal of `AgentLoggingHandler` only. The `langwatch.langchain.LangChainTracer` callback must stay wired through `RunnableConfig(callbacks=[...])` (or, equivalently, swapped to `langwatch.setup(instrumentors=[LangChainInstrumentor()])` — see Pattern 3).

**Primary recommendation:** Replace `AgentLoggingHandler` with three function-decorator middlewares (`log_before_model`, `log_after_model`, `log_wrap_tool_call`) on the agent built inside `LLMBackend.create_agent()`. Keep the LangWatch callback wiring exactly as it is today. Delete `src/robotina/agent/callbacks.py`. This is a 1-task migration plus test rewrites.

## User Constraints (from CONTEXT.md)

### Locked Decisions
All implementation choices are at Claude's discretion — this is an infrastructure phase (migration / refactor with technical success criteria only, no user-facing behavior). Use the ROADMAP phase goal, success criteria, and the LangChain 1.x middleware docs to guide decisions.

Constraints carried from ROADMAP notes:
- This is a rip-and-replace migration in principle, but the LangWatch interaction model needs verification first. If LangWatch's tracing depends on LangChain callbacks (rather than OTel directly), a thin bridge layer may be required and success criterion 5 (phase summary documents the interaction model) becomes the place to record the finding.
- A short research spike at the start of plan-phase is appropriate, before committing to the migration shape. (← This is that spike, completed.)
- Out of scope: custom state schemas for `reply_context` / `household_id` (backlog item 999.1).

### Claude's Discretion
Everything implementation-shaped: where to put the middleware module, whether to use class-based `AgentMiddleware` subclass vs. function decorators, naming, test layout.

### Deferred Ideas (OUT OF SCOPE)
- Token-budget pre-model guard (ROADMAP future work)
- Prompt-injection filter middleware (ROADMAP future work)
- Custom state schemas for `reply_context` / `household_id` (Phase 999.1 backlog)

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OBS-06 (candidate) | Per-agent instrumentation must use `create_agent` middleware. Legacy `AgentLoggingHandler` removed. `LLM stream start`, `Tool call`, `Tool result`, `Thinking` log lines preserved. LangWatch traces unchanged. | Patterns 1–3 below; mapping table in §"Mapping current callbacks → middleware". |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-LLM-call log lines (`LLM stream start`, `Thinking`) | Agent middleware (`@before_model`, `@after_model`) | — | Middleware is the LangChain 1.x recommended seam; runs inside the agent graph node and has typed access to `ModelRequest` / `AgentState`. |
| Per-tool-call log lines (`Tool call`, `Tool result`) | Agent middleware (`@wrap_tool_call`) | `@after_model` (alternative — read `AIMessage.tool_calls`) | `@wrap_tool_call` runs in the tools node with both the `ToolCallRequest` and `ToolMessage` available, mirroring the current `on_tool_start` / `on_tool_end` shape exactly. |
| LangWatch trace ingestion | LangChain callback bus (`RunnableConfig.callbacks` OR globally-installed `LangChainInstrumentor`) | — | LangWatch 0.17.0 has no callback-free path. Both `LangChainTracer` and the auto-instrumentor depend on `BaseCallbackHandler`. Verified empirically (`langwatch/langchain.py:110`, `openinference/instrumentation/langchain/__init__.py:54-58`). |
| OTel span emission for non-LLM events | Direct `opentelemetry.trace` API | — | Out of scope for this phase, but documenting: middleware decorators are the right place to add custom spans alongside log lines later (e.g., token-budget gauge). |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langchain | 1.2.13 (installed) | Provides `langchain.agents.middleware` package and `create_agent(middleware=...)` kwarg | The official LangChain 1.x recommended instrumentation seam. Decorators exposed: `before_model`, `after_model`, `wrap_model_call`, `wrap_tool_call`, `dynamic_prompt`, `hook_config`, plus base class `AgentMiddleware`. [VERIFIED: `.venv/lib/python3.12/site-packages/langchain/agents/middleware/__init__.py`] |
| langchain-core | 1.2.22 (installed) | `BaseMessage`, `AIMessage`, `ToolMessage`, `SystemMessage`, `BaseCallbackHandler` (still used by LangWatch) | Stable base abstractions [VERIFIED: `uv pip show`] |
| langgraph | 1.1.3 (installed) | `Runtime`, `ToolCallRequest`, `Command` — types middleware functions receive | Hard dep of `langchain.agents`; types are re-exported from `langchain.agents.middleware` for convenience [VERIFIED: `langchain/agents/middleware/__init__.py:1-3, types.py:35-37`] |
| langwatch | 0.17.0 (installed) | LangWatch SDK; provides `langwatch.langchain.LangChainTracer` callback handler and `langwatch.trace()` context manager | Currently in active use in `src/robotina/queue/jobs.py` and `experiments/`. **Stays unchanged** in this phase. [VERIFIED: `uv pip show langwatch`; `langwatch/langchain.py`] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| openinference-instrumentation-langchain | bundled with langwatch 0.17.0 | OTel auto-instrumentor for LangChain | **Optional alternative** to passing the callback per-call. If wired via `langwatch.setup(instrumentors=[LangChainInstrumentor()])` at startup, captures spans for every agent run with zero per-invoke wiring. Trades clarity for global behavior. See Pattern 3. [VERIFIED: `.venv/lib/python3.12/site-packages/openinference/instrumentation/langchain/__init__.py:26-58`] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Function decorators (`@before_model`, `@after_model`, `@wrap_tool_call`) | Class-based `AgentMiddleware` subclass with sync + async methods | Class form needed only when (a) you want to keep state between hooks (we don't — logging is stateless), or (b) you need both sync and async variants attached to one instance. Function decorators auto-generate the wrapper class and are idiomatic in the LangChain examples. [CITED: `langchain/agents/middleware/types.py:929-1073` for `before_model` decorator + 1843-1892 for `wrap_model_call` decorator.] |
| `@wrap_tool_call` for tool logging | `@after_model` reading `state["messages"][-1].tool_calls` | `after_model` only sees the request the model *intended* to make — it does not see the tool result. `wrap_tool_call` sees both request and result, in one handler, with retry-safe handler-callback semantics. Use `wrap_tool_call`. [VERIFIED: `langchain/agents/middleware/types.py:649-729`] |
| Remove the LangWatch callback entirely | Install `LangChainInstrumentor` globally in `_setup_langwatch()` | Equivalent observability outcome, but auto-instrumentation patches `BaseCallbackManager.__init__` globally → applies to *every* LangChain runnable in the process, including ones we don't intend to trace (e.g., experiments that want a specific `metadata=` tag set). Per-call `RunnableConfig(callbacks=[tracer])` keeps the metadata-tagging story working. Recommend KEEPING the current per-call wiring. |

**Installation:** Nothing new to install. All required packages are already pinned in `pyproject.toml` and present in `.venv/`.

**Version verification** (run inside `.venv`):
```bash
uv pip show langchain langgraph langwatch
# langchain 1.2.13, langgraph 1.1.3, langwatch 0.17.0 — confirmed 2026-05-13
```

## Architecture Patterns

### System Architecture Diagram (post-migration)

```
                                ┌──────────────────────────────┐
                                │ run_task() in queue/jobs.py  │
                                │  - reads task_type from meta │
                                │  - builds LLMBackend         │
                                │  - injects per-job tools     │
                                └──────────────┬───────────────┘
                                               │
                                               ▼
                                ┌──────────────────────────────┐
                                │ LLMBackend.create_agent(     │
                                │     system_prompt, tools,    │
                                │     response_format)         │
                                │ NEW: passes middleware=[...] │
                                └──────────────┬───────────────┘
                                               │
                                               ▼
                ┌──────────────────────────────────────────────────────┐
                │  langchain.agents.create_agent(..., middleware=[     │
                │      log_before_model,    # @before_model decorator  │
                │      log_after_model,     # @after_model decorator   │
                │      log_wrap_tool_call,  # @wrap_tool_call decorator│
                │  ])                                                  │
                └──────────────────────────┬───────────────────────────┘
                                           │ agent.invoke(state, config)
                                           ▼
        ┌──────────────────────────────────────────────────────────────┐
        │  RunnableConfig(callbacks=[langwatch.langchain.LangChainTracer()])  │
        │  (UNCHANGED — LangWatch still rides the callback bus)        │
        └──────────────────────────────────────────────────────────────┘
                                           │
                ┌──────────────────────────┴──────────────────────────┐
                ▼                                                     ▼
        Agent graph nodes                                      Callback bus
        (where middleware runs)                                (where LangWatch listens)
        - before_model  → log "LLM stream start"               on_chat_model_start → LangWatchSpan
        - model node    → ChatOllama / ChatAnthropic / Chat OpenAI
        - after_model   → log "Thinking" if reasoning_content  on_llm_end          → close span
        - wrap_tool_call → log "Tool call" + "Tool result"     on_tool_start/end   → tool spans
        - tools node    → execute BaseTool implementations
```

The two control planes (middleware + callbacks) run side-by-side without interference. Middleware is in-band with the graph; callbacks are out-of-band observers driven by `RunnableConfig`.

### Recommended Project Structure

```
src/robotina/agent/
├── callbacks.py         # DELETE after migration (or leave as 1-line shim with deprecation)
├── middleware.py        # NEW — defines log_before_model / log_after_model / log_wrap_tool_call
├── agents.py            # unchanged
├── workflows.py         # unchanged
├── prompts/             # unchanged
├── skills/              # unchanged
└── tools/               # unchanged
```

Place the new module at `src/robotina/agent/middleware.py`. Keep it short (~60 lines including docstrings). The plan should also update `src/robotina/llm/__init__.py` so each `*Backend.create_agent()` passes `middleware=[...]` to `_create_agent`.

### Pattern 1: Function-decorator middleware — minimal, stateless logging

This is the recommended shape. Direct replacement of `AgentLoggingHandler`. [VERIFIED: built and shape-checked against `langchain/agents/middleware/types.py:910-1073, 1736-1892, 1895-2052`]

```python
# src/robotina/agent/middleware.py
from __future__ import annotations

import logging
from typing import Callable

from langchain.agents.middleware import (
    after_model,
    before_model,
    wrap_tool_call,
    AgentState,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
)
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

logger = logging.getLogger(__name__)


@before_model
def log_before_model(state: AgentState, runtime: Runtime) -> None:
    """Log 'LLM stream start' before each model call.

    Replaces AgentLoggingHandler.on_chat_model_start. We do not have the
    model name in state here (the model is on ModelRequest, accessible only
    from wrap_model_call); using the agent name from runtime is acceptable.
    For exact parity with the old log line we use wrap_model_call instead
    — see log_around_model_call below as the preferred form when the
    'model=%s' field matters.
    """
    logger.info("LLM stream start")  # parity: existing log key


@after_model
def log_after_model(state: AgentState, runtime: Runtime) -> None:
    """Log 'Thinking | ...' when the latest AI message carries reasoning_content.

    Replaces AgentLoggingHandler.on_llm_end (the Thinking branch).
    state['messages'][-1] is the AIMessage just produced.
    """
    last = state["messages"][-1]
    if isinstance(last, AIMessage):
        thinking = last.additional_kwargs.get("reasoning_content")
        if thinking:
            logger.info("Thinking | %s", thinking)


@wrap_tool_call
def log_wrap_tool_call(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    """Log 'Tool call' before execution and 'Tool result' after.

    Replaces AgentLoggingHandler.on_tool_start + on_tool_end.
    request.tool_call is a dict with keys: name, args, id, type.
    handler(request) runs the actual BaseTool and returns ToolMessage|Command.
    """
    name = request.tool_call.get("name")
    args = request.tool_call.get("args", {})
    logger.info("Tool call | tool=%s input=%s", name, str(args)[:200])

    result = handler(request)

    if isinstance(result, ToolMessage):
        logger.info("Tool result | output=%s", str(result.content)[:200])
    else:
        # Command path — log a short marker; Command does not have a primary
        # output string. This case is rare in current Robotina tools.
        logger.info("Tool result | output=<Command>")

    return result
```

**To wire it up**, edit `LLMBackend.create_agent` implementations in `src/robotina/llm/__init__.py`:

```python
# Inside OllamaBackend.create_agent (and AnthropicBackend / OpenAIBackend identically):
from robotina.agent.middleware import (
    log_before_model, log_after_model, log_wrap_tool_call,
)

kwargs: dict[str, Any] = {
    "model": self._model,
    "tools": tools or [],
    "system_prompt": system_prompt,
    "middleware": [log_before_model, log_after_model, log_wrap_tool_call],  # NEW
}
if response_format is not None:
    from langchain.agents.structured_output import ToolStrategy  # or ProviderStrategy
    kwargs["response_format"] = ToolStrategy(response_format)
return _create_agent(**kwargs)
```

Then in `src/robotina/queue/jobs.py`, **delete** `AgentLoggingHandler` from the `callbacks=[...]` list:

```python
# BEFORE
callbacks=[AgentLoggingHandler(), langwatch.langchain.LangChainTracer()]

# AFTER (only LangWatch remains)
callbacks=[langwatch.langchain.LangChainTracer()]
```

and in the ImportError-fallback branch, drop the whole `config=` arg (no callbacks needed if LangWatch is unavailable, since middleware now produces all the log lines).

### Pattern 2: Preferred `wrap_model_call` for full model-name parity

The current log line is `LLM stream start | model=%s`. `before_model` does not have direct access to the model — that lives on `ModelRequest`, only available inside `wrap_model_call`. For exact parity, prefer this shape for the LLM-start log line:

```python
# Alternative — use this INSTEAD of log_before_model if you want the model name.
from langchain.agents.middleware import wrap_model_call

@wrap_model_call
def log_around_model_call(request: ModelRequest, handler):
    # serialized model class name, e.g. 'ChatOllama'
    model_name = type(request.model).__name__
    logger.info("LLM stream start | model=%s", model_name)
    return handler(request)
```

Choose one of: `[log_before_model, log_after_model, log_wrap_tool_call]` (loses model name) OR `[log_around_model_call, log_after_model, log_wrap_tool_call]` (preserves model name). The latter is recommended.

[VERIFIED: `ModelRequest.model: BaseChatModel` field is documented in `langchain/agents/middleware/types.py:96`. `wrap_model_call` decorator emits an `AgentMiddleware` with the `wrap_model_call` method populated — types.py:1843-1892.]

### Pattern 3: (NOT RECOMMENDED for this phase) Global OTel auto-instrumentation

LangWatch supports being wired with `instrumentors=[LangChainInstrumentor()]` at setup, which removes the need to pass the callback per `agent.invoke`. **Do not adopt in Phase 12** because:

- It still goes through the callback bus (monkey-patches `BaseCallbackManager.__init__`) — it's not an architectural improvement, just a syntactic one.
- Experiments today pass per-run `metadata={...}` to the tracer; moving to global instrumentation breaks that metadata-tagging story and would expand scope.

Documenting it here only so the next observability phase doesn't re-research it. [VERIFIED: `openinference/instrumentation/langchain/__init__.py:53-58`; `langwatch/client.py:158-179`]

### Mapping current callbacks → middleware (load-bearing table)

| Current `AgentLoggingHandler` method | Replacement middleware | Notes |
|--------------------------------------|------------------------|-------|
| `on_chat_model_start(serialized, messages)` → `logger.info("LLM stream start | model=%s", serialized.get("name"))` | `@wrap_model_call` (Pattern 2) reading `type(request.model).__name__` | `before_model` is the conceptual analog but lacks the model object. Use `wrap_model_call` for parity. |
| `on_llm_end(response)` → walks generations, logs `"Thinking | %s"` if `reasoning_content` present | `@after_model` reading `state["messages"][-1].additional_kwargs.get("reasoning_content")` | The most recently produced AIMessage is the one we want. |
| `on_tool_start(serialized, input_str)` → `logger.info("Tool call | tool=%s input=%s", ...)` | `@wrap_tool_call` BEFORE calling `handler(request)` | `request.tool_call["name"]`, `request.tool_call["args"]` |
| `on_tool_end(output)` → `logger.info("Tool result | output=%s", ...)` | `@wrap_tool_call` AFTER `handler(request)` | Wrap in `isinstance(result, ToolMessage)` for `.content` access. |

### Anti-Patterns to Avoid

- **Don't remove `langwatch.langchain.LangChainTracer` from `RunnableConfig.callbacks`** — that is the actual LangWatch integration. Removing it breaks every trace. Verified: the SDK class `LangChainTracer` inherits `BaseCallbackHandler` (`langwatch/langchain.py:110`). Success criterion 5 documents this fact.
- **Don't try to delete `from langchain_core.callbacks` imports entirely.** `src/robotina/llm/__init__.py` imports `CallbackManagerForLLMRun` / `AsyncCallbackManagerForLLMRun` for its `_RetryingChatOllama._generate` override (lines 23-26, 104, 135). Those signatures are required by LangChain's `BaseChatModel` contract and cannot be removed without breaking `bind_tools`. Success criterion 4's "where the LangWatch SDK itself requires them" clause covers BOTH the SDK and this internal override. Document explicitly in the phase summary.
- **Don't make the middleware module import-heavy.** Middleware decorators eagerly construct an `AgentMiddleware` instance at import time (the decorator returns an instance, not a class — see types.py:1041-1049). Keep the module side-effect-free except for that.
- **Don't bind state via closures over per-job data** (e.g., `chat_id`, `user_id`). Middleware decorators yield instances at module import time and are shared across all `create_agent` calls in the process. Per-job context must come from `state` / `runtime`, not closure capture.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tool-call event observation | Custom `BaseCallbackHandler.on_tool_start/end` wrapper | `@wrap_tool_call` decorator | The decorator gives typed `ToolCallRequest` + `ToolMessage` access, retry-safe handler-callback semantics, and is the LangChain 1.x recommended seam. Callback handlers for tool events are the legacy API CLAUDE.md explicitly tells us to migrate away from. |
| Pre/post-model hooks | A second `BaseCallbackHandler` for model events | `@before_model` + `@after_model` (or `@wrap_model_call`) | These run in-graph, see typed `AgentState`, and can short-circuit (`jump_to`) — capabilities the callback bus does not expose. |
| Dynamic system prompts (future) | Override `system_prompt` in `LLMBackend.create_agent()` | `@dynamic_prompt` decorator | Out of scope this phase, but worth noting — `langchain.agents.middleware` already solves this. [VERIFIED: types.py:1605-1733] |
| LangWatch trace creation | Hand-emit OTel spans inside middleware | Keep `langwatch.trace()` context manager + `LangChainTracer` callback as today | LangWatch's SDK already does the span hierarchy; reimplementing in middleware would duplicate work and create two parallel trace trees. |

**Key insight:** LangChain 1.x intentionally has *two* observability layers — middleware (in-band, for behavior modification) and callbacks (out-of-band, for tracing). Phase 12 moves the *logging* part to middleware and leaves the *tracing* part on callbacks. That's by design, not a workaround.

## Runtime State Inventory

This phase has minor refactor surface but does involve removing one Python class and changing how three callsites wire up. Each category checked:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `AgentLoggingHandler` has no persisted state. The class is stateless. | None. |
| Live service config | None — LangWatch endpoint, API key, and project tags are unchanged. Traces continue to land in the same LangWatch collection because the `LangChainTracer` callback is unchanged. | None. Verify post-deploy by checking that one production run + one experiment run appear in LangWatch with full span content. |
| OS-registered state | None — no OS-level registrations reference `AgentLoggingHandler`. The RQ worker (`rq`/SimpleWorker) registers job functions by name, not by callback class. | None. |
| Secrets / env vars | None — LANGWATCH_API_KEY and LANGWATCH_ENDPOINT are unchanged. No env vars reference callback/middleware names. | None. |
| Build artifacts / installed packages | None — no compiled artifacts depend on `robotina.agent.callbacks` symbol names. Package metadata (`*.egg-info`) does not list it as an entry point (the only `[project.scripts]` are `agent`, `migrate`, `gateway`, `all`, `experiments.recipe_research`, `experiments.recipe_load`). | None. |

**Verified by:** grep for `AgentLoggingHandler` across the entire repo (results below in §"Call-site inventory"). All references are in code or planning docs.

## Call-site Inventory (every place `AgentLoggingHandler` is wired today)

Plan must touch every one of these:

| File | Line | Current code | Action |
|------|------|--------------|--------|
| `src/robotina/agent/callbacks.py` | 11 | `class AgentLoggingHandler(BaseCallbackHandler):` | **Delete** the file. Or leave a 2-line module that re-exports nothing and emits a `DeprecationWarning` on import — preferable for safety if any downstream user imports it. |
| `src/robotina/queue/jobs.py` | 23 | `from robotina.agent.callbacks import AgentLoggingHandler` | **Remove import.** |
| `src/robotina/queue/jobs.py` | 195 | `callbacks=[AgentLoggingHandler(), langwatch.langchain.LangChainTracer()]` | **Remove `AgentLoggingHandler()`** — leaves `callbacks=[langwatch.langchain.LangChainTracer()]`. |
| `src/robotina/queue/jobs.py` | 201 | `config={"callbacks": [AgentLoggingHandler()]}` (ImportError fallback branch) | **Drop the `config=` kwarg entirely** in this branch — middleware now emits log lines regardless of whether `langwatch` is importable. |
| `src/robotina/queue/jobs.py` | 38 | docstring step 7 — `"7. Create and invoke the ReAct agent with AgentLoggingHandler"` | **Update docstring** to reference middleware. |
| `src/robotina/llm/__init__.py` | `create_agent` methods (3 classes) — Ollama lines 225-245, Anthropic 269-283, OpenAI 307-321 | Build `kwargs` then `return _create_agent(**kwargs)` | **Add `middleware=[...]` to `kwargs`.** Import the three (or two) middleware instances from `robotina.agent.middleware`. |
| `tests/unit/test_agent_runner.py` | 152-161 | `test_agent_logging_handler_on_llm_start` | **Rewrite** — see Test Strategy below. |
| `tests/unit/test_agent_runner.py` | 164-176 | `test_agent_logging_handler_on_tool_start` | **Rewrite.** |
| `tests/unit/test_agent_runner.py` | 325-340 | `test_agent_logging_handler_on_tool_end` | **Rewrite.** |
| `experiments/recipe_research.py` | 254 | `config=RunnableConfig(callbacks=[tracer])` | **No change.** Experiments never used `AgentLoggingHandler` — only the LangWatch tracer. Logging will now come from middleware automatically because `build_agent()` calls `backend.create_agent(...)` which now installs middleware. |
| `experiments/recipe_load.py` | 248 | `config=RunnableConfig(callbacks=[tracer])` | **No change.** Same reason. |

Total: **3 source-file edits (delete + modify 2) + 1 test file rewrite (3 tests). No experiment touches needed.**

## Common Pitfalls

### Pitfall 1: Removing the LangWatch callback by mistake
**What goes wrong:** Refactor "removes all callbacks because we're using middleware now" → LangWatch traces stop appearing.
**Why it happens:** Conflating *logging callbacks* (replaceable) with *tracing callbacks* (not replaceable in LangWatch 0.17.0).
**How to avoid:** The plan's diff in `jobs.py` line 195 must read `callbacks=[langwatch.langchain.LangChainTracer()]` — non-empty. Add an explicit test that asserts the `langwatch.langchain.LangChainTracer` callback survives a successful `agent.invoke` call.
**Warning signs:** Smoke run produces log lines but no LangWatch trace in the dashboard.

### Pitfall 2: Calling `handler(request)` twice in `wrap_tool_call`
**What goes wrong:** Tool gets invoked twice; effects double; tests pass because the second result is the one returned.
**Why it happens:** Misreading the example — the handler-callback pattern is *one call per attempt*, so loops for retry are explicit. A common copy-paste mistake is `result = handler(request); ...; return handler(request)`.
**How to avoid:** Code review rule: every `@wrap_tool_call` and `@wrap_model_call` must have exactly one un-conditional `handler(request)` call per code path. Add a unit test that mocks the handler and asserts call count == 1 per tool invocation.
**Warning signs:** `HouseholdManagerApiTool` POSTs duplicated; `send-notification` delivers twice.

### Pitfall 3: Middleware decorator yields an INSTANCE, not a class
**What goes wrong:** Code writes `middleware=[log_before_model()]` (calling it) and gets `TypeError: AgentMiddleware instance is not callable`.
**Why it happens:** Reading the decorator signature suggests "returns a class", but it actually returns an instance — see `types.py:1041-1049` where the decorator does `return type(...)()` (note the trailing parens — instantiation).
**How to avoid:** Plan example code uses `middleware=[log_before_model, log_after_model, log_wrap_tool_call]` (no parens). Test imports and confirms `isinstance(log_before_model, AgentMiddleware)` is True.
**Warning signs:** `TypeError` at agent build time.

### Pitfall 4: Middleware state leak across jobs
**What goes wrong:** Middleware closes over per-job data (e.g., a `chat_id`); subsequent jobs see stale values.
**Why it happens:** Decorators run at import time and produce one shared instance. Robotina's STATE.md constraint ("all per-job objects instantiated inside `run_task`") was previously implemented by per-job callback instantiation. With module-level middleware, that pattern no longer applies.
**How to avoid:** Module-level middleware must be **stateless** — no closures over per-job data. Per-job context flows through `state` / `runtime`, not capture. For this phase the middleware is purely logging-stateless, so this is safe. Documenting it for the next phase that adds token-budget guards.
**Warning signs:** Cross-job data appears in logs (e.g., wrong `chat_id` logged on job B).

### Pitfall 5: `on_llm_end` / `after_model` semantics when streaming
**What goes wrong:** `Thinking` line missing on streamed responses.
**Why it happens:** `on_llm_end` only fires after the full response is assembled. `after_model` runs once per model node execution and sees the final `AIMessage` in state. Both should work — but only if `additional_kwargs.reasoning_content` is populated. ChatOllama with `reasoning=True` populates it; ChatAnthropic populates `additional_kwargs.thinking`; ChatOpenAI does not expose chain-of-thought.
**How to avoid:** The current callback handler only reads `reasoning_content` — a documented Ollama-specific kwarg. Phase 12 preserves the exact same key, so behaviour is identical. Just document the limitation in the phase summary.
**Warning signs:** Missing `Thinking | ...` log line on Anthropic / OpenAI runs (which was also the case before the migration — no regression).

### Pitfall 6: Test file colocation
**What goes wrong:** Tests for `AgentLoggingHandler` are in `tests/unit/test_agent_runner.py`. Deleting the symbol breaks 3 tests there even though they look like they belong somewhere else.
**Why it happens:** Test file naming doesn't match what they actually test.
**How to avoid:** Plan task explicitly enumerates the 3 tests (line numbers 152, 164, 325 in current file) and specifies whether to relocate them to `tests/unit/test_agent_middleware.py` (new file) or rewrite in place. Recommend new file for the new middleware tests; delete the three old tests from `test_agent_runner.py`.

## Code Examples

### Example A: The full middleware module (paste-ready)

```python
# src/robotina/agent/middleware.py
"""LangChain agent middleware for Robotina structured-action logging.

This module is the LangChain 1.x replacement for the legacy
``robotina.agent.callbacks.AgentLoggingHandler`` (Phase 12 migration).

Three middleware instances are exposed:
  - ``log_around_model_call``: emits ``LLM stream start | model=...`` for each
    model invocation.
  - ``log_after_model``: emits ``Thinking | ...`` when the latest AI message
    carries ``additional_kwargs.reasoning_content`` (Ollama / Anthropic).
  - ``log_wrap_tool_call``: emits ``Tool call | tool=... input=...`` and
    ``Tool result | output=...`` around each tool invocation.

LangWatch tracing remains on the LangChain callback bus and is wired
separately via ``RunnableConfig(callbacks=[langwatch.langchain.LangChainTracer()])``
at agent.invoke() time — see ``src/robotina/queue/jobs.py``.
"""
from __future__ import annotations

import logging
from typing import Callable

from langchain.agents.middleware import (
    after_model,
    wrap_model_call,
    wrap_tool_call,
    AgentState,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
)
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

logger = logging.getLogger(__name__)


@wrap_model_call
def log_around_model_call(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    """Log ``LLM stream start | model=...`` before invoking the model."""
    model_name = type(request.model).__name__
    logger.info("LLM stream start | model=%s", model_name)
    return handler(request)


@after_model
def log_after_model(state: AgentState, runtime: Runtime) -> None:
    """Log ``Thinking | <reasoning>`` when reasoning_content is present."""
    messages = state.get("messages") or []
    if not messages:
        return
    last = messages[-1]
    if not isinstance(last, AIMessage):
        return
    thinking = last.additional_kwargs.get("reasoning_content")
    if thinking:
        logger.info("Thinking | %s", thinking)


@wrap_tool_call
def log_wrap_tool_call(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    """Log ``Tool call | tool=... input=...`` then ``Tool result | output=...``."""
    name = request.tool_call.get("name")
    args = request.tool_call.get("args", {})
    logger.info("Tool call | tool=%s input=%s", name, str(args)[:200])

    result = handler(request)

    if isinstance(result, ToolMessage):
        logger.info("Tool result | output=%s", str(result.content)[:200])
    else:
        logger.info("Tool result | output=<Command>")
    return result
```

### Example B: `LLMBackend.create_agent` wiring (diff form)

```python
# src/robotina/llm/__init__.py, inside OllamaBackend.create_agent (mirror in
# AnthropicBackend.create_agent and OpenAIBackend.create_agent):

+ from robotina.agent.middleware import (
+     log_around_model_call,
+     log_after_model,
+     log_wrap_tool_call,
+ )
+
  kwargs: dict[str, Any] = {
      "model": self._model,
      "tools": tools or [],
      "system_prompt": system_prompt,
+     "middleware": [log_around_model_call, log_after_model, log_wrap_tool_call],
  }
```

### Example C: `jobs.py` agent-invoke wiring (diff form)

```python
# src/robotina/queue/jobs.py — Step 7 block

- from robotina.agent.callbacks import AgentLoggingHandler

  try:
      import langwatch
      import langwatch.langchain
      from langchain_core.runnables import RunnableConfig
      with langwatch.trace():
          result = agent.invoke(
              {"messages": [{"role": "user", "content": user_message}]},
              config=RunnableConfig(
-                 callbacks=[AgentLoggingHandler(), langwatch.langchain.LangChainTracer()]
+                 callbacks=[langwatch.langchain.LangChainTracer()]
              ),
          )
  except ImportError:
      result = agent.invoke(
          {"messages": [{"role": "user", "content": user_message}]},
-         config={"callbacks": [AgentLoggingHandler()]},
+         # Middleware emits log lines without needing the callback. No
+         # RunnableConfig needed in this branch.
      )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `BaseCallbackHandler` for in-agent observability | `langchain.agents.middleware` decorators (`@before_model`, `@after_model`, `@wrap_model_call`, `@wrap_tool_call`) | LangChain 1.0 (early 2026) | Middleware is the documented, typed, composable seam. Callbacks remain valid for *external* observers (tracing SDKs) but are no longer the recommended place to put behaviour. |
| `from langchain_core.callbacks import BaseCallbackHandler` for app logic | `from langchain.agents.middleware import before_model, after_model, wrap_tool_call` | Same | CLAUDE.md "What NOT to Use" table already encodes this. |

**Deprecated / outdated in this codebase post-migration:**
- `src/robotina/agent/callbacks.py` — delete or stub.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x + pytest-asyncio 1.x |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) — `testpaths = ["tests"]`, `asyncio_mode = "auto"` |
| Quick run command | `uv run pytest tests/unit/test_agent_middleware.py -x` (after Wave 0 creates the file) |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OBS-06 | Middleware emits `LLM stream start | model=...` when agent is invoked | unit | `uv run pytest tests/unit/test_agent_middleware.py::test_log_around_model_call_emits_llm_start -x` | ❌ Wave 0 |
| OBS-06 | Middleware emits `Thinking | ...` only when `reasoning_content` is present | unit | `uv run pytest tests/unit/test_agent_middleware.py::test_log_after_model_emits_thinking_when_present -x` | ❌ Wave 0 |
| OBS-06 | Middleware does NOT emit `Thinking` when `reasoning_content` is absent | unit | `uv run pytest tests/unit/test_agent_middleware.py::test_log_after_model_silent_when_absent -x` | ❌ Wave 0 |
| OBS-06 | Middleware emits `Tool call | tool=... input=...` then `Tool result | output=...` around tool invocation | unit | `uv run pytest tests/unit/test_agent_middleware.py::test_log_wrap_tool_call_brackets_handler -x` | ❌ Wave 0 |
| OBS-06 | `wrap_tool_call` calls handler exactly once per invocation (no double execution) | unit | `uv run pytest tests/unit/test_agent_middleware.py::test_log_wrap_tool_call_invokes_handler_once -x` | ❌ Wave 0 |
| OBS-06 | `LLMBackend.create_agent()` passes `middleware=[...]` to `_create_agent` for all 3 adapters | unit | `uv run pytest tests/unit/test_llm.py -k middleware -x` | ❌ Wave 0 (or update existing) |
| OBS-06 | `run_task()` agent.invoke callbacks list contains LangChainTracer when langwatch importable | unit (existing-style mock) | `uv run pytest tests/unit/test_agent_runner.py::test_run_task_passes_langwatch_tracer -x` | ❌ Wave 0 |
| OBS-06 | `run_task()` agent.invoke callbacks list does NOT contain AgentLoggingHandler (regression-prevention) | unit | `uv run pytest tests/unit/test_agent_runner.py::test_run_task_no_legacy_callback -x` | ❌ Wave 0 |
| OBS-06 | Production smoke: one full `handle-incoming-message` → queue → `send-notification` run produces correct LangWatch trace with model name, tool calls, token usage | manual | Manual smoke + LangWatch dashboard check | manual-only — gated by `uv run all` + Telegram |
| OBS-06 | Experiment smoke: one `uv run experiments.recipe_research` produces correct LangWatch trace | manual | Manual smoke + LangWatch dashboard check | manual-only |
| OBS-06 | No `from langchain_core.callbacks` imports remain in `src/robotina/agent/` (success criterion 4) | static check | `! grep -rn 'from langchain_core.callbacks' src/robotina/agent/` | inline shell |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_agent_middleware.py tests/unit/test_agent_runner.py -x` (~ a few seconds)
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green + two manual smoke runs (one production, one experiment) with LangWatch trace screenshot saved to phase summary

### Wave 0 Gaps
- [ ] `tests/unit/test_agent_middleware.py` — new file; covers OBS-06 unit tests above
- [ ] `tests/unit/conftest.py` — not needed; existing fixtures sufficient (`caplog`, `MagicMock`)
- [ ] Remove obsolete tests from `tests/unit/test_agent_runner.py` — lines 152-176 and 325-340 (3 tests targeting `AgentLoggingHandler`)
- [ ] Framework install: none — pytest already installed via `[project.optional-dependencies].dev` and `[dependency-groups].dev`

### Test Strategy Notes

How to test middleware emissions in unit tests (no LLM call needed — middleware is a callable that takes state/runtime or request/handler):

```python
# tests/unit/test_agent_middleware.py — sketch
import logging
import pytest
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage, ToolMessage

def test_log_around_model_call_emits_llm_start(caplog):
    from robotina.agent.middleware import log_around_model_call
    # log_around_model_call is an AgentMiddleware INSTANCE; the @wrap_model_call
    # decorator stored the function on .wrap_model_call (or call the wrapper directly).
    request = MagicMock()
    request.model = MagicMock()
    request.model.__class__.__name__ = "ChatOllama"
    handler = MagicMock(return_value="ok")

    with caplog.at_level(logging.INFO, logger="robotina.agent.middleware"):
        result = log_around_model_call.wrap_model_call(request, handler)

    assert result == "ok"
    handler.assert_called_once_with(request)
    assert any("LLM stream start" in r.message and "ChatOllama" in r.message for r in caplog.records)


def test_log_wrap_tool_call_brackets_handler(caplog):
    from robotina.agent.middleware import log_wrap_tool_call
    request = MagicMock()
    request.tool_call = {"name": "household-manager-api", "args": {"endpoint": "/meals"}, "id": "t1", "type": "tool_call"}
    tool_msg = ToolMessage(content="ok-result", tool_call_id="t1")
    handler = MagicMock(return_value=tool_msg)

    with caplog.at_level(logging.INFO, logger="robotina.agent.middleware"):
        result = log_wrap_tool_call.wrap_tool_call(request, handler)

    assert result is tool_msg
    handler.assert_called_once_with(request)
    msgs = [r.message for r in caplog.records]
    assert any("Tool call" in m and "household-manager-api" in m for m in msgs)
    assert any("Tool result" in m and "ok-result" in m for m in msgs)
```

Note: the test calls `log_around_model_call.wrap_model_call(request, handler)` directly — the decorator stored the function as a bound method on the generated `AgentMiddleware` subclass. This avoids needing to spin up a real `create_agent` graph for unit tests. [VERIFIED: pattern follows from `types.py:1880-1892` where `wrapped` is bound as `wrap_model_call` on the generated subclass.]

## Security Domain

> `security_enforcement` is not explicitly set in `.planning/config.json`, so treat as enabled. Phase scope is internal refactor only; no new attack surface.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No new auth surface; LangWatch API key handling unchanged. |
| V3 Session Management | no | No sessions. |
| V4 Access Control | no | No new authorization decisions. |
| V5 Input Validation | partial | Tool args are logged (input=`%s`, truncated to 200 chars). Logging untrusted input is unchanged from before; truncation prevents log injection bloat. Confirm 200-char truncation is preserved post-migration. |
| V6 Cryptography | no | None. |
| V7 Error Handling and Logging | yes | Phase deliberately changes logging — must preserve same redaction behaviour (none today, but tool args containing tokens would leak). Out of scope to add redaction; document as a follow-up. |

### Known Threat Patterns for {middleware refactor}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Sensitive value (e.g., API token in a tool arg) leaks into structured logs | Information disclosure | Existing 200-char truncation. No tool currently passes a raw secret as an arg (per code review). If that ever changes, a `@wrap_tool_call` redaction middleware is the right place — but out of scope here. |
| Middleware closure capturing per-job context bleeds across jobs | Tampering / Information disclosure | Document the rule "module-level middleware is stateless". Covered in Pitfall 4. |

## Assumptions Log

> Empty — every load-bearing claim was verified by reading source files in `.venv/` or by `uv pip show`.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| (none) | — | — | — |

All five "Key questions to answer" from the upstream brief are now answered with [VERIFIED] tags. No `[ASSUMED]` claims remain.

## Open Questions

1. **Should the migration delete `src/robotina/agent/callbacks.py` outright, or leave a shim?**
   - What we know: no production code outside `robotina/queue/jobs.py` imports the class.
   - What's unclear: nothing — but a shim with a `DeprecationWarning` is cheap insurance against forgotten downstream imports (e.g., a half-finished branch).
   - Recommendation: **Delete the file**. The codebase is small and `grep` already confirms the only consumer is `jobs.py`. A shim is over-engineering.

2. **Should the LangWatch callback wiring be moved to `LLMBackend.create_agent` or stay in `jobs.py`?**
   - What we know: it's in `jobs.py` today because the `langwatch.trace()` parent context must wrap the `.invoke()` call.
   - What's unclear: whether the experiments' per-run `metadata=` tagging still works if the callback is constructed inside `create_agent` (it doesn't take a metadata kwarg per-call).
   - Recommendation: **Leave the LangWatch wiring in `jobs.py` (production) and in each experiment script.** The middleware migration changes only the logging callback, not the tracing one.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `langchain` | middleware API | ✓ | 1.2.13 | — |
| `langgraph` | `Runtime`, `Command`, `ToolCallRequest` types | ✓ | 1.1.3 | — |
| `langwatch` | tracing | ✓ | 0.17.0 | non-fatal — `runner.py:_setup_langwatch` already skips if creds missing |
| `pytest` | unit tests | ✓ | (dev dep) | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none.

## Sources

### Primary (HIGH confidence — verified against installed source on 2026-05-13)
- `langchain==1.2.13`, `.venv/lib/python3.12/site-packages/langchain/agents/middleware/__init__.py` — confirms decorators `before_model`, `after_model`, `wrap_model_call`, `wrap_tool_call`, `before_agent`, `after_agent`, `dynamic_prompt`, `hook_config` are all exported; confirms types `AgentMiddleware`, `AgentState`, `ModelRequest`, `ModelResponse`, `ToolCallRequest`, `ExtendedModelResponse`.
- `.venv/lib/python3.12/site-packages/langchain/agents/middleware/types.py` — signatures, decorator return shapes, composition semantics, async/sync handling.
- `.venv/lib/python3.12/site-packages/langchain/agents/factory.py:673-790` — `create_agent` signature confirming `middleware: Sequence[AgentMiddleware]` kwarg.
- `langwatch==0.17.0`, `.venv/lib/python3.12/site-packages/langwatch/langchain.py:110` — confirms `LangChainTracer(BaseCallbackHandler)` inheritance.
- `.venv/lib/python3.12/site-packages/openinference/instrumentation/langchain/__init__.py:26-58` — confirms OTel auto-instrumentor monkey-patches `BaseCallbackManager.__init__`.
- `.venv/lib/python3.12/site-packages/langwatch/client.py:158-179, 251-264` — confirms `langwatch.setup(instrumentors=...)` defaults to empty tuple.

### Secondary (HIGH confidence — repo source)
- `src/robotina/agent/callbacks.py` — current 44-line implementation.
- `src/robotina/queue/jobs.py:23, 191-202` — current callback wiring.
- `src/robotina/llm/__init__.py:225-321` — three `create_agent` methods to update.
- `experiments/recipe_research.py:236-255`, `experiments/recipe_load.py:232-248` — experiment-side LangWatch wiring (no change needed).
- `tests/unit/test_agent_runner.py:152-176, 325-340` — three tests to delete/rewrite.

### Tertiary
- LangChain official docs (cited in middleware module docstring): https://docs.langchain.com/oss/python/langchain/middleware — referenced but not re-fetched; installed source is authoritative for this phase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version is pinned in `pyproject.toml`/`uv.lock` and confirmed via `uv pip show`.
- Architecture: HIGH — decorator signatures, return shapes, and composition semantics read directly from installed `types.py`. Concrete code examples were derived from that file.
- LangWatch interaction model: HIGH — answered by reading `langwatch/langchain.py:110`. The "is LangWatch callback-based or OTel-based?" question is settled: callback-based, with an optional OTel-auto-instrumentor path that itself wraps callbacks. Either way, the LangWatch callback wiring stays.
- Pitfalls: MEDIUM-HIGH — derived from reading the implementation, but some (e.g., closure capture leaks) are general LangChain wisdom not yet exercised in this codebase.

**Research date:** 2026-05-13
**Valid until:** 2026-06-13 (LangChain 1.x and LangWatch 0.17.x are stable; re-verify if either is bumped to a new major).
