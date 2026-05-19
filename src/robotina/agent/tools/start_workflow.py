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
from typing import Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from robotina.queue.task_types import NonEmptyHouseholdId

logger = logging.getLogger(__name__)


class StartWorkflowArgs(BaseModel):
    """Strict argument schema for StartWorkflowTool.

    Two structural guardrails enforced at args-validation time (before
    _run is called), so misuse surfaces as a ToolMessage(status='error')
    the engine terminates on (return_direct=True), not as a downstream
    KeyError or registry miss:

    1. workflow_type is a Literal — only 'add-recipe' validates. A
       hallucinated name fails here, not at WORKFLOW_REGISTRY lookup.
    2. recipe_query is a required top-level string. The old
       shared_context dict surface — which let the LLM (a) omit
       recipe_query entirely and (b) attempt to shadow the trusted
       household_id / reply_context via WR-02 — is gone.

    ``extra='forbid'`` keeps any unknown LLM-emitted field at the top
    level as a ValidationError (e.g. an LLM cannot now inject
    household_id at the top level either).
    """

    model_config = ConfigDict(extra="forbid")

    workflow_type: Literal["add-recipe"] = Field(
        description=(
            "Workflow identifier. Currently only 'add-recipe' is supported."
        ),
    )
    recipe_query: str = Field(
        description=(
            "User's recipe request in natural language (e.g. 'lentil soup', "
            "'carbonara'). Forwarded to the add-recipe workflow."
        ),
    )


class StartWorkflowTool(BaseTool):
    """LangChain tool that initiates a multi-step workflow.

    Creates a WorkflowRun + all WorkflowRunStep records with PENDING status,
    enqueues the first step to the agent-tasks queue, and returns the
    workflow_run_id string.

    Recipient context (chat_id, user_id, platform, household_id) is injected at
    construction time by run_task() and merged into the internally-built
    shared_context dict as ``reply_context`` and ``household_id`` — the LLM
    never supplies these values and has no schema surface to attempt to.

    Args (via _run):
        workflow_type: Workflow identifier. Constrained to the Literal
                       ``"add-recipe"`` at args-validation time.
        recipe_query: User's recipe request in natural language. Required
                      top-level string; the old ``shared_context`` dict
                      surface is gone.

        The shared_context dict that downstream ``workflow_runner.queue_workflow``
        consumes is built internally from ``recipe_query`` plus the
        constructor-injected identity fields (chat_id/user_id/platform/
        household_id). The agent never sees or supplies it.

    Returns:
        Confirmation string with the workflow_run_id (or error string on
        failure). ``return_direct=True`` causes the LangGraph agent to
        terminate immediately after — no further model invocation. Both happy
        and error paths terminate; the agent must not loop on workflow-start
        failures.
    """

    name: str = "start-workflow"
    description: str = (
        "Initiate a multi-step workflow. Creates a WorkflowRun and enqueues "
        "the first step.\n"
        "Args:\n"
        "  workflow_type (str): Workflow name. Only 'add-recipe' is supported.\n"
        "  recipe_query (str): User's recipe request in natural language "
        "(e.g. 'lentil soup').\n"
        "reply_context and household_id are injected automatically by the "
        "runtime — do not pass them.\n"
        "Arguments are passed as JSON. Use JSON literals: null (not None or "
        "none), true/false (not True/False). Strings must use double quotes. "
        "Example: {\"workflow_type\": \"add-recipe\", \"recipe_query\": "
        "\"lentil soup\"}."
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
    # Phase 17 (ARCH-01 / D-03): conversation_id is constructor-injected by
    # run_task() from the Conversation row resolved via
    # session.query(Conversation).filter_by(platform=..., chat_id=...).one().
    # Plain ``str`` (not an Annotated alias) — the LLM never supplies this
    # field (it is not in args_schema), so the LLM-shadowing attack surface
    # that motivated NonEmptyHouseholdId does not exist here. FK NOT NULL on
    # WorkflowRun.conversation_id + .one() raise upstream cover the invariant.
    conversation_id: str

    def _run(self, workflow_type: str, recipe_query: str) -> str:
        from redis import Redis
        from rq import Queue

        from robotina.db import SessionLocal
        from robotina.queue import workflow_runner

        # Build shared_context internally from the LLM-supplied recipe_query
        # plus the constructor-injected identity fields. The LLM no longer
        # supplies a free-form dict, so the WR-02 shadowing attack surface
        # (LLM-supplied household_id / reply_context) is eliminated
        # structurally — there is nothing for the LLM to overwrite.
        shared_context: dict = {
            "recipe_query": recipe_query,
            "reply_context": {
                "platform": self.platform,
                "chat_id": self.chat_id,
                "user_id": self.user_id,
            },
            "household_id": self.household_id,
        }

        # Use the constructor value directly — avoid the dict round-trip so
        # a future refactor that reorders the build above doesn't silently
        # re-introduce an LLM-controlled path.
        household_id = self.household_id
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
                conversation_id=self.conversation_id,
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

    async def _arun(self, workflow_type: str, recipe_query: str) -> str:
        return self._run(workflow_type, recipe_query)
