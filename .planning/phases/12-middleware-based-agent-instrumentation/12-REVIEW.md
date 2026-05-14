---
phase: 12-middleware-based-agent-instrumentation
reviewed: 2026-05-13T00:00:00Z
fix_applied_at: 2026-05-13T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - src/robotina/agent/middleware.py
  - src/robotina/llm/__init__.py
  - src/robotina/queue/jobs.py
  - tests/unit/test_agent_middleware.py
  - tests/unit/test_agent_runner.py
  - tests/unit/test_llm_backend.py
findings:
  critical: 0
  warning: 2
  info: 5
  total: 7
findings_resolved:
  - WR-01  # middleware.py docstring — sync-only constraint added
  - IN-01  # middleware.py docstring — class-name reference updated
  - IN-04  # test_agent_runner.py — AsyncMock substitution for send_message
  - IN-05  # test_agent_runner.py — split test_run_task_no_legacy_callback in two
findings_deferred:
  - WR-02  # pre-existing jobs.py session leak — out of Phase 12 diff scope
  - IN-02  # log-injection hardening — separate observability item; legacy parity intentional
  - IN-03  # pre-existing _RetryingChatOllama assert under -O — out of Phase 12 diff scope
status: review_fixes_applied
---

# Phase 12: Code Review Report

**Reviewed:** 2026-05-13T00:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

The Phase 12 migration from `langchain_core.callbacks.BaseCallbackHandler` to `langchain.agents.middleware` decorators is implemented correctly in its central invariants. The four log lines are preserved byte-for-byte (`LLM stream start | model=…`, `Thinking | …`, `Tool call | tool=… input=…`, `Tool result | output=…`), the 200-character truncation is intact, `_create_agent(middleware=[…])` is wired identically across all three backends, and `langwatch.langchain.LangChainTracer` survives in `jobs.py:199` as a non-empty callbacks list (the LangWatch invariant called out in the spec). Middleware module is import-side-effect-free; singletons hold no per-job state.

Adversarial cross-checks against the installed `langchain==1.2.13` source (`.venv/.../langchain/agents/middleware/types.py`) confirm the decorator API and handler signatures used in `middleware.py` match the upstream contract.

Two warnings and five info-level findings below. No blockers — code is safe to ship pending the documented human smoke checkpoint (Task 2.3).

## Warnings

### WR-01: Async-invocation path will raise `NotImplementedError` inside middleware

**File:** `src/robotina/agent/middleware.py:50-112`
**Issue:** All three decorators (`@wrap_model_call`, `@after_model`, `@wrap_tool_call`) are applied to **sync** functions. The `wrap_*_call` decorators generate an `AgentMiddleware` subclass that populates only the sync hook; the async counterpart (`awrap_model_call`, `awrap_tool_call`) inherits the base-class implementation which raises `NotImplementedError` with a guidance message (verified at `.venv/.../langchain/agents/middleware/types.py:719-729`). The codebase today is sync-only (`agent.invoke(...)` in `jobs.py:193`, grep for `ainvoke|astream` returns no matches), so this is not a current bug. However, `_RetryingChatOllama` already implements both `_generate` and `_agenerate` (`src/robotina/llm/__init__.py:106, 137`), suggesting async readiness elsewhere in the stack. A future caller that switches to `agent.ainvoke()` will hit `NotImplementedError` at the first tool call with a misleading message that points to the user's middleware rather than the framework wiring.
**Fix:** Either (a) document the sync-only constraint explicitly in `middleware.py`'s module docstring (cheapest), or (b) provide async parity by adding `@awrap_tool_call` / `@awrap_model_call` decorators that mirror the sync logic. Suggested minimal docstring addition:

```python
"""LangChain agent middleware for Robotina structured-action logging.

...

CONSTRAINT: sync-only. The decorators below generate sync hooks only.
Invoking the agent via ``ainvoke``/``astream`` will raise
``NotImplementedError`` from the base-class async hook. Robotina invokes
agents synchronously today (``agent.invoke(...)`` in queue/jobs.py); revisit
if async invocation is introduced.
"""
```

### WR-02: Session leak when `workflow_runner.on_step_start` raises

**File:** `src/robotina/queue/jobs.py:76-84`
**Issue:** `_session = SessionLocal()` is created on line 76, then `workflow_runner.on_step_start(job.id, _session)` is invoked on line 84 **outside** any `try`/`finally`. The outer `try` block that owns the matching `finally: _session.close()` does not start until line 114. If `on_step_start` raises (DB connection error, integrity constraint, etc.), the SQLAlchemy session is leaked — no `.close()` runs, and the exception propagates to RQ. This is **pre-existing** code (Phase 5/Phase 07.1 layered in `on_step_start` / send-notification), not Phase 12's change, but the file is in scope and the leak is real.
**Fix:** Move the `_session = SessionLocal()` line to inside a single `try`/`finally` that brackets the entire function body, or use a context manager:

```python
_session = SessionLocal()
try:
    _queue_name = job.meta.get("queue_name", "agent-tasks")
    _queue = Queue(
        _queue_name,
        connection=Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379")),
    )
    workflow_runner.on_step_start(job.id, _session)
    # ... rest of function (including send-notification branch and main flow)
finally:
    _session.close()
```

This also removes the duplicated `_session.close()` calls in the two inner `finally` blocks (lines 112, 221) and the nested `try` in the send-notification branch.

## Info

### IN-01: `log_around_model_call` docstring claims model class names that won't appear in production

**File:** `src/robotina/agent/middleware.py:55-60`
**Issue:** The docstring states `request.model` is the `BaseChatModel` instance (`ChatOllama` / `ChatAnthropic` / `ChatOpenAI`). For the Ollama backend, however, `request.model` is an instance of the local subclass `_RetryingChatOllama` (`src/robotina/llm/__init__.py:89`). `type(request.model).__name__` will therefore log `model=_RetryingChatOllama` in production, not `model=ChatOllama`. Parity with the legacy callback is preserved (it used `serialized.get("name")` which also returns the actual class name), but the docstring drifts from runtime reality.
**Fix:** Update the docstring to either name the actual classes or note the wrapper:

```python
"""Log ``LLM stream start | model=<ChatClassName>`` before each model call.

Replaces ``AgentLoggingHandler.on_chat_model_start``. The class name comes
from ``type(request.model).__name__`` — ``request.model`` is the underlying
``BaseChatModel`` instance (``_RetryingChatOllama`` for Ollama,
``ChatAnthropic`` for Anthropic, ``ChatOpenAI`` for OpenAI; the Ollama
wrapper is a local retry subclass — see ``robotina.llm._RetryingChatOllama``).
"""
```

### IN-02: Log injection vector via unescaped newlines in tool args/output

**File:** `src/robotina/agent/middleware.py:102,107`
**Issue:** `logger.info("Tool call | tool=%s input=%s", name, str(args)[:200])` and `logger.info("Tool result | output=%s", str(result.content)[:200])` truncate by character count but do not escape newlines or other control characters. A tool argument or tool output containing `\n` followed by attacker-controlled text will produce log lines that visually impersonate other log records (CWE-117). The truncation prevents log bloat but not impersonation. This is parity with the legacy callback (`AgentLoggingHandler.on_tool_start/end`) and Phase 12 explicitly preserves the legacy boundary, so this is **not a regression**. Worth flagging because the V5/V7 ASVS comment in the middleware module claims the 200-char cap is the boundary — log-injection is a separate ASVS surface that the byte-cap does not address.

For most Robotina tools (HouseholdManagerApiTool returns JSON, WebSearchTool returns Tavily JSON), the output is JSON-safe at the source. Risk is highest for any future tool that returns free-form user-controlled text.
**Fix:** Optional hardening — sanitize control characters before logging:

```python
def _safe(s: str, limit: int = 200) -> str:
    # repr() escapes newlines/tabs/control chars and quotes; strip surrounding
    # quotes to keep log readable.
    return repr(s)[1:-1][:limit]

logger.info("Tool call | tool=%s input=%s", name, _safe(str(args)))
logger.info("Tool result | output=%s", _safe(str(result.content)))
```

Track as a separate observability hardening item; not a Phase 12 blocker.

### IN-03: `assert last_exc is not None` stripped under `python -O`

**File:** `src/robotina/llm/__init__.py:134, 165`
**Issue:** Both `_RetryingChatOllama._generate` and `_agenerate` use a defensive `assert last_exc is not None` before `raise last_exc` to satisfy type-checking. Under `python -O` (optimization flag), `assert` statements are elided, leaving `raise None` which raises `TypeError: exceptions must derive from BaseException`. The loop body guarantees `last_exc` is set on the only path that reaches the assertion, so this is unreachable in practice. Pre-existing code; not Phase 12's change.
**Fix:** Replace assertion with an explicit safe raise that survives `-O`:

```python
# Defensive: loop only exits via return or raise.
if last_exc is None:
    raise RuntimeError("retry loop exited without setting last_exc")  # unreachable
raise last_exc
```

### IN-04: `test_run_task_send_notification_takes_deterministic_path` triggers real `asyncio.run` overhead

**File:** `tests/unit/test_agent_runner.py:66-109`
**Issue:** The test patches `robotina.gateway.send.send_message` to return `mock_send_result`, but `jobs.py:94` wraps the call in `asyncio.run(send_message(...))`. Since the patched `send_message` is a `MagicMock` returning a `MagicMock`, `asyncio.run()` receives a non-awaitable and will raise `ValueError: a coroutine was expected`. The test passes today only because `asyncio.run` is somehow tolerating the mocked return value — verify by running this test in isolation. If it currently passes, it does so by accident; if a future asyncio version tightens the check, the test will break without indicating a real regression.
**Fix:** Patch with `AsyncMock` or wrap the return in a coroutine:

```python
from unittest.mock import AsyncMock
mock_send_result = MagicMock(message_id="42")
async_send = AsyncMock(return_value=mock_send_result)
with patch("robotina.gateway.send.send_message", new=async_send):
    ...
```

### IN-05: `test_run_task_no_legacy_callback` couples two unrelated assertions

**File:** `tests/unit/test_agent_runner.py:241-254`
**Issue:** This test asserts both (a) `robotina.agent.callbacks` is no longer importable and (b) `AgentLoggingHandler` is not in the captured `RunnableConfig.callbacks` list. Both are valid regression guards but failing for unrelated reasons. If a future commit re-adds the legacy module but the callback wiring stays clean, the test fails at (a) and you never learn the state of (b). Cleaner to split into two tests so a failure points at the actual regression direction.
**Fix:** Split into `test_legacy_callbacks_module_deleted` and `test_run_task_does_not_pass_agent_logging_handler`. Minor — current form is functional.

---

## Notes — what was verified but found clean

- **Middleware decorator signatures match upstream contract.** `wrap_model_call` expects `(request: ModelRequest, handler: Callable) -> ModelResponse | AIMessage | ExtendedModelResponse` (`.venv/.../langchain/agents/middleware/types.py:478-482`); the middleware returns `handler(request)` directly, preserving whatever the handler returns. `after_model` expects `(state, runtime) -> dict | None`; the middleware returns `None` implicitly. `wrap_tool_call` expects `(request: ToolCallRequest, handler) -> ToolMessage | Command`; returned correctly.
- **Handler invoked exactly once.** `log_wrap_tool_call` calls `handler(request)` on line 104 and never retries — explicit guard against the Pitfall 2 double-execution regression. `test_log_wrap_tool_call_invokes_handler_once` asserts `handler.call_count == 1`.
- **200-char truncation preserved.** Both input and output truncation present (`middleware.py:102, 107`). `test_log_wrap_tool_call_truncates_output_to_200_chars` asserts `"x" * 201 not in combined`.
- **LangWatch tracer non-empty.** `jobs.py:199` passes `callbacks=[langwatch.langchain.LangChainTracer()]` — single-element list, satisfies the "must be non-empty" invariant from RESEARCH.md Pitfall 1. Regression guard test `test_run_task_passes_langwatch_tracer` asserts class presence in the captured callbacks.
- **Module import is side-effect-free.** No top-level I/O, env reads, or network calls. The three module-level decorator invocations construct `AgentMiddleware` instances eagerly (`types.py:1041-1049` / `:2040-2048`), which is the expected and documented behavior.
- **No closure capture of per-job state.** Middleware singletons read all per-call data from `request` / `state` / `runtime` arguments — Pitfall 4 honored.
- **Type-annotation imports all used.** `ModelRequest`, `ModelResponse`, `ToolCallRequest`, `AgentState`, `Runtime`, `AIMessage`, `ToolMessage`, `Command` are each used in either a function annotation or an `isinstance` check.
- **MagicMock `__class__.__name__` test pattern is safe.** Empirically verified that `mock.__class__.__name__ = "ChatOllama"` mutates per-instance proxy state and does **not** pollute the global `MagicMock` class — newly constructed `MagicMock()` instances after the assignment still report `__name__ == "MagicMock"`. The test fixture in `test_log_around_model_call_emits_llm_start` is therefore isolation-safe.
- **`from langchain_core.callbacks` carve-out in `llm/__init__.py:23-26` is required.** `CallbackManagerForLLMRun` / `AsyncCallbackManagerForLLMRun` appear in the `BaseChatModel._generate/_agenerate` signature contract — removing them would break the override. This is documented as the SC#4 carve-out and not a quality issue.

---

_Reviewed: 2026-05-13T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

---

## Fix status (2026-05-13)

Review-fix pass applied via `/gsd-code-review --fix --auto` against the Phase 12 diff.

| Finding | Status | Commit / Notes |
|---------|--------|----------------|
| WR-01   | **Resolved** | Sync-only constraint added to `middleware.py` module docstring. Async parity (NotImplementedError-raising base hooks) called out explicitly. |
| WR-02   | **Deferred** | Pre-existing `jobs.py` session leak, predates Phase 12. Tracked in `deferred-items.md`. Out of Phase 12 diff scope. |
| IN-01   | **Resolved** | `log_around_model_call` docstring updated — names `_RetryingChatOllama` for Ollama and notes the wrapper. |
| IN-02   | **Skipped** | Log-injection hardening — minimal `\n`-only sanitization would create false sense of safety (does not handle `\r`, `\t`, ANSI escapes). Tracked in `deferred-items.md` as a separate observability item. |
| IN-03   | **Deferred** | Pre-existing `_RetryingChatOllama` `assert` under `python -O`. Out of Phase 12 diff scope. Tracked in `deferred-items.md`. |
| IN-04   | **Resolved** | `test_run_task_send_notification_takes_deterministic_path` now uses `AsyncMock` for `send_message`, removing reliance on quirky `asyncio.run` tolerance of `MagicMock`. |
| IN-05   | **Resolved** | `test_run_task_no_legacy_callback` split into `test_legacy_callbacks_module_deleted` + `test_run_task_does_not_pass_agent_logging_handler`. |

**Verification:** After each commit, `uv run pytest tests/unit/test_agent_middleware.py tests/unit/test_agent_runner.py tests/unit/test_llm_backend.py -x` stayed green (24 passed after the IN-05 split — was 23 before).

**Phase 12 manual smoke gate:** Unchanged. None of the applied fixes touch runtime behavior of agent invocation, middleware log emission, or the callbacks list passed to `agent.invoke`. They are docstring-only edits in `middleware.py` and test-only edits in `test_agent_runner.py`.
