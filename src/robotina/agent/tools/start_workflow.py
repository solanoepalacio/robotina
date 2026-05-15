"""start-workflow tool for the handle-incoming-message agent.

StartWorkflowTool creates a WorkflowRun record and all WorkflowRunStep records,
enqueues the first step, and returns the workflow_run_id string.

Used by the Robotina routing agent (Phase 7) when it identifies a multi-step
workflow intent.

Pattern: BaseTool subclass (same pattern as ReadSkillTool from Phase 4).
Session management: creates and closes its own session via SessionLocal() (D-10).

Phase 07.1: ``return_direct=True`` makes this a TERMINAL tool — the
``langchain.agents.create_agent`` graph terminates immediately after the tool
runs (both happy and error paths). This is engine-enforced termination, not a
prompt-level request. (Note: returning ``Command(goto=END)`` from a tool does
NOT short-circuit the prebuilt graph — verified empirically for both the
legacy prebuilt ReAct-agent path and the LangChain 1.x ``create_agent`` factory
— hence this ``return_direct=True`` approach.)
"""
from __future__ import annotations

import logging
import os

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from robotina.queue.task_types import NonEmptyHouseholdId

logger = logging.getLogger(__name__)


class StartWorkflowArgs(BaseModel):
    """Strict argument schema for StartWorkflowTool.

    ``extra='forbid'`` makes any unknown LLM-emitted field raise ``ValidationError``
    at ``tool.invoke()`` time, which the langgraph ``ToolNode`` converts into a
    ``ToolMessage(status='error')`` the agent sees on its next turn. See
    ``HouseholdManagerApiArgs`` docstring for the full rationale.
    """

    model_config = ConfigDict(extra="forbid")

    workflow_type: str = Field(
        description="Workflow identifier, e.g. 'add-recipe'.",
    )
    shared_context: dict = Field(
        description=(
            "Task-specific fields the workflow needs (e.g. recipe_query). "
            "reply_context and household_id are injected automatically."
        ),
    )


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
        Confirmation string with the workflow_run_id (or error string on
        failure). ``return_direct=True`` causes the LangGraph agent to
        terminate immediately after — no further model invocation. Both happy
        and error paths terminate; the agent must not loop on workflow-start
        failures.
    """

    name: str = "start-workflow"
    description: str = (
        "Initiate a multi-step workflow. Creates a WorkflowRun and enqueues the first step.\n"
        "Args:\n"
        "  workflow_type (str): Workflow name, e.g. 'add-recipe'.\n"
        "  shared_context (dict): Task-specific fields (e.g. recipe_query). "
        "reply_context and household_id are injected automatically.\n"
        "Arguments are passed as JSON. Use JSON literals: null (not None or none), "
        "true/false (not True/False). Strings must use double quotes. "
        "Example: {\"recipe_query\": \"lentil soup\"}, not {'recipe_query': 'lentil soup'}."
    )
    return_direct: bool = True

    # Strict input schema: rejects unknown LLM-emitted fields with ValidationError
    # rather than letting them flow into _run() as kwargs. See StartWorkflowArgs docstring.
    args_schema: type[BaseModel] = StartWorkflowArgs

    # Injected by run_task() at construction time
    # Phase 16 (REQ-HID-3 / RESEARCH Pitfall 5): household_id has NO default —
    # caller MUST pass a non-empty value. NonEmptyHouseholdId rejects '' and
    # whitespace at pydantic validation. chat_id / user_id / platform defaults
    # are intentionally LEFT as '' — out of scope for Phase 16.
    chat_id: str = ""
    user_id: str = ""
    platform: str = ""
    household_id: NonEmptyHouseholdId

    def _run(self, workflow_type: str, shared_context: dict) -> str:
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

        # Phase 16 (REQ-HID-3 / RESEARCH Pitfall 4): bracket form removes the silent
        # "" mask. Line above injects self.household_id via setdefault, so the
        # key is always present unless an explicit empty was passed in shared_context
        # — that case falls through to queue_workflow's raise (plan 16-04).
        household_id = shared_context["household_id"]
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
            return f"Workflow started. workflow_run_id={workflow_run_id}"
        except Exception as exc:
            logger.error(
                "start-workflow tool | workflow_type=%s error=%s",
                workflow_type,
                exc,
            )
            return f"Workflow start failed: {exc}"
        finally:
            session.close()

    async def _arun(self, workflow_type: str, shared_context: dict) -> str:
        return self._run(workflow_type, shared_context)
