---
phase: 18
plan: 02
subsystem: queue
tags: [wave-1, schema-land, robotina-invocation, alembic-0007, add-recipe-outcome]
requires:
  - Phase 18 Plan 01 complete (Wave 0 RED-state lock tests in place)
  - Phase 17 closed (WorkflowRun.conversation_id NOT NULL + WorkflowOutcome stub exist)
provides:
  - InvocationTrigger + InvocationStatus enums (full Phase-20-ready value sets)
  - RobotinaInvocation ORM class in robotina.queue.models (full schema with named UniqueConstraint)
  - WorkflowRun.triggered_by_invocation_id NULLABLE FK column
  - Alembic migration 0007 (creates table, enums, FK column — single revision)
  - AddRecipeOutcome Pydantic shape (replaces Phase 17 WorkflowOutcome stub; no consumer yet — Phase 20)
affects:
  - src/robotina/queue/models.py
  - src/robotina/queue/task_types.py
  - migrations/versions/0007_robotina_invocations.py (NEW)
  - tests/test_workflow_runner.py (Wave 0 migration_0007 skip filled in; pre-existing migration_0005/0006 tests pinned to explicit endpoints)
tech-stack:
  added: []
  patterns:
    - "SQLAlchemy 2.x Mapped/mapped_column ORM additive layer (verbatim from Phase 17 WorkflowRun template)"
    - "PostgreSQL native ENUM with idempotent DO $$ BEGIN IF NOT EXISTS ... pg_type guard (Phase 2 lesson)"
    - "values_callable=lambda x: [e.value for e in x] on every SQLAlchemy Enum column (Phase 3 lesson)"
    - "Named UniqueConstraint in __table_args__ (Phase-20 wake-rule idempotency guard, dormant in Phase 18)"
    - "Pydantic v2 BaseModel + ConfigDict(extra='forbid') + Literal status discriminator"
    - "Alembic migration-test pinning: explicit upgrade(target)/downgrade(target) over upgrade('head')/downgrade('-1') so test scope survives later revisions"
key-files:
  created:
    - migrations/versions/0007_robotina_invocations.py
  modified:
    - src/robotina/queue/models.py
    - src/robotina/queue/task_types.py
    - tests/test_workflow_runner.py
decisions:
  - "D-01..D-25 inherited from 18-CONTEXT.md verbatim; this plan is mirror-not-invent execution."
  - "Rule 1 deviation: pinned pre-existing test_migration_0005 + test_migration_0006 to explicit revision endpoints (was head/-1) — Phase 18's new revision 0007 shifts head and breaks the -1 downgrade boundary. Documented in Deviations section."
  - "Rule 3 deviation: TRUNCATEd workflow_runs + workflow_run_steps in the test DB before running migration tests — the test DB still carried pre-Phase-17 rows that block migration 0006's NOT NULL ALTER TABLE. This mirrors the Phase 17 deploy runbook (D-08) and is environment maintenance, not a code change."
metrics:
  duration: ~6min
  completed: 2026-05-19
requirements: [ARCH-02, ARCH-03, ARCH-04]
requirements_addressed: [ARCH-02, ARCH-03, ARCH-04]
---

# Phase 18 Plan 02: Wave 1 Schema Land Summary

**One-liner:** Land the RobotinaInvocation table + enums + nullable `workflow_runs.triggered_by_invocation_id` FK in a single Alembic revision (0007), and replace the Phase-17 `WorkflowOutcome` stub with the `AddRecipeOutcome` Pydantic shape that Phase 20's `finalize-outcome` step will populate.

## What Was Built

### Task 2.1 — RobotinaInvocation ORM + enums + WorkflowRun.triggered_by_invocation_id (commit `77b93cb`)

`src/robotina/queue/models.py`:
- Added `InvocationTrigger(enum.Enum)` with full value set: `USER_MESSAGE = "user_message"`, `WORKFLOW_COMPLETION = "workflow_completion"`, `CRON = "cron"` (D-06).
- Added `InvocationStatus(enum.Enum)` with full value set: `PENDING`, `RUNNING`, `DONE`, `FAILED` (D-07).
- Added `RobotinaInvocation(Base)` ORM class with full Phase-20-ready schema (D-04/D-05/D-10):
  - PK: `id` (uuid string, `default=lambda: str(uuid.uuid4())`).
  - FK: `conversation_id` → `conversations.id` (NOT NULL).
  - Lifecycle: `trigger` (Enum NOT NULL), `trigger_ref_id` (nullable), `rq_job_id` (nullable), `status` (Enum NOT NULL, default PENDING).
  - Phase-20 slots (all nullable in Phase 18): `wake_dispatched_at`, `started_at`, `completed_at`.
  - Timestamps: `created_at` (server_default now), `updated_at` (server_default now, onupdate now).
  - `__table_args__` carries the named `UniqueConstraint("trigger_ref_id", "trigger", name="ux_invocation_workflow_completion_once")` (D-08) — dormant in Phase 18, load-bearing in Phase 20 for the wake-rule idempotency invariant.
  - Both Enum columns use `values_callable=lambda x: [e.value for e in x]` (Phase 3 lesson — store VALUES not NAMES).
- Added `WorkflowRun.triggered_by_invocation_id: Mapped[Optional[str]]` — NULLABLE FK to `robotina_invocations.id` (ARCH-03 / D-02 — no backfill in v1.1).
- No new imports needed (everything was already imported at lines 1-10).
- No relationships added (out of scope per D-19 — dashboard reads as plain string).

### Task 2.2 — Alembic migration 0007 + round-trip test body (commit `778d799`)

`migrations/versions/0007_robotina_invocations.py` (NEW, 95 lines):
- `revision = '0007'`, `down_revision = '0006'`.
- `upgrade()`:
  - Idempotent `CREATE TYPE` via `DO $$ BEGIN IF NOT EXISTS ... END $$` for both `invocationtrigger` and `invocationstatus` (Phase 2 lesson).
  - `op.create_table('robotina_invocations', ...)` with full column set + `sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'])` + the named `sa.UniqueConstraint('trigger_ref_id', 'trigger', name='ux_invocation_workflow_completion_once')`.
  - `op.add_column('workflow_runs', sa.Column('triggered_by_invocation_id', sa.String(), sa.ForeignKey('robotina_invocations.id'), nullable=True))` (D-02).
  - `PgEnum(..., create_type=False)` used to attach already-created enums to the new columns.
- `downgrade()`: reverses in correct order: drop FK column → drop table → `DROP TYPE` both enums.
- D-03 guards verified: no `op.execute(...)` (only `conn.execute(sa.text(...))` for the idempotent enum guard), no `UPDATE workflow` SQL anywhere.

`tests/test_workflow_runner.py::test_migration_0007_upgrades_and_downgrades` — Wave-0 `pytest.skip(...)` removed; real round-trip body added:
- Loads migration module via `importlib.util.spec_from_file_location`, asserts `revision == "0007"` / `down_revision == "0006"`.
- `command.upgrade(cfg, "head")` then asserts via `sa.inspect(conn)`:
  - `has_table("robotina_invocations")` is True.
  - `workflow_runs.triggered_by_invocation_id` exists with `nullable=True`.
  - `get_unique_constraints("robotina_invocations")` includes `ux_invocation_workflow_completion_once` with column set `{"trigger_ref_id", "trigger"}` (order-insensitive).
  - `pg_type` contains both `invocationtrigger` and `invocationstatus` rows.
- `command.downgrade(cfg, "-1")` then asserts table + FK column are gone.
- Re-upgrades to head so the test DB is at head for subsequent tests.

### Task 2.3 — Replace WorkflowOutcome stub with AddRecipeOutcome (commit `b60cbd1`)

`src/robotina/queue/task_types.py`:
- DELETED Phase-17 `WorkflowOutcome` placeholder class + its section-header comment block.
- ADDED `AddRecipeOutcome(BaseModel)` with section-header divider (D-16/D-17/D-18):
  - `model_config = ConfigDict(extra="forbid")`.
  - `status: Literal["success", "failure"]` (rejects "completed", "pending", etc.).
  - `recipe_id: str | None = None`, `recipe_name: str | None = None`, `recipe_slug: str | None = None` (success variant).
  - `failure_reason: str | None = None` (failure variant).
  - `image_present: bool = False` (default — Phase 24 will flip per-recipe).
- No backward-compat alias for `WorkflowOutcome` (D-18: replace, don't supplement).
- No new imports needed (`BaseModel`, `ConfigDict`, `Literal` all already imported).
- Cross-module re-grep confirmed zero surviving consumers of `WorkflowOutcome` before the swap.

## Symbols + Schema Added

| Symbol | Type | Where | Purpose |
|---|---|---|---|
| `InvocationTrigger` | `enum.Enum` | `robotina.queue.models` | Trigger source: USER_MESSAGE / WORKFLOW_COMPLETION / CRON |
| `InvocationStatus` | `enum.Enum` | `robotina.queue.models` | Invocation lifecycle: PENDING / RUNNING / DONE / FAILED |
| `RobotinaInvocation` | `Base` ORM | `robotina.queue.models` | One row per Robotina LLM turn (D-04 / ARCH-02) |
| `WorkflowRun.triggered_by_invocation_id` | column | `workflow_runs` | NULLABLE FK to robotina_invocations.id (ARCH-03 / D-02) |
| `AddRecipeOutcome` | Pydantic v2 model | `robotina.queue.task_types` | Per-workflow outcome summary; replaces WorkflowOutcome stub (D-16..D-18) |
| `robotina_invocations` table | DDL | migration 0007 | New entity table with named unique constraint (D-08) |
| `invocationtrigger` ENUM | PG type | migration 0007 | DB-level enum, 3 values (D-06) |
| `invocationstatus` ENUM | PG type | migration 0007 | DB-level enum, 4 values (D-07) |
| `ux_invocation_workflow_completion_once` | constraint | migration 0007 | UNIQUE(trigger_ref_id, trigger) — Phase 20 wake-rule idempotency guard (D-08) |

## RED → GREEN flip (Wave 0 tests landed in Plan 18-01)

| Test | Wave 0 | Wave 1 | Notes |
|---|---|---|---|
| `tests/test_queue_models.py::test_invocation_trigger_enum_has_full_value_set` | RED | **GREEN** | D-06 |
| `tests/test_queue_models.py::test_invocation_status_enum_has_full_value_set` | RED | **GREEN** | D-07 |
| `tests/test_queue_models.py::test_robotina_invocation_model_has_required_columns` | RED | **GREEN** | D-04/D-05/D-10 |
| `tests/test_queue_models.py::test_robotina_invocation_has_unique_constraint_on_trigger_ref_and_trigger` | RED | **GREEN** | D-08 |
| `tests/test_queue_models.py::test_workflow_run_has_triggered_by_invocation_id_column` | RED | **GREEN** | ARCH-03 / D-02 |
| `tests/test_task_types.py::test_add_recipe_outcome_success_round_trip` | RED | **GREEN** | D-17 |
| `tests/test_task_types.py::test_add_recipe_outcome_failure_round_trip` | RED | **GREEN** | D-17 |
| `tests/test_task_types.py::test_add_recipe_outcome_rejects_unknown_fields` | RED | **GREEN** | D-17 (extra='forbid') |
| `tests/test_task_types.py::test_add_recipe_outcome_rejects_invalid_status` | RED | **GREEN** | D-17 (Literal) |
| `tests/test_task_types.py::test_add_recipe_outcome_image_present_defaults_false` | RED | **GREEN** | D-17 (default False) |
| `tests/test_task_types.py::test_workflow_outcome_class_no_longer_exists` | RED | **GREEN** | D-18 |
| `tests/test_workflow_runner.py::test_migration_0007_upgrades_and_downgrades` | RED (Wave-0 skip) | **GREEN** | D-23 round-trip |
| **Total Wave-1 GREEN flips** | — | **12 / 12** | All schema/shape RED tests now GREEN |

## RED tests that STAY RED (handed off to Plan 18-03 / Wave 2)

These wiring-layer tests remain RED until the call-site changes in 18-03:

| Test | Reason RED |
|---|---|
| `tests/test_workflow_runner.py::test_queue_workflow_requires_triggered_by_invocation_id` | `queue_workflow` signature not yet extended |
| `tests/test_workflow_runner.py::test_queue_workflow_persists_triggered_by_invocation_id` | same |
| `tests/test_gateway.py::test_user_message_creates_invocation` | gateway handler step 2b not yet wired |
| `tests/test_gateway.py::test_duplicate_message_no_orphan_invocation` | same (load-bearing D-24 guard) |
| `tests/unit/test_start_workflow_tool.py::test_constructor_requires_invocation_id_no_default` | `StartWorkflowTool.invocation_id` field not yet added |
| `tests/unit/test_start_workflow_tool.py::test_start_workflow_tool_propagates_invocation_id` | same |

This is the **expected** state — schema separation from wiring is the explicit plan design.

## DASH-14 Module Isolation

| Check | Result |
|---|---|
| `tests/dashboard/test_independence.py` | 3 / 3 PASSED — no new cross-module edges introduced |
| RobotinaInvocation lives in `robotina.queue.models` | YES (D-04 satisfied; dashboard reads via existing allowed channel) |

## Cross-module grep findings

Per D-18 / Pitfall 3, the planner mandated a re-grep at execution time:

```bash
grep -rE "from robotina\.queue\.task_types import [^)]*WorkflowOutcome|task_types\.WorkflowOutcome" \
  src/ tests/ experiments/ --include="*.py"
```

**Result:** zero hits (exit 1). The Phase 17 stub was unused by design, so deleting it broke no consumer. The replacement landed cleanly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Pinned `test_migration_0005` and `test_migration_0006` to explicit revision endpoints**

- **Found during:** Task 2.2 verification (running full `tests/test_workflow_runner.py` suite to ensure no regressions)
- **Issue:** Both pre-existing migration round-trip tests used `command.upgrade(cfg, "head")` followed by `command.downgrade(cfg, "-1")` to test their respective revision boundaries. Phase 18's new revision 0007 shifts `head` from 0006 to 0007, so `downgrade -1 from head=0007` lands at 0006 (not 0005 for the 0005 test, not 0005 for the 0006 test). The assertion that the revision's columns are absent after downgrade then fails because the test is now testing the wrong transition.
- **Fix:** Rewrote both tests to use explicit revision targets: `command.upgrade(cfg, "0005")` / `command.upgrade(cfg, "0006")` and `command.downgrade(cfg, "0004")` / `command.downgrade(cfg, "0005")`. This makes each test self-contained — it tests the 0004↔0005 boundary (or 0005↔0006 boundary) regardless of where head lives, so the next revision (e.g. Phase 19's 0008) won't break them either.
- **Files modified:** `tests/test_workflow_runner.py`
- **Commits:** `778d799` (0006 fix in same commit as migration 0007 landing), `a70d695` (0005 fix as separate Rule 1 commit)
- **Scope:** `tests/test_workflow_runner.py` is already on the plan's `files_modified` list, so this is in-scope; the same regression-prevention pattern applies to the 0005 sibling test, fixed in the same plan to keep the migration-test suite green.

### Environment maintenance (Rule 3 — not a code change)

The test DB carried pre-Phase-17 rows in `workflow_runs` that block migration 0006's `NOT NULL ALTER TABLE`. Per Phase 17's deploy runbook (D-08), the operator must `TRUNCATE workflow_runs` before running 0006. The local dev DB had not been TRUNCATEd, so the very first `command.upgrade(cfg, "head")` in my new test failed at the 0005→0006 boundary, not at 0006→0007. One-time `TRUNCATE workflow_run_steps, workflow_runs RESTART IDENTITY CASCADE` cleared the issue. No code changes; documenting here for traceability.

## Verification

| Check | Command | Result |
|---|---|---|
| Wave 0 schema RED → GREEN | `uv run pytest tests/test_queue_models.py tests/test_task_types.py -x` | 37 / 37 PASSED |
| Migration 0007 round-trip | `uv run pytest tests/test_workflow_runner.py -k migration_0007` | 1 / 1 PASSED |
| All migration tests still pass | `uv run pytest tests/test_workflow_runner.py -k migration_000` | 3 / 3 PASSED (0005, 0006, 0007) |
| DASH-14 grep gate green | `uv run pytest tests/dashboard/test_independence.py -x` | 3 / 3 PASSED |
| Wave 2 wiring tests stay RED | `uv run pytest tests/{test_workflow_runner.py,test_gateway.py,unit/test_start_workflow_tool.py} -k "triggered_by or invocation"` | 6 / 6 RED (expected) |
| Migration syntactically valid | `uv run python -c "import importlib.util; ... assert m.revision == '0007' and m.down_revision == '0006'"` | exit 0 |
| Import smoke | `uv run python -c "from robotina.queue.models import InvocationTrigger, InvocationStatus, RobotinaInvocation; ..."` | exit 0 |
| D-03 guard — no `op.execute` | `grep -E '^\s*op\.execute' migrations/versions/0007_robotina_invocations.py` | no hits |
| D-03 guard — no backfill SQL | `grep -i "UPDATE workflow" migrations/versions/0007_robotina_invocations.py` | no hits |

## Threat Flags

None — pure schema + Pydantic shape changes. No new network surface, no auth paths, no file access, no trust-boundary changes. The new `triggered_by_invocation_id` column is FK-only (string UUID); the dashboard reads it as a plain string per D-19 with no JOIN, so no SQL-injection or unbounded-query surface introduced.

## TDD Gate Compliance

This plan is `type: execute` with two `tdd="true"` tasks (Task 2.1 and Task 2.3). The TDD lifecycle was satisfied by Wave 0 (Plan 18-01) landing RED tests first; Wave 1's job is the GREEN flip on those exact tests. The single `tdd="false"` task (Task 2.2) covers the migration file, which Wave 0 only locked at the import-contract level (skip placeholder body) — Wave 1 fills in the live-DB round-trip body and removes the skip.

Commit types used:
- `feat(18-02): ...` for Tasks 2.1, 2.2, 2.3 (new feature/schema).
- `fix(18-02): ...` for the Rule 1 deviation (test migration pinning).

No `test(...)` commits this plan because Wave 0 already landed all RED tests in Plan 18-01.

## Self-Check: PASSED

**Files created — verified on disk:**
- `migrations/versions/0007_robotina_invocations.py` — FOUND

**Files modified — verified on disk:**
- `src/robotina/queue/models.py` — FOUND (RobotinaInvocation class + 2 enums + FK column present)
- `src/robotina/queue/task_types.py` — FOUND (AddRecipeOutcome class present, WorkflowOutcome class absent)
- `tests/test_workflow_runner.py` — FOUND (migration_0007 skip removed; migration_0005 + migration_0006 pinned to explicit endpoints)

**Commits — verified in `git log`:**
- `77b93cb` — `feat(18-02): add RobotinaInvocation ORM + enums + WorkflowRun FK`
- `778d799` — `feat(18-02): add Alembic migration 0007_robotina_invocations` (includes test_migration_0006 Rule 1 pin)
- `b60cbd1` — `feat(18-02): replace WorkflowOutcome stub with AddRecipeOutcome`
- `a70d695` — `fix(18-02): pin test_migration_0005 to explicit 0004<->0005 endpoints`

## Known Stubs

`AddRecipeOutcome` has no producer in Phase 18 (Phase 20's `finalize-outcome` deterministic step will be the single producer per D-16). This is intentional and documented in CONTEXT.md and ARCH-04 — the shape ships now to give Phase 20 a stable target to populate. No UI renders this shape yet (DASH-12 deferred to Phase 20). Not a code stub, a planned producer-staged rollout.

## What's Next

Plan 18-03 (Wave 2) lands the call-site wiring:
- `queue_workflow` signature gains required `triggered_by_invocation_id: str` arg (D-14).
- `StartWorkflowTool` gains required `invocation_id: str` constructor field (D-13).
- `run_task` (jobs.py) reads `job.meta["invocation_id"]` via bracket-key (D-15).
- Gateway handler (`handler.py`) inserts `RobotinaInvocation` in the same transaction, post-StoredMessage-dedup short-circuit (D-11/D-24).
- The 6 wiring-layer RED tests above flip GREEN.

Plan 18-04 (Wave 3) lands the dashboard detail-view rendering (DASH-13 / D-19).
