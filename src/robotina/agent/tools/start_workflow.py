"""start-workflow tool for the handle-incoming-message agent.

StartWorkflowTool creates a WorkflowRun record and all WorkflowRunStep records,
enqueues the first step, and returns the workflow_run_id string.

Used by the Robotina routing agent (Phase 7) when it identifies a multi-step
workflow intent.

Pattern: BaseTool subclass (same pattern as ReadSkillTool from Phase 4).
Session management: creates and closes its own session via SessionLocal() (D-10).

Phase 07.1: returns Command(goto=END) so the LangGraph state machine cannot
loop after the tool succeeds. Both happy and error paths terminate — we don't
want the agent to retry on errors either; the workflow is a structured retry
mechanism on its own.
"""
from __future__ import annotations

import logging
import os
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId
from langgraph.graph import END
from langgraph.types import Command

logger = logging.getLogger(__name__)


class StartWorkflowTool(BaseTool):
    """LangChain tool that initiates a multi-step workflow.

    Creates a WorkflowRun + all WorkflowRunStep records with PENDING status,
    enqueues the first step to the agent-tasks queue, and returns the
    workflow_run_id string.

    Recipient context (chat_id, user_id, platform, household_id) is injected at
    construction time by run_task() and auto-merged into shared_context as
    ``reply_context`` — the LLM never needs to know these values.

    Args (via _run):
        workflow_type: Workflow identifier (e.g. "add-recipe"). Must exist in WORKFLOW_REGISTRY.
        shared_context: Dict containing task-specific fields the workflow needs
                        (e.g. recipe_query). reply_context and household_id are
                        injected automatically — the agent does not need to provide them.

    Returns:
        Command(goto=END) carrying a ToolMessage with the workflow_run_id (or
        error string on failure). The agent graph routes to END immediately.
    """

    name: str = "start-workflow"
    description: str = (
        "Initiate a multi-step workflow. Creates a WorkflowRun and enqueues the first step.\n"
        "Args:\n"
        "  workflow_type (str): Workflow name, e.g. 'add-recipe'.\n"
        "  shared_context (dict): Task-specific fields (e.g. recipe_query). "
        "reply_context and household_id are injected automatically."
    )

    # Injected by run_task() at construction time
    chat_id: str = ""
    user_id: str = ""
    platform: str = ""
    household_id: str = ""

    def _run(
        self,
        workflow_type: str,
        shared_context: dict,
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        """Create and enqueue a workflow. Returns Command(goto=END).

        Both happy and error paths terminate — the agent must not loop on
        workflow-start failures.
        """
        from redis import Redis
        from rq import Queue

        from robotina.db import SessionLocal
        from robotina.queue import workflow_runner

        # Auto-inject reply_context and household_id from constructor fields
        # so the LLM never needs to know about chat_id/user_id/platform.
        shared_context.setdefault("reply_context", {
            "platform": self.platform,
            "chat_id": self.chat_id,
            "user_id": self.user_id,
        })
        shared_context.setdefault("household_id", self.household_id)

        household_id = shared_context.get("household_id", "")
        session = SessionLocal()
        try:
            queue = Queue(
                "agent-tasks",
                connection=Redis.from_url(
                    os.environ.get("REDIS_URL", "redis://localhost:6379")
                ),
            )
            workflow_run_id = workflow_runner.queue_workflow(
                workflow_type=workflow_type,
                shared_context=shared_context,
                household_id=household_id,
                queue=queue,
                session=session,
            )
            logger.info(
                "queue-workflow tool | workflow_type=%s run_id=%s",
                workflow_type,
                workflow_run_id,
            )
            content = f"Workflow started. workflow_run_id={workflow_run_id}"
        except Exception as exc:
            logger.error(
                "start-workflow tool | workflow_type=%s error=%s",
                workflow_type,
                exc,
            )
            content = f"Workflow start failed: {exc}"
        finally:
            session.close()

        return Command(
            update={"messages": [ToolMessage(
                content=content,
                tool_call_id=tool_call_id,
                name="start-workflow",
            )]},
            goto=END,
        )

    async def _arun(
        self,
        workflow_type: str,
        shared_context: dict,
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        return self._run(workflow_type, shared_context, tool_call_id)
