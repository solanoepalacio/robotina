---
phase: quick-260508-tdr
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/robotina/queue/workflow_runner.py
  - tests/test_workflow_runner.py
autonomous: true
requirements:
  - WF-FIX-01
must_haves:
  truths:
    - "_extract_task_output handles a final ToolMessage without raising ValueError"
    - "on_step_complete advances the workflow when an ack agent terminates via return_direct"
    - "Existing JSON-output extraction path is unchanged"
  artifacts:
    - path: "src/robotina/queue/workflow_runner.py"
      provides: "Robust artifact extraction tolerant of return_direct termination"
      contains: "ToolMessage short-circuit returning {'tool_message': ...}"
    - path: "tests/test_workflow_runner.py"
      provides: "Regression test covering ToolMessage-as-last-message"
      contains: "assert step.status == WorkflowStepStatus.DONE"
  key_links:
    - "src/robotina/queue/workflow_runner.py:29 — _extract_task_output"
    - "src/robotina/queue/workflow_runner.py:230 — on_step_complete artifact branch"
    - "src/robotina/agent/tools/queue.py — QueueTool with return_direct=True"
---

<objective>
Phase 07.1's switch to `return_direct=True` on `QueueTool` (commit e519ea1) terminates
the LangGraph agent immediately after the tool runs. For the `acknowledge-add-recipe`
agent — which runs as workflow step 1 — this means the agent's final state has a
`ToolMessage` as the last message (the queue tool's "Reply queued. job_id=..." string)
rather than a JSON-emitting `AIMessage`.

When `run_task()` invokes `workflow_runner.on_step_complete(...)`, the artifact
extractor `_extract_task_output()` (workflow_runner.py:29) walks back to the last
`AIMessage` (the one that emitted the tool_call). With Anthropic that AIMessage's
content is a list of tool-use blocks with no text — the extractor's `json.loads("")`
fails, the fallback scan fails, and `ValueError("Could not parse JSON from agent
output: ''")` is raised. That bubbles up, the step is marked `FAILED`, the workflow
is marked `FAILED`, and no further steps run. The user sees the acknowledgement (the
`send-notification` was already enqueued by `QueueTool` before extraction ran) but
never gets the recipe.

Fix: Teach `_extract_task_output` to recognise the return_direct termination shape
(last message is a `ToolMessage`) and return `{"tool_message": str(last.content)}`
instead of trying to JSON-parse a tool-call AIMessage. The `acknowledge` step's
artifact is not consumed by any later step (verified via `workflows.py:101–181`),
so the new artifact shape is safe.

Purpose: Restore add-recipe end-to-end (ack → gather → instructions → ingredients →
metadata → load → notify) and add a regression test so the next return_direct +
workflow-step combination doesn't regress silently.

Output:
- Updated `src/robotina/queue/workflow_runner.py` with the ToolMessage short-circuit.
- New regression tests in `tests/test_workflow_runner.py`.
</objective>

<execution_context>
@/home/solanoe/code/robotina-gsd/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
Bug origin: commit e519ea1 ("fix(07.1): switch terminal tools to return_direct=True").
That commit set `return_direct=True` on `QueueTool` and `StartWorkflowTool` to stop
LangGraph's prebuilt graph from looping back to the agent node after a terminal tool
runs. The change was correct for the agent-loop concern — and is correctly verified
by `_short_circuits_create_react_agent` regression tests — but did not exercise the
downstream `on_step_complete → _extract_task_output` artifact path.

Current `_extract_task_output` (workflow_runner.py:29-65):
- Finds the last AI message: `ai_messages[-1]`.
- Reads its `.content` (which can be a list of Anthropic tool-use blocks).
- Joins text-block content; for a tool-call AIMessage with no text block, this is `""`.
- `json.loads("")` raises; fallback scan finds no `{` or `[`; raises ValueError.

Why the routing agent isn't affected: `handle-incoming-message` jobs are direct tasks
with no `WorkflowRunStep`, so `on_step_complete` returns early at line 226 ("no
workflow step found for job_id"). `_extract_task_output` is never called for them.

Why the `acknowledge-add-recipe` step IS affected: it has a `WorkflowRunStep` row,
so `on_step_complete` proceeds past line 226 into the artifact-extraction branch.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Short-circuit _extract_task_output on ToolMessage as last message</name>
  <files>src/robotina/queue/workflow_runner.py</files>
  <action>
    Edit `_extract_task_output` (currently workflow_runner.py:29-65). Before the
    existing `ai_messages = [...]` line, inspect `result["messages"][-1]`. If its
    `type` attribute equals `"tool"`, return `{"tool_message": str(last.content)}`
    immediately. Leave the existing JSON-parsing path unchanged for the case where
    the agent terminated naturally with a final AIMessage.

    Update the docstring to mention the return_direct termination case.

    Implementation sketch:

        def _extract_task_output(result: dict) -> dict:
            messages = result["messages"]
            last = messages[-1]
            # return_direct=True terminal tool short-circuited the prebuilt graph;
            # the last message is a ToolMessage, not a JSON-emitting AIMessage.
            # Surface the tool result as the artifact directly — no JSON parsing.
            if getattr(last, "type", None) == "tool":
                return {"tool_message": str(last.content)}
            ai_messages = [m for m in messages if getattr(m, "type", None) == "ai"]
            raw = ai_messages[-1].content if ai_messages else last.content
            ...rest unchanged...

    Do NOT modify QueueTool, StartWorkflowTool, or any agent prompts.
  </action>
  <verify>
    <automated>grep -n 'tool_message' src/robotina/queue/workflow_runner.py</automated>
  </verify>
  <done>`_extract_task_output` returns `{"tool_message": ...}` when the last message has `type == "tool"`; the existing JSON-parsing path is preserved for the AIMessage-final case.</done>
</task>

<task type="auto">
  <name>Task 2: Add regression tests in tests/test_workflow_runner.py</name>
  <files>tests/test_workflow_runner.py</files>
  <action>
    Add two tests at the end of the unit-tests section:

    1. `test_extract_task_output_handles_return_direct_toolmessage`
       — direct unit test on `_extract_task_output`: build a `result` dict whose
       `messages[-1]` is a MagicMock with `type="tool"` and `content="Reply queued.
       job_id=abc"`, assert the returned dict equals `{"tool_message": "Reply
       queued. job_id=abc"}`.

    2. `test_on_step_complete_advances_after_return_direct_ack`
       — integration-style: simulate the acknowledge → gather transition end-to-end
       through `on_step_complete`. The agent output is a dict with `messages` whose
       last element is a ToolMessage (mock with `type="tool"` and `content="Reply
       queued. job_id=xyz"`), and an earlier AIMessage with empty content
       (mock with `type="ai"` and `content=""`). Use the same session-mock
       pattern as `test_on_step_complete_enqueues_next_step` (step="acknowledge",
       next_step="gather", workflow_type="add-recipe", same shared_context).

       Assertions:
       - `step.status == WorkflowStepStatus.DONE`
       - `step.artifact == {"tool_message": "Reply queued. job_id=xyz"}`
       - `queue.enqueue.called is True`  (next step enqueued)
       - `next_step.task_job_id is not None`

    These cover both the unit-level fix and the full on_step_complete path that
    the original bug crashed.
  </action>
  <verify>
    <automated>uv run pytest tests/test_workflow_runner.py -k 'return_direct or toolmessage' -q</automated>
  </verify>
  <done>Two new tests pass; existing tests in `tests/test_workflow_runner.py` still pass.</done>
</task>

<task type="auto">
  <name>Task 3: Run the workflow_runner test suite to confirm no regressions</name>
  <files></files>
  <action>
    Run `uv run pytest tests/test_workflow_runner.py -q` and confirm all tests
    (including the two new ones) pass. If anything red, fix and re-run.
  </action>
  <verify>
    <automated>uv run pytest tests/test_workflow_runner.py -q</automated>
  </verify>
  <done>All `tests/test_workflow_runner.py` tests pass.</done>
</task>

</tasks>

<verification>
- `grep -n 'tool_message' src/robotina/queue/workflow_runner.py` shows the new
  short-circuit branch and (likely) docstring mention.
- `uv run pytest tests/test_workflow_runner.py -q` passes (existing + 2 new tests).
- `git diff` shows changes confined to `src/robotina/queue/workflow_runner.py` and
  `tests/test_workflow_runner.py`. No changes to `QueueTool`, `StartWorkflowTool`,
  agents, prompts, workflows, or jobs.
</verification>

<success_criteria>
- `_extract_task_output` no longer raises `ValueError` when the agent terminated
  via a return_direct terminal tool.
- `on_step_complete` advances to the next workflow step when the ack agent
  finishes — verified by the new integration-style test.
- The `acknowledge` step's stored artifact is `{"tool_message": "Reply queued. ..."}`
  — non-empty, JSON-serializable, and not consumed by any later step (so it can't
  break gather, instructions, ingredients, metadata, load, or notify).
- All existing `tests/test_workflow_runner.py` tests still pass.
</success_criteria>

<output>
After completion, create `.planning/quick/260508-tdr-fix-extract-task-output-toolmessage/260508-tdr-SUMMARY.md`
documenting: the bug timeline (commit e519ea1 → ack workflow halt), the fix
location and shape, the test additions, and `pytest -q` output.
</output>
