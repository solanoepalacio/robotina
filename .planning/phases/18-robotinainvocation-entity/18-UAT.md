---
status: complete
phase: 18-robotinainvocation-entity
source: [18-01-SUMMARY.md, 18-02-SUMMARY.md, 18-03-SUMMARY.md, 18-RUNBOOK.md]
started: 2026-05-19T00:00:00Z
updated: 2026-05-19T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running task-runner/gateway. Start fresh (`uv run migrate` if pending, then `uv run agent` and gateway). Workers boot without errors, alembic head is '0007', and RobotinaInvocation model imports cleanly.
result: pass

### 2. Migration 0007 schema landed
expected: `psql "$DATABASE_URL" -c "\d robotina_invocations"` shows the table with columns id, conversation_id, trigger, trigger_ref_id, rq_job_id, status, wake_dispatched_at, started_at, completed_at, created_at, updated_at; unique constraint `ux_invocation_workflow_completion_once` present; `workflow_runs.triggered_by_invocation_id` exists and is nullable; `alembic_version.version_num = '0007'`.
result: pass

### 3. User message creates RobotinaInvocation row
expected: Send a real Telegram message (e.g. `agregá lentejas`). Within ~30s, `SELECT ... FROM robotina_invocations ORDER BY created_at DESC LIMIT 1` returns one new row with `trigger='user_message'`, `status='pending'`, and `trigger_ref_id` matching the latest `stored_messages.id`.
result: pass

### 4. WorkflowRun row carries triggered_by_invocation_id FK
expected: After the Telegram message dispatches a workflow, `SELECT id, triggered_by_invocation_id FROM workflow_runs ORDER BY created_at DESC LIMIT 1` shows `triggered_by_invocation_id` non-NULL and equal to the `robotina_invocations.id` from Test 3.
result: pass

### 5. Duplicate message: no orphan invocation (D-24 load-bearing guard)
expected: Send the same Telegram message twice in quick succession (same platform_message_id). The dedup short-circuit fires, and only ONE `robotina_invocations` row is created — no orphan invocation for the deduplicated second message.
result: pass
note: User could not trigger a duplicate send manually; passed by direction. Covered by automated test `test_duplicate_message_no_orphan_invocation` (GREEN).

### 6. Dashboard detail view renders "Triggered by invocation" with UUID
expected: Open `http://127.0.0.1:8123/workflows/<run.id>` for the workflow from Test 4. Detail-view kv-grid includes a row labeled "TRIGGERED BY INVOCATION" (CSS-uppercased) with the invocation UUID rendered in monospace.
result: pass

### 7. Dashboard detail view renders em-dash for null FK
expected: Open a workflow-detail page for a pre-Phase-18 historical run (or any run where `triggered_by_invocation_id IS NULL`). The same row appears with an em-dash placeholder ("—") instead of a UUID.
result: pass

### 8. REQUIREMENTS.md ARCH-02 wording uses rq_job_id
expected: `grep -n "rq_job_id" .planning/REQUIREMENTS.md` shows ARCH-02 description references `rq_job_id` (matching the implemented column name), with no stale `job_id` wording in that requirement.
result: pass

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
