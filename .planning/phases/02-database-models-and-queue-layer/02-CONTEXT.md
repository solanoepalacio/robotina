# Phase 2: Database Models and Queue Layer - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Define all shared data contracts before any agent is written: four SQLAlchemy 2.x models (Conversation, StoredMessage, WorkflowRun, WorkflowRunStep) exist as a clean Alembic migration, all Pydantic task I/O models are defined and round-trip through pickle serialization, and the RQ worker is verified to process jobs sequentially with the correct retention settings. No agent logic, no gateway wiring, no workflow engine — data contracts and queue verification only.

</domain>

<decisions>
## Implementation Decisions

### Model File Organization
- **D-01:** Split models by domain sub-package: `robotina/gateway/models.py` holds `Conversation` and `StoredMessage`; `robotina/queue/models.py` holds `WorkflowRun` and `WorkflowRunStep`
- **D-02:** Shared SQLAlchemy declarative `Base` lives in `robotina/db.py` (already exists as the migration entry point) — both model files import `Base` from there
- **D-03:** Model field definitions follow the spec verbatim (`plans/01-kickoff/spec.md` §"Conversation History Storage" and §"Workflow Engine") — no field additions or modifications

### Queue State Logging
- **D-04:** Implement a `LoggingWorker(Worker)` subclass in `robotina/queue/runner.py` that overrides `perform_job` to emit structured log lines at job start, finish, and failure — all lifecycle logging centralized in one place, no logging required in individual job functions
- **D-05:** Log format includes job ID, queue name, and task type: `[agent-tasks] job <id> starting | finished | failed`

### Pydantic Task I/O Models
- **D-06 (Claude's Discretion):** All four Pydantic task I/O models (`IncomingMessageInput/Output`, `RecipeResearchInput/Output`, `RecipeLoadInput/Output`, `SendNotificationInput/Output`) live in `robotina/queue/task_types.py` — centralized, imported by queue, agents, and task runner; follows the established sub-package pattern

### RQ Verification
- **D-07 (Claude's Discretion):** Verification uses an integration test (requires live Redis) that enqueues a trivial no-op job, asserts it completes with `result_ttl=-1`/`failure_ttl=-1`, and confirms the job appears in the finished registry; mirrors the Phase 1 approach of testing against the real stack

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### SQLAlchemy model schemas (verbatim field definitions)
- `plans/01-kickoff/spec.md` §"Conversation History Storage" — `Conversation` and `StoredMessage` field definitions, unique constraints, relationships
- `plans/01-kickoff/spec.md` §"Workflow Engine" — `WorkflowRun` and `WorkflowRunStep` field definitions, status enums, `shared_context` and `artifact` JSON columns

### Pydantic task I/O model schemas
- `plans/01-kickoff/spec.md` §"Shared models" — all four input/output Pydantic v2 models with field types and `RecipeData` nested model

### Requirements
- `.planning/REQUIREMENTS.md` §QUEUE-01 through QUEUE-07 — acceptance criteria for queue layer
- `.planning/REQUIREMENTS.md` §WF-01 — acceptance criteria for WorkflowRun/WorkflowRunStep models

### Phase 1 patterns
- `.planning/phases/01-developer-tooling-and-infrastructure/01-CONTEXT.md` — package layout decisions (D-01, D-02), queue name `agent-tasks`, `result_ttl=-1`/`failure_ttl=-1` mandate

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/robotina/db.py` — already exists as the Alembic migration entrypoint; will be extended to declare the shared `Base` and expose the `engine`/session factory for model imports
- `src/robotina/queue/runner.py` — worker entrypoint that starts `Worker([queue])` against `agent-tasks`; will be refactored to use `LoggingWorker` subclass
- `src/robotina/gateway/__init__.py`, `src/robotina/queue/__init__.py` — sub-packages exist (empty); model files slot directly in

### Established Patterns
- SQLAlchemy 2.x `Mapped` + `mapped_column` style is mandated (CLAUDE.md); no 1.x `Column` style
- Pydantic v2 exclusively — `BaseModel` with `list[...]`, `Literal[...]` annotations (no v1 syntax)
- `uv run migrate` runs `alembic upgrade head`; new models require a new migration added to `alembic/versions/`

### Integration Points
- `Alembic env.py` was fully rewritten in Phase 1 (includes `sys.path` injection and `DATABASE_URL` override); new models must be imported in `env.py` `target_metadata` so Alembic detects them
- `runner.py` `Worker` instantiation becomes `LoggingWorker` — no other changes to the worker startup flow
- `task_types.py` will be imported by Phase 4 (agents registry) and Phase 5 (task runner workflow engine) — keep it at `robotina/queue/task_types.py`

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-database-models-and-queue-layer*
*Context gathered: 2026-03-25*
