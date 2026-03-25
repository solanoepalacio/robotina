import os
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from redis import Redis
from rq import Queue
from sqlalchemy import text

from robotina.db import SessionLocal
from robotina.gateway.models import Conversation, StoredMessage


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
