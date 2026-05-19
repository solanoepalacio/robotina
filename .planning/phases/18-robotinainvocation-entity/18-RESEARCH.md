# Phase 18: RobotinaInvocation entity - Research

**Researched:** 2026-05-19
**Domain:** SQLAlchemy 2.x additive entity + nullable FK column + Pydantic outcome shape + single-cell Jinja template change
**Confidence:** HIGH (every claim verified against on-disk Phase-17 baseline; no library-version research required — same stack as Phase 17)

## Summary

Phase 18 is a strict additive entity-introduction phase layered on top of Phase 17's `WorkflowRun.conversation_id` + `WorkflowRun.outcome` baseline. The single Alembic revision `0007_robotina_invocations.py` (down_revision `"0006"`) creates one new table (`robotina_invocations`) and adds one nullable column (`workflow_runs.triggered_by_invocation_id`). Code touches mirror Phase 17's topology exactly: `StartWorkflowTool` gains a parallel `invocation_id` constructor field beside the just-landed `conversation_id`; `queue_workflow` gains a parallel required arg; `jobs.py::run_task` reads `job.meta["invocation_id"]` next to its existing `task_type` read; the gateway inserts the new row in the same transaction as the StoredMessage. The dashboard touch is one `<dt>/<dd>` pair in the existing `kv-grid`.

The `AddRecipeOutcome` Pydantic model replaces the Phase 17 `WorkflowOutcome` stub in `queue/task_types.py` — Phase 18 only defines the shape; Phase 20's `finalize-outcome` step will populate `WorkflowRun.outcome` from it.

**The decisions are fully locked in CONTEXT.md (D-01..D-25, auto-mode).** Research output here is verification-and-citation, not exploration. Every code-shape claim below was confirmed by reading the on-disk file at the line ranges CONTEXT.md cites.

**Primary recommendation:** Mirror Phase 17's `conversation_id` topology one-for-one. Resist any temptation to refactor the parallel rails (`chat_id`/`user_id`/`platform` stay on `StartWorkflowTool` per ARCH-05's deprecation window). The riskiest test is the gateway dedup-no-orphan-invocation case (D-24): a duplicate `platform_message_id` must NOT insert a RobotinaInvocation row — this is the single load-bearing new test in the phase.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

> Verbatim from `.planning/phases/18-robotinainvocation-entity/18-CONTEXT.md` (auto-mode). All D-NN below are Claude's call under the no-stopping system reminder. The user may redirect any decision before plan-phase runs.

#### Migration shape

- **D-01:** **Single Alembic revision** (`0007_robotina_invocations.py`) — creates the `robotina_invocations` table + its enums + its `UniqueConstraint` AND adds nullable `workflow_runs.triggered_by_invocation_id` (FK → `robotina_invocations.id`) in one upgrade. revision=`"0007"`, down_revision=`"0006"`. Style mirrors `0006_conversation_fk_and_outcome.py` (Phase 17).
- **D-02:** **`triggered_by_invocation_id` is NULLABLE in v1.1.** No backfill, no NOT NULL enforcement, no pre-clean of `workflow_runs` for this phase. NULL = "historical, ignored by wake."
- **D-03:** **No defensive backfill code, no orphan-handling branches.** Migration is `op.create_table(robotina_invocations, ...)` + `op.add_column("workflow_runs", Column(..., nullable=True))`. No `op.execute("UPDATE …")`, no synthetic invocation row creation.

#### RobotinaInvocation schema

- **D-04:** **Place in `src/robotina/queue/models.py`** alongside `WorkflowRun` (ARCHITECTURE §2.4). Satisfies DASH-14 automatically.
- **D-05:** **Ship the full Phase-20-ready schema in Phase 18** — `wake_dispatched_at`, `rq_job_id`, `status`, `started_at`, `completed_at` all land now, even though Phase 18 only writes `status=PENDING`.
- **D-06:** **`InvocationTrigger` enum: `USER_MESSAGE`, `WORKFLOW_COMPLETION`, `CRON` — full set.** Phase 18 only emits `USER_MESSAGE` rows.
- **D-07:** **`InvocationStatus` enum: `PENDING`, `RUNNING`, `DONE`, `FAILED` — full set.** Phase 18 writes only `PENDING`.
- **D-08:** **Add the `UniqueConstraint("trigger_ref_id", "trigger", name="ux_invocation_workflow_completion_once")` upfront in Phase 18.** Effectively dormant in Phase 18 (USER_MESSAGE rows have unique `StoredMessage.id`s); load-bearing wake-rule idempotency guard for Phase 20 (Pitfall 1 + Pitfall 2).
- **D-09:** **Column naming uses `rq_job_id` (not `job_id`).** Disambiguates from `WorkflowRunStep.task_job_id`. ARCH-02's `job_id` wording in REQUIREMENTS.md will be updated to `rq_job_id` in the same commit (D-25).
- **D-10:** **Suggested schema** (planner has discretion on exact SQLAlchemy syntax — see Code Examples §1 below). PostgreSQL `Enum` follows Phase 2 convention (`postgresql.ENUM(create_type=False)` inside Alembic `op.create_table`); `values_callable` ensures the DB stores enum values, not names.

#### `invocation_id` plumbing

- **D-11:** **Gateway insertion order in `handler.py`:** Conversation upsert → StoredMessage.flush() with `IntegrityError` short-circuit (no orphan invocation) → NEW: insert `RobotinaInvocation(conversation_id=conv.id, trigger=USER_MESSAGE, trigger_ref_id=stored.id, status=PENDING)` and `session.flush()` for `inv.id` → fetch history → commit → enqueue with `meta={'task_type': 'handle-incoming-message', 'invocation_id': inv.id}`.
- **D-12:** **`invocation_id` flows through `job.meta['invocation_id']`.** Do NOT add it to `IncomingMessageInput`. Symmetric with the existing `meta['task_type']` channel.
- **D-13:** **`StartWorkflowTool` gains required `invocation_id: str` constructor field.** Mirrors Phase 17 D-03's `conversation_id` injection. No `NonEmptyInvocationId` Pydantic alias (LLM cannot supply it; FK constraint is sufficient).
- **D-14:** **`queue_workflow` signature gains required `triggered_by_invocation_id: str` arg.** No default, no fallback. Mirrors Phase 17 D-05.
- **D-15:** **`run_task` (jobs.py) — diff in `handle-incoming-message` branch:**
  ```python
  invocation_id = job.meta["invocation_id"]  # bracket read — KeyError if missing
  tools.append(StartWorkflowTool(
      chat_id=task_input.chat_id, user_id=task_input.user_id,
      platform=task_input.platform, household_id=task_input.household_id,
      conversation_id=conversation.id,       # Phase 17
      invocation_id=invocation_id,           # Phase 18
  ))
  ```

#### AddRecipeOutcome Pydantic shape

- **D-16:** **Define `AddRecipeOutcome` in `src/robotina/queue/task_types.py`.** Replaces the Phase 17 `WorkflowOutcome` placeholder stub.
- **D-17:** Shape:
  ```python
  class AddRecipeOutcome(BaseModel):
      model_config = ConfigDict(extra="forbid")
      status: Literal["success", "failure"]
      recipe_id: str | None = None
      recipe_name: str | None = None
      recipe_slug: str | None = None
      failure_reason: str | None = None
      image_present: bool = False
  ```
- **D-18:** **Replace, don't supplement, the Phase 17 `WorkflowOutcome` stub.** No envelope until ≥2 workflow types with distinct outcome shapes exist.

#### Dashboard surfacing

- **D-19:** Add `triggered_by_invocation_id` to the WorkflowRun detail view (`workflow.html`) — and ONLY that. New `<dt>/<dd>` pair in the existing `kv-grid`:
  ```jinja
  <dt>Triggered by invocation</dt>
  <dd class="mono">{{ run.triggered_by_invocation_id or "—" }}</dd>
  ```
- **D-20:** Defer to Phase 20: `conversation_id` rendering (DASH-10), `outcome` summary cell (DASH-12), list-view changes, dedicated invocation list/detail view.
- **D-21:** Module-isolation grep gate (DASH-14): no work required. Verify with `uv run pytest tests/dashboard/test_independence.py -x`.

#### Test strategy

- **D-22:** Unit test for `StartWorkflowTool` — `invocation_id` propagates to `queue_workflow`.
- **D-23:** Integration test for `queue_workflow` — real Postgres, FK persisted on the row.
- **D-24:** Gateway handler tests — invocation insert, `meta['invocation_id']` set, **dedup short-circuits before insert** (no orphan).
- **D-25:** REQUIREMENTS.md ARCH-02 wording edit (`job_id` → `rq_job_id`) in the same commit as the schema change.

### Claude's Discretion

> Verbatim from CONTEXT.md `<decisions>` "Claude's Discretion" subsection. The planner may decide these without re-raising to the user.

- **Migration file naming:** `migrations/versions/0007_robotina_invocations.py`. Style mirrors `0006_conversation_fk_and_outcome.py`. No branch labels, no `depends_on`.
- **PostgreSQL ENUM creation:** follow the Phase 2 lesson (`postgresql.ENUM(create_type=False)` inside `op.create_table`; pre-create types with `DO $$ BEGIN IF NOT EXISTS ... END $$` idempotent guard).
- **`InvocationTrigger` / `InvocationStatus` location:** co-locate with `WorkflowStatus` / `WorkflowStepStatus` at the top of `src/robotina/queue/models.py`.
- **`AddRecipeOutcome` placement in `task_types.py`:** alongside the existing recipe models, after `RecipeLoadOutput`. Add a section header comment block matching the existing style.
- **No `NonEmptyInvocationId` Pydantic alias.** FK constraint + bracket-key read in `run_task` cover the empty-string surface.
- **Skip a `ScheduledTask`-style preview for the `CRON` trigger:** the enum value lands in Phase 18 but no model or table for `ScheduledTask` exists yet.

### Deferred Ideas (OUT OF SCOPE)

> Verbatim from CONTEXT.md `<deferred>`. Do not include any of these in the plan.

- Wake rule + `wake_dispatched_at` UPDATE-RETURNING idempotency — Phase 20.
- `InvocationStatus` transitions (PENDING → RUNNING → DONE/FAILED) + `_check_and_dispatch_wake` helper — Phase 20.
- `WakeInvocationInput` model + `run_task` dispatch on `trigger=WORKFLOW_COMPLETION` — Phase 20.
- Pre-assigned `rq_job_id` for the next invocation (transactional advancement for wake invocations) — Phase 20.
- Startup reconciler for orphan invocations (`wake_dispatched_at IS NOT NULL but no RQ job`) — Phase 20.
- `finalize-outcome` deterministic step that writes `WorkflowRun.outcome` from accumulated artifacts — Phase 20. Phase 18 only defines the shape.
- Dashboard rendering of `conversation_id` (DASH-10) — Phase 20.
- Dashboard rendering of the `outcome` summary cell (DASH-12) — Phase 20.
- Dashboard list-view changes for new columns — Phase 20.
- Dedicated `RobotinaInvocation` list/detail dashboard view — backlog (DASH-13 explicitly marks this "nice-to-have").
- Multi-call `StartWorkflowTool` (one invocation → N workflows in one LLM turn) — Phase 19 evidence first; Phase 21 flips the tool.
- Dropping `chat_id`/`user_id`/`platform` from `StartWorkflowTool` — defer until ARCH-05 deprecation window closes (post-v1.1).
- CRON-trigger `ScheduledTask` model + `trigger=CRON` rows actually being written — deferred scheduler milestone.
- `WorkflowOutcome` envelope wrapping per-workflow shapes — defer until ≥2 workflow types with distinct outcome shapes exist.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ARCH-02 | New `RobotinaInvocation` SQLAlchemy model records every Robotina LLM turn with `trigger`, `trigger_ref_id`, `conversation_id`, `started_at`, `completed_at`, `job_id`, `wake_dispatched_at`. | Standard Stack §"Schema model" + Code Examples §1 (full SQLAlchemy 2.x `Mapped`/`mapped_column` template per D-10). REQUIREMENTS.md `job_id` wording updated to `rq_job_id` in the same commit per D-25. |
| ARCH-03 | `WorkflowRun` rows have a `triggered_by_invocation_id` FK to `RobotinaInvocation`; the `StartWorkflowTool` populates it; the column lands nullable in v1.1. | Architecture Patterns §"Migration topology" + Code Examples §2 (migration upgrade body) + §4 (`queue_workflow` signature + `StartWorkflowTool` constructor field). |
| ARCH-04 | `WorkflowRun.outcome` is a JSON column written by a deterministic terminal step; for `add-recipe` workflows it serializes a Pydantic `AddRecipeOutcome` model (success/failure + recipe id/name OR failure reason + `image_present` flag) targeted at < ~300 bytes per workflow. | Code Examples §3 (`AddRecipeOutcome` Pydantic class). Phase 18 only **defines** the shape; the `WorkflowRun.outcome` JSON column already exists from Phase 17 (verified at `src/robotina/queue/models.py:46`). Phase 20's `finalize-outcome` step populates it. |
| DASH-13 | Dashboard surfaces RobotinaInvocation rows linked to a WorkflowRun (at minimum: `triggered_by_invocation_id` appears on the detail page). | Code Examples §6 (single new `<dt>/<dd>` pair in `workflow.html`'s `kv-grid`). UI-SPEC contract approved 2026-05-19. |
| DASH-14 | Dashboard module-isolation grep gate (Phase 13 D-01) still passes after model imports change — `RobotinaInvocation` is imported from `robotina.queue.models` like `WorkflowRun`. | Architecture Patterns §"Module-isolation invariant" + existing `tests/dashboard/test_independence.py` continues to pass without modification (D-04 places the model in the already-allowed module). |
</phase_requirements>

## Architectural Responsibility Map

> Single-tier Python service (no client/server split). The tiers are intra-service layers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Persist `RobotinaInvocation` row on user message | Gateway (`src/robotina/gateway/handler.py`) | Queue models (`src/robotina/queue/models.py`) | Gateway is the entrypoint; it owns the StoredMessage transaction and must own the parallel invocation insert so the two land atomically. Queue layer owns the schema definition only. |
| Schema (table + enums + unique constraint) | Queue models (`src/robotina/queue/models.py`) | Migration (`migrations/versions/0007_*.py`) | Established pattern: SQLAlchemy 2.x `Mapped` classes live in `queue/models.py` (WorkflowRun, WorkflowRunStep); Alembic mirrors via raw `sa.Column` / `postgresql.ENUM`. D-04 explicitly co-locates with `WorkflowRun`. |
| Propagate `invocation_id` through the queue boundary | RQ `job.meta` channel | — | Job-lifecycle context (already carries `task_type`, `queue_name`). Adding `invocation_id` is symmetric with Phase 17's pattern of resolving runtime context at tool-construction time in `run_task` (D-12 / D-15). |
| Stamp `WorkflowRun.triggered_by_invocation_id` | Workflow runner (`src/robotina/queue/workflow_runner.py::queue_workflow`) | StartWorkflowTool (`src/robotina/agent/tools/start_workflow.py`) | The runner owns the row write; the tool is constructor-injected and threads the value down. Mirrors Phase 17's `conversation_id` topology one-for-one. |
| Define `AddRecipeOutcome` shape | `src/robotina/queue/task_types.py` | — | Already the home for cross-module Pydantic contracts; replaces the Phase 17 `WorkflowOutcome` stub at the same location. |
| Render `triggered_by_invocation_id` cell | Dashboard template (`src/robotina/dashboard/templates/workflow.html`) | Dashboard queries (`src/robotina/dashboard/queries.py`) | Template reads the FK string directly off `run`; existing `get_workflow_with_steps` query auto-picks up the new column with no edit needed (D-19). |

## Standard Stack

> No new libraries. Phase 18 uses the same stack as Phase 17 (verified against on-disk `pyproject.toml` and existing imports).

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | `2.x` (`>=2.0`) | ORM for `RobotinaInvocation` model + FK column | Already in use throughout `src/robotina/queue/models.py`; `Mapped` / `mapped_column` 2.x style is the established pattern for every column on `WorkflowRun` and `WorkflowRunStep`. **[VERIFIED: src/robotina/queue/models.py:5-8 imports + every column declaration]** |
| Alembic | `>=1.13` | Schema migration `0007_robotina_invocations.py` | Already in use; the canonical template is `migrations/versions/0006_conversation_fk_and_outcome.py` (43 lines, simple `op.add_column` × 2). For ENUM creation, the canonical template is `0002_models.py` (`DO $$ BEGIN IF NOT EXISTS ... END $$` idiom + `postgresql.ENUM(create_type=False)` in `op.create_table`). **[VERIFIED: migrations/versions/0002_models.py:17-44, 0006_conversation_fk_and_outcome.py]** |
| Pydantic | `v2` (`>=2.7`) | `AddRecipeOutcome` model in `queue/task_types.py` | Every existing model in `task_types.py` is Pydantic v2 (`model_config = ConfigDict(extra="forbid")`, `Literal[...]`, `X \| None = None`). Same conventions apply. **[VERIFIED: src/robotina/queue/task_types.py:337-341 (Phase 17 WorkflowOutcome stub)]** |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `redis` + `rq` | `>=5.0` / `>=2.5` | `q.enqueue(..., meta={'task_type': ..., 'invocation_id': ...})` | Already in use at `src/robotina/gateway/handler.py:124-132` and `src/robotina/queue/workflow_runner.py:196-203`. Adding a sibling key to `meta` is a no-op change to the call site. **[VERIFIED]** |
| `langchain-core` BaseTool | `>=1.2` | `StartWorkflowTool` constructor extension | Tool already subclasses `BaseTool` with Pydantic fields; adding `invocation_id: str` is the same pattern as the Phase 17 `conversation_id: str` field. **[VERIFIED: src/robotina/agent/tools/start_workflow.py:69-138]** |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Co-locating `RobotinaInvocation` in `queue/models.py` (D-04) | Place in `gateway/models.py` next to `Conversation`/`StoredMessage` | Rejected by CONTEXT.md D-04 + ARCHITECTURE §2.4: gateway → queue dependency is one-way; placing the model in gateway/models would force `workflow_runner` to import from `gateway`, creating a cycle. The chosen placement also automatically satisfies DASH-14. |
| `meta['invocation_id']` (D-12) | Add `invocation_id` field to `IncomingMessageInput` | Rejected by CONTEXT.md D-12: couples the message-input schema to a queue-lifecycle id the input doesn't logically own; breaks symmetry with Phase 17's D-04 pattern. |
| `NonEmptyInvocationId` Pydantic alias | Plain `str` field on `StartWorkflowTool` (D-13) | Rejected by CONTEXT.md D-13: the LLM cannot supply `invocation_id` (it's resolved in `run_task` from `job.meta` and constructor-injected); the LLM-shadowing surface that motivated `NonEmptyHouseholdId` does not exist. FK constraint + bracket-key read cover the empty-string surface. |
| Discriminated union for `AddRecipeOutcome` | Optional fields + `extra='forbid'` (D-17) | Rejected by CONTEXT.md D-17: Pydantic's `Field(discriminator=...)` adds verbose construction friction for a 2-variant shape. Phase 20's `finalize-outcome` is the single producer; runtime guarantee is producer-side. Can be elevated to `model_validator` later if needed. |
| `WorkflowOutcome` envelope (architecture's `{workflow_run_id, workflow_type, status, summary, structured}` wrapper) | `AddRecipeOutcome` directly in `WorkflowRun.outcome` (D-18) | Rejected by CONTEXT.md D-18: premature abstraction for a single workflow type in v1.1. Phase 23 (URL ingestion) reuses `AddRecipeOutcome`. Introduce the envelope when a non-recipe workflow appears. |

**Installation:** No new packages. The phase is implementable with the existing dependency set in `pyproject.toml`.

**Version verification:** Not applicable — Phase 17 baseline already validates the relevant package versions. Phase 18 changes no `pyproject.toml` entries.

## Architecture Patterns

### System Architecture Diagram

Data flow during a single user-message turn under Phase 18 (post-deploy):

```
Telegram user
    │
    │ HTTPS POST (PTB webhook / long-poll)
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  gateway/handler.py::handle_message                                 │
│                                                                     │
│  1. Conversation upsert  (existing — Phase 3)                       │
│  2. StoredMessage insert ─── IntegrityError? → rollback, RETURN     │
│                              (no orphan invocation — D-11 critical) │
│  2b. NEW: RobotinaInvocation insert                                 │
│      (conversation_id, trigger=USER_MESSAGE,                        │
│       trigger_ref_id=stored.id, status=PENDING)                     │
│      session.flush() → inv.id materialized                          │
│  3. Fetch history (existing)                                        │
│  4. session.commit() (existing)                                     │
│  5. q.enqueue(..., meta={                                           │
│         'task_type': 'handle-incoming-message',                     │
│         'invocation_id': inv.id})  ← NEW key                        │
└─────────────────────────────────────────────────────────────────────┘
    │
    │ RQ job in agent-tasks queue (Redis AOF appendfsync=always)
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  queue/jobs.py::run_task  (handle-incoming-message branch)          │
│                                                                     │
│  • task_type = job.meta['task_type']  (existing)                    │
│  • invocation_id = job.meta['invocation_id']  ← NEW bracket read    │
│  • conversation = SELECT … one()  (Phase 17)                        │
│  • tools.append(StartWorkflowTool(                                  │
│        chat_id, user_id, platform, household_id,                    │
│        conversation_id=conversation.id,                             │
│        invocation_id=invocation_id))  ← NEW kwarg                   │
│  • agent.invoke(...)                                                │
└─────────────────────────────────────────────────────────────────────┘
    │
    │ (LLM emits start-workflow tool call)
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  agent/tools/start_workflow.py::StartWorkflowTool._run              │
│                                                                     │
│  • queue_workflow(                                                  │
│        workflow_type=..., shared_context=...,                       │
│        household_id=self.household_id,                              │
│        conversation_id=self.conversation_id,                        │
│        triggered_by_invocation_id=self.invocation_id, ← NEW arg     │
│        queue=..., session=...)                                      │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  queue/workflow_runner.py::queue_workflow                           │
│                                                                     │
│  • WorkflowRun(                                                     │
│        workflow_type, household_id, shared_context,                 │
│        conversation_id=conversation_id,                             │
│        triggered_by_invocation_id=triggered_by_invocation_id,       │
│        status=PENDING) ← NEW kwarg, NULLABLE FK                     │
│  • session.add(run); session.flush(); …                             │
│  • session.commit()                                                 │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
  WorkflowRun row in workflow_runs table now has BOTH
  conversation_id (NOT NULL, Phase 17) and
  triggered_by_invocation_id (nullable, Phase 18)

  Dashboard detail-view (separate read path):
  GET /workflows/{id} → workflow.html renders new <dd> with FK value
```

**[VERIFIED: all flow points cross-referenced with the on-disk Phase-17 baseline at the file:line numbers cited in CONTEXT.md `<canonical_refs>`]**

### Recommended Project Structure

No new directories. Only the listed files are touched:

```
src/robotina/
├── queue/
│   ├── models.py              # ADD: InvocationTrigger, InvocationStatus enums + RobotinaInvocation class
│   │                          # ADD: triggered_by_invocation_id column on WorkflowRun
│   ├── task_types.py          # REPLACE: WorkflowOutcome stub → AddRecipeOutcome
│   ├── workflow_runner.py     # MODIFY: queue_workflow signature + WorkflowRun(...) kwargs
│   └── jobs.py                # MODIFY: handle-incoming-message branch reads meta['invocation_id']
├── agent/
│   └── tools/
│       └── start_workflow.py  # MODIFY: invocation_id constructor field + _run passes it to queue_workflow
├── gateway/
│   └── handler.py             # MODIFY: insert RobotinaInvocation; add meta['invocation_id']
└── dashboard/
    └── templates/
        └── workflow.html      # MODIFY: one new <dt>/<dd> in kv-grid

migrations/versions/
└── 0007_robotina_invocations.py  # NEW: revision='0007', down_revision='0006'

tests/
├── test_gateway.py            # ADD: 3 new assertions (D-24: invocation insert, meta key, dedup no-orphan)
├── test_workflow_runner.py    # ADD: queue_workflow persists triggered_by_invocation_id (D-23)
│                              # ADD: migration 0007 upgrade/downgrade integration test
├── unit/test_start_workflow_tool.py  # ADD: invocation_id propagates to queue_workflow (D-22)
└── dashboard/test_detail_view.py     # ADD: template renders new <dd> (and "—" when NULL)

.planning/
└── REQUIREMENTS.md            # MODIFY: ARCH-02 wording (job_id → rq_job_id) per D-25
```

### Pattern 1: Mirror Phase 17's `conversation_id` topology

**What:** Every Phase-17 conversation_id touch-site gains a parallel rail for invocation_id. Never rewrite the conversation_id lines — add invocation_id as an additional argument next to it.

**When to use:** Every code change in Phase 18 that involves `StartWorkflowTool` / `queue_workflow` / `run_task`.

**Example:** Diff of `StartWorkflowTool.__init__` field declarations (on-disk Phase 17 baseline → Phase 18 target):

```python
# src/robotina/agent/tools/start_workflow.py (current; lines 127-138)
chat_id: str = ""
user_id: str = ""
platform: str = ""
household_id: NonEmptyHouseholdId
conversation_id: str

# Phase 18 target (parallel addition; comment block per CONTEXT.md style)
chat_id: str = ""
user_id: str = ""
platform: str = ""
household_id: NonEmptyHouseholdId
conversation_id: str
# Phase 18 (ARCH-02 / D-13): invocation_id is constructor-injected by
# run_task() from job.meta["invocation_id"]. No Pydantic alias — the LLM
# never supplies this field; FK NOT NULL + bracket-key meta read upstream
# cover the invariant. Mirrors the conversation_id pattern above.
invocation_id: str
```

**[VERIFIED: file structure at src/robotina/agent/tools/start_workflow.py:127-138 matches CONTEXT.md description]**

### Pattern 2: Migration topology — single revision, table + nullable FK column

**What:** One Alembic revision (`0007_robotina_invocations.py`) creates the new table AND adds the nullable FK column on `workflow_runs` in one `upgrade()` body.

**When to use:** Phase 18's single schema migration.

**Example:** See Code Examples §2 for the full template.

**Why one revision (D-01):** Mirrors Phase 17's "one revision per phase" pattern; the column references the table so they're co-dependent. Splitting would require brittle ordering across two revisions for no gain at this scale.

### Pattern 3: Same-transaction insertion with `session.flush()` to materialize FK

**What:** New `RobotinaInvocation` row goes into the existing `with SessionLocal() as session: ... session.commit()` block in `handle_message`. Use `session.flush()` (not `session.commit()`) between StoredMessage and RobotinaInvocation so `inv.id` is materialized for the enqueue meta but the whole transaction commits atomically.

**When to use:** The new step 2b in `handler.py`.

**Example:** Already in the file — Conversation upsert at lines 56-72 uses the same idiom (`session.add(conv); session.flush()`).

### Pattern 4: Module-isolation invariant (DASH-14)

**What:** Dashboard imports ONLY `robotina.queue.models`, `robotina.db`, `robotina.queue.task_types` (Phase 13 D-01 locked allow-list, AST-enforced).

**When to use:** Verifying Phase 18 didn't break the rule.

**Verification:**
- `RobotinaInvocation` lives in `robotina.queue.models` (D-04) — already an allowed import source.
- Template reads `run.triggered_by_invocation_id` (a string FK) directly off the existing `WorkflowRun` instance — no new import in template, queries.py, or any dashboard module.
- `tests/dashboard/test_independence.py` continues to pass without modification. **[VERIFIED: existing test file, lines 18-66, 69-123]**

### Anti-Patterns to Avoid

- **Pre-inserting the invocation BEFORE the StoredMessage dedup short-circuit:** Creates orphan PENDING invocations on duplicate messages. CONTEXT.md D-11 is explicit about the ordering. The test in D-24 is the load-bearing guard.
- **Adding `invocation_id` to `IncomingMessageInput`:** Couples message schema to queue-lifecycle id; breaks symmetry with Phase 17. D-12 explicitly rejects this.
- **Re-truncating `workflow_runs` for Phase 18 deploy:** Phase 17 already did this once; D-02 explicitly states no re-truncation. The nullable FK accepts NULL on historical rows.
- **Introducing a `WorkflowOutcome` envelope around `AddRecipeOutcome`:** Premature abstraction (`feedback_avoid_premature_abstraction.md`). D-18 defers until ≥2 workflow types exist.
- **Adding a JOIN to `RobotinaInvocation` in `get_workflow_with_steps`:** The detail view only needs the FK string. D-19 explicitly forbids the JOIN.
- **Making `invocation_id` mutable shared state on the tool:** Pitfall 5 — constructor injection is what keeps Phase 21's multi-call StartWorkflowTool race-free. Re-litigating it then would introduce a race.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Enum stored in Postgres as native ENUM type | Custom CHECK constraint + string column + Python-side validation | `sqlalchemy.Enum(InvocationTrigger, values_callable=lambda x: [e.value for e in x])` + `postgresql.ENUM(create_type=False)` in migration | Already the established pattern — see `WorkflowStatus`, `WorkflowStepStatus`, `Platform`, `MessageRole`. The `values_callable` lambda is mandatory (Phase 3 lesson: SQLAlchemy stores enum NAMES by default, but Postgres native ENUM expects VALUES). The `DO $$ BEGIN IF NOT EXISTS ... END $$` idempotency guard in Alembic is established at `migrations/versions/0002_models.py:21-35`. |
| Idempotent enum-type creation on re-run | `CREATE TYPE IF NOT EXISTS …` | `DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '…') THEN CREATE TYPE … END IF; END $$` | PostgreSQL 15 does NOT support `CREATE TYPE IF NOT EXISTS` (STATE.md decision log). Use the established idempotent pattern from `0002_models.py`. |
| UUID-string primary key default | Hand-rolled UUID generator | `default=lambda: str(uuid.uuid4())` in `mapped_column` | Established at every primary key in `src/robotina/queue/models.py` (lines 30, 55) and `src/robotina/gateway/models.py` (lines 29, 42). Re-use verbatim. |
| Partial unique constraint (only `WHERE trigger='workflow_completion'`) | `op.execute("CREATE UNIQUE INDEX ... WHERE ...")` raw SQL | `UniqueConstraint("trigger_ref_id", "trigger", name="ux_invocation_workflow_completion_once")` — full coverage | CONTEXT.md D-08 explicit: PostgreSQL doesn't support partial unique constraints via SQLAlchemy DDL cleanly. Full-coverage uniqueness on `(trigger_ref_id, trigger)` is equivalent strength for the wake-rule guarantee (Pitfall 1). USER_MESSAGE rows trivially satisfy uniqueness because `StoredMessage.platform_message_id` is unique. |
| `created_at` / `updated_at` columns | Manual datetime tracking | `server_default=func.now()` + `onupdate=func.now()` | Established at `WorkflowRun.created_at` / `updated_at` (models.py:47-48). Re-use verbatim. |
| `or "—"` null-cell rendering in Jinja | Custom Python helper / context processor | `{{ run.triggered_by_invocation_id or "—" }}` inline | Established at `workflow.html:13-15` for `created_at` / `updated_at` rows. UI-SPEC §"Visual placement" formalizes the convention. |

**Key insight:** Every pattern Phase 18 needs already exists in the codebase. The job is to mirror, not invent.

## Common Pitfalls

### Pitfall 1: Orphan PENDING invocation on duplicate user message

**What goes wrong:** If the new `RobotinaInvocation` insert is placed BEFORE the `StoredMessage` `IntegrityError` short-circuit (i.e., before the dedup branch at `handler.py:86-89`), every duplicate message creates an extra PENDING invocation row with no corresponding workflow. Phase 20's wake reconciler would treat these as stuck and dispatch a phantom wake.

**Why it happens:** A natural reading of "every user message becomes an invocation row" puts the insert next to the Conversation upsert. But the dedup happens AFTER both — if the message is a duplicate, we want to roll back EVERYTHING, including the invocation.

**How to avoid:** Insert sequence is explicit in CONTEXT.md D-11: (1) Conversation upsert, (2) StoredMessage.flush() — IntegrityError → rollback, return, (2b) RobotinaInvocation insert + flush, (3) history, commit, enqueue. The D-24 test is the load-bearing guard.

**Warning signs:**
- Test `tests/test_gateway.py::test_duplicate_message_skipped` still asserts only on StoredMessage row count — Phase 18 must extend it to also assert zero RobotinaInvocation rows for the duplicate.
- Production: `SELECT COUNT(*) FROM robotina_invocations WHERE status='pending' AND created_at < now() - interval '1 hour'` returns > 0.

### Pitfall 2: PostgreSQL native ENUM uses NAMES by default

**What goes wrong:** Without `values_callable=lambda x: [e.value for e in x]` on the SQLAlchemy `Enum` column, the DB stores `'USER_MESSAGE'` (the Python enum NAME) instead of `'user_message'` (the VALUE). Downstream queries that filter on the lowercase value (per the Phase 3 lesson) silently return zero rows.

**Why it happens:** SQLAlchemy's default is to use enum names. The fix is non-obvious until you've debugged it once.

**How to avoid:** Use the exact same `values_callable` lambda used on every other enum column in the codebase. See Code Examples §1 for the verbatim pattern. STATE.md records this as a Phase 3 lesson.

**Warning signs:** Integration test that inserts a `RobotinaInvocation` with `trigger=InvocationTrigger.USER_MESSAGE`, then `SELECT trigger FROM robotina_invocations` returns `'USER_MESSAGE'` instead of `'user_message'`.

### Pitfall 3: Replacing `WorkflowOutcome` stub breaks an unsuspecting import

**What goes wrong:** Phase 17 D-07 defined `WorkflowOutcome` as a stub. If any Phase 17 test or downstream module already imports it, Phase 18's replacement with `AddRecipeOutcome` (D-18) would break that import.

**Why it happens:** The stub was a code anchor; its purpose was to be replaced.

**How to avoid:** Before replacing, grep for `WorkflowOutcome` across `src/`, `tests/`, `experiments/`. CONTEXT.md D-18 asserts "none yet — Phase 17's stub was unused by design"; verify this is still true at plan time. If any consumer is found, decide: rename consumers in the same commit, OR keep `WorkflowOutcome = AddRecipeOutcome` as an alias for backward compat.

**Warning signs:** `grep -rn "WorkflowOutcome" src/ tests/ experiments/` returns matches beyond the definition site.

**[VERIFIED 2026-05-19: only match in src/ is the definition itself at task_types.py:337; no consumers]**

### Pitfall 4: `job.meta["invocation_id"]` raises KeyError on wake-triggered jobs (Phase 20 concern)

**What goes wrong:** Phase 18 reads `invocation_id = job.meta["invocation_id"]` in the `handle-incoming-message` branch of `run_task`. Phase 20 will introduce wake-triggered invocations that also enqueue jobs (possibly with the same `task_type`). If Phase 20 forgets to set `meta['invocation_id']` on those, Phase 18's bracket read raises KeyError — and the worker crashes.

**Why it happens:** Phase 18 codifies a contract ("`handle-incoming-message` always carries `invocation_id`"). Phase 20 must uphold it.

**How to avoid:** D-15 explicitly chose bracket-read over `.get()` to make this a fail-loud invariant. The Phase 18 plan doesn't need to do anything beyond documenting the contract — the bracket read IS the documentation. Phase 20 research will discover this as soon as they wire wake enqueue.

**Warning signs:** Phase 20 wake-rule rollout produces KeyError logs from `run_task`.

### Pitfall 5: Forgetting to update REQUIREMENTS.md ARCH-02 wording

**What goes wrong:** REQUIREMENTS.md ARCH-02 currently says "`job_id`". The implementation uses `rq_job_id` (D-09). The wording mismatch creates a stale-spec footgun — future readers think there's a `job_id` column that doesn't exist.

**Why it happens:** REQUIREMENTS edits are easy to forget — they live outside the code surface.

**How to avoid:** D-25 explicitly bundles the single-line REQUIREMENTS.md edit with the schema commit, mirroring the Phase 17 D-01 pattern. The planner must include this in the plan's task list, not as a follow-up.

**Warning signs:** Post-Phase-18 grep `grep -n 'job_id' .planning/REQUIREMENTS.md` returns ARCH-02's line with the unqualified `job_id`.

## Code Examples

> Every example below either reproduces an on-disk pattern verbatim or extends it minimally. All `[VERIFIED]` tags refer to the indicated file:line in the current working tree.

### §1. `RobotinaInvocation` SQLAlchemy class (full template per D-10)

```python
# src/robotina/queue/models.py — add after WorkflowStepStatus, before WorkflowRun
# [Source: extends established pattern at src/robotina/queue/models.py:13-48]

class InvocationTrigger(enum.Enum):
    USER_MESSAGE = "user_message"
    WORKFLOW_COMPLETION = "workflow_completion"
    CRON = "cron"  # reserved for the deferred scheduler milestone


class InvocationStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class RobotinaInvocation(Base):
    __tablename__ = "robotina_invocations"
    __table_args__ = (
        # Phase 18 / D-08: idempotency guard for Phase 20's wake rule (Pitfall 1
        # + Pitfall 2). Dormant in Phase 18 because USER_MESSAGE rows have
        # unique StoredMessage.id trigger_ref_ids; load-bearing once
        # WORKFLOW_COMPLETION rows start landing.
        UniqueConstraint(
            "trigger_ref_id", "trigger",
            name="ux_invocation_workflow_completion_once",
        ),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversations.id"), nullable=False
    )
    trigger: Mapped[InvocationTrigger] = mapped_column(
        Enum(InvocationTrigger, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    # USER_MESSAGE        → StoredMessage.id
    # WORKFLOW_COMPLETION → prior RobotinaInvocation.id (set in Phase 20)
    # CRON                → ScheduledTask.id (deferred scheduler milestone)
    trigger_ref_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rq_job_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[InvocationStatus] = mapped_column(
        Enum(InvocationStatus, values_callable=lambda x: [e.value for e in x]),
        default=InvocationStatus.PENDING,
        nullable=False,
    )
    wake_dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

### §2. Adding `triggered_by_invocation_id` to `WorkflowRun`

```python
# src/robotina/queue/models.py — added to existing WorkflowRun class, after `outcome` column
# [Source: extends pattern at src/robotina/queue/models.py:42-48]

# Phase 18 / ARCH-03 / D-02: nullable FK to RobotinaInvocation. NULL in v1.1
# for any historical row (none expected at deploy time per D-02); newly
# created rows always carry the value via queue_workflow's required
# triggered_by_invocation_id arg (D-14).
triggered_by_invocation_id: Mapped[Optional[str]] = mapped_column(
    String, ForeignKey("robotina_invocations.id"), nullable=True
)
```

### §3. Alembic migration `0007_robotina_invocations.py`

```python
# migrations/versions/0007_robotina_invocations.py
# [Source: combines migrations/versions/0006_conversation_fk_and_outcome.py (column-add shape)
# with migrations/versions/0002_models.py:17-44 (ENUM idiom)]

"""robotina_invocations table + workflow_runs.triggered_by_invocation_id (nullable FK)

Phase 18 / ARCH-02 + ARCH-03 + D-01: single revision creating the
RobotinaInvocation table (with its two enums and unique constraint) AND
adding the nullable FK column on workflow_runs in one upgrade. Mirrors
Phase 17's "one revision per phase" pattern.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-19
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent native ENUM creation (Phase 3 lesson: pg_type guard required)
    conn = op.get_bind()
    conn.execute(sa.text(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'invocationtrigger') "
        "THEN CREATE TYPE invocationtrigger AS ENUM ('user_message', 'workflow_completion', 'cron'); END IF; END $$"
    ))
    conn.execute(sa.text(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'invocationstatus') "
        "THEN CREATE TYPE invocationstatus AS ENUM ('pending', 'running', 'done', 'failed'); END IF; END $$"
    ))

    invocationtrigger_col_type = PgEnum(
        'user_message', 'workflow_completion', 'cron',
        name='invocationtrigger', create_type=False,
    )
    invocationstatus_col_type = PgEnum(
        'pending', 'running', 'done', 'failed',
        name='invocationstatus', create_type=False,
    )

    op.create_table(
        'robotina_invocations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('trigger', invocationtrigger_col_type, nullable=False),
        sa.Column('trigger_ref_id', sa.String(), nullable=True),
        sa.Column('rq_job_id', sa.String(), nullable=True),
        sa.Column('status', invocationstatus_col_type, nullable=False),
        sa.Column('wake_dispatched_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trigger_ref_id', 'trigger',
                            name='ux_invocation_workflow_completion_once'),
    )

    op.add_column(
        'workflow_runs',
        sa.Column(
            'triggered_by_invocation_id',
            sa.String(),
            sa.ForeignKey('robotina_invocations.id'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('workflow_runs', 'triggered_by_invocation_id')
    op.drop_table('robotina_invocations')
    conn = op.get_bind()
    conn.execute(sa.text("DROP TYPE IF EXISTS invocationstatus"))
    conn.execute(sa.text("DROP TYPE IF EXISTS invocationtrigger"))
```

### §4. `AddRecipeOutcome` Pydantic model (replaces Phase 17 `WorkflowOutcome` stub)

```python
# src/robotina/queue/task_types.py — replace lines 327-341 (the Phase 17 stub)
# [Source: extends Pydantic v2 patterns established throughout task_types.py]

# ---------------------------------------------------------------------------
# Phase 18 / ARCH-04 — AddRecipeOutcome
# ---------------------------------------------------------------------------
# Per-workflow outcome shape written by the `finalize-outcome` step (Phase 20)
# into WorkflowRun.outcome (JSON column added by Phase 17). Phase 18 only
# defines the shape; no code writes it yet.
#
# Target serialized size: < ~300 bytes per workflow (ARCH-04 / DASH-12).
#
# Per D-18: this REPLACES the Phase 17 WorkflowOutcome stub. No envelope is
# introduced — v1.1 has only one workflow type ("add-recipe") so the
# wrapper would be premature abstraction. Phase 23 (URL ingestion) reuses
# AddRecipeOutcome verbatim.


class AddRecipeOutcome(BaseModel):
    """Per-workflow outcome summary for add-recipe workflows.

    Producer: Phase 20's `finalize-outcome` deterministic step composes one
    of these from accumulated WorkflowRunStep artifacts and writes it into
    WorkflowRun.outcome (JSON column).

    Consumer: Phase 20's Robotina wake-context input model surfaces a list
    of these to Robotina; Phase 20's dashboard DASH-12 renders a compact cell.
    """

    model_config = ConfigDict(extra="forbid")
    status: Literal["success", "failure"]
    # Success-path fields (populated when status == "success")
    recipe_id: str | None = None
    recipe_name: str | None = None
    recipe_slug: str | None = None
    # Failure-path field (populated when status == "failure")
    failure_reason: str | None = None
    # Phase 24 (Recipe images) writes this; always False in v1.1 pre-Phase-24.
    image_present: bool = False
```

### §5. `queue_workflow` signature change

```python
# src/robotina/queue/workflow_runner.py — modify queue_workflow signature (current lines 106-113)
# [Source: extends current signature at src/robotina/queue/workflow_runner.py:106-113]

def queue_workflow(
    workflow_type: str,
    shared_context: dict,
    household_id: NonEmptyHouseholdId,
    conversation_id: str,                  # Phase 17
    triggered_by_invocation_id: str,       # Phase 18 / ARCH-03 / D-14 — required, no default
    queue,
    session: Session,
) -> str:
    # ... docstring extended with Phase 18 note ...
    # ... existing Phase 16 household_id guard at lines 145-151 ...
    # ... existing imports + WORKFLOW_REGISTRY lookup ...

    run = WorkflowRun(
        workflow_type=workflow_type,
        household_id=household_id,
        conversation_id=conversation_id,
        triggered_by_invocation_id=triggered_by_invocation_id,  # Phase 18
        shared_context=shared_context,
        status=WorkflowStatus.PENDING,
    )
    # ... rest of function unchanged ...
```

### §6. Gateway handler diff (insertion + meta key)

```python
# src/robotina/gateway/handler.py — modify (current Step 2 at lines 74-89, Step 4 at lines 113-132)
# [Source: extends existing pattern at handler.py:54-138 — same SessionLocal block]

    with SessionLocal() as session:
        # Step 1: Upsert Conversation (existing — unchanged)
        # ...

        # Step 2: Persist StoredMessage (existing — dedup short-circuit preserved)
        stored = StoredMessage(
            conversation_id=conv.id,
            platform_message_id=platform_message_id,
            role=MessageRole.USER,
            text=msg.text,
            sent_at=sent_at,
        )
        try:
            session.add(stored)
            session.flush()
        except IntegrityError:
            session.rollback()
            logger.debug("Duplicate message %s — skipping", platform_message_id)
            return  # CRITICAL: NO invocation insert on dedup (D-11 / D-24)

        # Step 2b (NEW): RobotinaInvocation insert in the same transaction
        # Phase 18 / ARCH-02 / D-11: invocation is recorded on every NEW user
        # message (not on duplicates). flush() materializes inv.id before
        # commit so the enqueue meta below can carry it.
        from robotina.queue.models import (
            RobotinaInvocation, InvocationTrigger, InvocationStatus,
        )
        inv = RobotinaInvocation(
            conversation_id=conv.id,
            trigger=InvocationTrigger.USER_MESSAGE,
            trigger_ref_id=stored.id,
            status=InvocationStatus.PENDING,
        )
        session.add(inv)
        session.flush()

        # Step 3: Fetch history (existing — unchanged)
        # ...

        session.commit()

    # Step 4: Enqueue at front of agent-tasks (modified — new meta key)
    # ...
    q.enqueue(
        "robotina.queue.jobs.run_task",
        task_input,
        at_front=True,
        result_ttl=-1,
        failure_ttl=-1,
        meta={
            "task_type": "handle-incoming-message",
            "invocation_id": inv.id,  # Phase 18 / D-12
        },
    )
```

### §7. Dashboard template diff

```jinja
{# src/robotina/dashboard/templates/workflow.html — add after line 17 (the existing ID row) #}
{# [Source: matches UI-SPEC §"Markup contract (exact)"] #}

    <dl class="kv-grid">
      <dt>Created</dt>
      <dd class="mono">{{ run.created_at.strftime("%Y-%m-%d %H:%M:%S") if run.created_at else "—" }}</dd>
      <dt>Updated</dt>
      <dd class="mono">{{ run.updated_at.strftime("%Y-%m-%d %H:%M:%S") if run.updated_at else "—" }}</dd>
      <dt>ID</dt>
      <dd class="mono">{{ run.id }}</dd>
      {# Phase 18 / DASH-13 / D-19 — single new row, nullable FK with em-dash fallback #}
      <dt>Triggered by invocation</dt>
      <dd class="mono">{{ run.triggered_by_invocation_id or "—" }}</dd>
    </dl>
```

## State of the Art

No State-of-the-Art research needed. Phase 18 uses the same library versions as Phase 17 (SQLAlchemy 2.x, Pydantic v2, Alembic 1.13, RQ 2.5, Redis 7) — already validated. No new libraries introduced.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 (auto mode) **[VERIFIED: pyproject.toml:55-67]** |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=`["tests"]`, asyncio_mode=`"auto"`, integration marker registered) |
| Quick run command | `uv run pytest -x -q --no-header -m "not integration"` |
| Full suite command | `uv run pytest -x -q` (requires `docker compose up` for integration marker) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| ARCH-02 | `RobotinaInvocation` model exists with required columns + enums | unit | `uv run pytest tests/test_workflow_runner.py::test_robotina_invocation_has_columns -x` | ❌ Wave 0 — new test |
| ARCH-02 | Migration 0007 upgrade/downgrade applies cleanly against live Postgres | integration | `uv run pytest tests/test_workflow_runner.py::test_migration_0007_upgrades_and_downgrades -x -m integration` | ❌ Wave 0 — new test mirroring existing `test_migration_0006_upgrades_and_downgrades` at lines 892-948 |
| ARCH-02 | `RobotinaInvocation` unique constraint enforces `(trigger_ref_id, trigger)` | integration | `uv run pytest tests/test_workflow_runner.py::test_invocation_unique_constraint -x -m integration` | ❌ Wave 0 — new test |
| ARCH-03 | `queue_workflow` persists `triggered_by_invocation_id` on the WorkflowRun row | unit | `uv run pytest tests/test_workflow_runner.py::test_queue_workflow_persists_triggered_by_invocation_id -x` | ❌ Wave 0 — new (mirror of existing `test_queue_workflow_persists_conversation_id` at lines 954-988) |
| ARCH-03 | `queue_workflow` rejects calls without `triggered_by_invocation_id` (TypeError) | unit | `uv run pytest tests/test_workflow_runner.py::test_queue_workflow_requires_triggered_by_invocation_id -x` | ❌ Wave 0 — new (mirror of `test_queue_workflow_requires_conversation_id` at lines 991-1013) |
| ARCH-03 | `StartWorkflowTool(invocation_id=…)` threads it to `queue_workflow` | unit | `uv run pytest tests/unit/test_start_workflow_tool.py::test_run_passes_invocation_id_to_queue_workflow -x` | ❌ Wave 0 — new (mirror of `test_run_passes_conversation_id_to_queue_workflow` at start_workflow tests lines 400-419) |
| ARCH-03 | `StartWorkflowTool` constructor requires `invocation_id` (no default) | unit | `uv run pytest tests/unit/test_start_workflow_tool.py::test_constructor_requires_invocation_id_no_default -x` | ❌ Wave 0 — new (mirror of `test_constructor_requires_conversation_id_no_default` at lines 377-386) |
| ARCH-04 | `AddRecipeOutcome` Pydantic model validates success + failure variants | unit | `uv run pytest tests/test_task_types.py::test_add_recipe_outcome_success_and_failure -x` | ❌ Wave 0 — new test file or extension to existing test module |
| ARCH-04 | `WorkflowOutcome` symbol replaced by `AddRecipeOutcome` (no consumers left) | grep + unit | `uv run pytest tests/test_task_types.py::test_workflow_outcome_replaced -x` | ❌ Wave 0 — new test |
| DASH-13 (gateway side) | `handle_message` inserts `RobotinaInvocation` with correct fields on fresh message | integration | `uv run pytest tests/test_gateway.py::test_invocation_inserted_on_fresh_message -x -m integration` | ❌ Wave 0 — new test |
| DASH-13 (gateway side) | `handle_message` sets `meta['invocation_id']` on enqueued RQ job | integration | `uv run pytest tests/test_gateway.py::test_enqueue_meta_carries_invocation_id -x -m integration` | ❌ Wave 0 — new test |
| DASH-13 (gateway side) | **Duplicate message does NOT create orphan invocation** | integration | `uv run pytest tests/test_gateway.py::test_duplicate_message_no_orphan_invocation -x -m integration` | ❌ Wave 0 — new test (THE load-bearing one per D-24) |
| DASH-13 (template) | Detail view renders `triggered_by_invocation_id` value when populated | integration | `uv run pytest tests/dashboard/test_detail_view.py::test_renders_triggered_by_invocation_id -x -m integration` | ❌ Wave 0 — new test |
| DASH-13 (template) | Detail view renders `—` when `triggered_by_invocation_id` is NULL | integration | `uv run pytest tests/dashboard/test_detail_view.py::test_renders_em_dash_when_invocation_null -x -m integration` | ❌ Wave 0 — new test |
| DASH-14 | Module-isolation gate still passes | unit | `uv run pytest tests/dashboard/test_independence.py -x` | ✅ Existing — verify still passes (no edits expected) |

### Sampling Rate

- **Per task commit:** `uv run pytest -x -q --no-header -m "not integration"` — runs unit tests in seconds. Catches model-shape regressions, signature breaks, args-schema failures, and `AddRecipeOutcome` validator coverage.
- **Per wave merge:** `uv run pytest -x -q` (full suite, requires `docker compose up`). Catches migration, gateway-handler, dashboard-template, and queue_workflow integration regressions.
- **Phase gate:** Full suite green before `/gsd-verify-work`. Plus the manual smoke step required by `feedback_test_before_handoff.md`: send a Telegram message → verify `SELECT id, status, trigger, trigger_ref_id, created_at FROM robotina_invocations ORDER BY created_at DESC LIMIT 1` shows a fresh row and `SELECT triggered_by_invocation_id FROM workflow_runs WHERE id = '<just-created>'` matches.

### Wave 0 Gaps

- [ ] `tests/test_workflow_runner.py` — extend with: `test_robotina_invocation_has_columns`, `test_migration_0007_upgrades_and_downgrades` (integration, mirror of 0006 test at lines 892-948), `test_invocation_unique_constraint` (integration), `test_queue_workflow_persists_triggered_by_invocation_id` (mirror of conversation_id test at 954-988), `test_queue_workflow_requires_triggered_by_invocation_id` (mirror of 991-1013).
- [ ] `tests/unit/test_start_workflow_tool.py` — extend with: `test_constructor_requires_invocation_id_no_default`, `test_constructor_accepts_non_empty_invocation_id`, `test_run_passes_invocation_id_to_queue_workflow` (mirrors of existing conversation_id tests at lines 377-419). Also update ALL existing `StartWorkflowTool(...)` constructor calls in the file (15+ instances) to add `invocation_id="inv-1"` — TypeError otherwise.
- [ ] `tests/test_gateway.py` — extend with: `test_invocation_inserted_on_fresh_message`, `test_enqueue_meta_carries_invocation_id`, **`test_duplicate_message_no_orphan_invocation`** (the load-bearing test for D-24). Also extend existing `test_duplicate_message_skipped` (lines 32-43) to assert zero RobotinaInvocation rows.
- [ ] `tests/dashboard/test_detail_view.py` — extend with: `test_renders_triggered_by_invocation_id`, `test_renders_em_dash_when_invocation_null`. Both `@pytest.mark.integration` + `@pytest.mark.asyncio`; reuse the `make_failed_cascade_run`-style fixture pattern at `tests/dashboard/conftest.py:61`.
- [ ] `tests/test_task_types.py` (may not yet exist as a dedicated file — check during plan) — add `AddRecipeOutcome` validation tests + `WorkflowOutcome`-replaced grep guard.
- [ ] Framework install: not required (pytest + pytest-asyncio already in dev group).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 18 introduces no authentication surface; agent-side household_id flows via existing four-layer validation (Phase 16). |
| V3 Session Management | no | RQ job context + SQLAlchemy session — both already vetted. |
| V4 Access Control | no | Internal entity, no external access surface in Phase 18. Dashboard read-only display is the only new surface; access control already governed by Phase 13 DASHBOARD_HOST loopback default (WR-01). |
| V5 Input Validation | yes | New surface: `meta['invocation_id']` read by `run_task` (bracket form, fails loud); `RobotinaInvocation.trigger_ref_id` accepts any string (FK on `trigger_ref_id` is intentionally NOT declared — D-10 — because the target table varies by `trigger` value: StoredMessage / RobotinaInvocation / future ScheduledTask. Validation happens at producer side: gateway writes `stored.id` which is a server-generated UUID, not LLM-controlled). |
| V6 Cryptography | no | No new crypto surface. UUIDs use Python's `uuid.uuid4()`, same as every other primary key in the codebase. |

### Known Threat Patterns for SQLAlchemy + Pydantic stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via raw SQL | Tampering | Not applicable — no raw SQL in Phase 18 code paths; ORM throughout. Migration ENUM creation uses parameterless `DO $$ BEGIN ... END $$` blocks (no user input). |
| LLM-controlled FK injection (LLM emits `invocation_id` to redirect a workflow to another invocation) | Tampering | Mitigated by constructor injection (D-13) + `extra='forbid'` on `StartWorkflowArgs` (already in place). The LLM never sees the `invocation_id` field; it cannot supply it via `args_schema`. |
| Orphan invocation row creation via message replay | Repudiation / minor DoS | Mitigated by D-11 ordering (dedup short-circuit BEFORE invocation insert). The D-24 test is the load-bearing guard; without it a malicious or buggy retry loop could create unbounded PENDING rows. |
| Duplicate wake fire | (Phase 20 concern) | Mitigated by D-08 `UniqueConstraint("trigger_ref_id", "trigger")` shipping in Phase 18 even though Phase 20 is the consumer (Pitfall 1). |

## Environment Availability

> Skip — Phase 18 introduces no new external dependencies. Postgres 15 (already deployed), Redis 7 (already deployed), Python 3.12 / SQLAlchemy 2.x / Alembic / Pydantic v2 / RQ (all already in `pyproject.toml`) are the full dependency set. Confirmed by reading `pyproject.toml` lines 1-67.

## Assumptions Log

> All factual claims in this research were verified against the on-disk Phase 17 baseline or quoted verbatim from CONTEXT.md. No `[ASSUMED]` claims remain — the table is empty.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | (none) | — | — |

## Open Questions (RESOLVED)

1. **Does `pyproject.toml` need an entry-point update for any new test file?**
   - What we know: `[tool.pytest.ini_options].testpaths = ["tests"]` already covers nested directories like `tests/dashboard/`.
   - What's unclear: whether the planner intends to add a new file `tests/test_task_types.py` (vs. extending `tests/test_workflow_runner.py` or co-locating with `tests/unit/`).
   - Recommendation: planner picks placement during plan time; no pyproject change required either way.

2. **Should the migration's `ux_invocation_workflow_completion_once` constraint be a partial unique index instead of a full-table one?**
   - What we know: CONTEXT.md D-08 explicitly chose full-coverage `UniqueConstraint("trigger_ref_id", "trigger")` because PostgreSQL/SQLAlchemy DDL doesn't express partial uniques cleanly. Phase 18 has no production-level rows to worry about; effectively dormant in Phase 18.
   - What's unclear: future scale concern (would `NULL`-heavy `trigger_ref_id` distribution skew the index?). Not relevant pre-launch.
   - Recommendation: ship the full constraint as D-08 specifies. Revisit only if Phase 20 metrics suggest a problem.

## Sources

### Primary (HIGH confidence)

- `.planning/phases/18-robotinainvocation-entity/18-CONTEXT.md` — auto-mode decisions D-01..D-25 (verbatim source for all locked decisions).
- `.planning/phases/18-robotinainvocation-entity/18-UI-SPEC.md` — approved 2026-05-19; verbatim source for the dashboard markup contract.
- `.planning/research/ARCHITECTURE.md` §2.4, §2.6, §2.8, §"Phase B" — placement, signature, handler diff (all reflected in CONTEXT.md decisions).
- `.planning/research/PITFALLS.md` Pitfall 1, Pitfall 5 — justification for the `UniqueConstraint` shipping in Phase 18 (idempotency guard) and the constructor-injected `invocation_id` (multi-call safety).
- `src/robotina/queue/models.py` (HEAD, post-Phase-17) — WorkflowRun template + conversation_id + outcome columns confirmed at lines 28-49.
- `src/robotina/queue/workflow_runner.py::queue_workflow` (lines 106-214) — current signature with `conversation_id` parameter confirmed.
- `src/robotina/queue/jobs.py::run_task` (lines 134-170) — current `handle-incoming-message` branch with `conversation_id` injection confirmed at lines 149-170.
- `src/robotina/agent/tools/start_workflow.py` (lines 127-138) — current constructor fields including `conversation_id: str` confirmed.
- `src/robotina/gateway/handler.py` (lines 54-138) — current `with SessionLocal()` block + enqueue meta + dedup short-circuit (lines 86-89) confirmed.
- `src/robotina/dashboard/templates/workflow.html` (lines 11-18) — current kv-grid structure confirmed.
- `src/robotina/dashboard/queries.py::get_workflow_with_steps` (lines 29-35) — confirmed no edit needed.
- `migrations/versions/0006_conversation_fk_and_outcome.py` — stylistic template for `0007` (43 lines, op.add_column × 2).
- `migrations/versions/0002_models.py:17-44` — PostgreSQL ENUM creation idiom (verbatim reuse for `InvocationTrigger` / `InvocationStatus`).
- `tests/dashboard/test_independence.py` (lines 1-123) — DASH-14 enforcement gate confirmed unchanged in Phase 18.
- `tests/test_workflow_runner.py` (lines 954-988, 991-1013, 892-948) — Phase 17 test patterns to mirror.
- `tests/unit/test_start_workflow_tool.py` (lines 377-419) — Phase 17 constructor-test patterns to mirror.
- `tests/test_gateway.py` (lines 32-43) — `test_duplicate_message_skipped` baseline to extend.

### Secondary (MEDIUM confidence)

- `CLAUDE.md` "Technology Stack" — SQLAlchemy 2.x `Mapped` + `mapped_column` mandatory; Pydantic v2 only; `uv run migrate` is the migration command. **[VERIFIED at top of file]**
- Memory `feedback_avoid_premature_abstraction.md` — applied in CONTEXT.md D-05 (columns OK, abstractions defer) and D-18 (no envelope until ≥2 workflow types).
- Memory `feedback_test_before_handoff.md` — gateway-handler change has runtime effect (extra DB write per message); planner must include manual smoke step before reporting Phase 18 complete.

### Tertiary (LOW confidence)

- (none)

## Project Constraints (from CLAUDE.md)

Verbatim or summarized from `./CLAUDE.md`:

1. **Tech Stack — no deviations in Phase 1+:** Python, LangChain, Postgres (SQLAlchemy + Alembic), Redis + RQ, uv. Phase 18 introduces no new dependencies.
2. **Concurrency:** task runner must remain sequential (concurrency=1). Phase 18 does not change worker config.
3. **Redis persistence:** AOF with `appendfsync always` — no tasks lost on crash/reboot. Phase 18 inherits.
4. **Observability:** LangWatch instrumentation must remain active. Phase 18 does not touch the agent loop's tracer wiring.
5. **GSD Workflow Enforcement:** Before using Edit/Write/file-changing tools, work must flow through a GSD command. Phase 18 is executed via `/gsd:execute-phase 18` after planning.
6. **SQLAlchemy 2.x `Mapped` + `mapped_column` mandatory** (Recommended Stack table). The Phase 17 baseline already uses this style; Phase 18 extends it.
7. **Pydantic v2 only** — `AddRecipeOutcome` uses `model_config = ConfigDict(extra="forbid")`, `Literal[...]`, `X | None = None` consistent with every existing model in `task_types.py`.
8. **`langchain.agents.create_agent`** is the agent factory; `AgentExecutor` and `langgraph.prebuilt.create_react_agent` are forbidden. Phase 18 does not touch agent construction.

## Metadata

**Confidence breakdown:**

| Area | Level | Reason |
|------|-------|--------|
| Standard stack | HIGH | No new libraries; every version is already validated in Phase 17 baseline. Verified against `pyproject.toml` and existing imports. |
| Architecture | HIGH | Every code-shape claim verified against on-disk file at the line ranges CONTEXT.md cites (handler.py, jobs.py, workflow_runner.py, start_workflow.py, models.py, task_types.py, queries.py, workflow.html, test files). |
| Pitfalls | HIGH | Two are documented in PITFALLS.md (Pitfall 1 wake-rule, Pitfall 5 multi-call). Three more (orphan invocation, ENUM names, stub replacement) derive from on-disk pattern verification or STATE.md decision log. |
| Validation | HIGH | Existing test patterns at well-known line numbers are verbatim mirrorable for Phase 18; pytest + asyncio config confirmed in `pyproject.toml`. |
| Security | HIGH | Phase 18 surface is internal-only and inherits Phase 17's four-layer household_id defense and Phase 13's loopback dashboard default. New surfaces (meta['invocation_id'], trigger_ref_id) have clear producer-side validation rationale. |

**Research date:** 2026-05-19
**Valid until:** 2026-06-18 (30 days for stable internal refactor; revisit only if Phase 17 baseline changes or CONTEXT.md is re-decided)
