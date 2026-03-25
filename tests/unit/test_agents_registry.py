import json
import os

import pytest

from robotina.agent.agents import AgentConfig, get_agent_config


def test_get_agent_config_returns_agent_config():
    """AGENT-03: get_agent_config(task_type) returns an AgentConfig dataclass."""
    config = get_agent_config("hello-world")
    assert isinstance(config, AgentConfig)
    assert config.task_type == "hello-world"
    assert config.model_config["provider"] == "ollama"
    assert config.prompt_path == "src/robotina/agent/prompts/hello-world/V001.md"


def test_agent_config_has_required_fields():
    """AGENT-03/AGENT-04: AgentConfig has task_type, model_config, prompt_path, skills, tools."""
    config = get_agent_config("hello-world")
    assert hasattr(config, "task_type")
    assert hasattr(config, "model_config")
    assert hasattr(config, "prompt_path")
    assert hasattr(config, "skills")
    assert hasattr(config, "tools")
    assert config.skills == []
    assert config.tools == []


def test_api_token_read_from_env_var_name():
    """AGENT-04: model_config stores env var NAME not the token value."""
    config = get_agent_config("hello-world")
    assert config.model_config["api_key_env"] == "HELLO_WORLD_API_TOKEN"


def test_overrides_filepath_hot_reload_model_config(tmp_path, monkeypatch):
    """AGENT-05: AGENT_OVERRIDES_FILEPATH overrides model_config per lookup."""
    overrides_file = tmp_path / "overrides.json"
    overrides_file.write_text(
        json.dumps(
            {
                "hello-world": {
                    "model_config": {
                        "provider": "anthropic",
                        "model": "claude-3-5-haiku",
                        "api_key_env": "MY_KEY",
                    }
                }
            }
        )
    )
    monkeypatch.setenv("AGENT_OVERRIDES_FILEPATH", str(overrides_file))

    config = get_agent_config("hello-world")
    assert config.model_config["provider"] == "anthropic"
    assert config.model_config["model"] == "claude-3-5-haiku"
    assert config.model_config["api_key_env"] == "MY_KEY"


def test_overrides_filepath_hot_reload_prompt_path(tmp_path, monkeypatch):
    """AGENT-05: AGENT_OVERRIDES_FILEPATH overrides prompt_path per lookup."""
    overrides_file = tmp_path / "overrides.json"
    overrides_file.write_text(
        json.dumps({"hello-world": {"prompt_path": "/tmp/override.md"}})
    )
    monkeypatch.setenv("AGENT_OVERRIDES_FILEPATH", str(overrides_file))

    config = get_agent_config("hello-world")
    assert config.prompt_path == "/tmp/override.md"


def test_unknown_task_type_raises_key_error():
    """AGENT-03: get_agent_config raises KeyError for unregistered task type."""
    with pytest.raises(KeyError):
        get_agent_config("nonexistent")
