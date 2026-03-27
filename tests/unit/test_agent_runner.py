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
    from robotina.queue.jobs import AgentLoggingHandler

    handler = AgentLoggingHandler()
    with caplog.at_level(logging.INFO, logger="robotina.queue.jobs"):
        handler.on_chat_model_start({"name": "ChatOllama"}, [[]])

    assert any("ChatOllama" in record.message for record in caplog.records), \
        f"Expected 'ChatOllama' in log. Got: {[r.message for r in caplog.records]}"


def test_agent_logging_handler_on_tool_start(caplog):
    """AGENT-10: AgentLoggingHandler.on_tool_start logs tool name and input."""
    from robotina.queue.jobs import AgentLoggingHandler

    handler = AgentLoggingHandler()
    with caplog.at_level(logging.INFO, logger="robotina.queue.jobs"):
        handler.on_tool_start({"name": "read-skill"}, "household-manager/index.md")

    messages = [r.message for r in caplog.records]
    assert any("read-skill" in m for m in messages), \
        f"Expected 'read-skill' in log. Got: {messages}"
    assert any("household-manager/index.md" in m for m in messages), \
        f"Expected input path in log. Got: {messages}"


def test_agent_logging_handler_on_tool_end(caplog):
    """AGENT-10: AgentLoggingHandler.on_tool_end logs tool output (truncated to 200 chars)."""
    from robotina.queue.jobs import AgentLoggingHandler

    handler = AgentLoggingHandler()
    long_output = "x" * 500
    with caplog.at_level(logging.INFO, logger="robotina.queue.jobs"):
        handler.on_tool_end(long_output)

    messages = [r.message for r in caplog.records]
    assert len(messages) > 0, "Expected at least one log message"
    # Verify output is truncated — logged message should not contain more than 200 'x' chars
    combined = " ".join(messages)
    assert "x" * 201 not in combined, "Output was not truncated to 200 chars"
    assert "x" * 200 in combined or "x" * 199 in combined, \
        f"Expected truncated output in log. Got: {combined[:100]}"
