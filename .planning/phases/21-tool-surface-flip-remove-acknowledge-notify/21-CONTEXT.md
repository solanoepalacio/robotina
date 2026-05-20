# Phase 21: Tool-surface flip + remove acknowledge/notify - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning
**Mode:** `--auto` (system reminder asked the discuss workflow to make reasonable
calls without stopping; every D-NN below is Claude's call with rationale — the
user can redirect any decision before `/gsd:plan-phase 21` runs.)

<domain>
## Phase Boundary

Flip Robotina's tool surface from the legacy "single-call terminal" pattern to
the new "Robotina-as-decider" surface. Concretely:

1. **Add `RespondTool`** — Robotina sends Spanish replies to the user by enqueuing a `send-notification` job at the front of the queue (mirrors the existing pattern; inherits AOF persistence). Non-terminal — Robotina can call it before/after `start-workflow` and continue.
2. **Add `TerminateTool`** — explicit `return_direct=True` termination. The prompt forbids trailing assistant text outside `respond()` / `terminate()`.
3. **Refactor `StartWorkflowTool`** — drop `return_direct=True`; new `{workflow_type, input}` schema; multi-call allowed; `invocation_id` stays constructor-injected (per Phase 18 D-13).
4. **Delete `acknowledge-add-recipe`** entirely — agent, prompt directory, registry entry, task type, workflow step, dashboard label entry, every `overrides/*.json` reference. Add a CI check enforcing AGENT_REGISTRY task types ↔ every `overrides/*.json` stay in sync.
5. **Delete `notify` step** from the `add-recipe` workflow definition — Robotina now closes the loop via `respond()` on wake. Also delete the dead-letter `send-notification` block in `on_step_failed` (Phase 20 D-05 kept it as a transitional fallback; Phase 21's working wake-respond path supersedes it).
6. **Introduce dashboard task-type label map** (DASH-11) — Spanish labels for the active task types, with retired types (`acknowledge-add-recipe`, `notify`) absent. Template tests guard against unknown task-type fallbacks producing raw enum values.
7. **Robotina prompt V005** — teaches the new tool surface (`respond` + `start-workflow` callable N times + `terminate`), multi-recipe extraction stays out of scope (BATCH is Phase 22).
8. **Remove `experiments/acknowledge_add_recipe.py`** if it exists, drop the `[project.scripts]` entry, update PROJECT.md / README experiment list. Current grep shows no such file in `experiments/` (only `recipe_load.py`, `recipe_research.py`) — EXP-05 is mostly a doc-only cleanup.
9. **Manual multi-call smoke checkpoint (EVAL-01..03)** — 5-8 hand-curated Spanish utterances exercised against Ollama `gpt-oss:20b` (local dev) AND OpenAI (staging). Results land in `21-SMOKE.md` with a go/no-go line. If OpenAI staging shows unacceptable reliability, the phase pivots `StartWorkflowTool` to single-call list-form `start-workflow(actions=[{workflow_type, input}, ...])` BEFORE merge. Ollama-only failures are noted but do NOT block merge (dev-only backend).

**In scope (mapped to plans 21-01..21-08-ish, planner decides):**

- New tool `src/robotina/agent/tools/respond.py` (`RespondTool`).
- New tool `src/robotina/agent/tools/terminate.py` (`TerminateTool`).
- `src/robotina/agent/tools/start_workflow.py` — drop `return_direct=True`; refactor schema to `{workflow_type, input}` with `Literal["add-recipe"]` for now (Phase 23 extends with `add-recipe-from-url`).
- `src/robotina/queue/jobs.py` — replace `QueueTool` injection with `RespondTool` + `TerminateTool` injection for Robotina; delete the `acknowledge-add-recipe` elif branch (lines ~191–272).
- `src/robotina/agent/agents.py` — delete the `acknowledge-add-recipe` registry entry; Robotina prompt path bumps V004 → V005.
- `src/robotina/agent/workflows.py` — remove the `acknowledge` step (step_key around line 102) AND the `notify` step (step_key around line 157). Workflow becomes: `gather → instructions → ingredients → metadata → load → finalize-outcome`. `finalize-outcome` is now the only post-`load` step.
- `src/robotina/queue/workflow_runner.py` — delete the dead-letter `send-notification` block in `on_step_failed` (Phase 20 wrapped it in try/except as a fallback; Phase 21 removes the block entirely now that Robotina speaks via `respond()` on wake).
- `src/robotina/agent/prompts/robotina/V005.md` — new prompt teaching the tool surface. V004 retained for rollback.
- Delete `src/robotina/agent/prompts/acknowledge-add-recipe/` directory entirely.
- `src/robotina/queue/task_types.py` — delete `AcknowledgeAddRecipeInput`. Keep `SendNotificationInput` (still used by `RespondTool`'s enqueue path).
- `overrides/anthropic.json`, `overrides/openai.json`, `overrides/staging.ollama.json` — remove the `acknowledge-add-recipe` entries from each. Same commit as the agent registry deletion (per memory `feedback_overrides_in_sync.md`).
- New CI guard test: `tests/agents/test_registry_override_sync.py` asserts every key in every `overrides/*.json` exists in `AGENT_REGISTRY` AND every key in `AGENT_REGISTRY` exists in every `overrides/*.json`. Per TOOLS-04.
- Dashboard label map (DASH-11): introduce in `src/robotina/dashboard/templates/_macros.html` (or wherever the kv-grid lives) as a Jinja dict `{ "gather": "Búsqueda", "instructions": "Instrucciones", "ingredients": "Ingredientes", "metadata": "Metadatos", "load": "Guardar", "finalize-outcome": "Cierre del flujo" }` (planner picks final Spanish phrasing). NO entry for `acknowledge-add-recipe` or `notify` — they're gone. Template tests guard against unknown task-type fallbacks producing raw enum values.
- `experiments/` cleanup: no `acknowledge_add_recipe.py` to delete (grep confirmed). PROJECT.md / README experiment list updated to reflect the new active set (recipe_research, recipe_load remain; finalize-outcome/wake context noted for Phase 24 experiments).
- `pyproject.toml` `[project.scripts]` — remove any `experiments.acknowledge_add_recipe` entry if present; otherwise no change.
- **Manual smoke `21-SMOKE.md`** committed before merge per EVAL-03.

**Out of scope (deferred):**
- Multi-recipe LLM extraction behavior (BATCH-*) — **Phase 22**. Phase 21 makes the tool surface multi-call-CAPABLE; Phase 22 teaches Robotina to USE it for multi-recipe extraction.
- URL ingestion + `safe_fetch` + `gather-from-url` (URL-*) — **Phase 23**. Phase 21's `StartWorkflowTool.workflow_type` Literal stays as `Literal["add-recipe"]` for now.
- `recipe-image` step (IMG-*) — **Phase 24**.
- New experiment scripts for `gather_from_url`, `recipe_image`, `robotina_wake` (EXP-02, EXP-03, EXP-04) — **Phase 23 / 24** respectively. EXP-05 (removal of `acknowledge_add_recipe`) IS in Phase 21 because it's coupled to the agent deletion.
- Compose Agent refactor (`COMP-01`) — v2.
- `parallel_tool_calls=False` provider binding — future hardening. Phase 21 ships with the default per-provider behavior (OpenAI parallel, Anthropic parallel, Ollama varies). Multi-recipe ordering isn't strict for Phase 22 either.

</domain>

<decisions>
## Implementation Decisions

> **Auto-mode note:** Every D-NN below is Claude's call under the no-stopping
> system reminder. The user can redirect any decision before `/gsd:plan-phase 21` runs.

### Tool surface shape

- **D-01: `RespondTool` enqueues a `send-notification` job at_front=True**, does NOT send to Telegram directly. Mirrors the existing `QueueTool` pattern (per memory `feedback_queue_at_front`). The tool returns immediately with the enqueued `job_id`. Persistence inherits AOF + `result_ttl=-1` semantics. The tool is **non-terminal**: `return_direct=False`. Tool args: `text: str` (the Spanish reply). Constructor-injected fields: `chat_id`, `user_id`, `platform`, `household_id` (same as `QueueTool` today).
  - **Why not call Telegram synchronously:** PITFALL 13 — `asyncio.run()` inside a sync RQ job opens a new event loop per invocation, brittle and slow. Queue-based send preserves the existing sync/async boundary discipline and lets Phase 6's existing send pipeline do its job.
  - **Why non-terminal:** the new flow is `respond("voy con lentejas") → start-workflow(...) → terminate()`. If `respond()` were `return_direct=True`, the graph would terminate before `start-workflow` runs.

- **D-02: `TerminateTool` is `return_direct=True`** and takes NO args (`terminate()`). Its `_run` returns a sentinel string ("turn complete" or similar) that the engine ignores because of `return_direct=True`. Engine-enforced termination point per PITFALL 4.
  - The Robotina prompt MUST instruct: "After your last tool call, call `terminate()`. Do not write user-facing text in your final assistant message — `respond()` is the ONLY user-visible channel."

- **D-03: `StartWorkflowTool` keeps constructor injection unchanged.** Phase 18 D-13 already constructor-injects `invocation_id`; Phase 17 D-03 already constructor-injects `conversation_id`; Phase 16 already constructor-injects `household_id` via `NonEmptyHouseholdId`. Phase 21's diff is:
  - `return_direct: bool = False` (was True).
  - New `args_schema`:
    ```python
    class StartWorkflowArgs(BaseModel):
        model_config = ConfigDict(extra="forbid")
        workflow_type: Literal["add-recipe"]  # Phase 23 extends to ["add-recipe-from-query", "add-recipe-from-url"]
        input: AddRecipeQueryInput  # for now; Phase 23 makes this a discriminated union
    ```
  - New input model `AddRecipeQueryInput { value: str }` in `task_types.py` (semantic: the recipe query). The current legacy field `recipe_query: str` flat on `shared_context` is replaced by this typed object inside the tool args. The tool's `_run` unwraps it: `recipe_query = input.value`.
  - **Why keep `Literal["add-recipe"]` instead of pivoting to URL discriminator now:** scope. Phase 21 is the tool-surface flip, not the URL surface (Phase 23). Adding the URL variant prematurely couples two big refactors.

- **D-04: Multi-call surface is enabled by `return_direct=False`** (TOOLS-01). No code change beyond the flag flip — the agent's ReAct loop naturally accumulates tool calls. Phase 21's smoke checkpoint validates this works on Ollama AND OpenAI. Phase 22's prompt then teaches Robotina to extract N recipes per message; Phase 21's prompt does NOT need to teach multi-recipe extraction (V005 supports it implicitly via the surface but the example utterances stay single-recipe to keep the EVAL smoke focused on tool-surface correctness, not LLM behavior).

- **D-05: `QueueTool` is deleted** entirely. `RespondTool` is its replacement. Greps in `src/robotina/agent/tools/queue.py` and any imports of `QueueTool` MUST return zero hits after Phase 21. The `feedback_queue_at_front` memory continues to apply — `RespondTool` carries the `at_front=True` invariant verbatim (it's the same queue-hop, just behind a new class name).

### Acknowledge + notify removal

- **D-06: Single PR removes both `acknowledge-add-recipe` AND `notify` step.** PITFALL 10 — split removal leaves orphan dependencies. Same commit MUST update:
  - `src/robotina/agent/agents.py` (delete `"acknowledge-add-recipe": AgentConfig(...)`)
  - `src/robotina/agent/workflows.py` (delete `step_key="acknowledge"` and `step_key="notify"` entries)
  - `src/robotina/agent/prompts/acknowledge-add-recipe/` directory (delete entirely)
  - `src/robotina/queue/jobs.py` (delete the `acknowledge-add-recipe` elif branch and the `task_type == "send-notification"` handling for the legacy `notify` step — `RespondTool`-enqueued send-notification jobs still work via the same task_type branch; only the workflow `notify` step is gone)
  - `src/robotina/queue/task_types.py` (delete `AcknowledgeAddRecipeInput`)
  - `overrides/anthropic.json`, `overrides/openai.json`, `overrides/staging.ollama.json` (remove `acknowledge-add-recipe` entries)
  - Dashboard label map (don't add the entries in the first place — D-11)

- **D-07: Wait — `send-notification` task_type STAYS.** Robotina's `RespondTool` enqueues `send-notification` jobs. `run_task`'s `if task_type == "send-notification":` branch (jobs.py line 90) MUST stay — it's how Phase 6's deterministic send happens. The thing being deleted is the `notify` STEP in the `add-recipe` workflow (which uses the `send-notification` task type). Subtle distinction; the planner must NOT conflate them.

- **D-08: Delete the dead-letter `send-notification` block in `on_step_failed`** entirely in Phase 21. Phase 20 D-05 kept it as a try/except fallback for wake-enqueue failure. Now that:
  - The Robotina wake turn has `respond()` (Phase 21 D-01),
  - The V005 prompt teaches Robotina to apologize on `outcome.status == "failure"` summaries,
  - The reconciler (Phase 20 D-11) catches wake-enqueue crashes structurally,
  …the dead-letter block is redundant. Removing it simplifies `on_step_failed` to its core: mark FAILED, call `_check_and_dispatch_wake`, commit. The try/except around the wake-helper stays for logging; the except branch is now just `logger.exception(...)`, no fallback send-notification.

### Robotina prompt V005

- **D-09: V005 is V004 + the new tool surface.** V004 stays for rollback. V005 teaches:
  - Three tools available: `respond(text)`, `start-workflow(workflow_type, input)`, `terminate()`.
  - **Output rule:** "All user-facing messages MUST go through `respond()`. After your last tool call, call `terminate()`. Do not write user-facing text in your final assistant message."
  - **Happy path (single-recipe):** `respond("Listo, voy con lentejas")` → `start-workflow(workflow_type="add-recipe", input={value: "lentejas"})` → `terminate()`. On wake: `respond("Lista guardada: lentejas (recipe-id abc123)")` → `terminate()`.
  - **Wake-context happy path:** when invoked with the wake-context preamble, compose a Spanish reply from `outcomes`, call `respond(text)`, then `terminate()`. Phase 20's V004 said "you may reflect but cannot speak" — V005 reverses that: speaking via `respond()` is the whole point.
  - **Wake-context failure path:** when an outcome's status is "failed", compose a Spanish apology including the `failure_reason`. Single `respond()` covers all outcomes; do not call `respond()` once per outcome (Telegram message spam).
  - **Multi-recipe path stays minimal in V005** — the prompt mentions "you may receive a multi-recipe message; emit one `start-workflow` per recipe" but the worked examples stay single-recipe to keep Phase 21's smoke checkpoint focused. Phase 22's V006 expands with multi-recipe examples + the over-cap rule.
  - **Forbidden behavior:** writing recipe data in `respond()` (Robotina doesn't know what was saved until wake), calling `respond()` AFTER `terminate()`, omitting `terminate()`.
  - Spanish user-facing text (per memory `feedback_prompts_language`); system prompt body in English.

- **D-10: `agents.py` bumps `handle-incoming-message` prompt_path** from `V004.md` to `V005.md`. Same one-line edit pattern as Phase 20's V003 → V004 bump.

### Dashboard task-type label map (DASH-11)

- **D-11: First introduction of the label map.** Phase 20 confirmed no label map currently exists. Phase 21 introduces it as a Jinja-side dict (NOT a Python-side import — keeps the dashboard module-isolation rule from Phase 13 D-01 intact). Suggested location: `src/robotina/dashboard/templates/_macros.html` as a `{% set TASK_TYPE_LABELS = { ... } %}` block, then a macro `task_type_label(t)` that returns `TASK_TYPE_LABELS.get(t, t)`.
  - **Initial entries (Spanish):**
    ```
    "gather":             "Búsqueda"
    "instructions":       "Instrucciones"
    "ingredients":        "Ingredientes"
    "metadata":           "Metadatos"
    "load":               "Guardar"
    "finalize-outcome":   "Cierre del flujo"
    "handle-incoming-message": "Robotina (mensaje)"
    ```
  - **NOT in the map:** `acknowledge-add-recipe`, `notify` (legacy `notify` STEP is gone — but `send-notification` task type stays as the underlying RespondTool delivery mechanism; if the dashboard surfaces RobotinaInvocation-driven send-notification jobs, the label is `"send-notification": "Notificación"` — planner decides whether to include).
  - **Phase 23 / 24** add: `"gather-from-url": "Búsqueda por URL"`, `"recipe-image": "Imagen de la receta"`. Not in Phase 21.
  - **Template test (DASH-11):** asserts that rendering a WorkflowRunStep with `task_type="gather"` produces "Búsqueda" in the output; asserts that rendering an unknown task_type produces the raw enum value (fallback) so the test catches missing-label regressions explicitly rather than silently rendering raw enums elsewhere.

### CI guard for AGENT_REGISTRY ↔ overrides

- **D-12: New test `tests/agents/test_registry_override_sync.py`** asserts bidirectional set equality between `AGENT_REGISTRY.keys()` and the keys of each `overrides/*.json`. Per TOOLS-04 + memory `feedback_overrides_in_sync`.
  - **Why a unit test, not a `gsd-sdk` gate:** unit tests run on every CI invocation; project-local invariants belong in pytest. A `gsd-sdk` gate would be an out-of-band check most contributors miss.
  - **Test loop:**
    ```python
    @pytest.mark.parametrize("overrides_file", list(Path("overrides").glob("*.json")))
    def test_overrides_match_registry(overrides_file):
        from robotina.agent.agents import AGENT_REGISTRY
        with overrides_file.open() as f:
            overrides = json.load(f)
        assert set(overrides.keys()) == set(AGENT_REGISTRY.keys()), \
            f"{overrides_file.name} drifted from AGENT_REGISTRY"
    ```
  - This test FAILS today (overrides have `acknowledge-add-recipe`, AGENT_REGISTRY has it too — they match). The deletion commit removes the entries from both in lockstep; the test stays green throughout. The CI value is preventing FUTURE drift, not catching current state.

### Smoke checkpoint EVAL-01..03

- **D-13: `21-SMOKE.md` is committed last** — after all code changes land and tests pass, the operator runs the smoke set. File structure:
  ```markdown
  # Phase 21 Multi-call Smoke Results

  **Backends:** Ollama gpt-oss:20b (local), OpenAI (staging)
  **Date:** <YYYY-MM-DD>
  **Operator:** <name>

  | # | Utterance (Spanish) | Expected N | Ollama N | Ollama OK? | OpenAI N | OpenAI OK? | LangWatch traces |
  |---|---|---|---|---|---|---|---|
  | 1 | agregá lentejas | 1 | | | | | |
  | 2 | agregá canelones y pollo | 2 | | | | | |
  | 3 | agregá canelones, pollo y arroz | 3 | | | | | |
  | 4 | agregá pollo al horno con papas | 1 or 2 (ambiguous — note which) | | | | | |
  | 5 | agregá canelones, pollo, arroz, lentejas, milanesas, salmón | over-cap (>5) — should split or reject | | | | | |

  ## Go / No-Go

  Ollama: <PASS/FAIL — notes>
  OpenAI: <PASS/FAIL — notes>

  Decision: <GO with current schema / NO-GO — pivot to list-form before merge>
  ```
- **D-14: Eval set sizing.** Per EVAL-02: 5-8 utterances minimum, covering 1 single-recipe + 2 multi-recipe (2-3 items) + 1 compound dish + 1 ambiguous + 1 over-cap. Phase 21's planner picks the exact set; the table above is a suggestion. PITFALL 12 has more utterance ideas if the operator wants to expand.
- **D-15: Pivot path** per EVAL-03: if OpenAI staging shows unacceptable multi-call reliability, pivot to single-call list-form `start-workflow(actions=[{workflow_type, input}, ...])` BEFORE merge. The pivot is small: change `args_schema` from `{workflow_type, input}` to `{actions: list[{workflow_type, input}]}` and update the `_run` loop. V005 prompt examples update accordingly. The smoke set re-runs. This is the explicit fallback baked into Phase 21's risk model.
- **D-16: No automated harness.** EVAL-01 explicitly says no automated test runner — the operator runs the agent against each utterance, inspects tool-call traces in LangWatch / the dashboard, and records the result.

### Test strategy (Claude's Discretion)

- **D-17: Tool unit tests:**
  - `tests/agents/tools/test_respond_tool.py` — `RespondTool` enqueues a `send-notification` job with `at_front=True`; returns job_id; constructor args propagate.
  - `tests/agents/tools/test_terminate_tool.py` — `TerminateTool` is `return_direct=True`; `_run` returns the sentinel.
  - `tests/agents/tools/test_start_workflow_tool.py` — updated for `return_direct=False`; new args_schema with `{workflow_type, input}`; constructor injection unchanged; multi-call (sequential) does N independent enqueues.

- **D-18: Agent surface integration test** (mocked LLM): `run_task` for a `handle-incoming-message` job with USER_MESSAGE invocation produces the new tool set (RespondTool, StartWorkflowTool, TerminateTool, HouseholdManagerApiTool); no `QueueTool` reference anywhere; no `acknowledge-add-recipe` branch.

- **D-19: Workflow registry test:** `WORKFLOW_REGISTRY['add-recipe'].steps` has exactly 6 step_keys in order: `gather`, `instructions`, `ingredients`, `metadata`, `load`, `finalize-outcome`. NO `acknowledge`, NO `notify`.

- **D-20: AGENT_REGISTRY tests:**
  - `AGENT_REGISTRY` has NO `acknowledge-add-recipe` entry.
  - `handle-incoming-message` agent loads `V005.md`.

- **D-21: CI guard test (D-12)** — bidirectional set equality between AGENT_REGISTRY and each `overrides/*.json`.

- **D-22: Dashboard label test (DASH-11)** — render a step with `task_type="gather"` → "Búsqueda" appears; render with `task_type="unknown-task"` → raw enum fallback; render with `task_type="acknowledge-add-recipe"` → falls into the fallback path (proves the legacy label is gone).

- **D-23: Repo grep gate** (in the deletion plan's verify block, not a permanent test): `! grep -rn "acknowledge-add-recipe" src/ tests/ overrides/ experiments/` returns zero hits after the deletion commit. Required by ROADMAP success-criterion #3 verbatim.

- **D-24: Manual smoke** (EVAL-01..03) is NOT an automated test. Operator runs it; commits `21-SMOKE.md`; phase verification routes as `human_needed` until the operator marks the file `verdict: pass`.

- **D-25: Single-recipe regression smoke** (still automated): an existing test like `tests/test_workflows.py::test_add_recipe_happy_path` (or wherever the existing happy-path lives) should be updated to assert the new step list (6 steps, no acknowledge/notify) and the new tool injection shape. PITFALL 4 / 5 risk-mitigation.

### Claude's Discretion

- **Tool file naming:** `src/robotina/agent/tools/respond.py` and `src/robotina/agent/tools/terminate.py`. Co-located with existing tools (`queue.py`, `start_workflow.py`, `household_manager_api.py`).
- **`QueueTool` deletion:** delete `src/robotina/agent/tools/queue.py` in the SAME commit as the `RespondTool` introduction. Update any imports (`from robotina.agent.tools.queue import QueueTool` in `jobs.py`) to import `RespondTool` instead.
- **`RespondTool` reuse of `SendNotificationInput`:** the tool's `_run` builds a `SendNotificationInput(chat_id, user_id, platform, text)` and enqueues via the existing queue path. NO new task_type. `SendNotificationInput` stays in `task_types.py`.
- **`StartWorkflowTool` new input model placement:** `AddRecipeQueryInput { value: str }` in `task_types.py` alongside `RecipeResearchInput`. Could be inlined in `start_workflow.py` instead, but co-locating with other task_types is the project convention.
- **V005 prompt versioning:** keep V003 / V004 / V005 all in repo. V005 is loaded by Phase 21's agents.py edit. The older versions are git-tracked rollback points.
- **Dashboard label rendering:** if the existing dashboard renders `step.task_type` raw today, the planner identifies the template line and wraps it in `{{ task_type_label(step.task_type) }}`. Same approach for any list/detail view that shows task types.
- **Tests directory placement:** new tool tests go under `tests/agents/tools/` if that directory exists, else `tests/unit/`. Match existing project convention by grepping for existing tool test locations.
- **Smoke results commit:** committed AFTER the code/CI commits land (so the smoke is run against the final state). One commit per smoke run; if OpenAI staging fails, the pivot commit lands BEFORE the SMOKE.md update.
- **Dead-letter block removal:** straight deletion in `workflow_runner.py::on_step_failed`. Tests that asserted dead-letter fires under specific conditions (Phase 20's `tests/test_workflow_runner.py` updates per 20-03's deviation note) are simplified to assert wake-helper is called and the FAILED status is committed atomically. The "dead-letter fires when wake raises" tests become "wake-helper exception is logged and swallowed" tests — the dead-letter expectation goes away.
- **PROJECT.md update:** the "Project" section lists experiments. After Phase 21, mention `recipe_research`, `recipe_load` (and Phase 23 will add `gather_from_url`, etc.). No mention of `acknowledge_add_recipe` (it's gone). One-line edit.
- **README update:** if README references the agent set or experiment list, sync. Otherwise no change.
- **No new env vars** anticipated.
- **No new Alembic revision** — Phase 21 is pure code refactor. No schema changes.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 21: Tool-surface flip + remove acknowledge/notify" — phase goal, 6 success criteria, dependency on Phase 20.
- `.planning/REQUIREMENTS.md` TOOLS-01..05, DASH-11, EXP-05, EVAL-01..03 — the ten requirements this phase delivers.

### Architecture and pitfalls (load-bearing context)
- `.planning/research/ARCHITECTURE.md` §"Phase E — Robotina-as-decider tool surface" — files touched, exit criteria, risk profile. Phase 21 IS Phase E with the ROADMAP's renumbering.
- `.planning/research/ARCHITECTURE.md` §2.6 "StartWorkflowTool refactor table" — the today vs target comparison for the schema flip.
- `.planning/research/ARCHITECTURE.md` §2.7 "Robotina prompt diff" — V004/V005 evolution guidance.
- `.planning/research/ARCHITECTURE.md` §2.3 "jobs.py diff" — RespondTool/TerminateTool injection, acknowledge-add-recipe elif deletion.
- `.planning/research/ARCHITECTURE.md` §2.5 "workflows.py diff" — acknowledge + notify deletion shape (Phase 21 implements; the doc framed it for the full milestone).
- `.planning/research/PITFALLS.md` Pitfall 4 "`return_direct=True` removal lets LLM text leak" — `terminate()` is the engine-enforced termination point; prompt forbids trailing AI text.
- `.planning/research/PITFALLS.md` Pitfall 5 "create_agent does not let us disable parallel tool calls" — multi-call ordering is provider-dependent; Phase 21's smoke checkpoint validates Ollama AND OpenAI; constructor-injected `invocation_id` (Phase 18 D-13) avoids race conditions.
- `.planning/research/PITFALLS.md` Pitfall 10 "Removing acknowledge-add-recipe step leaves orphan dependencies" — repo-wide grep + override sync are the structural guards.
- `.planning/research/PITFALLS.md` Pitfall 13 "respond() is synchronous but Telegram is async" — `RespondTool` enqueues via send-notification, doesn't call Telegram inline.

### Prior phase context (carries forward — do NOT re-decide)
- `.planning/phases/20-wake-rule-outcome-plumbing/20-CONTEXT.md` — Phase 20 decisions. Phase 21 inherits:
  - D-04 (single `_check_and_dispatch_wake` helper) — Phase 21 doesn't change it.
  - D-05 (dead-letter fallback) — Phase 21 REVERSES this: deletes the block now that wake-respond works.
  - D-07 (run_task branches on invocation.trigger) — Phase 21 doesn't change the dispatch logic; new tool injection happens inside the branch.
  - D-09 (V004 prompt) — Phase 21 supersedes with V005.
  - D-13 (DASH-12 outcome cell) — Phase 21 doesn't change the outcome cell; the new label map (D-11) is alongside it.
- `.planning/phases/18-robotinainvocation-entity/18-CONTEXT.md` — Phase 18 decisions, especially:
  - D-13 (constructor-injected `invocation_id` on StartWorkflowTool) — KEEP. Phase 21's schema change does NOT mutate the injection pattern.
- `.planning/phases/17-conversation-fk-closure/17-CONTEXT.md` D-03/D-04 — constructor-injected `conversation_id`. KEEP.
- `.planning/phases/16-fix-empty-string-household-id-propagation-through-gateway-an/` — `NonEmptyHouseholdId` pattern. KEEP on the new `StartWorkflowTool`.
- `.planning/phases/13-queue-visibility-dashboard/13-CONTEXT.md` D-01 — module-isolation rule. The new dashboard label map MUST live Jinja-side, not via a Python-side import from outside the dashboard module.
- `.planning/phases/06-send-notification-agent/` — `send-notification` task_type stays as `RespondTool`'s delivery mechanism. Read the SUMMARY for the queue-hop pattern.
- `.planning/phases/07.1-deterministic-agent-termination-make-termination-a-runtime-g/07.1-CONTEXT.md` (if exists) — original `return_direct=True` decision. Phase 21 supersedes for `StartWorkflowTool` AND `QueueTool` (QueueTool deleted). `TerminateTool` is the new `return_direct=True` carrier.

### Existing codebase contracts (current state — Phase 20 landed)
- `src/robotina/agent/tools/queue.py` — `QueueTool` with `return_direct=True`. DELETE entirely in Phase 21.
- `src/robotina/agent/tools/start_workflow.py` — `return_direct=True`, `args_schema=StartWorkflowArgs` with `workflow_type: Literal["add-recipe"]`, `recipe_query: str` flat. REFACTOR per D-03.
- `src/robotina/agent/agents.py` — `AGENT_REGISTRY["acknowledge-add-recipe"]` exists (line 180+); `handle-incoming-message` agent loads `V004.md` (Phase 20 D-10). Phase 21 DELETES the acknowledge entry and bumps V004 → V005.
- `src/robotina/agent/workflows.py::WORKFLOW_REGISTRY['add-recipe']` — step list (lines 102-167): acknowledge → gather → instructions → ingredients → metadata → load → notify → finalize-outcome. Phase 21 deletes step 0 (acknowledge) and step 6 (notify). Final list: gather → instructions → ingredients → metadata → load → finalize-outcome.
- `src/robotina/queue/jobs.py` — line 90 `if task_type == "send-notification":` STAYS. Line ~134-188 (`handle-incoming-message` branch) — tool injection changes: QueueTool → RespondTool + TerminateTool; StartWorkflowTool unchanged from injection-pattern perspective. Line ~191-272 (`acknowledge-add-recipe` elif branch + QueueTool import) — DELETE entirely.
- `src/robotina/queue/workflow_runner.py::on_step_failed` — dead-letter block (Phase 20 wrapped in try/except per D-05). Phase 21 DELETES the dead-letter block; the except branch becomes log-only.
- `src/robotina/agent/prompts/robotina/V004.md` — current Robotina prompt. Fork to V005.
- `src/robotina/agent/prompts/acknowledge-add-recipe/V002.md` — the to-be-deleted prompt.
- `src/robotina/queue/task_types.py::AcknowledgeAddRecipeInput` (line ~294-310) — DELETE. Keep `SendNotificationInput`.
- `overrides/anthropic.json`, `overrides/openai.json`, `overrides/staging.ollama.json` — all contain `acknowledge-add-recipe` blocks. DELETE from each (same commit).
- `src/robotina/dashboard/templates/workflow.html` — Phase 20 added Conversation + Outcome rows. Phase 21 wraps `step.task_type` rendering in `task_type_label()` macro.
- `src/robotina/dashboard/templates/` — new `_macros.html` (or extend existing) with the label map (D-11).
- `experiments/` — no `acknowledge_add_recipe.py` (grep confirmed). EXP-05 is doc-only.
- `pyproject.toml` `[project.scripts]` — verify no `experiments.acknowledge_add_recipe` entry; if present, remove (per EXP-05 + EXP-06).
- `PROJECT.md` — experiment list line; update to reflect post-acknowledge active set.

### Project conventions
- `CLAUDE.md` "Tech Stack" — Pydantic v2, LangChain 1.x `create_agent`, `QueueTool` already documented as being on the way out.
- Memory `feedback_queue_at_front` — `RespondTool` MUST use `at_front=True` (load-bearing for ordering).
- Memory `feedback_overrides_in_sync` — applied at D-06 (single PR with overrides) and D-12 (new CI test).
- Memory `feedback_prompts_language` — V005 prompt body in English; user-facing text Spanish. `respond()` examples in the prompt use Spanish.
- Memory `feedback_test_before_handoff` — Phase 21 has both an automated regression smoke (single-recipe happy path) AND the manual multi-backend smoke (EVAL-01..03). Both must run before reporting Phase 21 complete.
- Memory `feedback_no_task_id_in_code` — no "Phase 21" / "Quick task" tags in code/comments/docstrings. D-NN refs in comments are durable design refs and allowed.
- Memory `project_compose_agent_vision` — Phase 21 brings Robotina closer to the eventual Compose-agent split, but V005 keeps Robotina as both decider AND composer. The separation is v2 (COMP-01).
- Memory `feedback_avoid_premature_abstraction` — `StartWorkflowTool` stays as-is structurally; only the args_schema flips. Don't introduce a tool factory or generic dispatcher.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 6 `send-notification` deterministic branch + Phase 7.1 `QueueTool` at_front pattern** — `RespondTool` is literally `QueueTool` with `return_direct=False` and a Spanish-text-only contract. The internal `_run` is nearly identical (build `SendNotificationInput`, enqueue at_front, return job_id).
- **Phase 7.1 `return_direct=True` on terminal tools** — `TerminateTool` reuses this pattern, applied to a no-op tool whose only purpose is engine-enforced termination.
- **Phase 18 constructor-injection pattern on tools (`invocation_id`, `conversation_id`, `household_id`)** — `RespondTool` and `TerminateTool` inherit the same shape. `chat_id`, `user_id`, `platform`, `household_id` injected from `run_task`.
- **Phase 11 `_extract_task_output` strict rejection of free-text final messages** — Phase 21's V005 prompt teaches Robotina to NEVER write final-message text; the existing strict path catches violations as a defensive layer.
- **Phase 20 V004 prompt structure (English body, Spanish user-facing examples)** — V005 forks V004's structure verbatim and adds the new tool sections.
- **Existing test patterns under `tests/agents/tools/test_*.py` (if present) or `tests/unit/test_*_tool.py`** — copy the StartWorkflowTool test shape for RespondTool and TerminateTool.
- **Phase 20 finalize-outcome step (D-02 transitional append)** — Phase 21 doesn't move it. The step list reorders by deletion (acknowledge gone from front, notify gone from middle-end), leaving finalize-outcome where it is at the tail.

### Established Patterns
- **`AGENT_REGISTRY` dict structure** in `agents.py` — adding/removing entries is straight dict manipulation. The CI guard (D-12) enforces sync with overrides going forward.
- **Tool registration via `tools=[]` + per-job injection in `run_task`** — no global tool registry. Phase 21 adds two tool classes; `run_task` for `handle-incoming-message` injects the new set.
- **`overrides/*.json` keys mirror `AGENT_REGISTRY` keys** — pre-Phase-21 invariant. Phase 21 adds the test that enforces this going forward.
- **`Mapped[Optional[X]]` + `nullable=True`** — N/A in Phase 21 (no schema changes).
- **Module-isolation grep gate (Phase 13 D-01)** — dashboard label map MUST be Jinja-side. Tests/dashboard/test_independence.py continues to pass.
- **Spanish user-facing strings** — V005 prompt examples + dashboard label values + RespondTool args (the agent supplies the Spanish text).

### Integration Points
- `src/robotina/agent/tools/respond.py` (NEW) — RespondTool, mirrors QueueTool shape.
- `src/robotina/agent/tools/terminate.py` (NEW) — TerminateTool, return_direct=True no-op.
- `src/robotina/agent/tools/start_workflow.py` — `return_direct=False`, new args_schema, `recipe_query` flat field → `input.value` typed object.
- `src/robotina/agent/tools/queue.py` — DELETE.
- `src/robotina/agent/agents.py` — delete acknowledge-add-recipe entry; bump V004 → V005.
- `src/robotina/agent/workflows.py` — delete acknowledge step + notify step from `add-recipe`.
- `src/robotina/agent/prompts/robotina/V005.md` (NEW) — full prompt, see D-09.
- `src/robotina/agent/prompts/acknowledge-add-recipe/` — DELETE entire directory.
- `src/robotina/queue/jobs.py` — swap tool injection (QueueTool out, RespondTool + TerminateTool in); delete acknowledge-add-recipe elif branch.
- `src/robotina/queue/workflow_runner.py::on_step_failed` — delete dead-letter `send-notification` block; except branch becomes log-only.
- `src/robotina/queue/task_types.py` — delete AcknowledgeAddRecipeInput; add AddRecipeQueryInput.
- `overrides/anthropic.json`, `overrides/openai.json`, `overrides/staging.ollama.json` — delete acknowledge-add-recipe blocks.
- `src/robotina/dashboard/templates/_macros.html` (NEW or extend) — task_type_label macro + TASK_TYPE_LABELS dict.
- `src/robotina/dashboard/templates/workflow.html` — wrap step.task_type renders in task_type_label().
- Tests: `tests/agents/tools/test_respond_tool.py`, `test_terminate_tool.py`; updates to `test_start_workflow_tool.py`; `tests/agents/test_registry_override_sync.py`; updates to dashboard template tests for label rendering.
- `.planning/REQUIREMENTS.md` — tick TOOLS-01..05, DASH-11, EXP-05, EVAL-01..03 in same commit as the final wave / smoke commit.
- `.planning/phases/21-tool-surface-flip-remove-acknowledge-notify/21-SMOKE.md` (NEW) — manual smoke results.
- `PROJECT.md`, `README` if exists — experiment list / agent set update.
- `pyproject.toml` `[project.scripts]` — verify no acknowledge_add_recipe entry.

</code_context>

<specifics>
## Specific Ideas

- **Three orthogonal cuts:** (1) tool surface (add 2, refactor 1, delete 1), (2) deletion (acknowledge agent + notify step + dead-letter block + overrides), (3) labeling + smoke (dashboard label map + EVAL set). Plans 1+2 are tightly coupled (single PR per PITFALL 10); plan 3 follows. Planner picks the wave structure.
- **PITFALL 4 is the load-bearing risk.** Without `terminate()` being the engine-enforced termination point AND the prompt forbidding trailing AI text, the user gets surprise messages ("OK I started 3 workflows") AFTER the final `respond()`. The smoke test specifically probes prompts that tend to produce trailing text.
- **PITFALL 5 (parallel tool calls) is the secondary risk** — multi-call ordering is provider-dependent. Phase 21 doesn't enforce ordering (acceptable for v1.1); Phase 22 may need to per BATCH-04. Constructor-injected `invocation_id` (already done Phase 18) is what prevents concurrent-tool-call races; Phase 21 does NOT add mutable shared state.
- **`QueueTool` deletion is a one-way door.** Once deleted, any code path that still imports it breaks. Repo grep BEFORE the deletion commit is the safety check. After: `! grep -rn "QueueTool" src/ tests/` returns zero hits.
- **Dashboard label map is FIRST introduced in Phase 21** (Phase 20 confirmed it doesn't exist). DASH-11's "removed labels for retired ones" is therefore a vacuous condition for Phase 21 — there's no map to remove from. The phrase becomes: "the new map MUST NOT include acknowledge-add-recipe or notify entries." Plan accordingly.
- **CI guard test (D-12) is a future-drift gate**, not a current-state catch. It will go green immediately after the deletion PR — its value is preventing the NEXT contributor from adding an override without an AGENT_REGISTRY entry (or vice versa).
- **Smoke checkpoint timing:** automated tests pass → operator runs `21-SMOKE.md` → if Ollama-only fails, note + merge; if OpenAI fails, pivot to list-form schema (D-15) → re-run smoke → merge. The pivot path is real and pre-approved by EVAL-03.
- **No new env vars, no migration, no schema change.** Pure code refactor. The deploy runbook is just `docker compose restart task-runner` (after merge) — no DB work.

</specifics>

<deferred>
## Deferred Ideas

- **Multi-recipe LLM extraction (BATCH-*)** — Phase 22. Phase 21 enables the multi-call surface; Phase 22 teaches Robotina to USE it for N-recipe extraction.
- **URL ingestion (URL-*)** — Phase 23. Phase 21 keeps `Literal["add-recipe"]` on `StartWorkflowTool`. Phase 23 extends.
- **Recipe images (IMG-*)** — Phase 24.
- **`parallel_tool_calls=False` provider binding** — future hardening if multi-recipe ordering becomes load-bearing.
- **Compose Agent split (COMP-01)** — v2. V005 keeps Robotina as both decider and composer.
- **Mid-flight cancellation (MID-01)** — v2.
- **Cron-triggered Robotina (CRON-01)** — deferred scheduler milestone.
- **`safe_fetch` helper** — Phase 23 (load-bearing for URL ingestion, not needed in Phase 21).
- **Automated multi-call eval harness** — explicitly deferred per EVAL-01. Manual smoke is sufficient for v1.1.
- **`ask_user(question)` ambiguity-escalation tool** (PITFALL 12) — Phase 22 or v2. Phase 21's prompt handles ambiguity by erring toward FEWER recipes ("if unsure, ask the user").
- **Removing `chat_id`/`user_id`/`platform` from tools and reading them from Conversation FK** — ARCH-05 deprecation window closes post-v1.1.

</deferred>

---

*Phase: 21-Tool-surface flip + remove acknowledge/notify*
*Context gathered: 2026-05-19*
