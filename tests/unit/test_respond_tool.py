"""Tests for RespondTool (D-17).

Covers TOOLS-02: RespondTool is a non-terminal LangChain tool that enqueues a
send-notification job at the front of the queue with the Spanish reply text.

Per D-01: RespondTool replaces the retired QueueTool. Non-terminal
(return_direct=False) so Robotina can call it before start-workflow / terminate
in the same turn.

Tests mock RQ Queue — never touch real Redis.
"""
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError


def test_respond_tool_constructs():
    """RespondTool can be constructed with chat_id, user_id, platform, household_id."""
    from robotina.agent.tools.respond import RespondTool

    tool = RespondTool(
        chat_id="chat-42",
        user_id="user-7",
        platform="telegram",
        household_id="hh-1",
    )
    assert tool.chat_id == "chat-42"
    assert tool.user_id == "user-7"
    assert tool.platform == "telegram"
    assert tool.household_id == "hh-1"
    assert tool.name == "respond"


def test_respond_tool_is_non_terminal():
    """D-01: RespondTool is non-terminal (return_direct=False) so Robotina
    can call additional tools (start-workflow, terminate) in the same turn."""
    from robotina.agent.tools.respond import RespondTool

    tool = RespondTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="hh-1"
    )
    assert tool.return_direct is False


def test_respond_tool_args_schema_accepts_text():
    """args_schema accepts a single `text: str` field."""
    from robotina.agent.tools.respond import RespondTool

    tool = RespondTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="hh-1"
    )
    # args_schema validates {"text": "hola"} successfully
    schema = tool.args_schema
    validated = schema.model_validate({"text": "hola"})
    assert validated.text == "hola"


def test_respond_tool_args_schema_rejects_extra_fields():
    """args_schema has extra='forbid' — unknown LLM-emitted fields raise."""
    from robotina.agent.tools.respond import RespondTool

    tool = RespondTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="hh-1"
    )
    with pytest.raises(ValidationError):
        tool.args_schema.model_validate({"text": "hola", "platform": "telegram"})


def test_respond_tool_enqueues_send_notification_at_front():
    """_run(text=...) enqueues a send-notification job at_front=True,
    with result_ttl=-1, failure_ttl=-1, meta task_type, mirroring QueueTool."""
    from robotina.agent.tools.respond import RespondTool

    tool = RespondTool(
        chat_id="chat-42",
        user_id="user-7",
        platform="telegram",
        household_id="hh-1",
    )

    mock_job = MagicMock()
    mock_job.id = "job-uuid-abc"
    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = mock_job

    with patch("robotina.agent.tools.respond.Queue", return_value=mock_queue), \
         patch("robotina.agent.tools.respond.Redis"):
        result = tool._run(text="Hola, te aviso cuando tenga la receta.")

    call = mock_queue.enqueue.call_args
    assert call.args[0] == "robotina.queue.jobs.run_task"
    assert call.kwargs.get("at_front") is True
    assert call.kwargs.get("result_ttl") == -1
    assert call.kwargs.get("failure_ttl") == -1
    assert call.kwargs.get("meta") == {"task_type": "send-notification"}

    # First positional after the job-function name is the SendNotificationInput
    sni = call.args[1]
    from robotina.queue.task_types import SendNotificationInput
    assert isinstance(sni, SendNotificationInput)
    assert sni.text == "Hola, te aviso cuando tenga la receta."
    assert sni.chat_id == "chat-42"
    assert sni.user_id == "user-7"
    assert sni.platform == "telegram"

    assert "job-uuid-abc" in result


def test_respond_tool_empty_household_id_rejected():
    """Phase 16 (REQ-HID-2): NonEmptyHouseholdId rejects empty/whitespace."""
    from robotina.agent.tools.respond import RespondTool

    with pytest.raises(ValidationError):
        RespondTool(chat_id="c1", user_id="u1", platform="telegram", household_id="")
