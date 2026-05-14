---
phase: 15-recipe-artifact-accumulation-and-food-unit-validation
plan: 02
subsystem: agent/prompts
tags: [prompt-bump, recipe-research, accumulating-artifact, field-preservation]
requires:
  - "Plan 15-01: RecipeData is now a fully-Optional accumulating artifact; RecipeResearchGatherOutput = RecipeData alias"
  - "Phase 14: standardized prompt skeleton (Role / Inputs / Tools / Process / Rules)"
provides:
  - "recipe-research-gather V005 prompt (accumulating-artifact contract)"
  - "AGENT_REGISTRY[recipe-research-gather].prompt_path → V005.md"
  - "AGENT_REGISTRY[recipe-research-gather].response_format_model = RecipeData (canonical symbol)"
affects:
  - "src/robotina/agent/prompts/recipe-research-gather/ (V005.md added; V004.md untouched/superseded)"
  - "src/robotina/agent/agents.py (prompt_path + import + response_format_model swap)"
  - "tests/unit/test_agents_registry.py (asserts V005)"
tech-stack:
  added:
    - "src/robotina/agent/prompts/recipe-research-gather/V005.md"
  patterns:
    - "Phase 14 prompt skeleton (Role / Inputs / Tools / Process / Field Preservation Rule / Rules)"
    - "RESEARCH Pitfall 1 — explicit field-preservation rule listing owned fields"
    - "Atomic commit per [[feedback_overrides_in_sync]] (prompt + agents.py + test in one commit)"
key-files:
  created:
    - "src/robotina/agent/prompts/recipe-research-gather/V005.md"
    - ".planning/phases/15-recipe-artifact-accumulation-and-food-unit-validation/15-02-SUMMARY.md"
  modified:
    - "src/robotina/agent/agents.py"
    - "tests/unit/test_agents_registry.py"
decisions:
  - "Use canonical RecipeData symbol in AGENT_REGISTRY (per plan note 'prefer the canonical RecipeData symbol'); RecipeResearchGatherOutput alias from 15-01 still resolves correctly but the canonical name reads cleaner."
  - "No overrides/*.json edits — none of the 3 files pin a prompt_path for this agent (verified via json.load); atomic-commit rule still satisfied in spirit."
metrics:
  duration: "~10 minutes"
  completed: 2026-05-14
  tasks: 2
  files_created: 1
  files_modified: 2
  commits: 1
---

# Phase 15 Plan 02: recipe-research-gather V005 — Accumulating Artifact Contract Summary

Bump the gather agent's prompt to V005, rewriting it for the Phase 15 contract where each sub-agent receives a partial `RecipeData` and emits a copy with only the fields it owns populated.

## What Was Built

### 1. `recipe-research-gather/V005.md`

New prompt under the Phase 14 standardized skeleton (Role / Inputs / Tools / Process / Field Preservation Rule / Rules). Key shifts vs V004:

- **Role** now frames the agent as "the first step of the recipe-research pipeline" emitting a partial `RecipeData` with `name` and `gathered_sources` populated, instead of "extract per-source structured data so downstream steps can build by consensus".
- **Inputs** explicitly describes the incoming user message as carrying a partial `RecipeData` artifact (most likely empty) plus the user's Spanish query.
- **Process** drops the per-source `extract structured recipe data (title, ingredients, instructions, times, servings)` step. Phase 15 isolates that work to downstream steps. Gather now only: searches adaptively (3–5 sources, Argentine/LATAM-first), captures raw text + url + title into `gathered_sources` dicts, sets `name` to a clean canonical Spanish recipe name, and emits the artifact.
- **Field Preservation Rule (CRITICAL — Pitfall 1)** is a new dedicated section. Lists this step's owned fields (`name`, `gathered_sources`) and requires every other field to be copied through verbatim — including `null` and `[]` values — to prevent the "sub-agent forgets upstream fields on emit" failure mode described in RESEARCH §"Pitfall 1".
- **Rules** retains the Spanish-content / English-prompt clause (per [[feedback_prompts_language]]) and adds: `gathered_sources` must be non-empty; never invent source URLs; sources stay grounded in a single page (no synthesis at this stage — that's the next step's job).

No YAML frontmatter; H1 is `# Recipe Research Gather — V005`. No quick-task IDs anywhere in the file (per [[feedback_no_task_id_in_code]]).

### 2. `agents.py` bump

```python
prompt_path="src/robotina/agent/prompts/recipe-research-gather/V005.md",
...
response_format_model=RecipeData,
```

Switched the import from `RecipeResearchGatherOutput` to `RecipeData` (the canonical symbol; the alias from Plan 15-01 still works but the plan note prefers the canonical name).

### 3. Overrides

No edits needed. `overrides/anthropic.json`, `overrides/openai.json`, and `overrides/staging.ollama.json` all carry an entry for `recipe-research-gather` but none of them pin a `prompt_path` (model_config only). Verified with:

```bash
uv run python -c "import json
for f in ['overrides/anthropic.json','overrides/openai.json','overrides/staging.ollama.json']:
    print(f, json.load(open(f)).get('recipe-research-gather', {}).get('prompt_path'))"
# → all three print 'None'
```

The atomic-commit rule from [[feedback_overrides_in_sync]] is satisfied by including the prompt + agents.py + test in a single commit; the rule only requires every overrides file that pins a `prompt_path` to be updated in lockstep, which is vacuously true here.

### 4. Test bump

`tests/unit/test_agents_registry.py::test_recipe_research_gather_registered` asserted `prompt_path == ".../V004.md"`. Updated to V005 (Rule 1 — test pinned the old contract).

## Commits

| Task | Commit | Subject |
|------|--------|---------|
| 1+2  | `dd1ef97` | feat(15-02): recipe-research-gather V005 — accumulating artifact contract |

Atomic per [[feedback_overrides_in_sync]]: a single commit covers prompt + agents.py + the affected unit test. Files listed:
- `src/robotina/agent/agents.py`
- `src/robotina/agent/prompts/recipe-research-gather/V005.md`
- `tests/unit/test_agents_registry.py`

## Test Results

- `uv run pytest tests/unit/test_agents_registry.py` → **17 passed**
- `uv run python -c "from robotina.agent.agents import get_agent_config; c = get_agent_config('recipe-research-gather'); assert c.prompt_path.endswith('recipe-research-gather/V005.md'); from robotina.queue.task_types import RecipeData; assert c.response_format_model is RecipeData; print('OK')"` → **OK**
- Full non-DB suite remains green (only failures are pre-existing Postgres/dashboard tests requiring a running Postgres, same baseline as Plan 15-01 SUMMARY documents).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] `test_recipe_research_gather_registered` pinned the old V004 path**

- **Found during:** Task 2 verification (running pytest).
- **Issue:** `tests/unit/test_agents_registry.py:123` asserted `config.prompt_path == "src/robotina/agent/prompts/recipe-research-gather/V004.md"`. The plan supersedes that contract — V005 is now canonical.
- **Fix:** Updated the assertion to `V005.md`. No new test added (the existing test is the right place; we just kept it accurate).
- **Files modified:** `tests/unit/test_agents_registry.py`
- **Commit:** `dd1ef97`

### Authentication / Environment Gates

None.

### Architectural Decisions (no Rule 4 invocations)

All decisions were locked in CONTEXT D-01..D-23 and the plan's task descriptions. The only Claude's-discretion call was "use `RecipeData` directly vs the `RecipeResearchGatherOutput` alias" — the plan explicitly noted "prefer the canonical RecipeData symbol", so picked the canonical name.

## Known Stubs

None. V005 is fully wired:
- `AGENT_REGISTRY["recipe-research-gather"].prompt_path` resolves to V005.md.
- `response_format_model = RecipeData` matches the Phase 15 contract.
- No downstream consumer needs to change (the workflow runner reads `prompt_path` and `response_format_model` from the registry; both are live).

**Note (carries over from Plan 15-01 SUMMARY §"Known Stubs"):** The full `add-recipe` workflow is still partially mid-migration — only the gather step now speaks the new contract. Instructions / ingredients / metadata / load are bumped in Plans 15-03..15-06. Running the live workflow end-to-end against the current state will succeed at gather but fail at instructions (V003 expects the old per-step input shape). Python unit tests are unaffected because they mock the LLM.

## Threat Flags

None. Prompt-only change; no new network endpoints, no new auth paths, no schema changes.

## Self-Check: PASSED

- ✅ `src/robotina/agent/prompts/recipe-research-gather/V005.md` exists.
- ✅ `git log --oneline | grep dd1ef97` finds the commit.
- ✅ `AGENT_REGISTRY["recipe-research-gather"].prompt_path` ends with `V005.md`.
- ✅ `response_format_model` resolves to `RecipeData`.
- ✅ V005 contains the H1 `# Recipe Research Gather — V005`, the literal phrase `Field Preservation Rule`, and the field name `gathered_sources`.
- ✅ Phase 14 skeleton sections present (Role / Inputs / Tools / Process / Rules), with the explicit Field Preservation Rule subsection per RESEARCH Pitfall 1.
- ✅ Body is English; only the named-content references (e.g. `name` field guidance, search-query language) reference Spanish — consistent with [[feedback_prompts_language]].
- ✅ No quick-task IDs in V005 or in `agents.py` diff.
