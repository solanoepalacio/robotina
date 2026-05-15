---
phase: 15-recipe-artifact-accumulation-and-food-unit-validation
plan: 06
subsystem: agent/prompts + agent/tools
tags: [prompt-bump, recipe-load, household-manager-api, typed-body, model-validator, regression-tests, end-to-end-smoke]
requires:
  - "Plan 15-01: validate-foods + validate-units tools; per-job tool injection in queue/jobs.py for recipe-load"
  - "Plan 15-02..15-05: full recipe-research pipeline emits a fully-resolved RecipeData (every ingredient has food_id; units have unit_id when applicable)"
  - "Phase 14: standardized prompt skeleton"
  - "Phase 11: response_format=RecipeLoadOutput on the recipe-load agent"
provides:
  - "recipe-load V005 prompt (happy-path POST + recovery via validation tools)"
  - "AGENT_REGISTRY[recipe-load].prompt_path → V005.md"
  - "Per-job injection of ValidateFoodsTool + ValidateUnitsTool for recipe-load in queue/jobs.py"
  - "Typed CreateRecipeBody schema on HouseholdManagerApiTool args (closes empty-body POST retry loop)"
  - "model_validator on HouseholdManagerApiArgs that rejects null body for POST /api/recipes"
  - "5 Nyquist regression tests guarding the new validator behaviors"
  - "End-to-end smoke through staging Ollama / OpenAI overrides — manual UAT passed 2026-05-15 (5/5)"
affects:
  - "src/robotina/agent/prompts/recipe-load/ (V005.md added; multiple iterations 2026-05-12 → 2026-05-15 to close two distinct failure modes — see Deviations)"
  - "src/robotina/agent/tools/household_manager_api.py (typed CreateRecipeBody + model_validator; method Literal-restricted)"
  - "src/robotina/agent/skills/household-manager/recipes_create.md (slimmed; auth boilerplate + catalog-resolution duplication removed)"
  - "src/robotina/agent/agents.py (recipe-load registry uses V005)"
  - "src/robotina/queue/jobs.py (per-job tool injection for recipe-load)"
  - "tests/unit/test_household_manager_api_tool.py (5 new regression tests; 16 total)"
tech-stack:
  added:
    - "src/robotina/agent/prompts/recipe-load/V005.md"
  patterns:
    - "Phase 14 prompt skeleton (Role / Inputs / Tools / Process / Critical / Rules)"
    - "Per-job tool injection in queue/jobs.py (architecture invariant: AGENT_REGISTRY[*].tools=[])"
    - "Typed Pydantic body model bound to a tool's args_schema — every key required at the schema level so the constrained decoder cannot satisfy `body` with `{}` (D-17 + 2026-05-15 hardening)"
    - "Per-endpoint model_validator gating null body for POST /api/recipes (closes the last decode escape hatch)"
    - "Construct-then-call prompt structure (split body construction and tool invocation into two explicit steps, with 'never {} or null' wording, to defeat the model's path-of-least-resistance toward minimal-valid args)"
key-files:
  created:
    - "src/robotina/agent/prompts/recipe-load/V005.md"
    - ".planning/phases/15-recipe-artifact-accumulation-and-food-unit-validation/15-06-SUMMARY.md"
  modified:
    - "src/robotina/agent/tools/household_manager_api.py"
    - "src/robotina/agent/skills/household-manager/recipes_create.md"
    - "src/robotina/agent/agents.py"
    - "src/robotina/queue/jobs.py"
    - "tests/unit/test_household_manager_api_tool.py"
decisions:
  - "Recipe-load happy path is a thin POST that trusts upstream foodId / unitId resolution (D-16..D-19); validation responsibility moved entirely to the ingredients step."
  - "On non-2xx response, recipe-load uses validate-foods / validate-units (not household-manager-api GETs) to re-resolve and retry — symmetric with the ingredients step's recovery path."
  - "RecipeLoadOutput keeps only {recipe_id, recipe_name, recipe_description, recipe_slug}; missing_ingredients was dropped in Plan 15-01 and stays dropped here."
  - "Body schema for POST /api/recipes is typed strictly (CreateRecipeBody) on the tool, not just trusted from the prompt. The schema being permissive (`body: dict | None = None`) was the load-bearing cause of the empty-body decode loop — typing the schema and adding the model_validator together close the failure mode at the constrained-decoding layer rather than relying on prompt discipline alone."
  - "Other endpoints (PATCH recipes, meal-plans, etc.) keep `body` accepting either CreateRecipeBody or None for now. When a third typed endpoint appears, refactor `body` into a discriminated union or split into endpoint-specific tools (per [[feedback_avoid_premature_abstraction]] — concrete duplication beats premature generic until 3+ instances)."
metrics:
  duration: "~3 hours total across iterations 2026-05-12 → 2026-05-15"
  completed: 2026-05-15
  tasks: "Plan 15-06 + ad-hoc 15-06 hardening (typed body schema + construct-then-call prompt) + Nyquist regression tests"
  files_created: 2
  files_modified: 5
  commits: 4
---

# Phase 15 Plan 06: recipe-load V005 + Empty-Body-Loop Hardening Summary

Bring the recipe-load agent to V005, then iteratively harden it after smoke testing surfaced two distinct LLM failure modes: (a) the model burning 32K completion tokens "drafting structured output" without ever calling the POST tool, and (b) the model calling the POST tool 30+ times with `body={}` until interrupted. This plan's "end-to-end smoke through staging" was the trigger for both diagnoses; closing them required edits to the prompt, the tool's args schema, and a new model_validator. Final state: the agent constructs a fully-populated body and lands a single 201 Created on the happy path, with 5 regression tests guarding the schema-level constraint.

## What Was Built

### 1. `recipe-load/V005.md`

New prompt under the Phase 14 skeleton (Role / Inputs / Tools / Process / Critical / Rules). Differences vs prior recipe-load behavior:

- **Role** frames the agent as a thin POST step that trusts upstream resolution; the happy path is "apply the rename table, POST, return the receipt."
- **Process** is two explicit cognitive steps — (2) **construct** the request body as a complete JSON object, with a per-key transformation table covering all 12 input fields (snake_case → camelCase rename for renamed keys, drop `food_name`/`unit_name`/`gathered_sources`/`missing_ingredients`); (3) **call** `household-manager-api` with the body you just built. The two-verb split addresses the LLM tendency to fold construction into the tool call and shortcut to `{}`.
- **Tools section** declares up front that the tool's strict schema rejects `{}` or `null` body for POST /api/recipes at validation time, before any HTTP call — so the model knows the failure mode is local, not network.
- **Recovery (step 5)** uses `validate-foods` / `validate-units` (not arbitrary `household-manager-api` GETs) to re-resolve a rejected `foodId` / `unitId`.
- **"Critical: do not emit structured output before POSTing"** section retained from the V005 iteration on 2026-05-14: `RecipeLoadOutput` is the *result* of a successful POST, never a draft attempted before the tool call. Combats the `response_format=RecipeLoadOutput` "done-orientation" failure mode where the model rushes to fill the small final schema and treats the POST as an information-gathering probe.

### 2. `HouseholdManagerApiTool` — typed body schema (commit `7b15884`)

`HouseholdManagerApiArgs.body` was `dict | None = None`. Under that schema the OpenAI constrained decoder accepts `{}` and `null` as legal completions of `"body": ` — both pass validation, both produce a 400 from the backend with a low-information error ("name must be a string"), and the agent re-decodes the same minimal-valid args next turn. Replaced with:

- `CreateRecipeBody` (Pydantic model, `extra="forbid"`, every key required at the schema level — `name`, `description`, `servingsQty`, `servingsUnit`, `prepTime`, `cookTime`, `totalTime`, `sourceUrl`, `ingredients[CreateRecipeIngredient]`, `steps[CreateRecipeStep]`). Nullable optionals are typed `X | None` with no default, forcing the decoder to emit each key explicitly (it can pick `null` for unknowns but cannot collapse to `{}`).
- `body: CreateRecipeBody | None` on the args schema (still nullable to keep GET requests working).
- `model_validator(mode="after") _enforce_body_for_known_endpoints` — for POST `/api/recipes`, rejects `body=None` with an explicit message naming all 10 required keys. Closes the last decode escape hatch.
- `method: Literal["GET", "POST", "PATCH", "DELETE"]` (was `str`).
- `_run` / `_arun` updated to `model_dump(mode="json")` a `CreateRecipeBody` instance before passing to httpx.

### 3. `household-manager/recipes_create.md` slimmed

Removed auth boilerplate (already in `shared.md`) and the duplicated catalog-resolution flow (`GET /api/foods?name=…` instructions). Recipe-load reaches this skill already knowing the catalog has been resolved upstream — the duplicate text was redundant context-window cost. The compound-create example and the schema table remain, since those are what the agent actually consults.

### 4. `queue/jobs.py` per-job injection

The recipe-load branch of `run_task` appends `HouseholdManagerApiTool` + `ValidateFoodsTool` + `ValidateUnitsTool` (the latter two for recovery on non-2xx). Wiring was already added in Plan 15-01 and stayed intact; verified by both the UAT and the commit log.

### 5. `tests/unit/test_household_manager_api_tool.py` — 5 regression tests (commit `bb227ac`)

Added by gsd-nyquist-auditor in retroactive coverage of the new validator behaviors:

1. `test_post_recipes_with_null_body_is_rejected_by_validator` — direct ValidationError check; asserts the message contains "POST /api/recipes requires a non-null body".
2. `test_post_recipes_with_null_body_yields_tool_error_message_in_agent_loop` — end-to-end via `create_agent` + `FakeMessagesListChatModel`; confirms the loop stops with `ToolMessage(status="error")` rather than crashing.
3. `test_post_recipes_with_empty_body_flags_all_required_keys` — verifies Pydantic flags all 10 `CreateRecipeBody` keys as missing for `body={}`.
4. `test_post_recipes_with_full_body_dict_dumps_json_safe_payload` — full body as dict; httpx receives JSON-safe dict.
5. `test_post_recipes_with_full_body_model_instance_dumps_json_safe_payload` — full body as `CreateRecipeBody` instance; `_run` model_dumps before httpx.

Final test run: 16 passed (11 existing + 5 new).

## Deviations from Plan

The plan's "end-to-end smoke through staging Ollama" surfaced the empty-body failure mode that wasn't in the original threat model. Closing it required two iterations beyond the plan's strict scope:

1. **2026-05-14 (commit `ae42555`)** — A previous V005 iteration had a worked input→body example that triggered the *opposite* failure: the model burned 32K completion tokens drafting structured output (`RecipeLoadOutput`) without ever calling the POST tool. Dropping the worked example fixed that, but unmasked the empty-body decode loop because the model lost its only anchor for what a complete body looked like.

2. **2026-05-15 (commit `7b15884`)** — Replaced the prompt-only fix with a schema-level fix (typed `CreateRecipeBody` + `model_validator`) plus a restructured V005 prompt that splits "construct" and "call" into two explicit steps with "never `{}` or `null`" wording. Both pieces were needed; either alone leaves the model an escape hatch.

The discussion + diagnosis trail for both iterations is recorded in `recipe-load-loop.log` (untracked debug capture) and the conversation transcript that produced commit `7b15884`. The decision to fix at the schema layer (rather than continuing to iterate the prompt) was: prompt-only fixes proved fragile across two iterations; constrained-decoding constraints are deterministic.

## Verification

**Plan-level automated check (recipe-load registry pinned to V005):**

```
grep -q "recipe-load/V005.md" src/robotina/agent/agents.py
→ TASK_VERIFY_OK
```

**Schema-level regression tests (5 new + 11 pre-existing):**

```
uv run pytest tests/unit/test_household_manager_api_tool.py -x --tb=short
→ 16 passed in 0.21s
```

**End-to-end UAT (manual, recorded in `15-UAT.md`):**

5/5 tests passed on 2026-05-15 — full add-recipe workflow completes in one POST attempt with `201 Created` (vs. 30+ retries before the fix); created recipe is searchable; missing-ingredients surfaces correctly; catalog resolution lands on real catalog entries.

**Threat model (recorded in `15-SECURITY.md`):**

T15-T2 (empty/null body for POST /api/recipes — canelones loop) classified as `mitigate` with the typed `CreateRecipeBody` + `_enforce_body_for_known_endpoints` validator as evidence.

## Maintainer Note

The end-to-end regression test (`test_post_recipes_with_null_body_yields_tool_error_message_in_agent_loop`) confirms the validator stops the loop and `status="error"` surfaces — but the validator's diagnostic message text does NOT reach the agent's next turn, because langgraph's default `ToolNode` filters validator errors with empty `loc=()` (which `model_validator(mode="after")` produces). Recovery semantics are still correct (the agent stops looping; status="error" is set), but if a future maintainer wants the diagnostic visible to the model, attach `loc=("body",)` to the error — e.g. raise via `PydanticCustomError` on the `body` field rather than at the model level. Recorded in `15-VALIDATION.md`.

## Commits

- `7b15884` — `fix(15-06): recipe-load — typed body schema + construct-then-call prompt`
- `e3660d6` — `test(15): complete UAT - 5 passed, 0 issues`
- `3fff765` — `docs(phase-15): add retroactive security threat verification`
- `bb227ac` — `test(phase-15): add Nyquist regression tests for empty-body-loop fix`
- `c4525a9` — `docs(phase-15): add validation strategy`
