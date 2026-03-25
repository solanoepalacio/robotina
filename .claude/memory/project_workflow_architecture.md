---
name: workflow orchestration architecture decision
description: Robotina uses centralized workflow orchestration (Option C) instead of task choreography for multi-step sequences
type: project
---

Robotina uses a **WorkflowRun** orchestration pattern for multi-step task sequences, not choreography.

**Why:** Choreography (each task enqueuing the next) distributes workflow shape across agents, requires threading reply_context and RecipeData through all intermediate task inputs, and makes failure handling fragile. Centralized orchestration keeps task inputs clean and puts all sequence logic in one place (workflows.py).

**How to apply:**
- `workflows.py` (alongside `agents.py`) defines all multi-step workflows as `WorkflowDefinition` objects with ordered `WorkflowStepDef` entries and `build_input` callables.
- `WorkflowRun` / `WorkflowRunStep` are stored in Postgres. `sharedContext` holds reply_context, household_id etc — set once, never forwarded through task inputs. `artifact` per step holds the step's output.
- There is NO `workflow-advance` task type. When a step completes, the task runner advances inline: writes artifact, calls `build_input(shared_context, accumulated_artifacts)`, enqueues next agent task. The queue only ever holds LLM agent tasks.
- `recipe-research` and `recipe-load` agents do NOT have a `queue` tool — they don't enqueue successors. The task runner does.
- `handle-incoming-message` uses the `start-workflow` tool for multi-step intents, and the `queue` tool only for direct single-step replies (Workflow 1 path).
- Phase 1 workflows: `add-recipe` (recipe-research → recipe-load → send-notification).
