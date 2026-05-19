---
phase: 18
artifact: deploy-runbook
created: 2026-05-19
applies_to: production + staging
prerequisite: Phase 17 runbook executed (workflow_runs has conversation_id NOT NULL + outcome JSON column from revision 0006)
---

# Phase 18 Deploy Runbook — RobotinaInvocation entity

## Purpose

Migrate the live database from Alembic revision `0006` to `0007`. The migration is strictly additive (creates the new `robotina_invocations` table + enums; adds a NULLABLE FK on `workflow_runs`). NO data is truncated; NO backfill SQL is executed; NO existing rows are mutated. Per D-02 / D-03 (CONTEXT.md), historical `workflow_runs` rows carry NULL on the new FK column and are correctly ignored by Phase 20's wake rule.

## Pre-flight (operator)

1. Confirm prior phase is complete on this DB: `psql "$DATABASE_URL" -c "SELECT version_num FROM alembic_version;"` returns `0006`.
2. Confirm the codebase is at the Phase-18 deploy artifact (HEAD or release tag): `git log -1 --oneline` should reference the Phase-18 plans.
3. Optional: snapshot the DB before migrating (`pg_dump`) — additive migration is reversible via `alembic downgrade 0006`, but a backup is cheap insurance.

## Procedure

### Step 1 — Stop the task-runner

```bash
docker compose stop task-runner
```

The gateway can keep running — the migration is column-add only and does NOT lock `workflow_runs` for any meaningful duration. If the gateway accepts a message during the migration, the resulting `workflow_runs` row will have `triggered_by_invocation_id = NULL` (which is fine — the FK is nullable per D-02; Phase 20's wake rule ignores NULL).

If you prefer maximum strictness, stop the gateway too:

```bash
docker compose stop gateway
```

### Step 2 — Run the migration

```bash
uv run migrate
```

This applies revision `0007_robotina_invocations`. Expected output ends with `INFO  [alembic.runtime.migration] Running upgrade 0006 -> 0007, robotina_invocations: new table + nullable FK on workflow_runs`.

### Step 3 — Verify schema

```bash
psql "$DATABASE_URL" -c "\d robotina_invocations"
psql "$DATABASE_URL" -c "SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name='workflow_runs' AND column_name='triggered_by_invocation_id';"
```

Expected:
- `robotina_invocations` table exists with columns: `id`, `conversation_id`, `trigger`, `trigger_ref_id`, `rq_job_id`, `status`, `wake_dispatched_at`, `started_at`, `completed_at`, `created_at`, `updated_at`.
- Named unique constraint `ux_invocation_workflow_completion_once` on `(trigger_ref_id, trigger)`.
- FK `workflow_runs.triggered_by_invocation_id` exists, `is_nullable = YES`.
- `alembic_version.version_num = '0007'`.

### Step 4 — Restart task-runner (+ gateway if stopped)

```bash
docker compose start task-runner
docker compose start gateway   # only if stopped in Step 1
```

### Step 5 — Manual smoke (LOAD-BEARING — feedback_test_before_handoff.md)

Send one real Telegram message: e.g. `agregá lentejas`. After ~30 seconds:

```bash
psql "$DATABASE_URL" -c "SELECT id, trigger, trigger_ref_id, conversation_id, status, created_at FROM robotina_invocations ORDER BY created_at DESC LIMIT 1;"
```

Expected:
- One new row.
- `trigger = 'user_message'`.
- `status = 'pending'` (Phase 18 only writes PENDING; Phase 20 transitions it).
- `trigger_ref_id` matches a recent `stored_messages.id`.

Then:

```bash
psql "$DATABASE_URL" -c "SELECT id, triggered_by_invocation_id, conversation_id FROM workflow_runs ORDER BY created_at DESC LIMIT 1;"
```

Expected if Robotina dispatched a workflow:
- `triggered_by_invocation_id` is non-NULL AND matches the `robotina_invocations.id` from the previous query.

Finally, open the dashboard:

```
http://127.0.0.1:8123/workflows/<run.id>
```

Expected:
- The detail-view kv-grid includes a row labeled "TRIGGERED BY INVOCATION" (CSS-uppercased) with the invocation UUID in monospace.

If any of the above fails, the runbook has not completed cleanly — revert via `alembic downgrade 0006` and investigate.

## Rollback

```bash
docker compose stop task-runner
docker compose stop gateway
uv run alembic downgrade 0006
docker compose start gateway
```

Rollback drops `robotina_invocations` and `workflow_runs.triggered_by_invocation_id` cleanly. Codebase must be checked out at a pre-Phase-18 SHA for the running workers to be compatible with the post-rollback schema. (Phase 18 code paths read/write the new columns; running them against schema `0006` will produce errors.)

## Notes

- Per D-02, the migration intentionally lands the FK as NULLABLE. No backfill is needed.
- Per D-08, the named unique constraint `ux_invocation_workflow_completion_once` is shipped now but is dormant in Phase 18 (only USER_MESSAGE rows are inserted, all with distinct `trigger_ref_id`s). Phase 20's wake rule will exercise it.
- The full Phase-20-ready column set is on the table; Phase 20 will neither ALTER TABLE nor ALTER TYPE for this entity.
