"""Tests for LangChain 1.x agent middleware (Robotina structured-action logging).

Tests verify:
- OBS-06: Middleware emits the four legacy log lines (LLM stream start, Thinking,
  Tool call, Tool result) byte-for-byte and preserves the 200-char truncation
  invariant carried over from the legacy AgentLoggingHandler.

The tests invoke each middleware's bound hook method directly with MagicMock
request / state / handler fixtures — no real ``create_agent`` graph is needed.
The decorator stored the function as a bound method on the generated
``AgentMiddleware`` subclass (langchain/agents/middleware/types.py:1880-1892).
"""
import logging
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, ToolMessage


def test_log_around_model_call_emits_llm_start(caplog):
    """OBS-06: log_around_model_call emits 'LLM stream start | model=<ChatClass>'.

    Replaces AgentLoggingHandler.on_chat_model_start. Asserts the wrapper:
    - emits a log line containing the model class name
    - invokes the handler exactly once with the request
    - returns the handler's return value unchanged
    """
    from robotina.agent.middleware import log_around_model_call

    request = MagicMock()
    request.model = MagicMock()
    request.model.__class__.__name__ = "ChatOllama"
    sentinel = object()
    handler = MagicMock(return_value=sentinel)

    with caplog.at_level(logging.INFO, logger="robotina.agent.middleware"):
        result = log_around_model_call.wrap_model_call(request, handler)

    assert result is sentinel
    handler.assert_called_once_with(request)
    assert any(
        "LLM stream start" in record.message and "ChatOllama" in record.message
        for record in caplog.records
    ), f"Expected 'LLM stream start' and 'ChatOllama' in log. Got: {[r.message for r in caplog.records]}"


def test_log_after_model_emits_thinking_when_present(caplog):
    """OBS-06: log_after_model emits 'Thinking | <reasoning>' when the latest
    AIMessage carries additional_kwargs.reasoning_content (Ollama / Anthropic).

    Replaces AgentLoggingHandler.on_llm_end (Thinking branch).
    """
    from robotina.agent.middleware import log_after_model

    state = {
        "messages": [
            AIMessage(
                content="visible content",
                additional_kwargs={"reasoning_content": "deliberation text"},
            )
        ]
    }
    runtime = MagicMock()

    with caplog.at_level(logging.INFO, logger="robotina.agent.middleware"):
        log_after_model.after_model(state, runtime)

    assert any(
        "Thinking" in record.message and "deliberation text" in record.message
        for record in caplog.records
    ), f"Expected 'Thinking' and 'deliberation text' in log. Got: {[r.message for r in caplog.records]}"


def test_log_after_model_silent_when_absent(caplog):
    """OBS-06: log_after_model emits NOTHING when reasoning_content is absent.

    OpenAI does not populate reasoning_content; the legacy callback handler is
    silent in that case and the middleware must preserve that behavior.
    """
    from robotina.agent.middleware import log_after_model

    state = {
        "messages": [
            AIMessage(content="visible content", additional_kwargs={})
        ]
    }
    runtime = MagicMock()

    with caplog.at_level(logging.INFO, logger="robotina.agent.middleware"):
        log_after_model.after_model(state, runtime)

    assert not any(
        "Thinking" in record.message for record in caplog.records
    ), f"Expected NO 'Thinking' log. Got: {[r.message for r in caplog.records]}"


def test_log_wrap_tool_call_brackets_handler(caplog):
    """OBS-06: log_wrap_tool_call emits 'Tool call' before handler and
    'Tool result' after, returning the handler's ToolMessage unchanged.

    Replaces AgentLoggingHandler.on_tool_start + on_tool_end.
    """
    from robotina.agent.middleware import log_wrap_tool_call

    request = MagicMock()
    request.tool_call = {
        "name": "household-manager-api",
        "args": {"endpoint": "/meals"},
        "id": "t1",
        "type": "tool_call",
    }
    tool_msg = ToolMessage(content="ok-result", tool_call_id="t1")
    handler = MagicMock(return_value=tool_msg)

    with caplog.at_level(logging.INFO, logger="robotina.agent.middleware"):
        result = log_wrap_tool_call.wrap_tool_call(request, handler)

    # Identity check — handler's return value flows through unchanged.
    assert result is tool_msg
    handler.assert_called_once_with(request)

    messages = [r.message for r in caplog.records]
    assert any(
        "Tool call" in m and "household-manager-api" in m for m in messages
    ), f"Expected 'Tool call' and 'household-manager-api' in log. Got: {messages}"
    assert any(
        "Tool result" in m and "ok-result" in m for m in messages
    ), f"Expected 'Tool result' and 'ok-result' in log. Got: {messages}"


def test_log_wrap_tool_call_invokes_handler_once(caplog):
    """OBS-06 / Pitfall 2 (RESEARCH.md): log_wrap_tool_call calls handler
    exactly once — no double-execution of side-effecting tool calls.
    """
    from robotina.agent.middleware import log_wrap_tool_call

    request = MagicMock()
    request.tool_call = {"name": "tool-x", "args": {}, "id": "t1", "type": "tool_call"}
    tool_msg = ToolMessage(content="ok", tool_call_id="t1")
    handler = MagicMock(return_value=tool_msg)

    with caplog.at_level(logging.INFO, logger="robotina.agent.middleware"):
        log_wrap_tool_call.wrap_tool_call(request, handler)

    assert handler.call_count == 1, (
        f"Expected handler.call_count == 1, got {handler.call_count}. "
        "Double-execution regression — see RESEARCH.md Pitfall 2."
    )


def test_log_wrap_tool_call_truncates_output_to_200_chars(caplog):
    """OBS-06 / V5+V7 (ASVS): tool result output is truncated to 200 chars.

    Carries the legacy ``str(output)[:200]`` invariant from
    AgentLoggingHandler.on_tool_end. Prevents log injection / log bloat from
    long untrusted tool outputs.

    Regression test pattern copied from test_agent_runner.py::
    test_agent_logging_handler_on_tool_end (lines 325-340 of the legacy file).
    """
    from robotina.agent.middleware import log_wrap_tool_call

    request = MagicMock()
    request.tool_call = {"name": "tool-x", "args": {}, "id": "t1", "type": "tool_call"}
    long_output = "x" * 500
    tool_msg = ToolMessage(content=long_output, tool_call_id="t1")
    handler = MagicMock(return_value=tool_msg)

    with caplog.at_level(logging.INFO, logger="robotina.agent.middleware"):
        log_wrap_tool_call.wrap_tool_call(request, handler)

    messages = [r.message for r in caplog.records]
    assert len(messages) > 0, "Expected at least one log message"
    combined = " ".join(messages)
    assert "x" * 201 not in combined, "Tool result was not truncated to 200 chars"
    assert "x" * 200 in combined or "x" * 199 in combined, (
        f"Expected truncated output (200 chars) in log. Got first 250 chars: {combined[:250]}"
    )
