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
    """

    task_type: str
    model_config: dict  # {provider, url, model, api_key_env}
    prompt_path: str
    skills: list[str] = field(default_factory=list)
    tools: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

AGENT_REGISTRY: dict[str, AgentConfig] = {
    "send-notification": AgentConfig(
        task_type="send-notification",
        model_config={
            "provider": "ollama",
            "url": "http://localhost:11434",
            "model": "gpt-oss:20b",
            "api_key_env": "SEND_NOTIFICATION_API_TOKEN",
            "reasoning": True,  # gpt-oss:20b is a thinking model; separates CoT from tool-call response
        },
        prompt_path="src/robotina/agent/prompts/send-notification/V001.md",
        skills=["format-telegram-message"],
        tools=[],  # SendNotificationTool is injected per-job in run_task() — see D-05
    ),
}


def get_agent_config(task_type: str) -> AgentConfig:
    """Look up AgentConfig for a task type, applying runtime overrides.

    Override behavior (D-05):
    - If AGENT_OVERRIDES_FILEPATH env var is set, the JSON file at that path is
      loaded on EVERY call (hot-reload — no restart required).
    - Only model_config and prompt_path are overridable. Other fields are not.
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
