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

import asyncio
import logging
import os
import random
import time
from typing import Any, Protocol, runtime_checkable

import httpx
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama
from langchain.agents import create_agent as _create_agent  # AGENT-12
from ollama import ResponseError as OllamaResponseError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# --- OllamaBackend transient-retry config (hard-coded; no env vars per BRIEF) ---

_OLLAMA_RETRY_MAX_ATTEMPTS = 3            # 1 initial + 2 retries
_OLLAMA_RETRY_BASE_DELAY = 0.5            # seconds
_OLLAMA_RETRY_BACKOFF_FACTOR = 2.0
_OLLAMA_RETRY_JITTER = 0.25               # ±25%
_OLLAMA_RETRY_5XX_STATUSES = frozenset({500, 502, 503, 504})
_OLLAMA_RETRY_TRANSIENT_HTTPX = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
)


def _is_transient_ollama_error(exc: BaseException) -> bool:
    """True iff `exc` is a retryable Ollama transient error.

    Retryable:
      - ollama.ResponseError with status_code in {500, 502, 503, 504}
      - httpx.ConnectError / httpx.ReadTimeout / httpx.ConnectTimeout

    Not retryable (returns False):
      - 4xx ResponseError (auth, bad request, etc.)
      - ResponseError with status_code == -1 (unknown — fail fast)
      - any other exception
    """
    if isinstance(exc, OllamaResponseError):
        return exc.status_code in _OLLAMA_RETRY_5XX_STATUSES
    if isinstance(exc, _OLLAMA_RETRY_TRANSIENT_HTTPX):
        return True
    return False


def _compute_backoff(attempt_index: int) -> float:
    """Backoff delay in seconds for the (attempt_index)-th retry (0-indexed).

    attempt_index=0 → ~0.5s ±25% (i.e. [0.375, 0.625])
    attempt_index=1 → ~1.0s ±25% (i.e. [0.75, 1.25])
    """
    delay = _OLLAMA_RETRY_BASE_DELAY * (_OLLAMA_RETRY_BACKOFF_FACTOR ** attempt_index)
    jitter_ratio = random.uniform(-_OLLAMA_RETRY_JITTER, _OLLAMA_RETRY_JITTER)
    return max(0.0, delay * (1 + jitter_ratio))


class _RetryingChatOllama(ChatOllama):
    """ChatOllama with bounded retry on Ollama 5xx and transient httpx errors.

    Status-code-aware: 4xx errors (auth, etc.) propagate without retry. 5xx
    (including the 'error parsing tool call' 500 that Ollama returns when the
    model emits malformed tool-call JSON) and httpx connect/read timeouts are
    retried up to 3 attempts total with exponential backoff + ±25% jitter. On
    exhaustion the original exception is re-raised so the existing FAILED-step
    path in robotina/queue/jobs.py still works.

    Why a subclass and not Runnable.with_retry(): with_retry filters by
    exception type only, so it would also retry 4xx — undesirable. And the
    result of with_retry is a RunnableRetry wrapper, which
    ``langchain.agents.create_agent`` does not accept (it requires
    BaseChatModel | RunnableBinding).
    """

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_exc: BaseException | None = None
        for attempt in range(_OLLAMA_RETRY_MAX_ATTEMPTS):
            try:
                return super()._generate(
                    messages, stop=stop, run_manager=run_manager, **kwargs
                )
            except Exception as exc:
                last_exc = exc
                if not _is_transient_ollama_error(exc):
                    raise
                if attempt + 1 >= _OLLAMA_RETRY_MAX_ATTEMPTS:
                    raise
                delay = _compute_backoff(attempt)
                logger.warning(
                    "Ollama transient error, retrying (attempt %d/%d): %s",
                    attempt + 2,
                    _OLLAMA_RETRY_MAX_ATTEMPTS,
                    exc,
                )
                time.sleep(delay)
        # Defensive: loop only exits via return or raise.
        assert last_exc is not None
        raise last_exc

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_exc: BaseException | None = None
        for attempt in range(_OLLAMA_RETRY_MAX_ATTEMPTS):
            try:
                return await super()._agenerate(
                    messages, stop=stop, run_manager=run_manager, **kwargs
                )
            except Exception as exc:
                last_exc = exc
                if not _is_transient_ollama_error(exc):
                    raise
                if attempt + 1 >= _OLLAMA_RETRY_MAX_ATTEMPTS:
                    raise
                delay = _compute_backoff(attempt)
                logger.warning(
                    "Ollama transient error, retrying (attempt %d/%d): %s",
                    attempt + 2,
                    _OLLAMA_RETRY_MAX_ATTEMPTS,
                    exc,
                )
                await asyncio.sleep(delay)
        # Defensive: loop only exits via return or raise.
        assert last_exc is not None
        raise last_exc


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
        response_format: type[BaseModel] | None = None,
    ) -> Any:
        """Return a runnable agent graph bound to this model.

        Uses ``langchain.agents.create_agent`` (the LangChain 1.x agent factory;
        AGENT-12 supersedes AGENT-11/D-03). The factory returns a
        ``CompiledStateGraph`` whose ``.invoke({"messages": [...]})`` contract is
        unchanged from the previous prebuilt ReAct-agent path — including
        ``return_direct=True`` short-circuit semantics, strict-args validation
        producing ``ToolMessage(status='error')``, and callback delivery via
        ``RunnableConfig(callbacks=[...])``. Verified empirically against
        ``langchain 1.2.13``.

        When ``response_format`` is provided, the adapter wraps it in the
        provider-appropriate strategy:
          - Ollama   → ToolStrategy (synthesized emit tool)
          - Anthropic / OpenAI → ProviderStrategy (native strict-schema)
        The agent's invoke result will populate ``state['structured_response']``
        with a Pydantic instance of ``response_format``. See Phase 11
        RESEARCH.md "Pattern 1" / "Pattern 2" for full citations.
        """
        ...


class OllamaBackend:
    """LLMBackend adapter for local Ollama models.

    Ollama is unauthenticated — no api_key field. The api_key_env field in
    model_config is accepted but ignored for Ollama.

    Wraps ChatOllama in a `_RetryingChatOllama` to survive Ollama 5xx
    tool-call-parse errors and transient httpx connect/read timeouts.
    """

    def __init__(self, config: dict) -> None:
        self._model = _RetryingChatOllama(
            model=config["model"],
            base_url=config.get("url"),  # None = default http://localhost:11434
            reasoning=config.get("reasoning"),  # None = model default; True = separate think content from response
        )

    @property
    def model(self) -> BaseChatModel:
        return self._model

    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
        response_format: type[BaseModel] | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "tools": tools or [],
            "system_prompt": system_prompt,
        }
        if response_format is not None:
            # Explicit ToolStrategy: ChatOllama has no profile, but "gpt-oss"
            # is in FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT
            # (langchain/agents/factory.py:148-158), so AutoStrategy would
            # resolve to ProviderStrategy and call bind_tools(strict=True,
            # response_format=...) which Ollama does not honor.
            # See Phase 11 RESEARCH.md, Pitfall 1.
            from langchain.agents.structured_output import ToolStrategy
            kwargs["response_format"] = ToolStrategy(response_format)
        return _create_agent(**kwargs)


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
        response_format: type[BaseModel] | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "tools": tools or [],
            "system_prompt": system_prompt,
        }
        if response_format is not None:
            from langchain.agents.structured_output import ProviderStrategy
            kwargs["response_format"] = ProviderStrategy(response_format)
        return _create_agent(**kwargs)


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
        response_format: type[BaseModel] | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "tools": tools or [],
            "system_prompt": system_prompt,
        }
        if response_format is not None:
            from langchain.agents.structured_output import ProviderStrategy
            kwargs["response_format"] = ProviderStrategy(response_format)
        return _create_agent(**kwargs)


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
