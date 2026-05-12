# Phase 5: Task Runner and Workflow Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-26
**Phase:** 05-task-runner-and-workflow-engine
**Areas discussed:** Advancement hook structure, Tools module layout, Verification test scope, Workflow module encapsulation

---

## Advancement Hook Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Inline check in run_task() | run_task() queries WorkflowRunStep by task_job_id; wraps agent execution with workflow state management inline | ✓ |
| Dispatcher + run_workflow_step() | New dispatcher routes to run_workflow_step() or run_task() based on job meta | |
| Wrapper around run_task() | Separate run_workflow_step() wraps run_task() entirely; start-workflow enqueues this function | |

**User's choice:** Inline check in run_task()
**Notes:** Spec language "task runner checks if job is associated with a workflow" implies inline check approach.

---

## Tools Module Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Per-tool module files | Each tool gets its own file: tools/start_workflow.py, tools/queue.py, etc. | ✓ |
| Single tools.py file | All tools in src/robotina/agent/tools.py | |

**User's choice:** Per-tool module files (src/robotina/agent/tools/ package)
**Notes:** Matches spec file tree listing and Phase 4 pattern of logical unit separation.

---

## Verification Test Scope

| Option | Description | Selected |
|--------|-------------|----------|
| hello-world task type end-to-end | Test workflow with hello-world steps through real queue + DB | ✓ |
| Unit tests for advancement logic only | Mock DB + queue, no end-to-end execution | ✓ (also required) |
| Full add-recipe workflow with stubs | Stub implementations of all 3 agents | |

**User's choice:** hello-world-2step workflow (two hello-world steps) for integration tests, PLUS unit tests for workflow_runner.py advancement logic as a separate requirement.
**Notes:** "create a hello-world workflow that is formed by two hello-world tasks. Unit tests for advancement logic are also a must."

---

## Workflow Module Encapsulation

| Option | Description | Selected |
|--------|-------------|----------|
| queue/workflow_runner.py | Dedicated module in queue package; owns start_workflow(), on_step_start(), on_step_complete(), on_step_failed() | ✓ |
| agent/workflow_runner.py | Same module but in agent package (odd dependency direction) | |
| Inline in jobs.py | Advancement logic mixed with agent execution code | |

**User's choice:** src/robotina/queue/workflow_runner.py
**Notes:** User's concern: "The workflow logic must be encapsulated in a module, it can be [not] spread around multiple modules." workflow_runner.py becomes the single execution-side owner of all workflow state management.

---

## Claude's Discretion

- Exact SQLAlchemy query patterns for WorkflowRunStep lookup by task_job_id
- WorkflowStepDef as Pydantic BaseModel (per spec) vs dataclass
- accumulated_artifacts building approach (query all DONE steps for workflow_run_id)
- on_step_start / on_step_complete exact parameter signatures beyond the injected session/queue

## Deferred Ideas

None.
