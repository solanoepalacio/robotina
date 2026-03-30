"""send-notification tool for the Notification agent.

SendNotificationTool delivers a MarkdownV2-formatted message to the user via the
Telegram gateway. It is a dumb delivery mechanism — it sends whatever formatted_text
it receives without modification.

The tool is constructed with per-job recipient info (chat_id, user_id, platform) inside
run_task() — it is NEVER instantiated at module level or stored in AgentConfig.tools.
This is a locked architectural constraint (Phase 4, STATE.md).

asyncio.run() bridges the sync _run() context to the async send_message() function.
This is safe in the RQ worker subprocess — no event loop is running (D-02).
"""
from __future__ import annotations

import asyncio
import logging

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class SendNotificationTool(BaseTool):
    """LangChain tool that sends a formatted Telegram message via the gateway.

    Injected per-job into run_task() with recipient context from task_input.
    The agent's only job is to call this tool with MarkdownV2-formatted text.

    Args (via _run):
        formatted_text: The MarkdownV2-formatted message text to send.

    Returns:
        Delivery confirmation string with the Notification ID. Stop after receiving this.
    """

    name: str = "send-notification"
    description: str = (
        "Send the formatted message to the user via the gateway. "
        "Call this after applying the format-telegram-message skill to reformat the text. "
        "When this tool returns, the task is done — do not call it again. "
        "Args: formatted_text (str) — the MarkdownV2-formatted message to send."
    )

    # Injected at construction — agent never sees or reasons about these fields
    chat_id: str
    user_id: str
    platform: str  # always "telegram" for Phase 1

    def _run(self, formatted_text: str) -> str:
        """Send formatted_text via the Telegram gateway.

        Returns a clear completion signal so the agent stops after one call.
        Telegram errors (e.g. MarkdownV2 parse failures) are returned as error
        messages so the LLM can fix formatting and retry instead of failing the task.
        """
        from robotina.gateway.send import send_message

        try:
            result = asyncio.run(
                send_message(
                    chat_id=self.chat_id,
                    text=formatted_text,
                    user_id=self.user_id,
                    parse_mode="MarkdownV2",
                )
            )
        except Exception as exc:
            logger.warning(
                "send-notification tool failed | chat_id=%s error=%s",
                self.chat_id,
                exc,
            )
            return f"ERROR: {exc}"
        logger.info(
            "send-notification tool | chat_id=%s message_id=%s",
            self.chat_id,
            result.message_id,
        )
        return f"Notification Successfully Delivered. Notification ID = {result.message_id}"

    async def _arun(self, formatted_text: str) -> str:
        return self._run(formatted_text)
