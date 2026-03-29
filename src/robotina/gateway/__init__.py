"""Telegram gateway package.

Entry points:
  main()        — starts PTB polling loop (uv run gateway)
  send_message  — imported from robotina.gateway.send (used by Phase 6)
"""
import logging
import os

from telegram.ext import ApplicationBuilder, MessageHandler, filters

from robotina.gateway.handler import handle_message


def main() -> None:
    """Entry point for `uv run gateway`. Starts Telegram bot in polling mode.

    Reads TELEGRAM_BOT_TOKEN from env (KeyError on missing — fail fast).
    run_polling() is synchronous and manages its own asyncio event loop.
    Do NOT wrap in asyncio.run().
    """
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.getLogger(__name__).info("Starting Telegram gateway (polling mode)...")
    app.run_polling()
