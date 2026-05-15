"""Telegram gateway package.

Entry points:
  main()        — starts PTB polling loop (uv run gateway)
  send_message  — imported from robotina.gateway.send (used by Phase 6)
"""
import logging
import os
import sys

from telegram.ext import ApplicationBuilder, MessageHandler, filters

from robotina.gateway.handler import handle_message


def main() -> None:
    """Entry point for `uv run gateway`. Starts Telegram bot in polling mode.

    Reads TELEGRAM_BOT_TOKEN and HOUSEHOLD_ID from env. Both are required:
    - TELEGRAM_BOT_TOKEN: KeyError on missing (fail fast on first attribute read).
    - HOUSEHOLD_ID (Phase 16, REQ-HID-5): explicit guard below — empty/whitespace
      values cause sys.exit(1) with a clear stderr message before any side effects.
      This prevents the silent ``household_id=""`` propagation bug that previously
      corrupted Conversation and WorkflowRun rows.

    run_polling() is synchronous and manages its own asyncio event loop.
    Do NOT wrap in asyncio.run().
    """
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    # Phase 16 — REQ-HID-5 / RESEARCH Pattern 2: fail-fast on missing or empty
    # HOUSEHOLD_ID. The check happens BEFORE ApplicationBuilder so the process
    # exits cleanly without spinning up Telegram polling. Whitespace-only values
    # are treated as empty (strip()).
    household_id = os.environ.get("HOUSEHOLD_ID", "").strip()
    if not household_id:
        sys.stderr.write(
            "FATAL: HOUSEHOLD_ID environment variable is unset or empty.\n"
            "  The gateway refuses to start because every Conversation and "
            "WorkflowRun row would otherwise carry an empty household_id.\n"
            "  Set HOUSEHOLD_ID in your .env file (see .env.example) and retry.\n"
        )
        sys.exit(1)

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.getLogger(__name__).info(
        "Starting Telegram gateway (polling mode) | household_id=%s",
        household_id,
    )
    app.run_polling()
