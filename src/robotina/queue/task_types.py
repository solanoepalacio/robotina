"""Pydantic v2 task I/O models for all four RQ task types.

This module is the shared contract imported by:
- robotina.queue (enqueueing jobs)
- robotina.agent (agent input/output typing)
- robotina.task_runner (workflow advancement, Phase 5)

IMPORTANT:
- reply_context lives in WorkflowRun.shared_context and is resolved by the task
  runner. For research sub-step / load inputs, it is threaded into the per-step
  Pydantic input model so the agent has the platform/chat/user identifiers
  available during its turn — but the user does NOT see it in the user-message
  body (it stays metadata).
- All models use Pydantic v2 syntax: list[...], str | None, Literal[...]
- All models are pickle-serializable (RQ default serializer)
- When storing model output to a JSON column, use model.model_dump(mode='json')

Phase 15 — accumulating-artifact contract:
- ``RecipeData`` is the single shared artifact shape across the whole
  recipe-research pipeline (gather → instructions → ingredients → metadata →
  load). Every field except ``name`` is Optional with a sensible default; each
  sub-agent receives a partial ``RecipeData`` and emits a fuller copy. The four
  ``Recipe*Output`` sentinels are kept as aliases for ``RecipeData`` so existing
  imports keep working.
- All four downstream ``Recipe*Input`` models (instructions, ingredients,
  metadata, load) collapse to ``{recipe, reply_context, household_id}``.
  ``RecipeResearchGatherInput`` keeps ``{query, reply_context, household_id}``
  because gather has no prior artifact to thread.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Phase 16 — non-empty household_id constraint (REQ-HID-2)
# ---------------------------------------------------------------------------
# Centralized constraint applied to every task-input model that carries a
# household_id. ``min_length=1`` rejects the empty string; ``pattern=r"\S"``
# rejects strings that are non-empty but contain only whitespace. The two
# together close both branches of the silent-empty-default bug fixed in
# Phase 16 (see .planning/phases/16-*/16-RESEARCH.md Pattern 5).
#
# Future ambient-context refactor (backlog Phase 999.1) may lift household_id
# out of per-task models entirely; until then this alias is the single source
# of truth for the constraint.

NonEmptyHouseholdId = Annotated[
    str,
    Field(
        min_length=1,
        # Phase 16 WR-01 / IN-02: anchor both ends so leading/trailing whitespace
        # is also rejected. The prior pattern (r"\S") only required ONE
        # non-whitespace char anywhere, which let " hh-1 " through and caused
        # the boot guard (which strips) to disagree with the handler (which
        # does not strip) — silently persisting padded ids to the DB. The new
        # pattern accepts either a single non-whitespace char OR a string
        # whose first and last chars are non-whitespace.
        pattern=r"^\S(.*\S)?$",
        description=(
            "Household identifier. Must be a non-empty string with no leading "
            "or trailing whitespace. Empty/whitespace-only/padded values are "
            "rejected at model construction (Phase 16, REQ-HID-2 + WR-01)."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Shared models
# ---------------------------------------------------------------------------

class Message(BaseModel):
    message_id: str
    role: Literal["user", "assistant"]
    text: str
    sent_at: datetime


class ReplyContext(BaseModel):
    platform: Literal["telegram"]
    chat_id: str
    user_id: str


class RecipeIngredient(BaseModel):
    food_name: str                     # human-readable Spanish name
    unit_name: str | None = None
    quantity: float | None = None
    note: str | None = None
    # Phase 15: resolved catalog ids (populated by ingredients step's
    # validate-foods / validate-units tools; recipe-load reads these).
    food_id: str | None = None
    unit_id: str | None = None


class RecipeStep(BaseModel):
    body: str             # instruction text
    title: str | None = None     # optional step heading


class RecipeData(BaseModel):
    """Shared accumulating artifact across the recipe-research pipeline.

    Only ``name`` is required (must be present once the artifact reaches
    recipe-load). Every other field is Optional / defaulted so that each
    sub-agent can emit a partially-populated copy and the next sub-agent can
    add or refine its owned fields without losing upstream data.

    Field ownership (per pipeline step):
    - gather:        ``gathered_sources``
    - instructions:  ``name``, ``description``, ``steps``
    - ingredients:   ``ingredients``, ``missing_ingredients``
    - metadata:      ``servings_qty``, ``servings_unit``, ``prep_time``,
                     ``cook_time``, ``total_time``, ``source_url``; clears
                     ``gathered_sources`` to ``None`` on emit.
    Other fields must be preserved verbatim from the incoming artifact.
    """

    name: str
    description: str | None = None
    servings_qty: int | None = None
    servings_unit: str | None = None   # e.g. "porciones"
    prep_time: int | None = None       # minutes
    cook_time: int | None = None       # minutes
    total_time: int | None = None      # minutes
    source_url: str | None = None      # original recipe URL if found
    ingredients: list[RecipeIngredient] = []
    steps: list[RecipeStep] = []
    # Phase 15 additions:
    gathered_sources: list[dict] | None = None
    missing_ingredients: list[str] = []


# ---------------------------------------------------------------------------
# handle-incoming-message
# ---------------------------------------------------------------------------

class IncomingMessageInput(BaseModel):
    message_id: str               # platform-assigned ID, used for deduplication
    platform: Literal["telegram"]
    received_at: datetime         # when the gateway received the message
    chat_id: str                  # platform chat/thread identifier
    user_id: str                  # platform user identifier
    household_id: NonEmptyHouseholdId  # populated by the gateway from env var
    text: str                     # raw message text
    history: list[Message]        # last X messages, ordered oldest to newest

    def to_user_message(self) -> str:
        return self.text


class IncomingMessageOutput(BaseModel):
    action: Literal["replied", "started_workflow"]
    queued_task_ids: list[str]    # populated when action is "replied"
    workflow_run_id: str | None   # populated when action is "started_workflow"


# ---------------------------------------------------------------------------
# recipe-research (legacy single-shot task — retained for back-compat)
# reply_context is NOT here — it lives in WorkflowRun.shared_context
# ---------------------------------------------------------------------------

class RecipeResearchInput(BaseModel):
    query: str            # e.g. "spaghetti carbonara"
    household_id: NonEmptyHouseholdId

    def to_user_message(self) -> str:
        return self.query


class RecipeResearchOutput(BaseModel):
    recipe: RecipeData    # persisted to WorkflowRunStep.artifact by the task runner


# ---------------------------------------------------------------------------
# recipe-research pipeline — Phase 15 accumulating-artifact shape
#
# Every downstream sub-agent receives the prior step's RecipeData snapshot
# verbatim and emits a fuller copy. Only the gather step has no prior
# artifact, so it keeps the original {query, reply_context, household_id}
# shape.
# ---------------------------------------------------------------------------

class RecipeResearchGatherInput(BaseModel):
    query: str
    reply_context: ReplyContext
    household_id: NonEmptyHouseholdId

    def to_user_message(self) -> str:
        return self.query


class RecipeResearchInstructionsInput(BaseModel):
    recipe: RecipeData
    reply_context: ReplyContext
    household_id: NonEmptyHouseholdId

    def to_user_message(self) -> str:
        import json
        return (
            "Continue the recipe-research pipeline (instructions step). "
            "Preserve every field of the incoming RecipeData; only add/refine "
            "`steps`, `description`, and `name`.\n\n"
            + json.dumps(self.recipe.model_dump(mode="json"), ensure_ascii=False, indent=2)
        )


class RecipeResearchIngredientsInput(BaseModel):
    recipe: RecipeData
    reply_context: ReplyContext
    household_id: NonEmptyHouseholdId

    def to_user_message(self) -> str:
        import json
        return (
            "Continue the recipe-research pipeline (ingredients step). "
            "Preserve every field of the incoming RecipeData; resolve "
            "ingredients via validate-foods / validate-units.\n\n"
            + json.dumps(self.recipe.model_dump(mode="json"), ensure_ascii=False, indent=2)
        )


class RecipeResearchMetadataInput(BaseModel):
    recipe: RecipeData
    reply_context: ReplyContext
    household_id: NonEmptyHouseholdId

    def to_user_message(self) -> str:
        import json
        return (
            "Continue the recipe-research pipeline (metadata step). "
            "Preserve every field of the incoming RecipeData; only add/refine "
            "servings / times / source_url. Clear `gathered_sources` to null.\n\n"
            + json.dumps(self.recipe.model_dump(mode="json"), ensure_ascii=False, indent=2)
        )


# Sentinel aliases — every sub-agent's response_format target IS RecipeData.
# Kept as aliases so existing imports (agents.py, tests) keep working.
RecipeResearchGatherOutput = RecipeData
RecipeResearchInstructionsOutput = RecipeData
RecipeResearchIngredientsOutput = RecipeData
RecipeResearchMetadataOutput = RecipeData


# ---------------------------------------------------------------------------
# recipe-load
# ---------------------------------------------------------------------------

class RecipeLoadInput(BaseModel):
    recipe: RecipeData    # resolved from prior step's artifact by the task runner
    reply_context: ReplyContext
    household_id: NonEmptyHouseholdId

    def to_user_message(self) -> str:
        import json
        return (
            "Load this recipe into household-manager:\n\n"
            + json.dumps(self.recipe.model_dump(mode="json"), ensure_ascii=False, indent=2)
        )


class RecipeLoadOutput(BaseModel):
    recipe_id: str
    recipe_name: str      # persisted to WorkflowRunStep.artifact by the task runner
    recipe_description: str | None = None
    recipe_slug: str = ""


# ---------------------------------------------------------------------------
# send-notification
# ---------------------------------------------------------------------------

class SendNotificationInput(BaseModel):
    platform: Literal["telegram"]
    chat_id: str
    user_id: str
    text: str             # pre-written text; agent reformats for Telegram, does not compose

    def to_user_message(self) -> str:
        return f"""Format and send the following message:
{self.text}"""


class SendNotificationOutput(BaseModel):
    message_id: str       # platform-assigned ID


# ---------------------------------------------------------------------------
# acknowledge-add-recipe (Phase 07.1)
# ---------------------------------------------------------------------------

class AcknowledgeAddRecipeInput(BaseModel):
    """Input for the per-workflow ack agent that runs as add-recipe step 1.

    The agent composes a brief Spanish acknowledgment and calls `queue` to
    deliver it. Recipient context flows through `reply_context` (already
    auto-injected by StartWorkflowTool into shared_context).
    """
    recipe_query: str
    reply_context: dict   # {platform, chat_id, user_id}

    @property
    def chat_id(self) -> str:
        return self.reply_context["chat_id"]

    @property
    def user_id(self) -> str:
        return self.reply_context["user_id"]

    @property
    def platform(self) -> str:
        return self.reply_context["platform"]

    def to_user_message(self) -> str:
        return (
            f"User is asking to add a recipe: \"{self.recipe_query}\". "
            "Compose a brief, friendly acknowledgment in Spanish that you will "
            "search for the recipe and that data will be updated directly in the application."
        )


# ---------------------------------------------------------------------------
# Phase 18 / ARCH-04 — AddRecipeOutcome
# ---------------------------------------------------------------------------
# Per-workflow outcome summary written by the deterministic ``finalize-outcome``
# step in Phase 20. Phase 18 defines the shape; no code writes it yet. Replaces
# the Phase-17 ``WorkflowOutcome`` placeholder (D-18 — no envelope wrapper in
# v1.1, since ``add-recipe`` is the only workflow type; URL ingestion in
# Phase 23 reuses this shape).
#
# Target serialized size: < ~300 bytes per workflow (ARCH-04 / DASH-12).


class FinalizeOutcomeInput(BaseModel):
    """Input for the deterministic ``finalize-outcome`` step (Phase 20 / D-03).

    Populated by the workflow's ``build_input`` lambda from accumulated
    artifacts. Carries only what the deterministic composer needs to build an
    ``AddRecipeOutcome``: the metadata snapshot (for any future fields), the
    load artifact (for recipe_id / recipe_name / recipe_slug), and an optional
    failure_reason for future Phase 21 failure-path invocations.
    """

    model_config = ConfigDict(extra="forbid")

    metadata: dict | None = None
    load: dict | None = None
    failure_reason: str | None = None

    def to_user_message(self) -> str:  # pragma: no cover — agent-less branch never invokes this
        return ""


class AddRecipeOutcome(BaseModel):
    """Per-workflow outcome summary for the ``add-recipe`` workflow type.

    Phase 20's ``finalize-outcome`` deterministic step is the single producer.
    Optional fields encode the success/failure variant at the producer-contract
    level (not via a discriminated union — Pydantic's ``Field(discriminator=...)``
    adds verbose construction friction for a 2-variant shape; if the
    producer-side contract ever gets violated downstream, add a
    ``model_validator`` then).
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "failure"]
    recipe_id: str | None = None        # success only
    recipe_name: str | None = None      # success only
    recipe_slug: str | None = None      # success only
    failure_reason: str | None = None   # failure only
    image_present: bool = False         # always False in v1.1 until Phase 24 lands recipe-image
