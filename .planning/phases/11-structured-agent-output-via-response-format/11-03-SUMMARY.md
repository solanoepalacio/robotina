---
phase: 11
plan: 03
subsystem: agent-registry-and-prompts
tags:
  - structured-output
  - response_format
  - agent-registry
  - prompt-bump
  - tdd
  - wave-2
dependency_graph:
  requires:
    - "Plan 11-01: AgentConfig.response_format_model (field) + LLMBackend.create_agent(response_format=) (Protocol + 3 adapters)"
    - "langchain.agents.create_agent (Phase 10 — AGENT-12)"
    - "Pydantic v2 Output models in robotina.queue.task_types (Phase 9)"
  provides:
    - "5 named agents in AGENT_REGISTRY emit structured output (Pydantic instance in state['structured_response'])"
    - "run_task() threads response_format=config.response_format_model into backend.create_agent(...)"
    - "5 bumped prompt files free of 'respond with JSON only' boilerplate"
  affects:
    - "Plan 11-02 workflow_runner — its _extract_task_output now reads result['structured_response'] for the 5 bound agents"
    - "Plan 11-04 manual e2e checkpoint — verifies these bindings against live LLM"
tech_stack:
  added: []
  patterns:
    - "Per-file commit policy for multi-prompt edits (bounded rollback)"
    - "Pydantic-class identity binding via dataclass field (not string lookup) — response_format_model: type[BaseModel]"
key_files:
  created:
    - "src/robotina/agent/prompts/recipe-research-gather/V003.md"
    - "src/robotina/agent/prompts/recipe-research-instructions/V002.md"
    - "src/robotina/agent/prompts/recipe-research-ingredients/V002.md"
    - "src/robotina/agent/prompts/recipe-research-metadata/V002.md"
    - "src/robotina/agent/prompts/recipe-load/V002.md"
  modified:
    - "src/robotina/agent/agents.py"
    - "src/robotina/queue/jobs.py"
    - "tests/test_agents.py"
    - "tests/unit/test_agents_registry.py"
decisions:
  - "5 named agents bound by class identity (response_format_model=RecipeXOutput) — not by string lookup."
  - "Old V### prompts kept on disk per project versioning convention (no in-place rewrites)."
  - "handle-incoming-message + acknowledge-add-recipe deliberately unbound (out-of-scope per CONTEXT.md; return_direct conflict for acknowledge)."
  - "Per-file commit policy honored: 5 prompt files + 1 agents.py = 6 commits across Task 3.2, plus Task 3.1 RED + Rule 1 fix = 8 total (11-03) commits."
metrics:
  duration_minutes: 6
  completed_at: "2026-05-13T18:24:39Z"
---

# Phase 11 Plan 03: Bind 5 Agents to Pydantic Output Models + Bump Prompt Versions Summary

Bound the 5 in-scope agents in `AGENT_REGISTRY` (`recipe-research-gather`, `-instructions`, `-ingredients`, `-metadata`, `recipe-load`) to their existing Pydantic Output models via the `response_format_model` field landed in Plan 11-01, bumped the 5 affected prompt versions to strip "respond with JSON only" boilerplate, and threaded `config.response_format_model` through `run_task()` into `backend.create_agent(response_format=...)`. With Plan 11-02 (running in parallel in Wave 2), the canelones-class free-text-JSON parse failure is now structurally eliminated for the 5 named agents.

## What Was Built

**One-liner:** AGENT_REGISTRY 5-agent class-identity binding to Pydantic Output models + 5 prompt files freed of JSON boilerplate + run_task() response_format threading — Wave 2 of Phase 11 lands the runtime contract surface defined by Wave 1.

### Files

**Created (5 new prompt versions):**
- `src/robotina/agent/prompts/recipe-research-gather/V003.md` — 37 lines (V002 was 62L; delta -25)
- `src/robotina/agent/prompts/recipe-research-instructions/V002.md` — 35 lines (V001 was 47L; delta -12)
- `src/robotina/agent/prompts/recipe-research-ingredients/V002.md` — 40 lines (V001 was 51L; delta -11)
- `src/robotina/agent/prompts/recipe-research-metadata/V002.md` — 33 lines (V001 was 56L; delta -23)
- `src/robotina/agent/prompts/recipe-load/V002.md` — 71 lines (V001 was 89L; delta -18)

Total prompt line-count reduction: **89 lines** (across 5 files). Every removed line was schema-mirroring or JSON-syntax boilerplate now token-enforced by `response_format`.

**Modified:**
- `src/robotina/agent/agents.py` — Added 5 imports from `robotina.queue.task_types`; set `response_format_model=RecipeXOutput` on 5 registry entries; bumped 5 `prompt_path` values to the new V### files.
- `src/robotina/queue/jobs.py` — Line 175 `backend.create_agent(system_prompt=prompt_text, tools=tools)` → multi-line call passing `response_format=config.response_format_model`. Added a comment block citing Plan 11-01's omit-on-None contract.
- `tests/test_agents.py` — Appended 6 new tests (5 binding assertions + 1 non-scope-null assertion).
- `tests/unit/test_agents_registry.py` — Rule 1 fix: updated 5 `prompt_path == "...V###.md"` assertions to match the new versions.

**Untouched (per scope guardrail):**
- `overrides/openai.json` — unchanged. `response_format_model` is non-overridable per Plan 11-01.
- `src/robotina/queue/workflow_runner.py` and `tests/test_workflow_runner.py` — Plan 11-02 territory; deliberately not touched (Wave 2 parallel-safety guarantee).
- Old V### prompt files — all 5 remain on disk per project versioning convention (no in-place rewrites).

## Tasks

| Task | Name                                                                                | Commit  | Files                                                                                  |
| ---- | ----------------------------------------------------------------------------------- | ------- | -------------------------------------------------------------------------------------- |
| 3.1  | RED — registry-binding tests + thread response_format through run_task              | 2878ec5 | tests/test_agents.py, src/robotina/queue/jobs.py                                       |
| 3.2a | Write recipe-research-gather V003 prompt — strip JSON boilerplate                   | b8d8241 | src/robotina/agent/prompts/recipe-research-gather/V003.md                              |
| 3.2b | Write recipe-research-instructions V002 prompt — strip JSON boilerplate             | c97e5f1 | src/robotina/agent/prompts/recipe-research-instructions/V002.md                        |
| 3.2c | Write recipe-research-ingredients V002 prompt — strip JSON boilerplate              | b341a65 | src/robotina/agent/prompts/recipe-research-ingredients/V002.md                         |
| 3.2d | Write recipe-research-metadata V002 prompt — strip JSON boilerplate                 | aba9682 | src/robotina/agent/prompts/recipe-research-metadata/V002.md                            |
| 3.2e | Write recipe-load V002 prompt — strip JSON boilerplate                              | 5189d20 | src/robotina/agent/prompts/recipe-load/V002.md                                         |
| 3.2f | GREEN — bind 5 agents to Pydantic Output models in AGENT_REGISTRY + bump prompt_paths | ea263a4 | src/robotina/agent/agents.py                                                          |
| 3.2g | [Rule 1] Bump prompt_path assertions in test_agents_registry.py                     | 9f3fd97 | tests/unit/test_agents_registry.py                                                     |

Total: **8 commits** under `(11-03)` scope. Acceptance gate required ≥6 — exceeded.

## Registry Diff

```diff
 "recipe-research-gather": AgentConfig(
     ...
-    prompt_path="src/robotina/agent/prompts/recipe-research-gather/V002.md",
+    prompt_path="src/robotina/agent/prompts/recipe-research-gather/V003.md",
     skills=[],
     tools=[],
+    response_format_model=RecipeResearchGatherOutput,
 ),
 "recipe-research-instructions": AgentConfig(
     ...
-    prompt_path="src/robotina/agent/prompts/recipe-research-instructions/V001.md",
+    prompt_path="src/robotina/agent/prompts/recipe-research-instructions/V002.md",
     skills=[],
     tools=[],
+    response_format_model=RecipeResearchInstructionsOutput,
 ),
 "recipe-research-ingredients": AgentConfig(
     ...
-    prompt_path="src/robotina/agent/prompts/recipe-research-ingredients/V001.md",
+    prompt_path="src/robotina/agent/prompts/recipe-research-ingredients/V002.md",
     skills=[],
     tools=[],
+    response_format_model=RecipeResearchIngredientsOutput,
 ),
 "recipe-research-metadata": AgentConfig(
     ...
-    prompt_path="src/robotina/agent/prompts/recipe-research-metadata/V001.md",
+    prompt_path="src/robotina/agent/prompts/recipe-research-metadata/V002.md",
     skills=[],
     tools=[],
+    response_format_model=RecipeResearchMetadataOutput,
 ),
 "recipe-load": AgentConfig(
     ...
-    prompt_path="src/robotina/agent/prompts/recipe-load/V001.md",
+    prompt_path="src/robotina/agent/prompts/recipe-load/V002.md",
     skills=["household-manager"],
     tools=[],
+    response_format_model=RecipeLoadOutput,
 ),
```

Out-of-scope agents (`handle-incoming-message`, `acknowledge-add-recipe`): unchanged — no `response_format_model` line means the dataclass default `None` applies, which is exactly the desired invariant locked by `test_registry_non_scope_agents_have_no_response_format_model`.

## JSON-Boilerplate Strings Removed

The following boilerplate patterns were stripped across the 5 new prompt files:

| Pattern                                                                                                                       | Files affected                                                                |
| ----------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `"## Output format"` / `"## Output Format"` section heading + code-fenced JSON example                                        | gather V003, instructions V002, ingredients V002, metadata V002, recipe-load V002 |
| `"Your final response MUST be a JSON object..."` / `"Your final response must be a JSON object"`                              | gather V003, instructions V002, ingredients V002, metadata V002, recipe-load V002 |
| `"Output only JSON"` bullet in Critical Rules                                                                                 | recipe-load V002                                                              |
| `"Respond ONLY with the JSON object, no additional text"`                                                                     | recipe-load V002                                                              |
| `"JSON output rules"` paragraph (null vs None vs "none" guidance)                                                             | gather V003, instructions V002, ingredients V002, metadata V002               |
| `"CORRECT: {...} INCORRECT: [...]"` shape-pinning example                                                                     | gather V003                                                                   |
| Per-field bullet explanation that mirrored the Pydantic schema                                                                | recipe-load V002                                                              |

Replaced with a "What to populate" section per prompt that describes each field's **semantic** purpose (e.g. "what should `food_name` be?" rather than "make sure `food_name` is a string"). Schema is now token-enforced — the prompt should not duplicate it.

Boilerplate-free verification:

```bash
$ grep -l "respond with valid JSON only\|Output only JSON\|Respond ONLY with the JSON" \
    src/robotina/agent/prompts/recipe-research-gather/V003.md \
    src/robotina/agent/prompts/recipe-research-instructions/V002.md \
    src/robotina/agent/prompts/recipe-research-ingredients/V002.md \
    src/robotina/agent/prompts/recipe-research-metadata/V002.md \
    src/robotina/agent/prompts/recipe-load/V002.md
# (no output — zero matches)
```

## Wave 0 RED state observed before Task 3.2

After landing Task 3.1 (commit `2878ec5`) but BEFORE Task 3.2's agents.py edits, the 6 new tests were run as a sanity check. Five tests failed for the right reason (None vs expected class — not import errors, not syntax errors); the sixth passed because the non-scope invariant was already true:

```
tests/test_agents.py::test_registry_recipe_research_gather_bound_to_gather_output           FAILED
tests/test_agents.py::test_registry_recipe_research_instructions_bound_to_instructions_output FAILED
tests/test_agents.py::test_registry_recipe_research_ingredients_bound_to_ingredients_output FAILED
tests/test_agents.py::test_registry_recipe_research_metadata_bound_to_metadata_output       FAILED
tests/test_agents.py::test_registry_recipe_load_bound_to_load_output                        FAILED
tests/test_agents.py::test_registry_non_scope_agents_have_no_response_format_model          PASSED
5 failed, 1 passed
```

Sample failure detail:

```
>   assert AGENT_REGISTRY["recipe-load"].response_format_model is RecipeLoadOutput
E   AssertionError: assert None is RecipeLoadOutput
E    +  where None = AgentConfig(task_type='recipe-load', ..., response_format_model=None).response_format_model
```

This confirms the source-level intentional-RED gate `grep -c "response_format_model=Recipe" src/robotina/agent/agents.py == 0` correctly discriminated "test waiting for binding" from accidental import / syntax errors. After Task 3.2 GREEN (commit `ea263a4`), the gate flipped to `5` and all 10 tests/test_agents.py tests pass.

## Verification

### Per-task acceptance gates

| Task | Gate | Result |
| --- | --- | --- |
| 3.1 G1 | `grep -c "response_format=config.response_format_model" jobs.py >= 1` | PASS (1) |
| 3.1 G2 | 6 new test fn names present | PASS (6) |
| 3.1 G3 | Intentional-RED: `grep -c "response_format_model=Recipe" agents.py == 0` (before 3.2) | PASS (0) |
| 3.1 G4 | `uv run python -c "from robotina.queue import jobs"` exits 0 | PASS |
| 3.2 G1 | All 5 NEW prompt files exist | PASS |
| 3.2 G2 | All 5 OLD prompt files preserved on disk | PASS |
| 3.2 G3 | New prompt files contain zero JSON boilerplate (grep -l count == 0) | PASS (0) |
| 3.2 G4 | `grep V003.md agents.py` returns the gather row | PASS (line 99) |
| 3.2 G5 | `grep -c V002.md agents.py >= 5` | PASS (5: instructions/ingredients/metadata/recipe-load + robotina) |
| 3.2 G6 | `grep -c "response_format_model=Recipe" agents.py == 5` | PASS (5) |
| 3.2 G7 | `git log --grep="(11-03)" \| wc -l >= 6` | PASS (8) |
| 3.2 G8 | `uv run pytest tests/test_agents.py -x` exits 0, 10 passed | PASS (10 passed in 0.01s) |
| 3.2 G9 | Smoke `python -c ...` registry binding check exits 0 | PASS ("SMOKE OK") |

### Test counts

```bash
$ uv run pytest tests/test_agents.py -v
collected 10 items
test_agentconfig_response_format_model_defaults_to_none                              PASSED
test_agentconfig_response_format_model_accepts_basemodel_subclass                    PASSED
test_get_agent_config_does_not_propagate_response_format_model_from_overrides        PASSED
test_get_agent_config_preserves_registry_response_format_model_through_model_config_override PASSED
test_registry_recipe_research_gather_bound_to_gather_output                          PASSED
test_registry_recipe_research_instructions_bound_to_instructions_output              PASSED
test_registry_recipe_research_ingredients_bound_to_ingredients_output                PASSED
test_registry_recipe_research_metadata_bound_to_metadata_output                      PASSED
test_registry_recipe_load_bound_to_load_output                                       PASSED
test_registry_non_scope_agents_have_no_response_format_model                         PASSED
10 passed in 0.01s
```

```bash
$ uv run pytest tests/test_llm_backend.py
5 passed in 0.56s
```

```bash
$ uv run pytest tests/unit/test_agents_registry.py
17 passed in 0.01s
```

**32 tests across the three agent-surface modules — all green in isolation.**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Updated prompt_path assertions in tests/unit/test_agents_registry.py**

- **Found during:** Task 3.2 — full unit suite regression check.
- **Issue:** Five tests in `tests/unit/test_agents_registry.py` pinned the OLD prompt paths (V002 for gather, V001 for the other four). After Plan 11-03 bumped the registry entries, those tests failed correctly — they asserted yesterday's truth.
- **Fix:** Updated the five `prompt_path == "...V###.md"` assertions to match the new versions. This is in-scope per Rule 1 ("direct consequence of this plan's changes"), even though `tests/unit/test_agents_registry.py` was not in the original `files_modified` frontmatter. The plan correctly listed `tests/test_agents.py` as in-scope; `tests/unit/test_agents_registry.py` is a sibling module that pinned the same paths.
- **Files modified:** `tests/unit/test_agents_registry.py`
- **Commit:** `9f3fd97`

### Out-of-scope failures (logged, NOT fixed)

The full `uv run pytest --ignore=tests/integration` suite shows **19 failures + 6 errors**. None are introduced by Plan 11-03; all pre-exist and were documented in Plan 11-01's `deferred-items.md`:

1. **DB-required tests (10 failures + 6 errors):** `tests/test_db_models.py`, `tests/test_gateway.py`. Require Postgres running locally. Worktree environment does not run docker-compose.
2. **Env-pollution in `tests/unit/test_agents_registry.py` (9 failures when run after polluting tests):** `AGENT_OVERRIDES_FILEPATH` is set by another test and not restored in teardown. Reproduced empirically: `pytest tests/unit/test_agents_registry.py` in isolation shows **17 passed**; running it after the polluting test makes 9 fail. This is unchanged from Plan 11-01's snapshot. Belongs in a separate maintenance quick-task.

Plan 11-03 did NOT introduce these failures and did NOT exacerbate them (the failure count is identical pre- and post-11-03).

## TDD Gate Compliance

Both tasks followed the RED → GREEN gate sequence:

| Task | RED commit                                           | GREEN commit                                                                    | Gate intact? |
| ---- | ---------------------------------------------------- | ------------------------------------------------------------------------------- | ------------ |
| 3.1  | `2878ec5` (`test(11-03):` — 6 tests, 5 RED + 1 already green) | `2878ec5` itself also threads `response_format` through `run_task` (same commit) | YES (gate met at commit boundary; 5 binding tests stay RED until Task 3.2) |
| 3.2  | (Task 3.1's binding tests carried over as RED)       | `ea263a4` (`feat(11-03):` — populates AGENT_REGISTRY)                            | YES          |

The plan deliberately co-located Task 3.1's `run_task` threading with the RED tests because the threading is a no-op on agents whose `response_format_model is None` — i.e. it's safe to land before the registry bindings, and `jobs.py` cannot be tested without a live RQ job anyway. Source-level grep was used as the gate per the plan's checker-revision 2026-05-13 note.

## Notes for Plan 11-04 (Phase 11 manual checkpoint)

- The 5 named agents now emit `state['structured_response']` populated with a Pydantic instance of their bound Output model. The canelones-class failure mode (free-text JSON wrapped in prose + markdown fence) is structurally impossible for these agents because `_extract_task_output` (Plan 11-02) reads `structured_response` directly and never inspects free-text agent content.
- Manual e2e checkpoint should verify: (a) a recipe-research workflow end-to-end produces a recipe saved to household-manager, (b) the 4 sub-agents each populate `WorkflowRunStep.artifact` with structured JSON matching their Pydantic schemas, (c) the recipe-load agent successfully resolves food/unit IDs and returns a `RecipeLoadOutput` with a non-empty `recipe_id`.
- After successful checkpoint, flip RRECIPE-07 and RLOAD-07 in REQUIREMENTS.md from "In Progress" to "Complete". (WF-10 flips in Plan 11-02's checkpoint.)

## Self-Check: PASSED

**Created files (verified):**
- `src/robotina/agent/prompts/recipe-research-gather/V003.md` — FOUND
- `src/robotina/agent/prompts/recipe-research-instructions/V002.md` — FOUND
- `src/robotina/agent/prompts/recipe-research-ingredients/V002.md` — FOUND
- `src/robotina/agent/prompts/recipe-research-metadata/V002.md` — FOUND
- `src/robotina/agent/prompts/recipe-load/V002.md` — FOUND

**Old prompts preserved (verified):**
- `src/robotina/agent/prompts/recipe-research-gather/V002.md` — FOUND
- `src/robotina/agent/prompts/recipe-research-instructions/V001.md` — FOUND
- `src/robotina/agent/prompts/recipe-research-ingredients/V001.md` — FOUND
- `src/robotina/agent/prompts/recipe-research-metadata/V001.md` — FOUND
- `src/robotina/agent/prompts/recipe-load/V001.md` — FOUND

**Commits exist (verified):**
- `2878ec5` — Task 3.1 RED + run_task threading — FOUND
- `b8d8241` — gather V003 — FOUND
- `c97e5f1` — instructions V002 — FOUND
- `b341a65` — ingredients V002 — FOUND
- `aba9682` — metadata V002 — FOUND
- `5189d20` — recipe-load V002 — FOUND
- `ea263a4` — agents.py registry binding (Task 3.2 GREEN) — FOUND
- `9f3fd97` — Rule 1 fix: test_agents_registry.py prompt-path assertions — FOUND
