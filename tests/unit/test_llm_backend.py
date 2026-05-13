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
    """AGENT-02: OllamaBackend creates a create_react_agent runnable."""
    from robotina.llm import LLMBackend, OllamaBackend

    mock_model = MagicMock()
    mock_agent = MagicMock()
    mock_agent.invoke = MagicMock()

    with patch("robotina.llm.create_react_agent", return_value=mock_agent) as mock_cra:
        with patch("langchain_ollama.ChatOllama", return_value=mock_model):
            adapter = OllamaBackend({"model": "test", "api_key_env": "HELLO_WORLD_API_TOKEN"})
            result = adapter.create_agent("hello")

    assert isinstance(adapter, LLMBackend)
    assert hasattr(result, "invoke")
    mock_cra.assert_called_once()


def test_anthropic_adapter_creates_agent(monkeypatch):
    """AGENT-02: AnthropicBackend creates a create_react_agent runnable."""
    from robotina.llm import AnthropicBackend, LLMBackend

    monkeypatch.setenv("HELLO_WORLD_API_TOKEN", "test-api-key")

    mock_model = MagicMock()
    mock_agent = MagicMock()
    mock_agent.invoke = MagicMock()

    with patch("robotina.llm.create_react_agent", return_value=mock_agent) as mock_cra:
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
    """AGENT-02: OpenAIBackend creates a create_react_agent runnable."""
    from robotina.llm import LLMBackend, OpenAIBackend

    monkeypatch.setenv("HELLO_WORLD_API_TOKEN", "test-api-key")

    mock_model = MagicMock()
    mock_agent = MagicMock()
    mock_agent.invoke = MagicMock()

    with patch("robotina.llm.create_react_agent", return_value=mock_agent) as mock_cra:
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
