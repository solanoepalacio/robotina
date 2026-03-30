"""Tests for run_task() universal job function and AgentLoggingHandler.

Tests verify:
- AGENT-06: run_task reads task_type from RQ job meta, not from input model
- AGENT-07: LLM backend is created inside run_task, not at module level
- AGENT-10: AgentLoggingHandler logs LLM start, tool start, and tool end events
"""
import logging
from unittest.mock import MagicMock, patch

import pytest


def test_run_task_reads_task_type_from_job_meta():
    """AGENT-06: run_task reads task_type from RQ job meta, not from input model."""
    mock_job = MagicMock()
    mock_job.meta = {"task_type": "send-notification"}

    mock_config = MagicMock()
    mock_config.skills = []
    mock_config.tools = []
    mock_config.model_config = {
        "provider": "ollama",
        "url": "http://localhost:11434",
        "model": "llama3.2",
        "api_key_env": "TEST_TOKEN",
    }
    mock_config.prompt_path = "/tmp/test_prompt.md"

    mock_backend = MagicMock()
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {"messages": []}
    mock_backend.create_agent.return_value = mock_agent

    mock_session = MagicMock()
    mock_session_factory = MagicMock(return_value=mock_session)

    # Provide real string attributes for send-notification task input
    # (SendNotificationTool injection requires str fields — MagicMock auto-attrs fail Pydantic validation)
    mock_task_input = MagicMock()
    mock_task_input.chat_id = "test-chat-1"
    mock_task_input.user_id = "test-user-1"
    mock_task_input.platform = "telegram"
    mock_task_input.text = "test message"

    with patch("robotina.queue.jobs.get_current_job", return_value=mock_job), \
         patch("robotina.agent.agents.get_agent_config", return_value=mock_config) as mock_get_config, \
         patch("robotina.llm.make_backend", return_value=mock_backend), \
         patch("pathlib.Path.read_text", return_value="system prompt"), \
         patch("robotina.db.SessionLocal", mock_session_factory), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete"), \
         patch("robotina.queue.workflow_runner.on_step_failed"):
        from robotina.queue.jobs import run_task
        run_task(mock_task_input)

    mock_get_config.assert_called_once_with("send-notification")


def test_run_task_raises_if_no_task_type_in_meta():
    """AGENT-06: run_task raises ValueError when task_type missing from job meta."""
    mock_job = MagicMock()
    mock_job.meta = {}  # empty meta — no task_type

    with patch("robotina.queue.jobs.get_current_job", return_value=mock_job):
        from robotina.queue.jobs import run_task
        with pytest.raises(ValueError, match="task_type"):
            run_task(MagicMock())


def test_backend_instantiated_per_job_not_module_level():
    """AGENT-07: LLM backend is created inside run_task, not at import time.

    Verifies that importing robotina.queue.jobs does NOT trigger any LLM model
    instantiation. The module is imported with LLM constructors patched to raise
    if called — a module-level call would fail the import itself.
    """
    import sys

    # Remove cached module if already imported
    for mod_name in list(sys.modules.keys()):
        if mod_name == "robotina.queue.jobs":
            del sys.modules[mod_name]

    called = []

    def raise_if_called(*args, **kwargs):
        called.append(True)
        raise AssertionError("LLM model instantiated at module level!")

    # Patch all LLM constructors to raise if called at import time
    with patch("langchain_ollama.ChatOllama", side_effect=raise_if_called), \
         patch("langchain_anthropic.ChatAnthropic", side_effect=raise_if_called), \
         patch("langchain_openai.ChatOpenAI", side_effect=raise_if_called):
        # This should succeed without calling any LLM constructor
        import robotina.queue.jobs  # noqa: F401

    assert not called, "LLM model was instantiated at module level during import!"


def test_agent_logging_handler_on_llm_start(caplog):
    """AGENT-10: AgentLoggingHandler.on_chat_model_start logs LLM stream start."""
    from robotina.agent.callbacks import AgentLoggingHandler

    handler = AgentLoggingHandler()
    with caplog.at_level(logging.INFO, logger="robotina.agent.callbacks"):
        handler.on_chat_model_start({"name": "ChatOllama"}, [[]])

    assert any("ChatOllama" in record.message for record in caplog.records), \
        f"Expected 'ChatOllama' in log. Got: {[r.message for r in caplog.records]}"


def test_agent_logging_handler_on_tool_start(caplog):
    """AGENT-10: AgentLoggingHandler.on_tool_start logs tool name and input."""
    from robotina.agent.callbacks import AgentLoggingHandler

    handler = AgentLoggingHandler()
    with caplog.at_level(logging.INFO, logger="robotina.agent.callbacks"):
        handler.on_tool_start({"name": "read-skill"}, "household-manager/index.md")

    messages = [r.message for r in caplog.records]
    assert any("read-skill" in m for m in messages), \
        f"Expected 'read-skill' in log. Got: {messages}"
    assert any("household-manager/index.md" in m for m in messages), \
        f"Expected input path in log. Got: {messages}"


def test_run_task_injects_all_three_tools_for_handle_incoming_message():
    """ROBOT-01/D-04: run_task() injects HouseholdManagerApiTool, QueueTool, StartWorkflowTool
    for task_type == 'handle-incoming-message'."""
    from unittest.mock import MagicMock, patch

    mock_job = MagicMock()
    mock_job.id = "job-hm-001"
    mock_job.meta = {"task_type": "handle-incoming-message", "queue_name": "agent-tasks"}

    mock_config = MagicMock()
    mock_config.skills = []
    mock_config.tools = []
    mock_config.model_config = {
        "provider": "ollama",
        "url": "http://localhost:11434",
        "model": "gpt-oss:20b",
        "api_key_env": "HANDLE_INCOMING_MESSAGE_API_TOKEN",
    }
    mock_config.prompt_path = "/tmp/test_prompt.md"

    mock_backend = MagicMock()
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {"messages": []}
    mock_backend.create_agent.return_value = mock_agent

    mock_session = MagicMock()

    # Task input with all fields needed for tool construction
    task_input = MagicMock()
    task_input.chat_id = "chat-hm-1"
    task_input.user_id = "user-hm-1"
    task_input.platform = "telegram"
    task_input.household_id = "household-abc"
    task_input.text = "What's on the meal plan?"

    injected_tools = []

    def capture_tools(**kwargs):
        injected_tools.extend(kwargs.get("tools", []))
        return mock_agent

    mock_backend.create_agent.side_effect = capture_tools

    with (
        patch("robotina.queue.jobs.get_current_job", return_value=mock_job),
        patch("robotina.agent.agents.get_agent_config", return_value=mock_config),
        patch("robotina.llm.make_backend", return_value=mock_backend),
        patch("pathlib.Path.read_text", return_value="system prompt"),
        patch("robotina.db.SessionLocal", return_value=mock_session),
        patch("robotina.queue.workflow_runner.on_step_start"),
        patch("robotina.queue.workflow_runner.on_step_complete"),
        patch("robotina.queue.workflow_runner.on_step_failed"),
    ):
        from robotina.queue.jobs import run_task
        run_task(task_input)

    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    from robotina.agent.tools.queue import QueueTool
    from robotina.agent.tools.start_workflow import StartWorkflowTool

    hm_tools = [t for t in injected_tools if isinstance(t, HouseholdManagerApiTool)]
    q_tools = [t for t in injected_tools if isinstance(t, QueueTool)]
    sw_tools = [t for t in injected_tools if isinstance(t, StartWorkflowTool)]

    assert len(hm_tools) == 1, f"Expected 1 HouseholdManagerApiTool, got {injected_tools}"
    assert hm_tools[0].household_id == "household-abc"

    assert len(q_tools) == 1, f"Expected 1 QueueTool, got {injected_tools}"
    assert q_tools[0].chat_id == "chat-hm-1"
    assert q_tools[0].user_id == "user-hm-1"

    assert len(sw_tools) == 1, f"Expected 1 StartWorkflowTool, got {injected_tools}"
    assert sw_tools[0].chat_id == "chat-hm-1"
    assert sw_tools[0].user_id == "user-hm-1"
    assert sw_tools[0].platform == "telegram"
    assert sw_tools[0].household_id == "household-abc"

    # Verify AgentConfig.tools was NOT mutated
    assert mock_config.tools == []


def test_agent_logging_handler_on_tool_end(caplog):
    """AGENT-10: AgentLoggingHandler.on_tool_end logs tool output (truncated to 200 chars)."""
    from robotina.agent.callbacks import AgentLoggingHandler

    handler = AgentLoggingHandler()
    long_output = "x" * 500
    with caplog.at_level(logging.INFO, logger="robotina.agent.callbacks"):
        handler.on_tool_end(long_output)

    messages = [r.message for r in caplog.records]
    assert len(messages) > 0, "Expected at least one log message"
    # Verify output is truncated — logged message should not contain more than 200 'x' chars
    combined = " ".join(messages)
    assert "x" * 201 not in combined, "Output was not truncated to 200 chars"
    assert "x" * 200 in combined or "x" * 199 in combined, \
        f"Expected truncated output in log. Got: {combined[:100]}"
