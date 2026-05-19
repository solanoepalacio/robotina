"""Unit tests for Pydantic task I/O models (QUEUE-03).

No Docker required — all tests are pure Python.
Run: uv run pytest tests/test_task_types.py -x -q

Phase 15 contract:
- ``RecipeData`` is the single shared artifact across the recipe-research
  pipeline. Only ``name`` is required; every other field is Optional/defaulted.
- ``RecipeIngredient`` carries ``food_id`` and ``unit_id`` (resolved by the
  ingredients-step validation tools).
- All four downstream ``Recipe*Input`` models collapse to
  ``{recipe, reply_context, household_id}``. ``RecipeResearchGatherInput``
  keeps ``{query, reply_context, household_id}`` because gather has no
  prior artifact.
- ``RecipeLoadOutput`` no longer carries ``missing_ingredients``.
"""
import pickle
from datetime import datetime, timezone


def _reply_ctx():
    from robotina.queue.task_types import ReplyContext
    return ReplyContext(platform="telegram", chat_id="c1", user_id="u1")


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
    """All model classes must import without error."""
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
    from robotina.queue.task_types import IncomingMessageInput
    hints = IncomingMessageInput.model_fields
    assert "history" in hints, "IncomingMessageInput missing 'history' field"


def test_recipe_research_input_has_no_reply_context():
    """Legacy RecipeResearchInput (single-shot) must NOT have a reply_context field."""
    from robotina.queue.task_types import RecipeResearchInput
    assert "reply_context" not in RecipeResearchInput.model_fields


# ---------------------------------------------------------------------------
# Phase 15 — RecipeData / RecipeIngredient / RecipeLoadOutput shape
# ---------------------------------------------------------------------------

def test_recipe_data_only_name_required():
    """RecipeData(name='X') must construct with every other field defaulted."""
    from robotina.queue.task_types import RecipeData
    r = RecipeData(name="X")
    assert r.name == "X"
    assert r.description is None
    assert r.servings_qty is None
    assert r.ingredients == []
    assert r.steps == []
    assert r.gathered_sources is None
    assert r.missing_ingredients == []


def test_recipe_ingredient_food_id_unit_id_default_none():
    """RecipeIngredient has new food_id / unit_id fields, both default None."""
    from robotina.queue.task_types import RecipeIngredient
    i = RecipeIngredient(food_name="cebolla")
    assert i.food_id is None
    assert i.unit_id is None


def test_recipe_data_dump_round_trip_preserves_phase15_fields():
    from robotina.queue.task_types import RecipeData, RecipeIngredient
    r = RecipeData(
        name="X",
        gathered_sources=[{"url": "http://example.com"}],
        missing_ingredients=["paprika"],
        ingredients=[RecipeIngredient(food_name="cebolla", food_id="f1", unit_id="u1")],
    )
    dumped = r.model_dump(mode="json")
    restored = RecipeData(**dumped)
    assert restored.gathered_sources == [{"url": "http://example.com"}]
    assert restored.missing_ingredients == ["paprika"]
    assert restored.ingredients[0].food_id == "f1"
    assert restored.ingredients[0].unit_id == "u1"


def test_recipe_load_output_no_missing_ingredients():
    """Phase 15 / D-19: RecipeLoadOutput must NOT carry missing_ingredients."""
    from robotina.queue.task_types import RecipeLoadOutput
    assert "missing_ingredients" not in RecipeLoadOutput.model_fields


# ---------------------------------------------------------------------------
# Phase 15 — Recipe*Input collapse
# ---------------------------------------------------------------------------

def test_research_inputs_collapse_to_recipe_reply_context_household_id():
    """All four downstream Recipe*Input models have exactly {recipe, reply_context, household_id}."""
    from robotina.queue.task_types import (
        RecipeResearchInstructionsInput,
        RecipeResearchIngredientsInput,
        RecipeResearchMetadataInput,
        RecipeLoadInput,
    )
    expected = {"recipe", "reply_context", "household_id"}
    for M in (
        RecipeResearchInstructionsInput,
        RecipeResearchIngredientsInput,
        RecipeResearchMetadataInput,
        RecipeLoadInput,
    ):
        assert set(M.model_fields) == expected, (M.__name__, set(M.model_fields))


def test_gather_input_keeps_query_shape():
    """RecipeResearchGatherInput stays {query, reply_context, household_id}."""
    from robotina.queue.task_types import RecipeResearchGatherInput
    assert set(RecipeResearchGatherInput.model_fields) == {"query", "reply_context", "household_id"}


def test_collapsed_inputs_construct_and_round_trip():
    from robotina.queue.task_types import (
        RecipeResearchInstructionsInput,
        RecipeResearchIngredientsInput,
        RecipeResearchMetadataInput,
        RecipeLoadInput,
    )
    r = _make_recipe_data()
    for M in (
        RecipeResearchInstructionsInput,
        RecipeResearchIngredientsInput,
        RecipeResearchMetadataInput,
        RecipeLoadInput,
    ):
        m = M(recipe=r, reply_context=_reply_ctx(), household_id="h1")
        restored = pickle.loads(pickle.dumps(m))
        assert restored == m


def test_gather_input_to_user_message_is_query():
    from robotina.queue.task_types import RecipeResearchGatherInput
    m = RecipeResearchGatherInput(
        query="Pasta Bolognesa",
        reply_context=_reply_ctx(),
        household_id="h1",
    )
    assert m.to_user_message() == "Pasta Bolognesa"


def test_research_output_sentinels_are_recipe_data_aliases():
    """Per Plan 15-01: the four Recipe*Output sentinels alias RecipeData."""
    from robotina.queue.task_types import (
        RecipeData,
        RecipeResearchGatherOutput,
        RecipeResearchInstructionsOutput,
        RecipeResearchIngredientsOutput,
        RecipeResearchMetadataOutput,
    )
    for sentinel in (
        RecipeResearchGatherOutput,
        RecipeResearchInstructionsOutput,
        RecipeResearchIngredientsOutput,
        RecipeResearchMetadataOutput,
    ):
        assert sentinel is RecipeData


# ---------------------------------------------------------------------------
# Pickle round-trips (RQ serialization)
# ---------------------------------------------------------------------------

def test_incoming_message_input_pickle_round_trip():
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
    assert pickle.loads(pickle.dumps(model)) == model


def test_recipe_research_input_pickle_round_trip():
    """Legacy single-shot RecipeResearchInput must still survive pickle."""
    from robotina.queue.task_types import RecipeResearchInput
    model = RecipeResearchInput(query="carbonara", household_id="hh-789")
    assert pickle.loads(pickle.dumps(model)) == model


def test_recipe_load_input_pickle_round_trip():
    from robotina.queue.task_types import RecipeLoadInput
    model = RecipeLoadInput(
        recipe=_make_recipe_data(),
        reply_context=_reply_ctx(),
        household_id="hh-789",
    )
    assert pickle.loads(pickle.dumps(model)) == model


def test_send_notification_input_pickle_round_trip():
    from robotina.queue.task_types import SendNotificationInput
    model = SendNotificationInput(
        platform="telegram", chat_id="chat-123", user_id="user-456",
        text="Recipe added: Carbonara",
    )
    assert pickle.loads(pickle.dumps(model)) == model


def test_recipe_data_empty_lists_pickle_round_trip():
    from robotina.queue.task_types import RecipeData
    model = RecipeData(name="Empty Recipe", ingredients=[], steps=[])
    assert pickle.loads(pickle.dumps(model)) == model


def test_recipe_load_input_user_message_contains_full_recipe():
    """recipe-load agent gets the full structured recipe in its user message."""
    from robotina.queue.task_types import RecipeLoadInput
    recipe = _make_recipe_data()
    msg = RecipeLoadInput(
        recipe=recipe,
        reply_context=_reply_ctx(),
        household_id="hh-789",
    ).to_user_message()
    assert msg.startswith("Load this recipe into household-manager")
    assert recipe.name in msg
    assert recipe.description in msg
    assert recipe.source_url in msg
    for ing in recipe.ingredients:
        assert ing.food_name in msg
    for step in recipe.steps:
        assert step.body in msg


# ---------------------------------------------------------------------------
# Phase 18 / ARCH-04 — AddRecipeOutcome
# ---------------------------------------------------------------------------
# Per-workflow outcome summary written by the Phase-20 ``finalize-outcome``
# step. Phase 18 only defines the Pydantic shape — no producer or consumer
# this phase. Replaces the Phase-17 WorkflowOutcome placeholder (D-18).


def test_add_recipe_outcome_success_round_trip():
    """D-17: success variant round-trips with recipe_id/recipe_name/recipe_slug."""
    from robotina.queue.task_types import AddRecipeOutcome
    o = AddRecipeOutcome(
        status="success",
        recipe_id="r1",
        recipe_name="Lentejas",
        recipe_slug="lentejas",
    )
    dumped = o.model_dump()
    assert dumped["status"] == "success"
    assert dumped["recipe_id"] == "r1"
    assert dumped["recipe_name"] == "Lentejas"
    assert dumped["recipe_slug"] == "lentejas"
    assert dumped["image_present"] is False  # default


def test_add_recipe_outcome_failure_round_trip():
    """D-17: failure variant carries failure_reason."""
    from robotina.queue.task_types import AddRecipeOutcome
    o = AddRecipeOutcome(status="failure", failure_reason="boom")
    assert o.status == "failure"
    assert o.failure_reason == "boom"
    assert o.recipe_id is None


def test_add_recipe_outcome_rejects_unknown_fields():
    """D-17: model_config = ConfigDict(extra='forbid')."""
    import pytest
    from pydantic import ValidationError
    from robotina.queue.task_types import AddRecipeOutcome
    with pytest.raises(ValidationError):
        AddRecipeOutcome(status="success", unknown_field="oops")


def test_add_recipe_outcome_rejects_invalid_status():
    """D-17: status is Literal['success', 'failure']."""
    import pytest
    from pydantic import ValidationError
    from robotina.queue.task_types import AddRecipeOutcome
    with pytest.raises(ValidationError):
        AddRecipeOutcome(status="completed")


def test_add_recipe_outcome_image_present_defaults_false():
    """D-17: image_present default False — Phase 24 flips it."""
    from robotina.queue.task_types import AddRecipeOutcome
    o = AddRecipeOutcome(status="success")
    assert o.image_present is False


def test_workflow_outcome_class_no_longer_exists():
    """D-18: WorkflowOutcome stub is REPLACED (not supplemented) by AddRecipeOutcome.
    Imports of the old name must fail at module-attribute level."""
    import robotina.queue.task_types as tt
    assert not hasattr(tt, "WorkflowOutcome"), (
        "Phase 17 stub WorkflowOutcome must be removed by Phase 18 D-18 — "
        "AddRecipeOutcome replaces it; no envelope wrapper in v1.1."
    )
