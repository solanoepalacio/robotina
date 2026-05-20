# Phase 20: Wake rule + outcome plumbing - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning
**Mode:** `--auto` (system reminder asked the discuss workflow to make reasonable
calls without stopping; every D-NN below is Claude's call with rationale — the
user can redirect any decision before `/gsd:plan-phase 20` runs.)

<domain>
## Phase Boundary

Wire the wake-rule control loop on top of the schema Phase 18 already shipped.
When all `WorkflowRun` rows sharing a `triggered_by_invocation_id` reach
terminal status (`done` OR `failed`), enqueue **exactly one** follow-up
`RobotinaInvocation(trigger=workflow_completion)` row whose `trigger_ref_id` is
the parent invocation's id, with structured `WorkflowRun.outcome` JSON the next
Robotina turn can consume. Add a startup reconciler that recovers wake
invocations stranded by worker-crash between commit and RQ enqueue. Surface the
new columns on the dashboard.

**This phase does not flip the tool surface** (no `RespondTool`,
`TerminateTool`, multi-call `StartWorkflowTool`, no `acknowledge-add-recipe`
deletion, no `notify` removal). That is Phase 21. Phase 20 keeps the legacy
`notify` step in place as the user-facing reply channel; Robotina's
wake-context turn is observable in logs / dashboard / LangWatch traces but does
not yet `respond()` to the user. The wake path is exercised end-to-end; Phase
21 then deletes `notify` and lets Robotina speak.

**In scope:**

- **Migration** `0008_wake_rule_dashboard.py`:
  - Add nullable `WorkflowRunStep` reconciler-touchable columns if needed (none anticipated; reconciler operates on `RobotinaInvocation` only — see D-13).
  - No schema changes to `robotina_invocations` (Phase 18 D-05 shipped the full schema). The Alembic revision exists purely so future Phase 20 fixups (e.g. an index) have a stable head; if no DDL is needed it's a no-op revision with `revision="0008"`, `down_revision="0007"`, empty upgrade/downgrade. **Planner decides whether the file lands — drop it if truly empty.**
- **`finalize-outcome` task type** (agent-less, deterministic — D-01):
  - New `task_type="finalize-outcome"` registered in `WORKFLOW_TASK_TYPES`. No agent registry entry. `run_task` gains a branch alongside `send-notification` (jobs.py line 90 pattern) that reads accumulated artifacts via the workflow runner's `StepInput` plumbing, composes an `AddRecipeOutcome` (the model Phase 18 already defined in `queue/task_types.py`), writes it to `WorkflowRun.outcome`, and returns.
  - Inserted as the LAST step of `add-recipe` in `workflows.py` (after `notify`, not replacing it — D-02). `notify` stays so users keep getting the existing reply during the transition.
- **`_check_and_dispatch_wake(invocation_id, session, queue)` helper** in `workflow_runner.py` (D-03):
  - Counts all `WorkflowRun` rows where `triggered_by_invocation_id = inv.id`. If `count(status IN ('done','failed')) == count(*)` AND `count(*) > 0`, attempt wake.
  - Idempotency guard: `UPDATE robotina_invocations SET wake_dispatched_at = NOW() WHERE id = :parent_inv_id AND wake_dispatched_at IS NULL RETURNING id`. If 0 rows affected, return — wake already fired.
  - If 1 row affected: pre-assign `rq_job_id = str(uuid4())` on a new `RobotinaInvocation(trigger=WORKFLOW_COMPLETION, trigger_ref_id=parent_inv.id, conversation_id=parent_inv.conversation_id, rq_job_id=<pre>, status=PENDING)`; flush; commit the outer transaction; then `queue.enqueue(run_task, wake_input, job_id=<pre>, meta={'task_type': 'handle-incoming-message', 'invocation_id': new_inv.id}, result_ttl=-1, failure_ttl=-1)`.
- **Wake-check call sites** in `workflow_runner.py`:
  - `on_step_complete`'s final-step DONE branch (currently line 393-401): after `run.status = WorkflowStatus.DONE` and BEFORE the existing `session.commit()`, call `_check_and_dispatch_wake(run.triggered_by_invocation_id, session, queue)`. The helper performs the UPDATE-RETURNING + insert + flush INSIDE the same session, then the outer `session.commit()` flushes both the WorkflowRun status flip AND the new invocation atomically (Pitfall 2 — same transaction).
  - `on_step_failed`'s FAILED branch (currently around line 495 after `run.status = WorkflowStatus.FAILED`): same call, same transactional discipline. The existing dead-letter `send-notification` block stays as a fallback (D-04).
- **`WakeInvocationInput` Pydantic model** in `queue/task_types.py` (D-05):
  - Fields: `previous_invocation_id: str`, `conversation_id: str`, `outcomes: list[WorkflowOutcomeSummary]`. The `WorkflowOutcomeSummary` is a thin envelope (D-06).
- **`run_task` dispatch on `invocation.trigger`** in `queue/jobs.py` (D-07):
  - The `handle-incoming-message` branch (currently line 134) reads `job.meta['invocation_id']`, opens a session, SELECTs the `RobotinaInvocation`, and branches:
    - `trigger == USER_MESSAGE` → existing path. `task_input` is `IncomingMessageInput` (already validated upstream). No change to today's behavior.
    - `trigger == WORKFLOW_COMPLETION` → wake path. `task_input` is `WakeInvocationInput`. The agent receives a wake-context `to_user_message()` rendering — a structured Spanish prompt prefix listing outcomes (per V004 — see D-09).
  - `task_type` stays `"handle-incoming-message"` for both. Differentiation is on `invocation.trigger`, not `task_type`. This keeps the queue routing logic stable (one job key) while still letting the agent see different inputs.
- **Robotina prompt update** (`src/robotina/agent/prompts/robotina/`, D-09):
  - Bump to `V004.md`. Teach the wake path: when the agent is invoked with a "wake context" preamble listing workflow outcomes, it composes a thinking-out-loud reflection in the log (this phase) and **does NOT yet call `respond()` to the user** (no `RespondTool` until Phase 21). Phase 20's V004 still uses the existing `StartWorkflowTool`/`QueueTool` surface — same tools as V003 — but adds the wake-context interpretation rule.
  - V003 remains the active prompt for user-message turns until V004 lands; once V004 lands, it serves BOTH user-message and wake invocations. Single prompt, two contexts.
- **Status transitions** for `RobotinaInvocation` (D-10):
  - `PENDING` (gateway insert / wake-enqueue) → `RUNNING` (run_task entry, set `started_at = NOW()`) → `DONE` (run_task happy path return, set `completed_at = NOW()`) | `FAILED` (run_task exception path, set `completed_at = NOW()`).
  - Status writes happen in `run_task` itself, inside the same session that processes the job. No separate helper. Mirror the existing WorkflowRunStep status-flip pattern in `on_step_*`.
- **Startup reconciler** (D-11) in `src/robotina/cli/reconcile.py` or as a startup hook on the task-runner entrypoint (planner picks placement):
  - SELECT `RobotinaInvocation` rows WHERE `status = 'pending'` AND `wake_dispatched_at IS NOT NULL` AND `rq_job_id IS NOT NULL`. For each: `Job.exists(rq_job_id, connection=redis)` (RQ API). If False: re-enqueue with the same `job_id` (RQ deduplicates on `job_id`, so a second enqueue is safe even on the boundary case where the original DID enqueue but the reconciler ran first).
  - Run at task-runner boot, before the worker drains the queue. Logged result.
  - **Out of scope for the reconciler:** WorkflowRunStep orphans (`task_job_id IS NOT NULL` but no RQ job). PITFALL 11 flagged this as a "freebie" but it's a separate concern with its own surface (need to know which artifacts are accumulated for the orphan step, etc.). Deferred to a backlog phase.
- **Dashboard surfacing**:
  - **DASH-10:** add `conversation_id` to the `kv-grid` on `workflow.html` detail view as a new `<dt>/<dd>` pair below the `triggered_by_invocation_id` row Phase 18 added. Mono short UUID + full UUID. "—" only if NULL (it should never be NULL for new rows since Phase 17 made it NOT NULL).
  - **DASH-12:** add an `outcome` summary cell on the detail view rendering the `AddRecipeOutcome` JSON in a compact human-readable shape: `"✓ Canelones de choclo (recipe-id abc123)"` on success, `"✗ Falló: insufficient gather data"` on failure, "—" when NULL. NOT the raw JSON dump.
  - No JOIN to `RobotinaInvocation` rows (already done by Phase 18 — `triggered_by_invocation_id` shown raw). No dedicated invocation list/detail view (DASH-13 "nice-to-have" deferred to backlog).
  - Update the dashboard task-type label map to include `"finalize-outcome"` with a Spanish label (e.g. "Cierre del flujo" / "Finalizando"). Existing labels untouched.
- **Tests**:
  - `tests/queue/test_workflow_runner.py` — `_check_and_dispatch_wake` unit tests: happy-path single-workflow invocation, multi-workflow (3 done = wake), partial (2 done 1 pending = no wake), failed-workflow → wake fires, idempotency (call twice → only one new invocation), pre-assigned `rq_job_id` matches the enqueued job.
  - `tests/queue/test_workflow_runner.py` integration test (`@pytest.mark.integration`, real Postgres + fake Redis): full `on_step_complete` → wake-enqueue sequence with all DB state flushed; assert `wake_dispatched_at` and `rq_job_id` are set on the parent invocation, new invocation row exists with the right `trigger_ref_id`.
  - `tests/queue/test_jobs.py` — `run_task` branches on `invocation.trigger`: USER_MESSAGE path identical to today; WORKFLOW_COMPLETION path constructs the agent with `WakeInvocationInput` and the wake-context user message.
  - `tests/queue/test_finalize_outcome.py` (new) — `finalize-outcome` task: given artifacts dict, composes the right `AddRecipeOutcome`, writes to `WorkflowRun.outcome`. Success and failure shapes.
  - `tests/cli/test_reconcile.py` (new) — reconciler: orphan invocation re-enqueued; non-orphan untouched; happy-path no-op.
  - `tests/dashboard/test_workflow_template.py` — assert new `conversation_id` row renders, assert outcome summary renders for success/failure/null.
  - Module-isolation grep gate (Phase 13 D-01) still passes.
- **REQUIREMENTS.md edits**: tick WAKE-01..05, DASH-10, DASH-12 in same commit as the implementation lands (planner decides which commit; mirror Phase 18 D-25).

**Out of scope (deferred to later phases):**
- `RespondTool`, `TerminateTool`, multi-call `StartWorkflowTool` (`return_direct=False`) — **Phase 21**.
- Removing `acknowledge-add-recipe` agent / step / overrides / dashboard label — **Phase 21**.
- Removing `notify` step from `add-recipe` workflow — **Phase 21** (Phase 20 keeps it as the user-facing reply).
- Removing the dead-letter `send-notification` block from `on_step_failed` — **Phase 21**, only after Phase 20's wake path is verified end-to-end. Kept as fallback in Phase 20 (D-04).
- Robotina actually calling `respond()` on wake — Phase 21. Phase 20's V004 only adds wake-context interpretation; no new user-facing tool calls.
- Multi-recipe per-message dispatch (BATCH-*) — Phase 22.
- URL ingestion + `safe_fetch` (URL-*) — Phase 23.
- `recipe-image` step (IMG-*) — Phase 24.
- WorkflowRunStep orphan reconciliation — backlog (PITFALL 11 "freebie" deferred to keep Phase 20 focused).
- Dedicated `RobotinaInvocation` list/detail dashboard view (DASH-13 "nice-to-have") — backlog.
- `WorkflowOutcome` envelope generalization across multiple workflow types — defer until ≥2 workflow types with distinct outcome shapes exist (Phase 23+ at the earliest).

</domain>

<decisions>
## Implementation Decisions

> **Auto-mode note:** Every D-NN below is Claude's call under the no-stopping
> system reminder. Rationale is included so the user can spot a wrong turn.
> The user can redirect any decision before `/gsd:plan-phase 20` runs.

### `finalize-outcome` shape

- **D-01:** **`finalize-outcome` is an agent-less task type with a dedicated `run_task` branch — option (B) from ARCHITECTURE §2.2.** Not an inline `workflow_runner` special-case, not an LLM agent.
  - **Why:** Mirrors the existing `send-notification` deterministic branch (jobs.py line 90) — a pattern that already works, is testable in isolation, and surfaces in the dashboard like any other step. An inline `workflow_runner` special-case would hide the step from the dashboard's step-list view (DASH consumers expect every step to be a row). An LLM agent here is pure overhead — composing `AddRecipeOutcome` from accumulated artifacts is deterministic Python.
  - **Concretely:** `WorkflowStepDef(step_key="finalize-outcome", task_type="finalize-outcome", build_input=lambda ctx, artifacts: FinalizeOutcomeInput(metadata=artifacts["metadata"], load=artifacts.get("load")))`. The branch in `run_task` reads the input, composes `AddRecipeOutcome`, opens a session, writes `run.outcome = outcome.model_dump()`, commits, returns. No re-enqueue, no chain advancement work — `on_step_complete` handles step transitions as usual.

- **D-02:** **`finalize-outcome` is appended AFTER `notify`, not in place of it.** v1.1 add-recipe step list in Phase 20:
  ```
  acknowledge → gather → instructions → ingredients → metadata → load → notify → finalize-outcome
  ```
  - **Why:** ROADMAP success-criterion #4 requires every terminal workflow to have a non-null `outcome`. If `finalize-outcome` replaced `notify`, the user wouldn't get the legacy reply during the transition (Phase 21 hasn't shipped `respond()` yet) — that's a user-visible regression. Appending instead keeps the user reply path intact AND populates `outcome`. Phase 21 will both drop `notify` and possibly reorder `finalize-outcome` earlier (e.g. before the now-deleted `notify`) — that's a Phase 21 call.
  - **`finalize-outcome` is now the FINAL step**, so it's the one whose `on_step_complete` hits the "Final step — mark WorkflowRun DONE" branch and triggers the wake check. The `notify` step becoming non-terminal (it now has a successor) is a free behavioral consequence — no behavioral change to the user (they still get the same notification at the same point in the chain).

- **D-03:** **`FinalizeOutcomeInput` is a tight Pydantic model**, not just `dict`. Shape:
  ```python
  class FinalizeOutcomeInput(BaseModel):
      model_config = ConfigDict(extra="forbid")
      # Artifacts the deterministic composer needs:
      metadata: dict | None = None        # from "metadata" step artifact
      load: dict | None = None            # from "load" step artifact
      failure_reason: str | None = None   # only present when called on a failed workflow (future Phase 21 path)
  ```
  - The `build_input` lambda passes `artifacts.get("metadata")` / `artifacts.get("load")` — both are dicts from the existing artifact-accumulation contract. Validator-side, the composer in `run_task` builds the `AddRecipeOutcome`:
    - If `load.recipe_id` exists → `status="success"`, `recipe_id`, `recipe_name`, `recipe_slug` from `metadata`/`load`, `image_present=False` (Phase 24 fills the True case).
    - Otherwise → `status="failure"`, `failure_reason="finalize-outcome called without a load artifact"` (which means the workflow advanced past `load` somehow — shouldn't happen on the success path).
  - **Note:** Phase 20 does NOT instantiate `finalize-outcome` on a FAILED workflow. The wake-check fires whether the workflow ends DONE or FAILED, but `finalize-outcome` only runs on DONE workflows (it's a step in the chain; cancelled steps don't run). For FAILED workflows the wake fires with `WorkflowRun.outcome = NULL`, and the wake-context summary represents the failure via the WorkflowRun's `status='failed'` flag, not via `outcome`. The `WorkflowOutcomeSummary` envelope (D-06) handles both cases.

### Wake helper architecture

- **D-04:** **`_check_and_dispatch_wake(invocation_id: str, session: Session, queue: Queue) -> None`** is the single helper. Called from BOTH `on_step_complete` (final-step DONE) AND `on_step_failed` (any-step FAILED, which terminates the workflow). Same function, same logic, called from two sites — per PITFALL 1: "Make `on_step_complete` and `on_step_failed` both call the same `_check_and_dispatch_wake(invocation_id, session)` helper. Currently `on_step_complete` only marks RUN done; `on_step_failed` only marks RUN failed. Both terminal transitions need the wake check, and the helper has to be ONE function so the guard is one place."
  - **Same session:** the helper receives the caller's session, runs its UPDATE-RETURNING + insert + flush inside that session. The caller does the final `session.commit()`. PITFALL 2: "Commit ONCE at the end of `on_step_complete` / `on_step_failed`, AFTER both the status write and the wake check + invocation enqueue." Helper MUST NOT call `session.commit()` itself.
  - **Queue is optional** (callers can pass `queue=None`). On `queue=None`, the helper STILL performs the UPDATE-RETURNING + insert + flush in the DB, but skips the actual `queue.enqueue(...)` call. The reconciler picks up the orphan on next startup. Same shape as the existing dead-letter block's `if queue:` guard. This keeps the helper testable without a Redis dependency.

- **D-05:** **Dead-letter `send-notification` block in `on_step_failed` STAYS as a fallback.** Gated on "wake-enqueue raised an exception." Concretely:
  ```python
  try:
      _check_and_dispatch_wake(run.triggered_by_invocation_id, session, queue)
  except Exception as wake_err:
      logger.exception("wake dispatch failed; falling back to dead-letter notify | run_id=%s", run.id)
      # existing dead-letter block (lines 507-533)
  else:
      # existing dead-letter block is SKIPPED — Robotina will speak on wake
      pass
  ```
  - **Why:** ARCHITECTURE §2.2 explicitly mitigates "removing the dead-letter `send-notification` from `on_step_failed` leaves silent failures if wake-enqueue itself fails" with "Keep the dead-letter block as fallback iff wake-enqueue raises." Phase 21 will remove the dead-letter block entirely (and the legacy `notify` step) once Robotina's `respond()` path is verified.
  - **Side effect:** during Phase 20, on a healthy wake-enqueue path, the user gets the existing `notify` reply (from the legacy step that still runs) AND eventually a Robotina turn (silent in Phase 20 since no `respond()`). No double-notification. The dead-letter only fires when wake-enqueue itself raises — a rare path.

- **D-06:** **`WorkflowOutcomeSummary` envelope around `AddRecipeOutcome`** for the wake-input payload:
  ```python
  class WorkflowOutcomeSummary(BaseModel):
      model_config = ConfigDict(extra="forbid")
      workflow_run_id: str
      workflow_type: str           # "add-recipe" in v1.1; extends naturally
      status: Literal["done", "failed"]   # from WorkflowRun.status
      outcome: AddRecipeOutcome | None = None  # populated for DONE workflows; None for FAILED (no finalize-outcome ran)
  ```
  - **Why not just `list[AddRecipeOutcome]`:** ROADMAP success-criterion #5 says "The wake agent receives a `WakeInvocationInput` with the previous invocation id and list of `WorkflowOutcome` summaries." The wake agent needs to know which workflow succeeded vs failed, and the `workflow_run_id` to reference. `AddRecipeOutcome` alone doesn't carry that — it only knows about a recipe. The thin envelope per workflow row keeps `AddRecipeOutcome` focused on the recipe payload.
  - **Why not introduce the full generalized envelope yet:** Phase 18 D-18 deferred the generalized `WorkflowOutcome` wrapper "until ≥2 workflow types with distinct outcome shapes exist." `WorkflowOutcomeSummary` is intentionally minimal — it's a wake-input concern, not a general workflow-outcome architecture. Phase 23 (URL ingestion) is expected to reuse `AddRecipeOutcome` directly (recipe outcomes regardless of source), so the trigger for a real generalized envelope is later.

### `run_task` dispatch

- **D-07:** **`run_task` reads `RobotinaInvocation` from DB on entry, branches on `trigger`.** Both USER_MESSAGE and WORKFLOW_COMPLETION jobs share `task_type='handle-incoming-message'` in `meta`; differentiation is on `invocation.trigger`.
  - **Concrete shape** (around `jobs.py` line 134):
    ```python
    if task_type == "handle-incoming-message":
        invocation_id = job.meta["invocation_id"]
        with SessionLocal() as session:
            inv = session.get(RobotinaInvocation, invocation_id)
            if inv is None:
                raise RuntimeError(f"RobotinaInvocation {invocation_id} not found")
            # Status transition: PENDING → RUNNING
            inv.status = InvocationStatus.RUNNING
            inv.started_at = datetime.utcnow()
            session.commit()
            try:
                if inv.trigger == InvocationTrigger.USER_MESSAGE:
                    # Existing path — task_input is IncomingMessageInput
                    result = _run_user_message_turn(inv, task_input, session)
                elif inv.trigger == InvocationTrigger.WORKFLOW_COMPLETION:
                    # Wake path — task_input is WakeInvocationInput
                    result = _run_wake_turn(inv, task_input, session)
                else:
                    raise RuntimeError(f"unsupported trigger {inv.trigger}")
                inv.status = InvocationStatus.DONE
            except Exception:
                inv.status = InvocationStatus.FAILED
                raise
            finally:
                inv.completed_at = datetime.utcnow()
                session.commit()
            return result
    ```
  - **Why not branch on `task_type`:** Adding a new `task_type='wake-robotina'` would mean a second branch in `run_task` that's 90% identical to `handle-incoming-message`. The agent setup is the same; only the input shape and the prompt context differ. Branching on `invocation.trigger` keeps the queue routing logic stable and the differentiation localized.
  - **Why read from DB, not pass `trigger` in `meta`:** the invocation row is the source of truth. The `meta` channel is for routing concerns (`task_type`, `invocation_id`); pulling business state (trigger type) from there would put it in two places. Single source = the row. The SELECT is cheap (PK lookup) and gives the helper access to `conversation_id` and other fields the wake-context preamble needs.

- **D-08:** **`WakeInvocationInput` shape:**
  ```python
  class WakeInvocationInput(BaseModel):
      model_config = ConfigDict(extra="forbid")
      previous_invocation_id: str           # parent invocation that closed
      conversation_id: str                  # for history fetch
      outcomes: list[WorkflowOutcomeSummary]  # one per WorkflowRun
  ```
  - The gateway/wake-enqueue site populates `outcomes` by SELECTing every WorkflowRun with `triggered_by_invocation_id = parent.id`, joining each row's `outcome` JSON column, and building one `WorkflowOutcomeSummary` per row. This happens inside `_check_and_dispatch_wake`, BEFORE the actual `queue.enqueue(...)` — the input is built once and passed to the queue.
  - The `IncomingMessageInput` discriminator on the queue: `run_task` receives `task_input` as the result of `task_input = type_adapter.validate_python(...)` per the existing pattern. We add `WakeInvocationInput` to the discriminator union. The validator picks the right shape based on its fields.

### Prompt + agent surface

- **D-09:** **V004 prompt is added; V003 stays the previous version for rollback.** V004 teaches the wake path WITHOUT introducing new tools.
  - **Prompt structure:** V004 is V003 + a new section "When invoked with a wake context" that describes the `outcomes` block in the user-message payload and how the agent should interpret it. **Phase 20's V004 instructs the agent: "when invoked with a wake context, you may compose a thinking-out-loud reflection (visible in logs and LangWatch traces) but you cannot yet send the user a follow-up reply — that capability arrives in the next milestone phase. Use this opportunity to verify the outcomes look right; the user already received the notify message."** This is intentional Phase 20 / Phase 21 boundary discipline.
  - **`to_user_message()`:** the wake path renders `WakeInvocationInput` to a synthetic user message: "Los siguientes flujos terminaron: [list with status and outcome summaries]. (Wake-trigger; el usuario ya fue notificado.)" — Spanish, since the user-facing context is Spanish (per memory `feedback_prompts_language.md`), even though Phase 20 doesn't actually send a user reply. This keeps the rendering consistent for Phase 21 where the agent WILL reply.
  - **Why update the prompt at all if no new tools land in Phase 20:** ROADMAP success-criterion #5 says the wake agent "receives a `WakeInvocationInput` with the previous invocation id and list of `WorkflowOutcome` summaries." Receiving it without an updated prompt means the agent sees an unfamiliar input shape and behaves unpredictably. The prompt update is what makes the wake input safe to ship. The `respond()` tool flip is Phase 21.

- **D-10:** **`InvocationStatus` transitions happen in `run_task`, NOT in the wake helper.** The wake helper only inserts new invocations with `status=PENDING`. The lifecycle (`PENDING → RUNNING → DONE | FAILED`) is owned by `run_task` (per D-07 code shape). Mirrors WorkflowRunStep status management in `on_step_complete` / `on_step_failed` — same architectural pattern.
  - On `started_at` / `completed_at`: same `datetime.utcnow()` pattern as existing models. `started_at` set on PENDING → RUNNING transition; `completed_at` set on RUNNING → DONE/FAILED transition. Both timestamps written in the `run_task` body, not in the wake helper.

### Reconciler

- **D-11:** **Startup reconciler is a separate module `src/robotina/queue/reconcile.py`** with a `reconcile_invocations(session, queue)` function. Called from the task-runner entrypoint (`src/robotina/task_runner.py` — the `agent` script in `pyproject.toml`) BEFORE the worker starts draining the queue.
  - **Why a separate module:** keeps `workflow_runner.py` focused on the live wake path. The reconciler is a startup concern, not a step-completion concern. Different lifecycle, different consumers.
  - **Why not in the gateway:** the gateway might restart while the task-runner is still up. The orphan happens on TASK-RUNNER crash, so the TASK-RUNNER is the right place to reconcile on startup.
  - **Query shape:**
    ```sql
    SELECT id, rq_job_id FROM robotina_invocations
    WHERE status = 'pending'
      AND wake_dispatched_at IS NOT NULL
      AND rq_job_id IS NOT NULL
    ```
  - **Action per row:**
    - `if not Job.exists(rq_job_id, connection=redis):` re-enqueue with `job_id=rq_job_id` (RQ deduplicates on job_id so a race-win re-enqueue is safe).
    - Log result. No DB writes (the row already has the right state; we just bring RQ in line).
  - **What's intentionally NOT reconciled:**
    - `RobotinaInvocation` rows where `wake_dispatched_at IS NULL` and `status='pending'` — these are USER_MESSAGE invocations that the gateway enqueued but never got picked up. Surfaced by RQ's normal queue, no DB-side reconciliation needed.
    - WorkflowRunStep orphans — out of scope (see <domain>).

### Dashboard

- **D-12:** **`conversation_id` row (DASH-10) goes BELOW `triggered_by_invocation_id` in the existing `kv-grid`** in `src/robotina/dashboard/templates/workflow.html`. Concrete diff:
  ```jinja
  <dt>Triggered by invocation</dt>
  <dd class="mono">{{ run.triggered_by_invocation_id or "—" }}</dd>
  <dt>Conversation</dt>
  <dd class="mono">{{ run.conversation_id or "—" }}</dd>
  ```
  No JOIN to the Conversation table for now (the `chat_id` / `platform` are already implicit on the parent workflow context and can be added in a follow-up if needed).

- **D-13:** **`outcome` summary cell (DASH-12)** rendered via a small Jinja helper or template macro that consumes `AddRecipeOutcome`:
  ```jinja
  <dt>Outcome</dt>
  <dd>
    {% if run.outcome %}
      {% if run.outcome.status == "success" %}
        ✓ {{ run.outcome.recipe_name }}
        <span class="mono small">({{ run.outcome.recipe_id }})</span>
        {% if not run.outcome.image_present %} <span class="badge">sin imagen</span>{% endif %}
      {% else %}
        ✗ Falló: {{ run.outcome.failure_reason or "(sin detalle)" }}
      {% endif %}
    {% else %}—{% endif %}
  </dd>
  ```
  - The `run.outcome` field is the dict deserialized from `WorkflowRun.outcome` (JSON column). The template handles the dict directly — no Pydantic deserialization on the template side. The values are spotting-friendly Spanish (per project convention).
  - **No list-view changes.** DASH-12 only requires the detail view to render the outcome; the list view stays as-is for now.

- **D-14:** **`finalize-outcome` Spanish task-type label** added to the dashboard's task-type label map (single dict, planner finds it). Suggested: `"finalize-outcome": "Cierre del flujo"` or `"finalize-outcome": "Finalizando"`. Planner picks the better Spanish phrasing; not a load-bearing choice.

### Migrations + REQUIREMENTS sync

- **D-15:** **No new Alembic revision is strictly required** for Phase 20 — Phase 18 D-05 already shipped the full schema. If the planner / executor decides an index is needed (e.g. on `RobotinaInvocation.triggered_by_invocation_id` for the wake-check count query), add it as `0008_wake_indexes.py`. Otherwise no revision file lands.
  - **Wake-check index decision:** the count query `SELECT count(*) ... WHERE triggered_by_invocation_id = :id` runs once per terminal-step transition. v1.1 is a single household, low volume; an unindexed scan on `workflow_runs` is fine for now. Phase 23+ might warrant an index if multi-recipe batches make the table grow. Planner discretion.

- **D-16:** **REQUIREMENTS.md WAKE-01..05, DASH-10, DASH-12 tick-edits go in the same commit as the implementation lands.** Per Phase 18 D-25 / Phase 17 D-01 pattern. Planner includes them in the final wave's commit (likely the dashboard wave).

### Test strategy (Claude's Discretion)

- **D-17:** **Wake helper unit tests cover:**
  - Single-workflow happy path: 1 WorkflowRun DONE → wake fires, parent has `wake_dispatched_at`, new invocation has `trigger_ref_id=parent.id`.
  - Multi-workflow all-done: 3 WorkflowRuns DONE → wake fires once.
  - Multi-workflow partial: 2 DONE + 1 PENDING → no wake.
  - Failed terminal: 1 WorkflowRun FAILED → wake fires.
  - Idempotency: call helper twice with same state → second call returns without inserting. Assert via `count(*) FROM robotina_invocations WHERE trigger='workflow_completion' AND trigger_ref_id=:parent.id` is 1.
  - Pre-assigned `rq_job_id`: assert the row's `rq_job_id` matches the enqueued job's id.
  - `queue=None` skip: helper still UPDATEs `wake_dispatched_at` and inserts the row, just doesn't enqueue. Reconciler picks it up.

- **D-18:** **Integration test (`@pytest.mark.integration`, real Postgres):**
  - Full `on_step_complete` → wake-enqueue sequence. Insert parent invocation, insert a single WorkflowRun, transition through PENDING → RUNNING → DONE via the workflow_runner step-completion path (with a mocked `finalize-outcome` task that just writes a stub outcome). Assert at the end: parent `wake_dispatched_at` is set; child invocation row exists with `trigger=WORKFLOW_COMPLETION`, `trigger_ref_id=parent.id`, `status=PENDING`, `rq_job_id` set. The wake-enqueue side (RQ) is mocked / fake-Redis so we observe `enqueue` was called with the pre-assigned job_id.

- **D-19:** **`run_task` branch tests** cover both trigger paths and the status transition pattern (PENDING → RUNNING on entry; DONE on happy return; FAILED on exception). One test per branch. Assert `inv.started_at` and `inv.completed_at` are written. Mock the actual agent invocation (don't run an LLM).

- **D-20:** **`finalize-outcome` task test:**
  - Given a load artifact dict with `recipe_id="abc"`, `recipe_name="Lentejas"`, `recipe_slug="lentejas"`: expect `AddRecipeOutcome(status="success", recipe_id="abc", recipe_name="Lentejas", recipe_slug="lentejas", image_present=False)`.
  - Given no load artifact: expect `AddRecipeOutcome(status="failure", failure_reason="...")`.
  - Writes the outcome to `WorkflowRun.outcome`, asserts the DB row roundtrip.

- **D-21:** **Reconciler test:** orphan invocation (status PENDING + wake_dispatched_at set + rq_job_id set, no RQ job) → reconcile re-enqueues with same job_id. Non-orphan (RQ job exists) → no-op. Healthy state (no orphans) → no-op.

- **D-22:** **Dashboard template tests:**
  - Render `workflow.html` with a WorkflowRun whose `conversation_id` is set → asserts `<dt>Conversation</dt>` is present, `<dd>{conv_id}</dd>` is present.
  - Render with `outcome={"status": "success", "recipe_name": "Lentejas", "recipe_id": "abc", "image_present": False}` → asserts `✓ Lentejas` appears and the `sin imagen` badge appears.
  - Render with `outcome={"status": "failure", "failure_reason": "no gather artifact"}` → asserts `✗ Falló: no gather artifact`.
  - Render with `outcome=None` → asserts `—` placeholder.
  - Module-isolation grep gate (`tests/dashboard/test_independence.py`) still passes.

- **D-23:** **NO end-to-end live LLM test in Phase 20** — the wake-path agent invocation needs the `notify` step to stay intact (no `respond()` yet) for the user to actually see a reply. An E2E test for the wake reply is Phase 21's concern. Phase 20's E2E confidence comes from: (a) the integration test that asserts the wake-enqueue happens on terminal status, (b) manual smoke tests during the dashboard wave that confirm the new columns render and the wake-triggered run appears in the dashboard run list (per memory `feedback_test_before_handoff.md`).

### Claude's Discretion

- **`_check_and_dispatch_wake` placement:** in `src/robotina/queue/workflow_runner.py` as a private helper (`_check_and_dispatch_wake`). Same module as the call sites; mirrors `_build_send_notification_input` placement.
- **`finalize-outcome` task type registration:** in `src/robotina/agent/workflows.py::WORKFLOW_TASK_TYPES` (or whichever registry exists for agentless tasks; planner finds the right spot). NOT in `AGENT_REGISTRY` — it has no agent.
- **`WakeInvocationInput` and `WorkflowOutcomeSummary`** live in `src/robotina/queue/task_types.py` alongside `AddRecipeOutcome` and `IncomingMessageInput`.
- **`FinalizeOutcomeInput`** lives in `src/robotina/queue/task_types.py` too — task-input models are co-located.
- **`run_task` helper extraction:** the body branches in D-07 (`_run_user_message_turn`, `_run_wake_turn`) MAY remain inline initially. Planner extracts to helpers if/when the inline branches grow past ~30 lines each. Not a load-bearing choice for Phase 20.
- **Reconciler module location:** `src/robotina/queue/reconcile.py` (or `src/robotina/reconcile.py` if it grows beyond queue concerns). Planner picks; first impl is small.
- **Reconciler trigger:** called from `src/robotina/task_runner.py` boot (the `agent` script entry point) before `worker.work()`. Single call, top of the boot sequence after DB session init.
- **Status transition timestamps:** use `datetime.utcnow()` (existing convention in `models.py`). Not `func.now()` server-side default — those are only for `created_at`/`updated_at`.
- **Dead-letter block migration:** the existing block in `on_step_failed` (lines 507-533) gets wrapped in the `try/except` per D-05. Don't refactor it further in Phase 20.
- **`overrides/*.json` sync:** `finalize-outcome` is agentless — no AGENT_REGISTRY entry, no overrides entry. Memory `feedback_overrides_in_sync.md` does NOT apply unless the planner discovers an existing `overrides/*.json` entry to update. If the dashboard label map lives in an overrides file, sync there.
- **No new env vars** anticipated. If the reconciler needs a "skip-reconcile-on-boot" toggle for tests, planner adds it. Memory `feedback_env_example.md` requires `.env.example` to be updated in the same commit if any new var lands.
- **Quick-task tags:** per memory `feedback_no_task_id_in_code.md` — no "Quick task NNNNNN" or "Phase 20" tags in code/comments/docstrings. Decision IDs (D-04 etc.) are fine in comments since they reference durable design context, not transient tasks.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 20: Wake rule + outcome plumbing" — phase goal, 5 success criteria, dependency on Phase 18.
- `.planning/REQUIREMENTS.md` WAKE-01, WAKE-02, WAKE-03, WAKE-04, WAKE-05, DASH-10, DASH-12 — the seven requirements this phase delivers. Planner must propose ticking these (`[ ]` → `[x]`) in the final implementation commit (per D-16).

### Architecture and pitfalls (load-bearing context)
- `.planning/research/ARCHITECTURE.md` §2.2 "`workflow_runner.py` execution engine diff" — defines the wake-check call sites (lines 102-116 of the doc) and concurrency assumptions.
- `.planning/research/ARCHITECTURE.md` §2.3 "`jobs.py` task runner diff" — describes the `invocation_id` lookup pattern in `run_task` (lines 122-128).
- `.planning/research/ARCHITECTURE.md` §2.5 "`workflows.py` workflow definition diff" — items #4 ("Replace `notify` with `finalize-outcome`") and #1 (Phase 21 deletes `acknowledge`) inform D-01/D-02. **Phase 20 deviation from this doc:** the doc says "replace `notify` with `finalize-outcome`"; D-02 says "append after `notify`" because the doc was scoped to the full end-state. Phase 20 is mid-transition; Phase 21 will do the replace.
- `.planning/research/ARCHITECTURE.md` §2.8 "`gateway/handler.py` diff" — confirms wake invocations don't come through the gateway handler; the enqueue site is the wake helper (D-04).
- `.planning/research/ARCHITECTURE.md` §2.9 "Robotina re-invocation context" — defines what the wake agent sees (D-06, D-08, D-09).
- `.planning/research/ARCHITECTURE.md` §"Phase D — Wake rule + outcome plumbing" — confirms scope boundaries: `notify` stays, dead-letter stays as fallback, V004 prompt update.
- `.planning/research/PITFALLS.md` Pitfall 1 "Wake-rule double-fire on the failed-registry / manual-retry path" — load-bearing for D-04 (single helper, called from both completion sites) and D-05 (UPDATE-RETURNING idempotency). The `wake_dispatched_at` semantics here are the entire safety story.
- `.planning/research/PITFALLS.md` Pitfall 2 "Wake check runs against stale read inside a serializable race" — load-bearing for D-04's "same session, no commit inside helper" rule.
- `.planning/research/PITFALLS.md` Pitfall 11 "Idempotency across worker crash on chain advancement" — load-bearing for D-11 reconciler design + pre-assigned `rq_job_id` pattern.

### Prior phase context (carries forward — do NOT re-decide)
- `.planning/phases/18-robotinainvocation-entity/18-CONTEXT.md` — Phase 18 decisions. Phase 20 inherits ALL of them, especially:
  - D-04 (`RobotinaInvocation` lives in `robotina.queue.models`).
  - D-05 (full schema shipped: `wake_dispatched_at`, `rq_job_id`, `status`, `started_at`, `completed_at` already exist).
  - D-06/D-07 (`InvocationTrigger`/`InvocationStatus` enums shipped with all values).
  - D-08 (`UniqueConstraint("trigger_ref_id", "trigger")` already exists — this IS the WAKE-02 idempotency guard; Phase 20 just exercises it).
  - D-13 (constructor-injected `invocation_id` on `StartWorkflowTool` — no change in Phase 20).
  - D-16/D-17/D-18 (`AddRecipeOutcome` Pydantic shape — Phase 20 is its first consumer + first producer).
- `.planning/phases/17-conversation-fk-closure/17-CONTEXT.md`:
  - D-03/D-04/D-05 (constructor-injected `conversation_id`, `run_task` resolves runtime context) — Phase 20's wake-context dispatch follows the same shape for `WakeInvocationInput`.
- `.planning/phases/13-queue-visibility-dashboard/13-CONTEXT.md` D-01 — module-independence rule. Phase 20 stays compliant (new dashboard reads go through `robotina.queue.models` / `task_types` only).
- `.planning/phases/06-send-notification-agent/` — `send-notification` deterministic `run_task` branch (jobs.py line 90) is the architectural template for the new `finalize-outcome` branch (D-01).

### Existing codebase contracts (current state — Phase 18 has landed)
- `src/robotina/queue/models.py::RobotinaInvocation` — already exists with all columns Phase 20 needs (D-05). `wake_dispatched_at` is nullable `DateTime`; `rq_job_id` is nullable `String`; `status` is `Enum(InvocationStatus)`; `started_at`/`completed_at` are nullable `DateTime`. NO schema change required in Phase 20.
- `src/robotina/queue/models.py::WorkflowRun` — has `conversation_id` (Phase 17), `outcome` JSON column (Phase 17, currently always NULL), `triggered_by_invocation_id` (Phase 18). All three columns exist; Phase 20 starts WRITING `outcome` via `finalize-outcome` (D-01).
- `src/robotina/queue/workflow_runner.py::on_step_complete` (lines 263-401) — the final-step DONE branch (line 393-401) is the wake-check insertion point (D-04). The current `session.commit()` at line 396 stays; the wake-helper call goes BEFORE it.
- `src/robotina/queue/workflow_runner.py::on_step_failed` (lines 404-533) — the FAILED branch around line 495 (`run.status = WorkflowStatus.FAILED`) is the second wake-check insertion point. The dead-letter block (lines 507-533) gets wrapped in `try/except` per D-05.
- `src/robotina/queue/workflow_runner.py::queue_workflow` — no changes. The Phase 18 signature (`triggered_by_invocation_id` arg) already exists.
- `src/robotina/queue/jobs.py::run_task` (line 134 — `handle-incoming-message` branch) — refactored per D-07 to read `RobotinaInvocation` from DB and branch on `trigger`. Existing per-task branches (line 90 `send-notification`, line 181 `recipe-research-gather`, etc.) get a sibling `finalize-outcome` branch (D-01).
- `src/robotina/queue/task_types.py::AddRecipeOutcome` (line 339+) — already exists (Phase 18). Phase 20 adds `WakeInvocationInput`, `WorkflowOutcomeSummary`, `FinalizeOutcomeInput` alongside it.
- `src/robotina/agent/workflows.py::WORKFLOW_REGISTRY['add-recipe']` — step list ends in `notify` today (line 156). Phase 20 appends `finalize-outcome` as new last step (D-02). `acknowledge-add-recipe` stays at line 100; `notify` stays at line 156. Phase 21 will reorder/delete both.
- `src/robotina/dashboard/templates/workflow.html` — `kv-grid` block already has `triggered_by_invocation_id` row (Phase 18). Phase 20 adds `conversation_id` row (D-12) and `outcome` block (D-13). Both inside the same `kv-grid`.
- `src/robotina/dashboard/queries.py::get_workflow_with_steps` — Phase 18 noted "auto-picks up new columns once model has it"; same applies for `outcome`. No edits needed.
- `src/robotina/task_runner.py` — task-runner entry point (`agent` script). Phase 20 adds the reconciler call before `worker.work()` (D-11).
- `src/robotina/agent/prompts/robotina/V003.md` — current Robotina system prompt. Phase 20 forks to `V004.md` (D-09); V003 stays for rollback.

### Project conventions
- `CLAUDE.md` "Tech Stack" — SQLAlchemy 2.x `Mapped`/`mapped_column` mandatory; Pydantic v2 only; `uv run migrate` for migrations; `uv run agent` for task runner.
- Memory `feedback_avoid_premature_abstraction.md` — applied in D-06 (`WorkflowOutcomeSummary` is the minimum needed envelope; no generalized `WorkflowOutcome` wrapper until ≥2 workflow types). Applied in D-23 (no E2E test until tools to support it exist in Phase 21).
- Memory `feedback_queue_at_front.md` — does NOT apply directly (no new `QueueTool` usage in Phase 20). The existing `notify` and dead-letter `send-notification` already use `at_front=True`; we don't touch them. Phase 21's `RespondTool` will need this; flag for Phase 21.
- Memory `feedback_test_before_handoff.md` — gateway+workflow_runner+jobs+dashboard all change; planner MUST include a manual smoke step (send a Telegram message, observe wake invocation in DB + dashboard, observe `outcome` populated, observe `wake_dispatched_at` set, restart worker and observe reconciler logs) before reporting Phase 20 complete.
- Memory `feedback_prompts_language.md` — V004 prompt body in English, Spanish user-facing text only. The wake-context `to_user_message()` rendering is Spanish (D-09).
- Memory `feedback_overrides_in_sync.md` — only engages if `finalize-outcome` or `wake-robotina` ends up in any `overrides/*.json` (it shouldn't — `finalize-outcome` is agentless, wake reuses the existing `handle-incoming-message` task type). Planner greps before commit anyway.
- Memory `feedback_env_example.md` — applies if reconciler gains a config toggle (none anticipated).
- Memory `feedback_no_task_id_in_code.md` — applied in D-23 (decision IDs in comments are durable design refs, not transient task tags).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 18 `RobotinaInvocation` model** — full schema already shipped including `wake_dispatched_at`, `rq_job_id`, `status`, `started_at`, `completed_at`. Phase 20 writes to columns Phase 18 created.
- **Phase 18 `UniqueConstraint("trigger_ref_id", "trigger")`** — Phase 20 doesn't add a new constraint; it relies on this one to guarantee at-most-one wake per parent (Pitfall 1 mitigation). Combined with the UPDATE-RETURNING guard (D-04), this is belt-and-suspenders idempotency.
- **Phase 6 `send-notification` deterministic `run_task` branch** (`jobs.py` line 90) — exact architectural template for the new `finalize-outcome` branch (D-01). Same shape: read task input, do deterministic work, write to DB, return. No agent.
- **Phase 4 D-07 transactional advancement pattern** (`queue_workflow` pre-assigns `task_job_id` before commit; `on_step_complete` does the same for next step) — Phase 20 applies this verbatim for wake-invocation enqueues. Pre-assign `rq_job_id` on the row BEFORE commit; commit; then `queue.enqueue(..., job_id=<pre>)`. Reconciler picks up rows where enqueue didn't happen.
- **Phase 17 dead-letter `send-notification` block** in `on_step_failed` (lines 507-533) — kept as fallback in Phase 20 (D-05), wrapped in `try/except`. Deletion is Phase 21's work.
- **Phase 17 `outcome` JSON column** on `WorkflowRun` — written by `finalize-outcome` (D-01), read by `_check_and_dispatch_wake` (to build `WakeInvocationInput.outcomes`), rendered by the dashboard (D-13).
- **Phase 18 `meta['invocation_id']` channel** + `StartWorkflowTool(invocation_id=...)` constructor injection — Phase 20 doesn't touch the user-message side; it adds a parallel wake-side using the SAME `meta['invocation_id']` channel (just a different invocation id, with a different `trigger`).
- **Phase 13 dashboard `kv-grid`** — `triggered_by_invocation_id` row already exists from Phase 18 (D-19 in 18-CONTEXT). Phase 20 adds two more `<dt>/<dd>` pairs in the same grid (D-12, D-13).
- **`session.add() + session.flush()` for FK materialization** — same pattern as Phase 18 D-11. The wake helper uses it to materialize `new_inv.id` before the enqueue.

### Established Patterns
- **`values_callable=lambda x: [e.value for e in x]`** on enum columns — Phase 20 doesn't add new enums (Phase 18 shipped all values), so this just continues working.
- **Same-transaction multi-write in step-completion hooks** — `on_step_complete` already writes `step.status`, `step.artifact`, `step.completed_at`, optionally `next_step.task_job_id`, all in one session commit. Phase 20 adds the wake-helper's `RobotinaInvocation` insert to the same session (D-04).
- **`Mapped[Optional[X]]` + `nullable=True`** for additive columns — N/A in Phase 20 (no new columns).
- **`Job.exists(job_id, connection=redis)`** RQ API call — used by reconciler (D-11). Standard RQ idiom.
- **Module-isolation grep gate** (Phase 13 D-01) — must continue to pass. Dashboard imports stay within `robotina.queue.models`, `robotina.db`, `robotina.queue.task_types`.
- **Spanish user-facing strings** (per memory `feedback_prompts_language.md`) — applied in wake-context `to_user_message()` rendering (D-09) and dashboard outcome cell labels (D-13). System prompt body remains English.

### Integration Points
- `src/robotina/queue/workflow_runner.py` — add `_check_and_dispatch_wake` helper; wire it into `on_step_complete` final-step DONE branch (line 393-401) and `on_step_failed` FAILED branch (line 495); wrap dead-letter block in `try/except` (D-05).
- `src/robotina/queue/jobs.py` — refactor `handle-incoming-message` branch to read `RobotinaInvocation` from DB and branch on `trigger` (D-07); add `finalize-outcome` deterministic branch (D-01); add invocation status transitions (D-10).
- `src/robotina/queue/task_types.py` — add `WakeInvocationInput`, `WorkflowOutcomeSummary`, `FinalizeOutcomeInput` Pydantic models. Add `WakeInvocationInput` to the input-discriminator union used by `run_task`.
- `src/robotina/agent/workflows.py` — append `finalize-outcome` step to `WORKFLOW_REGISTRY['add-recipe']` step list. Add `finalize-outcome` task-type registration if there's a registry of agentless task types.
- `src/robotina/agent/prompts/robotina/V004.md` — new file. V003 + wake-context section (D-09).
- `src/robotina/agent/agents.py` — possibly add a `finalize-outcome` no-agent entry if the agent registry requires an entry for every task type, OR leave alone if agentless tasks aren't registered (planner confirms).
- `src/robotina/queue/reconcile.py` (new) — `reconcile_invocations(session, queue)` (D-11).
- `src/robotina/task_runner.py` — call `reconcile_invocations` at boot (D-11).
- `src/robotina/dashboard/templates/workflow.html` — add `<dt>/<dd>` for `conversation_id` (D-12) and outcome block (D-13).
- `src/robotina/dashboard/templates/` — task-type label map gets `"finalize-outcome": "Cierre del flujo"` entry (D-14).
- `tests/queue/test_workflow_runner.py` — wake helper tests (D-17), integration test (D-18).
- `tests/queue/test_jobs.py` — run_task branch tests (D-19).
- `tests/queue/test_finalize_outcome.py` (new) — finalize-outcome task tests (D-20).
- `tests/queue/test_reconcile.py` (new) — reconciler tests (D-21).
- `tests/dashboard/test_workflow_template.py` — outcome cell + conversation_id row tests (D-22).
- `.planning/REQUIREMENTS.md` — tick WAKE-01..05, DASH-10, DASH-12 (D-16).

</code_context>

<specifics>
## Specific Ideas

- **Phase 20 is two parallel deliverables:** (a) the wake-rule control loop (`_check_and_dispatch_wake` + reconciler + `WakeInvocationInput` + `run_task` dispatch + V004 prompt) and (b) the outcome plumbing (`finalize-outcome` task + dashboard rendering). They're independent waves and can be planned as such. (a) is the load-bearing safety story; (b) is the data plumbing for Phase 21+ Robotina turns.
- **The wake-rule safety story is `UniqueConstraint` (Phase 18, dormant) + `wake_dispatched_at IS NULL` UPDATE-RETURNING guard (Phase 20, active) + the `_check_and_dispatch_wake` helper being the ONLY caller (single guard site).** Three layers; any one of them alone would be necessary-but-insufficient. Re-litigating any of them weakens the safety story.
- **`finalize-outcome` after `notify` (D-02) is intentionally weird** — it's the bridge that lets Phase 20 ship without breaking the user-facing reply path. Phase 21 deletes `notify` AND reorders/keeps `finalize-outcome` as last step. Planner should note this so reviewers understand the architectural seam.
- **The wake-context agent has no user-facing capability in Phase 20 (no `respond()` tool).** This is the Phase 20 / Phase 21 boundary. The wake path is exercised end-to-end — invocation enqueues, agent runs, V004 prompt interprets the wake context — but the agent has nothing useful to do with that context except log it. Phase 21 gives the agent a voice.
- **Reconciler is small but load-bearing** — it's the AOF-can't-replay-RQ-enqueue safety net (Pitfall 11). Without it, a worker crash between commit and enqueue means a permanently-stuck wake invocation. Pure DB-side safety: AOF persists the commit (the row); reconciler aligns RQ to it on next boot.
- **`run_task` invocation-status writes are NEW** — Phase 18 only writes `PENDING` on insert. Phase 20 wires the full lifecycle. This is the gentlest possible diff (one `with SessionLocal():` block in `run_task`'s `handle-incoming-message` branch, four status writes) and it sets up Phase 21 to query `RobotinaInvocation.status` for the dashboard.
- **The dashboard outcome cell renders a dict, not a Pydantic model.** `WorkflowRun.outcome` is stored as a `JSON` column → fetched as a dict by SQLAlchemy → handed to Jinja. We don't deserialize to `AddRecipeOutcome` on the dashboard side; the Jinja template reads `run.outcome.status` etc. directly. This keeps the dashboard's import surface narrow (per Phase 13 D-01 module-isolation rule).

</specifics>

<deferred>
## Deferred Ideas

- **Robotina's `respond()` tool and the user-visible wake reply** — Phase 21 (TOOLS-02). Phase 20 ships the wake-context input shape and the V004 prompt's wake interpretation, but no new user-facing tool.
- **`TerminateTool`, multi-call `StartWorkflowTool`, removing `acknowledge-add-recipe`, removing `notify` step, removing dead-letter `send-notification` block** — all Phase 21.
- **Multi-recipe-per-message LLM behavior (BATCH-*)** — Phase 22. Phase 20's wake input shape already supports a list (`outcomes: list[WorkflowOutcomeSummary]`), so multi-recipe wake context is structurally supported the moment Phase 22 dispatches multiple workflows to one invocation.
- **URL ingestion + `safe_fetch` (URL-*)** — Phase 23. The URL-source workflow type will reuse `finalize-outcome` and the same wake context shape — no Phase 23 changes to Phase 20 surfaces anticipated.
- **`recipe-image` step (IMG-*)** — Phase 24. Will set `AddRecipeOutcome.image_present=True` on success; Phase 20 always writes `image_present=False` for now.
- **`WorkflowOutcome` envelope generalization** (the architecture doc's `{workflow_run_id, workflow_type, status, summary, structured}` wrapper) — defer until ≥2 workflow types with distinct outcome shapes exist. `WorkflowOutcomeSummary` (Phase 20 D-06) is the wake-input-only minimum envelope; the architectural generalization comes later.
- **WorkflowRunStep orphan reconciliation** (PITFALL 11 "freebie") — backlog. The reconciler in Phase 20 only handles `RobotinaInvocation` orphans. WorkflowRunStep orphans need their own design (which artifacts are recoverable, etc.) and don't block any v1.1 milestone.
- **`Index('ix_workflow_runs_invocation', 'triggered_by_invocation_id')`** for the wake-check count query — defer until load profile warrants it. v1.1 is single-household, low volume.
- **Dedicated `RobotinaInvocation` list/detail dashboard view** (DASH-13 "nice-to-have") — backlog.
- **CRON-trigger producers** (deferred scheduler milestone) — the enum value exists (Phase 18 D-06); no Phase 20 work.
- **WorkflowOutcomeSummary `.summary` human-readable line** (architecture doc §2.9 shape) — intentionally omitted from D-06. The wake-context `to_user_message()` rendering composes Spanish text from the structured fields directly. Adding a redundant `.summary` field would create a second source of truth for the human-readable summary. If V004 turns out to need it, add then.
- **`ask_user(question)` tool for ambiguity escalation** (PITFALL 12) — defer to Phase 22 or post-v1.1.

</deferred>

---

*Phase: 20-Wake rule + outcome plumbing*
*Context gathered: 2026-05-19*
