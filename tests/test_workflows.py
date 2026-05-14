"""Tests for workflows.py registry — Phase 15 accumulating-artifact contract.

Each research sub-step's build_input now reads ``RecipeData(**artifacts[<prev>])``
and emits a collapsed ``{recipe, reply_context, household_id}`` input.
"""
from pydantic import BaseModel


def _ctx():
    return {
        "recipe_query": "pasta",
        "reply_context": {"platform": "telegram", "chat_id": "c1", "user_id": "u1"},
        "household_id": "h1",
    }


def _recipe_dump(name: str = "Pasta", **overrides):
    """Build a RecipeData and dump it the way workflow_runner stores artifacts."""
    from robotina.queue.task_types import RecipeData
    return RecipeData(name=name, **overrides).model_dump(mode="json")


def test_workflow_step_def_is_pydantic_model():
    from robotina.agent.workflows import WorkflowStepDef
    assert issubclass(WorkflowStepDef, BaseModel)


def test_workflow_definition_is_pydantic_model():
    from robotina.agent.workflows import WorkflowDefinition
    assert issubclass(WorkflowDefinition, BaseModel)


def test_workflow_registry_is_dict():
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    assert isinstance(WORKFLOW_REGISTRY, dict)


def test_add_recipe_workflow_registered():
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    assert "add-recipe" in WORKFLOW_REGISTRY
    assert len(WORKFLOW_REGISTRY["add-recipe"].steps) == 7


def test_add_recipe_workflow_has_7_steps():
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    steps = WORKFLOW_REGISTRY["add-recipe"].steps
    expected = [
        ("acknowledge", "acknowledge-add-recipe"),
        ("gather", "recipe-research-gather"),
        ("instructions", "recipe-research-instructions"),
        ("ingredients", "recipe-research-ingredients"),
        ("metadata", "recipe-research-metadata"),
        ("load", "recipe-load"),
        ("notify", "send-notification"),
    ]
    for step, (key, task_type) in zip(steps, expected):
        assert step.step_key == key
        assert step.task_type == task_type


def test_acknowledge_build_input():
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import AcknowledgeAddRecipeInput
    result = WORKFLOW_REGISTRY["add-recipe"].steps[0].build_input(_ctx(), {})
    assert isinstance(result, AcknowledgeAddRecipeInput)
    assert result.recipe_query == "pasta"
    assert result.chat_id == "c1"


def test_gather_build_input_threads_reply_context_and_household_id():
    """Phase 15: gather now also receives reply_context."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeResearchGatherInput, ReplyContext
    result = WORKFLOW_REGISTRY["add-recipe"].steps[1].build_input(_ctx(), {})
    assert isinstance(result, RecipeResearchGatherInput)
    assert result.query == "pasta"
    assert result.household_id == "h1"
    assert result.reply_context == ReplyContext(platform="telegram", chat_id="c1", user_id="u1")


def test_instructions_build_input_reads_gather_artifact_as_recipe_data():
    """Phase 15: instructions reads RecipeData(**artifacts['gather'])."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeResearchInstructionsInput
    artifacts = {"gather": _recipe_dump(name="pasta", gathered_sources=[{"url": "u"}])}
    result = WORKFLOW_REGISTRY["add-recipe"].steps[2].build_input(_ctx(), artifacts)
    assert isinstance(result, RecipeResearchInstructionsInput)
    assert result.recipe.name == "pasta"
    assert result.recipe.gathered_sources == [{"url": "u"}]
    assert result.household_id == "h1"


def test_ingredients_build_input_reads_instructions_artifact():
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeResearchIngredientsInput, RecipeStep
    artifacts = {
        "gather": _recipe_dump(name="pasta"),
        "instructions": _recipe_dump(
            name="pasta", description="Tasty",
            steps=[RecipeStep(body="Boil water")],
        ),
    }
    result = WORKFLOW_REGISTRY["add-recipe"].steps[3].build_input(_ctx(), artifacts)
    assert isinstance(result, RecipeResearchIngredientsInput)
    assert result.recipe.description == "Tasty"
    assert len(result.recipe.steps) == 1


def test_metadata_build_input_reads_ingredients_artifact():
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeResearchMetadataInput, RecipeIngredient
    artifacts = {
        "ingredients": _recipe_dump(
            name="pasta",
            ingredients=[RecipeIngredient(food_name="pasta", food_id="f1")],
            missing_ingredients=["paprika"],
        ),
    }
    result = WORKFLOW_REGISTRY["add-recipe"].steps[4].build_input(_ctx(), artifacts)
    assert isinstance(result, RecipeResearchMetadataInput)
    assert result.recipe.ingredients[0].food_id == "f1"
    assert result.recipe.missing_ingredients == ["paprika"]


def test_load_build_input_reads_metadata_artifact_directly():
    """Phase 15: artifacts['metadata'] IS the RecipeData dump (no 'recipe' wrapper)."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeLoadInput
    artifacts = {"metadata": _recipe_dump(name="pasta", servings_qty=4)}
    result = WORKFLOW_REGISTRY["add-recipe"].steps[5].build_input(_ctx(), artifacts)
    assert isinstance(result, RecipeLoadInput)
    assert result.recipe.name == "pasta"
    assert result.recipe.servings_qty == 4
    assert result.household_id == "h1"


def test_notify_reads_missing_from_metadata_artifact():
    """D-05 / D-19: notify text reads missing_ingredients from metadata artifact."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import SendNotificationInput
    artifacts = {
        "metadata": _recipe_dump(name="Pasta", missing_ingredients=["paprika", "saffron"]),
        "load": {
            "recipe_name": "Pasta",
            "recipe_description": "Tasty",
            "recipe_slug": "pasta",
        },
    }
    result = WORKFLOW_REGISTRY["add-recipe"].steps[6].build_input(_ctx(), artifacts)
    assert isinstance(result, SendNotificationInput)
    assert "Pasta" in result.text
    assert "paprika" in result.text
    assert "saffron" in result.text


def test_build_notify_text_takes_two_artifacts():
    """_build_notify_text must accept (metadata_artifact, load_artifact)."""
    from robotina.agent.workflows import _build_notify_text
    text = _build_notify_text(
        {"missing_ingredients": ["paprika"]},
        {"recipe_name": "Pasta", "recipe_description": None, "recipe_slug": "pasta"},
    )
    assert "Pasta" in text
    assert "paprika" in text
