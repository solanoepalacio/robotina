import os
from unittest.mock import MagicMock, patch

import pytest


def test_llm_backend_protocol_exists():
    """AGENT-01: LLMBackend Protocol has model property and create_agent() method."""
    from robotina.llm import LLMBackend

    assert hasattr(LLMBackend, "__protocol_attrs__")
    assert "model" in LLMBackend.__protocol_attrs__
    assert "create_agent" in LLMBackend.__protocol_attrs__


def test_ollama_adapter_creates_agent():
    """AGENT-02 / AGENT-12: OllamaBackend creates a langchain.agents.create_agent runnable."""
    from robotina.llm import LLMBackend, OllamaBackend

    mock_model = MagicMock()
    mock_agent = MagicMock()
    mock_agent.invoke = MagicMock()

    with patch("robotina.llm._create_agent", return_value=mock_agent) as mock_cra:
        with patch("langchain_ollama.ChatOllama", return_value=mock_model):
            adapter = OllamaBackend({"model": "test", "api_key_env": "HELLO_WORLD_API_TOKEN"})
            result = adapter.create_agent("hello")

    assert isinstance(adapter, LLMBackend)
    assert hasattr(result, "invoke")
    mock_cra.assert_called_once()


def test_anthropic_adapter_creates_agent(monkeypatch):
    """AGENT-02 / AGENT-12: AnthropicBackend creates a langchain.agents.create_agent runnable."""
    from robotina.llm import AnthropicBackend, LLMBackend

    monkeypatch.setenv("HELLO_WORLD_API_TOKEN", "test-api-key")

    mock_model = MagicMock()
    mock_agent = MagicMock()
    mock_agent.invoke = MagicMock()

    with patch("robotina.llm._create_agent", return_value=mock_agent) as mock_cra:
        with patch("langchain_anthropic.ChatAnthropic", return_value=mock_model):
            adapter = AnthropicBackend({
                "model": "claude-3-5-haiku",
                "api_key_env": "HELLO_WORLD_API_TOKEN",
            })
            result = adapter.create_agent("hello")

    assert isinstance(adapter, LLMBackend)
    assert hasattr(result, "invoke")
    mock_cra.assert_called_once()


def test_openai_adapter_creates_agent(monkeypatch):
    """AGENT-02 / AGENT-12: OpenAIBackend creates a langchain.agents.create_agent runnable."""
    from robotina.llm import LLMBackend, OpenAIBackend

    monkeypatch.setenv("HELLO_WORLD_API_TOKEN", "test-api-key")

    mock_model = MagicMock()
    mock_agent = MagicMock()
    mock_agent.invoke = MagicMock()

    with patch("robotina.llm._create_agent", return_value=mock_agent) as mock_cra:
        with patch("langchain_openai.ChatOpenAI", return_value=mock_model):
            adapter = OpenAIBackend({
                "model": "gpt-4",
                "model_name": "gpt-4",
                "api_key_env": "HELLO_WORLD_API_TOKEN",
            })
            result = adapter.create_agent("hello")

    assert isinstance(adapter, LLMBackend)
    assert hasattr(result, "invoke")
    mock_cra.assert_called_once()


def test_adapter_reads_api_token_from_env(monkeypatch):
    """AGENT-03/AGENT-04: Adapter reads token from env var named by api_key_env."""
    from robotina.llm import AnthropicBackend

    monkeypatch.setenv("MY_API_KEY", "test-token")

    mock_model = MagicMock()

    with patch("langchain_anthropic.ChatAnthropic", return_value=mock_model) as mock_chat:
        adapter = AnthropicBackend({
            "model": "claude-3-5-haiku",
            "api_key_env": "MY_API_KEY",
        })
        # Verify the token was read from env and passed to ChatAnthropic
        call_kwargs = mock_chat.call_args.kwargs
        assert call_kwargs.get("anthropic_api_key") == "test-token"

    # If env var unset, should raise KeyError
    monkeypatch.delenv("MY_API_KEY", raising=False)
    with pytest.raises(KeyError):
        AnthropicBackend({
            "model": "claude-3-5-haiku",
            "api_key_env": "MY_API_KEY",
        })


def test_create_agent_used_not_agent_executor():
    """AGENT-12: create_agent from langchain.agents is used, not AgentExecutor or the deprecated create_react_agent."""
    import robotina.llm as llm_module
    import inspect

    source_path = inspect.getfile(llm_module)
    with open(source_path) as f:
        source = f.read()

    assert "AgentExecutor" not in source, "AgentExecutor must not be used in robotina.llm"
    assert "from langchain.agents import create_agent" in source, (
        "robotina.llm must import create_agent from langchain.agents"
    )
    assert "create_react_agent" not in source, (
        "robotina.llm must not reference the deprecated create_react_agent"
    )
    assert "from langgraph.prebuilt" not in source, (
        "robotina.llm must not import from the deprecated langgraph.prebuilt module"
    )


# ---------------------------------------------------------------------------
# OBS-06 / Phase 12: middleware wiring
# Assert all three backend.create_agent methods pass middleware=[
#     log_around_model_call, log_after_model, log_wrap_tool_call
# ] to _create_agent. Coexists with AgentLoggingHandler in jobs.py (Plan 12-02
# removes that legacy path atomically in Wave 2).
# ---------------------------------------------------------------------------


def test_ollama_create_agent_passes_middleware_to_factory():
    """OBS-06: OllamaBackend.create_agent installs the middleware list."""
    from robotina.llm import OllamaBackend
    from robotina.agent.middleware import (
        log_around_model_call,
        log_after_model,
        log_wrap_tool_call,
    )

    mock_agent = MagicMock()
    mock_agent.invoke = MagicMock()

    with patch("robotina.llm._create_agent", return_value=mock_agent) as mock_cra:
        with patch("langchain_ollama.ChatOllama", return_value=MagicMock()):
            adapter = OllamaBackend({"model": "test", "api_key_env": "HELLO_WORLD_API_TOKEN"})
            adapter.create_agent("hello")

    call_kwargs = mock_cra.call_args.kwargs
    assert "middleware" in call_kwargs, (
        f"Expected 'middleware' kwarg on _create_agent. Got: {list(call_kwargs)}"
    )
    middleware_list = call_kwargs["middleware"]
    assert middleware_list[0] is log_around_model_call
    assert middleware_list[1] is log_after_model
    assert middleware_list[2] is log_wrap_tool_call
    assert len(middleware_list) == 3


def test_anthropic_create_agent_passes_middleware_to_factory(monkeypatch):
    """OBS-06: AnthropicBackend.create_agent installs the middleware list."""
    from robotina.llm import AnthropicBackend
    from robotina.agent.middleware import (
        log_around_model_call,
        log_after_model,
        log_wrap_tool_call,
    )

    monkeypatch.setenv("HELLO_WORLD_API_TOKEN", "test-api-key")

    mock_agent = MagicMock()
    mock_agent.invoke = MagicMock()

    with patch("robotina.llm._create_agent", return_value=mock_agent) as mock_cra:
        with patch("langchain_anthropic.ChatAnthropic", return_value=MagicMock()):
            adapter = AnthropicBackend({
                "model": "claude-3-5-haiku",
                "api_key_env": "HELLO_WORLD_API_TOKEN",
            })
            adapter.create_agent("hello")

    call_kwargs = mock_cra.call_args.kwargs
    assert "middleware" in call_kwargs, (
        f"Expected 'middleware' kwarg on _create_agent. Got: {list(call_kwargs)}"
    )
    middleware_list = call_kwargs["middleware"]
    assert middleware_list[0] is log_around_model_call
    assert middleware_list[1] is log_after_model
    assert middleware_list[2] is log_wrap_tool_call
    assert len(middleware_list) == 3


def test_openai_create_agent_passes_middleware_to_factory(monkeypatch):
    """OBS-06: OpenAIBackend.create_agent installs the middleware list."""
    from robotina.llm import OpenAIBackend
    from robotina.agent.middleware import (
        log_around_model_call,
        log_after_model,
        log_wrap_tool_call,
    )

    monkeypatch.setenv("HELLO_WORLD_API_TOKEN", "test-api-key")

    mock_agent = MagicMock()
    mock_agent.invoke = MagicMock()

    with patch("robotina.llm._create_agent", return_value=mock_agent) as mock_cra:
        with patch("langchain_openai.ChatOpenAI", return_value=MagicMock()):
            adapter = OpenAIBackend({
                "model": "gpt-4",
                "model_name": "gpt-4",
                "api_key_env": "HELLO_WORLD_API_TOKEN",
            })
            adapter.create_agent("hello")

    call_kwargs = mock_cra.call_args.kwargs
    assert "middleware" in call_kwargs, (
        f"Expected 'middleware' kwarg on _create_agent. Got: {list(call_kwargs)}"
    )
    middleware_list = call_kwargs["middleware"]
    assert middleware_list[0] is log_around_model_call
    assert middleware_list[1] is log_after_model
    assert middleware_list[2] is log_wrap_tool_call
    assert len(middleware_list) == 3
