"""Tests for workflows.py registry (WF-02, WF-03)."""
import pytest


def test_workflow_step_def_is_pydantic_model():
    """WF-02: WorkflowStepDef is a Pydantic BaseModel with step_key, task_type, build_input."""
    pytest.skip("not yet implemented")


def test_workflow_definition_is_pydantic_model():
    """WF-02: WorkflowDefinition is a Pydantic BaseModel with workflow_type and steps list."""
    pytest.skip("not yet implemented")


def test_workflow_registry_is_dict():
    """WF-02: WORKFLOW_REGISTRY is a dict[str, WorkflowDefinition]."""
    pytest.skip("not yet implemented")


def test_add_recipe_workflow_registered():
    """WF-03: 'add-recipe' workflow is in WORKFLOW_REGISTRY with 3 steps."""
    pytest.skip("not yet implemented")


def test_add_recipe_steps_are_research_load_notify():
    """WF-03: add-recipe steps are: research (recipe-research) -> load (recipe-load) -> notify (send-notification)."""
    pytest.skip("not yet implemented")


def test_add_recipe_build_input_research_returns_recipe_research_input():
    """WF-03: research step build_input returns RecipeResearchInput with query and household_id from shared_context."""
    pytest.skip("not yet implemented")


def test_add_recipe_build_input_load_returns_recipe_load_input():
    """WF-03: load step build_input returns RecipeLoadInput with recipe from accumulated_artifacts['research']['recipe']."""
    pytest.skip("not yet implemented")


def test_add_recipe_build_input_notify_returns_send_notification_input():
    """WF-03: notify step build_input returns SendNotificationInput with reply_context fields from shared_context."""
    pytest.skip("not yet implemented")


def test_hello_world_2step_workflow_registered():
    """D-04: 'hello-world-2step' workflow is registered with 2 hello-world steps (step1, step2)."""
    pytest.skip("not yet implemented")
