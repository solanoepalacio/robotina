"""Tests for LLMBackend Protocol + adapter Strategy wrapping (Phase 11, RRECIPE-07 / RLOAD-07)."""
from __future__ import annotations

import inspect
from unittest.mock import patch, MagicMock

import pytest
from pydantic import BaseModel

from langchain.agents.structured_output import ToolStrategy, ProviderStrategy

from robotina.llm import LLMBackend, OllamaBackend, AnthropicBackend, OpenAIBackend


class ToyModel(BaseModel):
    x: int


@pytest.fixture
def ollama_config():
    return {"model": "test-model", "url": "http://localhost:11434"}


def test_llmbackend_protocol_has_response_format_param():
    sig = inspect.signature(LLMBackend.create_agent)
    assert "response_format" in sig.parameters
    assert sig.parameters["response_format"].default is None


def test_ollama_create_agent_omits_response_format_when_none(ollama_config):
    backend = OllamaBackend(ollama_config)
    with patch("robotina.llm._create_agent") as mock_create:
        backend.create_agent(system_prompt="x", tools=[])
    kwargs = mock_create.call_args.kwargs
    assert "response_format" not in kwargs


def test_ollama_create_agent_wraps_in_tool_strategy(ollama_config):
    backend = OllamaBackend(ollama_config)
    with patch("robotina.llm._create_agent") as mock_create:
        backend.create_agent(system_prompt="x", tools=[], response_format=ToyModel)
    kwargs = mock_create.call_args.kwargs
    assert isinstance(kwargs["response_format"], ToolStrategy)
    # _SchemaSpec.schema holds the original class
    assert kwargs["response_format"].schema_spec.schema is ToyModel


def test_anthropic_create_agent_wraps_in_provider_strategy(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_TEST_TOKEN", "test")
    with patch("langchain_anthropic.ChatAnthropic") as MockChat:
        MockChat.return_value = MagicMock()
        backend = AnthropicBackend({
            "model": "claude-test",
            "url": None,
            "api_key_env": "ANTHROPIC_TEST_TOKEN",
        })
        with patch("robotina.llm._create_agent") as mock_create:
            backend.create_agent(system_prompt="x", tools=[], response_format=ToyModel)
    kwargs = mock_create.call_args.kwargs
    assert isinstance(kwargs["response_format"], ProviderStrategy)
    assert kwargs["response_format"].schema_spec.schema is ToyModel


def test_openai_create_agent_wraps_in_provider_strategy(monkeypatch):
    monkeypatch.setenv("OPENAI_TEST_TOKEN", "test")
    with patch("langchain_openai.ChatOpenAI") as MockChat:
        MockChat.return_value = MagicMock()
        backend = OpenAIBackend({
            "model": "gpt-test",
            "url": None,
            "api_key_env": "OPENAI_TEST_TOKEN",
        })
        with patch("robotina.llm._create_agent") as mock_create:
            backend.create_agent(system_prompt="x", tools=[], response_format=ToyModel)
    kwargs = mock_create.call_args.kwargs
    assert isinstance(kwargs["response_format"], ProviderStrategy)
    assert kwargs["response_format"].schema_spec.schema is ToyModel
