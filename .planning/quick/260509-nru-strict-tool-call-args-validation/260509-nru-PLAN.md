---
quick_id: 260509-nru
slug: strict-tool-call-args-validation
type: execute
wave: 1
depends_on: []
files_modified:
  - src/robotina/agent/tools/household_manager_api.py
  - src/robotina/agent/tools/start_workflow.py
  - tests/unit/test_household_manager_api_tool.py
  - tests/unit/test_start_workflow_tool.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "An LLM-emitted tool call with an unknown argument key (e.g. extra `response`) does NOT crash run_task() with TypeError."
    - "An LLM-emitted tool call with an unknown argument key produces a ToolMessage(status='error') the agent sees on its next turn, so it can self-correct."
    - "Valid tool calls (including ones that omit optional fields like `body`/`query`) still succeed unchanged."
    - "HouseholdManagerApiTool.args_schema and StartWorkflowTool.args_schema both forbid extra fields (model_json_schema reports additionalProperties: false)."
  artifacts:
    - path: "src/robotina/agent/tools/household_manager_api.py"
      provides: "HouseholdManagerApiTool with explicit Pydantic v2 args_schema (extra='forbid')"
      contains: "args_schema"
    - path: "src/robotina/agent/tools/start_workflow.py"
      provides: "StartWorkflowTool with explicit Pydantic v2 args_schema (extra='forbid')"
      contains: "args_schema"
    - path: "tests/unit/test_household_manager_api_tool.py"
      provides: "Unit test that an extra/unknown arg yields ValidationError (not TypeError) and that a single agent turn returns a ToolMessage carrying the error rather than blowing up."
    - path: "tests/unit/test_start_workflow_tool.py"
      provides: "Unit test that an extra/unknown arg yields ValidationError (not TypeError)."
  key_links:
    - from: "HouseholdManagerApiTool / StartWorkflowTool"
      to: "Pydantic args_schema (BaseModel with model_config = ConfigDict(extra='forbid'))"
      via: "args_schema = <SchemaClass> on the BaseTool subclass"
      pattern: "args_schema: type\\[BaseModel\\] = "
    - from: "tool.invoke({...extra field...})"
      to: "ValidationError → ToolInvocationError → ToolMessage(status='error') seen by the agent"
      via: "langgraph ToolNode._execute_tool_sync default error handling (handle_tool_errors=_default_handle_tool_errors)"
      pattern: "handle_tool_errors|ToolInvocationError"
---

<objective>
Make tool-call argument validation strict on the two Robotina tools that take dict-shaped args
(`HouseholdManagerApiTool`, `StartWorkflowTool`) so a hallucinated/unknown LLM-emitted field is
rejected as a Pydantic `ValidationError` at `tool.invoke()` time. LangGraph's prebuilt ToolNode
already wraps that ValidationError in a `ToolMessage(status="error")` the agent sees on its next
turn (see `<context>` finding) — so the agent can self-correct instead of the worker dying with a
`TypeError` and the workflow_runner cancelling all pending steps.

Purpose: Convert one class of LLM hallucination (extra/unknown tool arg) from a terminal workflow
failure into a recoverable, agent-visible tool error. Reproduces the staging failure
`workflow_run_id=803da0b0-5512-4152-b689-77b0241ca7c3` (Ollama emitted `'response': '200'` →
`TypeError: HouseholdManagerApiTool._run() got an unexpected keyword argument 'response'` →
3 pending steps cancelled).

Output: Strict Pydantic v2 args_schema on both tools, plus unit tests that prove the new behavior
end-to-end (extra-arg invoke → no TypeError; single agent turn with extra arg → ToolMessage with
the validation error).
</objective>

<execution_context>
@/home/solanoe/code/robotina-gsd/.claude/get-shit-done/workflows/execute-plan.md
@/home/solanoe/code/robotina-gsd/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md

@src/robotina/agent/tools/household_manager_api.py
@src/robotina/agent/tools/start_workflow.py
@src/robotina/queue/jobs.py
@workflow-failure.log
@tests/unit/test_household_manager_api_tool.py
@tests/unit/test_start_workflow_tool.py
@src/robotina/llm/__init__.py

<interfaces>
<!-- Key contracts the executor needs. Already verified during planning. -->

Existing `_run` signatures (DO NOT CHANGE):

```python
# src/robotina/agent/tools/household_manager_api.py:72-78
def _run(
    self,
    method: str,
    path: str,
    body: dict | None = None,
    query: dict | None = None,
) -> dict | str: ...

# src/robotina/agent/tools/start_workflow.py:73
def _run(self, workflow_type: str, shared_context: dict) -> str: ...
```

Pydantic v2 strict-schema pattern (use this exact shape for both schemas):

```python
from pydantic import BaseModel, ConfigDict, Field

class HouseholdManagerApiArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str = Field(description="HTTP method: GET, POST, PATCH, or DELETE.")
    path: str = Field(description="API path relative to base URL, e.g. /api/recipes.")
    body: dict | None = Field(default=None, description="JSON request body for POST/PATCH; null for GET/DELETE.")
    query: dict | None = Field(default=None, description="URL query parameters; null if none.")
```

Then on the tool class, add (alongside `name`, `description`, `household_id`):

```python
args_schema: type[BaseModel] = HouseholdManagerApiArgs
```

Same pattern for `StartWorkflowArgs` with `workflow_type: str` and
`shared_context: dict = Field(default_factory=dict, ...)` (current `_run` requires it as
positional dict — keep it required, no default).

LangGraph error-path finding (verified during planning, do NOT re-derive — but executor
should sanity-check by reading once before deciding Layer 2):

- langgraph 1.1.3 is installed.
- `langgraph.prebuilt.tool_node.ToolNode._execute_tool_sync` (lines ~928-979) wraps any
  `pydantic.ValidationError` raised by `tool.invoke()` in `ToolInvocationError`, then
  feeds it through `handle_tool_errors`.
- `ToolNode.handle_tool_errors` defaults to `_default_handle_tool_errors`, which RETURNS
  `ToolInvocationError.message` (i.e. emits a `ToolMessage(status="error")`) instead of
  re-raising. Other exception types (incl. unsanitized `TypeError`) ARE re-raised by the
  default handler — but with `args_schema` in place, the tool-arg path raises `ValidationError`
  which IS wrapped, so the default is sufficient.
- `create_react_agent(model=..., tools=[...])` wraps `tools` in a default `ToolNode` with
  the default handler — see `chat_agent_executor.py` line ~560.
- Conclusion: with strict args_schema in Layer 1, no Layer 2 code change is required. The
  agent will see a `ToolMessage(status="error", content="Error: <ValidationError details>...")`
  and self-correct on its next turn. Layer 2 stays as a documented finding, not a code change.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add strict Pydantic args_schema to both dict-arg tools and prove the new behavior with unit tests</name>
  <files>
    src/robotina/agent/tools/household_manager_api.py,
    src/robotina/agent/tools/start_workflow.py,
    tests/unit/test_household_manager_api_tool.py,
    tests/unit/test_start_workflow_tool.py
  </files>
  <behavior>
    For BOTH tools (HouseholdManagerApiTool, StartWorkflowTool):

    - tool.invoke({...valid args, no extras...}) → succeeds, runs `_run` exactly as today.
    - tool.invoke({...valid args + one unknown key...}) → raises pydantic.ValidationError
      (NOT TypeError). The error message names the offending field (e.g. "response").
    - tool.args_schema.model_json_schema() includes `"additionalProperties": false`
      (Pydantic v2's representation of `extra="forbid"`).
    - For HouseholdManagerApiTool: tool.invoke({"method": "GET", "path": "/api/foods"})
      (omitting optional `body` and `query`) still works — strict schema must NOT break the
      optional-default path.

    Plus ONE end-to-end agent-loop test (in test_household_manager_api_tool.py is fine):

    - Build a `create_react_agent` with a stub chat model whose first response is an
      AIMessage containing a tool_call to `household-manager-api` with the EXTRA
      `response: "200"` field, and whose second response is a plain AIMessage (so the loop
      terminates on the next turn). Run `agent.invoke({"messages":[{"role":"user","content":"x"}]})`.
    - Assert the resulting messages list contains a `ToolMessage` with `status == "error"`
      whose `content` mentions the validation error / `response` field — and that the call
      did NOT raise TypeError. Use `langchain_core.language_models.fake_chat_models.GenericFakeChatModel`
      or a small `FakeListChatModel` subclass that yields the canned AIMessages, so the test
      stays hermetic (no Ollama, no httpx).
  </behavior>
  <action>
    Step 1 — Define the Pydantic v2 schemas in their respective tool modules.

    File `src/robotina/agent/tools/household_manager_api.py`:
    - Add imports: `from pydantic import BaseModel, ConfigDict, Field`.
    - Above the `HouseholdManagerApiTool` class, define:

      ```python
      class HouseholdManagerApiArgs(BaseModel):
          """Strict argument schema for HouseholdManagerApiTool.

          extra='forbid' makes any unknown LLM-emitted field raise ValidationError at
          tool.invoke() time, which langgraph ToolNode converts into a ToolMessage the
          agent sees on its next turn. This prevents one LLM hallucination from killing
          the workflow.
          """
          model_config = ConfigDict(extra="forbid")

          method: str = Field(description="HTTP method: GET, POST, PATCH, or DELETE.")
          path: str = Field(description="API path relative to base URL, e.g. /api/recipes.")
          body: dict | None = Field(default=None, description="JSON request body for POST/PATCH; null for GET/DELETE.")
          query: dict | None = Field(default=None, description="URL query parameters; null if none.")
      ```

    - Inside `HouseholdManagerApiTool` (alongside `name`, `description`, `household_id`),
      add:

      ```python
      args_schema: type[BaseModel] = HouseholdManagerApiArgs
      ```

    - Do NOT change `_run` or `_arun` signatures, return types, HTTP behavior, env-var
      reading, or the existing tool description string. The schema is purely an input
      gate. (Keep the JSON-literal guidance text in `description` — Layer 1 hardens
      validation; the description still helps the LLM emit valid args first time.)

    File `src/robotina/agent/tools/start_workflow.py`:
    - Add imports: `from pydantic import BaseModel, ConfigDict, Field`.
    - Above `StartWorkflowTool`, define:

      ```python
      class StartWorkflowArgs(BaseModel):
          """Strict argument schema for StartWorkflowTool. See HouseholdManagerApiArgs for rationale."""
          model_config = ConfigDict(extra="forbid")

          workflow_type: str = Field(description="Workflow identifier, e.g. 'add-recipe'.")
          shared_context: dict = Field(description="Task-specific fields. reply_context and household_id are injected automatically.")
      ```

    - On `StartWorkflowTool`, add `args_schema: type[BaseModel] = StartWorkflowArgs`.
    - Do NOT change `_run`/`_arun`, the `return_direct=True` flag, the auto-inject logic
      for `reply_context`/`household_id`, or any of the WorkflowRun creation logic.

    Step 2 — Sanity-check the langgraph error-path finding before declaring Layer 2 a no-op.

    Read `langgraph.prebuilt.tool_node` once (lines ~928-979 around `_execute_tool_sync`)
    AND `langgraph.prebuilt.chat_agent_executor` (around line 555 where `ToolNode` is
    built from a list). Confirm:

      (i) ValidationError raised at `tool.invoke(call_args, config)` is caught and
          re-raised as `ToolInvocationError` with the validation message included.
      (ii) The default `handle_tool_errors=_default_handle_tool_errors` returns
           `ToolInvocationError.message` (string), so a `ToolMessage(status="error")`
           is produced rather than the exception escaping.

    If both hold (they do, per the planner's read), write NO Layer 2 code. Document the
    finding in the commit body: "Layer 2 not required: langgraph 1.1.3 ToolNode default
    error handler already converts the args-schema ValidationError into a ToolMessage
    the agent sees." If something has changed in the installed version, fall back to
    Layer 2 (b) per task_brief — wrap the agent.invoke() call in jobs.py with a narrow
    `except (TypeError, ValidationError)` that injects a synthesized error message —
    but ONLY in that case. Do not add this code speculatively.

    Step 3 — Add the unit tests. Append to the existing test files (do not create new
    files); follow the style already in use (`monkeypatch`, `unittest.mock`, no live HTTP).

    In `tests/unit/test_household_manager_api_tool.py`, add:
      - test_args_schema_forbids_unknown_field — instantiate the tool with a fake
        household_id, call `tool.invoke({"method": "GET", "path": "/api/foods", "body": None,
        "query": None, "response": "200"})`, assert it raises `pydantic.ValidationError`
        (or its subclass) and that the error message references the unknown field. The
        important assertion is "no TypeError" — wrap with `pytest.raises(ValidationError)`.
      - test_args_schema_allows_optional_omitted — patch httpx as in the existing
        `test_household_manager_api_tool_injects_bearer_token` test, then call
        `tool.invoke({"method": "GET", "path": "/api/foods"})` (no body, no query) and
        assert the request still goes out and the tool returns a result without raising.
      - test_args_schema_json_schema_forbids_extra — assert
        `HouseholdManagerApiTool(household_id="x").args_schema.model_json_schema()
        ["additionalProperties"] is False`.
      - test_extra_field_in_agent_loop_yields_tool_error_message — build a fake chat
        model that returns a canned tool-call AIMessage with the extra `response` field
        on first call and a plain AIMessage on second call. Use
        `langgraph.prebuilt.create_react_agent(model=fake_model, tools=[tool])` directly
        (do NOT pull in OllamaBackend/RetryingChatOllama). Run `agent.invoke({...})`,
        find the `ToolMessage` in the result's `messages`, assert its `status == "error"`
        and its `content` mentions the validation problem ("response" or "extra" or
        "forbid" — pick whichever pydantic v2 actually produces; verify by running the
        test once before asserting). The point of this test is end-to-end proof that
        the workflow does NOT die. If building a hermetic fake chat model proves too
        finicky, this single test may be marked `@pytest.mark.integration` and use a
        smaller scope (e.g. directly call `ToolNode([tool], handle_tool_errors=True)`
        with a hand-built tool_call AIMessage and assert the resulting ToolMessage has
        `status="error"`) — that is acceptable and still proves the behavior.

    In `tests/unit/test_start_workflow_tool.py`, add the same trio (without the agent-loop
    test — one is enough):
      - test_args_schema_forbids_unknown_field
      - test_args_schema_allows_required_only — `tool.invoke({"workflow_type": "add-recipe",
        "shared_context": {"recipe_query": "x"}})` succeeds (mock SessionLocal +
        workflow_runner.queue_workflow as in the existing tests).
      - test_args_schema_json_schema_forbids_extra

    Step 4 — Run the full suite. `uv run pytest tests/ -x` must pass. Any pre-existing
    failure that is unrelated should be left as-is and noted in the SUMMARY; do not
    expand scope.

    CRITICAL — must NOT do:
      - Do not embed the quick-task ID (260509-nru) in any source/test file, comment,
        or docstring. Commit message and planning artifacts only. (CLAUDE.md + memory
        rule "no quick-task IDs in code".)
      - Do not modify `_run` / `_arun` signatures or behavior.
      - Do not modify `web_search.py`, `read_skill.py`, `queue.py`,
        `_RetryingChatOllama`, `workflow_runner`, or `jobs.py` (unless Step 2 forces
        the Layer 2 (b) fallback — and ONLY in that case).
      - Do not add new env vars.
      - Do not edit skill files or system prompts.
      - Do not change the JSON-literal guidance already in either tool description.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/test_household_manager_api_tool.py tests/unit/test_start_workflow_tool.py -x -v</automated>
    <automated>uv run pytest tests/ -x</automated>
    <automated>uv run python -c "from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool; t=HouseholdManagerApiTool(household_id='x'); s=t.args_schema.model_json_schema(); assert s.get('additionalProperties') is False, s; print('hh-api: additionalProperties=false OK')"</automated>
    <automated>uv run python -c "from robotina.agent.tools.start_workflow import StartWorkflowTool; t=StartWorkflowTool(); s=t.args_schema.model_json_schema(); assert s.get('additionalProperties') is False, s; print('start-workflow: additionalProperties=false OK')"</automated>
    <automated>uv run python -c "
import os
os.environ.setdefault('HOUSEHOLD_MANAGER_API_KEY','x')
from pydantic import ValidationError
from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
t=HouseholdManagerApiTool(household_id='x')
try:
    t.invoke({'method':'GET','path':'/api/foods','body':None,'query':None,'response':'200'})
except ValidationError as e:
    print('extra-field rejected (ValidationError) OK:', 'response' in str(e))
except TypeError as e:
    raise SystemExit('FAIL: TypeError leaked instead of ValidationError: '+str(e))
"</automated>
  </verify>
  <done>
    - Both tool modules export an explicit Pydantic v2 args schema with extra='forbid'
      and assign it via `args_schema = ...` on the BaseTool subclass.
    - `_run` / `_arun` signatures and behavior are byte-identical to before.
    - All four targeted unit tests (extra-field rejection, optional-omitted ok,
      json-schema additionalProperties:false) pass on both tools.
    - At least one test demonstrates that the agent loop receives a ToolMessage with
      status='error' instead of TypeError when the LLM emits an unknown field.
    - Full `uv run pytest tests/` passes (or pre-existing failures are unrelated and
      called out in SUMMARY).
    - The two `python -c` schema checks above print success.
    - No quick-task ID anywhere in source/test files.
  </done>
</task>

</tasks>

<verification>
- `uv run pytest tests/` — full suite passes.
- The four schema/extra-field unit tests are present in
  `tests/unit/test_household_manager_api_tool.py` and
  `tests/unit/test_start_workflow_tool.py`.
- Manual reproduction: replaying the staging tool-call payload
  `{'body': None, 'method': 'GET', 'response': '200', 'path': '/api/foods?name=chorizo colorado', 'query': None}`
  against `HouseholdManagerApiTool(household_id='x').invoke(...)` raises `ValidationError`
  rather than `TypeError`.
- `args_schema.model_json_schema()` for both tools reports
  `additionalProperties: False`.
- No Layer 2 code change unless the langgraph 1.1.3 default-handler finding is contradicted
  at execute time — and if so, the SUMMARY explains why and what was added in jobs.py.
</verification>

<success_criteria>
- A future Ollama hallucination of an unknown tool-call field on `household-manager-api`
  or `start-workflow` produces a ToolMessage(status="error") the agent sees on the next
  turn — NOT a `TypeError` that escapes `agent.invoke()` and trips
  `workflow_runner.on_step_failed`.
- Existing valid tool-call paths (including ones omitting optional `body`/`query`) work
  unchanged.
- All existing tests continue to pass; the four new unit tests pass.
- One atomic commit on the source/test changes, message style:
  `fix(agent-tools): strict args_schema on household-manager-api and start-workflow`
  (executor commits source/tests only — orchestrator commits planning docs separately
  per `commit_docs=false`).
</success_criteria>

<output>
After completion, create `.planning/quick/260509-nru-strict-tool-call-args-validation/260509-nru-SUMMARY.md`
covering:
- The two schemas added (with their field shapes).
- Whether Layer 2 was needed (expected: no — document the langgraph 1.1.3 behavior that
  makes Layer 1 sufficient). If yes, document the narrow except-clause that was added.
- The four unit tests added and what each proves.
- Reproduction of the staging failure payload now yielding ValidationError instead of
  TypeError.
- The single source/test commit hash.
</output>
