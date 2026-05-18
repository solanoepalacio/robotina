# Architecture Research — Milestone v1.1 Workflow Refinement

**Domain:** Refactor of an existing Python/LangChain/Postgres/Redis/RQ recipe agent — elevating Robotina from "workflow step" to "workflow dispatcher".
**Researched:** 2026-05-18
**Confidence:** HIGH for current-code mapping; MEDIUM for sequencing risk calls (depends on test coverage at each seam).

---

## 1. Current vs Target Architecture (one picture)

### Current shape (v1.0)

```
Telegram update
  └─> gateway/handler.handle_message
        ├─> Conversation upsert (platform, chat_id, household_id)
        ├─> StoredMessage insert
        └─> enqueue("handle-incoming-message")               [at_front=True]
                 └─> jobs.run_task("handle-incoming-message")
                       └─> Robotina agent (in-graph)
                             ├─ HouseholdManagerApiTool      (sync read)
                             ├─ QueueTool                    (sends one message)  [return_direct]
                             └─ StartWorkflowTool            (one call max)       [return_direct]
                                   │
                                   ▼
                              queue_workflow()
                                   │   - WorkflowRun (PENDING, shared_context = {recipe_query, reply_context, household_id})
                                   │   - WorkflowRunStep × N (PENDING)
                                   │   - enqueue step 0
                                   ▼
                              add-recipe steps drain sequentially
                                acknowledge → gather → instructions → ingredients → metadata → load → notify
                                                                                                        │
                                                                                                        └─> send-notification (deterministic path in run_task)
                                                                                                              └─ reads reply_context.{chat_id,user_id,platform} from shared_context
```

### Target shape (v1.1)

```
Telegram update
  └─> gateway/handler.handle_message
        ├─> Conversation upsert
        ├─> StoredMessage insert
        ├─> RobotinaInvocation insert  (trigger=user_message, trigger_ref_id=stored_message.id)   [NEW]
        └─> enqueue("handle-incoming-message", meta={invocation_id})
                 └─> jobs.run_task
                       └─> Robotina agent  (decider; outside work graph)
                             ├─ HouseholdManagerApiTool      (sync read)
                             ├─ RespondTool                  [NEW — writes StoredMessage(role=ASSISTANT) + sends; non-terminal]
                             ├─ StartWorkflowTool            [REFACTORED — N calls/turn allowed; return_direct=False]
                             └─ TerminateTool                [NEW — terminal; ends the LLM turn]
                                   │  (each start-workflow call)
                                   ▼
                              queue_workflow(conversation_id, triggered_by_invocation_id, workflow_type, input)
                                   │   - WorkflowRun(conversation_id FK, triggered_by_invocation_id FK, outcome=NULL)
                                   ▼
                              add-recipe steps drain
                                gather|gather-from-url → instructions → ingredients → metadata → recipe-image → load → finalize-outcome
                                                                                                                            │
                                                                                                                            └─> writes WorkflowRun.outcome (compact summary)
                                                                                                                            └─> wake-check coordinator
                                                                                                                                  │
                                                                                                                                  └─ if all WorkflowRuns for
                                                                                                                                     triggered_by_invocation_id are terminal:
                                                                                                                                       enqueue handle-incoming-message
                                                                                                                                       (trigger=workflow_completion,
                                                                                                                                        trigger_ref_id=prev invocation_id)
```

The single architectural inversion: **Robotina is no longer a step**. The send-notification "notify" step (last in current add-recipe) goes away, replaced by Robotina's own `respond()` after the wake. Acknowledgement (current step 0) likewise goes away, replaced by Robotina's pre-batch `respond()`.

---

## 2. Integration Points (file-by-file)

### 2.1 `src/robotina/queue/models.py` — schema diff

**Modified — `WorkflowRun`:**

| Column | Change | Notes |
|--------|--------|-------|
| `conversation_id` | NEW FK → `conversations.id`, NOT NULL | Closes the JSON-glue. Backfill required for existing rows. |
| `triggered_by_invocation_id` | NEW FK → `robotina_invocations.id`, NOT NULL | Wake-group key. Backfill: existing rows need a synthetic "pre-v1.1" invocation per Conversation, OR allow NULL with a deprecation window. |
| `outcome` | NEW `JSON`, nullable | Compact, Robotina-facing summary. Final step of each workflow writes it. |
| `input` | RENAME from `shared_context` (or keep `shared_context` and treat as `input`) | Stop using it as a transport for `reply_context` / `household_id`. Once the FKs land, these dict keys can be dropped from new writes. |
| `household_id` | Keep (denormalised) | Already validated end-to-end (Phase 16). Cheaper than joining through Conversation. |

**New — `RobotinaInvocation`:** see §2.4 below for placement.

**Risk:** Adding NOT NULL FKs requires a multi-step Alembic migration (add nullable → backfill → enforce). Done wrong, the worker crashes mid-deploy. Mitigation: ship the FKs as **nullable** in the first migration, backfill in a second, then enforce in a third — over three phases.

---

### 2.2 `src/robotina/queue/workflow_runner.py` — execution engine diff

**`queue_workflow` (lines 106–206):**
- New required args: `conversation_id`, `triggered_by_invocation_id`. Caller is `StartWorkflowTool._run` (only call site today).
- Stop storing `reply_context` inside `shared_context`. Replace with FK reads.
- The `household_id` guard at line 138 can stay; it's defensive and free.

**`on_step_complete` (lines 247–385):**
- After the "Final step — mark WorkflowRun DONE" branch, **also call** a new `_check_wake_robotina(run, session, queue)` helper. Same call site, same transaction.
- Before the wake-check, the final step is expected to have written `WorkflowRun.outcome`. The two options for who writes it:
  - **(A) Final agent of each workflow writes outcome via a structured `response_format` field** — clean but couples agent schemas to workflow-level concerns.
  - **(B) A new dedicated terminal step `finalize-outcome`** per workflow that composes `outcome` from accumulated artifacts via deterministic code (no LLM). Cheaper, easier to reason about, matches today's `notify` step pattern.
  - Recommend **(B)** — same pattern as the existing `notify` step, deterministic Python in `workflows.py`'s `build_input`.

**`on_step_failed` (lines 388–533):**
- Same wake check fires on workflow FAILED (terminal status). Existing dead-letter notification block (lines 490–533) goes away entirely — Robotina speaks for itself on the next invocation. This is a behavior simplification, not a regression: today's apology is also written post-failure; the new path lets Robotina compose a better one with context.
- **Risk:** removing the dead-letter block means a Robotina bug post-wake = silent user. Mitigation: keep the apology as a fallback hook iff the wake-enqueue itself fails.

**New helper — `_check_wake_robotina(run, session, queue)`:**
- Query: `count(*) WHERE triggered_by_invocation_id = run.triggered_by_invocation_id AND status IN ('done', 'failed')` vs `count(*) WHERE triggered_by_invocation_id = run.triggered_by_invocation_id`. If equal, fire wake.
- **Concurrency note:** workers are concurrency=1 (locked architectural constraint). Two workflows for the same invocation can never complete concurrently, so a naive count is correct. No SELECT FOR UPDATE needed today. Worth a code comment so a future concurrency-bump doesn't silently break it.
- **Idempotency:** the wake must enqueue at most one follow-up invocation per `triggered_by_invocation_id`. Use a uniqueness invariant — either a unique constraint `RobotinaInvocation.trigger_ref_id WHERE trigger='workflow_completion'`, or check-then-insert inside the same transaction as the final WorkflowRun status flip. The unique constraint is the safer call (idempotent across worker restarts).

---

### 2.3 `src/robotina/queue/jobs.py` — task runner diff

**Lines 134–149** (the `handle-incoming-message` per-job tool injection): swap `QueueTool` + `StartWorkflowTool` (current) for `RespondTool` + `StartWorkflowTool` (new schema) + `TerminateTool`. Drop `QueueTool` from Robotina's surface entirely — it was a one-shot terminal send; `RespondTool` is its replacement.

**Lines 176–182** (the `acknowledge-add-recipe` branch): delete the whole `elif`.

**Line 90** (`if task_type == "send-notification"`): keep the deterministic path. `RespondTool` should reuse `gateway.send.send_message` directly inside the tool body, not enqueue a `send-notification` job — that adds a queue hop for no benefit when the worker is sequential. (If you want to keep the queue hop for trace-symmetry, that's a real argument — but it's a style call, not a correctness one.)

**New** — the run_task must know the `invocation_id` for this turn so `StartWorkflowTool` can stamp `triggered_by_invocation_id` on each new WorkflowRun. Cleanest path: gateway sets `meta={'task_type': 'handle-incoming-message', 'invocation_id': inv.id}` on the enqueue (line 125–132 of handler.py); run_task reads `job.meta['invocation_id']` and passes it into the tool constructors.

---

### 2.4 RobotinaInvocation entity placement — `src/robotina/queue/models.py` (recommended)

Three placement options were on the table:

| Option | Pros | Cons |
|--------|------|------|
| `src/robotina/gateway/models.py` (alongside Conversation/StoredMessage) | "It's a conversation artifact" — adjacent to StoredMessage | Gateway has been kept thin and import-isolated from queue. Adding a row that workflow_runner writes to would force gateway → queue → gateway import cycles via the wake path. |
| `src/robotina/queue/models.py` (alongside WorkflowRun) ✓ recommended | All workflow-lifecycle state lives in one module. workflow_runner already imports from queue/models; no new dependency direction. Wake-rule writes RobotinaInvocation rows — natural home. | Gateway also writes RobotinaInvocation (on user-message trigger). But it already imports `robotina.queue.task_types` (handler.py line 31), so importing one more queue model is a tiny extension of an existing dependency. |
| New module `src/robotina/invocations/` | Conceptual purity | Premature abstraction; only one entity, no behavior beyond CRUD. Violates `feedback_avoid_premature_abstraction.md`. |

**Decision: place in `src/robotina/queue/models.py`.** Dependency arrows already flow gateway → queue and queue/workflow_runner → queue/models. Adding RobotinaInvocation there doesn't create cycles.

**Suggested schema:**

```python
class InvocationTrigger(enum.Enum):
    USER_MESSAGE = "user_message"
    WORKFLOW_COMPLETION = "workflow_completion"
    CRON = "cron"  # reserved for the deferred scheduler milestone

class RobotinaInvocation(Base):
    __tablename__ = "robotina_invocations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=...)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    trigger: Mapped[InvocationTrigger] = mapped_column(Enum(...), nullable=False)
    trigger_ref_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # USER_MESSAGE        → StoredMessage.id
    # WORKFLOW_COMPLETION → prior RobotinaInvocation.id (the one whose workflows just drained)
    # CRON                → scheduled-task id (future)
    rq_job_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[InvocationStatus] = mapped_column(Enum(...), default=PENDING, nullable=False)
    # PENDING → RUNNING → DONE | FAILED
    started_at, completed_at, created_at, updated_at
    __table_args__ = (
        # Idempotency: at most one workflow_completion wake per parent invocation
        UniqueConstraint("trigger_ref_id", "trigger",
                         name="ux_invocation_workflow_completion_once"),
    )
```

---

### 2.5 `src/robotina/agent/workflows.py` — workflow definition diff

**Step list changes (add-recipe):**

```
v1.0:    acknowledge → gather → instructions → ingredients → metadata → load → notify
v1.1:                    gather|gather-from-url → instructions → ingredients → metadata → recipe-image → load → finalize-outcome
```

Changes:
1. **Delete `acknowledge` step** (step 0). Robotina says it instead via `respond()` before dispatch.
2. **First step branches on `input.source.kind`.** The current static `steps: list[WorkflowStepDef]` shape can't express branching in-list. Two clean ways:
   - **(A) Per-source workflow types** — register `add-recipe-from-query` and `add-recipe-from-url` as separate entries in `WORKFLOW_REGISTRY`. Steps 2-N are identical and built by a shared helper. StartWorkflowTool's `workflow_type: Literal[...]` is extended.
   - **(B) Dynamic step list** — change `WorkflowDefinition.steps` from `list[WorkflowStepDef]` to `Callable[[input], list[WorkflowStepDef]]` evaluated once at `queue_workflow` time. More flexible, but breaks the "workflow definitions are static" mental model.
   - Recommend **(A)** for V1 — concrete, immediate, the Literal in `StartWorkflowTool` already enforces type-safety at the LLM boundary. Refactor to (B) if/when a third workflow needs branching.
3. **Insert `recipe-image` step** after `metadata`, before `load`. New task_type, new agent entry, new RecipeImageInput / RecipeImageOutput models. Failure must be marked non-fatal — needs a new policy (see §3 risks).
4. **Replace `notify` with `finalize-outcome`** — deterministic Python step that reads accumulated artifacts and writes `WorkflowRun.outcome`. No agent. Could be a special step_key the workflow_runner handles inline (not via `run_task`), or just an agent-less task type whose `run_task` branch (jobs.py line 90 pattern) writes the outcome and returns.
5. **Stop building `ReplyContext(**ctx["reply_context"])` in every step's `build_input`.** Steps now read what they need from the WorkflowRun's `conversation_id` join (most steps don't actually need reply_context — only `notify` did). Once `notify` is gone, the chain becomes much cleaner.

**Files that need updating in lockstep with workflows.py:**
- `src/robotina/queue/task_types.py` — drop `AcknowledgeAddRecipeInput`, drop `reply_context` from intermediate Pydantic models, add `RecipeImageInput/Output`, add `GatherFromUrlInput/Output` (likely shares the `RecipeData` output contract).
- `src/robotina/agent/agents.py` — drop `acknowledge-add-recipe` entry, add `gather-from-url` + `recipe-image` entries, possibly add `finalize-outcome` if it goes through `run_task`.
- All `overrides/*.json` files — per `feedback_overrides_in_sync.md`, every add/remove/rename must update every overrides file in the same commit.

---

### 2.6 `src/robotina/agent/tools/start_workflow.py` — tool refactor

| Today | Target |
|-------|--------|
| `return_direct=True` | `return_direct=False` |
| `args_schema=StartWorkflowArgs` with `workflow_type: Literal["add-recipe"]` and `recipe_query: str` flat | New schema: `workflow_type: Literal["add-recipe-from-query", "add-recipe-from-url"]`, `input: AddRecipeQueryInput | AddRecipeUrlInput` (discriminated union) |
| Builds `shared_context` = `{recipe_query, reply_context, household_id}` | Builds `input` = the agent-validated typed object; passes `conversation_id` and `triggered_by_invocation_id` as constructor-injected (like household_id today) |
| Caller: `run_task` injects `chat_id/user_id/platform/household_id` | Caller: `run_task` injects `conversation_id, invocation_id, household_id`. The `chat_id/user_id/platform` are no longer needed on the tool (they live on Conversation, fetched via FK when send needs them). |
| Tool runs once per turn, terminates the agent | Tool runs N times per turn, returns the workflow_run_id, agent continues |

**Robotina's expected tool-call pattern (target):**
```
respond("Listo, voy a buscar las 3 recetas y te aviso cuando estén")
start-workflow(workflow_type="add-recipe-from-query", input={value: "canelones de choclo"})
start-workflow(workflow_type="add-recipe-from-query", input={value: "pollo al horno"})
start-workflow(workflow_type="add-recipe-from-url",   input={url: "https://example/arroz-pilaf"})
terminate()
```

**Risk:** This is the LLM-behavior piece the milestone description flags as "can fail silently". `gpt-oss:20b` via Ollama (the current default) may not reliably emit multiple tool calls in one turn. Two mitigations on the table:
- **List form**: `start-workflows(workflows=[...])` — one call, list payload. Equivalent semantically, easier for an LLM to get right. Trades multi-call reliability for marginally worse error granularity (one validation failure rejects the whole list).
- **Strict prompting + a smoke test in the experiment harness** that verifies multi-call works on the chosen backend before the rest of the milestone is unblocked.
- Recommend a **dedicated investigation phase** before locking the schema (see build order §4).

---

### 2.7 `src/robotina/agent/prompts/robotina/` — prompt diff

Existing V003 prompt (`src/robotina/agent/prompts/robotina/V003.md`) instructs:
- "pass only task-specific fields in `shared_context` (e.g. `recipe_query`)"
- "Agrega guiso de lentejas" → `start-workflow(workflow_type="add-recipe", shared_context={"recipe_query": ...})`

V004 must teach:
- The new tool surface (`respond`, `start-workflow` callable N times, `terminate`).
- Multi-recipe extraction: when the user message references N recipes, dispatch N workflows.
- URL extraction: detect a URL → pick the `add-recipe-from-url` variant.
- The wake-completion flow: when invoked with `trigger=workflow_completion`, the user message is replaced with a summary of workflow outcomes; the agent must compose a reply and terminate.
- Spanish-language reply (per existing convention, `feedback_prompts_language.md`).

The system-prompt body remains in English; only user-facing text is Spanish.

---

### 2.8 `src/robotina/gateway/handler.py` — handler diff

**Line 113–132** (the enqueue): the handler currently builds `IncomingMessageInput` with `chat_id, user_id, platform, household_id, text, history` and enqueues with `meta={'task_type': 'handle-incoming-message'}`.

Diff:
1. After persisting the StoredMessage, insert a `RobotinaInvocation(conversation_id=conv.id, trigger=USER_MESSAGE, trigger_ref_id=stored.id, status=PENDING)` in the same transaction.
2. Enqueue with `meta={'task_type': 'handle-incoming-message', 'invocation_id': inv.id}`.
3. The `IncomingMessageInput` model can either gain `invocation_id` or stay as-is (job.meta is already the primary channel for `task_type`; adding `invocation_id` there is consistent).

**Risk:** wake-triggered invocations also enqueue `handle-incoming-message` jobs — but they don't come through this handler. The enqueue site for wake-driven invocations is `workflow_runner._check_wake_robotina`. Both call sites must produce the same shape of job (same meta, same input model). The input model for wake invocations differs: there's no fresh user message, instead a structured "here are the outcomes" payload. Options:
- Reuse `IncomingMessageInput` with `text=""` and a new `wake_outcomes: list[WorkflowOutcome]` field. Cheap, but mixes concerns.
- Add a sibling input model `WakeInvocationInput` and dispatch in `run_task` on `task_type` + `invocation.trigger`. Cleaner.

Recommend the second. The wake-input model carries `invocation_id` + `previous_invocation_id` + list of `WorkflowOutcome` summaries (the `WorkflowRun.outcome` blobs); the agent builds its user-facing context from those + the standard conversation history fetched via `conversation_id`.

---

### 2.9 Robotina re-invocation context (the new code path)

When woken with `trigger=workflow_completion`, the agent sees:
- **Conversation history** — same as today, fetched from `StoredMessage` (now includes any `respond()` writes Robotina made in the previous turn, so it remembers what it told the user before dispatch).
- **Workflow outcomes** — `WorkflowRun.outcome` for each workflow whose `triggered_by_invocation_id` matches the prior invocation. Compact, structured. Different from artifact: artifact is the verbose internal contract between steps, outcome is the summary Robotina sees.
- **The household-manager API** — still available via tool, same as user-message invocations.

The agent must terminate the chain: if it dispatches no new workflows and just `respond()`s + `terminate()`s, the chain ends naturally. If it dispatches more, the cycle continues.

Outcome schema (suggested compact shape):
```python
class WorkflowOutcome(BaseModel):
    workflow_run_id: str
    workflow_type: str        # "add-recipe-from-query" etc.
    status: Literal["done", "failed"]
    summary: str              # human-readable single line for Robotina to quote
    structured: dict          # workflow-specific payload: recipe_id, recipe_name, missing_ingredients[], image_saved bool
```

Build sites: each workflow's `finalize-outcome` deterministic step composes the structured shape from accumulated artifacts.

---

## 3. Risks Per Integration Point

| Risk | Likelihood | Severity | Mitigation |
|------|-----------|----------|------------|
| Multi-call StartWorkflowTool unreliable on `gpt-oss:20b` | MEDIUM-HIGH | HIGH — blocks Topic 1 | Build a smoke-test experiment first; fall back to list-form schema if multi-call fails. Decide *before* the refactor wave. |
| Migration of NOT NULL FKs crashes the worker mid-deploy | MEDIUM | HIGH | Three-step migration: add nullable → backfill → enforce. Backfill `conversation_id` from `shared_context.reply_context.chat_id` + `Conversation.chat_id` lookup. |
| Wake-rule fires twice (same invocation, two workers, race) | LOW (concurrency=1) | HIGH | UNIQUE(trigger_ref_id, trigger='workflow_completion'). Belt + suspenders even with single worker, because RQ retries / requeues can re-execute. |
| Existing recipe-research-* / recipe-load agents break when `reply_context` removed from their inputs | HIGH (they actively unpack it today) | MEDIUM | Land the schema change incrementally: keep `reply_context` flowing through `shared_context` for a deprecation window, drop it only after `notify` step is gone. |
| `recipe-image` step failure mode | MEDIUM | LOW | Make the step's run_task branch treat a structured "image-unavailable" output as success-with-degraded-flag (writes the artifact, advances). Real exceptions still fail the step → cancel pipeline. The "non-fatal" requirement is about *image acquisition failure*, not about the step itself never failing. |
| Removing the dead-letter `send-notification` from `on_step_failed` leaves silent failures if wake-enqueue itself fails | LOW | MEDIUM | Keep the dead-letter block as fallback iff wake-enqueue raises. |
| Robotina prompt regression on single-recipe text flow (today's happy path) | MEDIUM | MEDIUM | Pin a regression smoke test: "Agregá lentejas" must still result in exactly one add-recipe workflow + one final reply. |
| `acknowledge-add-recipe` prompt/agent removal breaks an override file referencing it | LOW | LOW | Sweep `overrides/*.json` in the same commit (per `feedback_overrides_in_sync.md`). |

---

## 4. Suggested Build Order (phase candidates for roadmapper)

The principle: **schema before code, code before prompts, prompts before behaviour-sensitive features**. Each phase must leave the system shippable.

### Phase A — Conversation FK closure (foundation)

**Why first:** every later phase wants `WorkflowRun.conversation_id` to exist. Doing this first means the rest of the work doesn't carry the JSON-glue burden.

**Files touched:**
- `src/robotina/queue/models.py` — add `conversation_id` and `outcome` as nullable.
- Alembic migration — three steps (add nullable, backfill from `shared_context.reply_context.chat_id` → Conversation.chat_id, enforce NOT NULL on conversation_id).
- `src/robotina/agent/tools/start_workflow.py` — start writing `conversation_id` on new WorkflowRuns. `reply_context` still written too (deprecation window).
- `src/robotina/queue/workflow_runner.py` — `queue_workflow` signature gains `conversation_id`.

**Exit criteria:** all new WorkflowRuns have `conversation_id` set; backfill complete; no behavior change visible to users.

**Risk:** MEDIUM — migration must be exact; staging soak before prod.

---

### Phase B — RobotinaInvocation entity (entity-first, no wake yet)

**Why second:** introduces the entity that Phase C's wake rule depends on. Phase B alone is a strict additive change — write rows but don't read them yet.

**Files touched:**
- `src/robotina/queue/models.py` — add `RobotinaInvocation` table, `InvocationTrigger` enum, unique constraint.
- Alembic migration — new table.
- `src/robotina/gateway/handler.py` — insert RobotinaInvocation on each user message; pass `invocation_id` through `job.meta`.
- `src/robotina/queue/jobs.py` — read `job.meta['invocation_id']`, stamp `WorkflowRun.triggered_by_invocation_id` when StartWorkflowTool is invoked.
- `src/robotina/agent/tools/start_workflow.py` — accept `invocation_id` constructor arg.
- Alembic migration — `WorkflowRun.triggered_by_invocation_id` nullable → backfill (existing rows get a synthetic invocation per Conversation, or stay NULL with a deprecation flag).

**Exit criteria:** every new WorkflowRun has both `conversation_id` and `triggered_by_invocation_id`; the table is populated; no behavior change.

**Risk:** LOW — strict additive change, no removed code paths yet.

---

### Phase C — LLM smoke test: does multi-call StartWorkflowTool actually work?

**Why third (and standalone):** the next phases (D, E) all assume the LLM can call `start-workflow` N times in one turn. If it can't, the schema must change to a list-form and the work in D/E rebases.

**Files touched:** mostly `experiments/` — a one-shot harness that invokes the existing `handle-incoming-message` agent with a multi-recipe message and counts tool calls. Tooling is just plumbing — `return_direct=True` is dropped on this experimental variant of `StartWorkflowTool`.

**Exit criteria:** evidence (HIGH confidence) that the target backend will reliably emit multiple `start-workflow` calls — or evidence that it won't, in which case the schema pivots to list-form before D/E.

**Risk:** HIGH — this is the load-bearing LLM-behaviour assumption.

---

### Phase D — Wake rule + outcome plumbing (the new control loop)

**Why fourth:** the entity exists (B), the FK exists (A), the schema is decided (C). Now wire the wake.

**Files touched:**
- `src/robotina/queue/workflow_runner.py` — add `_check_wake_robotina`, call from `on_step_complete` and `on_step_failed`.
- `src/robotina/queue/task_types.py` — new `WorkflowOutcome` model, new `WakeInvocationInput`.
- `src/robotina/agent/workflows.py` — add `finalize-outcome` terminal step writing `WorkflowRun.outcome`. Insert it as the new last step of `add-recipe` (replacing `notify` for the moment — but `notify` stays in place too while transitioning; remove `notify` only after D's wake path is verified end-to-end).
- `src/robotina/queue/jobs.py` — branch on `WakeInvocationInput` vs `IncomingMessageInput`; pass `WorkflowOutcome`s to the agent via `to_user_message()`.
- `src/robotina/agent/prompts/robotina/V004.md` — teach the wake path. Robotina now also handles `trigger=workflow_completion` invocations.

**Exit criteria:** add-recipe still works end-to-end. After the workflow drains, a second `handle-incoming-message` invocation fires. The reply still comes from the existing `notify` step (parallel path; not yet removed). Robotina's wake-path response is observable in logs but not yet user-visible.

**Risk:** MEDIUM-HIGH — this is the new control loop; bugs here look like "Robotina never speaks again after the first batch".

---

### Phase E — Robotina-as-decider tool surface (RespondTool, TerminateTool, multi-call StartWorkflowTool, drop acknowledge-add-recipe)

**Why fifth:** wake exists (D); now flip the user-facing path from "notify step talks" to "Robotina talks via respond()". Also delete the legacy ack step (already redundant by then).

**Files touched:**
- New tools: `src/robotina/agent/tools/respond.py`, `src/robotina/agent/tools/terminate.py`.
- `src/robotina/agent/tools/start_workflow.py` — drop `return_direct=True`; new schema with `{workflow_type, input}`; multi-call allowed.
- `src/robotina/queue/jobs.py` — swap tool injection (QueueTool out, RespondTool/TerminateTool in); delete the `acknowledge-add-recipe` elif branch (lines 176–182).
- `src/robotina/agent/agents.py` — delete `acknowledge-add-recipe` entry.
- `src/robotina/agent/prompts/robotina/V005.md` — teach the new tool surface.
- `src/robotina/agent/workflows.py` — remove the `acknowledge` step from add-recipe; remove the `notify` step (now redundant: Robotina speaks via `respond()` on wake).
- Delete `src/robotina/agent/prompts/acknowledge-add-recipe/`.
- Sweep all `overrides/*.json` for `acknowledge-add-recipe` references.
- Drop `AcknowledgeAddRecipeInput` and `SendNotificationInput`-from-workflows references in `src/robotina/queue/task_types.py`.

**Exit criteria:** single-recipe happy path: user sends "agregá lentejas" → Robotina `respond`s pre-batch → workflow drains → Robotina is woken → `respond`s post-batch with recipe link → `terminate`s. No regressions on the existing happy path.

**Risk:** MEDIUM — most behavior change concentrated here. Pin the regression smoke test.

---

### Phase F — Multi-recipe (Topic 1)

**Why sixth:** E gave Robotina the multi-call surface; now exercise it for the user-facing feature.

**Files touched:** prompt-only in the happy case. `V006.md` of robotina prompt: teach extraction of N recipes from one message, dispatch N start-workflow calls, compose the consolidated final reply.

**Exit criteria:** "agregá X, Y, Z" → 3 add-recipe workflows → one consolidated reply.

**Risk:** MEDIUM — LLM behaviour; falls back to Phase C's findings if it doesn't extract reliably.

---

### Phase G — URL ingestion (Topic 2)

**Files touched:**
- `src/robotina/queue/task_types.py` — `GatherFromUrlInput`, `RecipeData` output (same as gather).
- `src/robotina/agent/agents.py` — `gather-from-url` entry.
- `src/robotina/agent/prompts/gather-from-url/V001.md`.
- New tool `src/robotina/agent/tools/url_fetch.py` (and a recipe-scrapers integration).
- `src/robotina/agent/workflows.py` — register `add-recipe-from-url` variant; split the existing `add-recipe` into `add-recipe-from-query` and `add-recipe-from-url`; shared steps via helper.
- `src/robotina/agent/tools/start_workflow.py` — extend `Literal[...]` to include both variants; discriminated `input` union.
- Robotina prompt V007: URL detection, pick correct workflow_type.

**Exit criteria:** "agregá esta receta: https://..." → URL workflow → recipe saved.

**Risk:** MEDIUM — scraping library choice is open per milestone description. Add a fallback ladder (JSON-LD → microdata → LLM extraction → fail).

---

### Phase H — Recipe images (Topic 3)

**Files touched:**
- `src/robotina/queue/task_types.py` — `RecipeImageInput/Output`.
- `src/robotina/agent/agents.py` — `recipe-image` entry.
- `src/robotina/agent/prompts/recipe-image/V001.md`.
- New tool `src/robotina/agent/tools/image_search.py`.
- `src/robotina/agent/workflows.py` — insert `recipe-image` step before `load` in both add-recipe variants.
- `src/robotina/agent/tools/household_manager_api.py` — likely needs an image field on the recipe POST.
- `finalize-outcome` step — report image-saved flag in WorkflowOutcome.structured.

**Exit criteria:** saved recipes have images when available; image acquisition failure does not block save.

**Risk:** LOW-MEDIUM — quality features around image source choice are open but not blockers.

---

## 5. Order Summary and Riskiest Seams

```
A: Conversation FK closure          [foundation; nullable→backfill→enforce]
   ↓
B: RobotinaInvocation entity         [strict additive]
   ↓
C: LLM multi-call smoke test         [load-bearing assumption check]   ★ DECIDE BEFORE D
   ↓
D: Wake rule + outcome plumbing      [new control loop; parallel-path safe]
   ↓
E: Tool-surface flip (respond/      [biggest behaviour change;
    terminate/multi-call start,      removes ack step + notify step]
    drop acknowledge-add-recipe)
   ↓
F: Multi-recipe                      [prompt-only]
   ↓
G: URL ingestion                     [new task type + new step branch]
   ↓
H: Recipe images                     [new task type; non-fatal failure mode]
```

**Riskiest seams in priority order:**
1. **Phase C decision** — if multi-call LLM behaviour is unreliable, the entire E/F design pivots. **Investigate first.**
2. **Phase E** — the tool-surface flip + acknowledge/notify deletion is the biggest single behaviour change. Concentrated, but well-bounded if A/B/D landed cleanly.
3. **Phase A migration** — three-step Alembic; production-data backfill; one wrong query and the worker crashes on enqueue.
4. **Phase D wake-rule idempotency** — UNIQUE constraint + transaction shape; bugs here are silent (Robotina never wakes, or wakes twice).

**Lowest-risk seams:** Phase B (additive entity), Phase F (prompt), Phase H (non-fatal feature).

---

## 6. Component Responsibilities (target state)

| Component | Responsibility |
|-----------|----------------|
| `gateway/handler.py` | Telegram → DB writes (Conversation, StoredMessage, RobotinaInvocation) → enqueue. Single responsibility: get the message in, fire the invocation. Never writes WorkflowRuns. |
| `queue/models.py` | All persistent state: Conversation/StoredMessage (existing), RobotinaInvocation (new), WorkflowRun/WorkflowRunStep (existing + new FKs/outcome). |
| `queue/workflow_runner.py` | Workflow lifecycle: queue_workflow, on_step_start/complete/failed, _check_wake_robotina. Owns the wake decision. |
| `queue/jobs.py` | Universal RQ entry point; resolves task_type → tool surface → agent invoke; dispatches WakeInvocationInput vs IncomingMessageInput. |
| `agent/tools/start_workflow.py` | Creates one WorkflowRun per call, linked to the live RobotinaInvocation. No more `return_direct`. |
| `agent/tools/respond.py` (NEW) | Side-effect: write assistant StoredMessage + Telegram send. Returns success ack to the agent (non-terminal). |
| `agent/tools/terminate.py` (NEW) | Terminal tool. Ends the LLM turn. The agent's signal that it has nothing more to dispatch / say. |
| `agent/workflows.py` | Static WORKFLOW_REGISTRY with per-source variants (add-recipe-from-query, add-recipe-from-url). Last step of each: deterministic finalize-outcome. |
| `agent/agents.py` | Per-task-type LLM config. Loses `acknowledge-add-recipe`; gains `gather-from-url`, `recipe-image`. |

---

## 7. Anti-Patterns (to avoid during this refactor)

### Anti-Pattern 1: Land all schema changes in one migration
**What people do:** Single Alembic migration that adds `conversation_id NOT NULL`, `triggered_by_invocation_id NOT NULL`, `outcome`, and the new RobotinaInvocation table at once.
**Why it's wrong:** Forces a backfill in the same migration. If backfill SQL is wrong, you can't roll forward without manual surgery.
**Do this instead:** Three migrations per added NOT NULL FK: add nullable → backfill in app code (or a one-off script) → enforce.

### Anti-Pattern 2: Keep the JSON-glue "just in case"
**What people do:** Add `conversation_id` FK but also keep writing `shared_context.reply_context.chat_id` indefinitely.
**Why it's wrong:** Two sources of truth, drift inevitable, future readers don't know which is authoritative.
**Do this instead:** Deprecation window of exactly one phase (A keeps writing both; E removes the JSON write entirely).

### Anti-Pattern 3: Make `recipe-image` a regular step that's allowed to fail
**What people do:** Throw exceptions when image acquisition fails, let `on_step_failed` cancel the pipeline.
**Why it's wrong:** Image is non-fatal per the milestone description. Cancelling load over a missing image is a regression vs current behaviour (no image step → recipe always saves).
**Do this instead:** The step's agent (or deterministic branch) treats acquisition failure as a structured `RecipeImageOutput(status="unavailable", reason=...)` artifact and advances. Only infrastructure failures (HTTP errors, tool crashes) propagate as exceptions.

### Anti-Pattern 4: Branching first step via if-statements inside `build_input`
**What people do:** First step's `build_input` reads `ctx["source"]["kind"]` and… too late, `task_type` is already fixed in `WorkflowStepDef`.
**Why it's wrong:** `task_type` is decided at WorkflowRun creation time (queue_workflow), not at step build time. A single `add-recipe` workflow type with `task_type="gather"` can't conditionally dispatch a different task_type for step 0.
**Do this instead:** Separate workflow types per source variant (recommended) OR dynamic `WorkflowDefinition.steps` builder (more invasive). See §2.5.

### Anti-Pattern 5: Have Robotina speak from inside the work graph
**What people do:** Keep one "report success/failure" step at the end of each workflow that sends a message.
**Why it's wrong:** Defeats the entire architectural inversion. Multi-recipe would N-spam the user with N "done!" messages instead of one consolidated reply. The `acknowledge-add-recipe` workaround was exactly this anti-pattern; the milestone is built to delete it.
**Do this instead:** Workflows write structured `outcome` only. Robotina (woken post-batch) composes user-facing messages via `respond()`.

---

## 8. Integration Points — External & Internal

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Telegram (via python-telegram-bot v21) | Async handler in gateway; `send_message` in `gateway/send.py` reused by RespondTool | RespondTool can call `send_message` directly — no need to enqueue `send-notification`, given concurrency=1 worker. Trade-off: bypasses queue's persistence guarantees for assistant messages. If a crash mid-send is acceptable, fine; if not, route RespondTool → enqueue `send-notification`. |
| household-manager backend (HTTP) | `HouseholdManagerApiTool` via httpx | Recipe POST may need to accept an `image_url` field — coordinate with backend if not already supported. |
| Tavily web search | Existing `WebSearchTool` | Unchanged. |
| Image source (new) | TBD — web image search vs hybrid | Open per milestone description. URL-pinning vs backend re-host is a quality call, not a correctness one. |
| Recipe URL scraping (new) | TBD — recipe-scrapers (PyPI) recommended for JSON-LD/microdata layer | LLM fallback covers the long tail. Both behind a single tool: `url_fetch`. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| gateway → queue | Already-established: gateway writes Conversation/StoredMessage and enqueues. Adds RobotinaInvocation write. | No new dependency direction; just a new model write. |
| queue/workflow_runner → queue/jobs | Indirect via RQ enqueue; no new direct imports. | Wake-enqueue must pass `meta={'task_type': 'handle-incoming-message', 'invocation_id': inv.id, 'queue_name': 'agent-tasks'}` mirroring the gateway. |
| agent/tools → queue/workflow_runner | StartWorkflowTool imports `queue_workflow` (existing). | Tool gains `invocation_id` constructor arg; passed through to `queue_workflow`. |
| agent/tools → gateway/send | RespondTool calls `gateway.send.send_message` (already imported in jobs.py for `send-notification` deterministic path; the pattern is established). | Acceptable cross-module import; the deterministic send path is a stable seam. |
| dashboard/* | Reads-only; consumes WorkflowRun + new WorkflowRun.outcome | Dashboard rendering of `outcome` is a small follow-up; not blocking. |

---

## 9. Confidence Notes

| Claim | Confidence | Source |
|-------|------------|--------|
| Current code shape (file-by-file) | HIGH | Direct reading of all files listed in the prompt. |
| Recommended placement of RobotinaInvocation in queue/models.py | MEDIUM-HIGH | Reasoning from existing import-direction conventions and `feedback_avoid_premature_abstraction.md`. Alternative placements are viable; this is a judgement call. |
| Three-step migration pattern for NOT NULL FK | HIGH | Standard Alembic/Postgres practice. |
| Wake-rule idempotency via UNIQUE constraint | HIGH | Standard idempotency-key pattern. |
| Build order (A → H) | MEDIUM | Logically dependency-ordered, but actual phase boundaries the roadmapper draws may merge or split. Phase C as a *standalone* investigation is the strongest non-negotiable. |
| Multi-call LLM reliability risk on `gpt-oss:20b` | LOW (i.e. genuinely uncertain) | The milestone description explicitly flags this as the "LLM-behaviour piece that *can* fail silently". Phase C exists specifically to convert this from speculation to evidence. |
| `recipe-image` non-fatal failure handling pattern | MEDIUM | Inferred from the milestone description ("Failure is non-fatal — the recipe saves without an image"). Implementation detail (structured "unavailable" artifact vs swallowed exception) is a design call. |
| URL scraper choice | LOW | Open question per milestone description; not researched here. |
| Image source choice | LOW | Open question per milestone description; not researched here. |

---

*Architecture research for: milestone v1.1 Workflow Refinement — integration plan, file-by-file*
*Researched: 2026-05-18*
