"""Unit tests for Pydantic task I/O models (QUEUE-03).

No Docker required — all tests are pure Python.
Run: uv run pytest tests/test_task_types.py -x -q
"""
import pickle
from datetime import datetime, timezone

import pytest


def _make_recipe_data():
    from robotina.queue.task_types import RecipeData, RecipeIngredient, RecipeStep
    return RecipeData(
        name="Carbonara",
        description="Classic Italian pasta",
        servings_qty=4,
        servings_unit="porciones",
        prep_time=10,
        cook_time=20,
        total_time=30,
        source_url="https://example.com/carbonara",
        ingredients=[
            RecipeIngredient(food_name="Pasta", unit_name="gramo", quantity=400.0, note=None),
            RecipeIngredient(food_name="Huevo", unit_name=None, quantity=4.0, note="yolk only"),
        ],
        steps=[
            RecipeStep(body="Boil pasta", title="Step 1"),
            RecipeStep(body="Mix eggs and cheese", title=None),
        ],
    )


def test_all_models_importable():
    """All 13 model classes must import without error."""
    from robotina.queue.task_types import (
        Message, ReplyContext, RecipeIngredient, RecipeStep, RecipeData,
        IncomingMessageInput, IncomingMessageOutput,
        RecipeResearchInput, RecipeResearchOutput,
        RecipeLoadInput, RecipeLoadOutput,
        SendNotificationInput, SendNotificationOutput,
    )
    from pydantic import BaseModel
    for cls in [
        Message, ReplyContext, RecipeIngredient, RecipeStep, RecipeData,
        IncomingMessageInput, IncomingMessageOutput,
        RecipeResearchInput, RecipeResearchOutput,
        RecipeLoadInput, RecipeLoadOutput,
        SendNotificationInput, SendNotificationOutput,
    ]:
        assert issubclass(cls, BaseModel), f"{cls.__name__} is not a Pydantic BaseModel"


def test_incoming_message_input_has_history_field():
    """IncomingMessageInput must have a history: list[Message] field."""
    from robotina.queue.task_types import IncomingMessageInput, Message
    hints = IncomingMessageInput.model_fields
    assert "history" in hints, "IncomingMessageInput missing 'history' field"


def test_recipe_research_input_has_no_reply_context():
    """RecipeResearchInput must NOT have a reply_context field (it lives in WorkflowRun.shared_context)."""
    from robotina.queue.task_types import RecipeResearchInput
    assert "reply_context" not in RecipeResearchInput.model_fields, (
        "reply_context must NOT be in RecipeResearchInput — it lives in WorkflowRun.shared_context"
    )


def test_recipe_load_input_has_no_reply_context():
    """RecipeLoadInput must NOT have a reply_context field."""
    from robotina.queue.task_types import RecipeLoadInput
    assert "reply_context" not in RecipeLoadInput.model_fields, (
        "reply_context must NOT be in RecipeLoadInput — it lives in WorkflowRun.shared_context"
    )


def test_incoming_message_input_pickle_round_trip():
    """IncomingMessageInput must survive pickle round-trip (RQ serialization)."""
    from robotina.queue.task_types import IncomingMessageInput, Message
    now = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)
    model = IncomingMessageInput(
        message_id="msg-001",
        platform="telegram",
        received_at=now,
        chat_id="chat-123",
        user_id="user-456",
        household_id="hh-789",
        text="Hello Robotina",
        history=[Message(message_id="msg-000", role="user", text="Hi", sent_at=now)],
    )
    restored = pickle.loads(pickle.dumps(model))
    assert restored == model


def test_recipe_research_input_pickle_round_trip():
    """RecipeResearchInput must survive pickle round-trip."""
    from robotina.queue.task_types import RecipeResearchInput
    model = RecipeResearchInput(query="carbonara", household_id="hh-789")
    restored = pickle.loads(pickle.dumps(model))
    assert restored == model


def test_recipe_load_input_pickle_round_trip():
    """RecipeLoadInput with nested RecipeData must survive pickle round-trip."""
    from robotina.queue.task_types import RecipeLoadInput
    model = RecipeLoadInput(recipe=_make_recipe_data(), household_id="hh-789")
    restored = pickle.loads(pickle.dumps(model))
    assert restored == model


def test_send_notification_input_pickle_round_trip():
    """SendNotificationInput must survive pickle round-trip."""
    from robotina.queue.task_types import SendNotificationInput
    model = SendNotificationInput(
        platform="telegram", chat_id="chat-123", user_id="user-456",
        text="Recipe added: Carbonara"
    )
    restored = pickle.loads(pickle.dumps(model))
    assert restored == model


def test_recipe_data_empty_lists_pickle_round_trip():
    """RecipeData with empty ingredient/step lists must survive pickle round-trip."""
    from robotina.queue.task_types import RecipeData
    model = RecipeData(
        name="Empty Recipe",
        description=None, servings_qty=None, servings_unit=None,
        prep_time=None, cook_time=None, total_time=None, source_url=None,
        ingredients=[], steps=[],
    )
    restored = pickle.loads(pickle.dumps(model))
    assert restored == model
