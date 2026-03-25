"""Integration tests for Phase 3 Gateway (GW-01 through GW-06).

Requires: docker compose up (live Postgres + Redis).
Run: uv run pytest tests/test_gateway.py -x -q
"""
import pytest


@pytest.mark.integration
async def test_incoming_message_persisted(db_session, redis_conn, make_update):
    """GW-01: Incoming message is persisted as StoredMessage(role=USER)."""
    pytest.skip("stub — implement in Plan 02")


@pytest.mark.integration
async def test_duplicate_message_skipped(db_session, redis_conn, make_update):
    """GW-02: Duplicate platform_message_id is skipped silently (no second StoredMessage row)."""
    pytest.skip("stub — implement in Plan 02")


@pytest.mark.integration
async def test_history_window(db_session, redis_conn, make_update):
    """GW-03: Last N messages are attached as history, ordered oldest→newest."""
    pytest.skip("stub — implement in Plan 02")


@pytest.mark.integration
async def test_message_enqueued_at_front(db_session, redis_conn, make_update):
    """GW-04: handle-incoming-message job enqueued at front of agent-tasks queue."""
    pytest.skip("stub — implement in Plan 02")


async def test_send_message_persists(db_session, make_update):
    """GW-05: send_message() returns platform_message_id str; persists ASSISTANT StoredMessage."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from robotina.gateway.models import Conversation, MessageRole, Platform, StoredMessage
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
    pytest.skip("stub — implement in Plan 02")
