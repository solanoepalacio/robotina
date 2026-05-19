# Phase 18: RobotinaInvocation entity - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 18-robotinainvocation-entity
**Mode:** `--auto` (system reminder asked the workflow to make reasonable calls
without stopping; every Q below was auto-resolved by Claude. The user can
redirect any decision before `/gsd-plan-phase 18` runs.)
**Areas discussed:** Migration shape, RobotinaInvocation schema scope, `invocation_id` plumbing, `AddRecipeOutcome` shape, Dashboard surfacing, Test strategy

---

## Migration shape

| Option | Description | Selected |
|--------|-------------|----------|
| Single Alembic revision (`0007`) — new table + nullable FK in one upgrade | Mirrors Phase 17's "one revision per phase" pattern; the table and the FK are co-dependent, so atomic is cleanest | ✓ |
| Two revisions (table first, then FK column) | Allows rolling back FK independently | |
| `triggered_by_invocation_id` NOT NULL after a second TRUNCATE of `workflow_runs` | Symmetric with Phase 17's pre-clean approach | |
| `triggered_by_invocation_id` NULLABLE in v1.1 | Matches ARCH-03 verbatim; no second TRUNCATE needed | ✓ |

**Auto-mode choice:** Single revision + nullable FK.
**Notes:** ARCH-03 explicitly says "the column lands nullable in v1.1." Re-truncating `workflow_runs` would be ceremony for no gain — Phase 17 already did the pre-clean, and the Phase 20 wake rule only acts on rows where the FK is set (NULL = "historical, ignored by wake"). Captured in D-01/D-02/D-03.

---

## RobotinaInvocation schema scope

| Option | Description | Selected |
|--------|-------------|----------|
| Minimum schema (Phase 18 only): `id`, `conversation_id`, `trigger`, `trigger_ref_id` | YAGNI; add the rest in Phase 20 | |
| Full Phase-20-ready schema: + `rq_job_id`, `status`, `wake_dispatched_at`, `started_at`, `completed_at` | Forward-compat; Phase 20 wires the wake rule against an already-present schema, no `ALTER TABLE` churn | ✓ |
| `InvocationTrigger` enum: only `USER_MESSAGE` now | YAGNI on the enum values | |
| `InvocationTrigger` enum: full set (`USER_MESSAGE`, `WORKFLOW_COMPLETION`, `CRON`) | One DDL pass, no `ALTER TYPE ... ADD VALUE` later | ✓ |
| Skip the `UniqueConstraint("trigger_ref_id", "trigger")` until Phase 20 | Defer | |
| Ship the `UniqueConstraint` upfront in Phase 18 | Load-bearing wake-rule idempotency guard (Pitfall 1+2); zero schema work in Phase 20 | ✓ |

**Auto-mode choice:** Full schema, full enum, constraint upfront.
**Notes:** `feedback_avoid_premature_abstraction.md` is about code abstractions; nullable columns and pre-created enum values are a schema-migration-cost discussion, not abstractions. The columns are explicitly named in ARCH-02. Captured in D-04..D-10.

---

## `invocation_id` plumbing

| Option | Description | Selected |
|--------|-------------|----------|
| Channel: `job.meta['invocation_id']` | Symmetric with the existing `meta['task_type']` channel; matches the wake-invocation channel Phase 20 will use | ✓ |
| Channel: add `invocation_id` field on `IncomingMessageInput` | Couples a queue-lifecycle id to the message-input schema | |
| `StartWorkflowTool.invocation_id`: constructor-injected (mirror Phase 17 `conversation_id`) | Same topology; safe for the multi-call refactor in Phase 21 (Pitfall 5) | ✓ |
| `StartWorkflowTool.invocation_id`: read from mutable shared state per-call | Race-prone when Phase 21 lands multi-call | |
| Insert invocation BEFORE `StoredMessage` dedup check | Insert is unconditional | |
| Insert invocation AFTER `StoredMessage.flush()` (so dedup short-circuit returns without orphan) | Critical: duplicates must NOT create orphan invocations | ✓ |
| Use a Pydantic `NonEmptyInvocationId` alias | Mirrors `NonEmptyHouseholdId` | |
| Skip the Pydantic alias; rely on FK constraint + bracket-key read | `invocation_id` is runtime-generated, not LLM-supplied — no shadowing surface | ✓ |

**Auto-mode choice:** `job.meta` channel; constructor-injected on the tool; insert after dedup; no Pydantic alias.
**Notes:** Captured in D-11..D-15. Mirrors Phase 17 D-03/D-04/D-05 one-for-one.

---

## `AddRecipeOutcome` shape

| Option | Description | Selected |
|--------|-------------|----------|
| Discriminated union over `Literal["success", "failure"]` variants | Schema-level guarantee that success rows have `recipe_*` and failure rows have `failure_reason` | |
| Single class, Optional fields, `extra="forbid"`, producer-side contract | Less Pydantic ceremony; only one producer in v1.1 (`finalize-outcome`) so the contract is enforceable in code | ✓ |
| Define `AddRecipeOutcome` AND keep Phase 17's `WorkflowOutcome` stub as a wrapper | Forward-compat with multi-workflow-type future | |
| REPLACE Phase 17's stub with `AddRecipeOutcome`; no wrapper in v1.1 | `feedback_avoid_premature_abstraction.md` — single workflow type, no wrapper needed | ✓ |

**Auto-mode choice:** Single class with Optional fields; replace the Phase 17 stub.
**Notes:** Captured in D-16/D-17/D-18. URL ingestion (Phase 23) reuses the same shape — the wrapper trigger is "first non-recipe workflow," likely v1.2+.

---

## Dashboard surfacing

| Option | Description | Selected |
|--------|-------------|----------|
| Surface `triggered_by_invocation_id` on the WorkflowRun detail page (one new `<dt>/<dd>`) | Bare minimum per DASH-13 | ✓ |
| Also surface `conversation_id` (Phase 17's column) on the detail page | Cheap by-product; same template | |
| Also surface `outcome` summary cell | DASH-12 territory; Phase 20 work | |
| Surface invocation on the list view too | Premature; Phase 20 / DASH-10 work | |
| Build a dedicated RobotinaInvocation list/detail view | Premature; DASH-13 marks this "nice-to-have" | |
| Add a JOIN to RobotinaInvocation to render trigger type / started_at inline | Premature; raw FK string is sufficient for DASH-13 | |

**Auto-mode choice:** Just the FK on the detail view; defer everything else to Phase 20 (DASH-10/DASH-12).
**Notes:** Captured in D-19/D-20. Keeps DASH-13 narrowly scoped and avoids stealing Phase 20's surface area.

---

## Test strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Unit test: `StartWorkflowTool` propagates `invocation_id` to `queue_workflow` | Mirrors Phase 17's `conversation_id` unit test | ✓ |
| Integration test: `queue_workflow` persists `triggered_by_invocation_id` on the row | Real Postgres, `@pytest.mark.integration` | ✓ |
| Gateway test: assert `RobotinaInvocation` is inserted on a fresh message | Verifies the gateway diff | ✓ |
| Gateway test: assert `meta['invocation_id']` lands on the enqueued job | Verifies the meta channel | ✓ |
| Gateway test: assert duplicate `platform_message_id` does NOT create an orphan invocation | Load-bearing — the dedup-no-orphan invariant | ✓ |
| Dashboard test: template renders the new `<dt>/<dd>` correctly (set + NULL paths) | Trivial Jinja smoke test | ✓ |
| Module-isolation grep gate (`tests/dashboard/test_independence.py`) continues to pass | DASH-14; expected with no changes | ✓ |

**Auto-mode choice:** All seven (mandatory). Captured in D-21..D-24.

---

## Claude's Discretion

- Migration file naming: `migrations/versions/0007_robotina_invocations.py`.
- PostgreSQL ENUM creation: reuse the Phase 2 `postgresql.ENUM(create_type=False)` idiom from `migrations/versions/0001_create_*.py`.
- `InvocationTrigger` / `InvocationStatus` placement: top of `src/robotina/queue/models.py`, alongside existing `WorkflowStatus` / `WorkflowStepStatus`.
- `AddRecipeOutcome` placement in `task_types.py`: after `RecipeLoadOutput`, with a section header matching the existing style.
- `rq_job_id` (not `job_id`) as the column name, to disambiguate from `WorkflowRunStep.task_job_id`. REQUIREMENTS.md ARCH-02 wording update in the same commit (D-25).
- No `NonEmptyInvocationId` Pydantic alias (FK constraint + bracket-key meta read are sufficient).

## Deferred Ideas

(See CONTEXT.md `<deferred>` for the full list — abridged here.)

- Wake rule + `wake_dispatched_at` UPDATE-RETURNING idempotency — Phase 20.
- `InvocationStatus` transitions (PENDING → RUNNING → DONE/FAILED) — Phase 20.
- `WakeInvocationInput` model + `run_task` dispatch on `trigger=WORKFLOW_COMPLETION` — Phase 20.
- Pre-assigned `rq_job_id` (transactional advancement for wake invocations) — Phase 20.
- Startup reconciler for orphan invocations — Phase 20.
- `finalize-outcome` deterministic step that writes `WorkflowRun.outcome` — Phase 20.
- Dashboard rendering of `conversation_id` (DASH-10), `outcome` summary cell (DASH-12), list-view changes — Phase 20.
- Dedicated RobotinaInvocation list/detail dashboard view — backlog.
- Multi-call `StartWorkflowTool` — Phase 21 (Phase 19 evidence first).
- `WorkflowOutcome` envelope wrapper — defer until ≥2 workflow types with distinct outcome shapes exist (likely v1.2+).
- CRON-trigger producer (`ScheduledTask` model) — deferred scheduler milestone.
