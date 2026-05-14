---
phase: 15-recipe-artifact-accumulation-and-food-unit-validation
plan: 04
subsystem: agent/prompts
tags: [prompt-bump, recipe-research, ingredients, validation-tools, accumulating-artifact, field-preservation]
requires:
  - "Plan 15-01: RecipeIngredient.food_id / unit_id; validate-foods + validate-units tools; per-job tool wiring in queue/jobs.py"
  - "Plan 15-02: gather V005 emits partial RecipeData with gathered_sources populated"
  - "Plan 15-03: instructions V004 emits steps[] + description, preserves the rest"
  - "Phase 14: standardized prompt skeleton"
provides:
  - "recipe-research-ingredients V004 prompt (validation-tool-driven, accumulating-artifact contract)"
  - "AGENT_REGISTRY[recipe-research-ingredients].prompt_path → V004.md"
  - "AGENT_REGISTRY[recipe-research-ingredients].response_format_model = canonical RecipeData"
affects:
  - "src/robotina/agent/prompts/recipe-research-ingredients/ (V004.md added; V003 superseded)"
  - "src/robotina/agent/agents.py (prompt_path bump, canonical RecipeData, dropped unused alias import)"
  - "tests/unit/test_agents_registry.py (asserts V004)"
tech-stack:
  added:
    - "src/robotina/agent/prompts/recipe-research-ingredients/V004.md"
  patterns:
    - "Phase 14 prompt skeleton (Role / Inputs / Tools / Process / Field Preservation Rule / Rules)"
    - "Batched validation tool calls (one validate-foods + one validate-units per agent run; D-15)"
    - "RESEARCH Pitfall 1 — explicit field-preservation rule listing owned fields"
    - "Atomic commit per [[feedback_overrides_in_sync]]"
key-files:
  created:
    - "src/robotina/agent/prompts/recipe-research-ingredients/V004.md"
    - ".planning/phases/15-recipe-artifact-accumulation-and-food-unit-validation/15-04-SUMMARY.md"
  modified:
    - "src/robotina/agent/agents.py"
    - "tests/unit/test_agents_registry.py"
decisions:
  - "response_format_model migrated from RecipeResearchIngredientsOutput → canonical RecipeData (matches gather / instructions; ingredients now own a subset of fields on the shared artifact, not its own output schema)."
  - "AGENT_REGISTRY[*].tools left as []; the architecture invariant is per-job tool injection in queue/jobs.py — wiring already added in 15-01 and verified intact (ValidateFoodsTool + ValidateUnitsTool + HouseholdManagerApiTool)."
  - "No overrides/*.json edits — none of the 3 override files pin prompt_path for recipe-research-ingredients (model_config only)."
  - "Dropped unused RecipeResearchIngredientsOutput import from agents.py (consistent with the 15-03 cleanup pattern)."
metrics:
  duration: "~6 minutes"
  completed: 2026-05-14
  tasks: 2
  files_created: 1
  files_modified: 2
  commits: 1
---

# Phase 15 Plan 04: recipe-research-ingredients V004 — Validation Tools + Accumulating Artifact Summary

Bump the ingredients agent prompt to V004. New contract per Phase 15: receive a partial `RecipeData` whose `gathered_sources` is populated, call the two new validation tools (`validate-foods`, `validate-units`) to resolve every Spanish ingredient name to a household-catalog id, emit a copy of the artifact with `ingredients[]` fully resolved (every entry has `food_id`, and `unit_id` when a unit is specified) and `missing_ingredients[]` populated with any names that couldn't be matched. Every other field is preserved verbatim per the Field Preservation Rule.

## What Was Built

### 1. `recipe-research-ingredients/V004.md`

New prompt following the Phase 14 skeleton. Differences vs V003:

- **Process is built around the two validation tools, not `household-manager-api`.** V003 used `GET /api/foods?name={food_name}` once per ingredient. V004 collects DISTINCT food names into one list and calls `validate-foods({names: [...]})` ONCE; same shape for unit names via `validate-units`. Batched calls are explicit in the prompt: "ONE `validate-foods` call per agent run, ONE `validate-units` call per agent run. Per-item calls waste tokens and traces and are explicitly rejected." This honors D-15.
- **Two distinct fates for unmatched names.** Unmatched FOODS → drop ingredient + append name to `missing_ingredients[]`. Unmatched UNITS → leave `unit_id = null` and KEEP the ingredient (units degrade gracefully). The prompt calls this out explicitly so the LLM doesn't drop ingredients over missing units.
- **Resolved ids flow onto the artifact.** Matched food names populate `food_id` on each `RecipeIngredient`; matched unit names populate `unit_id`. This is the data recipe-load needs in Plan 15-06.
- **Field Preservation Rule (Pitfall 1).** Explicit ownership table: this step owns `ingredients` and `missing_ingredients`; everything else (`gathered_sources`, `steps`, `description`, `name`, `servings_qty`, `servings_unit`, `prep_time`, `cook_time`, `total_time`, `source_url`) is copied through verbatim. `gathered_sources` is called out specifically — the metadata step (Plan 15-05) still needs it.
- **Tool-call hygiene section.** Explicit: no `extra` fields (`args_schema` is `extra='forbid'`), and skipping the `validate-units` call is acceptable when there are zero unit names to validate.
- **Spanish content, English prompt.** Per project rule.
- **No quick-task IDs.**

37 lines of substantive content (plan asked for ≥35).

### 2. `agents.py` — `AGENT_REGISTRY["recipe-research-ingredients"]`

- `prompt_path` → `src/robotina/agent/prompts/recipe-research-ingredients/V004.md`.
- `response_format_model` → canonical `RecipeData` (was `RecipeResearchIngredientsOutput`, which is now an alias for `RecipeData` after Plan 15-01).
- `tools=[]` preserved by design. Comment updated to reflect the three tools that `queue/jobs.py` injects per-job: `HouseholdManagerApiTool + ValidateFoodsTool + ValidateUnitsTool`.
- Removed the now-unused `RecipeResearchIngredientsOutput` import.

### 3. `jobs.py` — verification only

The verify command for Task 2 greps for `ValidateFoodsTool` and `ValidateUnitsTool` inside the `task_type == "recipe-research-ingredients"` branch. Confirmed both are present (added by Plan 15-01 Task 3). No edits to `jobs.py` in this plan.

### 4. `overrides/*.json` — audit only, no edits

Grepped all 3 override files for `recipe-research-ingredients`: each pins only `model_config` (provider, model, api_key_env), not `prompt_path`. No edits required to honor `[[feedback_overrides_in_sync]]`.

### 5. `tests/unit/test_agents_registry.py`

Updated the V003 → V004 assertion in `test_recipe_research_ingredients_registered`. All 27 unit tests in `tests/unit/` pass.

## Deviations from Plan

None — plan executed as written. The plan correctly anticipated the response_format_model migration (the verify command asserts `RecipeData`), and the cleanup of the unused alias import follows the precedent established in 15-03.

## Verification

**Task 1 (V004 prompt):** Plan's automated check passed —
```
test -f V004.md && grep -q '^# Recipe Research Ingredients — V004' && grep -q 'Field Preservation Rule' && grep -q 'validate-foods' && grep -q 'validate-units' && grep -qE 'ONCE|single call|batched'
→ TASK1_VERIFY_OK
```

**Task 2 (registry + jobs.py + overrides):** Plan's automated check passed —
```
uv run python -c "… assert c.prompt_path.endswith('recipe-research-ingredients/V004.md'); assert c.tools == []; assert c.response_format_model is RecipeData …"
→ OK
grep -A 10 'task_type == "recipe-research-ingredients"' src/robotina/queue/jobs.py | grep ValidateFoodsTool
grep -A 10 'task_type == "recipe-research-ingredients"' src/robotina/queue/jobs.py | grep ValidateUnitsTool
→ TASK2_VERIFY_OK
```

**Test suite:** `uv run pytest tests/test_task_types.py tests/test_agents.py tests/unit/ -q` → 122 passed.

**Manual sanity:** Re-read V004.md end-to-end after writing — batched-call instruction is unambiguous ("ONCE per agent run with ALL distinct food names batched into a single call"); no language permits a per-ingredient call pattern.

## Deferred Issues

A full `uv run pytest -x -q` shows pre-existing failures in `tests/dashboard/`, `tests/test_db_models.py`, `tests/test_gateway.py`, and `tests/test_workflow_runner.py` because Postgres is not running on this dev box. These are infrastructure-level failures unrelated to Plan 15-04 (the same files were green/red independent of this plan's edits). Out of scope per the executor scope-boundary rule.

`tests/unit/test_agent_middleware.py` and `tests/unit/test_observability.py` failures observed inside the larger run are also test-pollution artifacts of the upstream DB-connection errors — when those two files are run in isolation, all 27 unit tests pass.

## Commits

- `f8f76eb` — `feat(15-04): recipe-research-ingredients V004 — validation tools + accumulating artifact`

## Self-Check: PASSED

- V004.md exists at `src/robotina/agent/prompts/recipe-research-ingredients/V004.md` ✓
- agents.py points to V004.md and uses canonical `RecipeData` ✓
- jobs.py still injects `ValidateFoodsTool` + `ValidateUnitsTool` for `recipe-research-ingredients` ✓
- Commit `f8f76eb` present in `git log` ✓
- Test suite (unit + task_types + agents): 122 passed ✓
