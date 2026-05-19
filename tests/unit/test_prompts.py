from pathlib import Path
from unittest.mock import MagicMock, patch


def test_prompt_file_exists_for_robotina():
    """ROBOT-06: src/robotina/agent/prompts/robotina/V002.md exists."""
    prompt_path = Path("src/robotina/agent/prompts/robotina/V002.md")
    assert prompt_path.exists(), (
        f"Expected prompt file at {prompt_path} — run from project root"
    )
    assert prompt_path.read_text().strip(), "Prompt file must not be empty"


def test_prompt_file_exists_for_recipe_research_gather():
    """RRECIPE-05: src/robotina/agent/prompts/recipe-research-gather/V001.md exists."""
    prompt_path = Path("src/robotina/agent/prompts/recipe-research-gather/V001.md")
    assert prompt_path.exists(), f"Expected prompt file at {prompt_path}"
    assert prompt_path.read_text().strip(), "Prompt file must not be empty"


def test_prompt_file_exists_for_recipe_research_instructions():
    """RRECIPE-05: src/robotina/agent/prompts/recipe-research-instructions/V001.md exists."""
    prompt_path = Path("src/robotina/agent/prompts/recipe-research-instructions/V001.md")
    assert prompt_path.exists(), f"Expected prompt file at {prompt_path}"
    assert prompt_path.read_text().strip(), "Prompt file must not be empty"


def test_prompt_file_exists_for_recipe_research_ingredients():
    """RRECIPE-05: src/robotina/agent/prompts/recipe-research-ingredients/V001.md exists."""
    prompt_path = Path("src/robotina/agent/prompts/recipe-research-ingredients/V001.md")
    assert prompt_path.exists(), f"Expected prompt file at {prompt_path}"
    assert prompt_path.read_text().strip(), "Prompt file must not be empty"


def test_prompt_file_exists_for_recipe_research_metadata():
    """RRECIPE-05: src/robotina/agent/prompts/recipe-research-metadata/V001.md exists."""
    prompt_path = Path("src/robotina/agent/prompts/recipe-research-metadata/V001.md")
    assert prompt_path.exists(), f"Expected prompt file at {prompt_path}"
    assert prompt_path.read_text().strip(), "Prompt file must not be empty"


def test_prompt_file_exists_for_recipe_load():
    """RLOAD-05: src/robotina/agent/prompts/recipe-load/V001.md exists."""
    prompt_path = Path("src/robotina/agent/prompts/recipe-load/V001.md")
    assert prompt_path.exists(), f"Expected prompt file at {prompt_path}"
    assert prompt_path.read_text().strip(), "Prompt file must not be empty"


def test_skill_index_appended_to_prompt():
    """AGENT-11: Skill index.md content is appended to system prompt before agent invocation.

    Uses the handle-incoming-message agent (which has a real skill, household-manager)
    rather than send-notification (deterministic non-LLM since Phase 07.1).
    """
    skill_index_content = "## Skill Index\nThis is the skill index content."

    mock_skill = MagicMock()
    mock_skill.index_content = skill_index_content

    mock_backend = MagicMock()
    mock_agent = MagicMock()
    mock_backend.create_agent.return_value = mock_agent
    mock_agent.invoke.return_value = {"messages": []}

    mock_job = MagicMock()
    mock_job.meta = {"task_type": "handle-incoming-message", "invocation_id": "inv-stub-1"}

    mock_session = MagicMock()
    # Phase 17 / D-04: run_task's handle-incoming-message branch resolves
    # Conversation via session.query(Conversation).filter_by(...).one().
    # Stub the lookup so .id returns a string (not a MagicMock) — the
    # StartWorkflowTool ctor field validation requires a str.
    fake_conversation = MagicMock()
    fake_conversation.id = "conv-stub-1"
    query_mock = MagicMock()
    query_mock.filter_by.return_value = query_mock
    query_mock.one.return_value = fake_conversation
    mock_session.query.return_value = query_mock
    mock_session_factory = MagicMock(return_value=mock_session)

    with (
        patch("robotina.queue.jobs.get_current_job", return_value=mock_job),
        patch("robotina.llm.make_backend", return_value=mock_backend),
        patch("robotina.agent.tools.read_skill.SkillSet", return_value=mock_skill),
        patch("robotina.agent.tools.read_skill.build_read_skill_tool", return_value=MagicMock()),
        patch("robotina.db.SessionLocal", mock_session_factory),
        patch("robotina.queue.workflow_runner.on_step_start"),
        patch("robotina.queue.workflow_runner.on_step_complete"),
        patch("robotina.queue.workflow_runner.on_step_failed"),
    ):
        from robotina.queue.jobs import run_task
        # handle-incoming-message expects a task_input with chat_id/user_id/platform/household_id
        # and a to_user_message() method.
        task_input = MagicMock(
            chat_id="123",
            user_id="456",
            platform="telegram",
            household_id="hh-1",
        )
        task_input.to_user_message.return_value = "test input"
        run_task(task_input)

    # Verify create_agent was called with a system_prompt containing skill index content
    assert mock_backend.create_agent.called, "create_agent was not called"
    call_kwargs = mock_backend.create_agent.call_args
    system_prompt = call_kwargs.kwargs.get("system_prompt") or call_kwargs.args[0]
    assert skill_index_content in system_prompt, (
        f"Skill index content not found in system_prompt.\n"
        f"Expected to find: {skill_index_content!r}\n"
        f"Got: {system_prompt!r}"
    )
