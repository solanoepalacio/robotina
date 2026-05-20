---
phase: 20-wake-rule-outcome-plumbing
plan: 06
subsystem: dashboard
tags: [dashboard, jinja, requirements-tick, wave-3, phase-closure]
requires: [20-02, 20-03]
provides: [DASH-10, DASH-12]
affects: [src/robotina/dashboard/templates/workflow.html, .planning/REQUIREMENTS.md]
tech-stack:
  added: []
  patterns:
    - "Jinja2 template reads JSON dict directly (no Pydantic deserialization on dashboard side) — preserves Phase 13 D-01 module isolation"
key-files:
  created:
    - tests/dashboard/test_workflow_template.py
  modified:
    - src/robotina/dashboard/templates/workflow.html
    - .planning/REQUIREMENTS.md
decisions:
  - "D-12 honored: Conversation row placed below Triggered by invocation in existing kv-grid"
  - "D-13 honored: outcome cell renders compact Spanish (✓ name (id) [sin imagen] / ✗ Falló: reason / —); never raw JSON"
  - "D-14 confirmed no-op for Phase 20: grep showed no task_type label map currently exists in src/robotina/dashboard/; deferred to Phase 21 per plan_notes"
  - "D-16 honored: REQUIREMENTS ticks land alongside the final wave commit (this plan)"
  - "Template tests use direct Jinja2 FileSystemLoader rendering against a dataclass stub — no DB, no HTTP — keeps the test suite fast and the dashboard module surface unchanged"
  - "Manual smoke checkpoint (Task 6.5) intentionally deferred to phase-level verification — operator is AFK during this autonomous run; smoke steps recorded below for later execution"
metrics:
  duration: "~5 minutes (auto-mode, dashboard-only changes)"
  completed: 2026-05-19
---

# Phase 20 Plan 06: Wave 3 Dashboard Surfacing + REQUIREMENTS Closure Summary

Two new `<dt>/<dd>` rows on the WorkflowRun detail page (Conversation, Outcome) plus REQUIREMENTS.md ticks closing all seven Phase 20 requirements.

## What Shipped

### Template (DASH-10 + DASH-12)

`src/robotina/dashboard/templates/workflow.html` — the existing `kv-grid` block gained two new pairs immediately after the `Triggered by invocation` row:

- **`<dt>Conversation</dt>`** — renders `run.conversation_id` in mono, em-dash on NULL. Always set for new rows since Phase 17 made the column NOT NULL.
- **`<dt>Outcome</dt>`** — compact human-readable Spanish summary built from `run.outcome` (read as a `dict`, no Pydantic deserialization):
  - Success: `✓ <recipe_name> (<recipe_id>)` with a `sin imagen` badge when `image_present` is falsy.
  - Failure: `✗ Falló: <failure_reason or "(sin detalle)">`.
  - NULL: em-dash placeholder.

The template intentionally does NOT import `AddRecipeOutcome` or any Pydantic model — it reads dict keys directly, preserving the Phase 13 D-01 module-isolation contract (`tests/dashboard/test_independence.py` still green).

### Tests

`tests/dashboard/test_workflow_template.py` (new, 9 tests, all passing):

1. Conversation row renders when `conversation_id` is set.
2. Conversation row falls back to em-dash when `conversation_id` is None (defensive — should never happen for new rows post Phase 17).
3. Success outcome renders ✓ + name + (id) + `sin imagen` badge.
4. Success outcome with `image_present=True` omits the `sin imagen` badge.
5. Failure outcome renders ✗ Falló: + reason.
6. Failure outcome with no `failure_reason` falls back to `(sin detalle)`.
7. NULL outcome renders em-dash placeholder; no ✓/✗ markers leak through.
8 & 9. Falsifiability: parameterised over success/failure — the Outcome cell never wraps the outcome in a `json-block` class (which is reserved for the `shared_context` dump elsewhere).

The tests render `workflow.html` directly via a `Jinja2 Environment(FileSystemLoader(...))` against a `_StubRun` dataclass — no DB, no FastAPI client, no fixtures from `conftest.py`. This makes them cheap (~70ms for all 9) and immune to the Postgres connectivity issues affecting the broader test sweep on this worktree.

### REQUIREMENTS.md (D-16)

Seven requirements flipped from `[ ]` to `[x]` and `Pending` → `Complete` in the traceability table:

- WAKE-01..05 (delivered by plans 20-02 and 20-03 — wake control loop, idempotency guard, pre-assigned job id, `WakeInvocationInput`, reconciler).
- DASH-10 (Conversation row — this plan).
- DASH-12 (Outcome cell — this plan).

## Commits

| Task | Commit  | Type | Description                                            |
| ---- | ------- | ---- | ------------------------------------------------------ |
| 6.1  | 776e7b5 | feat | Conversation + Outcome rows added to kv-grid           |
| 6.2  | ef5841b | test | 9 workflow.html render tests (Jinja-direct)            |
| 6.3  | —       | —    | Module-isolation gate verified green (no code change)  |
| 6.4  | fd9ee03 | docs | REQUIREMENTS.md: 7 ticks + traceability table updates  |

## Verification

- `grep -q "Conversation" src/robotina/dashboard/templates/workflow.html && grep -q "Outcome" ... && grep -q "sin imagen" ... && grep -q "Falló" ...` → OK
- `uv run pytest tests/dashboard/test_workflow_template.py -x -q` → 9 passed
- `uv run pytest tests/dashboard/test_independence.py -x -q` → 3 passed (module-isolation gate intact)
- `uv run pytest tests/dashboard/test_workflow_template.py tests/dashboard/test_independence.py tests/dashboard/test_app_starts.py -q` → 13 passed
- `grep -c "^- \[x\] \*\*WAKE-0[1-5]\*\*" .planning/REQUIREMENTS.md` → 5
- `grep -c "^- \[x\] \*\*DASH-1[02]\*\*" .planning/REQUIREMENTS.md` → 2

## D-14 Disposition (No-op for Phase 20)

Per the plan's `<plan_notes>`, D-14 (a Spanish task-type label for `finalize-outcome`) was confirmed a no-op:

```text
$ grep -rn "task_type\|TASK_TYPE_LABEL\|label_map" src/robotina/dashboard/
src/robotina/dashboard/__init__.py:4:except robotina.db, robotina.queue.models, robotina.queue.task_types.
```

No label map exists in the dashboard today; `task_type` strings are surfaced raw in templates. Introducing the first label map in Phase 20 would expand the dashboard surface area beyond what WAKE-01..05 / DASH-10 / DASH-12 require. **Deferred to Phase 21**, alongside the broader task-type cleanup. This is an explicit deferral, not a silent skip; Phase 21 planning must pick D-14 up.

## Known Stubs

None. The Conversation cell reads a live FK column populated by gateway inserts since Phase 17. The Outcome cell reads `WorkflowRun.outcome`, which is populated by the `finalize-outcome` step delivered in plan 20-02. No mock data, no placeholder TODOs.

## Deviations from Plan

None. Plan executed exactly as written:

- Task 6.1 template diff applied verbatim from the plan's `<action>` block.
- Task 6.2 tests cover all seven scenarios listed in the plan's `<behavior>` block plus two falsifiability variants (no-raw-JSON sanity check).
- Task 6.3 module-isolation gate ran green with no whitelist changes needed.
- Task 6.4 REQUIREMENTS.md ticks applied to exactly the seven IDs called out in D-16.
- Task 6.5 manual smoke checkpoint deferred per the spawn objective (see next section).

## MANUAL SMOKE CHECKPOINT (deferred)

> **Status:** Not yet executed — operator is AFK during this autonomous run. These steps should run at the phase-level human-verification step OR on the next interactive session, before declaring Phase 20 complete in any external sense (the code-level requirements are met; this is an end-to-end behavior smoke).

Per plan task 6.5 and CONTEXT D-23 / memory `feedback_test_before_handoff.md`, the following manual smoke verifies Phase 20 end-to-end (wake-rule control loop + finalize-outcome + V004 prompt + startup reconciler + dashboard surfacing):

1. **Start services.**
   - `docker compose up -d` (Postgres + Redis on host)
   - Separate terminals: `uv run migrate`, `uv run agent`, `uv run gateway`, `uv run dashboard`.
2. **Trigger an add-recipe.** Send a Telegram message to the bot: `agregá guiso de lentejas`.
3. **Wait for end-to-end completion** and observe:
   - Dashboard at `http://localhost:8000` shows the WorkflowRun with status DONE.
   - Detail view shows the new `Conversation` row populated AND the `Outcome` row reading `✓ <recipe-name> (<recipe-id>)` with a `sin imagen` badge (image step deferred to Phase 24).
   - The legacy `notify` reply arrives on Telegram (user-facing notification NOT removed in Phase 20).
4. **Inspect Postgres** for wake-rule plumbing:
   ```sql
   SELECT id, trigger, trigger_ref_id, status, wake_dispatched_at, rq_job_id
   FROM robotina_invocations
   ORDER BY created_at DESC
   LIMIT 5;
   ```
   - Most recent USER_MESSAGE invocation has `wake_dispatched_at` populated.
   - A new row exists with `trigger='workflow_completion'`, `trigger_ref_id = <USER_MESSAGE invocation id>`, and `status` in `{running, done, failed}` (depending on how V004 resolves the wake turn — no `respond()` tool until Phase 21, so DONE with no tool call is the expected happy path).
5. **Reconciler smoke (worker-crash recovery).**
   a. Start a recipe-add, watch dashboard.
   b. As soon as the dashboard shows the workflow DONE, immediately `Ctrl-C` the `uv run agent` process.
   c. Restart with `uv run agent`. In boot logs, expect EITHER `Reconciler: re-enqueued N orphan(s)` OR `Reconciler: no orphan invocations` (race-dependent — either is acceptable). The failure mode is a stuck PENDING invocation with no live RQ job; if observed, file a Phase 20 bug.
6. **Module-isolation gate.** `uv run pytest tests/dashboard/test_independence.py -q` → green.
7. **Full test sweep.** `uv run pytest -q` exits 0 (note: this requires the local Postgres credentials in `.env` to match `docker-compose.yml`; the worktree where this plan ran had a `password authentication failed for user "robotina"` mismatch, so integration tests in `tests/dashboard/test_detail_view.py`, `tests/queue/test_wake_dispatch.py`, `tests/queue/test_reconcile.py` etc. could not be executed here — they MUST be exercised on a properly-credentialed environment as part of this smoke).

**Resume signal:** Operator types `approved` (or describes any observed issue) at the phase-verification step.

## Self-Check: PASSED

Verified all artifacts and commits:

- `src/robotina/dashboard/templates/workflow.html` — FOUND, contains `Conversation`, `Outcome`, `sin imagen`, `Falló`.
- `tests/dashboard/test_workflow_template.py` — FOUND (9 tests, all passing).
- `.planning/REQUIREMENTS.md` — FOUND, 5x `[x] **WAKE-0[1-5]**` + 2x `[x] **DASH-1[02]**` confirmed via grep.
- Commits 776e7b5, ef5841b, fd9ee03 — all FOUND in `git log`.
- Module-isolation gate (`tests/dashboard/test_independence.py`) — still green (3 passed).
