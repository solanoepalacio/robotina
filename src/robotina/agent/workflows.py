"""Workflow registry for Robotina.

WorkflowDefinition + WorkflowStepDef data models and the WORKFLOW_REGISTRY
mapping workflow type names to their ordered steps and build_input callables.

IMPORTANT: build_input callables receive:
  - shared_context: dict — frozen snapshot set at workflow creation; NEVER mutate it
  - accumulated_artifacts: dict[str, dict] — keyed by step_key, values are the
    step output dicts (model.model_dump(mode='json') from each completed step)

The 'hello-world-2step' entry was removed in Phase 6.
"""
from __future__ import annotations

from typing import Callable

from pydantic import BaseModel, ConfigDict

from robotina.queue.task_types import (
    RecipeData,
    RecipeIngredient,
    RecipeLoadInput,
    RecipeResearchGatherInput,
    RecipeResearchIngredientsInput,
    RecipeResearchInstructionsInput,
    RecipeResearchMetadataInput,
    RecipeStep,
    SendNotificationInput,
)


class WorkflowStepDef(BaseModel):
    """Definition of a single step within a workflow.

    Fields:
        step_key: Unique identifier within this workflow (matches WorkflowRunStep.step_key).
        task_type: RQ task type string (matches AGENT_REGISTRY key in agents.py).
        build_input: Callable(shared_context, accumulated_artifacts) -> Pydantic input model.
                     shared_context is a frozen dict — never mutate it.
                     accumulated_artifacts is {step_key: step_output_dict} for DONE steps.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    step_key: str
    task_type: str
    build_input: Callable[[dict, dict], object]


class WorkflowDefinition(BaseModel):
    """Complete definition of a workflow: its type name and ordered steps."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    workflow_type: str
    steps: list[WorkflowStepDef]


# ---------------------------------------------------------------------------
# Workflow Registry
# ---------------------------------------------------------------------------

WORKFLOW_REGISTRY: dict[str, WorkflowDefinition] = {
    "add-recipe": WorkflowDefinition(
        workflow_type="add-recipe",
        steps=[
            WorkflowStepDef(
                step_key="gather",
                task_type="recipe-research-gather",
                build_input=lambda ctx, _: RecipeResearchGatherInput(
                    query=ctx["recipe_query"],
                    household_id=ctx["household_id"],
                ),
            ),
            WorkflowStepDef(
                step_key="instructions",
                task_type="recipe-research-instructions",
                build_input=lambda ctx, artifacts: RecipeResearchInstructionsInput(
                    query=ctx["recipe_query"],
                    gathered_recipes=artifacts["gather"]["recipes"],
                ),
            ),
            WorkflowStepDef(
                step_key="ingredients",
                task_type="recipe-research-ingredients",
                build_input=lambda ctx, artifacts: RecipeResearchIngredientsInput(
                    query=ctx["recipe_query"],
                    draft_instructions=[
                        RecipeStep(**s) for s in artifacts["instructions"]["draft_instructions"]
                    ],
                    gathered_recipes=artifacts["gather"]["recipes"],
                    household_id=ctx["household_id"],
                ),
            ),
            WorkflowStepDef(
                step_key="metadata",
                task_type="recipe-research-metadata",
                build_input=lambda ctx, artifacts: RecipeResearchMetadataInput(
                    query=ctx["recipe_query"],
                    draft_name=artifacts["instructions"]["draft_name"],
                    draft_description=artifacts["instructions"]["draft_description"],
                    draft_instructions=[
                        RecipeStep(**s) for s in artifacts["instructions"]["draft_instructions"]
                    ],
                    ingredients=[
                        RecipeIngredient(**i) for i in artifacts["ingredients"]["ingredients"]
                    ],
                    gathered_recipes=artifacts["gather"]["recipes"],
                    source_url=artifacts["gather"]["recipes"][0].get("url") if artifacts["gather"]["recipes"] else None,
                ),
            ),
            WorkflowStepDef(
                step_key="load",
                task_type="recipe-load",
                # artifacts["metadata"]["recipe"] is a dict from model_dump(mode='json')
                # -- must reconstruct RecipeData before passing to RecipeLoadInput
                build_input=lambda ctx, artifacts: RecipeLoadInput(
                    recipe=RecipeData(**artifacts["metadata"]["recipe"]),
                    household_id=ctx["household_id"],
                ),
            ),
            WorkflowStepDef(
                step_key="notify",
                task_type="send-notification",
                build_input=lambda ctx, artifacts: SendNotificationInput(
                    **ctx["reply_context"],
                    text=f"Recipe added: {artifacts['load']['recipe_name']}",
                ),
            ),
        ],
    ),
}
