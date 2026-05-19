# Phase 17 — Deploy Runbook

**Status:** Pre-deploy procedure
**Applies to:** Migration `0006_conversation_fk_and_outcome.py` (adds `WorkflowRun.conversation_id` NOT NULL FK + `WorkflowRun.outcome` JSON nullable)
**Decision reference:** Phase 17 CONTEXT.md D-08; REQUIREMENTS.md ARCH-01 (post-wording-update)
**Sequencing:** Run this BEFORE invoking `uv run migrate` in any environment that has live data in `workflow_runs`.

---

## Why this runbook exists

Migration 0006 adds `conversation_id` to `workflow_runs` as **NOT NULL** with no
default and **no defensive backfill code** in the migration body (per D-02). If
`workflow_runs` is non-empty when `0006` runs, Postgres rejects the ALTER and
the deploy fails loudly — that is the intended signal that this runbook was
skipped.

The operational scale of v1.1 pre-launch (single household, weeks of v1.0 use,
no production traffic the user cares about) makes a clean-slate deploy
correct. Three-step nullable→backfill→enforce ceremony is overhead-for-the-sake-of-it
when there are no rows worth preserving.

---

## Procedure (5 steps)

### Step 1 — Stop the workers

```bash
docker compose stop task-runner
docker compose stop scheduler-worker  # if running
```

Confirm no RQ worker is still attached to the `agent-tasks` queue.

### Step 2 — Drain RQ

Verify zero PENDING / RUNNING workflows. From the rq-dashboard at
`http://localhost:9181` (or via `rq info`), confirm:
- `agent-tasks` queue depth = 0
- No jobs in `StartedJobRegistry` for `agent-tasks`

If any PENDING / RUNNING WorkflowRuns exist, either wait for them to drain
naturally before stopping the worker (preferred) or manually fail them via
the dashboard. Do NOT proceed to Step 3 with jobs in flight — the TRUNCATE
will orphan them.

### Step 3 — Truncate workflow tables (preserve conversations + messages)

```sql
TRUNCATE workflow_runs, workflow_run_steps RESTART IDENTITY CASCADE;
```

Run this via `psql` directly against the live DB. The `CASCADE` clause is
defensive — `workflow_run_steps.workflow_run_id` already FKs to `workflow_runs`
so the truncate must propagate. `RESTART IDENTITY` resets any sequence-backed
columns (there are none in these tables today — both PKs are UUID-defaulted —
but the clause is harmless and explicit).

**Tables explicitly preserved:**
- `conversations` (gateway upserts; required by D-04's `.one()` lookup)
- `stored_messages` (referenced by `conversations` via FK; orphaning them is harmless but not necessary)
- All other tables (auth, dashboard config, etc.)

### Step 4 — Apply the migration

```bash
uv run migrate
```

This invokes `alembic upgrade head` (`src/robotina/db.py:31-34`). 0006 adds:
- `workflow_runs.conversation_id` (String, NOT NULL, FK → `conversations.id`)
- `workflow_runs.outcome` (JSON, nullable)

Verify success:
```bash
psql -c "\d workflow_runs"
```
- `conversation_id` row should show `character varying`, `not null`
- `outcome` row should show `json`, nullable
- A constraint named `workflow_runs_conversation_id_fkey` should reference `conversations(id)`

### Step 5 — Restart the worker

```bash
docker compose start task-runner
docker compose start scheduler-worker  # if it was running
```

Smoke-test from Telegram with a single message ("hola"). Verify:
- The gateway upserts a `Conversation` row (existing behavior)
- The agent run produces an `acknowledge-add-recipe` step that completes
- A new `WorkflowRun` row exists with `conversation_id` populated (matching the
  Conversation row's id) and `outcome` NULL

---

## Failure modes

| Symptom | Cause | Recovery |
|---------|-------|----------|
| `psycopg2.errors.NotNullViolation` during `uv run migrate` | Step 3 (TRUNCATE) was skipped or partial; some `workflow_runs` rows remain | Run Step 3, then re-run Step 4 |
| `sqlalchemy.exc.NoResultFound` in worker logs after restart | A `handle-incoming-message` job's `task_input.chat_id` does not match any Conversation row | Indicates a stale RQ job (Step 2 drain incomplete) OR a manually-enqueued test job bypassed the gateway. Manually fail the job from the dashboard. |
| `sqlalchemy.exc.MultipleResultsFound` in worker logs | Two Conversation rows share `(platform, chat_id)` — UniqueConstraint violation | Should be impossible (gateway models.py:28 enforces uniqueness). If observed, a manual seed bypassed the constraint; reconcile by deleting duplicates. |

---

## What NOT to do

- **Do NOT** add a backfill `op.execute("UPDATE ...")` in 0006. The migration is `add_column` × 2 only (D-02).
- **Do NOT** drop `chat_id` / `user_id` / `platform` from `StartWorkflowTool` or strip the `reply_context` write in `start_workflow.py:144-152`. The ARCH-05 deprecation window stays open through v1.1 — multiple read sites still depend on `shared_context.reply_context`.
- **Do NOT** mark ARCH-01 / ARCH-05 as Complete in REQUIREMENTS.md until this runbook has been executed on the live DB AND a smoke-test confirms a Telegram message produces a `WorkflowRun` with a populated `conversation_id`.

---

*Phase: 17 — Conversation FK closure*
*Runbook generated: Phase 17 Plan 04 (Wave 3)*
*Source: CONTEXT.md D-08; reflected in this phase's final commit message*
