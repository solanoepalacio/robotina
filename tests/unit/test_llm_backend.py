import pytest


def test_llm_backend_protocol_exists():
    """AGENT-01: LLMBackend Protocol has model property and create_agent() method."""
    pytest.skip("not implemented")


def test_ollama_adapter_creates_agent():
    """AGENT-02: OllamaBackend creates a create_react_agent runnable."""
    pytest.skip("not implemented")


def test_anthropic_adapter_creates_agent():
    """AGENT-02: AnthropicBackend creates a create_react_agent runnable."""
    pytest.skip("not implemented")


def test_openai_adapter_creates_agent():
    """AGENT-02: OpenAIBackend creates a create_react_agent runnable."""
    pytest.skip("not implemented")


def test_adapter_reads_api_token_from_env():
    """AGENT-03/AGENT-04: Adapter reads token from env var named by api_key_env."""
    pytest.skip("not implemented")


def test_create_react_agent_used_not_agent_executor():
    """AGENT-11: create_react_agent from langgraph.prebuilt is used, not AgentExecutor."""
    pytest.skip("not implemented")
