# Phase 11 — Verification

**Status:** APPROVED (narrow goal met; recipe-load behavior debt logged separately)
**Owner:** Solano (project user)
**Created:** 2026-05-13
**Approved:** 2026-05-13

---

## Manual 3-query End-to-End Checkpoint

**Goal:** Verify the 5 named agents emit structured output via the response_format / structured_response channel in production conditions; verify no canelones-class parse failures occur.

**Verification scope (per user decision 2026-05-13):** Single representative run was sufficient to demonstrate the canelones-class regression has been retired. The 3-query criterion in the original ROADMAP success criteria was a confidence margin; one clean run through all 7 workflow steps satisfies the same intent. A separate behavioral regression in `recipe-load` (emit-without-POST hallucination, see Deferred Debt below) was uncovered but is independent of Phase 11's stated goal and will be addressed in follow-up work.

---

## Sign-Off

**Query 1: `agrega canelones de verdura`**

- `workflow_run_id`: `f1d930d4-a409-45b5-a59f-55eb504ea311`
- final state: `DONE` (all 7 steps advanced: `handle-incoming-message` → `acknowledge` → `gather` → `instructions` → `ingredients` → `metadata` → `load` → `notify`)
- LangWatch trace: captured
- prompt_version + model tags present: NOT VERIFIED in this run (LangWatch tagging is a Phase 8/9 deliverable; not a Phase 11 regression — flagged for separate review)
- `ValueError: structured_response missing` log lines: **0** ✓
- Ollama 500 "error parsing tool call" retries: **0** (run used OpenAI backend per override)
- Free-text JSON parse failures (canelones-class): **0** ✓
- Result: **PASS for Phase 11 narrow goal** — canelones-class parse failures structurally eliminated

**Queries 2 + 3 (`agrega tarta de zapallo`, `agrega milanesa de berenjena`):** Not executed. User judgment: one clean run was sufficient evidence that the parse-failure regression mode has been retired. Approving on Query 1 alone.

---

## Overall Sign-Off

- Phase 11 narrow goal (eliminate canelones-class parse failures): **yes**
- All 5 agents emit via structured_response channel: **yes** (verified via worker logs — every `recipe-research-*` and `recipe-load` step completed `Agent run complete` with no `_extract_task_output` parse-ladder hits)
- LangWatch trace tagging works: **deferred** (separate Phase 8/9 audit, not a Phase 11 regression)
- Zero canelones-class regressions: **yes**

**Approval:** APPROVED
**Approved by:** Solano
**Approval date:** 2026-05-13

---

## Deferred Debt Uncovered During Verification

**Two issues surfaced that are NOT Phase 11 regressions but were observed during the verification run. Both are explicitly out of Phase 11 scope per the user's 2026-05-13 decision to finalize:**

### Debt 1 — `recipe-load` emits hallucinated `recipe_id`/`recipe_slug` without calling `POST /api/recipes`

**Observed:** workflow_run_id `f1d930d4-a409-45b5-a59f-55eb504ea311`, log lines 173-200. `recipe-load` read both API skill files, called `GET /api/foods` + `GET /api/units`, then returned `Agent run complete` and emitted a `RecipeLoadOutput` with invented values. No `POST /api/recipes` was ever sent. Workflow advanced to `notify` and the user received a "recipe loaded" confirmation; the database had nothing.

**Why this happened (root cause):**

V001's prompt had a strong terminal directive *"Your final response MUST be ONLY a valid JSON object… Respond ONLY with the JSON object, no additional text"* which, combined with free-text JSON emission, structurally forced the model to actually POST first (the only path to real `id`/`slug` values to emit). V002 stripped that boilerplate per the Phase 11 directive. With `response_format=RecipeLoadOutput` bound via `ProviderStrategy` (OpenAI strict JSON schema mode), the schema becomes the exit condition — the model can satisfy it the moment it produces any `RecipeLoadOutput`-shaped JSON. `RecipeLoadOutput` fields are unconstrained strings (`recipe_id: str`, etc.), so hallucinated UUID-shaped values pass validation. The model takes the cheapest path.

V003 was rewritten (commit `3ce39c5`) to lead with the failure mode and reframe the output as a "receipt of the POST" rather than a synthesis. User confirmed V003 did not change behavior under retest — the structural pull of the schema-as-exit-condition is stronger than prompt-level mitigation alone.

**Why this is NOT a Phase 11 regression of stated goal:** Phase 11's success criteria #1-3 are about eliminating canelones-class parse failures (free-text JSON wrapping prose/fences defeating the parser). All five named agents now emit cleanly via `structured_response`; the parse-failure mode is structurally impossible. The recipe-load hallucination is a different failure class (semantic, not parsing) that pre-existed in latent form — V001 happened to mask it because the free-text exit condition forced the POST. Phase 11 exposed it by removing the implicit constraint.

**Remediation path (deferred):**

1. **Prompt iteration** — user will iterate on the recipe-load prompt outside this phase. Multiple framing approaches available (e.g., explicit pre-emit checklist, two-message exchange, narrative grounding).
2. **Schema tightening** — add Pydantic validators to `RecipeLoadOutput` to require UUID format on `recipe_id`. Catches obvious hallucinations; doesn't catch hallucinated valid UUIDs.
3. **Middleware gate (Phase 12)** — `@before_model` / `@after_model` middleware that asserts a specific tool call appeared in message history before allowing the structured-response channel to fire. This is the deterministic fix.

**Files affected (no changes required for sign-off):**
- `src/robotina/agent/prompts/recipe-load/V003.md` (current; under iteration)
- `src/robotina/queue/task_types.py` (`RecipeLoadOutput` model — candidate for tightening)

### Debt 2 — `WorkflowRun.shared_context.household_id == ""` from `start-workflow` tool call

**Observed:** worker log line 35: `Tool call | tool=start-workflow input={'workflow_type': 'add-recipe', 'shared_context': {'recipe_query': 'canelones de verdura'}}`. No `household_id` in `shared_context`. Downstream steps' inputs (e.g., `RecipeResearchGatherInput(query='canelones de verdura', household_id='')`) carry the empty string through the whole pipeline.

**Why this is NOT a Phase 11 regression:** Phase 11 did not touch `handle-incoming-message`, the `start-workflow` tool, or the workflow-runner's shared_context construction. This is a latent bug from earlier phases that the verification surfaced incidentally.

**Remediation path:** Phase 999.1 (*Custom State Schemas for Reply Context and Household Id*) is the scoped slot for this. User decision 2026-05-13: leave alone for now; revisit when 999.1 is activated or when a downstream consumer breaks visibly.

---

## Notes

- The full pytest suite (`uv run pytest --ignore=tests/integration -x`) trips on environmental tests (docker-compose Postgres required for `test_db_models.py`/`test_gateway.py`) and the pre-existing `test_pyproject.py` env-pollution issue documented in `.planning/phases/11-.../deferred-items.md`. Phase 11 unit-test suites (`tests/test_llm_backend.py`, `tests/test_agents.py`, `tests/test_workflow_runner.py`, `tests/unit/`) are all green: 119 passed, 0 failed in isolation.
- Workflow run `f1d930d4-a409-45b5-a59f-55eb504ea311` is preserved as the canonical proof-of-life. Logs: `canelones-de-verdura.log` (project root, retained as long as it's useful).
