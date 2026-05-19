import os
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from redis import Redis
from rq import Queue
from sqlalchemy import text

from robotina.db import SessionLocal
from robotina.gateway.models import Conversation, StoredMessage


@pytest.fixture(autouse=True)
def _set_household_id(monkeypatch):
    """Ensure every test sees HOUSEHOLD_ID set so per-message bracket-form reads
    in gateway/handler.py (Phase 16) do not raise KeyError during collection or
    unrelated test execution. Tests that need to verify behavior with the env var
    unset/empty must explicitly call ``monkeypatch.delenv("HOUSEHOLD_ID", raising=False)``
    inside the test body.
    """
    monkeypatch.setenv("HOUSEHOLD_ID", "test-household")


@pytest.fixture
def db_session():
    """Live Postgres session. Cleans up all gateway rows after each test."""
    with SessionLocal() as session:
        try:
            yield session
        finally:
            session.execute(text("DELETE FROM stored_messages"))
            session.execute(text("DELETE FROM conversations"))
            session.commit()


@pytest.fixture
def redis_conn():
    """Live Redis connection. Flushes agent-tasks queue after each test."""
    conn = Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))
    yield conn
    q = Queue("agent-tasks", connection=conn)
    q.empty()


@pytest.fixture
def make_update():
    """Factory for mock telegram.Update objects."""
    def _make(
        message_id: int = 1001,
        chat_id: int = 99001,
        user_id: int = 55001,
        text: str = "test message",
        date: datetime | None = None,
    ):
        update = MagicMock()
        update.message.message_id = message_id
        update.message.chat_id = chat_id
        update.message.text = text
        update.message.date = date or datetime.now(timezone.utc)
        update.effective_user.id = user_id
        return update
    return _make


# ---------------------------------------------------------------------------
# Phase 18 / Wave 0 — shared invocation_factory fixture
# ---------------------------------------------------------------------------
# Used by gateway + dashboard tests to build RobotinaInvocation rows.


@pytest.fixture
def invocation_factory():
    """Build a RobotinaInvocation row in a session, defaulting to USER_MESSAGE + PENDING.

    Usage:
        inv = invocation_factory(session, conversation_id="conv-1", trigger_ref_id="msg-7")
    """
    def _make(session, *, conversation_id: str, trigger=None, trigger_ref_id=None, status=None):
        from robotina.queue.models import (
            RobotinaInvocation,
            InvocationTrigger,
            InvocationStatus,
        )
        inv = RobotinaInvocation(
            conversation_id=conversation_id,
            trigger=trigger or InvocationTrigger.USER_MESSAGE,
            trigger_ref_id=trigger_ref_id,
            status=status or InvocationStatus.PENDING,
        )
        session.add(inv)
        session.flush()
        return inv

    return _make
