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
    pytest.skip("stub — implement in Plan 03")


@pytest.mark.integration
async def test_conversation_upsert(db_session, redis_conn, make_update):
    """GW-06: Second message from same chat reuses existing Conversation row."""
    pytest.skip("stub — implement in Plan 02")
