# Phase 16: Fix empty-string household_id propagation through gateway and workflow_run - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Stop empty-string `household_id` from silently propagating from a missing `HOUSEHOLD_ID` env var through `Conversation`, `IncomingMessageInput`, `WorkflowRun`, `StartWorkflowTool`, and `HouseholdManagerApiTool`. After this phase:

- Gateway refuses to start if `HOUSEHOLD_ID` is unset/empty (RuntimeError at module import).
- Task-input Pydantic models reject empty `household_id` at construction.
- `HouseholdManagerApiTool` and `queue_workflow` raise on empty `household_id`.
- `HOUSEHOLD_ID` is documented in `.env.example`.

Out of scope: multi-household support, per-household API keys, migrating existing DB rows that already have `household_id=""`.

</domain>

<decisions>
## Implementation Decisions

### Failure Strategy
- Validate at both layers: gateway entry (fail-fast on missing env) **and** Pydantic field-level validators on task-input models — belt-and-suspenders.
- Gateway reaction on unset/empty `HOUSEHOLD_ID`: raise `RuntimeError` at handler module import — process refuses to start with a clear error.
- Add `HOUSEHOLD_ID` to `.env.example` with placeholder value and a one-line comment (per the "always update .env.example" rule).
- No data migration for existing DB rows with `household_id=""`. They are dev artifacts; the fix prevents new ones.

### Defensive Validation
- Use `Field(min_length=1)` on every task-input model field that carries `household_id` — declarative, raises `ValidationError` at construction.
- `HouseholdManagerApiTool.__init__` raises `ValueError` on empty `household_id`.
- `queue_workflow` raises on empty `household_id` so no `WorkflowRun` row is ever written with `""`.
- Tests: unit tests for each validator + one gateway-level test that confirms missing `HOUSEHOLD_ID` raises `RuntimeError`.

### Scope
- Do **not** centralize env reading into a helper. Single-line `os.environ[...]` in the gateway is enough — avoids premature abstraction (per established preference). Fail-fast via `os.environ["HOUSEHOLD_ID"]` (bracket form, not `.get()`).
- Audit `src/robotina/gateway/send.py` for `HOUSEHOLD_ID` — the docstring references it but the code path does not appear to use it. Remove the stale docstring line.
- Sweep `tests/` for empty-string `household_id` fixtures; replace with a placeholder UUID (`"test-household"` or similar) so future tests don't accidentally pass empty.
- Add one Key Decision entry to `PROJECT.md`: "`household_id` is required end-to-end and validated at gateway, Pydantic models, and tool construction."

### Claude's Discretion
- Exact placeholder value in `.env.example` (e.g. `HOUSEHOLD_ID=replace-with-your-household-uuid`).
- Exact wording of the gateway `RuntimeError` message — should make the cause obvious to an operator skimming logs.
- Whether validation uses `Field(min_length=1)` directly per-model or a single `NonEmptyStr = Annotated[str, Field(min_length=1)]` alias — pick whichever yields cleaner Pydantic model definitions.

</decisions>

<code_context>
## Existing Code Insights

### Affected Files
- `src/robotina/gateway/handler.py:43` — current bug: `os.environ.get("HOUSEHOLD_ID", "")`.
- `src/robotina/gateway/send.py:12` — docstring references `HOUSEHOLD_ID`; code path doesn't actually use it (audit).
- `src/robotina/gateway/models.py:34` — `Conversation.household_id` column is `nullable=False` but accepts empty string today.
- `src/robotina/queue/models.py:32` — `WorkflowRun.household_id` column is `nullable=False`, accepts empty string today.
- `src/robotina/queue/task_types.py` — `IncomingMessageInput`, `RecipeResearchInput`, `RecipeLoadInput`, etc. all have `household_id: str` with no length constraint.
- `src/robotina/agent/tools/household_manager_api.py` — `HouseholdManagerApiTool(household_id=...)` constructor.
- `src/robotina/agent/tools/start_workflow.py:99` — `StartWorkflowTool.household_id: str = ""` default.
- `src/robotina/queue/workflow_runner.py:107` — `queue_workflow(household_id: str, ...)` parameter.

### Established Patterns
- Per-job objects instantiated inside `run_task()`, never at module level (Phase 4 decision) — gateway env-var check at module import is fine because gateway is its own long-lived process, not a per-job object.
- Pydantic v2 with declarative `Field(...)` constraints (used in task_types.py).
- `.env.example` is required to stay in sync with code (memory: `feedback_env_example.md`).

### Integration Points
- Gateway is the only entry point that reads `HOUSEHOLD_ID` from env. All downstream consumers receive it via `IncomingMessageInput.household_id` and propagate via `shared_context["household_id"]`.

</code_context>

<specifics>
## Specific Ideas

- The bug surfaces as confusing 4xx responses from household-manager backend. The fix should make the misconfiguration loud at startup, not silent until the first API call.
- Bracket-form `os.environ["HOUSEHOLD_ID"]` at module import achieves fail-fast for free — no extra validation code needed.

</specifics>

<deferred>
## Deferred Ideas

- Multi-household support (still out of scope per PROJECT.md).
- Centralized `get_household_id()` helper — premature; revisit if a third call site appears.
- DB-level CHECK constraints for non-empty `household_id` — Pydantic + tool validation is enough; revisit if bypass paths emerge.

</deferred>
