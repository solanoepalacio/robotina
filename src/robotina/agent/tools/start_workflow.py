"""start-workflow tool for the handle-incoming-message agent.

StartWorkflowTool creates a WorkflowRun record and all WorkflowRunStep records,
enqueues the first step, and returns the workflow_run_id string.

Used by the Robotina routing agent (Phase 7) when it identifies a multi-step
workflow intent.

Pattern: BaseTool subclass (same pattern as ReadSkillTool from Phase 4).
Session management: creates and closes its own session via SessionLocal() (D-10).

D-03 (Phase 21 tool-surface flip): ``return_direct=False`` — the tool is
NON-TERMINAL. Robotina's loop continues after each call so the LLM can chain
multiple start-workflow calls in a single turn and then call ``terminate()``.
The engine-enforced termination point moves to TerminateTool (separate tool,
terminal flag set). The previous Phase 07.1 terminal-tool decision is
superseded for this tool.
"""
from __future__ import annotations

import logging
import os
from typing import Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from robotina.queue.task_types import AddRecipeQueryInput, NonEmptyHouseholdId

logger = logging.getLogger(__name__)


class StartWorkflowArgs(BaseModel):
    """Strict argument schema for StartWorkflowTool.

    Two structural guardrails enforced at args-validation time (before
    _run is called), so misuse surfaces as a ToolMessage(status='error')
    the engine reports back to the LLM (the tool is non-terminal —
    return_direct=False per D-03), not as a downstream KeyError or
    registry miss:

    1. workflow_type is a Literal — only 'add-recipe' validates. A
       hallucinated name fails here, not at WORKFLOW_REGISTRY lookup.
       (A future plan extends this to a discriminated union with the
       URL ingestion variant.)
    2. input is a required typed AddRecipeQueryInput {value: str}. The
       old flat top-level recipe_query string field is gone; the old shared_context
       dict surface — which let the LLM (a) omit recipe_query entirely
       and (b) attempt to shadow the trusted household_id /
       reply_context via WR-02 — was already gone, and stays gone.

    ``extra='forbid'`` on both the outer schema AND the inner
    AddRecipeQueryInput keeps any unknown LLM-emitted field as a
    ValidationError at validation time.
    """

    model_config = ConfigDict(extra="forbid")

    workflow_type: Literal["add-recipe"] = Field(
        description=(
            "Workflow identifier. Currently only 'add-recipe' is supported."
        ),
    )
    input: AddRecipeQueryInput = Field(
        description=(
            "Typed input for the workflow. For 'add-recipe', shape is "
            "{value: <recipe query string>} — e.g. {\"value\": \"lentil soup\"}."
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
        input: AddRecipeQueryInput {value: str} (D-03). The tool unwraps
               ``input.value`` to obtain the recipe query. The old flat
               top-level recipe_query string arg is gone.

        The shared_context dict that downstream ``workflow_runner.queue_workflow``
        consumes is built internally from ``input.value`` plus the
        constructor-injected identity fields (chat_id/user_id/platform/
        household_id). The agent never sees or supplies it.

    Returns:
        Confirmation string with the workflow_run_id (or error string on
        failure). D-03: ``return_direct=False`` — the tool is non-terminal;
        Robotina's loop continues after the call. The LLM is expected to
        call ``terminate()`` (separate tool) to end the turn.
    """

    name: str = "start-workflow"
    description: str = (
        "Inicia un flujo de tipo workflow_type con el input dado. "
        "Podes llamarme varias veces en un mismo turno para iniciar N flujos. "
        "No termino el turno — usa terminate() cuando hayas terminado.\n"
        "Args:\n"
        "  workflow_type (str): Workflow name. Only 'add-recipe' is supported.\n"
        "  input (object): Typed input for the workflow. For 'add-recipe', "
        "shape is {value: <recipe query string>}.\n"
        "reply_context and household_id are injected automatically by the "
        "runtime — do not pass them.\n"
        "Arguments are passed as JSON. Use JSON literals: null (not None or "
        "none), true/false (not True/False). Strings must use double quotes. "
        "Example: {\"workflow_type\": \"add-recipe\", \"input\": "
        "{\"value\": \"lentil soup\"}}."
    )
    # D-03: tool is non-terminal — Robotina's loop continues after each call
    # so the LLM can chain start-workflow → start-workflow → terminate().
    # Engine-enforced termination moves to TerminateTool (which sets the flag).
    return_direct: bool = False

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
    # Phase 18 (ARCH-02 / D-13): invocation_id is constructor-injected by
    # run_task() from ``job.meta["invocation_id"]`` (bracket read — KeyError
    # if missing is an invariant violation; the gateway boot-time enqueue
    # contract is the guarantee). No Pydantic alias — same rationale as
    # ``conversation_id`` above: the LLM never supplies this field
    # (it is not in args_schema), so the LLM-shadowing attack surface that
    # motivated NonEmptyHouseholdId does not exist here. FK NULLABLE on
    # WorkflowRun.triggered_by_invocation_id + bracket-key meta read upstream
    # cover the invariant. CONSTRUCTOR-INJECTED, not mutable state — when
    # Phase 21 lands multi-call StartWorkflowTool, this prevents the
    # concurrent-tool-call race that Pitfall 5 calls out.
    invocation_id: str

    def _run(self, workflow_type: str, input: AddRecipeQueryInput) -> str:
        from redis import Redis
        from rq import Queue

        from robotina.db import SessionLocal
        from robotina.queue import workflow_runner

        # D-03: unwrap the typed input on entry. The args_schema guarantees
        # `input` is an AddRecipeQueryInput (pydantic coerces dict → model
        # at validation time), but some test paths may pass a dict directly
        # via _run; accept both for robustness.
        if isinstance(input, dict):
            input = AddRecipeQueryInput.model_validate(input)
        recipe_query = input.value

        # Build shared_context internally from the LLM-supplied recipe_query
        # plus the constructor-injected identity fields. The LLM no longer
        # supplies a free-form dict, so the WR-02 shadowing attack surface
        # (LLM-supplied household_id / reply_context) is eliminated
        # structurally — there is nothing for the LLM to overwrite.
        # Constructor injection of invocation_id (Phase 18 D-13),
        # conversation_id (Phase 17 D-03/04), household_id (Phase 16
        # NonEmptyHouseholdId) is unchanged by D-03.
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
                triggered_by_invocation_id=self.invocation_id,
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

    async def _arun(self, workflow_type: str, input: AddRecipeQueryInput) -> str:
        return self._run(workflow_type, input)
