# Roadmap: Robotina

## Milestones

- ✅ **v1.0 MVP** — Phases 1–16 + decimal 07.1 (shipped 2026-05-18)
- 🚧 **v1.1 Workflows Abstraction Refinement** — Phases 17–24 (planning complete 2026-05-18)

See `.planning/MILESTONES.md` for shipped-milestone details.
See `.planning/milestones/v1.0-ROADMAP.md` for the full v1.0 phase detail at close.

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–16 + 07.1) — SHIPPED 2026-05-18</summary>

- [x] Phase 1: Developer Tooling and Infrastructure (3/3 plans)
- [x] Phase 2: Database Models and Queue Layer (3/3 plans)
- [x] Phase 3: Gateway (3/3 plans)
- [x] Phase 4: LLM Module and Agent Infrastructure (6/6 plans)
- [x] Phase 5: Task Runner and Workflow Engine (5/5 plans)
- [x] Phase 6: send-notification Agent (4/4 plans)
- [x] Phase 7: handle-incoming-message Agent (4/4 plans)
- [x] Phase 07.1 (INSERTED): Deterministic Agent Termination (3/3 plans)
- [x] Phase 8: recipe-research Agent (4/4 plans)
- [x] Phase 9: recipe-load Agent and End-to-End Integration (2/2 plans)
- [x] Phase 10: LangChain 1.x Agent API Migration (3/3 plans)
- [x] Phase 11: Structured Agent Output via response_format (4/4 plans)
- [x] Phase 12: Middleware-Based Agent Instrumentation (2/2 plans)
- [x] Phase 13: Queue Visibility Dashboard (3/3 plans)
- [x] Phase 14: Prompt Cleanup and Structural Standardization (8/8 plans)
- [x] Phase 15: Recipe Artifact Accumulation and Food/Unit Validation (6/6 plans)
- [x] Phase 16: Fix empty-string household_id propagation (7/7 plans)

</details>

### 🚧 v1.1 Workflows Abstraction Refinement (Phases 17–24)

- [x] **Phase 17: Conversation FK closure** — Single Alembic revision 0006 adds `WorkflowRun.conversation_id` NOT NULL FK (table pre-cleaned via runbook) and nullable `outcome` column; `StartWorkflowTool` and `queue_workflow` write the FK; legacy `reply_context` JSON path remains readable. Code/migration shipped 2026-05-19; runbook executed and Telegram smoke test + integration migration test confirmed green against live DB (2026-05-19).
- [x] **Phase 18: RobotinaInvocation entity** — New `robotina_invocations` table + `InvocationTrigger` enum + idempotency `UniqueConstraint`; gateway inserts invocation on user_message; `WorkflowRun.triggered_by_invocation_id` FK populated by `StartWorkflowTool`; dashboard surfaces the new FK on detail view. (completed 2026-05-19)
- [ ] **Phase 19**: _removed 2026-05-19_ — original "LLM multi-call smoke test" was infeasible against the current `return_direct=True` tool surface, which terminates the turn after one `start-workflow` call. The empirical gate is folded into Phase 21 as a manual smoke checkpoint after the surface is flipped. Phase number left vacant to avoid renumbering churn on downstream phases.
- [ ] **Phase 20: Wake rule + outcome plumbing** — `_check_wake_robotina(session)` helper called from `on_step_complete`/`on_step_failed`; `wake_dispatched_at` atomic guard; pre-assigned `job_id` (D-07); startup reconciler; `AddRecipeOutcome` Pydantic + `finalize-outcome` deterministic step; `WakeInvocationInput`; dashboard `outcome` summary cell.
- [ ] **Phase 21: Tool-surface flip + remove acknowledge/notify (+ manual multi-call smoke)** — `RespondTool` (queue-at-front) + `TerminateTool` (return_direct); `StartWorkflowTool` refactored (multi-call, discriminated `{workflow_type, input}`, `invocation_id` constructor-injected); `acknowledge-add-recipe` agent/prompts/registry/overrides/dashboard label/experiment all removed; `notify` workflow step deleted; CI guard for AGENT_REGISTRY ↔ overrides. Includes a manual smoke checkpoint on Ollama (`gpt-oss:20b` local) + OpenAI (staging) with 5–8 hand-curated Spanish utterances; results committed as `.planning/phases/21-.../SMOKE.md`; if reliability is unacceptable on the staging backend, pivot to list-form `start-workflow(actions=[...])` before merging the phase.
- [ ] **Phase 22: Multi-recipe per message** — Robotina prompt V006 teaches multi-recipe extraction + consolidated post-batch reply + soft cap at 5; eval set committed; partial-failure reporting verified end-to-end.
- [ ] **Phase 23: URL ingestion** — `safe_fetch` helper (six SSRF defenses, lands FIRST commit); `gather-from-url` task type with `recipe-scrapers` + LLM fallback; `add-recipe-from-url` workflow variant; Robotina URL detection + routing; experiment script; 20-URL eval ≥85% field-level success.
- [ ] **Phase 24: Recipe images** — `recipe-image` task type with Tavily image search + source-page fallback; new per-step non-fatal-failure runner capability; `safe_fetch` reused for image URL validation; `image_url` persisted via household-manager API; `AddRecipeOutcome.image_present` flag; experiment script.

## Phase Details

### Phase 17: Conversation FK closure
**Goal**: Every WorkflowRun is linked to its originating Conversation via FK; existing rows are safely backfilled.
**Depends on**: v1.0 baseline (Phase 16)
**Requirements**: ARCH-01, ARCH-05
**Success Criteria** (what must be TRUE):
  1. A new WorkflowRun written via `StartWorkflowTool` has `conversation_id` set and matches the Conversation the originating message belonged to.
  2. The single Alembic revision 0006 (add `conversation_id` NOT NULL + `outcome` nullable JSON in one upgrade) runs cleanly on a pre-cleaned database; post-migration `COUNT(*) WHERE conversation_id IS NULL` returns 0 trivially because the runbook truncates `workflow_runs` before applying 0006.
  3. Existing code paths that previously read `shared_context.reply_context.chat_id` continue to function (deprecation window) — single-recipe happy path unaffected.
  4. `WorkflowRun.outcome` JSON column exists (nullable, unused this phase) ready for Phase 20.
**Plans**: 4 plans
- [x] 17-01-PLAN.md — Wave 0 RED-state lock tests (schema/ctor/signature/lookup/stub)
- [x] 17-02-PLAN.md — Wave 1 schema + ORM model + WorkflowOutcome Pydantic stub (Alembic 0006)
- [x] 17-03-PLAN.md — Wave 2 signatures + wire-up (queue_workflow / StartWorkflowTool / run_task Conversation lookup) + bulk-update existing test ctor sites
- [x] 17-04-PLAN.md — Wave 3 REQUIREMENTS.md ARCH-01 wording edit + deploy runbook (D-08)

### Phase 18: RobotinaInvocation entity
**Goal**: Every Robotina LLM turn is recorded as a persisted row, and every new WorkflowRun points back to the invocation that dispatched it.
**Depends on**: Phase 17
**Requirements**: ARCH-02, ARCH-03, ARCH-04, DASH-13, DASH-14
**Success Criteria** (what must be TRUE):
  1. A user-message in Telegram inserts a `RobotinaInvocation(trigger=user_message)` row with `trigger_ref_id` set to the StoredMessage id; the agent job is enqueued with `meta['invocation_id']`.
  2. Every WorkflowRun created during that turn carries `triggered_by_invocation_id` matching the invocation row.
  3. The `RobotinaInvocation` schema includes the `AddRecipeOutcome`-shaped `outcome` JSON contract on `WorkflowRun` (Pydantic model defined; not yet written).
  4. Dashboard's WorkflowRun detail view surfaces `triggered_by_invocation_id`; module-isolation grep gate still passes (RobotinaInvocation imported from `queue.models` only).
**Plans**: 4 plans
- [x] 18-01-PLAN.md — Wave 0 RED-state lock tests (model introspection, AddRecipeOutcome shape, queue_workflow signature, StartWorkflowTool ctor, gateway insert + dedup-no-orphan, dashboard render)
- [x] 18-02-PLAN.md — Wave 1 schema (Alembic 0007 + RobotinaInvocation ORM + InvocationTrigger/Status enums + WorkflowRun.triggered_by_invocation_id) + AddRecipeOutcome Pydantic replacement
- [x] 18-03-PLAN.md — Wave 2 wiring (queue_workflow signature + StartWorkflowTool.invocation_id + jobs.py bracket-read + gateway handler step 2b with dedup-no-orphan guard)
- [x] 18-04-PLAN.md — Wave 3 dashboard row (DASH-13) + REQUIREMENTS.md ARCH-02 wording (rq_job_id) + deploy runbook + manual smoke checkpoint
**UI hint**: yes

### Phase 19: _removed_

Originally scoped as a standalone LLM multi-call smoke test. Removed 2026-05-19 because the current `StartWorkflowTool` has `return_direct=True` — the LangGraph engine terminates the turn after the first `start-workflow` call, so no smoke test against the current tool surface could measure N-calls-per-turn reliability. The empirical gate is preserved as a manual smoke checkpoint inside Phase 21 (after `return_direct=False` and the prompt rewrite land in the same branch). EVAL-01/02/03 were reframed and reassigned to Phase 21. Phase number left vacant to keep downstream phase numbers stable.

### Phase 20: Wake rule + outcome plumbing
**Goal**: When all workflows linked to one invocation reach terminal status, exactly one wake invocation is enqueued — with structured outcomes the next Robotina turn can consume.
**Depends on**: Phase 18
**Requirements**: WAKE-01, WAKE-02, WAKE-03, WAKE-04, WAKE-05, DASH-10, DASH-12
**Success Criteria** (what must be TRUE):
  1. A single add-recipe workflow that completes triggers exactly one new `RobotinaInvocation(trigger=workflow_completion)` row whose `trigger_ref_id` is the prior invocation's id.
  2. The wake check is idempotent: manual requeue from RQ failed registry on a terminal workflow does NOT enqueue a second wake invocation (verified by `wake_dispatched_at` UPDATE-RETURNING semantics).
  3. A `kill -9` of the worker between the wake-enqueue's commit and RQ enqueue is recovered on startup — the reconciler re-enqueues the pre-assigned `job_id`.
  4. Each terminal workflow has a non-null `WorkflowRun.outcome` (`AddRecipeOutcome` JSON, < 300 bytes) written by the deterministic `finalize-outcome` step; the dashboard renders a compact outcome summary.
  5. The wake agent receives a `WakeInvocationInput` with the previous invocation id and list of `WorkflowOutcome` summaries.
**Plans**: 6 plans
- [ ] 20-01-PLAN.md — Wave 1: Pydantic models (WakeInvocationInput, WorkflowOutcomeSummary, FinalizeOutcomeInput)
- [ ] 20-02-PLAN.md — Wave 1: finalize-outcome task type + agent-less run_task branch + workflow step append
- [ ] 20-03-PLAN.md — Wave 2: _check_and_dispatch_wake helper + wiring in on_step_complete / on_step_failed (UPDATE-RETURNING + pre-assigned rq_job_id + dead-letter fallback)
- [ ] 20-04-PLAN.md — Wave 2: run_task trigger dispatch + invocation lifecycle + V004 prompt with wake-context section
- [ ] 20-05-PLAN.md — Wave 3: startup reconciler module + runner.py boot wiring
- [ ] 20-06-PLAN.md — Wave 3: dashboard Conversation + Outcome rows + REQUIREMENTS.md ticks + manual smoke checkpoint
**UI hint**: yes

### Phase 21: Tool-surface flip + remove acknowledge/notify
**Goal**: Robotina speaks via explicit `respond()`/`terminate()` tools and dispatches N workflows per turn; the legacy `acknowledge-add-recipe` agent and `notify` workflow step are gone.
**Depends on**: Phase 20
**Requirements**: TOOLS-01, TOOLS-02, TOOLS-03, TOOLS-04, TOOLS-05, DASH-11, EXP-05, EVAL-01, EVAL-02, EVAL-03
**Success Criteria** (what must be TRUE):
  1. Single-recipe happy path: "agregá lentejas" → Robotina `respond()`s pre-batch → workflow drains → wake invocation `respond()`s post-batch with recipe link → `terminate()`s. No final-AI-message-content leakage to the user.
  2. `StartWorkflowTool` accepts N calls per turn with `{workflow_type, input}` schema; `return_direct=False`; `invocation_id` is constructor-injected (not mutable state).
  3. `grep -r "acknowledge-add-recipe" src/ tests/ overrides/ experiments/` returns zero hits; AGENT_REGISTRY ↔ `overrides/*.json` CI guard fails the build if they drift.
  4. `notify` workflow step is removed from the add-recipe definition; dashboard task-type label map updated (Spanish labels for new types, removed labels for retired ones); no template regression.
  5. `experiments/acknowledge_add_recipe.py` and its `[project.scripts]` entry are removed; documentation updated.
  6. **Manual multi-call smoke checkpoint**: 5–8 hand-curated Spanish utterances (single-recipe, multi-recipe 2–3 items, compound dish, ambiguous, over-cap) are run once on Ollama `gpt-oss:20b` (local) and once on OpenAI (staging), with the resulting tool-call traces eyeballed and recorded in `.planning/phases/21-*/SMOKE.md` (utterance, backend, expected N, observed N, pass/fail, LangWatch trace link). The file ends with an explicit go/no-go line. If OpenAI staging shows unacceptable reliability, the phase pivots `StartWorkflowTool` to single-call list-form `start-workflow(actions=[{workflow_type, input}, ...])` before merge; Ollama-only failures are noted but do not block merge (dev-only backend).
**Plans**: 8 plans
- [ ] 21-01-PLAN.md — Add RespondTool (non-terminal send-notification enqueue at_front=True) + unit tests
- [ ] 21-02-PLAN.md — Add TerminateTool (return_direct=True, no-arg) + unit tests
- [ ] 21-03-PLAN.md — Refactor StartWorkflowTool to multi-call surface ({workflow_type, input}, return_direct=False) + AddRecipeQueryInput + tests
- [ ] 21-04-PLAN.md — Coupled deletion: jobs.py tool swap, agents.py V004→V005, workflows.py 6-step list, dead-letter block, QueueTool/acknowledge-add-recipe/AcknowledgeAddRecipeInput, overrides entries (D-06 single PR) + repo grep gate
- [ ] 21-05-PLAN.md — V005 Robotina prompt (new tool surface, strict output rule, single-recipe examples; V004 retained)
- [ ] 21-06-PLAN.md — CI guard test: AGENT_REGISTRY ↔ overrides/*.json bidirectional sync + AGENT_REGISTRY content tests
- [ ] 21-07-PLAN.md — Dashboard task-type label map (DASH-11, Jinja-side _macros.html, Spanish labels) + template tests
- [ ] 21-08-PLAN.md — Manual multi-call smoke checkpoint (21-SMOKE.md, Ollama+OpenAI) + REQUIREMENTS.md ticks + doc updates (autonomous=false)
**UI hint**: yes

### Phase 22: Multi-recipe per message (Topic 1)
**Goal**: A single user message naming up to 5 recipes results in N parallel add-recipe workflows and one consolidated final reply summarizing each outcome.
**Depends on**: Phase 21
**Requirements**: BATCH-01, BATCH-02, BATCH-03, BATCH-04, BATCH-05
**Success Criteria** (what must be TRUE):
  1. "agregá canelones, pollo al horno y arroz pilaf" produces 3 `RobotinaInvocation`-linked WorkflowRuns and a single pre-batch `respond()` acknowledging all three.
  2. After all 3 workflows reach terminal status, the wake-invocation reply summarizes each (success: name+slug; failure: brief reason) in user-input order, in one Telegram message.
  3. A partial-failure batch ("2 listos, canelones falló: …") reports cleanly — no silent drops, no all-or-nothing.
  4. A request with > 5 recipes is handled per the prompt's soft cap (asks the user to split, or proceeds with first 5 and notes the cap).
**Plans**: 4 plans
- [x] 22-01-PLAN.md — Wave 1: WorkflowOutcomeSummary.recipe_query + ORDER BY + to_user_message rewrite (BATCH-03/04)
- [x] 22-02-PLAN.md — Wave 1: V006 prompt fork (multi-recipe + ambiguity + over-cap + wake-reply examples) + agents.py bump (BATCH-01/02/05)
- [x] 22-03-PLAN.md — Wave 2: 30-utterance eval set + per-backend harness + result templates
- [ ] 22-04-PLAN.md — Wave 3: Operator smoke checkpoint + conditional REQUIREMENTS.md ticks

### Phase 23: URL ingestion (Topic 2)
**Goal**: A user can paste a recipe URL and have Robotina save that exact recipe, with SSRF/abuse defenses around every URL fetch.
**Depends on**: Phase 22
**Requirements**: URL-01, URL-02, URL-03, URL-04, URL-05, URL-06, EXP-02
**Success Criteria** (what must be TRUE):
  1. `safe_fetch` (the FIRST commit in this phase) rejects all SSRF/abuse vectors in a dedicated test suite: non-HTTPS scheme, RFC1918/loopback/link-local IPs, redirect-chain to internal IP, content-length > 5 MB, content-type/magic-byte mismatch.
  2. "agregá esta receta: https://example/x" routes through `add-recipe-from-url` workflow; `gather-from-url` extracts structured RecipeData via `recipe-scrapers` (`wild_mode=True`) with per-field try/except; downstream steps (instructions/ingredients/metadata/recipe-image/recipe-load) are unchanged.
  3. When `recipe-scrapers` returns insufficient data, the LLM fallback agent re-extracts from raw HTML using the same `RecipeData` schema.
  4. A 20-URL Spanish-recipe-blog eval set runs and achieves ≥85% field-level success at v1.1 ship; results documented.
  5. `uv run experiments.gather_from_url` exercises the pipeline end-to-end with LangWatch traces tagged to the experiment.
**Plans**: TBD

### Phase 24: Recipe images (Topic 3)
**Goal**: Saved recipes have an associated image when one can be acquired; image acquisition failure never blocks recipe save.
**Depends on**: Phase 23 (`safe_fetch` reused)
**Requirements**: IMG-01, IMG-02, IMG-03, IMG-04, IMG-05, IMG-06, EXP-01, EXP-03, EXP-04, EXP-06
**Success Criteria** (what must be TRUE):
  1. The add-recipe pipeline (both query and URL variants) inserts a `recipe-image` step between metadata and `recipe-load` that produces an `image_url` (or empty/sentinel on miss).
  2. The image fallback ladder works: source-page image (recipe-scrapers `.image()`) on URL-sourced inputs → Tavily image search (`include_images=True`) otherwise → mark missing.
  3. The new per-step non-fatal-failure runner capability is declared on `recipe-image`: failure writes a structured "unavailable" artifact and advances the workflow; the recipe still saves; `WorkflowRun.outcome.image_present=False` records the gap.
  4. The image URL is validated via `safe_fetch` before persist (re-uses Phase 23's SSRF defenses); persisted to the household-manager API per the storage strategy decided at planning time.
  5. `uv run experiments.recipe_image` exercises Tavily image search + source-page fallback with LangWatch traces; `experiments.robotina_wake` exercises wake-context Robotina iteration; existing experiment scripts (recipe_research, recipe_load) still run unchanged thanks to default source discriminators; `pyproject.toml` and CLAUDE.md experiment list reflect the new entry points.
**Plans**: TBD

## Progress

| Phase                                                | Milestone | Plans | Status      | Completed  |
| ---------------------------------------------------- | --------- | ----- | ----------- | ---------- |
| 1. Developer Tooling and Infrastructure              | v1.0      | 3/3   | Complete    | 2026-03-25 |
| 2. Database Models and Queue Layer                   | v1.0      | 3/3   | Complete    | 2026-03-25 |
| 3. Gateway                                           | v1.0      | 3/3   | Complete    | 2026-03-26 |
| 4. LLM Module and Agent Infrastructure               | v1.0      | 6/6   | Complete    | 2026-03-27 |
| 5. Task Runner and Workflow Engine                   | v1.0      | 5/5   | Complete    | 2026-03-27 |
| 6. send-notification Agent                           | v1.0      | 4/4   | Complete    | 2026-03-27 |
| 7. handle-incoming-message Agent                     | v1.0      | 4/4   | Complete    | 2026-03-27 |
| 07.1. Deterministic Agent Termination (INSERTED)     | v1.0      | 3/3   | Complete    | 2026-03-30 |
| 8. recipe-research Agent                             | v1.0      | 4/4   | Complete    | 2026-03-30 |
| 9. recipe-load Agent and End-to-End Integration      | v1.0      | 2/2   | Complete    | 2026-05-12 |
| 10. LangChain 1.x Agent API Migration                | v1.0      | 3/3   | Complete    | 2026-05-13 |
| 11. Structured Agent Output via response_format      | v1.0      | 4/4   | Complete    | 2026-05-13 |
| 12. Middleware-Based Agent Instrumentation           | v1.0      | 2/2   | Complete    | 2026-05-14 |
| 13. Queue Visibility Dashboard                       | v1.0      | 3/3   | Complete    | 2026-05-14 |
| 14. Prompt Cleanup and Structural Standardization    | v1.0      | 8/8   | Complete    | 2026-05-14 |
| 15. Recipe Artifact Accumulation                     | v1.0      | 6/6   | Complete    | 2026-05-15 |
| 16. household_id propagation fix                     | v1.0      | 7/7   | Complete    | 2026-05-15 |
| 17. Conversation FK closure                          | v1.1      | 4/4 | Complete   | 2026-05-19 |
| 18. RobotinaInvocation entity                        | v1.1      | 4/4 | Complete    | 2026-05-19 |
| 19. LLM multi-call smoke test                        | v1.1      | 0/0   | Not started | —          |
| 20. Wake rule + outcome plumbing                     | v1.1      | 0/6   | Planned     | —          |
| 21. Tool-surface flip + remove acknowledge/notify    | v1.1      | 0/0   | Not started | —          |
| 22. Multi-recipe per message                         | v1.1      | 3/4 | In Progress|  |
| 23. URL ingestion                                    | v1.1      | 0/0   | Not started | —          |
| 24. Recipe images                                    | v1.1      | 0/0   | Not started | —          |

## Backlog

Unsequenced ideas that aren't ready for active planning. Promote with `/gsd-review-backlog` when promotion criteria are met.

### Phase 999.1: Custom state schemas for reply_context and household_id (BACKLOG)

**Goal:** Lift `reply_context: ReplyContext` and `household_id: str` from per-task `*Input` Pydantic models into a typed `AgentState` schema passed to `create_agent(state_schema=...)`. Tools access these via `InjectedState` rather than runtime kwargs. The job dispatcher in `run_task()` (`src/robotina/queue/jobs.py`) maps `WorkflowRun.shared_context` -> agent state at invocation time.

**Why this is a backlog item, not an active phase:** This refactor changes the contract between the workflow runner / job dispatcher and the agent -- a meaningful structural shift. Real ergonomic value (removes the "thread `household_id` through every `*Input` model and every tool signature" plumbing) but no current production pain forces it. Adding new ambient fields today is annoying-but-rare, not blocking. v1.1's FK closure (Phase 17) reduces but does not eliminate the threading pressure.

**Requirements:** TBD

**Depends on:** Phase 10 (requires `langchain.agents.create_agent`; `langgraph.prebuilt.create_react_agent` does not cleanly support `state_schema=`). Independent of Phases 11 and 12 -- they make this phase nicer when promoted, but neither requires it.

**Promotion criteria** -- promote to an active phase via `/gsd-review-backlog` when ANY of:
  1. Three or more tools need ambient context (currently only `household_id` is threaded; if `user_id`, `locale`, or workflow-scoped flags get added, this triggers)
  2. Adding a new ambient field becomes a recurring chore (touched in 2+ phases of work over a quarter)
  3. A future phase wants middleware that needs typed state reads (Phase 12 follow-on, e.g. enriching spans with `reply_context.platform` automatically)

**Scope estimate when promoted:** 1-2 days. Touches: agent construction in `src/robotina/llm/__init__.py` (3 backends); tool signatures (`household_manager_api.py`, `queue.py`, `start_workflow.py`, `web_search.py`); job dispatcher in `src/robotina/queue/jobs.py`; the 4 test files that build real agents.

**Source decision:** Sequencing discussion 2026-05-12, conversation following the canelones de choclo parse failure analysis (2026-05-13 logs). User opted to land A/B/C (Phases 10/11/12) and defer D as backlog.

**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)
