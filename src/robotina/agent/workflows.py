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
    FinalizeOutcomeInput,
    RecipeData,
    RecipeLoadInput,
    RecipeResearchGatherInput,
    RecipeResearchIngredientsInput,
    RecipeResearchInstructionsInput,
    RecipeResearchMetadataInput,
    ReplyContext,
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
# Phase 21 D-06: legacy ``acknowledge`` (acknowledge-add-recipe) and
# ``notify`` (send-notification) steps removed. User-facing acknowledgment
# now happens directly in Robotina's V005 routing turn via RespondTool;
# user-facing completion announcement happens on the wake invocation
# (also via RespondTool) after ``finalize-outcome`` writes the WorkflowRun
# outcome.

WORKFLOW_REGISTRY: dict[str, WorkflowDefinition] = {
    "add-recipe": WorkflowDefinition(
        workflow_type="add-recipe",
        steps=[
            WorkflowStepDef(
                step_key="gather",
                task_type="recipe-research-gather",
                build_input=lambda ctx, _: RecipeResearchGatherInput(
                    query=ctx["recipe_query"],
                    reply_context=ReplyContext(**ctx["reply_context"]),
                    household_id=ctx["household_id"],
                ),
            ),
            WorkflowStepDef(
                step_key="instructions",
                task_type="recipe-research-instructions",
                # Phase 15: artifacts["gather"] is now a RecipeData dump.
                build_input=lambda ctx, artifacts: RecipeResearchInstructionsInput(
                    recipe=RecipeData(**artifacts["gather"]),
                    reply_context=ReplyContext(**ctx["reply_context"]),
                    household_id=ctx["household_id"],
                ),
            ),
            WorkflowStepDef(
                step_key="ingredients",
                task_type="recipe-research-ingredients",
                build_input=lambda ctx, artifacts: RecipeResearchIngredientsInput(
                    recipe=RecipeData(**artifacts["instructions"]),
                    reply_context=ReplyContext(**ctx["reply_context"]),
                    household_id=ctx["household_id"],
                ),
            ),
            WorkflowStepDef(
                step_key="metadata",
                task_type="recipe-research-metadata",
                build_input=lambda ctx, artifacts: RecipeResearchMetadataInput(
                    recipe=RecipeData(**artifacts["ingredients"]),
                    reply_context=ReplyContext(**ctx["reply_context"]),
                    household_id=ctx["household_id"],
                ),
            ),
            WorkflowStepDef(
                step_key="load",
                task_type="recipe-load",
                # Phase 15: artifacts["metadata"] IS the RecipeData dump (no "recipe" wrapper).
                build_input=lambda ctx, artifacts: RecipeLoadInput(
                    recipe=RecipeData(**artifacts["metadata"]),
                    reply_context=ReplyContext(**ctx["reply_context"]),
                    household_id=ctx["household_id"],
                ),
            ),
            # Phase 21 D-02 / D-06: terminal step composes the AddRecipeOutcome
            # JSON. The legacy ``notify`` send-notification step was deleted in
            # this plan — user-facing completion announcement happens on the
            # wake invocation via RespondTool after this step writes the outcome.
            # Agent-less — run_task has a dedicated branch (D-01).
            WorkflowStepDef(
                step_key="finalize-outcome",
                task_type="finalize-outcome",
                build_input=lambda ctx, artifacts: FinalizeOutcomeInput(
                    metadata=artifacts.get("metadata"),
                    load=artifacts.get("load"),
                ),
            ),
        ],
    ),
}
