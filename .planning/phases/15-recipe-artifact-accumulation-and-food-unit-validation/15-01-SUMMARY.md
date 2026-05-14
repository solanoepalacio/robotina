---
phase: 15-recipe-artifact-accumulation-and-food-unit-validation
plan: 01
subsystem: agent/queue
tags: [refactor, agent-tools, pipeline, llm-matcher]
requires:
  - "Phase 11: response_format on all recipe sub-agents"
  - "Phase 12: LLMBackend middleware (matcher LLM call piggybacks via LangChainTracer)"
provides:
  - "RecipeData (accumulating artifact) — shared shape for all 5 recipe sub-agents"
  - "RecipeIngredient.food_id / unit_id"
  - "validate-foods + validate-units BaseTool subclasses"
  - "validate-catalog AGENT_REGISTRY entry (matcher LLM)"
  - "resolve_catalog helper (NFKD direct match + batched semantic fallback)"
  - "Per-job tool injection for recipe-research-ingredients in jobs.py"
affects:
  - "src/robotina/queue/task_types.py (model shapes)"
  - "src/robotina/agent/workflows.py (build_input threading)"
  - "src/robotina/agent/agents.py (new agent registered)"
tech-stack:
  added:
    - "src/robotina/agent/tools/_catalog_match.py"
    - "src/robotina/agent/tools/validate_foods.py"
    - "src/robotina/agent/tools/validate_units.py"
    - "src/robotina/agent/prompts/validate-catalog/V001.md"
  patterns:
    - "Single batched LLM call for semantic fallback (D-15)"
    - "extra='forbid' args_schema on every new BaseTool (matches HouseholdManagerApiTool)"
    - "Deferred LLM-backend imports inside resolve_catalog (no module-level construction)"
    - "Method override method='function_calling' on Ollama with_structured_output (Pitfall 3)"
    - "LangChainTracer threaded via RunnableConfig for LangWatch coverage (Pitfall 2)"
key-files:
  created:
    - "src/robotina/agent/tools/_catalog_match.py"
    - "src/robotina/agent/tools/validate_foods.py"
    - "src/robotina/agent/tools/validate_units.py"
    - "src/robotina/agent/prompts/validate-catalog/V001.md"
    - "tests/test_catalog_match.py"
    - "tests/test_validate_foods.py"
    - "tests/test_validate_units.py"
  modified:
    - "src/robotina/queue/task_types.py"
    - "src/robotina/agent/workflows.py"
    - "src/robotina/agent/agents.py"
    - "src/robotina/agent/tools/__init__.py"
    - "src/robotina/queue/jobs.py"
    - "overrides/anthropic.json"
    - "overrides/openai.json"
    - "overrides/staging.ollama.json"
    - ".env.example"
    - "tests/test_task_types.py"
    - "tests/test_workflows.py"
    - "tests/test_workflow_runner.py"
decisions:
  - "RecipeData becomes the single shared artifact; all 5 sub-agents will bind it as response_format (locked from CONTEXT D-01..D-23)"
  - "Recipe*Output sentinels redefined as = RecipeData (aliases preserve existing imports)"
  - "RecipeLoadInput gains reply_context (collapses every downstream input to the same 3-field shape, supersedes WF-09 for RecipeLoadInput)"
  - "Tool wiring lives in jobs.py per-job branches; AGENT_REGISTRY[*].tools stays [] by design"
metrics:
  duration: "~1.5 hours"
  completed: 2026-05-14
  tasks: 3
  files_created: 7
  files_modified: 12
  commits: 3
---

# Phase 15 Plan 01: Foundation — Accumulating RecipeData + validate-foods/units + matcher

JWT-style accumulating-artifact refactor of the recipe-research pipeline plus two new household-manager validation tools backed by an NFKD-direct-match + single-batched-LLM-call matcher.

## What Was Built

### 1. Shared accumulating `RecipeData` artifact

`src/robotina/queue/task_types.py` was rewritten so that **only `name` is required** on `RecipeData`. Every other field defaults to `None` / `[]`. Two new fields land here:

- `gathered_sources: list[dict] | None = None` — populated by the gather step; cleared by metadata.
- `missing_ingredients: list[str] = []` — populated by ingredients (names the validation tools could not resolve); preserved by metadata; read by `_build_notify_text`.

`RecipeIngredient` gains `food_id: str | None = None` and `unit_id: str | None = None` (resolved by the ingredients-step validation tools; consumed by recipe-load).

`RecipeLoadOutput` **drops** `missing_ingredients` per D-19; it now carries only API-response fields (`recipe_id`, `recipe_name`, `recipe_description`, `recipe_slug`).

All four downstream `Recipe*Input` models collapse to `{recipe: RecipeData, reply_context: ReplyContext, household_id: str}`:

- `RecipeResearchInstructionsInput`
- `RecipeResearchIngredientsInput`
- `RecipeResearchMetadataInput`
- `RecipeLoadInput`

`RecipeResearchGatherInput` keeps `{query, reply_context, household_id}` because gather has no prior artifact to thread. The four `Recipe*Output` sentinels are redefined as **aliases** for `RecipeData` (`RecipeResearchGatherOutput = RecipeData`) — existing imports keep working; every sub-agent's `response_format_model` now points at the same shape.

### 2. `workflows.py` rewiring

Every research sub-step's `build_input` now reads `RecipeData(**artifacts[<prev_step_key>])` and feeds it as `recipe=` into the next step's collapsed input. The load step uses `artifacts["metadata"]` directly (no wrapping `"recipe"` key — the artifact dict IS the RecipeData dump). `_build_notify_text(metadata_artifact, load_artifact)` now reads `missing_ingredients` from `metadata_artifact` and the recipe echo fields from `load_artifact`.

### 3. `validate-catalog` matcher LLM

New AGENT_REGISTRY entry `validate-catalog` (Ollama gpt-oss:20b default, mirrored in all three `overrides/*.json`). It has its own prompt (`src/robotina/agent/prompts/validate-catalog/V001.md`) and its own env var (`VALIDATE_CATALOG_API_TOKEN`) in `.env.example`. The matcher is **not** a workflow task type — it is invoked synchronously from inside the `resolve_catalog` helper.

`resolve_catalog(category, catalog, names)` (in `_catalog_match.py`):

1. NFKD-normalized direct match: `unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode("ascii").casefold().strip()`. Zero LLM cost.
2. For the unmatched remainder, **one batched LLM call** with the full catalog + remaining names. The matcher backend is built per call (`get_agent_config("validate-catalog")` + `make_backend`) so AGENT_OVERRIDES_FILEPATH hot-reload behaves consistently.
3. Ollama backends get `method="function_calling"` passed to `with_structured_output` (Pitfall 3 — gpt-oss returns malformed output under the default `json_schema` method).
4. `LangChainTracer()` is threaded via `RunnableConfig(callbacks=...)` so the matcher's LLM call appears in LangWatch traces (Pitfall 2 — `with_structured_output` is NOT covered by Phase 12's `create_agent` middleware).
5. Defensive filter: drops matcher responses that hallucinate input names not present in `names`, and drops responses that reference a `catalog_id` not present in the input catalog.

### 4. `validate-foods` and `validate-units` BaseTool subclasses

Both tools mirror `HouseholdManagerApiTool`:

- `args_schema` with `extra="forbid"` (LLM-hallucinated extra args become recoverable `ToolMessage(status="error")`).
- `GET /api/foods` / `GET /api/units` via `httpx.AsyncClient` with `Authorization: Bearer {HOUSEHOLD_MANAGER_API_KEY}`.
- 401/403 → `raise RuntimeError(...)` (hard stop). Other non-2xx → `{"error": status, "message": text}`.
- 2xx → hand the full catalog list to `resolve_catalog(category=..., catalog=..., names=...)` and return its envelope.

Return shape (D-09):
```json
{
  "matched":   [ {"name": "Cebolla",  "id": "uuid-1"}, ... ],
  "unmatched": [ {"name": "ricotón", "id": null},     ... ]
}
```

### 5. Per-job tool injection in `jobs.py`

The `recipe-research-ingredients` branch now appends `ValidateFoodsTool()` and `ValidateUnitsTool()` alongside `HouseholdManagerApiTool(household_id=...)`. AGENT_REGISTRY[*].tools stays `[]` by design — wiring lives in `jobs.py`. **Recipe-load wiring is Plan 15-06's responsibility** (intentional — pairs with the V005 prompt bump).

### 6. Test coverage

- `tests/test_catalog_match.py` (13 tests): normalize edge cases (case, accents, ñ→n, whitespace); direct-match shortcut skips LLM; semantic-fallback invokes matcher exactly once; `catalog_id=None` propagates; hallucinated-name filter; hallucinated-id filter; unaddressed-name fallthrough; `validate-catalog` AGENT_REGISTRY loadable.
- `tests/test_validate_foods.py` (7 tests): strict args_schema rejects extras; direct match; semantic fallback; 401/403 raise `RuntimeError`; 500 returns error dict; tool metadata; AGENT_REGISTRY[ingredients].tools stays `[]`.
- `tests/test_validate_units.py` (6 tests): mirrors validate-foods coverage.
- `tests/test_task_types.py` rewritten for the Phase 15 contract (only-`name`-required, food_id/unit_id, RecipeLoadOutput shape, collapsed inputs).
- `tests/test_workflows.py` rewritten to assert the new `build_input` threading semantics and `_build_notify_text(metadata, load)` signature.

## Commits

| Task | Commit | Subject |
|------|--------|---------|
| 1 | `5bd34d2` | feat(15-01): accumulating RecipeData artifact + collapsed Recipe*Input models |
| 2 | `bdebb61` | feat(15-01): add validate-catalog matcher (NFKD + semantic fallback) |
| 3 | `989eabc` | feat(15-01): validate-foods + validate-units tools + per-job wiring |

## Test Results

- `uv run pytest tests/test_catalog_match.py tests/test_validate_foods.py tests/test_validate_units.py` → **27 passed**
- `uv run pytest tests/test_task_types.py tests/test_workflows.py tests/test_workflow_runner.py` → **54 passed** (1 deselected: DB migration test needs Postgres)
- Full non-DB suite: **203 passed**
- DB-dependent test failures are pre-existing baseline (Postgres not running locally); zero new failures attributable to this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Test patch target for `make_backend` was inside helper module, but the function uses a deferred import**

- **Found during:** Task 2 test run
- **Issue:** `tests/test_catalog_match.py` initially patched `robotina.agent.tools._catalog_match.make_backend`, but `make_backend` is imported **inside** `resolve_catalog` (per the locked architectural rule — no module-level adapter construction). The patch raised `AttributeError: module … does not have the attribute 'make_backend'`.
- **Fix:** Switched all patches to `robotina.llm.make_backend` (the source module) and `robotina.agent.agents.get_agent_config`. Applied the same fix in `test_validate_foods.py` / `test_validate_units.py`.
- **Commit:** included in `bdebb61`, `989eabc`.

**2. [Rule 1 — Bug] Existing `test_workflow_runner.py::test_reply_context_not_in_recipe_load_input` asserted the old WF-09 contract**

- **Found during:** Task 1 verification (`uv run pytest tests/test_workflow_runner.py`)
- **Issue:** The plan explicitly adds `reply_context` to `RecipeLoadInput` (and to every other downstream input) so build_input can thread reply context for the recipe-load recovery loop. The legacy test asserted the opposite.
- **Fix:** Renamed the test to `test_recipe_load_input_has_reply_context` with an explanatory docstring that Phase 15 supersedes WF-09 for this model. The legacy `RecipeResearchInput` (single-shot) test still asserts no reply_context — that model is untouched.
- **Commit:** `5bd34d2`.

**3. [Rule 2 — Missing critical functionality] Test for "unaddressed name" fallthrough**

- The plan's `<behavior>` enumerates: hallucinated names dropped, hallucinated ids dropped, null id → unmatched. It does not explicitly call out the case where the matcher returns FEWER entries than input names. Added a regression test (`test_resolve_catalog_unaddressed_name_becomes_unmatched`) because the implementation's defensive design — populate `unmatched` for every `remaining` name not addressed by the LLM — is load-bearing and needs pinning.
- **Commit:** `bdebb61`.

### Authentication / Environment Gates

None. All work was offline / mocked.

### Architectural Decisions (none required Rule 4 / user input)

All decisions in the plan were already locked in CONTEXT D-01..D-23.

## Known Stubs

None. Every code path created in this plan is fully wired:
- `validate-foods` / `validate-units` tools are constructed in `jobs.py`'s `recipe-research-ingredients` branch.
- `validate-catalog` matcher is reachable via `resolve_catalog` (called from both tools).
- All 3 overrides files carry the new entry.
- `.env.example` lists `VALIDATE_CATALOG_API_TOKEN`.

**Note:** Sub-agent prompts (gather/instructions/ingredients/metadata/recipe-load) still emit the OLD per-step output shapes — they are bumped to the new RecipeData contract in **Plans 15-02..15-06**. Running the live `add-recipe` workflow against the gather V004 prompt today will fail at `_extract_task_output`'s structured-response check, because gather's `response_format_model` is now `RecipeData` (which requires `name`) but the V004 prompt emits `{"recipes": [...]}`. This is intentional and called out in the plan — the foundation lands first, then the prompt rewrites cascade behind it. The Python test suite (which mocks LLM output) is unaffected.

## Threat Flags

None. No new network endpoints introduced; the new tools call existing household-manager endpoints (`GET /api/foods`, `GET /api/units`) with the existing auth flow.

## Self-Check: PASSED

- ✅ `src/robotina/queue/task_types.py` updated; `food_id`, `gathered_sources`, `missing_ingredients` present; `RecipeLoadOutput` no longer has `missing_ingredients`.
- ✅ `src/robotina/agent/tools/_catalog_match.py` created.
- ✅ `src/robotina/agent/tools/validate_foods.py` created.
- ✅ `src/robotina/agent/tools/validate_units.py` created.
- ✅ `src/robotina/agent/prompts/validate-catalog/V001.md` created.
- ✅ `AGENT_REGISTRY["validate-catalog"]` resolvable.
- ✅ All 3 `overrides/*.json` contain `validate-catalog` (verified by `json.load` + `'validate-catalog' in` check).
- ✅ `.env.example` lists `VALIDATE_CATALOG_API_TOKEN`.
- ✅ `src/robotina/queue/jobs.py` `recipe-research-ingredients` branch appends both validation tools (grepped).
- ✅ All three task commits exist (`5bd34d2`, `bdebb61`, `989eabc`) in `git log`.
- ✅ `uv run pytest tests/test_catalog_match.py tests/test_validate_foods.py tests/test_validate_units.py` → 27 passed.
