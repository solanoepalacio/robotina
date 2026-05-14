---
phase: 15-recipe-artifact-accumulation-and-food-unit-validation
plan: 05
subsystem: agent/prompts
tags: [prompt-bump, recipe-research, metadata, accumulating-artifact, field-preservation, clean-payload]
requires:
  - "Plan 15-01: RecipeData.gathered_sources field; canonical RecipeData aliasing for *Output models"
  - "Plan 15-02: gather V005 emits partial RecipeData with gathered_sources populated"
  - "Plan 15-03: instructions V004 emits steps[] + description, preserves gathered_sources"
  - "Plan 15-04: ingredients V004 resolves food_id / unit_id, preserves gathered_sources"
  - "Phase 14: standardized prompt skeleton"
provides:
  - "recipe-research-metadata V004 prompt (final synthesis + clean-payload emit per D-04)"
  - "AGENT_REGISTRY[recipe-research-metadata].prompt_path → V004.md"
  - "AGENT_REGISTRY[recipe-research-metadata].response_format_model = canonical RecipeData"
affects:
  - "src/robotina/agent/prompts/recipe-research-metadata/ (V004.md added; V003 superseded)"
  - "src/robotina/agent/agents.py (prompt_path bump, canonical RecipeData, dropped unused alias import)"
  - "tests/unit/test_agents_registry.py (asserts V004)"
tech-stack:
  added:
    - "src/robotina/agent/prompts/recipe-research-metadata/V004.md"
  patterns:
    - "Phase 14 prompt skeleton (Role / Inputs / Tools / Process / Field Preservation Rule / Rules)"
    - "RESEARCH Pitfall 1 — explicit ownership table listing owned vs nulled vs preserved fields"
    - "D-04 clean-payload contract — gathered_sources nulled on emit so recipe-load sees a focused artifact"
    - "Atomic commit per [[feedback_overrides_in_sync]]"
key-files:
  created:
    - "src/robotina/agent/prompts/recipe-research-metadata/V004.md"
    - ".planning/phases/15-recipe-artifact-accumulation-and-food-unit-validation/15-05-SUMMARY.md"
  modified:
    - "src/robotina/agent/agents.py"
    - "tests/unit/test_agents_registry.py"
decisions:
  - "response_format_model migrated from RecipeResearchMetadataOutput → canonical RecipeData (alias kept in task_types.py for backward compat; agents.py now uses the canonical symbol — consistent with 15-02/15-03/15-04)."
  - "Dropped unused RecipeResearchMetadataOutput import from agents.py (15-03/15-04 precedent)."
  - "No overrides/*.json edits — all 3 overrides pin only model_config for recipe-research-metadata, not prompt_path. [[feedback_overrides_in_sync]] honored by audit, not by edit."
  - "Prompt explicitly lists `null` as the preferable choice when sources don't supply a value (replaces V003's never-null-always-estimate rule). Recipe-load and the household-manager API both accept null metadata fields."
metrics:
  duration: "~65s"
  completed: 2026-05-14
  tasks: 2
  files_created: 1
  files_modified: 2
  commits: 1
---

# Phase 15 Plan 05: recipe-research-metadata V004 — Accumulating Artifact + Clean-Payload Emit Summary

Bump the metadata agent prompt to V004. New contract per Phase 15: receive a partial `RecipeData` whose `name` / `description` / `steps[]` / `ingredients[]` (with `food_id` and `unit_id`) / `missing_ingredients[]` are populated and whose `gathered_sources` is still populated; fill in the remaining metadata fields (`servings_qty`, `servings_unit`, `prep_time`, `cook_time`, `total_time`, `source_url`); then perform the clean-payload step from D-04 — set `gathered_sources = null` on the outgoing artifact so recipe-load receives an insert-ready, focused payload. Every other field is preserved verbatim per the Field Preservation Rule.

## What Was Built

### 1. `recipe-research-metadata/V004.md`

New prompt following the Phase 14 skeleton (Role / Inputs / Tools / Process / Field Preservation Rule / Rules). Differences vs V003:

- **Accumulating-artifact contract.** V003 received per-step output schemas (`instructions`, `ingredients`, `gather_recipes`). V004 receives ONE partial `RecipeData` and emits a fuller copy of the SAME `RecipeData`. The "Inputs" section explicitly names `gathered_sources` as the field this step reads for metadata extraction.
- **Owned-field set.** This step owns `servings_qty`, `servings_unit`, `prep_time`, `cook_time`, `total_time`, `source_url`. The "Process" section enumerates them with type + Spanish-format guidance.
- **Clean-payload step (D-04).** Explicit Process step 3 and a Rules-section invariant: `gathered_sources` is set to `null` on emit. This is called out in two places (Role intro and Rules) so the LLM cannot miss it. The prompt clarifies that intermediate `workflow_run_steps.artifact` rows from upstream steps still contain the sources for DB-level debugging — nothing is lost.
- **Field Preservation Rule (Pitfall 1).** Explicit ownership table:
  - populated by this step: `servings_qty`, `servings_unit`, `prep_time`, `cook_time`, `total_time`, `source_url`
  - intentionally nulled: `gathered_sources` (the ONE field this step nulls)
  - preserved verbatim: `name`, `description`, `steps`, `ingredients` (including `food_id` / `unit_id`), `missing_ingredients`
  Explicit "do not refine the name; do not edit steps; do not touch ingredients; do not change missing_ingredients" so the LLM doesn't accidentally re-resolve work owned by upstream steps.
- **`null` preferable to invented metadata.** V003 forced never-null estimates with default `servings_qty=4` and `servings_unit="porciones"`. V004 reverses this: if the sources don't supply a value, the field is `null`. Recipe-load and the household-manager API both accept `null` here — invented numbers cause silent data-quality drift.
- **`source_url` must come from `gathered_sources`.** Anti-hallucination rule made explicit.
- **Spanish content, English prompt.** Per project rule. `servings_unit`, time strings ("20 min", "1 h 15 min") are user-facing Spanish.
- **No quick-task IDs.**

46 lines of substantive content (plan asked for ≥30).

### 2. `agents.py` — `AGENT_REGISTRY["recipe-research-metadata"]`

- `prompt_path` → `src/robotina/agent/prompts/recipe-research-metadata/V004.md`.
- `response_format_model` → canonical `RecipeData` (was `RecipeResearchMetadataOutput`, which is now an alias for `RecipeData` per Plan 15-01). Matches the symbol used by `recipe-research-gather` / `-instructions` / `-ingredients` and makes the "single shared artifact across all 5 sub-agents" rule visible at the registry level.
- `tools=[]` preserved — pure synthesis step, no tools.
- Removed the now-unused `RecipeResearchMetadataOutput` import (15-03 / 15-04 precedent).

### 3. `overrides/*.json` — audit only, no edits

Grepped all 3 override files for `recipe-research-metadata`: each pins only `model_config` (provider, model, api_key_env, and `url` + `reasoning` for the staging Ollama variant). None pin `prompt_path`. No edits required to honor `[[feedback_overrides_in_sync]]`.

### 4. `tests/unit/test_agents_registry.py`

Updated the V003 → V004 assertion in `test_recipe_research_metadata_registered`. All 122 tests in `tests/test_task_types.py + tests/test_agents.py + tests/unit/` pass.

## Deviations from Plan

None — plan executed as written. The plan correctly anticipated the response_format_model migration (the verify command asserts `RecipeData`), and the cleanup of the unused alias import follows the precedent established in 15-03 / 15-04.

## Verification

**Task 1 (V004 prompt) — plan automated check:**

```
test -f V004.md && grep -q '^# Recipe Research Metadata — V004' && grep -q 'Field Preservation Rule' && grep -qE 'gathered_sources = null|gathered_sources=null|gathered_sources to null|set .*gathered_sources' && grep -q 'servings_qty'
→ TASK1_VERIFY_OK
```

**Task 2 (registry + overrides) — plan automated check:**

```
uv run python -c "from robotina.agent.agents import get_agent_config; c = get_agent_config('recipe-research-metadata'); assert c.prompt_path.endswith('recipe-research-metadata/V004.md'); from robotina.queue.task_types import RecipeData; assert c.response_format_model is RecipeData or c.response_format_model.__name__ == 'RecipeData'; print('OK')"
→ OK
```

**Test suite:** `uv run pytest tests/test_task_types.py tests/test_agents.py tests/unit/ -q` → **122 passed in 1.02s**.

**Manual sanity:** Re-read V004.md end-to-end after writing — the `gathered_sources = null` contract is stated in three places (Role intro, Process step 3, Rules) so the LLM cannot miss it. The Field Preservation Rule names every preserved field explicitly so the metadata step cannot accidentally undo `food_id` / `unit_id` resolution from Plan 15-04.

## Deferred Issues

A full `uv run pytest -x -q` still has pre-existing failures in `tests/dashboard/`, `tests/test_db_models.py`, `tests/test_gateway.py`, and `tests/test_workflow_runner.py` because Postgres is not running on this dev box. Same posture as 15-04 — infrastructure-level failures unrelated to this plan's edits. Out of scope per the executor scope-boundary rule.

## Commits

- `a0a311c` — `feat(15-05): recipe-research-metadata V004 — accumulating artifact + clean-payload emit`

## Self-Check: PASSED

- V004.md exists at `src/robotina/agent/prompts/recipe-research-metadata/V004.md` ✓
- agents.py points to V004.md and uses canonical `RecipeData` ✓
- Commit `a0a311c` present in `git log` ✓
- Test suite (unit + task_types + agents): 122 passed ✓
