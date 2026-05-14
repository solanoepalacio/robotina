import json
import os

import pytest

from robotina.agent.agents import AgentConfig, get_agent_config


def test_get_agent_config_returns_agent_config():
    """AGENT-03: get_agent_config(task_type) returns an AgentConfig dataclass."""
    config = get_agent_config("handle-incoming-message")
    assert isinstance(config, AgentConfig)
    assert config.task_type == "handle-incoming-message"
    assert config.model_config["provider"] == "ollama"
    assert config.prompt_path == "src/robotina/agent/prompts/robotina/V003.md"


def test_agent_config_has_required_fields():
    """AGENT-03/AGENT-04: AgentConfig has task_type, model_config, prompt_path, skills, tools."""
    config = get_agent_config("handle-incoming-message")
    assert hasattr(config, "task_type")
    assert hasattr(config, "model_config")
    assert hasattr(config, "prompt_path")
    assert hasattr(config, "skills")
    assert hasattr(config, "tools")
    assert config.skills == ["household-manager"]
    assert config.tools == []


def test_api_token_read_from_env_var_name():
    """AGENT-04: model_config stores env var NAME not the token value."""
    config = get_agent_config("handle-incoming-message")
    assert config.model_config["api_key_env"] == "HANDLE_INCOMING_MESSAGE_API_TOKEN"


def test_overrides_filepath_hot_reload_model_config(tmp_path, monkeypatch):
    """AGENT-05: AGENT_OVERRIDES_FILEPATH overrides model_config per lookup."""
    overrides_file = tmp_path / "overrides.json"
    overrides_file.write_text(
        json.dumps(
            {
                "handle-incoming-message": {
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

    config = get_agent_config("handle-incoming-message")
    assert config.model_config["provider"] == "anthropic"
    assert config.model_config["model"] == "claude-3-5-haiku"
    assert config.model_config["api_key_env"] == "MY_KEY"


def test_overrides_filepath_hot_reload_prompt_path(tmp_path, monkeypatch):
    """AGENT-05: AGENT_OVERRIDES_FILEPATH overrides prompt_path per lookup."""
    overrides_file = tmp_path / "overrides.json"
    overrides_file.write_text(
        json.dumps({"handle-incoming-message": {"prompt_path": "/tmp/override.md"}})
    )
    monkeypatch.setenv("AGENT_OVERRIDES_FILEPATH", str(overrides_file))

    config = get_agent_config("handle-incoming-message")
    assert config.prompt_path == "/tmp/override.md"


def test_unknown_task_type_raises_key_error():
    """AGENT-03: get_agent_config raises KeyError for unregistered task type."""
    with pytest.raises(KeyError):
        get_agent_config("nonexistent")


def test_hello_world_removed_from_registry():
    """NOTIF-01: hello-world placeholder removed from AGENT_REGISTRY in Phase 6 (D-03)."""
    with pytest.raises(KeyError):
        get_agent_config("hello-world")


def test_send_notification_removed_from_registry():
    """Phase 07.1: send-notification is no longer an LLM agent (deterministic Python in run_task)."""
    with pytest.raises(KeyError):
        get_agent_config("send-notification")


def test_acknowledge_add_recipe_registered():
    """Phase 07.1: acknowledge-add-recipe runs as add-recipe workflow step 1."""
    config = get_agent_config("acknowledge-add-recipe")
    assert isinstance(config, AgentConfig)
    assert config.task_type == "acknowledge-add-recipe"
    assert config.prompt_path == "src/robotina/agent/prompts/acknowledge-add-recipe/V002.md"
    assert config.skills == []
    assert config.tools == []  # QueueTool injected per-job in run_task
    assert config.model_config["api_key_env"] == "ACKNOWLEDGE_ADD_RECIPE_API_TOKEN"


def test_handle_incoming_message_registered_in_agent_registry():
    """ROBOT-01: handle-incoming-message is registered in AGENT_REGISTRY."""
    config = get_agent_config("handle-incoming-message")
    assert isinstance(config, AgentConfig)
    assert config.task_type == "handle-incoming-message"
    assert config.skills == ["household-manager"]
    assert config.prompt_path == "src/robotina/agent/prompts/robotina/V003.md"
    assert config.tools == []  # tools are injected per-job, not stored in registry


def test_handle_incoming_message_api_token_env_var():
    """ROBOT-01/D-03: handle-incoming-message uses HANDLE_INCOMING_MESSAGE_API_TOKEN env var."""
    config = get_agent_config("handle-incoming-message")
    assert config.model_config["api_key_env"] == "HANDLE_INCOMING_MESSAGE_API_TOKEN"


def test_recipe_research_gather_registered():
    """RRECIPE-01/D-25: recipe-research-gather is registered in AGENT_REGISTRY."""
    config = get_agent_config("recipe-research-gather")
    assert isinstance(config, AgentConfig)
    assert config.task_type == "recipe-research-gather"
    assert config.skills == []
    assert config.prompt_path == "src/robotina/agent/prompts/recipe-research-gather/V005.md"
    assert config.tools == []
    assert config.model_config["api_key_env"] == "RECIPE_RESEARCH_GATHER_API_TOKEN"


def test_recipe_research_instructions_registered():
    """RRECIPE-01/D-25: recipe-research-instructions is registered."""
    config = get_agent_config("recipe-research-instructions")
    assert isinstance(config, AgentConfig)
    assert config.task_type == "recipe-research-instructions"
    assert config.skills == []
    assert config.prompt_path == "src/robotina/agent/prompts/recipe-research-instructions/V004.md"
    assert config.model_config["api_key_env"] == "RECIPE_RESEARCH_INSTRUCTIONS_API_TOKEN"


def test_recipe_research_ingredients_registered():
    """RRECIPE-01/D-25: recipe-research-ingredients is registered."""
    config = get_agent_config("recipe-research-ingredients")
    assert isinstance(config, AgentConfig)
    assert config.task_type == "recipe-research-ingredients"
    assert config.skills == []
    assert config.prompt_path == "src/robotina/agent/prompts/recipe-research-ingredients/V004.md"
    assert config.model_config["api_key_env"] == "RECIPE_RESEARCH_INGREDIENTS_API_TOKEN"


def test_recipe_research_metadata_registered():
    """RRECIPE-01/D-25: recipe-research-metadata is registered."""
    config = get_agent_config("recipe-research-metadata")
    assert isinstance(config, AgentConfig)
    assert config.task_type == "recipe-research-metadata"
    assert config.skills == []
    assert config.prompt_path == "src/robotina/agent/prompts/recipe-research-metadata/V003.md"
    assert config.model_config["api_key_env"] == "RECIPE_RESEARCH_METADATA_API_TOKEN"


def test_recipe_load_registered():
    """RLOAD-01: recipe-load is registered in AGENT_REGISTRY."""
    config = get_agent_config("recipe-load")
    assert isinstance(config, AgentConfig)
    assert config.task_type == "recipe-load"
    assert config.prompt_path == "src/robotina/agent/prompts/recipe-load/V004.md"
    assert config.tools == []
    assert config.model_config["api_key_env"] == "RECIPE_LOAD_API_TOKEN"


def test_recipe_load_uses_household_manager_skill():
    """RLOAD-02: recipe-load uses household-manager skill (D-08)."""
    config = get_agent_config("recipe-load")
    assert config.skills == ["household-manager"]
