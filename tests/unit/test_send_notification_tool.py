"""Tests for SendNotificationTool.

Covers NOTIF-04: SendNotificationTool sends formatted message via gateway.
Tests mock send_message() — never call the real async gateway in unit tests.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_send_notification_tool_construction():
    """NOTIF-04: SendNotificationTool can be constructed with chat_id, user_id, platform."""
    from robotina.agent.tools.send_notification import SendNotificationTool
    tool = SendNotificationTool(chat_id="123", user_id="456", platform="telegram")
    assert tool.chat_id == "123"
    assert tool.user_id == "456"
    assert tool.platform == "telegram"


def test_send_notification_tool_name_and_description():
    """NOTIF-04: Tool name is 'send-notification' and description mentions formatted_text."""
    from robotina.agent.tools.send_notification import SendNotificationTool
    tool = SendNotificationTool(chat_id="1", user_id="2", platform="telegram")
    assert tool.name == "send-notification"
    assert "formatted_text" in tool.description
    assert len(tool.description) > 20


def test_send_notification_tool_run_calls_send_message():
    """NOTIF-04: _run(formatted_text) calls send_message with chat_id, text, user_id, parse_mode."""
    from robotina.agent.tools.send_notification import SendNotificationTool
    from robotina.gateway.send import SendResult

    tool = SendNotificationTool(chat_id="123", user_id="456", platform="telegram")

    mock_coro = AsyncMock(return_value=SendResult(message_id="msg-001"))
    with patch("robotina.gateway.send.send_message", mock_coro):
        result = tool._run("*formatted text*")

    mock_coro.assert_called_once_with(
        chat_id="123",
        text="*formatted text*",
        user_id="456",
        parse_mode="MarkdownV2",
    )


def test_send_notification_tool_run_returns_delivery_confirmation():
    """NOTIF-04: _run() returns a clear stop signal with the Notification ID."""
    from robotina.agent.tools.send_notification import SendNotificationTool
    from robotina.gateway.send import SendResult

    tool = SendNotificationTool(chat_id="123", user_id="456", platform="telegram")

    mock_coro = AsyncMock(return_value=SendResult(message_id="telegram-msg-999"))
    with patch("robotina.gateway.send.send_message", mock_coro):
        result = tool._run("hello")

    assert result == "Notification Successfully Delivered. Notification ID = telegram-msg-999"


def test_send_notification_tool_run_uses_asyncio_run():
    """NOTIF-04: _run() uses asyncio.run() to bridge sync->async — safe for RQ workers."""
    import asyncio as asyncio_module
    from robotina.agent.tools.send_notification import SendNotificationTool

    tool = SendNotificationTool(chat_id="1", user_id="2", platform="telegram")
    calls = []

    original_run = asyncio_module.run

    def capture_run(coro, **kwargs):
        calls.append(coro)
        return original_run(coro, **kwargs)

    from robotina.gateway.send import SendResult
    mock_send = AsyncMock(return_value=SendResult(message_id="msg-abc"))
    with (
        patch("robotina.gateway.send.send_message", mock_send),
        patch("asyncio.run", side_effect=capture_run),
    ):
        tool._run("test")

    assert len(calls) == 1, "asyncio.run() must be called exactly once"


def test_run_task_injects_send_notification_tool_for_task_type():
    """NOTIF-04/D-05: run_task() creates SendNotificationTool with task_input fields
    when task_type == 'send-notification', without mutating AgentConfig."""
    from unittest.mock import MagicMock, patch

    mock_job = MagicMock()
    mock_job.id = "job-123"
    mock_job.meta = {"task_type": "send-notification", "queue_name": "agent-tasks"}

    mock_config = MagicMock()
    mock_config.skills = []
    mock_config.tools = []
    mock_config.model_config = {
        "provider": "ollama",
        "url": "http://localhost:11434",
        "model": "llama3.2",
        "api_key_env": "SEND_NOTIFICATION_API_TOKEN",
    }
    mock_config.prompt_path = "/tmp/test_prompt.md"

    mock_backend = MagicMock()
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {"messages": []}
    mock_backend.create_agent.return_value = mock_agent

    mock_session = MagicMock()
    mock_session_factory = MagicMock(return_value=mock_session)

    task_input = MagicMock()
    task_input.chat_id = "telegram-chat-42"
    task_input.user_id = "user-7"
    task_input.platform = "telegram"
    task_input.text = "The recipe was saved."

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
        patch("robotina.db.SessionLocal", mock_session_factory),
        patch("robotina.queue.workflow_runner.on_step_start"),
        patch("robotina.queue.workflow_runner.on_step_complete"),
        patch("robotina.queue.workflow_runner.on_step_failed"),
    ):
        from robotina.queue.jobs import run_task
        run_task(task_input)

    from robotina.agent.tools.send_notification import SendNotificationTool
    notif_tools = [t for t in injected_tools if isinstance(t, SendNotificationTool)]
    assert len(notif_tools) == 1, f"Expected 1 SendNotificationTool, got {injected_tools}"
    assert notif_tools[0].chat_id == "telegram-chat-42"
    assert notif_tools[0].user_id == "user-7"
    assert notif_tools[0].platform == "telegram"
    # Verify AgentConfig.tools was NOT mutated (still empty list)
    assert mock_config.tools == []
