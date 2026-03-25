"""LLM provider abstraction for Robotina agents.

LLMBackend Protocol + three adapters (Ollama, Anthropic, OpenAI).

IMPORTANT: All adapter instances MUST be created inside job functions (run_task),
never at module level. This is a locked architectural constraint from STATE.md.

API token strategy: model_config stores the env var NAME (api_key_env), not the
token value. The adapter reads os.environ[config["api_key_env"]] at instantiation
time. This means missing tokens produce a KeyError at job execution time, not at
import time — which is the desired behavior for per-task-type configuration.
"""
from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent  # locked per AGENT-11/D-03


@runtime_checkable
class LLMBackend(Protocol):
    """Interface for LLM adapters. Each agent run holds its own backend instance.

    Per STATE.md: all adapter instances are created inside the job function (run_task),
    never at module level or as class-level singletons.
    """

    @property
    def model(self) -> BaseChatModel:
        """The underlying LangChain chat model."""
        ...

    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
    ) -> Any:
        """Return a runnable LangGraph ReAct agent bound to this model.

        Uses create_react_agent from langgraph.prebuilt (locked per AGENT-11/D-03).
        Note: langgraph 1.1.3 emits LangGraphDeprecatedSinceV10 — this is expected
        and the API remains fully functional through at least LangGraph v1.x.
        """
        ...


class OllamaBackend:
    """LLMBackend adapter for local Ollama models.

    Ollama is unauthenticated — no api_key field. The api_key_env field in
    model_config is accepted but ignored for Ollama.
    """

    def __init__(self, config: dict) -> None:
        from langchain_ollama import ChatOllama

        self._model = ChatOllama(
            model=config["model"],
            base_url=config.get("url"),  # None = default http://localhost:11434
        )

    @property
    def model(self) -> BaseChatModel:
        return self._model

    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
    ) -> Any:
        return create_react_agent(
            model=self._model,
            tools=tools or [],
            prompt=system_prompt,
        )


class AnthropicBackend:
    """LLMBackend adapter for Anthropic Claude models.

    Reads API token from os.environ[config["api_key_env"]] at instantiation.
    Raises KeyError if the env var is not set (hard error — misconfiguration).
    """

    def __init__(self, config: dict) -> None:
        from langchain_anthropic import ChatAnthropic

        api_key = os.environ[config["api_key_env"]]
        self._model = ChatAnthropic(
            model=config["model"],
            anthropic_api_url=config.get("url"),
            anthropic_api_key=api_key,
        )

    @property
    def model(self) -> BaseChatModel:
        return self._model

    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
    ) -> Any:
        return create_react_agent(
            model=self._model,
            tools=tools or [],
            prompt=system_prompt,
        )


class OpenAIBackend:
    """LLMBackend adapter for OpenAI-compatible endpoints (GPT-4, self-hosted, etc.).

    Uses model_name (not model) and openai_api_base (not base_url) — these are the
    verified field names for langchain-openai 1.1.12. See RESEARCH.md Pattern 2.
    """

    def __init__(self, config: dict) -> None:
        from langchain_openai import ChatOpenAI

        api_key = os.environ[config["api_key_env"]]
        self._model = ChatOpenAI(
            model_name=config["model"],        # NOTE: model_name not model
            openai_api_base=config.get("url"),
            openai_api_key=api_key,
        )

    @property
    def model(self) -> BaseChatModel:
        return self._model

    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
    ) -> Any:
        return create_react_agent(
            model=self._model,
            tools=tools or [],
            prompt=system_prompt,
        )


def make_backend(model_config: dict) -> LLMBackend:
    """Factory: instantiate the correct adapter based on model_config['provider'].

    This is the single dispatch point. run_task() calls this to get a backend.
    Supported providers: 'ollama', 'anthropic', 'openai'.
    """
    provider = model_config.get("provider", "")
    if provider == "ollama":
        return OllamaBackend(model_config)
    elif provider == "anthropic":
        return AnthropicBackend(model_config)
    elif provider == "openai":
        return OpenAIBackend(model_config)
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider!r}. Must be 'ollama', 'anthropic', or 'openai'."
        )
