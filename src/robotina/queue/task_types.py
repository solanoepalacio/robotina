"""Pydantic v2 task I/O models for all four RQ task types.

This module is the shared contract imported by:
- robotina.queue (enqueueing jobs)
- robotina.agent (agent input/output typing)
- robotina.task_runner (workflow advancement, Phase 5)

IMPORTANT:
- reply_context is NOT present in RecipeResearchInput or RecipeLoadInput.
  It lives in WorkflowRun.shared_context and is resolved by the task runner.
- All models use Pydantic v2 syntax: list[...], str | None, Literal[...]
- All models are pickle-serializable (RQ default serializer)
- When storing model output to a JSON column, use model.model_dump(mode='json')
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


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
    food_name: str        # human-readable name — resolved to foodId by recipe-load
    unit_name: str | None
    quantity: float | None
    note: str | None


class RecipeStep(BaseModel):
    body: str             # instruction text
    title: str | None     # optional step heading


class RecipeData(BaseModel):
    name: str
    description: str | None
    servings_qty: int | None
    servings_unit: str | None   # e.g. "porciones"
    prep_time: int | None       # minutes
    cook_time: int | None       # minutes
    total_time: int | None      # minutes
    source_url: str | None      # original recipe URL if found
    ingredients: list[RecipeIngredient]
    steps: list[RecipeStep]


# ---------------------------------------------------------------------------
# handle-incoming-message
# ---------------------------------------------------------------------------

class IncomingMessageInput(BaseModel):
    message_id: str               # platform-assigned ID, used for deduplication
    platform: Literal["telegram"]
    received_at: datetime         # when the gateway received the message
    chat_id: str                  # platform chat/thread identifier
    user_id: str                  # platform user identifier
    household_id: str             # populated by the gateway from env var
    text: str                     # raw message text
    history: list[Message]        # last X messages, ordered oldest to newest

    def to_user_message(self) -> str:
        return self.text


class IncomingMessageOutput(BaseModel):
    action: Literal["replied", "started_workflow"]
    queued_task_ids: list[str]    # populated when action is "replied"
    workflow_run_id: str | None   # populated when action is "started_workflow"


# ---------------------------------------------------------------------------
# recipe-research
# reply_context is NOT here — it lives in WorkflowRun.shared_context
# ---------------------------------------------------------------------------

class RecipeResearchInput(BaseModel):
    query: str            # e.g. "spaghetti carbonara"
    household_id: str

    def to_user_message(self) -> str:
        return self.query


class RecipeResearchOutput(BaseModel):
    recipe: RecipeData    # persisted to WorkflowRunStep.artifact by the task runner


# ---------------------------------------------------------------------------
# recipe-research-gather (Step 1 of recipe research pipeline)
# ---------------------------------------------------------------------------

class RecipeResearchGatherInput(BaseModel):
    query: str            # meal name, e.g. "Pasta Bolognesa"
    household_id: str

    def to_user_message(self) -> str:
        return self.query


class RecipeResearchGatherOutput(BaseModel):
    recipes: list[dict]   # list of scraped/extracted recipe dicts from web search


# ---------------------------------------------------------------------------
# recipe-research-instructions (Step 2 of recipe research pipeline)
# ---------------------------------------------------------------------------

class RecipeResearchInstructionsInput(BaseModel):
    query: str
    gathered_recipes: list[dict]  # from gather step artifact

    def to_user_message(self) -> str:
        import json
        return f"Create baseline instructions for: {self.query}\n\nGathered recipes:\n{json.dumps(self.gathered_recipes, ensure_ascii=False, indent=2)}"


class RecipeResearchInstructionsOutput(BaseModel):
    draft_name: str
    draft_description: str
    draft_instructions: list[RecipeStep]


# ---------------------------------------------------------------------------
# recipe-research-ingredients (Step 3 of recipe research pipeline)
# ---------------------------------------------------------------------------

class RecipeResearchIngredientsInput(BaseModel):
    query: str
    draft_instructions: list[RecipeStep]
    gathered_recipes: list[dict]  # for substitute lookup (D-15)
    household_id: str

    def to_user_message(self) -> str:
        import json
        instructions_text = "\n".join(f"- {s.body}" for s in self.draft_instructions)
        return f"Extract and verify ingredients for: {self.query}\n\nDraft instructions:\n{instructions_text}\n\nGathered recipes:\n{json.dumps(self.gathered_recipes, ensure_ascii=False, indent=2)}"


class RecipeResearchIngredientsOutput(BaseModel):
    ingredients: list[RecipeIngredient]


# ---------------------------------------------------------------------------
# recipe-research-metadata (Step 4 of recipe research pipeline)
# ---------------------------------------------------------------------------

class RecipeResearchMetadataInput(BaseModel):
    query: str
    draft_name: str
    draft_description: str
    draft_instructions: list[RecipeStep]
    ingredients: list[RecipeIngredient]
    gathered_recipes: list[dict]  # for metadata hints
    source_url: str | None = None

    def to_user_message(self) -> str:
        import json
        instructions_text = "\n".join(f"- {s.body}" for s in self.draft_instructions)
        ingredients_text = "\n".join(f"- {i.food_name}: {i.quantity} {i.unit_name}" for i in self.ingredients)
        return (
            f"Estimate metadata for: {self.query}\n\n"
            f"Name: {self.draft_name}\n"
            f"Description: {self.draft_description}\n\n"
            f"Instructions:\n{instructions_text}\n\n"
            f"Ingredients:\n{ingredients_text}\n\n"
            f"Gathered recipes:\n{json.dumps(self.gathered_recipes, ensure_ascii=False, indent=2)}"
        )


class RecipeResearchMetadataOutput(BaseModel):
    recipe: RecipeData    # final fully-populated RecipeData (D-19)


# ---------------------------------------------------------------------------
# recipe-load
# reply_context is NOT here — it lives in WorkflowRun.shared_context
# ---------------------------------------------------------------------------

class RecipeLoadInput(BaseModel):
    recipe: RecipeData    # resolved from prior step's artifact by the task runner
    household_id: str

    def to_user_message(self) -> str:
        import json
        return (
            "Load this recipe into the household-manager system:\n\n"
            + json.dumps(self.recipe.model_dump(mode="json"), ensure_ascii=False, indent=2)
        )


class RecipeLoadOutput(BaseModel):
    recipe_id: str
    recipe_name: str      # persisted to WorkflowRunStep.artifact by the task runner
    recipe_description: str | None = None
    recipe_slug: str = ""
    missing_ingredients: list[str] = []


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
