---
phase: 260518-ksv-tighten-startworkflowtool-schema-flatten
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/robotina/agent/tools/start_workflow.py
  - tests/unit/test_start_workflow_tool.py
autonomous: true
requirements:
  - QUICK-SW-01  # Flatten StartWorkflowArgs to top-level recipe_query
  - QUICK-SW-02  # Constrain workflow_type to Literal["add-recipe"]
  - QUICK-SW-03  # Preserve WR-02 trust boundary (constructor authoritative)

must_haves:
  truths:
    - "LLM cannot omit recipe_query — Pydantic ValidationError fires before _run if absent."
    - "LLM cannot pass a workflow_type other than 'add-recipe' — Literal narrows the JSON schema enum."
    - "LLM cannot inject household_id / reply_context via tool args — extra='forbid' rejects them at the top level (the old shared_context dict surface is gone)."
    - "Constructor-injected household_id / chat_id / user_id / platform remain authoritative (WR-02 invariant preserved)."
    - "Happy-path tool call with workflow_type='add-recipe' + recipe_query='...' still returns the workflow_run_id string."
    - "return_direct=True is unchanged — terminal-tool semantics intact."
    - "uv run pytest tests/unit/test_start_workflow_tool.py passes."
  artifacts:
    - path: "src/robotina/agent/tools/start_workflow.py"
      provides: "StartWorkflowTool with tightened args schema"
      contains: "Literal[\"add-recipe\"]"
    - path: "src/robotina/agent/tools/start_workflow.py"
      provides: "StartWorkflowArgs without shared_context dict"
      contains: "recipe_query: str"
    - path: "tests/unit/test_start_workflow_tool.py"
      provides: "Tests updated for flat schema"
      contains: "recipe_query="
  key_links:
    - from: "StartWorkflowTool._run"
      to: "workflow_runner.queue_workflow"
      via: "internally-built shared_context dict"
      pattern: "shared_context\\s*=\\s*\\{"
    - from: "StartWorkflowArgs"
      to: "JSON schema surfaced to the LLM"
      via: "Literal narrowing + extra='forbid'"
      pattern: "additionalProperties.*false"
---

<objective>
Tighten the StartWorkflowTool input schema so structural failures surface in the
Pydantic args-validation layer rather than at downstream WORKFLOW_REGISTRY
lookup or as a silent missing-key KeyError.

Two independent tightenings against the same model:

1. Flatten `shared_context: dict` → top-level required `recipe_query: str`.
2. Constrain `workflow_type` → `Literal["add-recipe"]`.

`_run()` now reconstructs the `shared_context` dict internally from
`recipe_query` plus the constructor-injected `reply_context` / `household_id`.
The LLM-facing schema no longer accepts ANY free-form dict — the entire
LLM-controlled identity-injection surface (the WR-02 attack surface) is
eliminated structurally.

Purpose: With `return_direct=True`, an args ValidationError terminates the
agent run with no retry. The schema must make the required shape obvious to
the LLM, and it must fail loudly and structurally on misuse rather than
silently downstream.

Output: Tightened `StartWorkflowArgs`, updated tool description, updated
`_run` / `_arun` signatures, and updated unit tests.
</objective>

<execution_context>
@/home/solanoe/code/robotina-gsd/.claude/get-shit-done/workflows/execute-plan.md
@/home/solanoe/code/robotina-gsd/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.planning/STATE.md
@src/robotina/agent/tools/start_workflow.py
@src/robotina/agent/workflows.py
@tests/unit/test_start_workflow_tool.py

<interfaces>
<!-- Key contracts. The plan creates everything it needs; these are the
     downstream consumers that must keep working unchanged. -->

WORKFLOW_REGISTRY (src/robotina/agent/workflows.py) — the "add-recipe"
workflow's first build_input callable expects:
```python
ctx["recipe_query"]      # str
ctx["reply_context"]     # dict[platform, chat_id, user_id]
ctx["household_id"]      # str
```
The internally-constructed shared_context dict in StartWorkflowTool._run
MUST continue to satisfy this contract.

workflow_runner.queue_workflow signature (unchanged):
```python
def queue_workflow(
    *, workflow_type: str, shared_context: dict,
    household_id: str, queue, session,
) -> str
```

Constructor fields (unchanged — WR-02 trust boundary):
```python
chat_id: str = ""
user_id: str = ""
platform: str = ""
household_id: NonEmptyHouseholdId  # required, non-empty
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Tighten StartWorkflowArgs and refactor _run / _arun</name>
  <files>src/robotina/agent/tools/start_workflow.py</files>
  <action>
Edit `src/robotina/agent/tools/start_workflow.py` to flatten the LLM-facing
schema and restrict `workflow_type` to a Literal.

1. Imports: add `Literal` from `typing` at the top of the module.

2. Replace `StartWorkflowArgs` body so it reads:
   ```python
   class StartWorkflowArgs(BaseModel):
       """Strict argument schema for StartWorkflowTool.

       Two structural guardrails enforced at args-validation time (before
       _run is called), so misuse surfaces as a ToolMessage(status='error')
       the engine terminates on (return_direct=True), not as a downstream
       KeyError or registry miss:

       1. workflow_type is a Literal — only 'add-recipe' validates. A
          hallucinated name fails here, not at WORKFLOW_REGISTRY lookup.
       2. recipe_query is a required top-level string. The old
          shared_context dict surface — which let the LLM (a) omit
          recipe_query entirely and (b) attempt to shadow the trusted
          household_id / reply_context via WR-02 — is gone.

       ``extra='forbid'`` keeps any unknown LLM-emitted field at the top
       level as a ValidationError (e.g. an LLM cannot now inject
       household_id at the top level either).
       """

       model_config = ConfigDict(extra="forbid")

       workflow_type: Literal["add-recipe"] = Field(
           description=(
               "Workflow identifier. Currently only 'add-recipe' is supported."
           ),
       )
       recipe_query: str = Field(
           description=(
               "User's recipe request in natural language (e.g. 'lentil soup', "
               "'carbonara'). Forwarded to the add-recipe workflow."
           ),
       )
   ```
   Do NOT add a `min_length=1` constraint to `recipe_query` — out of scope;
   the existing tool also did not validate emptiness on shared_context's
   inner string.

3. Rewrite the tool `description` attribute to match the new schema. Drop
   every mention of `shared_context`. New text:
   ```python
   description: str = (
       "Initiate a multi-step workflow. Creates a WorkflowRun and enqueues "
       "the first step.\n"
       "Args:\n"
       "  workflow_type (str): Workflow name. Only 'add-recipe' is supported.\n"
       "  recipe_query (str): User's recipe request in natural language "
       "(e.g. 'lentil soup').\n"
       "reply_context and household_id are injected automatically by the "
       "runtime — do not pass them.\n"
       "Arguments are passed as JSON. Use JSON literals: null (not None or "
       "none), true/false (not True/False). Strings must use double quotes. "
       "Example: {\"workflow_type\": \"add-recipe\", \"recipe_query\": "
       "\"lentil soup\"}."
   )
   ```

4. Update the class docstring `Args (via _run):` block to describe
   `workflow_type` and `recipe_query` (no more `shared_context`). Keep the
   existing "reply_context auto-injection" paragraph but rewrite it so it
   refers to the internally-constructed dict rather than an LLM-supplied
   one. Keep the `return_direct=True` paragraph as-is.

5. Replace `_run` to take `recipe_query` instead of `shared_context`. The
   new body builds the dict internally:
   ```python
   def _run(self, workflow_type: str, recipe_query: str) -> str:
       from redis import Redis
       from rq import Queue

       from robotina.db import SessionLocal
       from robotina.queue import workflow_runner

       # Build shared_context internally from the LLM-supplied recipe_query
       # plus the constructor-injected identity fields. The LLM no longer
       # supplies a free-form dict, so the WR-02 shadowing attack surface
       # (LLM-supplied household_id / reply_context) is eliminated
       # structurally — there is nothing for the LLM to overwrite.
       shared_context: dict = {
           "recipe_query": recipe_query,
           "reply_context": {
               "platform": self.platform,
               "chat_id": self.chat_id,
               "user_id": self.user_id,
           },
           "household_id": self.household_id,
       }

       # Use the constructor value directly — avoid the dict round-trip so
       # a future refactor that reorders the build above doesn't silently
       # re-introduce an LLM-controlled path.
       household_id = self.household_id
       session = SessionLocal()
       try:
           queue = Queue(
               "agent-tasks",
               connection=Redis.from_url(
                   os.environ.get("REDIS_URL", "redis://localhost:6379")
               ),
           )
           workflow_run_id = workflow_runner.queue_workflow(
               workflow_type=workflow_type,
               shared_context=shared_context,
               household_id=household_id,
               queue=queue,
               session=session,
           )
           logger.info(
               "queue-workflow tool | workflow_type=%s run_id=%s",
               workflow_type,
               workflow_run_id,
           )
           return f"Workflow started. workflow_run_id={workflow_run_id}"
       except Exception as exc:
           logger.error(
               "start-workflow tool | workflow_type=%s error=%s",
               workflow_type,
               exc,
           )
           return f"Workflow start failed: {exc}"
       finally:
           session.close()
   ```

6. Update `_arun` signature to match:
   ```python
   async def _arun(self, workflow_type: str, recipe_query: str) -> str:
       return self._run(workflow_type, recipe_query)
   ```

Note on Literal + Pydantic v2 + create_agent: `Literal["add-recipe"]` becomes
`enum: ["add-recipe"]` in the model_json_schema, which is exactly the surface
the LangChain 1.x `create_agent` tool-call path serializes to the model. No
manual JSON-schema munging required.
  </action>
  <verify>
    <automated>uv run python -c "from robotina.agent.tools.start_workflow import StartWorkflowTool, StartWorkflowArgs; import json; s = StartWorkflowArgs.model_json_schema(); print(json.dumps(s, indent=2))" | grep -E "(recipe_query|add-recipe|additionalProperties|shared_context)"</automated>
  </verify>
  <done>
    - `StartWorkflowArgs` exports two fields: `workflow_type: Literal["add-recipe"]` and `recipe_query: str`.
    - No `shared_context` field on the args model.
    - `additionalProperties: false` still present in `model_json_schema()`.
    - JSON schema's `workflow_type` carries `enum: ["add-recipe"]` (or `const: "add-recipe"` — both are acceptable Pydantic v2 emissions for a single-value Literal).
    - `_run(self, workflow_type, recipe_query)` builds shared_context internally; constructor `household_id` / `chat_id` / `user_id` / `platform` are the sole sources of identity (WR-02 preserved).
    - `_arun` signature mirrors `_run`.
    - Tool `description` no longer mentions `shared_context`.
    - `return_direct = True` unchanged.
  </done>
</task>

<task type="auto">
  <name>Task 2: Update tests for the flat schema</name>
  <files>tests/unit/test_start_workflow_tool.py</files>
  <action>
Rewrite the tests in `tests/unit/test_start_workflow_tool.py` to match the
new top-level `recipe_query` schema and the narrowed `workflow_type`.

Per-test changes (keep the rest of each test body unchanged unless noted):

1. `test_start_workflow_tool_is_terminal_via_return_direct` — no change.

2. `test_start_workflow_tool_returns_workflow_run_id_on_success` — replace
   the `tool._run(...)` call args:
   - OLD: `tool._run(workflow_type="add-recipe", shared_context={"recipe_query": "carbonara"})`
   - NEW: `tool._run(workflow_type="add-recipe", recipe_query="carbonara")`

3. `test_start_workflow_tool_error_path_returns_string` — this test
   currently passes `workflow_type="nonexistent"` to force the
   `workflow_runner.queue_workflow` side_effect. Under the new schema,
   `workflow_type="nonexistent"` would not fail at `_run` boundary (we're
   calling `_run` directly, bypassing args validation), so the existing
   `side_effect=ValueError("unknown workflow_type")` still drives the
   error path. Update only the call shape:
   - OLD: `tool._run(workflow_type="nonexistent", shared_context={})`
   - NEW: `tool._run(workflow_type="nonexistent", recipe_query="anything")`
   Keep the `side_effect` and the final assertions as-is.

4. `test_start_workflow_tool_auto_injects_reply_context` — replace the call
   args and keep the captured-shared_context assertions, which still hold
   because the dict is now built internally with the same keys:
   - OLD: `tool._run(workflow_type="add-recipe", shared_context={"recipe_query": "pasta"})`
   - NEW: `tool._run(workflow_type="add-recipe", recipe_query="pasta")`
   The `shared["recipe_query"] == "pasta"`, `shared["reply_context"] ==
   {...}`, and `shared["household_id"] == "house-1"` assertions remain.

5. `test_start_workflow_tool_short_circuits_create_agent` — update the
   stub tool_calls args:
   - OLD: `"args": {"workflow_type": "add-recipe", "shared_context": {"recipe_query": "carbonara"}}`
   - NEW: `"args": {"workflow_type": "add-recipe", "recipe_query": "carbonara"}`

6. `test_start_workflow_tool_description_no_prompt_level_stop_hack` — no
   change to assertions. Add one additional assertion to lock in the new
   description shape:
   ```python
   assert "shared_context" not in tool.description.lower()
   ```

7. `test_args_schema_forbids_unknown_field` — update `bad_args`:
   - OLD:
     ```python
     bad_args = {
         "workflow_type": "add-recipe",
         "shared_context": {"recipe_query": "carbonara"},
         "response": "200",
     }
     ```
   - NEW:
     ```python
     bad_args = {
         "workflow_type": "add-recipe",
         "recipe_query": "carbonara",
         "response": "200",  # hallucinated extra field
     }
     ```

8. `test_args_schema_allows_required_only` — update the `tool.invoke({...})`
   payload:
   - OLD: `{"workflow_type": "add-recipe", "shared_context": {"recipe_query": "carbonara"}}`
   - NEW: `{"workflow_type": "add-recipe", "recipe_query": "carbonara"}`

9. `test_args_schema_json_schema_forbids_extra` — no change.

10. `test_constructor_rejects_empty_household_id` /
    `test_constructor_requires_household_id_no_default` /
    `test_constructor_accepts_non_empty_household_id` — no change.

11. ADD a new test that replaces the now-impossible WR-02-via-shared_context
    attack — the new attack surface is "LLM tries to pass `household_id`
    or `reply_context` at the TOP level," which `extra='forbid'` must
    reject. Add at the end of the file:
    ```python
    def test_args_schema_rejects_top_level_household_id():
        """Phase quick (260518-ksv): the LLM cannot smuggle identity fields
        via the flat schema either — extra='forbid' rejects top-level
        household_id / reply_context. The old WR-02 attack surface (LLM
        supplying these inside shared_context) is structurally eliminated;
        this test guards the replacement surface."""
        import pytest
        from pydantic import ValidationError

        from robotina.agent.tools.start_workflow import StartWorkflowTool

        tool = StartWorkflowTool(
            chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
        )

        for hostile_field, hostile_value in [
            ("household_id", "attacker-house"),
            ("reply_context", {"platform": "telegram", "chat_id": "evil", "user_id": "evil"}),
        ]:
            bad_args = {
                "workflow_type": "add-recipe",
                "recipe_query": "carbonara",
                hostile_field: hostile_value,
            }
            with pytest.raises(ValidationError) as exc_info:
                tool.invoke(bad_args)
            assert hostile_field in str(exc_info.value)
    ```

12. ADD a Literal-narrowing test (guards the workflow_type tightening):
    ```python
    def test_args_schema_rejects_unknown_workflow_type():
        """Phase quick (260518-ksv): workflow_type is Literal['add-recipe'];
        any other value must fail at args validation, not at WORKFLOW_REGISTRY
        lookup. This catches LLM hallucinations like 'remove-recipe' or
        'shopping-list' before they reach the queue."""
        import pytest
        from pydantic import ValidationError

        from robotina.agent.tools.start_workflow import StartWorkflowTool

        tool = StartWorkflowTool(
            chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
        )

        bad_args = {
            "workflow_type": "remove-recipe",  # not in the Literal
            "recipe_query": "carbonara",
        }
        with pytest.raises(ValidationError) as exc_info:
            tool.invoke(bad_args)
        assert "workflow_type" in str(exc_info.value)
    ```

Do NOT delete any existing tests except where their semantics no longer
exist; the dict-shadowing attack test was implicit in
`test_start_workflow_tool_auto_injects_reply_context` (which proved the
constructor wins over an empty dict) — the new equivalent is the
top-level-rejection test above. The auto-injection test still proves
the constructor values flow into the dict, so it stays.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/test_start_workflow_tool.py -v</automated>
  </verify>
  <done>
    - All previously passing tests in `tests/unit/test_start_workflow_tool.py` still pass after the schema change.
    - Two new tests pass: `test_args_schema_rejects_top_level_household_id` and `test_args_schema_rejects_unknown_workflow_type`.
    - No test still references `shared_context=` as a kwarg or dict key passed to the tool.
    - `uv run pytest tests/unit/test_start_workflow_tool.py` exits 0.
  </done>
</task>

</tasks>

<verification>
1. `uv run pytest tests/unit/test_start_workflow_tool.py` — full module passes.
2. `grep -nE "shared_context\s*[:=]" src/robotina/agent/tools/start_workflow.py` — the only matches are inside `_run` (internal dict construction + `workflow_runner.queue_workflow(shared_context=...)`); the args schema and method signatures have none.
3. `grep -n "shared_context" tests/unit/test_start_workflow_tool.py` — only matches are the assertion lines reading from the captured `captured["shared_context"]` dict (downstream contract, unchanged).
4. Smoke: `uv run python -c "from robotina.agent.tools.start_workflow import StartWorkflowArgs; StartWorkflowArgs(workflow_type='add-recipe', recipe_query='x')"` exits 0; `... workflow_type='remove-recipe' ...` raises ValidationError.
</verification>

<success_criteria>
- LLM-facing args schema is `{workflow_type: Literal["add-recipe"], recipe_query: str}` with `extra='forbid'`.
- Tool description text matches the new schema and contains no mention of `shared_context`.
- `_run` / `_arun` accept `(workflow_type, recipe_query)`; the `shared_context` dict is constructed internally with the constructor-injected identity fields as the sole source of `household_id` and `reply_context` (WR-02 preserved structurally — there is no LLM-supplied dict for the constructor to fight with).
- `return_direct=True` and the constructor's `NonEmptyHouseholdId` validation are unchanged.
- All updated and newly-added unit tests pass under `uv run pytest tests/unit/test_start_workflow_tool.py`.
- `WORKFLOW_REGISTRY` and `workflow_runner.queue_workflow` are not modified.
</success_criteria>

<output>
After completion, create `.planning/quick/260518-ksv-tighten-startworkflowtool-schema-flatten/260518-ksv-SUMMARY.md`.
</output>
