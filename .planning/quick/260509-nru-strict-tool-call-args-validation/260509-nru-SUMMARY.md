---
quick_id: 260509-nru
slug: strict-tool-call-args-validation
type: execute
wave: 1
status: complete
files_modified:
  - src/robotina/agent/tools/household_manager_api.py
  - src/robotina/agent/tools/start_workflow.py
  - tests/unit/test_household_manager_api_tool.py
  - tests/unit/test_start_workflow_tool.py
tests_added: 7
tests_passing: 151
tests_deselected_integration: 14
duration_min: ~25
---

# Quick Task 260509-nru — Strict tool-call args validation

**One-liner:** Added Pydantic v2 ``args_schema`` with ``extra='forbid'`` to ``HouseholdManagerApiTool`` and ``StartWorkflowTool`` so a hallucinated extra LLM-emitted field becomes a recoverable ``ToolMessage(status='error')`` instead of a workflow-killing ``TypeError``.

## Problem

Reproduces staging failure ``workflow_run_id=803da0b0-5512-4152-b689-77b0241ca7c3``:
the Ollama agent emitted a tool call to ``household-manager-api`` with an extra
``response: "200"`` argument. With no explicit ``args_schema``, langchain's
``BaseTool.invoke()`` derived the schema from ``_run``'s signature, which
accepted ``**kwargs`` semantics loosely — the extra key was forwarded as a
kwarg to ``_run``, producing:

    TypeError: HouseholdManagerApiTool._run() got an unexpected keyword argument 'response'

That ``TypeError`` escaped ``agent.invoke()`` and tripped
``workflow_runner.on_step_failed``, which cancelled the three pending workflow
steps. One LLM hallucination → terminal workflow death.

## Fix (Layer 1 — strict args_schema)

Both tools now declare an explicit Pydantic v2 schema with ``extra='forbid'``
and assign it via ``args_schema`` on the ``BaseTool`` subclass. This intercepts
unknown keys at ``tool.invoke()`` time and raises ``pydantic.ValidationError``
**before** ``_run`` is ever called.

### `HouseholdManagerApiTool` — `HouseholdManagerApiArgs`

```python
class HouseholdManagerApiArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str = Field(description="HTTP method: GET, POST, PATCH, or DELETE.")
    path: str = Field(description="API path relative to base URL, e.g. /api/recipes.")
    body: dict | None = Field(default=None, description="JSON request body for POST/PATCH; null for GET/DELETE.")
    query: dict | None = Field(default=None, description="URL query parameters; null if none.")
```

### `StartWorkflowTool` — `StartWorkflowArgs`

```python
class StartWorkflowArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_type: str = Field(description="Workflow identifier, e.g. 'add-recipe'.")
    shared_context: dict = Field(description="Task-specific fields ... reply_context and household_id are injected automatically.")
```

`_run` / `_arun` signatures, return types, HTTP behavior, JSON-literal
guidance in the tool descriptions, the `return_direct=True` flag on
`StartWorkflowTool`, and the auto-inject logic for `reply_context`/`household_id`
are all unchanged. The schema is purely an input gate.

## Layer 2 — confirmed NOT needed

The PLAN's `<context>` finding was empirically validated at execute time by
reading the installed langgraph 1.1.3 source:

- `langgraph.prebuilt.tool_node.ToolNode._execute_tool_sync`
  (`tool_node.py:928-938`) catches `pydantic.ValidationError` raised by
  `tool.invoke()` and re-raises it as `ToolInvocationError`.
- The outer `except Exception` block (`tool_node.py:951-979`) calls
  `_handle_tool_error` which (with the default `handle_tool_errors=True`)
  returns a `ToolMessage(content=..., status="error", ...)` rather than
  letting the exception escape.
- `langgraph.prebuilt.chat_agent_executor.create_react_agent`
  (`chat_agent_executor.py:560`) constructs a default `ToolNode([...])`,
  which uses `handle_tool_errors=True` by default.

Net effect: with strict `args_schema` in place, an extra-field tool call
produces a `ToolMessage(status="error")` the agent sees on its next turn —
exactly the desired behavior — with **zero changes** to `jobs.py` or any
other layer. No `try/except (TypeError, ValidationError)` was added around
`agent.invoke(...)`.

The end-to-end behavior was verified by the load-bearing unit test
`test_extra_field_in_agent_loop_yields_tool_error_message` (see below).

## Tests added (7)

In `tests/unit/test_household_manager_api_tool.py` (4 new):

| Test | Proves |
|------|--------|
| `test_args_schema_forbids_unknown_field` | Extra arg `response` raises `pydantic.ValidationError` (not `TypeError`); error message names the field. |
| `test_args_schema_allows_optional_omitted` | Strict schema doesn't break the optional-defaults path: `tool.invoke({"method":"GET","path":"/api/foods"})` still works. |
| `test_args_schema_json_schema_forbids_extra` | `args_schema.model_json_schema()["additionalProperties"] is False` (Pydantic v2's representation of `extra="forbid"`, the schema LLM tool-binding adapters serialize). |
| `test_extra_field_in_agent_loop_yields_tool_error_message` | **Load-bearing.** Drives the bad tool call through a real `create_react_agent` with a `FakeMessagesListChatModel` stub; asserts the result contains a `ToolMessage(status="error")` whose content references the validation problem, and `agent.invoke()` does NOT raise `TypeError`. |

In `tests/unit/test_start_workflow_tool.py` (3 new):

| Test | Proves |
|------|--------|
| `test_args_schema_forbids_unknown_field` | Extra arg `response` raises `pydantic.ValidationError` (not `TypeError`); error message names the field. |
| `test_args_schema_allows_required_only` | Strict schema doesn't break the happy path: `tool.invoke({"workflow_type":"add-recipe","shared_context":{...}})` still queues the workflow. |
| `test_args_schema_json_schema_forbids_extra` | `args_schema.model_json_schema()["additionalProperties"] is False`. |

(The agent-loop end-to-end assertion is on the `HouseholdManagerApiTool` test
because it's the same code path — one such test is sufficient.)

## Reproduction of the staging failure (now ValidationError)

```python
>>> import os
>>> os.environ['HOUSEHOLD_MANAGER_API_KEY'] = 'x'
>>> from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
>>> t = HouseholdManagerApiTool(household_id='hh-staging')
>>> # Exact payload from staging workflow_run_id=803da0b0-5512-...
>>> t.invoke({'body': None, 'method': 'GET', 'response': '200',
...            'path': '/api/foods?name=chorizo colorado', 'query': None})
pydantic_core._pydantic_core.ValidationError: 1 validation error for HouseholdManagerApiArgs
response
  Extra inputs are not permitted [type=extra_forbidden, input_value='200', input_type=str]
```

Pre-fix: `TypeError: HouseholdManagerApiTool._run() got an unexpected keyword argument 'response'`
→ workflow died, 3 steps cancelled.
Post-fix: `ValidationError` → wrapped by langgraph `ToolNode` →
`ToolMessage(status="error", content="... response: Extra inputs are not permitted ...")`
→ agent self-corrects on its next turn.

## Verification results

- ``uv run pytest tests/unit/test_household_manager_api_tool.py tests/unit/test_start_workflow_tool.py -x -v`` → **20 passed** (13 existing + 7 new).
- ``uv run pytest tests/ -m "not integration"`` → **151 passed, 14 deselected**.
- 14 deselected = pre-existing integration tests in ``tests/test_db_models.py`` and ``tests/test_gateway.py`` that require a live Postgres on ``localhost:5432``. All marked ``@pytest.mark.integration``. They are unaffected by this change (they don't even import the modified tools).
- ``uv run python -c "from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool; t=HouseholdManagerApiTool(household_id='x'); print(t.args_schema.model_json_schema()['additionalProperties'])"`` → ``False``.
- ``uv run python -c "from robotina.agent.tools.start_workflow import StartWorkflowTool; t=StartWorkflowTool(); print(t.args_schema.model_json_schema()['additionalProperties'])"`` → ``False``.

## Deviations from plan

None. Layer 1 only, exactly as the plan recommended. No Layer 2 code added.

## Out-of-scope items NOT touched

Per PLAN ``<critical_constraints>``: ``web_search.py``, ``read_skill.py``,
``queue.py``, ``_RetryingChatOllama``, ``workflow_runner.py``, ``jobs.py``,
skill files, and system prompts were all left untouched. No env vars added.
``_run``/``_arun`` signatures and HTTP behavior unchanged.

## Commit

Source + tests committed in ONE atomic commit:

- ``f12c56b`` — ``fix(agent-tools): strict args_schema on household-manager-api and start-workflow``

(Docs commit — STATE.md, this SUMMARY.md, and the PLAN.md — is handled
separately by the orchestrator per ``commit_docs=false``.)

## Self-Check: PASSED

- All 4 source/test files modified and present in the worktree.
- SUMMARY.md created at the expected path.
- Commit ``f12c56b`` exists in ``git log``.
- No quick-task ID present in any source/test file or its docstrings/comments.
- No unexpected deletions in the commit (``git diff --diff-filter=D HEAD~1 HEAD`` empty).
- Working tree clean after commit.
