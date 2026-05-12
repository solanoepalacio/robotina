# Phase 5: Task Runner and Workflow Engine - Research

**Researched:** 2026-03-26
**Domain:** RQ job orchestration, SQLAlchemy workflow state management, LangChain BaseTool, Python transactional advancement pattern
**Confidence:** HIGH

## Summary

Phase 5 wires workflow orchestration into the existing task runner. All foundational pieces already exist: `WorkflowRun` and `WorkflowRunStep` SQLAlchemy models (Phase 2), `run_task()` entry point in `jobs.py` (Phase 4), and the full set of task I/O types in `task_types.py`. This phase adds three new source files (`workflows.py`, `queue/workflow_runner.py`, `agent/tools/start_workflow.py`) and modifies `run_task()` and `agents.py`.

The architectural pattern is a centralized orchestrator: agents know nothing about sequences, the task runner wraps every job execution with lightweight workflow state hooks, and advancement (enqueue next step) happens transactionally within the same Postgres commit. This is a well-established pattern for sequential task queue systems and the entire design is locked in CONTEXT.md with no discretionary architecture choices remaining.

The single previously-flagged blocker — whether RQ supports pre-assigned `job_id` — is now confirmed verified. `Queue.enqueue(..., job_id=pre_id)` correctly assigns the job ID before enqueueing, enabling the transactional advancement pattern. RQ 2.7.0 is installed (above the 2.5 minimum).

**Primary recommendation:** Implement the three new modules and the `run_task()` hook exactly as specified in CONTEXT.md decisions D-01 through D-13. No architectural decisions remain open.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `WorkflowDefinition` and `WorkflowStepDef` live in `src/robotina/agent/workflows.py` alongside `agents.py`.
- **D-02:** `build_input: Callable[[dict, dict], BaseModel]` signature — receives a frozen copy of `shared_context` and `accumulated_artifacts: dict[str, dict]` keyed by `step_key`. Never mutates `shared_context`.
- **D-03:** `add-recipe` workflow registered verbatim per spec: `research` (recipe-research) → `load` (recipe-load) → `notify` (send-notification) with `build_input` lambdas as shown in spec §Workflow Registry.
- **D-04:** A `"hello-world-2step"` test workflow is registered in `WORKFLOW_REGISTRY` alongside `"add-recipe"`. It has two `hello-world` steps (`step1`, `step2`) — used exclusively for Phase 5 integration tests. Remove this entry (and the `hello-world` agent config) when `send-notification` is added in Phase 6.
- **D-05:** All execution-side workflow state management is encapsulated in `src/robotina/queue/workflow_runner.py`. Exposes: `start_workflow()`, `on_step_start()`, `on_step_complete()`, `on_step_failed()`.
- **D-06:** Job linkage — task runner finds workflow step by querying `WorkflowRunStep WHERE task_job_id = current_rq_job.id`. If no row found → direct task → skip all workflow state management.
- **D-07:** Transactional advancement — enqueue next RQ job BEFORE committing the Postgres transaction using pre-assigned job ID (`job_id = str(uuid.uuid4())`). VERIFIED: RQ 2.7.0 correctly assigns pre-assigned IDs.
- **D-08:** `run_task()` in `jobs.py` gains workflow awareness via inline calls to `workflow_runner` — no new dispatcher function.
- **D-09:** `StartWorkflowTool` lives in `src/robotina/agent/tools/start_workflow.py` as `BaseTool` subclass. `tools/` directory is created as a Python package.
- **D-10:** `StartWorkflowTool._run(workflow_type: str, shared_context: dict)` — reads `household_id` from `shared_context`, creates its own DB session via `robotina.db.SessionLocal()`, creates RQ queue connection, calls `workflow_runner.start_workflow()`, returns `workflow_run_id` string. Session closed in `finally` block.
- **D-11:** `workflow_runner` functions accept a `session` argument (injected by the caller) to keep the module testable without live DB.
- **D-12:** Integration tests use `hello-world-2step` workflow through the real queue + DB.
- **D-13:** Unit tests cover `workflow_runner.py` functions in isolation — mocked SQLAlchemy session (MagicMock) and mocked RQ queue.

### Claude's Discretion

- Exact `WorkflowStepDef` model configuration (Pydantic BaseModel vs dataclass — spec shows Pydantic, use that)
- `on_step_start` / `on_step_complete` exact function signatures beyond what's specified
- SQLAlchemy query patterns for looking up `WorkflowRunStep` by `task_job_id`
- How `accumulated_artifacts` is built (query all DONE steps for the `workflow_run_id`)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QUEUE-01 | Redis configured with AOF persistence — no tasks lost on crash/reboot | Already complete (Phase 2). No action needed in Phase 5. |
| WF-02 | `workflows.py` defines a `WorkflowDefinition` registry with `WorkflowStepDef` entries and `build_input` callables | Spec §Workflow Registry provides verbatim Python code. `WorkflowStepDef` is a `BaseModel` (Pydantic). |
| WF-03 | `add-recipe` workflow registered with three steps: `research` → `load` → `notify` | Spec §Workflow Registry has the complete WORKFLOW_REGISTRY dict with all `build_input` lambdas. All input types exist in `task_types.py`. |
| WF-04 | `start-workflow` tool creates `WorkflowRun` + all `WorkflowRunStep` records (PENDING), enqueues first step, returns `workflow_run_id` | D-09/D-10 fully specify the tool. Pre-assigned job ID pattern verified working in RQ 2.7.0. |
| WF-05 | Task runner marks `WorkflowRunStep` as RUNNING when its job starts processing | `on_step_start(job_id, session)` in `workflow_runner.py`. Called from `run_task()` before agent execution. |
| WF-06 | On step completion, task runner writes output to `WorkflowRunStep.artifact`, builds `accumulated_artifacts`, and enqueues next PENDING step | `on_step_complete(job_id, output, session, queue)` in `workflow_runner.py`. Output serialized via `model.model_dump(mode='json')`. |
| WF-07 | On final step completion, task runner marks the `WorkflowRun` as DONE | Handled inside `on_step_complete` — if no next PENDING step, mark `WorkflowRun` DONE. |
| WF-08 | On step failure, task runner marks step FAILED, cancels all remaining PENDING steps, marks `WorkflowRun` FAILED | `on_step_failed(job_id, session)` in `workflow_runner.py`. Exception re-raised so RQ retains the job in FailedJobRegistry. |
| WF-09 | `reply_context` stored in `WorkflowRun.shared_context` and never appears in intermediate task inputs | Already enforced in `task_types.py` — `RecipeResearchInput` and `RecipeLoadInput` have no `reply_context` field. `build_input` lambdas read `reply_context` from `shared_context` only in the `notify` step. |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 5 |
|-----------|-------------------|
| Python, LangChain, Postgres (SQLAlchemy + Alembic), Redis + RQ, uv — no deviations | All new code uses only these. `workflow_runner.py` uses SQLAlchemy + RQ. `start_workflow.py` uses LangChain `BaseTool`. |
| Task runner processes jobs sequentially (concurrency = 1) | No change to worker concurrency. Workflow advancement stays within single-worker model. |
| API tokens read from env vars named by task type | `hello-world-2step` uses the `hello-world` AgentConfig which already reads `HELLO_WORLD_API_TOKEN`. |
| Redis persistence AOF `appendfsync always` | Already configured. No Phase 5 changes. |
| LangWatch instrumentation must be active during production and experiment runs | No LangWatch changes in Phase 5. `run_task()` tracing already in place from Phase 4. |
| `result_ttl=-1` and `failure_ttl=-1` on all RQ jobs | `workflow_runner.start_workflow()` and `on_step_complete()` must pass `result_ttl=-1, failure_ttl=-1` when enqueuing. |
| GSD workflow enforcement — changes via GSD commands | Handled by this research/planning process. |

---

## Standard Stack

### Core (all pre-installed, versions verified)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| rq | 2.7.0 | Job enqueueing with pre-assigned IDs, job lookup | `job_id=` parameter verified working. `Queue.enqueue()` signature stable. |
| SQLAlchemy | 2.x | `WorkflowRun`/`WorkflowRunStep` queries and updates | `Mapped` + `mapped_column` style already used throughout. |
| pydantic | v2 | `WorkflowStepDef`, `WorkflowDefinition` models | Spec shows Pydantic BaseModel. Consistent with all other models. |
| langchain-core | >=0.3 | `BaseTool` base class for `StartWorkflowTool` | Same pattern as `ReadSkillTool` in Phase 4 (`__init__.py`). |
| uuid | stdlib | Pre-assigned job ID generation | `str(uuid.uuid4())` as locked in D-07. |
| datetime | stdlib | `started_at`, `completed_at` timestamps | `datetime.now(timezone.utc)` for consistency. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unittest.mock.MagicMock | stdlib | Mock SQLAlchemy session in unit tests | D-13: unit tests for `workflow_runner.py` |
| pytest | installed | Test runner | Integration tests (D-12) and unit tests (D-13) |

### Alternatives Considered

None applicable — all choices are locked by CONTEXT.md decisions.

---

## Architecture Patterns

### New File Structure

```
src/robotina/
├── agent/
│   ├── agents.py          # MODIFY: add hello-world to WORKFLOW_REGISTRY task types
│   ├── workflows.py       # NEW: WorkflowStepDef, WorkflowDefinition, WORKFLOW_REGISTRY
│   └── tools/
│       ├── __init__.py    # NEW: empty package init
│       └── start_workflow.py  # NEW: StartWorkflowTool BaseTool subclass
└── queue/
    ├── jobs.py            # MODIFY: add on_step_start/complete/failed hooks to run_task()
    └── workflow_runner.py # NEW: start_workflow(), on_step_start(), on_step_complete(), on_step_failed()

tests/
├── conftest.py            # MODIFY: add workflow/workflow_step cleanup to db_session fixture
├── test_workflow_runner.py   # NEW: integration tests for hello-world-2step (D-12)
└── unit/
    └── test_workflow_runner_unit.py  # NEW: unit tests with mocked session (D-13)
```

### Pattern 1: Workflow Registry (workflows.py)

**What:** Pydantic `BaseModel` registry mapping workflow type names to ordered step definitions with `build_input` callables.

**When to use:** Planner must copy the spec verbatim for `add-recipe`. Pydantic validators on `WorkflowStepDef` — no arbitrary_types_allowed needed since `Callable` is supported in Pydantic v2 with `model_config = ConfigDict(arbitrary_types_allowed=True)`.

**Spec source:** `plans/01-kickoff/spec.md` §Workflow Registry (lines ~388-430).

```python
# Source: plans/01-kickoff/spec.md §Workflow Registry
from pydantic import BaseModel, ConfigDict
from typing import Callable
from robotina.queue.task_types import (
    RecipeResearchInput, RecipeLoadInput, SendNotificationInput
)

class WorkflowStepDef(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    step_key: str
    task_type: str
    build_input: Callable[[dict, dict], BaseModel]

class WorkflowDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    workflow_type: str
    steps: list[WorkflowStepDef]

WORKFLOW_REGISTRY: dict[str, WorkflowDefinition] = {
    "add-recipe": WorkflowDefinition(...),      # verbatim from spec
    "hello-world-2step": WorkflowDefinition(...),  # Phase 5 test fixture (D-04)
}
```

**Critical detail:** Pydantic v2 does not support `Callable` fields by default. `ConfigDict(arbitrary_types_allowed=True)` is required on both `WorkflowStepDef` and `WorkflowDefinition`.

### Pattern 2: Workflow Runner Module (workflow_runner.py)

**What:** Four functions that own all workflow state transitions. Receives an injected `session` for testability (D-11).

**Advancement algorithm for `on_step_complete`:**
1. Load step by `task_job_id = job_id`, set `artifact = output.model_dump(mode='json')` if Pydantic, else `dict(output)`. Set `status = DONE`, `completed_at = now`.
2. Query all DONE steps for same `workflow_run_id`, build `accumulated_artifacts = {step.step_key: step.artifact for step in done_steps}`.
3. Query all PENDING steps ordered by position (use `step_key` ordering per `WorkflowDefinition.steps` list — match by index).
4. If next PENDING step exists: generate `next_job_id = str(uuid.uuid4())`, call `step_def.build_input(shared_context, accumulated_artifacts)` to get input model, `queue.enqueue('robotina.queue.jobs.run_task', task_input, job_id=next_job_id, result_ttl=-1, failure_ttl=-1, meta={'task_type': step_def.task_type})`, set `next_step.task_job_id = next_job_id`.
5. If no next PENDING step: set `workflow_run.status = WorkflowStatus.DONE`.
6. `session.commit()` — AFTER enqueue (D-07: enqueue before commit).

**Ordering note:** The `WorkflowRunStep` records don't have a positional index column. To identify "next PENDING step" in order, the runner must look up the `WorkflowDefinition` from the registry, find the current step's position by `step_key`, and select the next step in the definition's `steps` list that has `PENDING` status.

```python
# Source: plans/01-kickoff/spec.md §Artifact Flow + decisions D-05/D-06/D-07
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from rq import Queue
from robotina.queue.models import (
    WorkflowRun, WorkflowRunStep, WorkflowStatus, WorkflowStepStatus
)
from robotina.agent.workflows import WORKFLOW_REGISTRY

def start_workflow(
    workflow_type: str,
    shared_context: dict,
    household_id: str,
    queue: Queue,
    session: Session,
) -> str:
    workflow_def = WORKFLOW_REGISTRY[workflow_type]
    run = WorkflowRun(
        workflow_type=workflow_type,
        household_id=household_id,
        status=WorkflowStatus.RUNNING,
        shared_context=shared_context,
    )
    session.add(run)
    session.flush()  # get run.id before steps

    first_job_id = str(uuid.uuid4())
    steps = []
    for i, step_def in enumerate(workflow_def.steps):
        step = WorkflowRunStep(
            workflow_run_id=run.id,
            step_key=step_def.step_key,
            task_type=step_def.task_type,
            status=WorkflowStepStatus.PENDING,
            task_job_id=first_job_id if i == 0 else None,
        )
        steps.append(step)
    session.add_all(steps)

    # Enqueue first step BEFORE commit (D-07)
    first_step_def = workflow_def.steps[0]
    first_input = first_step_def.build_input(shared_context, {})
    queue.enqueue(
        'robotina.queue.jobs.run_task',
        first_input,
        job_id=first_job_id,
        result_ttl=-1,
        failure_ttl=-1,
        meta={'task_type': first_step_def.task_type},
    )
    session.commit()
    return run.id
```

### Pattern 3: run_task() Workflow Hook (jobs.py)

**What:** Three inline calls to `workflow_runner` functions wrap the existing agent execution (D-08).

```python
# Source: decisions D-08, referencing existing jobs.py structure
def run_task(task_input) -> object:
    job = get_current_job()
    # ... existing task_type lookup, config, backend, prompt loading ...

    from robotina.queue import workflow_runner
    from robotina.db import SessionLocal

    session = SessionLocal()
    try:
        # Before agent execution
        workflow_runner.on_step_start(job.id, session)

        # ... existing agent invocation (langwatch trace, agent.invoke) ...

        # After successful agent execution
        workflow_runner.on_step_complete(job.id, result, session, queue)
        return result
    except Exception:
        workflow_runner.on_step_failed(job.id, session)
        raise  # re-raise so RQ moves job to FailedJobRegistry
    finally:
        session.close()
```

**Critical detail:** The session must be closed in a `finally` block (D-11). The `queue` object needed by `on_step_complete` must be obtained inside `run_task()` — use `get_current_job().origin` to get the queue name and create an RQ `Queue` instance with a fresh Redis connection.

### Pattern 4: StartWorkflowTool (BaseTool subclass)

**What:** Thin wrapper over `workflow_runner.start_workflow()`. Follows the `ReadSkillTool` pattern from Phase 4.

```python
# Source: decisions D-09/D-10 + ReadSkillTool pattern from agent/__init__.py
import os
from langchain_core.tools import BaseTool
from robotina.db import SessionLocal
from redis import Redis
from rq import Queue
from robotina.queue import workflow_runner

class StartWorkflowTool(BaseTool):
    name: str = "start-workflow"
    description: str = (
        "Initiate a multi-step workflow. Provide workflow_type and shared_context dict. "
        "Returns the workflow_run_id."
    )

    def _run(self, workflow_type: str, shared_context: dict) -> str:
        household_id = shared_context.get("household_id", "")
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        conn = Redis.from_url(redis_url)
        queue = Queue("agent-tasks", connection=conn)
        session = SessionLocal()
        try:
            return workflow_runner.start_workflow(
                workflow_type, shared_context, household_id, queue, session
            )
        finally:
            session.close()

    async def _arun(self, workflow_type: str, shared_context: dict) -> str:
        return self._run(workflow_type, shared_context)
```

### Pattern 5: SQLAlchemy Query for Step Lookup

**What:** Query `WorkflowRunStep` by `task_job_id`, then load related `WorkflowRun`.

```python
# Source: SQLAlchemy 2.x select() pattern used throughout codebase
from sqlalchemy import select

def on_step_start(job_id: str, session: Session) -> None:
    stmt = select(WorkflowRunStep).where(WorkflowRunStep.task_job_id == job_id)
    step = session.scalars(stmt).first()
    if step is None:
        return  # direct task — no workflow state management (D-06)
    step.status = WorkflowStepStatus.RUNNING
    step.started_at = datetime.now(timezone.utc)
    session.commit()
```

**Loading accumulated_artifacts:**

```python
# Query all DONE steps for the same workflow_run_id
done_stmt = (
    select(WorkflowRunStep)
    .where(WorkflowRunStep.workflow_run_id == step.workflow_run_id)
    .where(WorkflowRunStep.status == WorkflowStepStatus.DONE)
)
done_steps = session.scalars(done_stmt).all()
accumulated_artifacts = {s.step_key: s.artifact for s in done_steps}
```

### Anti-Patterns to Avoid

- **Committing before enqueue:** The transactional order is enqueue-then-commit (D-07). Reversing this order loses the job if the process crashes between the commit and the enqueue call.
- **Querying steps by step_key alone:** `step_key` is unique within a `workflow_run_id` but not globally. Always filter by both `workflow_run_id` and `step_key` when looking up by step_key (vs. `task_job_id` which is globally unique as a UUID).
- **Mutating `shared_context` in `build_input`:** The `build_input` lambdas receive `shared_context` read from the DB. The caller must pass a copy (`dict(run.shared_context)`) if there is any risk of mutation, per D-02. The lambdas in the spec are pure and don't mutate, but defensive copying is safer.
- **Module-level session or queue objects:** All DB sessions and Redis connections must be created inside job/tool function bodies, never at module level (locked Phase 4 constraint).
- **Swallowing the exception in `on_step_failed`:** The exception must be re-raised after calling `on_step_failed()` so RQ moves the job to `FailedJobRegistry` (QUEUE-05).
- **Missing `result_ttl=-1, failure_ttl=-1` on enqueued workflow steps:** Every `queue.enqueue()` call inside `workflow_runner` must include these (QUEUE-04 / CLAUDE.md).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Job ID pre-assignment | Custom ID tracking table | `queue.enqueue(..., job_id=pre_id)` | RQ 2.7.0 natively supports this; VERIFIED working |
| Workflow step ordering | Positional index column in DB | Position from `WorkflowDefinition.steps` list order | Spec design: DB is state store, registry is structure source |
| Artifact serialization | Custom serializer | `model.model_dump(mode='json')` | Pydantic v2 `mode='json'` handles datetime/enum/UUID natively |
| Queue connection in tools | Cached module-level Redis | `Redis.from_url(os.environ[...])` per call | Locked architectural constraint: no module-level state |

**Key insight:** The workflow engine is intentionally minimal — it is a state machine with 5 states per step. All complexity lives in the centralized `workflow_runner.py`, not in agents or task-specific code.

---

## Common Pitfalls

### Pitfall 1: Pydantic v2 rejects Callable fields without arbitrary_types_allowed

**What goes wrong:** `WorkflowStepDef(build_input=lambda ...)` raises `PydanticSchemaGenerationError` because `Callable` is not a JSON-serializable type.

**Why it happens:** Pydantic v2 strict type validation by default.

**How to avoid:** Add `model_config = ConfigDict(arbitrary_types_allowed=True)` to both `WorkflowStepDef` and `WorkflowDefinition`.

**Warning signs:** `PydanticSchemaGenerationError: Unable to generate pydantic-core schema for type Callable`.

### Pitfall 2: run_task() session not closed on exception path

**What goes wrong:** Session leaked when agent raises; connection pool exhausted after a few failures.

**Why it happens:** Session created before the try/except block, exception bypasses `session.close()`.

**How to avoid:** Always use `try/finally: session.close()` pattern (same as `StartWorkflowTool._run()`).

**Warning signs:** `TimeoutError: QueuePool limit overflow` in Postgres logs after multiple test failures.

### Pitfall 3: Step "not found" path hides real bugs

**What goes wrong:** A bug in job metadata assignment (missing `task_job_id` on `WorkflowRunStep`) silently degrades to the "direct task" path — workflow steps appear to succeed but no state transitions happen.

**Why it happens:** The `on_step_start(job_id, session)` no-op path is correct for direct tasks but masks DB linkage errors.

**How to avoid:** In integration tests, assert the `WorkflowRunStep` record transitions to `RUNNING` at the correct moment. If it stays `PENDING`, the `task_job_id` linkage is broken.

**Warning signs:** `WorkflowRun` stays `RUNNING` forever; no `DONE`/`FAILED` transitions.

### Pitfall 4: on_step_complete receives raw LangGraph messages dict, not Pydantic output

**What goes wrong:** `result.model_dump(mode='json')` fails because `run_task()` returns the raw LangGraph agent result (a messages dict), not a typed Pydantic output model.

**Why it happens:** The current `run_task()` returns `agent.invoke()` result directly, which is `{"messages": [...]}` from LangGraph — not a `RecipeResearchOutput` etc.

**How to avoid:** For the `hello-world-2step` test, define the `build_input` lambda to accept whatever `hello-world` outputs. In `on_step_complete`, serialize with `model.model_dump(mode='json')` only if the output is a Pydantic `BaseModel`; otherwise use a safe fallback like storing the raw dict. The `artifact` column is `JSON`, so any dict works.

**Practical approach for Phase 5:** `hello-world` agent returns a messages list. Store it as-is (it's a serializable list). Use `isinstance(output, BaseModel)` to branch serialization.

### Pitfall 5: Postgres ENUM status transitions not validated at DB level

**What goes wrong:** A bug writes an invalid status combination (e.g., `DONE` → `RUNNING`) and Postgres accepts it because ENUMs only validate the value name, not the state machine.

**Why it happens:** SQLAlchemy `Enum` column validates Python enum membership but not transition validity.

**How to avoid:** Unit tests for `workflow_runner.py` functions must assert the expected final status — catching transitions that go backwards.

### Pitfall 6: session.flush() vs session.commit() order for workflow_run_id FK

**What goes wrong:** Creating `WorkflowRun` and `WorkflowRunStep` in the same function fails with FK constraint violation if `run.id` is not available when creating steps.

**Why it happens:** `session.add(run)` doesn't flush the INSERT immediately; `run.id` may not be populated until flush.

**How to avoid:** Call `session.flush()` after adding `WorkflowRun` and before adding `WorkflowRunStep` records. This populates `run.id` without committing the transaction.

---

## Code Examples

### Verified RQ pre-assigned job_id (CONFIRMED working, RQ 2.7.0)

```python
# Verified 2026-03-26 against live Redis
import uuid
from rq import Queue

job_id = str(uuid.uuid4())
job = queue.enqueue(
    'robotina.queue.jobs.run_task',
    task_input,
    job_id=job_id,        # pre-assigned — confirmed: job.id == job_id
    result_ttl=-1,
    failure_ttl=-1,
    meta={'task_type': 'hello-world'},
)
assert job.id == job_id  # True — verified
```

### Verified SessionLocal() usage pattern

```python
# Verified 2026-03-26 — supports both context manager and direct instantiation
from robotina.db import SessionLocal

# Pattern used in workflow_runner (session injected by caller):
session = SessionLocal()
try:
    # ... DB operations ...
    session.commit()
finally:
    session.close()

# Pattern used in StartWorkflowTool._run():
session = SessionLocal()
try:
    result = workflow_runner.start_workflow(..., session=session)
    return result
finally:
    session.close()
```

### hello-world-2step workflow (test fixture, D-04)

```python
# Source: decision D-04
WORKFLOW_REGISTRY: dict[str, WorkflowDefinition] = {
    "add-recipe": ...,  # from spec
    "hello-world-2step": WorkflowDefinition(
        workflow_type="hello-world-2step",
        steps=[
            WorkflowStepDef(
                step_key="step1",
                task_type="hello-world",
                build_input=lambda ctx, _: HelloWorldInput(
                    message=ctx.get("message", "step1")
                ),
            ),
            WorkflowStepDef(
                step_key="step2",
                task_type="hello-world",
                build_input=lambda ctx, artifacts: HelloWorldInput(
                    message=f"step2 after: {artifacts.get('step1', {})}"
                ),
            ),
        ],
    ),
}
```

**Note:** `HelloWorldInput` does not currently exist as a typed Pydantic model in `task_types.py`. The test workflow's `build_input` can return any `BaseModel`. Either add a minimal `HelloWorldInput(BaseModel)` to `task_types.py` for Phase 5, or pass a generic dict/simple model. This is a discretionary implementation choice.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `rq-scheduler` add-on | RQ 2.5+ native scheduler | RQ 2.0 (matured 2.5) | `rq-scheduler` not used in this project |
| Polling for next step | Inline advancement in job completion | Phase 5 design | Simpler, no polling loop needed |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Redis | Workflow advancement, RQ | Yes | 7.x (docker compose) | — |
| PostgreSQL | WorkflowRun/Step persistence | Yes | 15 (docker compose) | — |
| RQ | Job enqueueing with pre-assigned IDs | Yes | 2.7.0 | — |
| SQLAlchemy | WorkflowRun/Step model queries | Yes | 2.x | — |
| Pydantic v2 | WorkflowStepDef, WorkflowDefinition | Yes | v2 | — |
| langchain-core | BaseTool for StartWorkflowTool | Yes | >=0.3 | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (installed) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/unit/test_workflow_runner_unit.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WF-02 | WorkflowDefinition registry defines steps with build_input callables | unit | `uv run pytest tests/unit/test_workflow_runner_unit.py -x -q` | No — Wave 0 |
| WF-03 | add-recipe workflow registered with 3 steps in correct order | unit | `uv run pytest tests/unit/test_workflow_runner_unit.py -x -q` | No — Wave 0 |
| WF-04 | start_workflow() creates WorkflowRun + all steps PENDING, enqueues first step | unit + integration | `uv run pytest tests/test_workflow_runner.py -x -q -m integration` | No — Wave 0 |
| WF-05 | on_step_start marks step RUNNING | unit | `uv run pytest tests/unit/test_workflow_runner_unit.py -x -q` | No — Wave 0 |
| WF-06 | on_step_complete writes artifact, builds accumulated_artifacts, enqueues next | unit + integration | `uv run pytest tests/test_workflow_runner.py -x -q -m integration` | No — Wave 0 |
| WF-07 | Final step completion marks WorkflowRun DONE | integration | `uv run pytest tests/test_workflow_runner.py -x -q -m integration` | No — Wave 0 |
| WF-08 | Step failure marks step FAILED, cancels PENDING, marks WorkflowRun FAILED | unit + integration | `uv run pytest tests/test_workflow_runner.py -x -q -m integration` | No — Wave 0 |
| WF-09 | reply_context not in RecipeResearchInput or RecipeLoadInput | unit | `uv run pytest tests/test_task_types.py -x -q` | Yes — existing test |
| QUEUE-01 | Redis AOF persistence | infrastructure | manual or existing test | Yes — Phase 2 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/test_workflow_runner_unit.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_workflow_runner_unit.py` — unit tests for `workflow_runner.py` (covers WF-02, WF-03, WF-05, WF-06, WF-07, WF-08, D-06 no-op path)
- [ ] `tests/test_workflow_runner.py` — integration tests for hello-world-2step workflow (covers WF-04, WF-06, WF-07, WF-08 end-to-end)
- [ ] `tests/conftest.py` update — add `workflow_run` and `workflow_run_step` table cleanup to `db_session` fixture

---

## Open Questions

1. **HelloWorldInput model for test workflow**
   - What we know: `task_types.py` has no `HelloWorldInput`. The `hello-world` agent is already in `agents.py` with a model config. `run_task()` uses `_extract_user_message()` which falls back to `str(task_input)` for unknown types.
   - What's unclear: Should Phase 5 add a minimal `HelloWorldInput(BaseModel)` to `task_types.py` or use a generic approach?
   - Recommendation: Add `HelloWorldInput(BaseModel): message: str` to `task_types.py` as part of Phase 5. It keeps `build_input` lambdas clean and `_extract_user_message` can detect the `message` attribute. Remove when `hello-world` is removed in Phase 6.

2. **Output serialization for hello-world step artifacts**
   - What we know: LangGraph `create_react_agent` returns `{"messages": [...]}` which is a dict of lists. `on_step_complete` receives this raw dict (not a Pydantic BaseModel) for the hello-world steps.
   - What's unclear: Should `on_step_complete` handle both Pydantic and dict outputs uniformly?
   - Recommendation: In `on_step_complete`, check `isinstance(output, BaseModel)` — if true, use `output.model_dump(mode='json')`; otherwise, attempt `dict(output)` or store as-is (it's already a dict). For real agents (Phase 8+), output will be typed Pydantic models.

3. **Queue object availability inside run_task()**
   - What we know: `run_task()` currently has access to `get_current_job()` which returns the current RQ job. The job has `.origin` (queue name) and can provide a Redis connection via `job.connection`.
   - What's unclear: Best way to reconstruct the RQ Queue inside `run_task()` for passing to `on_step_complete()`.
   - Recommendation: Use `job.connection` (the existing Redis connection used by the job) and `job.origin` (the queue name) to construct `Queue(job.origin, connection=job.connection)` inside `run_task()`. This avoids creating a new Redis connection.

---

## Sources

### Primary (HIGH confidence)

- `plans/01-kickoff/spec.md` §Workflow Registry, §Artifact Flow, §Failure Handling, §Tools — verbatim Python definitions and advancement algorithm
- `.planning/phases/05-task-runner-and-workflow-engine/05-CONTEXT.md` — all locked decisions D-01 through D-13
- Existing codebase: `src/robotina/queue/models.py`, `jobs.py`, `runner.py`, `task_types.py`, `agent/__init__.py`, `agent/agents.py`, `db.py` — verified against actual file contents
- RQ 2.7.0 `job_id=` parameter: VERIFIED working against live Redis (2026-03-26)
- SessionLocal() context manager support: VERIFIED in Python REPL (2026-03-26)

### Secondary (MEDIUM confidence)

- Pydantic v2 `ConfigDict(arbitrary_types_allowed=True)` for Callable fields — standard Pydantic v2 pattern, consistent with existing codebase Pydantic v2 usage

### Tertiary (LOW confidence)

- `job.connection` and `job.origin` attributes on RQ Job objects — training data (RQ 2.x). Should be verified at implementation time if `Queue` reconstruction inside `run_task()` is chosen.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified as installed, versions confirmed
- Architecture: HIGH — all decisions locked in CONTEXT.md, spec has verbatim code
- Pitfalls: HIGH — identified from direct code reading + RQ/SQLAlchemy patterns
- Test approach: HIGH — follows existing integration test pattern from `test_rq_integration.py`

**Research date:** 2026-03-26
**Valid until:** 2026-04-26 (stable libraries; only risk is RQ API changes, LOW probability)
