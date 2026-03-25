import pytest


def test_get_agent_config_returns_agent_config():
    """AGENT-03: get_agent_config(task_type) returns an AgentConfig dataclass."""
    pytest.skip("not implemented")


def test_agent_config_has_required_fields():
    """AGENT-03/AGENT-04: AgentConfig has task_type, model_config, prompt_path, skills, tools."""
    pytest.skip("not implemented")


def test_api_token_read_from_env_var_name():
    """AGENT-04: model_config stores env var NAME not the token value."""
    pytest.skip("not implemented")


def test_overrides_filepath_hot_reload_model_config():
    """AGENT-05: AGENT_OVERRIDES_FILEPATH overrides model_config per lookup."""
    pytest.skip("not implemented")


def test_overrides_filepath_hot_reload_prompt_path():
    """AGENT-05: AGENT_OVERRIDES_FILEPATH overrides prompt_path per lookup."""
    pytest.skip("not implemented")


def test_unknown_task_type_raises_key_error():
    """AGENT-03: get_agent_config raises KeyError for unregistered task type."""
    pytest.skip("not implemented")
