"""Tests for AgentConfig + get_agent_config behavior (Phase 11 — response_format_model field)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from robotina.agent.agents import AgentConfig, get_agent_config, AGENT_REGISTRY


class ToyModel(BaseModel):
    x: int


def test_agentconfig_response_format_model_defaults_to_none():
    cfg = AgentConfig(task_type="x", model_config={}, prompt_path="p")
    assert cfg.response_format_model is None


def test_agentconfig_response_format_model_accepts_basemodel_subclass():
    cfg = AgentConfig(
        task_type="x",
        model_config={},
        prompt_path="p",
        response_format_model=ToyModel,
    )
    assert cfg.response_format_model is ToyModel


def test_get_agent_config_does_not_propagate_response_format_model_from_overrides(
    tmp_path: Path, monkeypatch
):
    # Build an override file that tries to set response_format_model AND
    # a legitimate model_config override (the latter MUST still work).
    override_file = tmp_path / "overrides.json"
    override_file.write_text(json.dumps({
        "handle-incoming-message": {
            "model_config": {
                "provider": "openai",
                "model": "gpt-test",
                "api_key_env": "API_TOKEN_OPENAI",
            },
            "response_format_model": "this-should-be-ignored",
        }
    }))
    monkeypatch.setenv("AGENT_OVERRIDES_FILEPATH", str(override_file))

    config = get_agent_config("handle-incoming-message")
    # The override's response_format_model is silently dropped — schema is
    # a code contract, not config (per Phase 11 RESEARCH.md Anti-Patterns).
    assert config.response_format_model is None
    # The legitimate model_config override IS applied.
    assert config.model_config["provider"] == "openai"
    assert config.model_config["model"] == "gpt-test"


def test_get_agent_config_preserves_registry_response_format_model_through_model_config_override(
    tmp_path: Path, monkeypatch
):
    # Regression: if a registry entry has response_format_model set AND an
    # override modifies its model_config, the rebuilt AgentConfig must
    # retain the registry's response_format_model (the **vars(config) clone
    # must include the new field).
    # Pre-condition: ensure the registry has at least one entry with
    # response_format_model set. This task only adds the field; Plan 11-03
    # populates the 5 named agents. For this test, mutate AGENT_REGISTRY
    # for the duration of the test instead.
    original = AGENT_REGISTRY["handle-incoming-message"]
    AGENT_REGISTRY["handle-incoming-message"] = AgentConfig(
        task_type=original.task_type,
        model_config=original.model_config,
        prompt_path=original.prompt_path,
        skills=original.skills,
        tools=original.tools,
        response_format_model=ToyModel,
    )
    try:
        override_file = tmp_path / "overrides.json"
        override_file.write_text(json.dumps({
            "handle-incoming-message": {
                "model_config": {
                    "provider": "openai",
                    "model": "gpt-test",
                    "api_key_env": "API_TOKEN_OPENAI",
                }
            }
        }))
        monkeypatch.setenv("AGENT_OVERRIDES_FILEPATH", str(override_file))

        config = get_agent_config("handle-incoming-message")
        # Registry value flows through even though override touched model_config
        assert config.response_format_model is ToyModel
        assert config.model_config["provider"] == "openai"
    finally:
        AGENT_REGISTRY["handle-incoming-message"] = original
