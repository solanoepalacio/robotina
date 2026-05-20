"""Agent registry for Robotina.

AgentConfig dataclass + AGENT_REGISTRY dict + get_agent_config() with hot-reload
override via AGENT_OVERRIDES_FILEPATH env var.

Registry contains all active agent configurations. The 'send-notification' entry was
added in Phase 6; 'hello-world' placeholder was removed.

API token strategy (D-07): model_config stores the env var NAME (api_key_env field),
not the resolved token. The LLM adapter reads os.environ[api_key_env] at job
execution time. Never store token values in this registry.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from pydantic import BaseModel

from robotina.agent.tools._catalog_match import SemanticMatchResult
from robotina.queue.task_types import (
    RecipeData,
    RecipeLoadOutput,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Per-task-type agent configuration.

    Fields:
        task_type: Unique identifier matching the RQ job meta['task_type'] value.
        model_config: LLM provider config dict with keys:
            - provider: 'ollama' | 'anthropic' | 'openai'
            - url: provider base URL (optional for some providers)
            - model: model name/identifier
            - api_key_env: name of the env var holding the API token
        prompt_path: Relative path to the versioned system prompt markdown file.
        skills: List of skill directory names under src/robotina/agent/skills/.
        tools: List of pre-built LangChain BaseTool instances. Empty in Phase 4;
               tools are added in the phase that implements each tool.
        response_format_model: Optional Pydantic v2 BaseModel subclass to bind as
               ``response_format=`` on ``langchain.agents.create_agent``. When set,
               the LLM adapter wraps this in the provider-appropriate Strategy
               (ToolStrategy for Ollama, ProviderStrategy for Anthropic/OpenAI)
               and the agent's result populates state['structured_response'] with
               a Pydantic instance. NOT overridable via AGENT_OVERRIDES_FILEPATH
               — schema is a code contract, not config (Phase 11 RESEARCH.md
               Anti-Patterns). Default None means the agent emits free-text /
               tool-message artifacts and the workflow runner uses the
               return_direct branch in _extract_task_output.
    """

    task_type: str
    model_config: dict  # {provider, url, model, api_key_env}
    prompt_path: str
    skills: list[str] = field(default_factory=list)
    tools: list = field(default_factory=list)
    response_format_model: type[BaseModel] | None = None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

AGENT_REGISTRY: dict[str, AgentConfig] = {
    # Phase 07.1: send-notification is no longer an LLM agent. It runs as a
    # deterministic Python path inside run_task() (jobs.py). Removed from registry
    # to ensure get_agent_config("send-notification") raises KeyError if anything
    # accidentally tries to take the agent path.
    "handle-incoming-message": AgentConfig(
        task_type="handle-incoming-message",
        model_config={
            "provider": "ollama",
            "url": "http://localhost:11434",
            "model": "gpt-oss:20b",
            "api_key_env": "HANDLE_INCOMING_MESSAGE_API_TOKEN",
            "reasoning": True,
        },
        prompt_path="src/robotina/agent/prompts/robotina/V006.md",
        skills=["household-manager"],
        tools=[],  # HouseholdManagerApiTool, RespondTool, TerminateTool, StartWorkflowTool injected per-job in run_task() — per Phase 21 D-01/D-02/D-10
    ),
    "recipe-research-gather": AgentConfig(
        task_type="recipe-research-gather",
        model_config={
            "provider": "ollama",
            "url": "http://localhost:11434",
            "model": "gpt-oss:20b",
            "api_key_env": "RECIPE_RESEARCH_GATHER_API_TOKEN",
            "reasoning": True,
        },
        prompt_path="src/robotina/agent/prompts/recipe-research-gather/V005.md",
        skills=[],
        tools=[],  # WebSearchTool injected per-job in run_task()
        response_format_model=RecipeData,
    ),
    # Phase 23 D-03 / D-23: gather-from-url is the first step of the
    # add-recipe-from-url workflow variant. response_format=RecipeData
    # mirrors recipe-research-gather; FetchAndScrapeTool is injected
    # per-job in run_task() (see queue/jobs.py). Atomic AGENT_REGISTRY +
    # overrides/*.json sync per feedback_overrides_in_sync (Phase 21 D-12).
    "gather-from-url": AgentConfig(
        task_type="gather-from-url",
        model_config={
            "provider": "ollama",
            "url": "http://localhost:11434",
            "model": "gpt-oss:20b",
            "api_key_env": "GATHER_FROM_URL_API_TOKEN",
            "reasoning": True,
        },
        prompt_path="src/robotina/agent/prompts/gather-from-url/V001.md",
        skills=[],
        tools=[],  # FetchAndScrapeTool injected per-job in run_task()
        response_format_model=RecipeData,
    ),
    "recipe-research-instructions": AgentConfig(
        task_type="recipe-research-instructions",
        model_config={
            "provider": "ollama",
            "url": "http://localhost:11434",
            "model": "gpt-oss:20b",
            "api_key_env": "RECIPE_RESEARCH_INSTRUCTIONS_API_TOKEN",
            "reasoning": True,
        },
        prompt_path="src/robotina/agent/prompts/recipe-research-instructions/V004.md",
        skills=[],
        tools=[],  # no tools — produces structured output directly from user message
        response_format_model=RecipeData,
    ),
    "recipe-research-ingredients": AgentConfig(
        task_type="recipe-research-ingredients",
        model_config={
            "provider": "ollama",
            "url": "http://localhost:11434",
            "model": "gpt-oss:20b",
            "api_key_env": "RECIPE_RESEARCH_INGREDIENTS_API_TOKEN",
            "reasoning": True,
        },
        prompt_path="src/robotina/agent/prompts/recipe-research-ingredients/V004.md",
        skills=[],
        tools=[],  # HouseholdManagerApiTool + ValidateFoodsTool + ValidateUnitsTool injected per-job in run_task()
        response_format_model=RecipeData,
    ),
    "recipe-research-metadata": AgentConfig(
        task_type="recipe-research-metadata",
        model_config={
            "provider": "ollama",
            "url": "http://localhost:11434",
            "model": "gpt-oss:20b",
            "api_key_env": "RECIPE_RESEARCH_METADATA_API_TOKEN",
            "reasoning": True,
        },
        prompt_path="src/robotina/agent/prompts/recipe-research-metadata/V004.md",
        skills=[],
        tools=[],  # no tools — produces structured output directly from user message
        response_format_model=RecipeData,
    ),
    "recipe-load": AgentConfig(
        task_type="recipe-load",
        model_config={
            "provider": "ollama",
            "url": "http://localhost:11434",
            "model": "gpt-oss:20b",
            "api_key_env": "RECIPE_LOAD_API_TOKEN",
            "reasoning": True,
        },
        prompt_path="src/robotina/agent/prompts/recipe-load/V005.md",
        skills=["household-manager"],
        tools=[],  # HouseholdManagerApiTool + ValidateFoodsTool + ValidateUnitsTool injected per-job in run_task()
        response_format_model=RecipeLoadOutput,
    ),
    # Phase 15: matcher LLM for validate-foods / validate-units tools. Not a
    # workflow task type — invoked synchronously from inside a tool call
    # (see robotina.agent.tools._catalog_match.resolve_catalog). Registered
    # here so it picks up AGENT_OVERRIDES_FILEPATH hot-reload like every other
    # LLM call site.
    "validate-catalog": AgentConfig(
        task_type="validate-catalog",
        model_config={
            "provider": "ollama",
            "url": "http://localhost:11434",
            "model": "gpt-oss:20b",
            "api_key_env": "VALIDATE_CATALOG_API_TOKEN",
            "reasoning": False,
        },
        prompt_path="src/robotina/agent/prompts/validate-catalog/V001.md",
        skills=[],
        tools=[],
        response_format_model=SemanticMatchResult,
    ),
}


def get_agent_config(task_type: str) -> AgentConfig:
    """Look up AgentConfig for a task type, applying runtime overrides.

    Override behavior (D-05):
    - If AGENT_OVERRIDES_FILEPATH env var is set, the JSON file at that path is
      loaded on EVERY call (hot-reload — no restart required).
    - Only model_config and prompt_path are overridable. Other fields
      (skills, tools, response_format_model) are NOT — they are code contracts.
    - Override format: {"task-type": {"model_config": {...}, "prompt_path": "..."}}

    Raises:
        KeyError: If task_type is not registered in AGENT_REGISTRY.
        FileNotFoundError: If AGENT_OVERRIDES_FILEPATH is set but file doesn't exist.
        json.JSONDecodeError: If the override file is invalid JSON.
    """
    config = AGENT_REGISTRY[task_type]  # KeyError = unsupported task type

    overrides_path = os.getenv("AGENT_OVERRIDES_FILEPATH")
    if overrides_path:
        with open(overrides_path) as f:
            overrides = json.load(f)
        if task_type in overrides:
            o = overrides[task_type]
            # Apply only model_config and prompt_path overrides (D-05)
            if "model_config" in o:
                config = AgentConfig(
                    **{**vars(config), "model_config": o["model_config"]}
                )
            if "prompt_path" in o:
                config = AgentConfig(
                    **{**vars(config), "prompt_path": o["prompt_path"]}
                )
            logger.debug(
                "Applied overrides for task_type=%s from %s", task_type, overrides_path
            )

    return config


# ---------------------------------------------------------------------------
# Per-module logging configuration (AGENT-09)
# ---------------------------------------------------------------------------

def configure_logging() -> None:
    """Configure per-module log levels from environment variables.

    Reads ROBOTINA_LOG_LEVEL_{MODULE} for modules: gateway, queue, agent, llm.
    Example: ROBOTINA_LOG_LEVEL_AGENT=DEBUG enables debug logging for all agent code.

    Call this once at process startup in runner.main() before any other setup.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    modules = ["gateway", "queue", "agent", "llm"]
    for module in modules:
        env_key = f"ROBOTINA_LOG_LEVEL_{module.upper()}"
        level_str = os.getenv(env_key, "")
        if level_str:
            level = getattr(logging, level_str.upper(), None)
            if level is not None:
                logging.getLogger(f"robotina.{module}").setLevel(level)
                logger.debug(
                    "Set log level for robotina.%s to %s (from %s)",
                    module, level_str.upper(), env_key,
                )
            else:
                logger.warning(
                    "Unknown log level %r in %s — ignoring", level_str, env_key
                )
