# Phase 20 Discussion Log

**Mode:** `--auto` (system reminder asked the discuss workflow to make reasonable
calls without stopping). No interactive AskUserQuestion turns were used; every
gray area below was resolved by Claude with rationale and is captured as a
D-NN decision in `20-CONTEXT.md`. The user can redirect any decision before
`/gsd:plan-phase 20` runs.

This log is for human reference only (audits, retrospectives) and is NOT
consumed by downstream agents.

---

## Prior Context Loaded

- `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md` (WAKE-01..05, DASH-10, DASH-12), `.planning/STATE.md`
- `.planning/ROADMAP.md` §"Phase 20: Wake rule + outcome plumbing"
- `.planning/phases/18-robotinainvocation-entity/18-CONTEXT.md` (the load-bearing prior phase)
- `.planning/phases/17-conversation-fk-closure/17-CONTEXT.md` (constructor-injection pattern source)
- `.planning/research/ARCHITECTURE.md` §§2.2, 2.3, 2.5, 2.8, 2.9, "Phase D"
- `.planning/research/PITFALLS.md` Pitfalls 1, 2, 11
- Source files: `workflow_runner.py`, `jobs.py`, `task_types.py`, `workflows.py`, `models.py`

Carried-forward decisions (NOT re-asked):
- `RobotinaInvocation` lives in `robotina.queue.models` (Phase 18 D-04)
- Full invocation schema already shipped: `wake_dispatched_at`, `rq_job_id`, `status`, `started_at`, `completed_at` (Phase 18 D-05)
- `InvocationTrigger` / `InvocationStatus` enums shipped with all values (Phase 18 D-06/D-07)
- `UniqueConstraint("trigger_ref_id", "trigger")` already exists — Phase 20 just exercises it (Phase 18 D-08)
- Constructor-injected `invocation_id` on `StartWorkflowTool` (Phase 18 D-13)
- `AddRecipeOutcome` Pydantic shape already defined (Phase 18 D-16/D-17/D-18)
- Constructor-injected `conversation_id`, `run_task` resolves runtime context (Phase 17 D-03/D-04/D-05)
- Dashboard module-isolation rule (Phase 13 D-01)

---

## Gray Areas Identified

Domain: Wire the wake-rule control loop and outcome plumbing on top of the
schema Phase 18 already shipped. Single household, single-worker, sequential
queue. The hard parts are idempotency under retry, transactional discipline,
and the Phase 20 / Phase 21 boundary (no `respond()` yet).

Gray areas (all resolved by Claude under auto-mode):

1. **`finalize-outcome` implementation shape** — agent-less task type vs inline workflow_runner special-case vs LLM agent. **→ D-01:** agent-less `run_task` branch (mirrors `send-notification`).
2. **`finalize-outcome` position in step list** — replace `notify` (architecture doc) vs append after `notify` (transitional). **→ D-02:** append after; Phase 21 will replace.
3. **`FinalizeOutcomeInput` shape** — dict-passthrough vs tight Pydantic model. **→ D-03:** tight model with `extra="forbid"`.
4. **`_check_and_dispatch_wake` function topology** — one helper vs two (one per terminal status). **→ D-04:** single helper, called from both `on_step_complete` and `on_step_failed`, same session.
5. **Dead-letter `send-notification` block behavior** — delete now vs keep as fallback vs always run. **→ D-05:** keep as fallback when wake-enqueue raises; Phase 21 deletes.
6. **`WakeInvocationInput` envelope** — `list[AddRecipeOutcome]` vs envelope-per-row. **→ D-06:** thin `WorkflowOutcomeSummary` envelope (carries workflow_run_id + workflow_type + status + outcome).
7. **`run_task` dispatch on wake** — branch on `task_type` (new task_type) vs branch on `invocation.trigger` (same task_type). **→ D-07:** branch on `invocation.trigger`, single `task_type='handle-incoming-message'` for both.
8. **`WakeInvocationInput` field set** — minimum vs maximum (include outcomes here vs fetch in agent). **→ D-08:** include outcomes in input (pre-computed by wake helper).
9. **Robotina prompt** — V003 reuse vs new V004 (no new tools land in Phase 20). **→ D-09:** V004 (adds wake-context section); without it the agent sees an unfamiliar input shape.
10. **`InvocationStatus` transition writer** — wake helper vs `run_task` vs both. **→ D-10:** `run_task` owns the lifecycle; wake helper only inserts PENDING.
11. **Reconciler module placement** — inside `workflow_runner.py` vs separate module. **→ D-11:** separate `src/robotina/queue/reconcile.py`; called at task-runner boot.
12. **DASH-10 placement** — list view vs detail view; column layout. **→ D-12:** detail view `kv-grid`, below `triggered_by_invocation_id`.
13. **DASH-12 outcome rendering** — raw JSON dump vs compact summary. **→ D-13:** compact summary with status icon + recipe name + image badge. Spanish.
14. **Dashboard task-type label** — name for `finalize-outcome`. **→ D-14:** "Cierre del flujo" or "Finalizando" (planner picks).
15. **New Alembic revision** — needed or not. **→ D-15:** no DDL strictly required; skip unless an index is added.
16. **REQUIREMENTS.md sync** — when to tick WAKE-* and DASH-10/12. **→ D-16:** same commit as the final implementation wave (mirrors Phase 18 D-25).
17. **Test scope** — unit + integration + dashboard + reconciler. **→ D-17..D-22:** itemized in CONTEXT.md.
18. **E2E live-LLM test in Phase 20** — included or deferred. **→ D-23:** deferred to Phase 21 (no `respond()` yet means the wake path can't produce a user-visible E2E observation in Phase 20).

---

## Scope Decisions (kept inside Phase 20)

- Wake-rule control loop: helper + idempotency guard + pre-assigned `rq_job_id` + reconciler.
- Outcome plumbing: `finalize-outcome` task type + `AddRecipeOutcome` writes + dashboard rendering.
- `run_task` dispatch on `invocation.trigger`; status transitions on `RobotinaInvocation`.
- V004 prompt with wake-context interpretation (no new tools).
- All seven requirements: WAKE-01..05, DASH-10, DASH-12.

---

## Deferred to Other Phases

Captured in CONTEXT.md `<deferred>` section. Highlights:

- **Phase 21:** `RespondTool`, `TerminateTool`, multi-call `StartWorkflowTool`, removing `acknowledge-add-recipe`, removing `notify` step, removing dead-letter block.
- **Phase 22:** Multi-recipe LLM behavior (BATCH-*).
- **Phase 23:** URL ingestion (URL-*).
- **Phase 24:** `recipe-image` step (IMG-*); `image_present=True` path.
- **Backlog:** WorkflowRunStep orphan reconciliation; dedicated `RobotinaInvocation` dashboard view (DASH-13); `WorkflowOutcome` envelope generalization across workflow types.

---

## Claude's Discretion (auto-mode calls flagged for user review)

The decisions most likely to warrant user review before `/gsd:plan-phase 20`:

- **D-02 — Append `finalize-outcome` AFTER `notify` (not replace).** This is the deliberate Phase 20 / Phase 21 seam. If the user prefers a single-phase flip (delete `notify` AND wire `respond()` in one milestone), that pivots Phase 20 ↔ Phase 21 scope significantly.
- **D-05 — Keep the dead-letter `send-notification` block as a fallback.** The architecture doc explicitly recommends this, but it's a soft call. Removing it now means the only safety net for wake-enqueue failure is the reconciler-on-next-boot path. The dead-letter gives an immediate user-visible apology; reconciler gives an eventual recovery.
- **D-06 — `WorkflowOutcomeSummary` envelope vs reusing `AddRecipeOutcome` directly.** The envelope is the minimum needed (workflow_run_id + status). The user might prefer to just pass `list[AddRecipeOutcome]` and reconstruct context from `WorkflowRun` lookups in the agent. The envelope is forward-compatible with Phase 23 URL workflows (same shape, different `workflow_type`).
- **D-09 — Bump prompt to V004 in Phase 20.** Alternative: V003 stays through Phase 20, V004 lands in Phase 21 alongside the new tools. Picking V004 now means V004 owns both user-message and wake interpretation for the entire Phase 20 → Phase 21 transition (cleaner mental model); deferring means Phase 20's wake-context turn runs against a prompt that doesn't know about the wake input shape (fragile).
- **D-11 — Reconciler runs at task-runner boot, before `worker.work()`.** Alternative: as a periodic RQ scheduled task. Boot-only is simpler and matches the failure mode (worker-crash recovery on next start). If the worker is long-lived without restarts, a stuck wake invocation could linger; a periodic check would catch it.
- **D-23 — No E2E live-LLM test in Phase 20.** The wake path is end-to-end-exercisable in Phase 20 (invocation enqueues, agent runs, V004 prompt sees wake context) but the agent can't speak to the user. Integration tests + a manual smoke step cover the wake-enqueue + outcome population; the user-facing wake reply test waits for Phase 21.

---

*All decisions are recorded in `20-CONTEXT.md`. This log is the rationale + open-loops record; the CONTEXT.md is what downstream agents consume.*
