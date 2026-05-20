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

import os
from typing import Callable

from pydantic import BaseModel, ConfigDict

from robotina.queue.task_types import (
    AcknowledgeAddRecipeInput,
    FinalizeOutcomeInput,
    RecipeData,
    RecipeLoadInput,
    RecipeResearchGatherInput,
    RecipeResearchIngredientsInput,
    RecipeResearchInstructionsInput,
    RecipeResearchMetadataInput,
    ReplyContext,
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
# Notification helpers
# ---------------------------------------------------------------------------

def _build_notify_text(metadata_artifact: dict, load_artifact: dict) -> str:
    """Compose notification text from the metadata and load step artifacts.

    Phase 15: ``missing_ingredients`` now lives on the metadata-step's
    ``RecipeData`` snapshot (the ingredients step writes it; metadata
    preserves it). ``RecipeLoadOutput`` no longer carries it. Pull the
    recipe-name/description/slug from ``load_artifact`` and the missing
    list from ``metadata_artifact``.
    """
    base_url = os.environ.get("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")
    name = load_artifact.get("recipe_name", "Unknown recipe")
    description = load_artifact.get("recipe_description")
    slug = load_artifact.get("recipe_slug", "")
    missing = metadata_artifact.get("missing_ingredients", [])

    parts = [f"Receta agregada: {name}"]
    if description:
        parts.append(description)
    if slug:
        parts.append(f"{base_url}/recipe/{slug}")
    if missing:
        parts.append(f"Ingredientes no encontrados: {', '.join(missing)}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Workflow Registry
# ---------------------------------------------------------------------------

WORKFLOW_REGISTRY: dict[str, WorkflowDefinition] = {
    "add-recipe": WorkflowDefinition(
        workflow_type="add-recipe",
        steps=[
            # Phase 07.1: per-workflow acknowledgment agent runs as step 1.
            # Routes the user-facing ack out of the routing agent so handle-incoming-message
            # can emit a single tool call (start-workflow) and terminate.
            WorkflowStepDef(
                step_key="acknowledge",
                task_type="acknowledge-add-recipe",
                build_input=lambda ctx, _: AcknowledgeAddRecipeInput(
                    recipe_query=ctx["recipe_query"],
                    reply_context=ctx["reply_context"],
                ),
            ),
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
            WorkflowStepDef(
                step_key="notify",
                task_type="send-notification",
                build_input=lambda ctx, artifacts: SendNotificationInput(
                    **ctx["reply_context"],
                    text=_build_notify_text(artifacts["metadata"], artifacts["load"]),
                ),
            ),
            # WAKE-04 / D-02: deterministic terminal step that composes the
            # AddRecipeOutcome JSON. APPENDED after `notify` (not replacing it) so
            # users keep getting the legacy reply through this milestone; the next
            # milestone deletes `notify` and moves this step accordingly.
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
