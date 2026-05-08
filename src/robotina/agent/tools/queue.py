"""queue tool for the Robotina routing agent.

QueueTool enqueues a send-notification follow-up task when the agent has a
direct-reply answer for the user. The agent calls this with the reply text only.

Recipient context (chat_id, user_id, platform) is injected at construction inside
run_task() — the agent never sees or reasons about these fields.

Per-job injection pattern (locked Phase 4 constraint):
    tools.append(QueueTool(
        chat_id=task_input.chat_id,
        user_id=task_input.user_id,
        platform=task_input.platform,
    ))

Enqueues at FRONT of queue (at_front=True). Notification replies to the user
should always be delivered before other pending jobs like research or loading.

Phase 07.1: returns Command(goto=END) so the LangGraph state machine cannot
loop after the tool succeeds. Termination is enforced by the engine, not by
prompt-level pleading.
"""
from __future__ import annotations

import logging
import os
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId
from langgraph.graph import END
from langgraph.types import Command
from redis import Redis
from rq import Queue

logger = logging.getLogger(__name__)


class QueueTool(BaseTool):
    """LangChain tool that enqueues a send-notification task as a direct reply.

    Hardcoded to enqueue 'send-notification' task type. The agent provides
    only the reply text — recipient context is injected invisibly.

    Args (via _run):
        text: The reply text to deliver to the user.

    Returns:
        Command(goto=END) carrying a ToolMessage with the enqueued job_id.
        The agent graph routes to END immediately — no further model invocation.
    """

    name: str = "queue"
    description: str = (
        "Enqueue a send-notification task to deliver a reply to the user. "
        "Use this for direct replies (answers to questions). "
        "Args: text (str) — the reply text to send to the user."
    )

    # Injected at construction — agent never sees or reasons about these fields
    chat_id: str
    user_id: str
    platform: str  # always "telegram" for Phase 1

    def _run(self, text: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
        """Enqueue a send-notification task. Returns Command(goto=END)."""
        from robotina.queue.task_types import SendNotificationInput

        task_input = SendNotificationInput(
            platform=self.platform,
            chat_id=self.chat_id,
            user_id=self.user_id,
            text=text,
        )
        q = Queue(
            "agent-tasks",
            connection=Redis.from_url(
                os.environ.get("REDIS_URL", "redis://localhost:6379")
            ),
        )
        job = q.enqueue(
            "robotina.queue.jobs.run_task",
            task_input,
            result_ttl=-1,
            failure_ttl=-1,
            meta={"task_type": "send-notification"},
            at_front=True,
        )
        logger.info("queue tool | enqueued send-notification | job_id=%s", job.id)
        return Command(
            update={"messages": [ToolMessage(
                content=f"Reply queued. job_id={job.id}",
                tool_call_id=tool_call_id,
                name="queue",
            )]},
            goto=END,
        )

    async def _arun(self, text: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
        return self._run(text, tool_call_id)
