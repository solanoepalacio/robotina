"""Integration tests for Phase 3 Gateway (GW-01 through GW-06).

Requires: docker compose up (live Postgres + Redis).
Run: uv run pytest tests/test_gateway.py -x -q
"""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rq import Queue

from robotina.gateway.models import Conversation, MessageRole, Platform, StoredMessage


@pytest.mark.integration
async def test_incoming_message_persisted(db_session, redis_conn, make_update):
    """GW-01: Incoming message is persisted as StoredMessage(role=USER)."""
    from robotina.gateway.handler import handle_message

    update = make_update(message_id=1001, chat_id=99001, user_id=55001, text="Hello Robotina")

    await handle_message(update, None)

    msgs = db_session.query(StoredMessage).filter_by(platform_message_id="1001").all()
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg.role == MessageRole.USER
    assert msg.text == "Hello Robotina"


@pytest.mark.integration
async def test_duplicate_message_skipped(db_session, redis_conn, make_update):
    """GW-02: Duplicate platform_message_id is skipped silently (no second StoredMessage row)."""
    from robotina.gateway.handler import handle_message

    update = make_update(message_id=2002, chat_id=99002, user_id=55002, text="First")

    await handle_message(update, None)
    await handle_message(update, None)  # second call with same message_id

    msgs = db_session.query(StoredMessage).filter_by(platform_message_id="2002").all()
    assert len(msgs) == 1  # only one row — duplicate was silently skipped


@pytest.mark.integration
async def test_history_window(db_session, redis_conn, make_update):
    """GW-03: Last N messages are attached as history, ordered oldest→newest."""
    from robotina.gateway.handler import handle_message

    with patch.dict(os.environ, {"CONVERSATION_HISTORY_WINDOW": "3"}):
        base_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chat_id = 99003
        user_id = 55003

        # Send 4 messages; window=3 means history of message 4 should contain msgs 2,3,4
        for i in range(1, 5):
            update = make_update(
                message_id=3000 + i,
                chat_id=chat_id,
                user_id=user_id,
                text=f"Message {i}",
                date=base_ts + timedelta(minutes=i),
            )
            await handle_message(update, None)

    # Fetch jobs from the queue - last one is message 4
    q = Queue("agent-tasks", connection=redis_conn)
    jobs = q.get_jobs()
    assert len(jobs) >= 4
    # Most recent job (enqueued at_front=True, but all 4 are in queue; last enqueued is first in queue)
    last_job = jobs[0]
    task_input = last_job.args[0]

    # history should have 3 messages (window=3), oldest first
    assert len(task_input.history) == 3
    texts = [h.text for h in task_input.history]
    assert texts == ["Message 2", "Message 3", "Message 4"]


@pytest.mark.integration
async def test_message_enqueued_at_front(db_session, redis_conn, make_update):
    """GW-04: handle-incoming-message job enqueued at front of agent-tasks queue."""
    from robotina.gateway.handler import handle_message

    update = make_update(message_id=4004, chat_id=99004, user_id=55004, text="Enqueue me")

    await handle_message(update, None)

    q = Queue("agent-tasks", connection=redis_conn)
    jobs = q.get_jobs()
    assert len(jobs) >= 1
    job = jobs[0]  # at_front=True means it's at the front
    assert job.meta.get("task_type") == "handle-incoming-message"
    task_input = job.args[0]
    assert task_input.message_id == "4004"
    assert task_input.platform == "telegram"
    assert task_input.text == "Enqueue me"


@pytest.mark.integration
async def test_send_message_persists(db_session, make_update):
    """GW-05: send_message() returns platform_message_id str; persists ASSISTANT StoredMessage."""
    from robotina.gateway.send import send_message

    # Pre-create a Conversation so send_message can find it
    conv = Conversation(platform=Platform.TELEGRAM, chat_id="99001", household_id="hh-1")
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)

    # Mock Bot.send_message to return a fake sent message
    fake_sent = MagicMock()
    fake_sent.message_id = 7777

    with patch("robotina.gateway.send.Bot") as MockBot:
        mock_bot_instance = AsyncMock()
        mock_bot_instance.send_message = AsyncMock(return_value=fake_sent)
        mock_bot_instance.__aenter__ = AsyncMock(return_value=mock_bot_instance)
        mock_bot_instance.__aexit__ = AsyncMock(return_value=None)
        MockBot.return_value = mock_bot_instance

        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test-token", "HOUSEHOLD_ID": "hh-1"}):
            result = await send_message(chat_id="99001", text="Hello!", user_id="55001")

    # Assert return value
    assert result == "7777", f"Expected '7777', got {result!r}"

    # Assert ASSISTANT StoredMessage was persisted
    db_session.expire_all()  # ensure fresh read
    rows = db_session.query(StoredMessage).filter_by(
        platform_message_id="7777"
    ).all()
    assert len(rows) == 1, f"Expected 1 StoredMessage with id 7777, found {len(rows)}"
    assert rows[0].role == MessageRole.ASSISTANT
    assert rows[0].text == "Hello!"
    assert rows[0].conversation_id == conv.id


@pytest.mark.integration
async def test_conversation_upsert(db_session, redis_conn, make_update):
    """GW-06: Second message from same chat reuses existing Conversation row."""
    from robotina.gateway.handler import handle_message

    chat_id = 99006
    user_id = 55006

    update1 = make_update(message_id=6001, chat_id=chat_id, user_id=user_id, text="First message")
    update2 = make_update(message_id=6002, chat_id=chat_id, user_id=user_id, text="Second message")

    await handle_message(update1, None)
    await handle_message(update2, None)

    conversations = db_session.query(Conversation).filter_by(
        platform=Platform.TELEGRAM, chat_id=str(chat_id)
    ).all()
    assert len(conversations) == 1  # only one Conversation row for the same chat

    messages = db_session.query(StoredMessage).filter(
        StoredMessage.conversation_id == conversations[0].id
    ).all()
    assert len(messages) == 2
