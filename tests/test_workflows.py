"""Tests for workflows.py registry (WF-02, WF-03, D-02)."""
import pytest
from pydantic import BaseModel


def test_workflow_step_def_is_pydantic_model():
    """WF-02: WorkflowStepDef is a Pydantic BaseModel with step_key, task_type, build_input."""
    from robotina.agent.workflows import WorkflowStepDef
    assert issubclass(WorkflowStepDef, BaseModel)


def test_workflow_definition_is_pydantic_model():
    """WF-02: WorkflowDefinition is a Pydantic BaseModel with workflow_type and steps list."""
    from robotina.agent.workflows import WorkflowDefinition
    assert issubclass(WorkflowDefinition, BaseModel)


def test_workflow_registry_is_dict():
    """WF-02: WORKFLOW_REGISTRY is a dict[str, WorkflowDefinition]."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    assert isinstance(WORKFLOW_REGISTRY, dict)


def test_add_recipe_workflow_registered():
    """WF-03: 'add-recipe' workflow is in WORKFLOW_REGISTRY with 6 steps."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    assert "add-recipe" in WORKFLOW_REGISTRY
    assert len(WORKFLOW_REGISTRY["add-recipe"].steps) == 6


def test_add_recipe_workflow_has_6_steps():
    """D-02: add-recipe workflow has 6 steps: gather -> instructions -> ingredients -> metadata -> load -> notify."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    steps = WORKFLOW_REGISTRY["add-recipe"].steps
    assert len(steps) == 6
    expected = [
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


def test_add_recipe_build_input_gather_returns_gather_input():
    """D-02: gather step build_input returns RecipeResearchGatherInput."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeResearchGatherInput
    ctx = {"recipe_query": "pasta", "household_id": "h1"}
    result = WORKFLOW_REGISTRY["add-recipe"].steps[0].build_input(ctx, {})
    assert result == RecipeResearchGatherInput(query="pasta", household_id="h1")


def test_add_recipe_build_input_instructions():
    """D-02: instructions step reads gathered_recipes from gather artifact."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeResearchInstructionsInput
    ctx = {"recipe_query": "pasta"}
    artifacts = {"gather": {"recipes": [{"title": "Test"}]}}
    result = WORKFLOW_REGISTRY["add-recipe"].steps[1].build_input(ctx, artifacts)
    assert isinstance(result, RecipeResearchInstructionsInput)
    assert result.query == "pasta"
    assert result.gathered_recipes == [{"title": "Test"}]


def test_add_recipe_build_input_ingredients():
    """D-02: ingredients step reads draft_instructions from instructions artifact."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeResearchIngredientsInput
    ctx = {"recipe_query": "pasta", "household_id": "h1"}
    artifacts = {
        "gather": {"recipes": [{"title": "Test"}]},
        "instructions": {
            "draft_name": "Pasta",
            "draft_description": "Desc",
            "draft_instructions": [{"body": "Cook pasta", "title": None}],
        },
    }
    result = WORKFLOW_REGISTRY["add-recipe"].steps[2].build_input(ctx, artifacts)
    assert isinstance(result, RecipeResearchIngredientsInput)
    assert result.query == "pasta"
    assert len(result.draft_instructions) == 1
    assert result.draft_instructions[0].body == "Cook pasta"


def test_add_recipe_build_input_metadata():
    """D-02: metadata step reads from instructions + ingredients + gather artifacts."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeResearchMetadataInput
    ctx = {"recipe_query": "pasta"}
    artifacts = {
        "gather": {"recipes": [{"title": "Test", "url": "http://example.com"}]},
        "instructions": {
            "draft_name": "Pasta Bolognesa",
            "draft_description": "Classic dish",
            "draft_instructions": [{"body": "Cook pasta", "title": None}],
        },
        "ingredients": {
            "ingredients": [{"food_name": "pasta", "unit_name": "g", "quantity": 500.0, "note": None}],
        },
    }
    result = WORKFLOW_REGISTRY["add-recipe"].steps[3].build_input(ctx, artifacts)
    assert isinstance(result, RecipeResearchMetadataInput)
    assert result.draft_name == "Pasta Bolognesa"
    assert len(result.ingredients) == 1
    assert result.source_url == "http://example.com"


def test_add_recipe_build_input_load_returns_recipe_load_input():
    """D-02: load step build_input reads recipe from metadata artifact."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeLoadInput
    ctx = {"household_id": "h1"}
    artifacts = {
        "gather": {"recipes": []},
        "instructions": {"draft_name": "Pasta", "draft_description": "Desc", "draft_instructions": []},
        "ingredients": {"ingredients": []},
        "metadata": {
            "recipe": {
                "name": "pasta",
                "description": None,
                "servings_qty": None,
                "servings_unit": None,
                "prep_time": None,
                "cook_time": None,
                "total_time": None,
                "source_url": None,
                "ingredients": [],
                "steps": [],
            }
        },
    }
    result = WORKFLOW_REGISTRY["add-recipe"].steps[4].build_input(ctx, artifacts)
    assert isinstance(result, RecipeLoadInput)
    assert result.household_id == "h1"
    assert result.recipe.name == "pasta"


def test_add_recipe_build_input_notify_returns_send_notification_input():
    """D-02: notify step (index 5) build_input uses reply_context and load artifact."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import SendNotificationInput
    ctx = {"reply_context": {"platform": "telegram", "chat_id": "c1", "user_id": "u1"}}
    artifacts = {"load": {"recipe_name": "Pasta"}}
    result = WORKFLOW_REGISTRY["add-recipe"].steps[5].build_input(ctx, artifacts)
    assert result == SendNotificationInput(
        platform="telegram", chat_id="c1", user_id="u1", text="Receta agregada: Pasta"
    )
