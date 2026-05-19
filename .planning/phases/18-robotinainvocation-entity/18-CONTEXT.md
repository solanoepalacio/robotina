# Phase 18: RobotinaInvocation entity - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning
**Mode:** `--auto` (system reminder asked the discuss workflow to make reasonable
calls without stopping; gray areas resolved by Claude with rationale below — the
user can redirect any D-NN in this file before planning lands.)

<domain>
## Phase Boundary

Land the `RobotinaInvocation` entity as a strict additive change: every Robotina
turn becomes a persisted row, and every new WorkflowRun back-points to the
invocation that dispatched it. No wake rule yet (Phase 20), no respond/terminate
tools yet (Phase 21) — Phase 18 only writes rows and surfaces the new FK on the
dashboard detail view. Phase 18 also defines the `AddRecipeOutcome` Pydantic
shape that Phase 20's `finalize-outcome` step will populate; no code writes the
`WorkflowRun.outcome` JSON column this phase.

**In scope:**
- New `robotina_invocations` table — `id`, `conversation_id` (FK → conversations.id), `trigger` (InvocationTrigger enum), `trigger_ref_id`, `rq_job_id`, `status` (InvocationStatus enum), `wake_dispatched_at`, `started_at`, `completed_at`, `created_at`, `updated_at`.
- `InvocationTrigger` enum: `USER_MESSAGE`, `WORKFLOW_COMPLETION`, `CRON`.
- `InvocationStatus` enum: `PENDING`, `RUNNING`, `DONE`, `FAILED`.
- Idempotency `UniqueConstraint("trigger_ref_id", "trigger", name="ux_invocation_workflow_completion_once")` on the new table.
- `WorkflowRun.triggered_by_invocation_id` — nullable FK to `robotina_invocations.id` (per ARCH-03: "the column lands nullable in v1.1").
- Single Alembic revision `0007_robotina_invocations.py` adds the table + the nullable FK column.
- Gateway (`handler.py`): insert `RobotinaInvocation(trigger=USER_MESSAGE, trigger_ref_id=StoredMessage.id, conversation_id=conv.id, status=PENDING)` in the same transaction as the StoredMessage; enqueue with `meta={'task_type': 'handle-incoming-message', 'invocation_id': inv.id}`.
- `queue/jobs.py` (`handle-incoming-message` branch): read `invocation_id = job.meta["invocation_id"]`; pass it into `StartWorkflowTool(invocation_id=…)` alongside the Phase 17 `conversation_id`.
- `agent/tools/start_workflow.py`: new constructor field `invocation_id: str`; `_run` stamps it via `queue_workflow(..., triggered_by_invocation_id=self.invocation_id, ...)`.
- `queue/workflow_runner.py::queue_workflow`: signature gains required `triggered_by_invocation_id: str` arg; writes it to the new column.
- `queue/task_types.py`: define `AddRecipeOutcome` Pydantic model (success/failure + recipe id/name/slug OR failure_reason + `image_present` flag). Replaces the Phase 17 `WorkflowOutcome` placeholder stub.
- Dashboard (`workflow.html`): add `triggered_by_invocation_id` row to the detail-view `kv-grid` (short UUID + full UUID in mono); "—" when NULL.
- Tests: gateway handler (invocation insert + dedup-no-orphan); `StartWorkflowTool` (invocation_id propagates to `queue_workflow`); `queue_workflow` (FK persisted on the row); dashboard template (the new dt/dd renders when the FK is set and renders "—" otherwise); module-isolation grep gate still green.
- One-line REQUIREMENTS.md edit if ARCH-02's `job_id` wording is kept — align to `rq_job_id` to match Phase 17's REQUIREMENTS-edit pattern (D-25).

**Out of scope (deferred to later phases):**
- The wake rule (`_check_wake_robotina(session)` helper, `wake_dispatched_at` UPDATE-RETURNING idempotency, `on_step_complete`/`on_step_failed` hook into the wake check) — Phase 20.
- `InvocationStatus` transitions (PENDING → RUNNING → DONE/FAILED). Phase 18 writes only PENDING; Phase 20 wires the rest.
- `WakeInvocationInput` model + `run_task` dispatch on `trigger=WORKFLOW_COMPLETION` — Phase 20.
- Pre-assigned `rq_job_id` for the next invocation (transactional advancement for wake invocations) — Phase 20.
- Startup reconciler for `wake_dispatched_at IS NOT NULL but no RQ job` rows — Phase 20.
- Populating `WorkflowRun.outcome` from a deterministic `finalize-outcome` step — Phase 20 (Phase 18 only defines the Pydantic shape).
- Dashboard rendering of `conversation_id` or `outcome` cells (DASH-10, DASH-12) — Phase 20.
- A dedicated `RobotinaInvocation` list/detail dashboard view — backlog (DASH-13 explicitly marks this "nice-to-have").
- Multi-call `StartWorkflowTool` (one invocation → N workflows in one LLM turn) — Phase 19 evidence first; flip happens in Phase 21.
- Dropping `chat_id`/`user_id`/`platform` from `StartWorkflowTool` — ARCH-05 deprecation window stays open through v1.1.

</domain>

<decisions>
## Implementation Decisions

> **Auto-mode note:** Every D-NN below is Claude's call under the "no-stopping"
> system reminder. Where the call balances trade-offs, the alternative is named.
> The user can redirect any decision before `/gsd-plan-phase 18` runs.

### Migration shape

- **D-01:** **Single Alembic revision** (`0007_robotina_invocations.py`) — creates the `robotina_invocations` table + its enums + its `UniqueConstraint` AND adds nullable `workflow_runs.triggered_by_invocation_id` (FK → `robotina_invocations.id`) in one upgrade. revision=`"0007"`, down_revision=`"0006"`. Style mirrors `0006_conversation_fk_and_outcome.py` (Phase 17).
  - **Why:** Mirrors Phase 17's "one revision per phase" pattern; the two changes are co-dependent (the FK column references the new table) so they belong in one atomic migration. Splitting them would require a brittle ordering across two revisions for no gain at this scale (single household, pre-launch v1.1).

- **D-02:** **`triggered_by_invocation_id` is NULLABLE in v1.1.** No backfill, no NOT NULL enforcement, no pre-clean of `workflow_runs` for this phase. Per ARCH-03 verbatim ("the column lands nullable in v1.1") and ROADMAP success-criterion #2 ("Every WorkflowRun created during that turn carries `triggered_by_invocation_id`") — the criterion is satisfied by writing the FK on new rows, not by enforcing it on historical ones.
  - **Why:** Phase 17 already TRUNCATEd `workflow_runs` once; doing it again for Phase 18 would be ceremony for nothing — the only WorkflowRuns that could exist between Phase 17 deploy and Phase 18 deploy are happy-path rows created by the post-Phase-17 codebase. Those would carry the FK if Phase 18 deploys at the same checkpoint, or carry NULL if a few rows slipped in between deploys; either case is acceptable because Phase 20's wake rule only acts on rows where the FK is set. NULL = "historical, ignored by wake."

- **D-03:** **No defensive backfill code, no orphan-handling branches.** Migration is `op.create_table(robotina_invocations, ...)` + `op.add_column("workflow_runs", Column("triggered_by_invocation_id", String, ForeignKey("robotina_invocations.id"), nullable=True))`. No `op.execute("UPDATE …")`, no synthetic invocation row creation.

### RobotinaInvocation schema

- **D-04:** **Place in `src/robotina/queue/models.py`** alongside `WorkflowRun` (per ARCHITECTURE §2.4). Dependency arrows already flow gateway → queue and queue/workflow_runner → queue/models. Adding `RobotinaInvocation` there creates no new dependency directions. This also automatically satisfies DASH-14 ("RobotinaInvocation imported from `robotina.queue.models` like `WorkflowRun`, not via a cross-module shortcut").

- **D-05:** **Ship the full Phase-20-ready schema in Phase 18** — `wake_dispatched_at`, `rq_job_id`, `status`, `started_at`, `completed_at` all land now, even though Phase 18 only writes `status=PENDING` and the rest stay NULL on insert. Forward-compat: Phase 20 wires the wake rule against an already-present schema, no `ALTER TABLE` migration churn between phases.
  - **Why this doesn't violate `feedback_avoid_premature_abstraction.md`:** That feedback is about code-level abstractions (generic agents, factory wrappers, etc.). Adding nullable columns now vs. in two phases is a schema migration cost discussion, not an abstraction. Migrating in pieces means two Alembic revisions touching the same table for cohesive functionality (`RobotinaInvocation` + its lifecycle columns) — net pain. The columns are explicitly named in ARCH-02; not adding them now would be the deviation.

- **D-06:** **`InvocationTrigger` enum: `USER_MESSAGE`, `WORKFLOW_COMPLETION`, `CRON` — full set.** Phase 18 only emits `USER_MESSAGE` rows. Phase 20 emits `WORKFLOW_COMPLETION`. `CRON` is reserved per the deferred scheduler milestone. Defining the enum once avoids the `ALTER TYPE ... ADD VALUE` migration friction in Phase 20.

- **D-07:** **`InvocationStatus` enum: `PENDING`, `RUNNING`, `DONE`, `FAILED` — full set.** Phase 18 writes only `PENDING` (on gateway insert). Phase 20 transitions through the rest. Same enum-evolution-avoidance rationale as D-06.

- **D-08:** **Add the `UniqueConstraint("trigger_ref_id", "trigger", name="ux_invocation_workflow_completion_once")` upfront in Phase 18.** For Phase 18 it's effectively dormant (Phase 18 only creates `USER_MESSAGE` rows where `trigger_ref_id = StoredMessage.id` — `StoredMessage.platform_message_id` is already unique so collisions are nearly impossible). The constraint exists in the schema because it's the load-bearing wake-rule idempotency guard (Pitfall 1 + Pitfall 2) and shipping it in Phase 18 means Phase 20 has zero schema-migration work.
  - **What this protects:** Phase 20 will need the invariant "at most one `WORKFLOW_COMPLETION` invocation per parent invocation." That maps to UNIQUE(`trigger_ref_id`, `trigger`) on rows where `trigger='workflow_completion'`. PostgreSQL doesn't support partial unique constraints via SQLAlchemy DDL cleanly, so we use a full-coverage uniqueness on (`trigger_ref_id`, `trigger`) instead — equivalent strength, simpler DDL.
  - **Note on USER_MESSAGE rows:** Two messages from the same Telegram chat get different `platform_message_id`s, so distinct `trigger_ref_id`s, so the constraint never trips for legitimate user messages.

- **D-09:** **Column naming uses `rq_job_id` (not `job_id`).** Disambiguates from `WorkflowRunStep.task_job_id` and makes the cross-reference to RQ explicit. ARCH-02's `job_id` wording in REQUIREMENTS.md will be updated to `rq_job_id` in the same commit (per D-25, mirroring Phase 17's REQUIREMENTS-edit pattern).

- **D-10:** **Suggested schema (planner has discretion on exact SQLAlchemy syntax):**
  ```python
  class InvocationTrigger(enum.Enum):
      USER_MESSAGE = "user_message"
      WORKFLOW_COMPLETION = "workflow_completion"
      CRON = "cron"

  class InvocationStatus(enum.Enum):
      PENDING = "pending"
      RUNNING = "running"
      DONE = "done"
      FAILED = "failed"

  class RobotinaInvocation(Base):
      __tablename__ = "robotina_invocations"
      __table_args__ = (
          UniqueConstraint(
              "trigger_ref_id", "trigger",
              name="ux_invocation_workflow_completion_once",
          ),
      )
      id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
      conversation_id: Mapped[str] = mapped_column(String, ForeignKey("conversations.id"), nullable=False)
      trigger: Mapped[InvocationTrigger] = mapped_column(
          Enum(InvocationTrigger, values_callable=lambda x: [e.value for e in x]),
          nullable=False,
      )
      trigger_ref_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
      # USER_MESSAGE        → StoredMessage.id
      # WORKFLOW_COMPLETION → prior RobotinaInvocation.id (the one whose workflows drained)
      # CRON                → ScheduledTask.id (future)
      rq_job_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
      status: Mapped[InvocationStatus] = mapped_column(
          Enum(InvocationStatus, values_callable=lambda x: [e.value for e in x]),
          default=InvocationStatus.PENDING, nullable=False,
      )
      wake_dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
      started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
      completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
      created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
      updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
  ```
  PostgreSQL `Enum` construction follows the Phase 2 convention (`postgresql.ENUM(create_type=False)` inside Alembic `op.create_table` — see `migrations/versions/0001_*.py` for the exact idiom). `values_callable` ensures the DB stores enum values, not names (Phase 3 lesson).

### `invocation_id` plumbing

- **D-11:** **Gateway insertion order in `handler.py`:**
  1. Step 1 (existing) — upsert `Conversation`.
  2. Step 2 (existing) — `StoredMessage.flush()`. **On `IntegrityError` (duplicate): rollback, return without enqueue. Do NOT insert an invocation.** Critical: invocation insert must happen AFTER the StoredMessage dedup short-circuit so duplicates don't create orphan invocations.
  3. Step 2b (NEW) — `session.add(RobotinaInvocation(conversation_id=conv.id, trigger=USER_MESSAGE, trigger_ref_id=stored.id, status=PENDING))`; `session.flush()` to materialize `inv.id`.
  4. Step 3 (existing) — fetch history.
  5. `session.commit()` (existing).
  6. Step 4 (existing, modified) — enqueue with `meta={'task_type': 'handle-incoming-message', 'invocation_id': inv.id}`.
  - **Why same transaction:** if the worker crashes between insert and enqueue, restart sees an orphan PENDING invocation. That's tolerable for Phase 18 (no wake rule yet); Phase 20's reconciler can sweep these. Alternative — pre-assign `rq_job_id` BEFORE commit so the reconciler can re-enqueue (Phase 4 D-07 pattern) — is the cleaner answer but is Phase 20's concern. Phase 18 ships the simpler "insert then enqueue" sequence and leaves the recoverability story to Phase 20.

- **D-12:** **`invocation_id` flows through `job.meta['invocation_id']`. Do NOT add it to `IncomingMessageInput`.**
  - **Why:** `job.meta` is already the primary channel for the related `task_type` field (gateway sets `meta={'task_type': 'handle-incoming-message'}`; `run_task` reads it). Adding a sibling key on the same channel is symmetric. Pushing it into `IncomingMessageInput` would couple the message-input schema to a queue-lifecycle id that the input doesn't logically own — and it would break the Phase 17 decision (D-04) to keep similar runtime context out of `IncomingMessageInput`.
  - **Phase 20 alignment:** wake-triggered invocations (Phase 20) will also use `meta['invocation_id']`, dispatched against a `WakeInvocationInput` model — same channel, different input model.

- **D-13:** **`StartWorkflowTool` gains required `invocation_id: str` constructor field.** Mirrors Phase 17 D-03's `conversation_id` injection. `_run` stamps it via `queue_workflow(..., triggered_by_invocation_id=self.invocation_id, ...)`.
  - **No Pydantic alias (`NonEmptyInvocationId`):** Same reasoning as Phase 17 D-04's `conversation_id` discussion — `invocation_id` is a UUID we just SELECTed (or generated in the gateway). The LLM cannot supply it; the LLM-shadowing surface that motivated `NonEmptyHouseholdId` doesn't exist. The FK constraint is sufficient enforcement.

- **D-14:** **`queue_workflow` signature gains required `triggered_by_invocation_id: str` arg.** No default, no fallback. Mirrors Phase 17 D-05's `conversation_id` addition. Tests update accordingly.

- **D-15:** **`run_task` (jobs.py) — diff in the `handle-incoming-message` branch (around line 134):**
  ```python
  if task_type == "handle-incoming-message":
      invocation_id = job.meta["invocation_id"]  # KeyError if missing — fail loud
      # ... existing Conversation lookup from Phase 17 D-04 ...
      tools.append(StartWorkflowTool(
          chat_id=task_input.chat_id,
          user_id=task_input.user_id,
          platform=task_input.platform,
          household_id=task_input.household_id,
          conversation_id=conversation.id,       # Phase 17
          invocation_id=invocation_id,           # Phase 18
      ))
  ```
  `job.meta["invocation_id"]` is a bracket read (not `.get(...)`) — missing key is an invariant violation (the gateway always sets it for `handle-incoming-message`). The boot-time enqueue contract is the guarantee.

### AddRecipeOutcome Pydantic shape

- **D-16:** **Define `AddRecipeOutcome` in `src/robotina/queue/task_types.py`.** Replaces the Phase 17 `WorkflowOutcome` placeholder stub (Phase 17 D-07). Phase 18 only defines the model; Phase 20's `finalize-outcome` step populates the `WorkflowRun.outcome` JSON column from it.

- **D-17:** **Shape (per ROADMAP success-criterion #3 + ARCH-04):**
  ```python
  class AddRecipeOutcome(BaseModel):
      """Per-workflow outcome summary written by the `finalize-outcome` step (Phase 20).

      Phase 18 defines the shape; no code writes it yet. Phase 20 will add the
      deterministic step that serializes one of these into `WorkflowRun.outcome`
      at workflow termination.

      Target serialized size: < ~300 bytes per workflow (ARCH-04 / DASH-12).
      """
      model_config = ConfigDict(extra="forbid")
      status: Literal["success", "failure"]
      recipe_id: str | None = None        # success only
      recipe_name: str | None = None      # success only
      recipe_slug: str | None = None      # success only
      failure_reason: str | None = None   # failure only
      image_present: bool = False         # always False in v1.1 until Phase 24 lands recipe-image
  ```
  - **Not a discriminated union:** Pydantic's `Field(discriminator=...)` adds verbose construction friction for a 2-variant shape. Optional fields + `model_config = ConfigDict(extra="forbid")` keeps the shape readable; Phase 20's `finalize-outcome` step is the single producer, so the runtime guarantee that success-rows have `recipe_*` and failure-rows have `failure_reason` is a producer-side contract, not a schema-level one. If the contract gets violated downstream, add a `model_validator` then.

- **D-18:** **Replace, don't supplement, the Phase 17 `WorkflowOutcome` stub.** The stub (`status: Literal["pending"]`) was a code anchor; Phase 18 fills in the real shape for the only workflow type that exists in v1.1 (`add-recipe`). No envelope (architecture's `WorkflowOutcome(workflow_run_id, workflow_type, status, summary, structured)`) is introduced in Phase 18 — that's premature abstraction for a single workflow type (per `feedback_avoid_premature_abstraction.md`). If/when Phase 23 (URL ingestion) or future workflows need distinct outcome shapes, the envelope can be introduced then.
  - **Practical:** in `queue/task_types.py`, replace the Phase-17 `WorkflowOutcome` class definition with `AddRecipeOutcome`. Update any test that imports `WorkflowOutcome` (none yet — Phase 17's stub was unused by design) to import `AddRecipeOutcome`.

### Dashboard surfacing

- **D-19:** **Add `triggered_by_invocation_id` to the WorkflowRun detail view (`src/robotina/dashboard/templates/workflow.html`) — and ONLY that.** Add it as a new `<dt>/<dd>` pair in the existing `kv-grid`:
  ```jinja
  <dt>Triggered by invocation</dt>
  <dd class="mono">{{ run.triggered_by_invocation_id or "—" }}</dd>
  ```
  No JOIN to `RobotinaInvocation`, no link to a future invocation view (premature), no list-view column, no extra query. The existing `get_workflow_with_steps` query (`src/robotina/dashboard/queries.py`) auto-picks up the new column once the model has it; no `queries.py` edit needed.

- **D-20:** **Defer to Phase 20:** rendering `conversation_id` (DASH-10), rendering the `outcome` summary cell (DASH-12), the list-view changes for new columns, any dedicated invocation list/detail dashboard view. Phase 18 stays minimal to keep DASH-13 narrowly scoped ("at minimum: `triggered_by_invocation_id` appears on the detail page").

- **D-21:** **Module-isolation grep gate (DASH-14):** no work required — `RobotinaInvocation` lives in `robotina.queue.models` (D-04), which dashboard already imports per Phase 13 D-01. The existing `tests/dashboard/test_independence.py` (grep gate + AST gate + inward-only audit) continues to pass without modification. Verify by running `uv run pytest tests/dashboard/test_independence.py -x` as part of the phase's exit criteria.

### Test strategy (Claude's Discretion)

- **D-22:** **Unit test for `StartWorkflowTool`** — construct with `invocation_id="inv-abc"`, mock `queue_workflow`, assert `queue_workflow` was called with `triggered_by_invocation_id="inv-abc"`. Mirror the Phase 17 unit-test pattern for `conversation_id`.
- **D-23:** **Integration test for `queue_workflow`** — `@pytest.mark.integration`, real Postgres session. Insert a `Conversation` + a `RobotinaInvocation`, call `queue_workflow(triggered_by_invocation_id=inv.id, conversation_id=conv.id, ...)`, assert the persisted `WorkflowRun` row has both FKs set.
- **D-24:** **Gateway handler tests** — `tests/gateway/test_handler.py`:
  - Assert that on a fresh message, `RobotinaInvocation` is inserted with `trigger=USER_MESSAGE`, `trigger_ref_id=<stored.id>`, `conversation_id=<conv.id>`, `status=PENDING`.
  - Assert that the enqueued RQ job has `meta['invocation_id'] = inv.id`.
  - **Critical:** assert that on a duplicate `platform_message_id` (IntegrityError on StoredMessage), the function returns WITHOUT inserting an invocation and WITHOUT enqueueing.
- **D-25:** **REQUIREMENTS.md ARCH-02 wording edit** in the same commit as the schema change — if ARCH-02 says `job_id`, update to `rq_job_id` to match the implementation (per Phase 17 D-01's pattern of keeping REQUIREMENTS in sync with implementation). Single-line edit, planner includes it alongside the model commit.

### Claude's Discretion

- **Migration file naming:** `migrations/versions/0007_robotina_invocations.py`. Style mirrors `0006_conversation_fk_and_outcome.py`. No branch labels, no `depends_on`.
- **PostgreSQL ENUM creation:** follow the Phase 2 lesson (`postgresql.ENUM(create_type=False)` inside `op.create_table`; pre-create types with the `DO $$ BEGIN IF NOT EXISTS ... END $$` idempotent guard if Alembic runs against an existing DB). See `migrations/versions/0001_create_*.py` for the exact pattern; reuse verbatim.
- **`InvocationTrigger` / `InvocationStatus` location:** co-locate with `WorkflowStatus` / `WorkflowStepStatus` at the top of `src/robotina/queue/models.py`. Single import point.
- **`AddRecipeOutcome` placement in `task_types.py`:** alongside the existing recipe models, after `RecipeLoadOutput`. Add a section header comment block matching the existing style.
- **No `NonEmptyInvocationId` Pydantic alias** (per D-13 rationale). FK constraint + bracket-key read in `run_task` (D-15) cover the empty-string surface.
- **Skip a `ScheduledTask`-style preview for the `CRON` trigger:** the enum value lands in Phase 18 (D-06) but no model or table for ScheduledTask exists yet (deferred scheduler milestone). `trigger_ref_id` will be NULL or unset for CRON rows until that milestone lands.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 18: RobotinaInvocation entity" — phase goal, success criteria, dependency on Phase 17.
- `.planning/REQUIREMENTS.md` ARCH-02, ARCH-03, ARCH-04, DASH-13, DASH-14 — the five requirements this phase delivers. **Planner must propose the ARCH-02 wording update described in D-09/D-25** (`job_id` → `rq_job_id`).

### Architecture and pitfalls (load-bearing context)
- `.planning/research/ARCHITECTURE.md` §2.4 "RobotinaInvocation entity placement" — placement decision (recap of D-04) + suggested schema (the source for D-10).
- `.planning/research/ARCHITECTURE.md` §2.6 "StartWorkflowTool refactor table" — the row "Caller: `run_task` injects `conversation_id, invocation_id, household_id`" matches D-13/D-15.
- `.planning/research/ARCHITECTURE.md` §2.8 "handler diff" — confirms the gateway insertion sequence in D-11.
- `.planning/research/ARCHITECTURE.md` §"Phase B — RobotinaInvocation entity (entity-first, no wake yet)" — confirms this phase is strict additive; the wake rule is explicitly deferred.
- `.planning/research/PITFALLS.md` Pitfall 1 "Wake-rule double-fire" — explains why the `UniqueConstraint` in D-08 ships in Phase 18 even though the wake rule doesn't.
- `.planning/research/PITFALLS.md` Pitfall 5 "`create_agent` does not let us disable parallel tool calls" — explains why the tool MUST receive `invocation_id` via constructor injection (D-13), not via mutable shared state. Multi-call StartWorkflowTool isn't in Phase 18, but the constructor-injection decision must not be re-litigated when Phase 21 lands.

### Prior phase context (carries forward — do NOT re-decide)
- `.planning/phases/17-conversation-fk-closure/17-CONTEXT.md` — Phase 17 decisions. Phase 18 inherits all of them:
  - D-03/D-05 (constructor-injected `conversation_id` on `StartWorkflowTool`, required arg on `queue_workflow`) — Phase 18 mirrors the topology for `invocation_id`.
  - D-04 (`run_task` resolves runtime context at tool-construction time, fail loud on miss) — Phase 18 follows the same pattern for `meta['invocation_id']`.
  - D-06/D-07 (`WorkflowRun.outcome` JSON column + `WorkflowOutcome` stub) — Phase 18 fills in the real shape (`AddRecipeOutcome`) per D-16/D-17/D-18.
  - D-08 (deploy runbook: drain RQ + TRUNCATE workflow_runs + migrate) — Phase 18 does NOT re-truncate (D-02 explains why); the migration runbook for Phase 18 is just `docker compose stop task-runner` → `uv run migrate` → restart.
- `.planning/phases/13-queue-visibility-dashboard/13-CONTEXT.md` D-01 — module-independence rule. Phase 18 stays compliant (D-21).

### Existing codebase contracts (current state — Phase 17 not yet executed)
- `src/robotina/queue/models.py` — `WorkflowRun` 2.x `Mapped`/`mapped_column` style is the template; new columns and the new `RobotinaInvocation` class follow it. **Phase 17 will add `conversation_id` and `outcome` to `WorkflowRun` BEFORE Phase 18 starts**; Phase 18's diff is on top of Phase 17's diff.
- `src/robotina/queue/workflow_runner.py::queue_workflow` (lines 106–206) — function being modified. Phase 16 REQ-HID-4 guard at line 138 stays. Phase 17 adds `conversation_id` arg; Phase 18 adds `triggered_by_invocation_id` arg in the same position pattern.
- `src/robotina/agent/tools/start_workflow.py` (lines 100–187) — Phase 16's `NonEmptyHouseholdId` injection pattern; Phase 17 mirrors for `conversation_id`; Phase 18 mirrors for `invocation_id` (without the Pydantic alias — D-13).
- `src/robotina/gateway/handler.py` (lines 54–138) — handler being modified. New step 2b (D-11) between the existing dedup and history fetch.
- `src/robotina/gateway/models.py::Conversation` (lines 26–37) — uniqueness on `(platform, chat_id)`; `Conversation.id` is the FK target.
- `src/robotina/queue/jobs.py` (lines 130–149) — `handle-incoming-message` branch. New `meta['invocation_id']` read + new constructor field on `StartWorkflowTool`.
- `src/robotina/dashboard/templates/workflow.html` — single new `<dt>/<dd>` insertion per D-19.
- `src/robotina/dashboard/queries.py::get_workflow_with_steps` — no change needed; the SQLAlchemy query auto-picks the new column.
- `migrations/versions/0006_*.py` (will exist after Phase 17 lands) — closest stylistic template for `0007`.
- `migrations/versions/0001_create_*.py` — PostgreSQL ENUM creation idiom (D-10 implementation note).
- `tests/dashboard/test_independence.py` — DASH-14 enforcement; must continue to pass.

### Project conventions
- `CLAUDE.md` "Tech Stack" — SQLAlchemy 2.x `Mapped` + `mapped_column` mandatory; Pydantic v2 only; `uv run migrate` is the migration command.
- Memory `feedback_avoid_premature_abstraction.md` — applied in D-05 (columns OK, abstractions defer) and D-18 (no envelope until ≥2 workflow types).
- Memory `feedback_overrides_in_sync.md` — not engaged this phase (no AGENT_REGISTRY changes); but planner should still grep `overrides/*.json` for any drift before commit.
- Memory `feedback_test_before_handoff.md` — gateway-handler change has a runtime effect (extra DB write per message); planner must include a manual smoke step before reporting Phase 18 complete.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 17 `conversation_id` plumbing pattern** (`StartWorkflowTool.__init__` + `queue_workflow(...)` signature + `run_task` resolves runtime context): Phase 18 copies the topology one-for-one for `invocation_id`. Concretely: the same insertion sites in `start_workflow.py:127–131`, `workflow_runner.py::queue_workflow` signature, and `jobs.py:134–149` are touched again — by then they will already have `conversation_id` from Phase 17, so Phase 18 just adds the parallel `invocation_id` argument alongside it.
- **Phase 2 PostgreSQL ENUM creation idiom** (`migrations/versions/0001_create_*.py` for both Workflow enums + the Phase 13 `0005_dashboard_columns.py` revision for the JSON-column-additive pattern): combine these for the `InvocationTrigger`/`InvocationStatus` enum DDL in `0007`.
- **Phase 6 `QueueTool` + Phase 16 `NonEmptyHouseholdId` constructor-injection pattern**: same shape as the new `invocation_id` field on `StartWorkflowTool`. Reuse the exact field-declaration ordering (`chat_id, user_id, platform, household_id` today → add `conversation_id, invocation_id` per Phase 17 + Phase 18).
- **Phase 13 dashboard `kv-grid` Jinja block** (`src/robotina/dashboard/templates/workflow.html:11–18`): the natural insertion point for the new `triggered_by_invocation_id` row (D-19). Same `class="mono"` styling as the existing `ID` row.
- **`session.add(...) + session.flush()` to materialize FK IDs before commit**: existing pattern in `handler.py:65–67` (Conversation upsert) and `handler.py:84–89` (StoredMessage insert). The new `RobotinaInvocation` insert (D-11) uses the same idiom — flush so `inv.id` is materialized before the enqueue.

### Established Patterns
- **`Mapped[Optional[X]]` + `nullable=True`** for additive columns on existing tables (`WorkflowRunStep.step_input`, `WorkflowRunStep.failure_reason`, Phase 17's `WorkflowRun.conversation_id` despite NOT NULL, Phase 17's `WorkflowRun.outcome`). `triggered_by_invocation_id` follows the nullable variant per ARCH-03.
- **`values_callable=lambda x: [e.value for e in x]` on SQLAlchemy `Enum` columns** (`models.py:33,50`) — required so PostgreSQL stores enum VALUES not NAMES. New `InvocationTrigger` and `InvocationStatus` columns follow this exactly.
- **Same-transaction multi-insert in `handler.py`** (Conversation + StoredMessage + history fetch all share the same `with SessionLocal() as session: ... session.commit()`). The new `RobotinaInvocation` insert joins this transaction (D-11) — no separate session.
- **`job.meta`-based runtime context channel** for `task_type` (`handler.py:131`, `jobs.py:60`) — `invocation_id` joins this channel per D-12. Symmetric, no schema change to `IncomingMessageInput`.
- **Dashboard module isolation** (Phase 13 D-01) — `src/robotina/dashboard/` may import ONLY `robotina.queue.models`, `robotina.db`, `robotina.queue.task_types`. `RobotinaInvocation` lives in `robotina.queue.models`, so dashboard reads it via the existing allowed channel — no new imports, no grep-gate violation (D-21).

### Integration Points
- `src/robotina/queue/models.py` — add `InvocationTrigger`, `InvocationStatus` enums and the `RobotinaInvocation` model; add `triggered_by_invocation_id` column to `WorkflowRun`.
- `src/robotina/queue/task_types.py` — replace Phase 17's `WorkflowOutcome` stub with the real `AddRecipeOutcome` (D-16/D-17/D-18).
- `src/robotina/queue/workflow_runner.py::queue_workflow` — signature gains `triggered_by_invocation_id` arg; passes to `WorkflowRun(...)` kwargs (D-14).
- `src/robotina/agent/tools/start_workflow.py` — class body gains `invocation_id: str` field; `_run` passes it to `queue_workflow` (D-13).
- `src/robotina/queue/jobs.py` — `handle-incoming-message` branch reads `meta['invocation_id']` and passes to `StartWorkflowTool` constructor (D-15).
- `src/robotina/gateway/handler.py` — new step 2b for `RobotinaInvocation` insert; enqueue gains `meta['invocation_id']` (D-11).
- `src/robotina/dashboard/templates/workflow.html` — new `<dt>/<dd>` in `kv-grid` (D-19).
- `migrations/versions/` — one new file (`0007_robotina_invocations.py`).
- `tests/gateway/test_handler.py` — three new assertions (D-24).
- `tests/unit/test_start_workflow_tool.py` (or wherever Phase 17 adds `conversation_id` tests) — extend with `invocation_id` propagation (D-22).
- `tests/integration/test_workflow_runner.py` — extend to assert `triggered_by_invocation_id` on the persisted row (D-23).

</code_context>

<specifics>
## Specific Ideas

- **Phase 17 + Phase 18 are siblings.** Phase 18 inherits Phase 17's topology and adds a parallel rail (`invocation_id` next to `conversation_id`). Every `StartWorkflowTool` / `queue_workflow` / `run_task` diff in Phase 18 should be done as an additive parallel — never rewrite Phase 17's `conversation_id` lines.
- **Ship Phase-20-ready schema columns now (D-05/D-06/D-07/D-08).** The user's preference in Phase 17 to avoid backfill ceremony does not extend to this question — adding nullable columns and pre-creating enum values is forward-compat, not ceremony. The cost of `ALTER TABLE`/`ALTER TYPE` in Phase 20 is higher than carrying NULL columns in Phase 18.
- **`AddRecipeOutcome` is the only outcome shape in v1.1.** Resist the temptation to introduce a `WorkflowOutcome` wrapper or a discriminated union over future outcomes — `feedback_avoid_premature_abstraction.md` applies. Phase 23 (URL ingestion) reuses `AddRecipeOutcome` (URL ingestion produces the same shape). If/when a workflow with a non-recipe outcome shows up, the wrapper can be introduced as a refactor then.
- **The duplicate-message dedup path in `handler.py:86–89` is load-bearing for Phase 18.** The test D-24 explicitly guards it: a duplicate `platform_message_id` must NOT create an orphan invocation. This is the single most important new test in the phase.
- **`StartWorkflowTool.invocation_id` MUST be constructor-injected, not mutable state** (Pitfall 5). When Phase 21 lands multi-call StartWorkflowTool, this decision is what keeps concurrent tool calls correct. Re-litigating it then will introduce a race; do not let the planner relax it.

</specifics>

<deferred>
## Deferred Ideas

- **Wake rule + `wake_dispatched_at` UPDATE-RETURNING idempotency** — Phase 20 (WAKE-01..05). The column exists from Phase 18 (D-05) but is unused.
- **`InvocationStatus` transitions (PENDING → RUNNING → DONE/FAILED) + the `_check_and_dispatch_wake` helper** — Phase 20.
- **`WakeInvocationInput` model + `run_task` dispatch on `trigger=WORKFLOW_COMPLETION`** — Phase 20.
- **Pre-assigned `rq_job_id` for the next invocation (the Phase 4 D-07 pattern, applied to invocations)** — Phase 20. Phase 18's insert-then-enqueue sequence (D-11) is the simpler shape; recoverability is Phase 20's concern.
- **Startup reconciler for orphan invocations** (`wake_dispatched_at IS NOT NULL but no RQ job`) — Phase 20.
- **`finalize-outcome` deterministic step that writes `WorkflowRun.outcome` from accumulated artifacts** — Phase 20. Phase 18 only defines the Pydantic shape (`AddRecipeOutcome`).
- **Dashboard rendering of `conversation_id`** — Phase 20 (DASH-10). Phase 18 leaves Phase 17's column unrendered.
- **Dashboard rendering of the `outcome` summary cell** — Phase 20 (DASH-12). Phase 18 leaves the column unrendered.
- **Dashboard list-view changes** for new columns — Phase 20.
- **Dedicated RobotinaInvocation list/detail dashboard view** — backlog. DASH-13 marks it "nice-to-have"; not load-bearing for any milestone.
- **Multi-call `StartWorkflowTool`** (one invocation → N WorkflowRuns) — Phase 19 evidence first; Phase 21 flips the tool. Phase 18's constructor-injection (D-13) makes this safe to flip later.
- **Dropping `chat_id`/`user_id`/`platform` from `StartWorkflowTool`** — defer until ARCH-05 deprecation window closes (post-v1.1).
- **CRON-trigger `ScheduledTask` model + Phase 18's `trigger=CRON` rows actually being written** — deferred scheduler milestone. Phase 18 ships the enum value (D-06) but no producer.
- **`WorkflowOutcome` envelope** (architecture's `{workflow_run_id, workflow_type, status, summary, structured}` wrapper around per-workflow outcome shapes) — defer until ≥2 workflow types with distinct outcome shapes exist. URL ingestion (Phase 23) reuses `AddRecipeOutcome`, so the trigger is "first non-recipe workflow," likely a v1.2+ milestone.

</deferred>

---

*Phase: 18-RobotinaInvocation entity*
*Context gathered: 2026-05-18*
