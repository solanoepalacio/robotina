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

IMPORTANT: Enqueues at BACK of queue (no at_front=True). The gateway uses
at_front=True because it originates from outside the worker. Follow-up tasks
enqueued by agents go to the back so they don't preempt other waiting jobs.
"""
from __future__ import annotations

import logging
import os

from langchain_core.tools import BaseTool
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
        job_id string (UUID) — use for IncomingMessageOutput.queued_task_ids.
    """

    name: str = "queue"
    description: str = (
        "Enqueue a send-notification task to deliver a direct reply to the user. "
        "Use this when the user's request can be answered directly — questions "
        "about household data, current meal plan, recipe lookup, etc. "
        "When this tool returns, the task is done — do not call it again. "
        "Args: text (str) — the reply text to send to the user."
    )

    # Injected at construction — agent never sees or reasons about these fields
    chat_id: str
    user_id: str
    platform: str  # always "telegram" for Phase 1

    def _run(self, text: str) -> str:
        """Enqueue a send-notification task. Returns job.id string."""
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
            # NOTE: NO at_front=True — follow-up tasks go to back of queue
        )
        logger.info("queue tool | enqueued send-notification | job_id=%s", job.id)
        return job.id

    async def _arun(self, text: str) -> str:
        return self._run(text)
