"""Tests for SendNotificationTool.

Covers NOTIF-04: SendNotificationTool sends formatted message via gateway.
Tests use mocked send_message() — never call the real async gateway in unit tests.
"""
import pytest


def test_send_notification_tool_construction():
    """NOTIF-04: SendNotificationTool can be constructed with chat_id, user_id, platform."""
    pytest.skip("Wave 0 stub — Plan 06-02 implements SendNotificationTool")
    from robotina.agent.tools.send_notification import SendNotificationTool  # noqa


def test_send_notification_tool_name_and_description():
    """NOTIF-04: Tool name is 'send-notification' and description is non-empty."""
    pytest.skip("Wave 0 stub — Plan 06-02 implements SendNotificationTool")
    from robotina.agent.tools.send_notification import SendNotificationTool  # noqa


def test_send_notification_tool_run_calls_send_message():
    """NOTIF-04: _run(formatted_text) calls send_message with correct chat_id and text."""
    pytest.skip("Wave 0 stub — Plan 06-02 implements SendNotificationTool")
    from robotina.agent.tools.send_notification import SendNotificationTool  # noqa


def test_send_notification_tool_run_returns_platform_message_id():
    """NOTIF-04: _run() returns the platform_message_id string from send_message()."""
    pytest.skip("Wave 0 stub — Plan 06-02 implements SendNotificationTool")
    from robotina.agent.tools.send_notification import SendNotificationTool  # noqa


def test_send_notification_tool_run_uses_asyncio_run():
    """NOTIF-04: _run() bridges sync->async via asyncio.run() — safe for RQ workers."""
    pytest.skip("Wave 0 stub — Plan 06-02 implements SendNotificationTool")
    from robotina.agent.tools.send_notification import SendNotificationTool  # noqa


def test_run_task_injects_send_notification_tool_for_task_type():
    """NOTIF-04/D-05: run_task() creates SendNotificationTool with task_input fields
    when task_type == 'send-notification', without mutating AgentConfig."""
    pytest.skip("Wave 0 stub — Plan 06-02 implements run_task() injection")
    from robotina.agent.tools.send_notification import SendNotificationTool  # noqa
