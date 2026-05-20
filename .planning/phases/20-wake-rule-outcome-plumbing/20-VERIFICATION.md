---
phase: 20
status: human_needed
checked: 2026-05-19
must_haves_verified: 5/5
---

# Phase 20: Wake Rule + Outcome Plumbing — Verification Report

**Phase Goal:** When all workflows linked to one invocation reach terminal status, exactly one wake invocation is enqueued — with structured outcomes the next Robotina turn can consume.

**Verified:** 2026-05-19
**Status:** human_needed (code complete; manual Telegram round-trip smoke test deferred per 20-06)

---

## Goal Achievement — Must-Haves

### MH1 — Single wake enqueue on workflow completion (WAKE-01)

**Status:** VERIFIED

`_check_and_dispatch_wake` in `src/robotina/queue/workflow_runner.py:106-250`:

- Returns early when `invocation_id` is None (legacy rows).
- Counts sibling `WorkflowRun` rows via `triggered_by_invocation_id` and returns when any are non-terminal (`status not in {DONE, FAILED}`).
- Inserts a new `RobotinaInvocation` with `trigger=InvocationTrigger.WORKFLOW_COMPLETION` and `trigger_ref_id=parent.id` (lines 211-219).
- Enqueues `run_task` with the pre-assigned `rq_job_id` (lines 235-246).

Called from `on_step_complete` final-DONE branch at `workflow_runner.py:547` and `on_step_failed` at `workflow_runner.py:655` — both inside the same session before `session.commit()` (single-commit atomic write covering status flip + new row, Pitfall 2).

### MH2 — Idempotency via UPDATE-RETURNING (WAKE-02)

**Status:** VERIFIED

`workflow_runner.py:164-172`:

```
UPDATE robotina_invocations
SET wake_dispatched_at = :now
WHERE id = :iid AND wake_dispatched_at IS NULL
RETURNING id
```

Zero rows affected → log "Wake skipped (already dispatched)" and return, so a manual requeue from RQ FailedJobRegistry cannot fire a second wake. The guard is the FIRST mutation after the terminal-sibling check, before any `RobotinaInvocation` insert.

### MH3 — Reconciler recovers crash-stranded wake row (WAKE-05)

**Status:** VERIFIED

- `reconcile_invocations` in `src/robotina/queue/reconcile.py:25-133` selects `RobotinaInvocation` rows with `status=PENDING AND wake_dispatched_at IS NOT NULL AND rq_job_id IS NOT NULL`.
- For each, `Job.exists(row.rq_job_id, connection=queue.connection)` skips live jobs; missing jobs are re-enqueued with the **same pre-assigned `rq_job_id`** (line 112), rebuilding the `WakeInvocationInput` from committed sibling outcomes.
- Boot wiring in `src/robotina/queue/runner.py:101-113` opens a `SessionLocal()` and calls `reconcile_invocations(_recon_session, queue)` before `worker.work()`, inside a `try/except` so a reconciler failure does not block boot.

### MH4 — Non-null `WorkflowRun.outcome` + dashboard cell (WAKE-04 / DASH-12)

**Status:** VERIFIED

- Workflow step appended in `src/robotina/agent/workflows.py:169-176`: `step_key="finalize-outcome"`, `task_type="finalize-outcome"`, builds a `FinalizeOutcomeInput` from the prior `metadata` and `load` artifacts.
- Deterministic branch in `src/robotina/queue/jobs.py:119-165` composes `AddRecipeOutcome` (success when `recipe_id` present, failure otherwise), writes `run.outcome = outcome.model_dump(mode="json")` (line 155) on the `WorkflowRun` row, then advances via `workflow_runner.on_step_complete`.
- Dashboard renders the compact cell in `src/robotina/dashboard/templates/workflow.html:23-34` — success path: `✓ {recipe_name} ({recipe_id})` plus `sin imagen` badge when `image_present` is False; failure path: `✗ Falló: {failure_reason}`. No raw JSON dump.
- `AddRecipeOutcome` model in `task_types.py:339` is the < 300 byte JSON envelope.

### MH5 — Wake invocation flows `WakeInvocationInput` to V004 agent (WAKE-03 / WAKE-04)

**Status:** VERIFIED

- `task_types.py:381-394` — `WakeInvocationInput` carries `previous_invocation_id`, `conversation_id`, `outcomes: list[WorkflowOutcomeSummary]`.
- `jobs.py:204-217`: `run_task` reads `invocation_id` from `job.meta`, loads the `RobotinaInvocation`, flips `PENDING → RUNNING` (with `started_at`), and commits. Terminal `DONE`/`FAILED` writes (with `completed_at`) happen in `_write_invocation_terminal_status` at the bottom (`jobs.py:372-385, 392-424`).
- `jobs.py:247-284`: `WORKFLOW_COMPLETION` branch resolves `Conversation` via `inv.conversation_id`, reads `HOUSEHOLD_ID` via bracket-key (fail loud), and wires the three tools with `chat_id` as the user_id placeholder (V004 instructs the agent NOT to call queue/start-workflow on wake turns).
- V004 prompt at `src/robotina/agent/prompts/robotina/V004.md` contains the "Wake context" section (line 34+) including the synthetic preamble pattern and the no-tool-call exception in the tool-call rule (line 29). Loaded by `agents.py:84`.

---

## Requirement Coverage

| Requirement | Status     | Evidence                                                                                                    |
| ----------- | ---------- | ----------------------------------------------------------------------------------------------------------- |
| WAKE-01     | SATISFIED  | `_check_and_dispatch_wake` + both call sites in `workflow_runner.py`; REQUIREMENTS.md line 20 `[x]`         |
| WAKE-02     | SATISFIED  | UPDATE-RETURNING guard, `workflow_runner.py:162-178`; REQUIREMENTS.md line 21 `[x]`                          |
| WAKE-03     | SATISFIED  | Pre-assigned `rq_job_id = str(uuid.uuid4())` at `workflow_runner.py:211`, threaded via `job_id=` at line 238 |
| WAKE-04     | SATISFIED  | `WakeInvocationInput`, `finalize-outcome` branch in `jobs.py`, V004 wake-context section                     |
| WAKE-05     | SATISFIED  | `reconcile_invocations` + boot wiring in `runner.py`                                                         |
| DASH-10     | SATISFIED  | `workflow.html` line 21-22 renders `Conversation` row with `run.conversation_id`                             |
| DASH-12     | SATISFIED  | `workflow.html` line 23-34 compact outcome cell                                                              |

All 7 IDs ticked `[x]` in REQUIREMENTS.md (lines 20-24, 72, 74). Status table lines 136-140, 166-168 all show "Complete".

---

## Phase-21 Boundary Check (these MUST NOT be present yet)

| Boundary item                                                       | Status | Evidence                                                                          |
| ------------------------------------------------------------------- | ------ | --------------------------------------------------------------------------------- |
| NO `RespondTool` / `TerminateTool` classes                          | OK     | `grep -rE 'RespondTool\|TerminateTool' src/` returns no class definitions          |
| Legacy `return_direct=True` shape on StartWorkflowTool retained     | OK     | `src/robotina/agent/tools/start_workflow.py` keeps `return_direct: bool = True`    |
| `acknowledge-add-recipe` agent + task + overrides still present     | OK     | Present in `agents.py`, `workflows.py`, `jobs.py`, and prompt directory             |
| `notify` step still in `add-recipe` workflow                        | OK     | `workflows.py:156-163` — `step_key="notify"` still present, finalize-outcome appended AFTER |
| Dead-letter `send-notification` still wrapped in try/except         | OK     | `workflow_runner.py:712-755` — gated on `wake_branch_ok`, not deleted              |

All boundaries respected — Phase 21 work has not bled into Phase 20.

---

## Anti-Patterns Scan

No stubs, TODOs, or hardcoded empties found in the modified files. The wake helper handles edge cases (None invocation_id, missing parent row, invalid outcome JSON) with explicit logging and early returns. The terminal-status writer is defensive ("never raises") to avoid masking real job exceptions.

The `try/except` around wake dispatch in `on_step_failed` is intentional: when wake fails (e.g., DB error), the rollback discards the FAILED status write, so the code re-marks FAILED in a fresh transaction (`workflow_runner.py:667-702`) before falling back to dead-letter notify. This is a documented design decision (Pitfall 2 + Phase 21 transition note), not an anti-pattern.

---

## Behavioral Spot-Checks

Skipped — verification environment cannot reach live Postgres (password auth errors expected per phase context). The 184 non-DB unit/queue/dashboard tests are reported green by the orchestrator. DB-bound tests (`tests/queue/test_wake_dispatch.py`, `tests/queue/test_reconcile.py`, `tests/dashboard/test_detail_view.py`) were green in executors' isolated worktrees; environment auth issues are NOT a code defect per the phase brief.

---

## Human Verification Required

### 1. Telegram round-trip smoke (deferred per 20-06)

**Test:** Send an `add-recipe` request through Telegram, wait for the full workflow to complete (acknowledge → research-gather → instructions → ingredients → metadata → load → notify → finalize-outcome), and verify:

- The `WorkflowRun.outcome` row is populated with a valid `AddRecipeOutcome` JSON.
- Exactly ONE new `RobotinaInvocation(trigger=workflow_completion)` row is created with `trigger_ref_id` matching the parent.
- The wake invocation's V004 agent run produces a reasonable assistant message (no tool call, per V004 rule).
- Dashboard detail view shows the Conversation row and compact outcome summary.

**Expected:** All four observations hold; no second wake row appears on retry from RQ failed registry.

**Why human:** Requires a live Telegram bot session, real Postgres + Redis, and visual confirmation of dashboard rendering. Manual smoke checkpoint was explicitly deferred in Plan 20-06 because the user was AFK.

---

## Summary

Phase 20 delivers exactly what its goal promised: when all sibling workflows on one invocation reach a terminal status, a single wake invocation is enqueued — guarded by an UPDATE-RETURNING atomic guard — carrying structured `AddRecipeOutcome` summaries to a V004 wake-aware Robotina turn, with a startup reconciler recovering crash-stranded rows. All 5 must-haves verify in code; all 7 requirement IDs are satisfied and ticked; the Phase 21 boundary is intact.

Status is `human_needed` (not `passed`) solely because the manual Telegram smoke checkpoint from Plan 20-06 was deferred. No code-level gaps were found.

---

_Verified: 2026-05-19_
_Verifier: Claude (gsd-verifier)_
