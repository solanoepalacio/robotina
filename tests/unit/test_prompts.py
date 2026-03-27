from pathlib import Path
from unittest.mock import MagicMock, patch


def test_prompt_file_exists_for_send_notification():
    """AGENT-08/NOTIF-05: src/robotina/agent/prompts/send-notification/V001.md exists."""
    prompt_path = Path("src/robotina/agent/prompts/send-notification/V001.md")
    assert prompt_path.exists(), (
        f"Expected prompt file at {prompt_path} — run from project root"
    )


def test_prompt_loaded_from_agent_config_path():
    """AGENT-08: Prompt text is loaded from the path in AgentConfig.prompt_path."""
    from robotina.agent.agents import get_agent_config

    config = get_agent_config("send-notification")
    assert config.prompt_path == "src/robotina/agent/prompts/send-notification/V001.md"

    prompt_text = Path(config.prompt_path).read_text()
    assert prompt_text.strip(), "Prompt file must not be empty"


def test_prompt_file_exists_for_robotina():
    """ROBOT-06: src/robotina/agent/prompts/robotina/V001.md exists."""
    from pathlib import Path
    prompt_path = Path("src/robotina/agent/prompts/robotina/V001.md")
    assert prompt_path.exists(), (
        f"Expected prompt file at {prompt_path} — run from project root"
    )
    assert prompt_path.read_text().strip(), "Prompt file must not be empty"


def test_skill_index_appended_to_prompt():
    """AGENT-11: Skill index.md content is appended to system prompt before agent invocation."""
    skill_index_content = "## Skill Index\nThis is the skill index content."

    mock_skill = MagicMock()
    mock_skill.index_content = skill_index_content

    mock_backend = MagicMock()
    mock_agent = MagicMock()
    mock_backend.create_agent.return_value = mock_agent
    mock_agent.invoke.return_value = {"messages": []}

    mock_job = MagicMock()
    mock_job.meta = {"task_type": "send-notification"}

    mock_session = MagicMock()
    mock_session_factory = MagicMock(return_value=mock_session)

    with (
        patch("robotina.queue.jobs.get_current_job", return_value=mock_job),
        patch("robotina.llm.make_backend", return_value=mock_backend),
        patch("robotina.agent.SkillSet", return_value=mock_skill),
        patch("robotina.agent.build_read_skill_tool", return_value=MagicMock()),
        patch("robotina.db.SessionLocal", mock_session_factory),
        patch("robotina.queue.workflow_runner.on_step_start"),
        patch("robotina.queue.workflow_runner.on_step_complete"),
        patch("robotina.queue.workflow_runner.on_step_failed"),
    ):
        # Temporarily give send-notification a skill so skill_index is non-empty
        from robotina.agent.agents import AGENT_REGISTRY, AgentConfig
        original_config = AGENT_REGISTRY["send-notification"]
        AGENT_REGISTRY["send-notification"] = AgentConfig(
            task_type="send-notification",
            model_config=original_config.model_config,
            prompt_path=original_config.prompt_path,
            skills=["fake-skill"],
            tools=[],
        )

        try:
            from robotina.queue.jobs import run_task
            run_task(MagicMock(text="test input", chat_id="123", user_id="456", platform="telegram"))
        finally:
            AGENT_REGISTRY["send-notification"] = original_config

    # Verify create_agent was called with a system_prompt containing skill index content
    assert mock_backend.create_agent.called, "create_agent was not called"
    call_kwargs = mock_backend.create_agent.call_args
    system_prompt = call_kwargs.kwargs.get("system_prompt") or call_kwargs.args[0]
    assert skill_index_content in system_prompt, (
        f"Skill index content not found in system_prompt.\n"
        f"Expected to find: {skill_index_content!r}\n"
        f"Got: {system_prompt!r}"
    )
