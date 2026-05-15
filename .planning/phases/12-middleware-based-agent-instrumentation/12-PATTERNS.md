# Phase 12: Middleware-Based Agent Instrumentation - Pattern Map

**Mapped:** 2026-05-13
**Files analyzed:** 5 (1 delete + 1 create + 2 edit + 1 new test file; plus pruning of an existing test file)
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Action | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|--------|------|-----------|----------------|---------------|
| `src/robotina/agent/callbacks.py` | DELETE | callbacks (legacy) | event-driven (LangChain bus) | — | n/a (target of deletion) |
| `src/robotina/agent/middleware.py` | CREATE | agent middleware | event-driven (in-graph hooks) | `src/robotina/agent/callbacks.py` (semantic twin — same log lines) | exact (one-for-one functional replacement) |
| `src/robotina/llm/__init__.py` | EDIT | adapter / factory | request-response (build agent) | self — three near-identical `create_agent` methods (OllamaBackend, AnthropicBackend, OpenAIBackend) | exact (mirror change across 3 methods) |
| `src/robotina/queue/jobs.py` | EDIT | job orchestrator | event-driven (RQ worker) | self (lines 23, 187–202) — the existing callback wiring site | exact |
| `tests/unit/test_agent_middleware.py` | CREATE | unit tests | request-response (direct call) | `tests/unit/test_agent_runner.py` lines 152–176, 325–340 (`caplog`-based logging tests) | exact (caplog pattern reusable verbatim) |
| `tests/unit/test_agent_runner.py` | EDIT (prune) | unit tests | request-response | self (3 tests to delete in place) | exact |

## Pattern Assignments

### `src/robotina/agent/middleware.py` (CREATE — agent middleware, event-driven)

**Analog:** `src/robotina/agent/callbacks.py` (lines 1–44) — semantic twin. Same logger, same module-level instance pattern, same log line keys (`LLM stream start`, `Thinking`, `Tool call`, `Tool result`), same 200-char truncation. The new module is a one-for-one structural mirror with three decorator-based instances instead of one class with four methods.

**Module header / imports pattern** (analog `callbacks.py` lines 1–8):
```python
"""LangChain callback handlers for Robotina agents."""
from __future__ import annotations

import logging

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)
```

Copy this shape exactly — `from __future__ import annotations`, single `logger = logging.getLogger(__name__)` at module scope, concise module docstring. Only the import surface changes (swap `BaseCallbackHandler` for the `langchain.agents.middleware` decorators and types).

**Log-line emission pattern** (analog `callbacks.py` lines 24–43):
```python
def on_chat_model_start(self, serialized: dict, messages: list, **kwargs) -> None:
    logger.info("LLM stream start | model=%s", serialized.get("name"))

def on_llm_end(self, response, **kwargs) -> None:
    for gen_list in response.generations:
        for gen in gen_list:
            msg = getattr(gen, "message", None)
            thinking = msg and msg.additional_kwargs.get("reasoning_content")
            if thinking:
                logger.info("Thinking | %s", thinking)

def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
    logger.info(
        "Tool call | tool=%s input=%s",
        serialized.get("name"),
        str(input_str)[:200],
    )

def on_tool_end(self, output: str, **kwargs) -> None:
    logger.info("Tool result | output=%s", str(output)[:200])
```

The four log statements above are the load-bearing behavioural contract. The replacement middleware MUST emit log lines that match these four format strings byte-for-byte (including the `| model=`, `| tool=`, `input=`, `output=` separators and the 200-char truncation). Anything else changes observable behaviour. The new module body (decorator-based) is fully specified in `12-RESEARCH.md` §"Code Examples / Example A" — copy that body verbatim into `src/robotina/agent/middleware.py`.

**Stateless-module rule** (carried from STATE.md Phase 4 constraint, see `src/robotina/llm/__init__.py` lines 8–12 and 167–169): `callbacks.py` defines a stateless class so any instantiation can happen anywhere. The middleware module is more constrained — decorators yield singleton instances at import time, so the rule is: no closures over per-job data, no module-level mutable state, no I/O at import. See RESEARCH.md Pitfall 4.

---

### `src/robotina/llm/__init__.py` (EDIT — adapter / factory, request-response)

**Analog (self-similarity):** Three sibling methods in this same file — `OllamaBackend.create_agent` (lines 225–245), `AnthropicBackend.create_agent` (lines 269–283), `OpenAIBackend.create_agent` (lines 307–321). All three share an identical `kwargs: dict[str, Any] = {...}` → conditional `response_format` strategy wrapping → `return _create_agent(**kwargs)` shape. The Phase 12 edit applies the SAME diff to all three.

**Existing kwargs-building pattern** (lines 231–245 — OllamaBackend; mirror in the other two):
```python
kwargs: dict[str, Any] = {
    "model": self._model,
    "tools": tools or [],
    "system_prompt": system_prompt,
}
if response_format is not None:
    # ... ToolStrategy / ProviderStrategy branch ...
    kwargs["response_format"] = ToolStrategy(response_format)
return _create_agent(**kwargs)
```

**Pattern to apply** — add a fixed `middleware` key to the kwargs dict, in the same place response_format was added in Phase 11 (i.e. as a new line in the literal dict, before the `response_format` conditional). The middleware list is identical across all three adapters because the middleware is provider-agnostic.

```python
# Imported at module top (alongside the existing langchain.agents.create_agent import on line 32):
from robotina.agent.middleware import (
    log_around_model_call,
    log_after_model,
    log_wrap_tool_call,
)

# Inside each *.create_agent method, kwargs literal becomes:
kwargs: dict[str, Any] = {
    "model": self._model,
    "tools": tools or [],
    "system_prompt": system_prompt,
    "middleware": [log_around_model_call, log_after_model, log_wrap_tool_call],
}
```

**Import-site precedent** (line 32):
```python
from langchain.agents import create_agent as _create_agent  # AGENT-12
```

Follow this same style for the new import — module-level, top-of-file alongside other LangChain imports. Do NOT lazy-import inside `create_agent` methods; the middleware module has no heavy side effects (RESEARCH.md confirms it must be import-side-effect-free).

**Docstring precedent** (lines 184–199 — `LLMBackend.create_agent` Protocol docstring): mentions AGENT-12 + Phase 11 response_format wiring. Add a one-sentence note that middleware is now installed by default, with a phase tag (e.g. `# AGENT-13 / Phase 12`) — keep the audit-trail comment style consistent with the existing AGENT-12 marker on line 32.

---

### `src/robotina/queue/jobs.py` (EDIT — job orchestrator, event-driven worker)

**Analog (self):** Existing callback wiring at lines 23, 38, 180–202.

**Current import** (line 23):
```python
from robotina.agent.callbacks import AgentLoggingHandler
```
**Action:** Remove this import.

**Current docstring step 7** (line 38):
```python
7. Create and invoke the ReAct agent with AgentLoggingHandler
```
**Action:** Update wording. Pattern for the replacement comes from the existing Phase-11 docstring note (lines 176–179) which references the structured-output thread. New wording: `7. Create and invoke the agent (per-agent logging emitted by middleware; LangWatch trace via callback bus).`

**Current invoke wiring** (lines 187–202) — this is the load-bearing block:
```python
try:
    import langwatch
    import langwatch.langchain
    from langchain_core.runnables import RunnableConfig
    with langwatch.trace():
        result = agent.invoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config=RunnableConfig(
                callbacks=[AgentLoggingHandler(), langwatch.langchain.LangChainTracer()]
            ),
        )
except ImportError:
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config={"callbacks": [AgentLoggingHandler()]},
    )
```

**Replacement** (verbatim from `12-RESEARCH.md` §"Code Examples / Example C"):
```python
try:
    import langwatch
    import langwatch.langchain
    from langchain_core.runnables import RunnableConfig
    with langwatch.trace():
        result = agent.invoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config=RunnableConfig(
                callbacks=[langwatch.langchain.LangChainTracer()]
            ),
        )
except ImportError:
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
    )
```

**Critical pattern to preserve** (anti-pattern Pitfall 1 in RESEARCH): the `langwatch.langchain.LangChainTracer()` callback MUST survive. The diff is a removal of `AgentLoggingHandler()` only — the callbacks list is non-empty in the `try` branch.

---

### `tests/unit/test_agent_middleware.py` (CREATE — unit tests)

**Analog:** `tests/unit/test_agent_runner.py` lines 152–176, 325–340 — three existing `caplog`-based tests for `AgentLoggingHandler`. These are the direct functional predecessors and use the EXACT pattern the new tests should follow.

**Test imports / fixture pattern** (analog `test_agent_runner.py` lines 1–12 — top of file):
```python
"""Tests for run_task() universal job function and AgentLoggingHandler.

Tests verify:
- AGENT-06: ...
- AGENT-10: AgentLoggingHandler logs LLM start, tool start, and tool end events
"""
import logging
from unittest.mock import MagicMock, patch

import pytest
```
Copy this header shape: short docstring listing the req IDs covered, `import logging`, `from unittest.mock import MagicMock, patch`, `import pytest`. Pattern lines up with every other file in `tests/unit/` (see also `tests/unit/test_observability.py` lines 1–11).

**`caplog` + `at_level` pattern** (analog `test_agent_runner.py` lines 152–161, 325–340):
```python
def test_agent_logging_handler_on_llm_start(caplog):
    """AGENT-10: AgentLoggingHandler.on_chat_model_start logs LLM stream start."""
    from robotina.agent.callbacks import AgentLoggingHandler

    handler = AgentLoggingHandler()
    with caplog.at_level(logging.INFO, logger="robotina.agent.callbacks"):
        handler.on_chat_model_start({"name": "ChatOllama"}, [[]])

    assert any("ChatOllama" in record.message for record in caplog.records), \
        f"Expected 'ChatOllama' in log. Got: {[r.message for r in caplog.records]}"
```

**Key conventions to copy:**
1. Function-local import (`from robotina.agent.middleware import ...` inside each test) — keeps import-time side effects out of test collection. Matches all three legacy tests at lines 154, 166, 327.
2. `with caplog.at_level(logging.INFO, logger="robotina.agent.middleware"):` — explicit logger name parameter. The legacy tests use `"robotina.agent.callbacks"`; new tests must use `"robotina.agent.middleware"` to match where `logger = logging.getLogger(__name__)` resolves.
3. Assertion style: `any("SUBSTRING" in record.message for record in caplog.records)` with an f-string failure message that dumps the full message list. Used verbatim at lines 160–161, 173–176, and 334–340 of `test_agent_runner.py`.

**200-char truncation regression test pattern** (analog `test_agent_runner.py` lines 325–340 — the on_tool_end test):
```python
def test_agent_logging_handler_on_tool_end(caplog):
    """AGENT-10: AgentLoggingHandler.on_tool_end logs tool output (truncated to 200 chars)."""
    from robotina.agent.callbacks import AgentLoggingHandler

    handler = AgentLoggingHandler()
    long_output = "x" * 500
    with caplog.at_level(logging.INFO, logger="robotina.agent.callbacks"):
        handler.on_tool_end(long_output)

    messages = [r.message for r in caplog.records]
    assert len(messages) > 0, "Expected at least one log message"
    combined = " ".join(messages)
    assert "x" * 201 not in combined, "Output was not truncated to 200 chars"
    assert "x" * 200 in combined or "x" * 199 in combined, \
        f"Expected truncated output in log. Got: {combined[:100]}"
```

This truncation assertion (`"x" * 201 not in combined`) is load-bearing and must be carried over to the new middleware test for `log_wrap_tool_call`'s `Tool result` line — it preserves the V5/V7 security boundary (Tool args / outputs truncated to 200 chars to prevent log injection bloat; see RESEARCH §Security Domain).

**Direct-call pattern for middleware instances** (from RESEARCH.md §"Test Strategy Notes" — verified against `langchain/agents/middleware/types.py:1880-1892`):
```python
# Decorator stored the function as a bound method on the generated AgentMiddleware
# subclass. Direct call sidesteps needing a full create_agent graph.
result = log_around_model_call.wrap_model_call(request, handler)
result = log_wrap_tool_call.wrap_tool_call(request, handler)
```

Use `MagicMock()` for `request`, `request.model`, and `handler` — matches the mocking style established in `test_agent_runner.py` lines 36–49 (MagicMock-heavy fixture construction).

**Test set** (from RESEARCH §"Validation Architecture / Phase Requirements → Test Map"):
- `test_log_around_model_call_emits_llm_start`
- `test_log_after_model_emits_thinking_when_present`
- `test_log_after_model_silent_when_absent`
- `test_log_wrap_tool_call_brackets_handler`
- `test_log_wrap_tool_call_invokes_handler_once` (Pitfall 2: double-execution regression)
- `test_log_wrap_tool_call_truncates_output_to_200_chars` (carry the legacy truncation invariant)

---

### `tests/unit/test_agent_runner.py` (EDIT — prune obsolete tests)

**Action:** Delete three tests (lines 152–161, 164–176, 325–340) that import `AgentLoggingHandler`. Update the module docstring at lines 1–7 to remove the `AGENT-10: AgentLoggingHandler` bullet, OR replace it with a forward-reference comment pointing to `test_agent_middleware.py`.

**Pattern for module-docstring update** (current lines 1–7):
```python
"""Tests for run_task() universal job function and AgentLoggingHandler.

Tests verify:
- AGENT-06: run_task reads task_type from RQ job meta, not from input model
- AGENT-07: LLM backend is created inside run_task, not at module level
- AGENT-10: AgentLoggingHandler logs LLM start, tool start, and tool end events
"""
```

**Replacement** — drop the third bullet, drop the trailing "and AgentLoggingHandler" from the first line. Result:
```python
"""Tests for run_task() universal job function.

Tests verify:
- AGENT-06: run_task reads task_type from RQ job meta, not from input model
- AGENT-07: LLM backend is created inside run_task, not at module level
"""
```

The remaining tests (run_task task-type reading, per-job tool injection, module-level instantiation guard) are unaffected by Phase 12 and stay byte-for-byte.

## Shared Patterns

### Module-Level Logger
**Source:** `src/robotina/agent/callbacks.py` line 8 — `logger = logging.getLogger(__name__)`
**Also in:** `src/robotina/llm/__init__.py` line 36; `src/robotina/queue/jobs.py` line 25
**Apply to:** `src/robotina/agent/middleware.py` (new file).
Single module-scope logger named via `__name__`. No custom formatter, no handler installation in the module itself — those are configured globally by `configure_logging()` in `agents.py` (see `test_observability.py` lines 62–78 for that contract).

### Phase / Requirement Tags in Comments
**Source:** `src/robotina/llm/__init__.py` line 32 — `from langchain.agents import create_agent as _create_agent  # AGENT-12`
**Also in:** `src/robotina/queue/jobs.py` line 89 (`# Phase 07.1: deterministic non-LLM path...`), lines 130, 174–179 (Phase 11 reference)
**Apply to:** All Phase 12 edits should carry a single inline `# AGENT-XX / Phase 12` marker at the introduction point (middleware import in `llm/__init__.py`; removal site in `jobs.py`). Pattern matches existing audit-trail style and is greppable for future migration phases.

### Import-Time Side-Effect Discipline
**Source:** `src/robotina/llm/__init__.py` lines 6–12 (STATE.md constraint quoted) — "All adapter instances MUST be created inside job functions (run_task), never at module level."
**Also enforced by:** `tests/unit/test_agent_runner.py` lines 90–149 — `test_no_llm_instantiation_at_import_time` which patches `ChatOllama`/`ChatAnthropic`/`ChatOpenAI` to raise if called during `import robotina.queue.jobs`.
**Apply to:** `src/robotina/agent/middleware.py`. The decorators DO produce module-level singletons (this is intrinsic to LangChain 1.x's `@before_model` / `@after_model` / `@wrap_tool_call` API — see Pitfall 3 / 4 in RESEARCH). That's allowed because the singletons hold no per-job state. The plan must include an assertion (one new test or static check) that the module imports without side effects beyond the three middleware-instance constructions.

### `RunnableConfig(callbacks=[...])` Wiring
**Source:** `src/robotina/queue/jobs.py` lines 188–197 (current shape)
**Pattern reference:** RESEARCH.md §"Anti-Patterns to Avoid" — `langwatch.langchain.LangChainTracer` must remain in the callbacks list post-migration. The diff is **subtractive only** (remove `AgentLoggingHandler()`); never replace the list with an empty `[]`.

### Test-File Naming + Layout
**Source:** `tests/unit/` has one test file per source module being tested (`test_agent_runner.py`, `test_llm_backend.py`, `test_skills.py`, `test_agents_registry.py`, `test_queue_tool.py`, ...). Each starts with a 3–10-line docstring listing requirement IDs.
**Apply to:** New file is `tests/unit/test_agent_middleware.py` (matches `src/robotina/agent/middleware.py`). Use the same docstring → imports → test-function order. No conftest.py changes needed (RESEARCH confirms `caplog` + `MagicMock` cover all assertions).

## No Analog Found

| File | Reason |
|------|--------|
| (none) | Every file in this phase has a close analog — either the file itself (edits) or a semantic twin (`callbacks.py` → `middleware.py`; `test_agent_runner.py` callback tests → `test_agent_middleware.py` middleware tests). The migration is structurally symmetric. |

## Metadata

**Analog search scope:**
- `src/robotina/agent/` (callbacks.py, agents.py, workflows.py, __init__.py, tools/)
- `src/robotina/llm/__init__.py`
- `src/robotina/queue/jobs.py`
- `tests/unit/` (all 11 files listed for layout / fixture conventions)

**Files scanned:** 18 source/test files (per Glob results above).

**Pattern extraction date:** 2026-05-13

**Confidence:** HIGH. RESEARCH.md already verified all decorator signatures, LangWatch interaction, and call-site inventory. PATTERNS.md adds the codebase-local extraction (existing log-line format strings, caplog conventions, the three-mirror `create_agent` shape) that the planner needs to write per-task instructions.
