---
phase: 15-recipe-artifact-accumulation-and-food-unit-validation
plan: 03
subsystem: agent/prompts
tags: [prompt-bump, recipe-research, accumulating-artifact, field-preservation]
requires:
  - "Plan 15-01: RecipeData fully-Optional accumulating artifact; RecipeResearchInstructionsOutput = RecipeData alias"
  - "Plan 15-02: gather V005 emits partial RecipeData with gathered_sources populated"
  - "Phase 14: standardized prompt skeleton"
provides:
  - "recipe-research-instructions V004 prompt (accumulating-artifact contract)"
  - "AGENT_REGISTRY[recipe-research-instructions].prompt_path → V004.md"
  - "AGENT_REGISTRY[recipe-research-instructions].response_format_model = RecipeData (canonical)"
affects:
  - "src/robotina/agent/prompts/recipe-research-instructions/ (V004.md added; V003 superseded)"
  - "src/robotina/agent/agents.py (prompt_path bump + import cleanup + canonical RecipeData)"
  - "tests/unit/test_agents_registry.py (asserts V004)"
tech-stack:
  added:
    - "src/robotina/agent/prompts/recipe-research-instructions/V004.md"
  patterns:
    - "Phase 14 prompt skeleton (Role / Inputs / Tools / Process / Field Preservation Rule / Rules)"
    - "RESEARCH Pitfall 1 — explicit field-preservation rule listing owned fields"
    - "Atomic commit per [[feedback_overrides_in_sync]]"
key-files:
  created:
    - "src/robotina/agent/prompts/recipe-research-instructions/V004.md"
    - ".planning/phases/15-recipe-artifact-accumulation-and-food-unit-validation/15-03-SUMMARY.md"
  modified:
    - "src/robotina/agent/agents.py"
    - "tests/unit/test_agents_registry.py"
decisions:
  - "Use canonical RecipeData symbol in AGENT_REGISTRY (matches plan note 'prefer canonical RecipeData'); dropped unused RecipeResearchInstructionsOutput import."
  - "No overrides/*.json edits — verified none of the 3 files pin a prompt_path for recipe-research-instructions (model_config only)."
metrics:
  duration: "~5 minutes"
  completed: 2026-05-14
  tasks: 2
  files_created: 1
  files_modified: 2
  commits: 1
---

# Phase 15 Plan 03: recipe-research-instructions V004 — Accumulating Artifact Contract Summary

Bump the instructions agent prompt to V004, rewritten for the Phase 15 contract: receive a partial `RecipeData` with `gathered_sources` populated, emit a copy with `steps[]` and `description` (and optionally refined `name`) populated; every other field passes through verbatim.

## What Was Built

### 1. `recipe-research-instructions/V004.md`

New prompt under the Phase 14 standardized skeleton (Role / Inputs / Tools / Process / Field Preservation Rule / Rules). Key shifts vs V003:

- **Role** reframed: instructions step of the pipeline that synthesizes `steps[]` + `description` from `gathered_sources`, with optional `name` refinement and verbatim preservation of every other field.
- **Inputs** explicitly references the incoming partial `RecipeData` and tells the agent to read `name` + `gathered_sources` (list of `{url, title, content}` dicts captured by Plan 15-02's gather V005).
- **Process** dropped the V003 "you receive the full list of per-source recipes" framing — that shape is gone in Phase 15. New process: read `gathered_sources` → majority-consensus step extraction → emit `steps[]` (cooking order, single-action Spanish bodies, no in-text numbering) → emit `description` (1–3 Spanish sentences) → optionally refine `name` → emit the full RecipeData.
- **Field Preservation Rule (CRITICAL — Pitfall 1)** new dedicated section per RESEARCH §"Pitfall 1". Lists this step's owned fields (`steps`, `description`, optional `name`) and enumerates the non-owned fields (`gathered_sources`, `ingredients`, `servings_qty`, `servings_unit`, `prep_time`, `cook_time`, `total_time`, `source_url`, `missing_ingredients`) that MUST pass through verbatim — including `null` and `[]` values. Explicit "do not null out `gathered_sources`" because ingredients and metadata still need it.
- **Rules** retains the Spanish-content / English-prompt clause ([[feedback_prompts_language]]), the Argentine/LATAM kitchen vocabulary clause, and adds: structured-output discipline (no prose/fences); `steps[]` non-empty; never invent steps not supported by `gathered_sources`.

H1: `# Recipe Research Instructions — V004`. No YAML frontmatter. No quick-task IDs.

### 2. `agents.py` bump

```python
prompt_path="src/robotina/agent/prompts/recipe-research-instructions/V004.md",
...
response_format_model=RecipeData,
```

Dropped the now-unused `RecipeResearchInstructionsOutput` import in favor of the canonical `RecipeData` symbol. The alias still exists in `task_types.py` for backward compatibility (tests that import `RecipeResearchInstructionsOutput` still resolve to `RecipeData`).

### 3. Overrides

No edits needed. Verified all three overrides files for `recipe-research-instructions` — each carries `model_config` only, no `prompt_path` pin:

```bash
overrides/anthropic.json  → {'model_config': {'provider': 'anthropic', ...}}
overrides/openai.json     → {'model_config': {'provider': 'openai', ...}}
overrides/staging.ollama.json → {'model_config': {'provider': 'ollama', ...}}
```

Atomic-commit rule from [[feedback_overrides_in_sync]] is satisfied — the rule only requires overrides files that pin a `prompt_path` to be updated in lockstep with the registry, which is vacuously true here.

### 4. Test bump

`tests/unit/test_agents_registry.py::test_recipe_research_instructions_registered` asserted `prompt_path == ".../V003.md"`. Updated to V004 (Rule 1 — test pinned the old contract). The companion `test_registry_recipe_research_instructions_bound_to_instructions_output` in `tests/test_agents.py` still passes unchanged because `RecipeResearchInstructionsOutput` is a runtime alias of `RecipeData` (same object identity).

## Commits

| Task | Commit | Subject |
|------|--------|---------|
| 1+2  | `2b28cdc` | feat(15-03): recipe-research-instructions V004 — accumulating artifact contract |

Atomic per [[feedback_overrides_in_sync]]: one commit covering prompt + agents.py + the affected unit test. Files:
- `src/robotina/agent/prompts/recipe-research-instructions/V004.md`
- `src/robotina/agent/agents.py`
- `tests/unit/test_agents_registry.py`

## Test Results

- `uv run pytest -x -q tests/unit/test_agents_registry.py tests/test_agents.py` → **27 passed**
- `uv run python -c "from robotina.agent.agents import get_agent_config; c = get_agent_config('recipe-research-instructions'); assert c.prompt_path.endswith('recipe-research-instructions/V004.md'); from robotina.queue.task_types import RecipeData; assert c.response_format_model is RecipeData; print('OK')"` → **OK**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] `test_recipe_research_instructions_registered` pinned the old V003 path**

- **Found during:** Task 2 verification (pytest).
- **Issue:** `tests/unit/test_agents_registry.py:134` asserted `prompt_path == ".../V003.md"`. V004 is now canonical.
- **Fix:** Updated assertion to V004.md.
- **Files modified:** `tests/unit/test_agents_registry.py`
- **Commit:** `2b28cdc`

**2. [Rule 3 — Blocking] Unused `RecipeResearchInstructionsOutput` import in agents.py**

- **Found during:** Task 2 edit.
- **Issue:** After switching `response_format_model=RecipeData`, the `RecipeResearchInstructionsOutput` import became unused. Linters and code review would flag.
- **Fix:** Removed the import. The alias in `task_types.py` remains for any other consumers.
- **Files modified:** `src/robotina/agent/agents.py`
- **Commit:** `2b28cdc`

### Authentication / Environment Gates

None.

### Architectural Decisions (no Rule 4 invocations)

All decisions locked in CONTEXT D-01..D-23 and the plan's task descriptions. Discretion call: canonical `RecipeData` symbol vs alias — plan explicitly noted "prefer the canonical RecipeData symbol".

## Known Stubs

None for this plan. V004 is fully wired and live in the registry.

**Note (carries over from Plan 15-02):** Live end-to-end workflow is still mid-migration. Gather (V005) and Instructions (V004) now speak the new contract. Ingredients / metadata / load are bumped in Plans 15-04..15-06. Running the live workflow today succeeds through instructions but fails at ingredients (V003 expects the old per-step input shape). Python unit tests are unaffected — they mock the LLM.

## Threat Flags

None. Prompt-only change; no new network endpoints, no new auth paths, no schema changes.

## Self-Check: PASSED

- `src/robotina/agent/prompts/recipe-research-instructions/V004.md` exists.
- Commit `2b28cdc` present in `git log`.
- `AGENT_REGISTRY["recipe-research-instructions"].prompt_path` ends with `V004.md`.
- `response_format_model` resolves to `RecipeData`.
- V004 contains H1 `# Recipe Research Instructions — V004`, the literal phrase `Field Preservation Rule`, and the field name `gathered_sources`.
- Phase 14 skeleton sections present (Role / Inputs / Tools / Process / Field Preservation Rule / Rules).
- Body is English; user-facing references (name, description, step bodies) require Spanish — consistent with [[feedback_prompts_language]].
- No quick-task IDs in V004 or in the `agents.py` diff.
