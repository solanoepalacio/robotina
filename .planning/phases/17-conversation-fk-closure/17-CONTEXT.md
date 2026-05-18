# Phase 17: Conversation FK closure - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire a hard `WorkflowRun → Conversation` foreign key into the schema and the
write-path so every new WorkflowRun is provably linked to its originating
Conversation. Also land an unused, nullable `WorkflowRun.outcome` JSON column
(with a stub Pydantic model) as the slot Phase 20 will fill.

**In scope:**
- Add `WorkflowRun.conversation_id` (String, FK → `conversations.id`, NOT NULL).
- Add `WorkflowRun.outcome` (JSON, nullable; unused this phase).
- Add `queue/task_types.py::WorkflowOutcome` Pydantic stub (defined; not yet written by any step).
- `queue_workflow` signature: gains required `conversation_id: str` arg.
- `StartWorkflowTool`: gains constructor-injected `conversation_id` like `household_id`; passes it into `queue_workflow`.
- `run_task` (jobs.py) `handle-incoming-message` branch: resolve Conversation via `SELECT … WHERE platform = task_input.platform AND chat_id = task_input.chat_id`, raise `NoResultFound` on miss, pass `conversation.id` into `StartWorkflowTool(__init__)`.
- Single Alembic revision (0006) adds both columns. `conversation_id` NOT NULL upfront (table is empty before migrate per the operational runbook below).
- Tests update to reflect the new required arg (no NULL-fallback code path).

**Out of scope (deferred to later phases):**
- Reading `conversation_id` anywhere in the codebase — Phase 18+ start reading it; Phase 17 only writes it.
- Removing `shared_context.reply_context` writes — ARCH-05 deprecation window stays open through v1.1.
- `triggered_by_invocation_id` — Phase 18.
- The `finalize-outcome` step / `AddRecipeOutcome` real shape — Phase 20.
- Dashboard surfacing of `conversation_id` / `outcome` — Phase 18 (DASH-13, DASH-14) and Phase 20 (DASH-10, DASH-12).
- Any backfill logic — operator pre-cleans (see runbook).

</domain>

<decisions>
## Implementation Decisions

### Migration shape

- **D-01:** **Single Alembic revision** (`0006_conversation_fk_and_outcome.py`) — adds `conversation_id` as **NOT NULL** + `outcome` as nullable JSON in one upgrade. No three-step nullable→backfill→enforce ceremony.
  - **Why:** The user's operational plan pre-cleans the DB before migrating (see D-05). The three-step pattern was designed for production data backfill (ARCH research §2.1, PITFALLS #3); with an empty `workflow_runs` table the backfill step is a no-op and the staged enforce is ceremony for ceremony's sake. ROADMAP success-criterion #2's "post-migration `COUNT(*) WHERE conversation_id IS NULL` returns 0" is satisfied trivially because no rows exist when the migration runs.
  - **Implication for REQUIREMENTS.md:** ARCH-01's wording ("column is migrated nullable → backfill → NOT NULL via a three-step Alembic sequence") no longer matches the implementation. Planner should propose a one-line REQUIREMENTS.md edit alongside the migration commit: drop "via a three-step Alembic sequence; existing rows are backfilled" and replace with "as a single Alembic revision (table is pre-cleaned before deploy)".

- **D-02:** **No defensive backfill code, no orphan-handling branches.** Migration's `upgrade()` is `op.add_column(...)` × 2. No `op.execute("UPDATE …")`. No SELECT pre-flight. If the table is non-empty when the migration runs, Alembic / Postgres will fail loudly on the NOT NULL constraint — that is the intended signal that the operator skipped the runbook.

### `conversation_id` plumbing

- **D-03:** **Constructor-injected on StartWorkflowTool**, mirroring the Phase 16 `household_id` pattern.
  - Tool gains a required `conversation_id: str` field (Pydantic-validated against empty string the same way `NonEmptyHouseholdId` works on `household_id` — define a `NonEmptyConversationId` alias in `queue/task_types.py` or co-locate with `NonEmptyHouseholdId`).
  - `_run` stamps `self.conversation_id` into the `queue_workflow` call.
  - The existing `chat_id` / `user_id` / `platform` fields on the tool **stay** in this phase (read-path for `shared_context.reply_context` is unchanged; ARCH-05 deprecation window).

- **D-04:** **`run_task` resolves the Conversation row at tool-construction time.**
  - In `src/robotina/queue/jobs.py`, the `handle-incoming-message` branch (currently lines 134–149-ish) adds:
    ```python
    conversation = (
        session.query(Conversation)
        .filter_by(platform=Platform(task_input.platform), chat_id=task_input.chat_id)
        .one()
    )
    ```
  - `.one()` raises `sqlalchemy.exc.NoResultFound` on miss. The gateway always upserts a Conversation before enqueuing (`handler.py:57–71`), so a miss = invariant violation = fail loud.
  - Pass `conversation.id` into `StartWorkflowTool(conversation_id=conversation.id, …)`.
  - **Not chosen:** lookup inside `StartWorkflowTool._run` (cheap query repetition; Phase 18 will need this lookup *again* for `RobotinaInvocation` so deduping in run_task fits better); adding `conversation_id` to `IncomingMessageInput` (couples the message schema to a model the input doesn't logically own; also less symmetric with how `household_id` already flows).

- **D-05:** **`queue_workflow` signature gains required `conversation_id: str` arg.** No default, no fallback. Tests update accordingly. Forces the contract at the function boundary — no silent NULL writes possible.

### `outcome` column shape (this phase)

- **D-06:** **`outcome: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)`** on `WorkflowRun`. No constraint, no server default.

- **D-07:** **Add a `WorkflowOutcome` Pydantic stub in `src/robotina/queue/task_types.py`.** Minimal placeholder shape — exists so Phase 20 has a concrete extension point and so this phase exercises the import path the executor will land on later. Suggested skeleton:
  ```python
  class WorkflowOutcome(BaseModel):
      """Placeholder — Phase 20 defines the per-workflow-type shape (AddRecipeOutcome, etc.)."""
      model_config = ConfigDict(extra="forbid")
      status: Literal["pending"] = "pending"
  ```
  - Not yet imported by `workflow_runner.py` or any agent. The stub is a code anchor, not a runtime dependency this phase.

### Deploy runbook (Phase 17 → prod)

- **D-08:** **Documented procedure in PLAN.md (and surfaced in the final commit message):**
  1. `docker compose stop task-runner` (and `scheduler-worker` if running).
  2. Drain RQ: confirm zero PENDING / RUNNING WorkflowRuns; if any, wait or manually fail them.
  3. `TRUNCATE workflow_runs, workflow_run_steps RESTART IDENTITY CASCADE;` — Conversations and StoredMessages preserved.
  4. `uv run migrate` — applies `0006`.
  5. Restart the worker.
- **Rationale:** Phase 17 ships during pre-launch of v1.1; the household-scale data volume (single family, weeks of v1.0 use) makes wiping `workflow_runs` cheap. No pre-deploy gate code in the migration itself — the runbook + Alembic's loud failure-on-non-empty-table are sufficient at this scale.

### Claude's Discretion

- **Migration file location & naming:** Use the existing pattern (`migrations/versions/0006_<descriptive_snake_case>.py`); revision `0006`, down_revision `0005`. No branch labels, no `depends_on`. Mirror `0005_dashboard_columns.py` for style.
- **Test layout:** Standard Phase-2-style approach — Wave 0 stubs that fail (RED) for the new column / new arg, then implementation flips them green. Unit tests for `StartWorkflowTool` should construct it with a fake `conversation_id` and assert it propagates into the `queue_workflow` mock. Integration test on `queue_workflow` asserts the FK is set on the persisted row.
- **`NonEmptyConversationId` alias location:** Either co-locate next to `NonEmptyHouseholdId` (probably in `queue/task_types.py` or wherever that alias lives today) or skip the alias and let the FK + DB constraint do the validation. Planner chooses; a Pydantic-level guard is the project's established style (Phase 16 four-layer pattern) but `conversation_id` is generated by us (it's a UUID we just SELECTed), not LLM-supplied, so the LLM-shadowing attack surface that motivated `NonEmptyHouseholdId` doesn't exist here. Recommend skipping the alias; the FK constraint is sufficient.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 17: Conversation FK closure" — phase goal, success criteria, dependency on Phase 16.
- `.planning/REQUIREMENTS.md` ARCH-01, ARCH-05 — the two requirements this phase delivers. **Planner must propose the ARCH-01 wording update described in D-01.**

### Architecture and pitfalls (load-bearing context)
- `.planning/research/ARCHITECTURE.md` §2.1 "queue/models.py — schema diff" — original three-step migration recommendation (superseded for this phase by D-01; rationale preserved for future phases that need real backfill).
- `.planning/research/ARCHITECTURE.md` §2.2 "queue_workflow signature change" — confirms `conversation_id` belongs on the function signature.
- `.planning/research/ARCHITECTURE.md` §2.6 "StartWorkflowTool refactor table" — the row "Caller: `run_task` injects `conversation_id, invocation_id, household_id`" matches D-03/D-04 (this phase lands `conversation_id` only; `invocation_id` is Phase 18).
- `.planning/research/PITFALLS.md` Pitfall 3 "Migration backfill of `WorkflowRun.conversation_id` is non-trivial" — the reasoning behind the original three-step recommendation. D-01 sidesteps it via pre-clean; planner should still skim this so the alternative is understood.

### Existing codebase contracts
- `src/robotina/queue/models.py` (lines 28–37) — `WorkflowRun` 2.x `Mapped`/`mapped_column` style is the template; new columns follow it.
- `src/robotina/queue/workflow_runner.py::queue_workflow` (lines 106–206) — function being modified. Note Phase 16 REQ-HID-4 guard at line 138; keep it.
- `src/robotina/agent/tools/start_workflow.py` (lines 100–187) — Phase 16 `NonEmptyHouseholdId` injection pattern; mirror for `conversation_id` per D-03.
- `src/robotina/gateway/handler.py` (lines 57–94) — confirms Conversation is upserted before enqueue, validating D-04's "fail loud on miss".
- `src/robotina/gateway/models.py::Conversation` (lines 26–37) — uniqueness on `(platform, chat_id)`; this is the lookup key.
- `migrations/versions/0005_dashboard_columns.py` — closest stylistic template for `0006`.

### Project conventions
- `CLAUDE.md` "Tech Stack" — SQLAlchemy 2.x `Mapped` + `mapped_column` mandatory; Pydantic v2 only; `uv run migrate` is the migration command.
- `CLAUDE.md` "What NOT to Use" — confirms `AgentExecutor` / `create_react_agent` forbidden; not directly relevant here but governs any new agent code (none in this phase).
- Memory `feedback_avoid_premature_abstraction.md` — the `WorkflowOutcome` stub (D-07) is the smallest concession to forward-compatibility; do not generalize further this phase.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 16 `NonEmptyHouseholdId` pattern** (`src/robotina/queue/task_types.py` — exact location to confirm during planning): the Pydantic alias + tool-constructor + queue_workflow-guard chain is the canonical pattern. `conversation_id` plumbing copies the topology but skips the alias (Claude's Discretion above) — the rationale for keeping or dropping it is documented in PLAN.md.
- **Phase 16 `queue_workflow` REQ-HID-4 guard** (`workflow_runner.py:138`): defensive last-line-of-defense. Phase 17 does NOT add a parallel guard for `conversation_id` — FK constraint + run_task `.one()` raise cover it.
- **`Conversation` lookup primitive**: `session.query(Conversation).filter_by(platform=…, chat_id=…).one()` is used in `handler.py:57` and `handler.py:71` already. D-04 reuses that exact idiom.
- **Alembic revision template**: `0005_dashboard_columns.py` is the shape to copy — minimal upgrade/downgrade, no JSON-path SQL, no branch labels.

### Established Patterns
- **`Mapped[Optional[dict]]` + `JSON` + `nullable=True`** for additive JSON columns (already used for `WorkflowRunStep.artifact` and `WorkflowRunStep.step_input` per `models.py:51,54`).
- **Phase 4 D-07 transactional advancement**: pre-assign `job_id` BEFORE commit. Phase 17 does not enqueue anything new, so this pattern does not engage here — but planner should not break the existing `queue_workflow` D-07 wiring while refactoring its signature.
- **`shared_context.reply_context` read-path stays**: workflow_runner.py lines 401–533 (the dead-letter `send-notification` block) and `agent/workflows.py:105–159` (every step's `build_input`) still read `reply_context` from `shared_context`. These are unchanged this phase per ARCH-05.
- **`WorkflowRun.shared_context` continues to receive `reply_context`** from `start_workflow.py:144–152`. Don't strip it.

### Integration Points
- `src/robotina/queue/jobs.py` — the `handle-incoming-message` branch (around line 134–149) is the single integration point for the new Conversation lookup. No other branch needs to change this phase.
- `src/robotina/agent/tools/start_workflow.py` — class body (chat_id/user_id/platform/household_id fields) is the integration point for the new `conversation_id` constructor field.
- `src/robotina/queue/workflow_runner.py::queue_workflow` — signature update + new `WorkflowRun(...)` kwarg.
- `src/robotina/queue/models.py::WorkflowRun` — two new columns.
- `migrations/versions/` — one new file (`0006_*.py`).
- Tests: existing `tests/unit/test_workflow_runner.py`, `tests/unit/test_start_workflow_tool.py` (or wherever Phase 16 added the `NonEmptyHouseholdId` cases) need the new required arg threaded through their fixtures.

</code_context>

<specifics>
## Specific Ideas

- User explicitly rejected backfill / orphan-handling complexity. The operational reality (single household, pre-launch of v1.1) makes a clean-slate deploy correct. Capture this so future readers don't re-litigate the three-step pattern.
- User opted to define a `WorkflowOutcome` Pydantic stub now even though Phase 20 will rewrite it. The stub is a code anchor — it pre-pays the cost of "where does this live" so Phase 20 reads as "fill in the shape", not "introduce a new concept".
- ARCH-01's REQUIREMENTS.md wording is now out of sync with the implementation. Planner must include a one-line REQUIREMENTS.md edit in the phase, NOT leave it as a follow-up — the requirement and the schema must agree at phase close.

</specifics>

<deferred>
## Deferred Ideas

- **`triggered_by_invocation_id` FK on WorkflowRun** — Phase 18 (ARCH-02, ARCH-03). The same `run_task` Conversation-lookup site (D-04) is where Phase 18 will also insert the `RobotinaInvocation` row and pass `invocation_id` into the tool.
- **Real `AddRecipeOutcome` shape + `finalize-outcome` step** — Phase 20 (ARCH-04, WAKE-01..05).
- **Dashboard surfacing of `conversation_id` / `outcome`** — Phase 18 (DASH-13, DASH-14) and Phase 20 (DASH-10, DASH-12). Phase 17 explicitly does not touch dashboard templates.
- **Dropping `chat_id` / `user_id` / `platform` from `StartWorkflowTool`** — defer until ARCH-05 deprecation window closes (post-v1.1). Same logic for `shared_context.reply_context` writes.
- **`shared_context` rename to `input`** mentioned in ARCH §2.1 — out of scope for v1.1.
- **CI guard that fails the build if any `queue_workflow` caller passes `conversation_id=None`** — overkill for this phase; the type signature is enough enforcement.

</deferred>

---

*Phase: 17-Conversation FK closure*
*Context gathered: 2026-05-18*
