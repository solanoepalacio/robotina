"""LangChain agent middleware for Robotina structured-action logging.

Phase 12 (OBS-06) replacement for the legacy
``robotina.agent.callbacks.AgentLoggingHandler``. LangWatch tracing remains
on the LangChain callback bus (``langwatch.langchain.LangChainTracer`` in
``robotina.queue.jobs``) — only the per-agent log lines move to middleware.

Three module-level ``AgentMiddleware`` singletons are exposed:
  - ``log_around_model_call``: emits ``LLM stream start | model=<ChatClassName>``
    via the ``robotina.agent.middleware`` logger before invoking the handler.
  - ``log_after_model``: emits ``Thinking | <reasoning_content>`` iff the latest
    AIMessage in state carries ``additional_kwargs.reasoning_content`` (Ollama /
    Anthropic populate this; OpenAI does not — same behavior as the legacy
    callback, no regression).
  - ``log_wrap_tool_call``: emits ``Tool call | tool=<name> input=<args>`` before
    handler() and ``Tool result | output=<content>`` after, with both input and
    output truncated to 200 chars (preserves the V5/V7 ASVS log-injection /
    log-bloat boundary carried from the legacy callback).

The handler is invoked EXACTLY ONCE per ``wrap_tool_call`` invocation — no
double-execution of side-effecting tool calls (RESEARCH.md Pitfall 2).

Stateless-module rule: this module's import must have no side effects beyond
constructing the three ``AgentMiddleware`` singletons (no I/O, no network, no
env reads). The singletons are shared across all jobs in the process — they
MUST hold no per-job state and MUST NOT close over per-job context
(RESEARCH.md Pitfall 4).

CONSTRAINT — sync-only invocation path:
    The decorators below (``@wrap_model_call``, ``@after_model``,
    ``@wrap_tool_call``) generate ``AgentMiddleware`` subclasses that populate
    ONLY the sync hooks. The async counterparts (``awrap_model_call``,
    ``awrap_tool_call``, ``aafter_model``) inherit the base-class
    implementation, which raises ``NotImplementedError``. Robotina's task
    runner invokes agents synchronously today (``agent.invoke(...)`` in
    ``robotina.queue.jobs``); a future caller that switches to
    ``agent.ainvoke()`` / ``agent.astream()`` will hit ``NotImplementedError``
    at the first tool or model call. Revisit by adding async parity decorators
    (mirroring the sync logic) if async invocation is introduced.
"""
from __future__ import annotations

import logging
from typing import Callable

from langchain.agents.middleware import (  # AGENT-13 / Phase 12
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
    """Log ``LLM stream start | model=<ChatClassName>`` before each model call.

    Replaces ``AgentLoggingHandler.on_chat_model_start``. The class name comes
    from ``type(request.model).__name__`` — ``request.model`` is the underlying
    ``BaseChatModel`` instance configured for this run. In practice that's
    ``_RetryingChatOllama`` for the Ollama backend (a local retry subclass —
    see ``robotina.llm._RetryingChatOllama``), ``ChatAnthropic`` for Anthropic,
    and ``ChatOpenAI`` for OpenAI. The log line therefore carries the actual
    runtime class name, not a normalized provider label — parity with the
    legacy callback (which used ``serialized.get("name")``).
    """
    model_name = type(request.model).__name__
    logger.info("LLM stream start | model=%s", model_name)
    return handler(request)


@after_model
def log_after_model(state: AgentState, runtime: Runtime) -> None:
    """Log ``Thinking | <reasoning>`` when the latest AI message carries
    ``additional_kwargs.reasoning_content``.

    Replaces the Thinking branch of ``AgentLoggingHandler.on_llm_end``. Silent
    when the key is absent — matches legacy behavior (OpenAI never populates
    reasoning_content, so no Thinking line is emitted for OpenAI runs; no
    regression).
    """
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
    """Log ``Tool call | tool=... input=...`` then ``Tool result | output=...``.

    Replaces ``AgentLoggingHandler.on_tool_start`` + ``on_tool_end``. Both
    input and output are truncated to 200 chars — preserves the V5/V7 security
    invariant from the legacy callback (see RESEARCH.md §"Security Domain").
    The handler is invoked EXACTLY ONCE (RESEARCH.md Pitfall 2 — no double
    execution of side-effecting tool calls).
    """
    name = request.tool_call.get("name")
    args = request.tool_call.get("args", {})
    logger.info("Tool call | tool=%s input=%s", name, str(args)[:200])

    result = handler(request)

    if isinstance(result, ToolMessage):
        logger.info("Tool result | output=%s", str(result.content)[:200])
    else:
        # Command path — Command has no primary output string. Rare in current
        # Robotina tools; matches the parity surface of the legacy handler.
        logger.info("Tool result | output=<Command>")
    return result
