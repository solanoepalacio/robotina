"""Incoming Telegram message handler for the gateway.

Flow per message:
1. Upsert Conversation for (platform=TELEGRAM, chat_id)
2. Persist StoredMessage with role=USER — skip silently on duplicate
3. Fetch last CONVERSATION_HISTORY_WINDOW messages (oldest->newest)
4. Enqueue handle-incoming-message job at front of agent-tasks queue

Env vars consumed:
  TELEGRAM_BOT_TOKEN  — required (KeyError on missing)
  HOUSEHOLD_ID        — REQUIRED for Conversation; KeyError on missing (Phase 16, REQ-HID-5).
                        The gateway entrypoint guard in __init__.py::main() validates
                        HOUSEHOLD_ID at startup, so by the time this handler runs the
                        env var is guaranteed non-empty.
  CONVERSATION_HISTORY_WINDOW — int, default 10
  REDIS_URL           — default redis://localhost:6379
  DATABASE_URL        — default postgresql://robotina:robotina@localhost:5432/robotina
"""
import logging
import os
from datetime import datetime, timezone

from redis import Redis
from rq import Queue
from sqlalchemy.exc import IntegrityError
from telegram import Update
from telegram.ext import ContextTypes

from robotina.db import SessionLocal
from robotina.gateway.models import Conversation, MessageRole, Platform, StoredMessage
from robotina.queue.models import InvocationStatus, InvocationTrigger, RobotinaInvocation
from robotina.queue.task_types import IncomingMessageInput
from robotina.queue.task_types import Message as HistoryMessage

logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """PTB async handler — processes one incoming Telegram text message."""
    msg = update.message
    if not msg or not msg.text:
        return

    platform_message_id = str(msg.message_id)
    chat_id = str(msg.chat_id)
    user_id = str(update.effective_user.id)
    # Phase 16 — REQ-HID-5: bracket form removes the silent "" default. The
    # gateway entrypoint guard (__init__.py::main) validates HOUSEHOLD_ID at
    # startup, so in production this read never raises. In tests, the autouse
    # conftest fixture (_set_household_id) injects "test-household".
    household_id = os.environ["HOUSEHOLD_ID"]
    history_limit = int(os.environ.get("CONVERSATION_HISTORY_WINDOW", "10"))
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")

    with SessionLocal() as session:
        # Step 1: Upsert Conversation
        conv = session.query(Conversation).filter_by(
            platform=Platform.TELEGRAM, chat_id=chat_id
        ).first()
        if conv is None:
            conv = Conversation(
                platform=Platform.TELEGRAM,
                chat_id=chat_id,
                household_id=household_id,
            )
            try:
                session.add(conv)
                session.flush()
            except IntegrityError:
                session.rollback()
                conv = session.query(Conversation).filter_by(
                    platform=Platform.TELEGRAM, chat_id=chat_id
                ).first()

        # Step 2: Persist StoredMessage (dedup via unique constraint)
        sent_at = msg.date if msg.date.tzinfo is not None else msg.date.replace(tzinfo=timezone.utc)
        stored = StoredMessage(
            conversation_id=conv.id,
            platform_message_id=platform_message_id,
            role=MessageRole.USER,
            text=msg.text,
            sent_at=sent_at,
        )
        try:
            session.add(stored)
            session.flush()
        except IntegrityError:
            session.rollback()
            logger.debug("Duplicate message %s — skipping", platform_message_id)
            return  # deduplicated; do not enqueue

        # Step 2b (Phase 18 / ARCH-02 / D-11): persist RobotinaInvocation in
        # the SAME transaction as the StoredMessage. MUST run AFTER the
        # IntegrityError short-circuit above — a duplicate message must NOT
        # create an orphan PENDING invocation (Phase 20's wake reconciler
        # would treat orphans as stuck; D-24, Pitfall 1).
        inv = RobotinaInvocation(
            conversation_id=conv.id,
            trigger=InvocationTrigger.USER_MESSAGE,
            trigger_ref_id=stored.id,
            status=InvocationStatus.PENDING,
        )
        session.add(inv)
        session.flush()  # materialize inv.id for the meta dict below
        invocation_id = inv.id

        # Step 3: Fetch history (oldest->newest)
        rows = (
            session.query(StoredMessage)
            .filter_by(conversation_id=conv.id)
            .order_by(StoredMessage.sent_at.desc())
            .limit(history_limit)
            .all()
        )
        rows.reverse()
        history = [
            HistoryMessage(
                message_id=r.platform_message_id,
                role=r.role.value,
                text=r.text,
                sent_at=r.sent_at,
            )
            for r in rows
        ]

        session.commit()

    # Step 4: Enqueue at front of agent-tasks (outside DB session)
    task_input = IncomingMessageInput(
        message_id=platform_message_id,
        platform="telegram",
        received_at=datetime.now(timezone.utc),
        chat_id=chat_id,
        user_id=user_id,
        household_id=household_id,
        text=msg.text,
        history=history,
    )
    redis_conn = Redis.from_url(redis_url)
    q = Queue("agent-tasks", connection=redis_conn)
    q.enqueue(
        "robotina.queue.jobs.run_task",
        task_input,
        at_front=True,
        result_ttl=-1,
        failure_ttl=-1,
        meta={"task_type": "handle-incoming-message", "invocation_id": invocation_id},
    )
    logger.info(
        "Enqueued handle-incoming-message at front of agent-tasks | "
        "chat_id=%s message_id=%s",
        chat_id,
        platform_message_id,
    )
