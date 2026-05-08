---
quick_id: 260508-tdr
status: complete
date: 2026-05-08
description: Fix workflow halt after return_direct ack tool — tolerate ToolMessage in _extract_task_output
---

# Quick Task 260508-tdr — Summary

## What broke

Phase 07.1 commit `e519ea1` ("fix(07.1): switch terminal tools to return_direct=True") added
`return_direct=True` on `QueueTool` and `StartWorkflowTool` to stop LangGraph's prebuilt
graph from looping back to the agent node after a terminal tool runs. The change was correct
for the agent-loop concern (and verified by per-tool `_short_circuits_create_react_agent`
regression tests) but did not exercise the downstream `on_step_complete → _extract_task_output`
artifact-extraction path.

For the `acknowledge-add-recipe` agent — which runs as **workflow step 1** of `add-recipe`
— the change had a hidden side effect:

1. The agent calls `queue` once.
2. `return_direct=True` short-circuits the graph; the agent state's last message is the
   `ToolMessage` returned by `QueueTool` (`"Reply queued. job_id=..."`).
3. The tool-call `AIMessage` immediately preceding it has, on Anthropic, a `content` value
   that is a list of `tool_use` blocks with no text block.
4. `run_task()` calls `workflow_runner.on_step_complete(...)`, which calls
   `_extract_task_output(result)`.
5. That function walked back to the last `AIMessage` and tried `json.loads("")`. Both the
   primary parse and the fallback `find('{') / find('[')` scan failed.
6. `ValueError("Could not parse JSON from agent output: ''")` bubbled up to `run_task`'s
   `except`, which called `on_step_failed`, marking the step `FAILED` and the
   `WorkflowRun` `FAILED`.
7. **The `send-notification` ack was already enqueued by `QueueTool` before extraction
   ran**, so the user *did* see the acknowledgment — but no further steps fired, so the
   recipe was never gathered, looked up, or saved.

The routing agent (`handle-incoming-message`) was unaffected: its job has no
`WorkflowRunStep` row, so `on_step_complete` returns early at line 226 and never calls
`_extract_task_output`.

## What was changed

**`src/robotina/queue/workflow_runner.py`** — `_extract_task_output()`

Added a single short-circuit at the top of the function: if `messages[-1].type == "tool"`,
return `{"tool_message": str(last.content)}` instead of trying to JSON-parse the
preceding tool-call AIMessage. The existing JSON-parsing path is preserved for agents
that still terminate with a final `AIMessage` (recipe-research-*, recipe-load).

Why the new artifact shape is safe: traced `src/robotina/agent/workflows.py:101–181` —
no `build_input` callable in `WORKFLOW_REGISTRY` reads `artifacts["acknowledge"]`. The
ack step's artifact is record-only.

**`tests/test_workflow_runner.py`** — two new tests

1. `test_extract_task_output_handles_return_direct_toolmessage` — direct unit test on
   `_extract_task_output`, asserting the ToolMessage short-circuit returns
   `{"tool_message": "Reply queued. job_id=abc"}`.
2. `test_on_step_complete_advances_after_return_direct_ack` — integration-style test
   driving `on_step_complete` end-to-end with a return_direct-shaped agent result
   (HumanMessage → tool-call AIMessage with no text → ToolMessage). Asserts:
   - `step.status == WorkflowStepStatus.DONE`
   - `step.artifact == {"tool_message": "Reply queued. job_id=xyz"}`
   - `queue.enqueue.called` (next `gather` step enqueued)
   - `next_step.task_job_id is not None`

   This is exactly the scenario the original commit's tests missed — it would have
   caught the bug.

## What was *not* changed

- `QueueTool` and `StartWorkflowTool` keep `return_direct=True`. The agent-loop
  optimisation from `e519ea1` is preserved.
- No agent prompts were touched (acknowledge-add-recipe, robotina, recipe-research-*,
  recipe-load).
- No workflow definitions were touched.
- `run_task`, `on_step_failed`, `queue_workflow` are unchanged.

## Verification

```
$ uv run pytest tests/test_workflow_runner.py -q
.............                                                            [100%]
13 passed in 0.02s
```

```
$ uv run pytest tests/unit/test_queue_tool.py tests/unit/test_start_workflow_tool.py tests/test_workflows.py -q
........................                                                 [100%]
24 passed, 2 warnings in 0.18s
```

(Warnings are pre-existing `LangGraphDeprecatedSinceV10` notices from `create_react_agent`
import paths in the per-tool short-circuit tests — unrelated to this fix.)
