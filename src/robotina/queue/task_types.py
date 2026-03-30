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
# recipe-load
# reply_context is NOT here — it lives in WorkflowRun.shared_context
# ---------------------------------------------------------------------------

class RecipeLoadInput(BaseModel):
    recipe: RecipeData    # resolved from prior step's artifact by the task runner
    household_id: str

    def to_user_message(self) -> str:
        return f"Load recipe: {self.recipe.name}"


class RecipeLoadOutput(BaseModel):
    recipe_id: str
    recipe_name: str      # persisted to WorkflowRunStep.artifact by the task runner


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
