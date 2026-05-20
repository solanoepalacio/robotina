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

Phase 23 D-01 / D-02: workflow_type Literal is hard-renamed to
``Literal["add-recipe-from-query", "add-recipe-from-url"]`` (no transitional
alias). ``input`` becomes the plain union ``AddRecipeQueryInput |
AddRecipeUrlInput``; a ``@model_validator(mode="after")`` enforces the
workflow_type ↔ input pairing so LLM-emitted mismatches surface as a
ValidationError → ToolMessage(status='error') the agent retries.
"""
from __future__ import annotations

import logging
import os
from typing import Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, model_validator

from robotina.queue.task_types import (
    AddRecipeQueryInput,
    AddRecipeUrlInput,
    NonEmptyHouseholdId,
)

logger = logging.getLogger(__name__)


class StartWorkflowArgs(BaseModel):
    """Strict argument schema for StartWorkflowTool.

    Three structural guardrails enforced at args-validation time (before
    _run is called), so misuse surfaces as a ToolMessage(status='error')
    the engine reports back to the LLM (the tool is non-terminal —
    return_direct=False per D-03), not as a downstream KeyError or
    registry miss:

    1. ``workflow_type`` is a ``Literal["add-recipe-from-query",
       "add-recipe-from-url"]`` (Phase 23 D-01 hard rename — no
       transitional alias for ``"add-recipe"``). A hallucinated name
       fails here, not at WORKFLOW_REGISTRY lookup.
    2. ``input`` is a required typed union
       ``AddRecipeQueryInput | AddRecipeUrlInput``. Pydantic resolves
       the variant by shape (one carries ``value: str``, the other
       ``url: str``; mutually exclusive — no explicit discriminator
       needed). The legacy flat top-level ``recipe_query`` string field
       is gone; the WR-02 shared_context-shadowing attack surface stays
       gone.
    3. ``_enforce_pairing`` (``@model_validator(mode="after")``) raises
       ``ValueError`` if ``workflow_type`` and ``input`` shape disagree
       (Phase 23 D-22). Catches LLM-emitted mismatches at validation
       time so they become structured ToolMessages.

    ``extra='forbid'`` on the outer schema AND every inner input model
    keeps any unknown LLM-emitted field as a ValidationError.
    """

    model_config = ConfigDict(extra="forbid")

    workflow_type: Literal["add-recipe-from-query", "add-recipe-from-url"] = Field(
        description=(
            "Workflow identifier. Supported values: 'add-recipe-from-query' "
            "(free-text recipe query) and 'add-recipe-from-url' (recipe URL)."
        ),
    )
    input: AddRecipeQueryInput | AddRecipeUrlInput = Field(
        description=(
            "Typed input for the workflow. For 'add-recipe-from-query', shape is "
            "{value: <recipe query string>} — e.g. {\"value\": \"lentil soup\"}. "
            "For 'add-recipe-from-url', shape is {url: <recipe URL>} — e.g. "
            "{\"url\": \"https://example.com/recipe\"}."
        ),
    )

    @model_validator(mode="after")
    def _enforce_pairing(self) -> "StartWorkflowArgs":
        """Phase 23 D-22: workflow_type ↔ input variant must agree.

        Pydantic's union resolves the input variant by structural fit; the
        outer ``workflow_type`` Literal independently could disagree (LLM
        emits ``workflow_type='add-recipe-from-url'`` with
        ``input={value: 'x'}``). Reject the mismatch here so the LLM gets
        a clear error rather than a downstream KeyError on
        ``shared_context["recipe_url"]``.
        """
        if self.workflow_type == "add-recipe-from-query" and not isinstance(
            self.input, AddRecipeQueryInput
        ):
            raise ValueError(
                "workflow_type='add-recipe-from-query' requires input shape "
                "{value: <recipe query string>} (AddRecipeQueryInput)."
            )
        if self.workflow_type == "add-recipe-from-url" and not isinstance(
            self.input, AddRecipeUrlInput
        ):
            raise ValueError(
                "workflow_type='add-recipe-from-url' requires input shape "
                "{url: <recipe URL>} (AddRecipeUrlInput)."
            )
        return self


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
                       ``"add-recipe-from-query"`` | ``"add-recipe-from-url"``
                       at args-validation time (Phase 23 D-01 hard rename).
        input: AddRecipeQueryInput {value: str} OR AddRecipeUrlInput
               {url: str} (Phase 23 D-01 plain union). The tool unwraps
               ``input.value`` (query variant) or ``input.url`` (URL
               variant) to populate shared_context.

        The shared_context dict that downstream ``workflow_runner.queue_workflow``
        consumes is built internally from the input plus the
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
        "  workflow_type (str): Workflow name. Supported: "
        "'add-recipe-from-query' (free-text query) or "
        "'add-recipe-from-url' (recipe URL).\n"
        "  input (object): Typed input for the workflow. For "
        "'add-recipe-from-query', shape is {value: <recipe query string>}. "
        "For 'add-recipe-from-url', shape is {url: <recipe URL>}.\n"
        "reply_context and household_id are injected automatically by the "
        "runtime — do not pass them.\n"
        "Arguments are passed as JSON. Use JSON literals: null (not None or "
        "none), true/false (not True/False). Strings must use double quotes. "
        "Examples: {\"workflow_type\": \"add-recipe-from-query\", \"input\": "
        "{\"value\": \"lentil soup\"}} or "
        "{\"workflow_type\": \"add-recipe-from-url\", \"input\": "
        "{\"url\": \"https://example.com/recipe\"}}."
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

    def _run(
        self,
        workflow_type: str,
        input: AddRecipeQueryInput | AddRecipeUrlInput | dict,
    ) -> str:
        from redis import Redis
        from rq import Queue

        from robotina.db import SessionLocal
        from robotina.queue import workflow_runner

        # Phase 23 D-01 / D-02: unwrap the typed input on entry. The
        # args_schema guarantees ``input`` is one of the union variants
        # (pydantic coerces dict → model at validation time), but some
        # test paths may pass a dict directly via _run; accept both.
        # Dict → variant resolution: prefer the field name present.
        if isinstance(input, dict):
            if "value" in input:
                input = AddRecipeQueryInput.model_validate(input)
            elif "url" in input:
                input = AddRecipeUrlInput.model_validate(input)
            else:  # pragma: no cover — args_schema would already have rejected
                raise ValueError(
                    "start-workflow input dict missing both 'value' and 'url' fields"
                )

        # Build shared_context internally from the LLM-supplied input
        # plus the constructor-injected identity fields. The LLM no longer
        # supplies a free-form dict, so the WR-02 shadowing attack surface
        # (LLM-supplied household_id / reply_context) is eliminated
        # structurally — there is nothing for the LLM to overwrite.
        # Constructor injection of invocation_id (Phase 18 D-13),
        # conversation_id (Phase 17 D-03/04), household_id (Phase 16
        # NonEmptyHouseholdId) is unchanged.
        shared_context: dict = {
            "reply_context": {
                "platform": self.platform,
                "chat_id": self.chat_id,
                "user_id": self.user_id,
            },
            "household_id": self.household_id,
        }
        if isinstance(input, AddRecipeQueryInput):
            shared_context["recipe_query"] = input.value
        elif isinstance(input, AddRecipeUrlInput):
            # Phase 23 D-08: URL workflows store recipe_url in shared_context;
            # the wake-helper reads recipe_query OR recipe_url to populate the
            # WorkflowOutcomeSummary.recipe_query display field.
            shared_context["recipe_url"] = input.url

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

    async def _arun(
        self,
        workflow_type: str,
        input: AddRecipeQueryInput | AddRecipeUrlInput | dict,
    ) -> str:
        return self._run(workflow_type, input)
