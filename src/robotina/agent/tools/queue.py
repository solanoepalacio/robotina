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

Phase 07.1: ``return_direct=True`` makes this a TERMINAL tool — the LangGraph
``create_react_agent`` graph terminates immediately after the tool runs, with no
further LLM invocation. This is engine-enforced termination, not a prompt-level
request. (Note: returning ``Command(goto=END)`` does NOT short-circuit the
prebuilt graph in langgraph 1.1.x — verified empirically. ``return_direct``
is the supported mechanism.)
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
        Confirmation string with the enqueued job_id. ``return_direct=True``
        causes the LangGraph agent to terminate immediately after — no
        further model invocation.
    """

    name: str = "queue"
    description: str = (
        "Enqueue a send-notification task to deliver a reply to the user. "
        "Use this for direct replies (answers to questions). "
        "Args: text (str) — the reply text to send to the user."
    )
    return_direct: bool = True

    # Injected at construction — agent never sees or reasons about these fields
    chat_id: str
    user_id: str
    platform: str  # always "telegram" for Phase 1

    def _run(self, text: str) -> str:
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
        return f"Reply queued. job_id={job.id}"

    async def _arun(self, text: str) -> str:
        return self._run(text)
