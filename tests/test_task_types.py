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


# ---------------------------------------------------------------------------
# recipe-research sub-task I/O model tests (RRECIPE-04)
# ---------------------------------------------------------------------------


def test_recipe_research_gather_input_round_trip():
    """RRECIPE-04: RecipeResearchGatherInput is pickle-serializable."""
    from robotina.queue.task_types import RecipeResearchGatherInput
    m = RecipeResearchGatherInput(query="Pasta Bolognesa", household_id="h1")
    assert m.to_user_message() == "Pasta Bolognesa"
    assert pickle.loads(pickle.dumps(m)) == m


def test_recipe_research_gather_output_accepts_list_of_dicts():
    """RRECIPE-04: RecipeResearchGatherOutput stores list[dict]."""
    from robotina.queue.task_types import RecipeResearchGatherOutput
    m = RecipeResearchGatherOutput(recipes=[{"title": "test", "url": "http://x.com"}])
    assert len(m.recipes) == 1


def test_recipe_research_instructions_input_round_trip():
    from robotina.queue.task_types import RecipeResearchInstructionsInput
    m = RecipeResearchInstructionsInput(query="Pasta", gathered_recipes=[{"title": "t"}])
    assert "Pasta" in m.to_user_message()
    assert pickle.loads(pickle.dumps(m)) == m


def test_recipe_research_instructions_output_has_draft_fields():
    from robotina.queue.task_types import RecipeResearchInstructionsOutput, RecipeStep
    m = RecipeResearchInstructionsOutput(
        draft_name="Pasta Bolognesa",
        draft_description="Classic pasta dish",
        draft_instructions=[RecipeStep(body="Cook pasta", title=None)],
    )
    assert m.draft_name == "Pasta Bolognesa"
    assert len(m.draft_instructions) == 1


def test_recipe_research_ingredients_input_round_trip():
    from robotina.queue.task_types import RecipeResearchIngredientsInput, RecipeStep
    m = RecipeResearchIngredientsInput(
        query="Pasta",
        draft_instructions=[RecipeStep(body="Cook", title=None)],
        gathered_recipes=[],
        household_id="h1",
    )
    assert "Pasta" in m.to_user_message()
    assert pickle.loads(pickle.dumps(m)) == m


def test_recipe_research_ingredients_output_has_ingredients():
    from robotina.queue.task_types import RecipeResearchIngredientsOutput, RecipeIngredient
    m = RecipeResearchIngredientsOutput(
        ingredients=[RecipeIngredient(food_name="cebolla", unit_name="unidad", quantity=1.0, note=None)]
    )
    assert len(m.ingredients) == 1
    assert m.ingredients[0].food_name == "cebolla"


def test_recipe_research_metadata_input_round_trip():
    from robotina.queue.task_types import RecipeResearchMetadataInput, RecipeStep, RecipeIngredient
    m = RecipeResearchMetadataInput(
        query="Pasta",
        draft_name="Pasta Bolognesa",
        draft_description="Desc",
        draft_instructions=[RecipeStep(body="Cook", title=None)],
        ingredients=[RecipeIngredient(food_name="pasta", unit_name="g", quantity=500.0, note=None)],
        gathered_recipes=[],
    )
    assert "Pasta" in m.to_user_message()
    assert pickle.loads(pickle.dumps(m)) == m


def test_recipe_research_metadata_output_conforms_to_recipe_data():
    """RRECIPE-04: Final metadata output uses RecipeData model."""
    from robotina.queue.task_types import RecipeResearchMetadataOutput, RecipeData
    m = RecipeResearchMetadataOutput(
        recipe=RecipeData(
            name="Pasta Bolognesa",
            description="Classic",
            servings_qty=4,
            servings_unit="porciones",
            prep_time=15,
            cook_time=30,
            total_time=45,
            source_url="http://example.com",
            ingredients=[],
            steps=[],
        )
    )
    assert m.recipe.name == "Pasta Bolognesa"
    assert m.recipe.servings_qty == 4


def test_recipe_load_input_user_message_contains_full_recipe():
    """The recipe-load agent needs the full structured recipe — not just the name —
    to resolve foods, build the compound payload, and POST /api/recipes. A prior
    bug rendered only `f"Load recipe: {self.recipe.name}"`, so the agent
    (correctly) refused to proceed and the workflow advanced to a misleading
    "Receta agregada: unknown recipe" notification with no recipe actually
    created. This test pins the contract.
    """
    from robotina.queue.task_types import RecipeLoadInput

    recipe = _make_recipe_data()
    msg = RecipeLoadInput(recipe=recipe, household_id="hh-789").to_user_message()

    assert msg.startswith("Load this recipe into the household-manager system:")
    # Top-level fields
    assert recipe.name in msg
    assert recipe.description in msg
    assert recipe.source_url in msg
    # Every ingredient food_name and (non-null) unit_name
    for ing in recipe.ingredients:
        assert ing.food_name in msg
        if ing.unit_name is not None:
            assert ing.unit_name in msg
    # Every step body
    for step in recipe.steps:
        assert step.body in msg
