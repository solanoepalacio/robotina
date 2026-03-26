"""Tests for workflows.py registry (WF-02, WF-03)."""
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
    """WF-03: 'add-recipe' workflow is in WORKFLOW_REGISTRY with 3 steps."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    assert "add-recipe" in WORKFLOW_REGISTRY
    assert len(WORKFLOW_REGISTRY["add-recipe"].steps) == 3


def test_add_recipe_steps_are_research_load_notify():
    """WF-03: add-recipe steps are: research (recipe-research) -> load (recipe-load) -> notify (send-notification)."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    steps = WORKFLOW_REGISTRY["add-recipe"].steps
    assert steps[0].step_key == "research"
    assert steps[0].task_type == "recipe-research"
    assert steps[1].step_key == "load"
    assert steps[1].task_type == "recipe-load"
    assert steps[2].step_key == "notify"
    assert steps[2].task_type == "send-notification"


def test_add_recipe_build_input_research_returns_recipe_research_input():
    """WF-03: research step build_input returns RecipeResearchInput with query and household_id from shared_context."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeResearchInput
    ctx = {"recipe_query": "pasta", "household_id": "h1"}
    artifacts = {}
    result = WORKFLOW_REGISTRY["add-recipe"].steps[0].build_input(ctx, artifacts)
    assert result == RecipeResearchInput(query="pasta", household_id="h1")


def test_add_recipe_build_input_load_returns_recipe_load_input():
    """WF-03: load step build_input returns RecipeLoadInput with recipe from accumulated_artifacts['research']['recipe']."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeLoadInput
    ctx = {"household_id": "h1"}
    artifacts = {
        "research": {
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
        }
    }
    result = WORKFLOW_REGISTRY["add-recipe"].steps[1].build_input(ctx, artifacts)
    assert isinstance(result, RecipeLoadInput)
    assert result.household_id == "h1"
    assert result.recipe.name == "pasta"


def test_add_recipe_build_input_notify_returns_send_notification_input():
    """WF-03: notify step build_input returns SendNotificationInput with reply_context fields from shared_context."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import SendNotificationInput
    ctx = {"reply_context": {"platform": "telegram", "chat_id": "c1", "user_id": "u1"}}
    artifacts = {"load": {"recipe_name": "Pasta"}}
    result = WORKFLOW_REGISTRY["add-recipe"].steps[2].build_input(ctx, artifacts)
    assert result == SendNotificationInput(
        platform="telegram", chat_id="c1", user_id="u1", text="Recipe added: Pasta"
    )


def test_hello_world_2step_workflow_registered():
    """D-04: 'hello-world-2step' workflow is registered with 2 hello-world steps (step1, step2)."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    assert "hello-world-2step" in WORKFLOW_REGISTRY
    steps = WORKFLOW_REGISTRY["hello-world-2step"].steps
    assert len(steps) == 2
    assert steps[0].step_key == "step1"
    assert steps[1].step_key == "step2"
