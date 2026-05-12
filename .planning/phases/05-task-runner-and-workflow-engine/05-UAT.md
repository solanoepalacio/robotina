---
status: resolved
phase: 05-task-runner-and-workflow-engine
source: [05-01-SUMMARY.md, 05-02-SUMMARY.md, 05-03-SUMMARY.md, 05-04-SUMMARY.md]
started: 2026-03-27T00:00:00Z
updated: 2026-03-27T01:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Unit test suite passes clean
expected: Run `uv run pytest tests/ -k "not integration" -q`. All non-integration tests pass with 0 errors and 0 failures. Expect ~81+ passed, 0 failed.
result: pass

### 2. Workflow registry has correct structure
expected: Run `uv run python -c "from robotina.agent.workflows import WORKFLOW_REGISTRY; r = WORKFLOW_REGISTRY; print(list(r.keys())); print(len(r['add-recipe'].steps), 'steps in add-recipe'); print(len(r['hello-world-2step'].steps), 'steps in hello-world-2step')"`. Output shows `['add-recipe', 'hello-world-2step']`, `3 steps in add-recipe`, `2 steps in hello-world-2step`.
result: pass

### 3. add-recipe steps have correct task types
expected: Run `uv run python -c "from robotina.agent.workflows import WORKFLOW_REGISTRY; steps = WORKFLOW_REGISTRY['add-recipe'].steps; print([s.step_key for s in steps]); print([s.task_type for s in steps])"`. Output shows step_keys `['research', 'load', 'notify']` and task_types `['recipe-research', 'recipe-load', 'send-notification']`.
result: pass

### 4. StartWorkflowTool is a valid LangChain BaseTool
expected: Run `uv run python -c "from robotina.agent.tools.start_workflow import StartWorkflowTool; from langchain_core.tools import BaseTool; print(issubclass(StartWorkflowTool, BaseTool)); t = StartWorkflowTool(); print(t.name)"`. Output shows `True` and the tool name (e.g. `start_workflow`). No import errors.
result: pass

### 5. Integration tests pass — hello-world-2step happy path
expected: With Docker services running (`docker compose up -d`), run `uv run pytest tests/test_workflow_runner.py -v -m integration --timeout=60`. The happy path test passes: WorkflowRun status is DONE, both steps are DONE, both artifacts are recorded. No failures.
result: issue
reported: "start_workflow sets WorkflowRun status=RUNNING immediately on creation, but the workflow is technically PENDING (enqueued, not yet executing). Should create as PENDING and on_step_start should transition to RUNNING. Also rename start_workflow -> queue_workflow to reflect this."
severity: major

### 6. Integration tests pass — hello-world-2step failure path
expected: With Docker services running, the failure path integration test in `tests/test_workflow_runner.py` passes: when step1 fails, step2 is CANCELLED and WorkflowRun is FAILED. No failures.
result: pass

### 7. StartWorkflowTool integration test passes
expected: Run `uv run pytest tests/test_start_workflow_tool.py -v -m integration --timeout=60`. Integration tests pass: StartWorkflowTool creates a WorkflowRun in the DB and enqueues a job in Redis. No failures.
result: pass

## Summary

total: 7
passed: 6
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "WorkflowRun is created as PENDING (not RUNNING) by queue_workflow; on_step_start transitions it to RUNNING when the worker picks up the first step"
  status: resolved
  reason: "User reported: start_workflow sets WorkflowRun status=RUNNING immediately on creation, but the workflow is technically PENDING (enqueued, not yet executing). Should create as PENDING and on_step_start should transition to RUNNING. Also rename start_workflow -> queue_workflow."
  severity: major
  test: 5
  artifacts: []
  missing: []
