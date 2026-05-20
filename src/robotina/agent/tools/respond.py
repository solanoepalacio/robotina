"""respond tool for the Robotina routing agent.

Per D-01: non-terminal Spanish-replier; enqueues send-notification at_front=True
(mirrors the retired QueueTool). Replaces QueueTool — RespondTool is the new
agent surface for direct replies.

Non-terminal (``return_direct=False``) so Robotina can chain calls within the
same turn, e.g. ``respond("Buscando la receta...") → start-workflow(...) →
terminate()``. The Spanish reply lands on the queue first (``at_front=True``)
so the user sees it before workflow steps run.

Recipient context (chat_id, user_id, platform, household_id) is injected at
construction inside run_task(); the agent only supplies ``text``.
"""
from __future__ import annotations

import logging
import os

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field
from redis import Redis
from rq import Queue

from robotina.queue.task_types import NonEmptyHouseholdId

logger = logging.getLogger(__name__)


class RespondArgs(BaseModel):
    """Strict argument schema for RespondTool — only ``text`` is exposed to
    the LLM. ``extra='forbid'`` rejects any unknown field the model might
    hallucinate (e.g. attempts to pass chat_id / household_id)."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(
        description="Mensaje en español para enviar al usuario.",
    )


class RespondTool(BaseTool):
    """Non-terminal tool that enqueues a Spanish reply via send-notification.

    Mirrors QueueTool's enqueue contract exactly:
      - target function:  robotina.queue.jobs.run_task
      - payload:          SendNotificationInput(platform, chat_id, user_id, text)
      - at_front:         True (notification replies take priority — load-bearing
                          per feedback_queue_at_front)
      - result_ttl:       -1
      - failure_ttl:      -1
      - meta:             {"task_type": "send-notification"}

    Difference vs QueueTool: ``return_direct=False`` (non-terminal). Robotina
    can call respond → start-workflow → terminate in the same turn.
    """

    name: str = "respond"
    description: str = (
        "Envía un mensaje al usuario en español. No termina el turno: "
        "podés llamar a otras herramientas después (start-workflow, terminate). "
        "Args: text (str) — el mensaje en español para el usuario."
    )
    return_direct: bool = False

    args_schema: type[BaseModel] = RespondArgs

    # Injected at construction by run_task — agent never sees these fields
    chat_id: str
    user_id: str
    platform: str  # always "telegram" for Phase 1
    household_id: NonEmptyHouseholdId

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
        logger.info("respond tool | enqueued send-notification | job_id=%s", job.id)
        return f"Reply queued. job_id={job.id}"

    async def _arun(self, text: str) -> str:
        return self._run(text)
