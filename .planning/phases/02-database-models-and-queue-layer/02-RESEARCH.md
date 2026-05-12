# Phase 2: Database Models and Queue Layer - Research

**Researched:** 2026-03-25
**Domain:** SQLAlchemy 2.x models, Alembic migrations, Pydantic v2 task types, RQ queue verification
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Split models by domain sub-package: `robotina/gateway/models.py` holds `Conversation` and `StoredMessage`; `robotina/queue/models.py` holds `WorkflowRun` and `WorkflowRunStep`
- **D-02:** Shared SQLAlchemy declarative `Base` lives in `robotina/db.py` — both model files import `Base` from there
- **D-03:** Model field definitions follow the spec verbatim (`plans/01-kickoff/spec.md` §"Conversation History Storage" and §"Workflow Engine") — no field additions or modifications
- **D-04:** Implement a `LoggingWorker(Worker)` subclass in `robotina/queue/runner.py` that overrides `perform_job` to emit structured log lines at job start, finish, and failure — all lifecycle logging centralized in one place, no logging required in individual job functions
- **D-05:** Log format includes job ID, queue name, and task type: `[agent-tasks] job <id> starting | finished | failed`

### Claude's Discretion
- **D-06:** All four Pydantic task I/O models (`IncomingMessageInput/Output`, `RecipeResearchInput/Output`, `RecipeLoadInput/Output`, `SendNotificationInput/Output`) live in `robotina/queue/task_types.py` — centralized, imported by queue, agents, and task runner
- **D-07:** Verification uses an integration test (requires live Redis) that enqueues a trivial no-op job, asserts it completes with `result_ttl=-1`/`failure_ttl=-1`, and confirms the job appears in the finished registry

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QUEUE-01 | Redis configured with AOF persistence (`appendfsync always`) — no tasks lost on crash/reboot | Already wired in docker-compose from Phase 1; verify config is in place, no new work needed |
| QUEUE-02 | Task runner processes jobs sequentially with exactly one worker (concurrency = 1) | Confirmed: RQ Worker has no `concurrency` param; single Worker instance = concurrency 1. `LoggingWorker(Worker)` subclass in runner.py |
| QUEUE-03 | All task inputs/outputs are strongly-typed Pydantic v2 models (all 8 model classes) | Verified: spec defines verbatim model schemas; Pydantic v2 installed (2.12.5); pickle round-trip confirmed |
| QUEUE-04 | All jobs have `result_ttl=-1` and `failure_ttl=-1` (infinite retention) | `Queue.enqueue()` accepts `result_ttl` and `failure_ttl` kwargs; set per-enqueue call |
| QUEUE-05 | Failed jobs retained in RQ's built-in failed job registry | RQ 2.7 has `FailedJobRegistry`; `handle_job_failure` moves jobs there automatically |
| QUEUE-06 | Agent can enqueue follow-up tasks at normal or urgent priority (front of queue) | `Queue.enqueue(..., at_front=True)` confirmed in RQ 2.7; `Queue.enqueue_job(job, at_front=False/True)` |
| QUEUE-07 | All queue state changes logged to console (queued, processing started, finished/failed) | `LoggingWorker.perform_job()` override provides start/finish/fail hooks; queued logging needs separate hook |
| WF-01 | `WorkflowRun` and `WorkflowRunStep` SQLAlchemy 2.x models exist in Postgres with Alembic migration | Verbatim spec schemas researched; Alembic migration pattern documented; env.py already has sys.path injection |
</phase_requirements>

---

## Summary

Phase 2 establishes all shared data contracts before any agent logic is written. Three distinct workstreams run in parallel: (1) SQLAlchemy model definitions and their Alembic migration, (2) Pydantic v2 task I/O model definitions, and (3) RQ worker verification with lifecycle logging.

All model schemas are verbatim from `plans/01-kickoff/spec.md` — no design decisions remain for field layout. The key implementation risks are in `robotina/db.py` (adding `DeclarativeBase` subclass, engine/session factory), wiring `env.py` to import models before setting `target_metadata`, and correctly subclassing `Worker.perform_job()` to emit structured log lines for all three lifecycle states. The Alembic pitfall of native PostgreSQL ENUM types requiring explicit TYPE management on downgrade is documented below.

The integration test for RQ verification (D-07) requires live Redis — this is consistent with the Phase 1 test philosophy of testing against the real stack. All other tests (model import, pickle round-trip, file structure) can run without external services.

**Primary recommendation:** Follow the spec field definitions verbatim. The only genuine decision points are the `Base` initialization pattern in `db.py`, the Alembic migration strategy for native PG ENUMs, and the exact `LoggingWorker.perform_job()` override structure.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.48 (installed) | ORM — model definitions, Base, session factory | Project mandated; `Mapped`/`mapped_column` syntax in spec verbatim |
| Alembic | >=1.13 (in pyproject.toml) | Schema migration | Standard companion to SQLAlchemy 2.x |
| psycopg2-binary | installed | PostgreSQL driver for SQLAlchemy | Already in pyproject.toml; sync sessions in task-runner context |
| Pydantic | 2.12.5 (installed) | Task I/O model definitions | Project mandated; v2 syntax in spec verbatim |
| RQ | 2.7.0 (installed) | Queue, worker, job registries | Project mandated; 2.5+ native scheduler |
| Redis | >=4.0 (in pyproject.toml) | RQ backing store | Already configured with AOF from Phase 1 |

### No Alternatives
All libraries are locked by CLAUDE.md and the spec. No alternative evaluation needed.

---

## Architecture Patterns

### File Layout (locked by D-01 through D-03)

```
src/robotina/
├── db.py                    # DeclarativeBase subclass, engine, session factory
├── gateway/
│   ├── __init__.py          # exists (empty)
│   └── models.py            # Conversation, StoredMessage — NEW
└── queue/
    ├── __init__.py          # exists (empty)
    ├── runner.py            # refactor: Worker → LoggingWorker — MODIFY
    └── task_types.py        # all 8 Pydantic task I/O models — NEW

migrations/
├── env.py                   # add model imports, set target_metadata — MODIFY
└── versions/
    ├── 0001_init.py         # exists (empty migration)
    └── 0002_models.py       # new: all 4 SQLAlchemy tables — NEW
```

### Pattern 1: DeclarativeBase in db.py

The spec uses `Base` as a shared declarative base. SQLAlchemy 2.x uses `DeclarativeBase` subclass pattern (not the legacy `declarative_base()` function). `db.py` must export `Base`, `engine`, and a session factory so that both model files and Alembic's `env.py` can import from a single location.

```python
# Source: SQLAlchemy 2.x docs / verified against installed 2.0.48
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

class Base(DeclarativeBase):
    pass

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://robotina:robotina@localhost:5432/robotina")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
```

### Pattern 2: Alembic env.py — importing models for autogenerate

`target_metadata = None` must be replaced with `Base.metadata` after importing all model modules. Models register themselves with `Base.metadata` at import time — the import must happen before the metadata assignment.

```python
# Source: migrations/env.py (existing Phase 1 file — this is the required modification)
# Line to change: "target_metadata = None"  →
from robotina.db import Base
import robotina.gateway.models   # noqa: F401 — registers Conversation, StoredMessage
import robotina.queue.models     # noqa: F401 — registers WorkflowRun, WorkflowRunStep
target_metadata = Base.metadata
```

The `sys.path.insert(0, ...)` already present in `env.py` ensures `robotina` is importable. No additional path changes needed.

### Pattern 3: LoggingWorker subclass — perform_job override

`Worker.perform_job(self, job, queue)` is the lowest-level hook that runs inside the forked work-horse process. It handles the job execution and calls `handle_job_success`/`handle_job_failure`. This is the correct override point for logging start, finish, and failure.

`job.meta` is a dict that can store arbitrary data (including `task_type`). `job.description` is set automatically to the function call string when not overridden. `job.origin` holds the queue name.

```python
# Source: verified against RQ 2.7.0 Worker.perform_job source
import logging
from rq import Worker

logger = logging.getLogger(__name__)

class LoggingWorker(Worker):
    def perform_job(self, job, queue) -> bool:
        task_type = job.meta.get("task_type", job.func_name)
        logger.info("[%s] job %s starting | task_type=%s", job.origin, job.id, task_type)
        success = super().perform_job(job, queue)
        if success:
            logger.info("[%s] job %s finished | task_type=%s", job.origin, job.id, task_type)
        else:
            logger.error("[%s] job %s failed | task_type=%s", job.origin, job.id, task_type)
        return success
```

**Note on QUEUE-07 "queued" logging:** `perform_job` only covers start/finish/fail. Logging when a job is *enqueued* requires either: (a) logging at the call site when `queue.enqueue()` is called, or (b) using RQ callbacks. Since no task enqueue call sites exist yet in this phase, the integration test can log at enqueue time explicitly. Phase 5 (workflow advancement) will be the natural place to add per-enqueue logging.

### Pattern 4: RQ enqueue with mandatory TTL settings

Per CLAUDE.md and spec, every `queue.enqueue()` call MUST set `result_ttl=-1` and `failure_ttl=-1`.

```python
# Source: verified against RQ 2.7.0 Queue.enqueue_call signature
job = queue.enqueue(
    my_func,
    my_arg,
    result_ttl=-1,
    failure_ttl=-1,
    meta={"task_type": "handle-incoming-message"},
)
# Urgent (front of queue):
job = queue.enqueue(
    my_func,
    my_arg,
    result_ttl=-1,
    failure_ttl=-1,
    at_front=True,
    meta={"task_type": "handle-incoming-message"},
)
```

### Pattern 5: All SQLAlchemy model imports (verbatim from spec)

`robotina/gateway/models.py` must import:
```python
import enum, uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Enum, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from robotina.db import Base
```

`robotina/queue/models.py` must import:
```python
import enum, uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Enum, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from robotina.db import Base
```

### Anti-Patterns to Avoid
- **Using `declarative_base()` (SQLAlchemy 1.x style):** The spec and CLAUDE.md mandate `DeclarativeBase` subclass — never use the legacy function-based approach.
- **Defining engine at module level in model files:** Engine belongs in `db.py`; model files import only `Base`. Models instantiated at module import time with DB connections cause test isolation failures.
- **Setting `target_metadata = Base.metadata` before importing model modules:** Alembic will see an empty metadata and generate a no-op migration. Always import model modules first.
- **Forgetting `at_front=False` is the default:** Normal priority enqueue needs no special param; only urgent tasks use `at_front=True`. Document this in enqueue helpers so future agents don't accidentally use urgent for everything.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Job failure registry (dead-letter queue) | Custom failed job table | `rq.registry.FailedJobRegistry` | Built into RQ; jobs land there automatically via `handle_job_failure` |
| Job status tracking | Custom status column on a DB table | `job.get_status()`, `job.is_finished`, `job.is_failed` | RQ maintains job state in Redis natively |
| UUID primary key generation | Custom ID factory | `default=lambda: str(uuid.uuid4())` in `mapped_column` | Already in spec verbatim; standard SQLAlchemy pattern |
| Schema diffing for migration | Manual SQL DDL | `alembic revision --autogenerate` | Alembic compares `target_metadata` against live DB; generates DDL automatically |
| Pickle serialization for Pydantic | Custom JSON serializer | Python built-in `pickle` (RQ default serializer) | Pydantic v2 `BaseModel` is picklable by default; verified round-trip works |

**Key insight:** RQ handles all job lifecycle state, retry, and registry management. The only custom behavior needed is the `LoggingWorker` subclass for structured log output — everything else uses RQ defaults.

---

## Common Pitfalls

### Pitfall 1: Native PostgreSQL ENUM types in Alembic migrations
**What goes wrong:** SQLAlchemy `Enum(PythonEnum)` creates a native PostgreSQL TYPE object (e.g., `CREATE TYPE workflowstatus AS ENUM (...)`) in addition to the table column. Alembic's autogenerated `downgrade()` may not drop these TYPE objects correctly, causing the next `upgrade` to fail with "type already exists" if migration is re-run or the downgrade path is used.
**Why it happens:** The spec uses `Enum(Platform)`, `Enum(MessageRole)`, `Enum(WorkflowStatus)`, `Enum(WorkflowStepStatus)` without `native_enum=False`. By default, SQLAlchemy creates native PG enum types.
**How to avoid:** In the Alembic migration file, explicitly use `sa.Enum(..., name='enumname', create_type=False)` in the column definitions and add explicit `op.execute("CREATE TYPE ...")` / `op.execute("DROP TYPE ...")` calls in `upgrade()`/`downgrade()`. Alternatively, after autogeneration, inspect the migration and verify that ENUM type creation and DROP are handled symmetrically.
**Warning signs:** `ProgrammingError: type "workflowstatus" already exists` on re-run; or `ProgrammingError: type "workflowstatus" does not exist` on fresh migration after failed downgrade.

### Pitfall 2: Alembic autogenerate sees empty metadata
**What goes wrong:** `alembic revision --autogenerate` generates a migration with empty `upgrade()` body — no tables are created.
**Why it happens:** `target_metadata = Base.metadata` is set before model modules are imported, so `Base.metadata.tables` is empty at the time Alembic reads it.
**How to avoid:** In `migrations/env.py`, import model modules before the `target_metadata` assignment (see Pattern 2 above). The comment `# Phase 1: no models yet — Phase 2 will set Base.metadata here` in the current `env.py` is the exact line to replace.
**Warning signs:** `INFO [alembic.autogenerate.compare] No changes in schema detected.` when you know tables should be created.

### Pitfall 3: LoggingWorker.perform_job runs inside the forked work-horse process
**What goes wrong:** Any state set up in the parent process (open DB connections, cached values) is not available inside `perform_job` — it runs in a forked subprocess (the "work horse").
**Why it happens:** RQ forks a new process for each job via `execute_job → fork_work_horse`. `perform_job` is called inside that fork.
**How to avoid:** Do not rely on parent-process state inside `perform_job`. All connections (DB, Redis) that `perform_job` needs must be created fresh inside the method, or passed through the job function itself. For the logging use case this is not a problem — `logging` is inherited by the fork.
**Warning signs:** AttributeError or ConnectionError inside LoggingWorker when accessing objects initialized in `main()`.

### Pitfall 4: Pydantic v2 model field with `list[...]` and `datetime` — pickle is fine, JSON round-trip is not
**What goes wrong:** RQ by default uses `pickle` to serialize job arguments and results. Pydantic v2 models pickle correctly. However, if any code path tries to JSON-serialize a `datetime` field from a Pydantic model without calling `.model_dump(mode='json')`, it will fail with a `TypeError` (datetime is not JSON-serializable by default).
**Why it happens:** `model.model_dump()` returns Python objects (datetime instances); `model.model_dump(mode='json')` converts them to ISO strings. The distinction matters when storing artifacts to `WorkflowRunStep.artifact` (JSON column).
**How to avoid:** When storing Pydantic model output to a `JSON` column in Postgres, always use `model.model_dump(mode='json')`. When reading back from a JSON column, use `MyModel(**artifact_dict)` to reconstruct.
**Warning signs:** `TypeError: Object of type datetime is not JSON serializable` when saving to `WorkflowRunStep.artifact`. (This pitfall is more relevant in Phase 5 but the `task_types.py` models should be designed with this in mind.)

### Pitfall 5: Forgetting result_ttl / failure_ttl on enqueue calls
**What goes wrong:** Jobs disappear from Redis after the default TTL (500 seconds for results, 360 seconds for failures) — violating QUEUE-04 and QUEUE-05.
**Why it happens:** `Worker.__init__` has a `default_result_ttl=500` — any job enqueued without explicit `result_ttl` uses this default.
**How to avoid:** Always pass `result_ttl=-1` and `failure_ttl=-1` to every `queue.enqueue()` call. Consider creating a wrapper function `enqueue_task(queue, func, *args, **kwargs)` that always injects these defaults, so individual callers cannot forget.
**Warning signs:** `rq.registry.FinishedJobRegistry.get_job_ids()` returns an empty list shortly after job completion when it should be retained indefinitely.

---

## Code Examples

Verified patterns from official sources and installed package inspection:

### SQLAlchemy 2.x model file structure
```python
# Source: spec verbatim + SQLAlchemy 2.0.48 installed API
# robotina/gateway/models.py
import enum, uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Enum, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from robotina.db import Base

class Platform(enum.Enum):
    TELEGRAM = "telegram"

class MessageRole(enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"

class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("platform", "chat_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    chat_id: Mapped[str] = mapped_column(String, nullable=False)
    household_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    messages: Mapped[list["StoredMessage"]] = relationship(back_populates="conversation")
```

### Pydantic v2 model with pickle verification
```python
# Source: spec verbatim + Pydantic 2.12.5 verified round-trip
# robotina/queue/task_types.py
from pydantic import BaseModel
from typing import Literal
from datetime import datetime

class Message(BaseModel):
    message_id: str
    role: Literal["user", "assistant"]
    text: str
    sent_at: datetime

class IncomingMessageInput(BaseModel):
    message_id: str
    platform: Literal["telegram"]
    received_at: datetime
    chat_id: str
    user_id: str
    household_id: str
    text: str
    history: list[Message]

# Pickle round-trip (verified):
# import pickle
# m = IncomingMessageInput(...)
# assert pickle.loads(pickle.dumps(m)) == m  # True
```

### RQ FinishedJobRegistry verification
```python
# Source: verified against RQ 2.7.0 installed API
from rq.registry import FinishedJobRegistry, FailedJobRegistry

finished = FinishedJobRegistry("agent-tasks", connection=redis_conn)
assert job.id in finished.get_job_ids()

failed = FailedJobRegistry("agent-tasks", connection=redis_conn)
# After a failed job:
assert job.id in failed.get_job_ids()
```

### Alembic migration file structure for native Enum types
```python
# Source: Alembic autogenerate output pattern for native Enum columns
import sqlalchemy as sa

def upgrade() -> None:
    # Postgres: Enum types are created by sa.Enum() implicitly
    # but explicit handling is safer for downgrade:
    workflowstatus = sa.Enum('running', 'done', 'failed', name='workflowstatus')
    workflowstepstatus = sa.Enum('pending', 'running', 'done', 'failed', 'cancelled', name='workflowstepstatus')
    workflowstatus.create(op.get_bind(), checkfirst=True)
    workflowstepstatus.create(op.get_bind(), checkfirst=True)
    op.create_table('workflow_runs', ...)

def downgrade() -> None:
    op.drop_table('workflow_runs')
    op.drop_table('workflow_run_steps')
    sa.Enum(name='workflowstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='workflowstepstatus').drop(op.get_bind(), checkfirst=True)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `declarative_base()` function | `DeclarativeBase` subclass | SQLAlchemy 2.0 (Jan 2023) | Old function still works but emits deprecation warning in 2.x |
| `Column(String)` style | `mapped_column(String)` with `Mapped[str]` type hint | SQLAlchemy 2.0 | 1.x style is not supported in spec; CLAUDE.md forbids it |
| `AgentExecutor` | `create_react_agent` from `langgraph.prebuilt` | LangChain 0.2 | Not relevant to Phase 2 but documented in CLAUDE.md |

---

## Open Questions

1. **Alembic autogenerate vs manual migration for initial models**
   - What we know: `alembic revision --autogenerate` can generate the migration if env.py is correct; manual authoring also works
   - What's unclear: Whether autogenerate correctly handles all 5 Enum types across 4 models without manual adjustment
   - Recommendation: Run autogenerate first, then inspect and manually adjust ENUM type CREATE/DROP in upgrade()/downgrade() for correctness. Do not blindly trust the autogenerated output.

2. **QUEUE-07 "queued" log event — where to emit it**
   - What we know: `LoggingWorker.perform_job` only fires when a job starts processing, not when it's enqueued
   - What's unclear: Whether QUEUE-07 strictly requires logging at enqueue time, or whether "queued" state is implied by "starting"
   - Recommendation: Log the "queued" event at the enqueue call site (in the integration test for this phase). Document that Phase 5 worker job dispatch logic will add per-enqueue logging there. If the requirement demands a worker-side hook, RQ 2.7 does not expose a clean "on_enqueue" event at the worker level.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL 15 | SQLAlchemy models, Alembic migration | ✓ via Docker | 15 (docker-compose) | — |
| Redis 7 | RQ worker, integration test (D-07) | ✓ via Docker | 7 (docker-compose) | — |
| Python 3.12 | Runtime | ✓ | 3.12 (uv-managed) | — |
| SQLAlchemy | Model definitions | ✓ | 2.0.48 (installed) | — |
| Alembic | Migrations | ✓ | >=1.13 (pyproject.toml) | — |
| Pydantic | Task types | ✓ | 2.12.5 (installed) | — |
| RQ | Worker, queue | ✓ | 2.7.0 (installed) | — |
| psycopg2-binary | PostgreSQL driver | ✓ | in pyproject.toml | — |

**Missing dependencies with no fallback:** None.

**Note:** Integration test (D-07) requires Docker to be running (`docker compose up`). Structural tests (model imports, pickle round-trip, file existence) run without Docker.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (installed in dev deps) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — testpaths=["tests"], asyncio_mode="auto" |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QUEUE-01 | Redis AOF persistence configured | manual / docker-compose verify | `docker compose exec redis redis-cli config get appendfsync` | ✅ docker-compose.yml from Phase 1 |
| QUEUE-02 | Single worker, concurrency=1 | unit | `uv run pytest tests/test_queue_models.py::test_logging_worker_is_single_worker -x` | ❌ Wave 0 |
| QUEUE-03 | Pydantic models importable and pickle round-trip | unit | `uv run pytest tests/test_task_types.py -x` | ❌ Wave 0 |
| QUEUE-04 | Jobs retain result_ttl=-1 / failure_ttl=-1 | integration (live Redis) | `uv run pytest tests/test_rq_integration.py::test_job_retention -x` | ❌ Wave 0 |
| QUEUE-05 | Failed jobs appear in FailedJobRegistry | integration (live Redis) | `uv run pytest tests/test_rq_integration.py::test_failed_job_registry -x` | ❌ Wave 0 |
| QUEUE-06 | at_front=True enqueue works | integration (live Redis) | `uv run pytest tests/test_rq_integration.py::test_at_front_enqueue -x` | ❌ Wave 0 |
| QUEUE-07 | LoggingWorker emits structured log lines | unit | `uv run pytest tests/test_queue_models.py::test_logging_worker_emits_logs -x` | ❌ Wave 0 |
| WF-01 | WorkflowRun/WorkflowRunStep models importable, Alembic migration applies | integration (live Postgres) | `uv run migrate && uv run pytest tests/test_db_models.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q --ignore=tests/test_rq_integration.py --ignore=tests/test_db_models.py` (unit tests only, no Docker)
- **Per wave merge:** `uv run pytest tests/` (full suite, requires Docker)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_task_types.py` — covers QUEUE-03 (all 8 model classes importable, pickle round-trips)
- [ ] `tests/test_queue_models.py` — covers QUEUE-02 (LoggingWorker structure), QUEUE-07 (log emission)
- [ ] `tests/test_rq_integration.py` — covers QUEUE-04, QUEUE-05, QUEUE-06 (requires live Redis; marked with pytest marker `integration`)
- [ ] `tests/test_db_models.py` — covers WF-01 (models importable, migration applies; requires live Postgres)
- [ ] `pytest.ini_options` marker: add `markers = ["integration: requires Docker services"]` to `pyproject.toml`

---

## Project Constraints (from CLAUDE.md)

All of the following directives are locked and the planner MUST verify compliance:

| Directive | Impact on Phase 2 |
|-----------|-------------------|
| SQLAlchemy 2.x `Mapped` + `mapped_column` style mandated; 1.x `Column` style forbidden | All model fields must use `Mapped[type] = mapped_column(...)` syntax |
| Pydantic v2 exclusively; never mix v1 and v2 | `BaseModel` with `list[...]`, `Literal[...]` (no quotes) syntax throughout `task_types.py` |
| Redis AOF `appendfsync always` required | Verify docker-compose still has this; no new configuration needed in Phase 2 |
| `result_ttl=-1` and `failure_ttl=-1` on all RQ jobs | Enforce at every `queue.enqueue()` call site |
| Concurrency = 1 (sequential worker) | Single `LoggingWorker` instance; no threads, no multiprocessing |
| LLM full connection details per task type; API tokens from env vars | Not applicable to Phase 2 (no agent code) |
| LangWatch instrumentation active during production and experiment runs | Not applicable to Phase 2 (no agent code) |
| Queue name is `agent-tasks` | Already in `runner.py`; must remain unchanged |

---

## Sources

### Primary (HIGH confidence)
- `plans/01-kickoff/spec.md` — verbatim SQLAlchemy model field definitions, Pydantic task I/O model definitions, workflow storage schema
- RQ 2.7.0 installed source — `Worker.perform_job`, `Worker.__init__`, `Queue.enqueue`, `Queue.enqueue_call`, `FinishedJobRegistry`, `FailedJobRegistry` — all inspected directly against installed version
- SQLAlchemy 2.0.48 installed — `DeclarativeBase`, `Mapped`, `mapped_column` imports verified
- Pydantic 2.12.5 installed — pickle round-trip verified with actual `BaseModel` subclass

### Secondary (MEDIUM confidence)
- Alembic native ENUM pitfall — well-known pattern from SQLAlchemy/Alembic ecosystem; recommended handling verified against Alembic documentation pattern for `sa.Enum.create()`/`sa.Enum.drop()`

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages installed and verified against actual source
- Architecture: HIGH — model schemas verbatim from spec; lock file patterns confirmed
- Pitfalls: HIGH — Alembic ENUM issue is well-documented; other pitfalls verified against installed RQ/SQLAlchemy source
- Test map: HIGH — all test patterns consistent with Phase 1 established approach

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable ecosystem; SQLAlchemy/RQ/Pydantic APIs are stable)
