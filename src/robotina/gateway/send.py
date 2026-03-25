"""Outgoing Telegram message function for the gateway.

This module is imported directly by Phase 6's send-notification tool:
    from robotina.gateway.send import send_message

send_message() is a standalone async function — it is NOT tied to the
PTB Application polling loop. It uses Bot as an async context manager
to ensure the HTTP client is properly initialized and closed per call.

Env vars consumed:
  TELEGRAM_BOT_TOKEN  — required (KeyError on missing)
  HOUSEHOLD_ID        — used for Conversation lookup; defaults ""
  DATABASE_URL        — default postgresql://robotina:robotina@localhost:5432/robotina
"""
import logging
import os
from datetime import datetime, timezone

from telegram import Bot

from robotina.db import SessionLocal
from robotina.gateway.models import Conversation, MessageRole, Platform, StoredMessage

logger = logging.getLogger(__name__)


async def send_message(chat_id: str, text: str, user_id: str) -> str:
    """Send a Telegram message and persist it as an ASSISTANT StoredMessage.

    Args:
        chat_id: Telegram chat ID (stored as str in DB; cast to int for API call).
        text: Message text to send.
        user_id: Platform user ID (for context; not used in this function directly).

    Returns:
        platform_message_id: Telegram-assigned message_id as str.

    Called by: Phase 6 send-notification tool
    """
    token = os.environ["TELEGRAM_BOT_TOKEN"]

    # Send via Telegram Bot API — standalone usage requires async with context manager
    bot = Bot(token=token)
    async with bot:
        sent = await bot.send_message(chat_id=int(chat_id), text=text)
    platform_message_id = str(sent.message_id)

    # Persist outgoing message to Postgres
    with SessionLocal() as session:
        conv = session.query(Conversation).filter_by(
            platform=Platform.TELEGRAM, chat_id=chat_id
        ).first()
        if conv is not None:
            msg = StoredMessage(
                conversation_id=conv.id,
                platform_message_id=platform_message_id,
                role=MessageRole.ASSISTANT,
                text=text,
                sent_at=datetime.now(timezone.utc),
            )
            session.add(msg)
            session.commit()
            logger.debug(
                "Persisted outgoing message %s to conversation %s",
                platform_message_id,
                conv.id,
            )
        else:
            logger.warning(
                "No Conversation found for chat_id=%s — outgoing message not persisted",
                chat_id,
            )

    logger.info(
        "Sent Telegram message to chat_id=%s | message_id=%s",
        chat_id,
        platform_message_id,
    )
    return platform_message_id
