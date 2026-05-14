# Phase 15: Recipe Artifact Accumulation and Food/Unit Validation — Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Refactor the 5-step recipe-research pipeline (gather → instructions → ingredients → metadata → load) so that:

1. **Each sub-agent emits a copy of the same `RecipeData` artifact with more fields populated.** No more disjoint per-step output schemas. The artifact accumulates as it travels through the workflow; the workflow_runner snapshot on `workflow_run_steps.artifact` continues to work unchanged (each row carries that step's incremental snapshot — same plumbing as today).
2. **Food and unit validation moves into the ingredients step** via two new agent tools — `validate-foods` and `validate-units` — that resolve a list of Spanish names against the household-manager catalog. Each tool: (a) does a single full-catalog fetch, (b) does normalized exact match (lowercase + NFKD accent-strip) programmatically, (c) on any unmatched items, makes a single batched LLM call against the full catalog to find semantic matches, (d) returns `{matched: [{name,id}], unmatched: [{name,id:null}]}`.
3. **Recipe-load shrinks to a happy-path POST + targeted error recovery.** Because the artifact arrives with `food_id` / `unit_id` already resolved on every ingredient, recipe-load no longer has to fetch foods/units. It applies the snake_case → camelCase field renames (as in V004 today), POSTs, and on a non-2xx error it can use the same two validation tools to fix a bad resolution and retry. RecipeLoadOutput shrinks to API-response fields only.
4. **The notification step reads `missing_ingredients` from the metadata-step artifact**, not from RecipeLoadOutput.

The phase is a pipeline refactor — workflow shape (steps, dependencies, sequential execution) and infrastructure (LangChain 1.x agents, `response_format`, middleware) stay exactly as in Phase 12. The only behavior change is: recipe-load reliably succeeds for any recipe whose ingredients are in (or near) the household catalog.

</domain>

<decisions>
## Implementation Decisions

### Accumulating Artifact Shape

- **D-01:** Single mutable `RecipeData` (in `src/robotina/queue/task_types.py`) becomes the shared artifact across all 5 sub-agents. All current required fields become Optional except a minimal core (`name` required when the artifact reaches recipe-load; everything else `| None`). Every sub-agent binds `response_format=RecipeData` on `create_agent` (per Phase 11), receives the previous step's artifact in its user message, and emits a copy with additional fields populated.
- **D-02:** Existing artifact plumbing in `src/robotina/queue/workflow_runner.py` is unchanged. Each sub-agent's full RecipeData snapshot continues to land in `workflow_run_steps.artifact` so the DB-backed debugging path (and the Phase 13 dashboard) keeps working — every step's row shows that step's incremental progress.
- **D-03:** `RecipeIngredient` gains `food_id: str | None` and `unit_id: str | None`. The ingredients step's validation tools populate them. Recipe-load reads ids only — `food_name` / `unit_name` are not required by recipe-load.
- **D-04:** Add `gathered_sources: list[dict] | None = None` to `RecipeData`. The gather step populates it; instructions / ingredients / metadata read from it. The metadata step's final emit sets it back to `None` so the artifact handed to recipe-load is a clean payload. Intermediate `workflow_run_steps.artifact` rows still contain the sources for DB-level debugging.
- **D-05:** Add `missing_ingredients: list[str] = []` to `RecipeData`. The ingredients step's validation tools surface unmatched names; the agent drops those items from `ingredients[]` and appends the names here. The notification step reads it from the final (metadata-step) artifact — no longer from `RecipeLoadOutput`.

### Validation Tools Shape

- **D-06:** Two distinct LangChain `BaseTool` classes — `validate-foods` and `validate-units` — in new files `src/robotina/agent/tools/validate_foods.py` and `src/robotina/agent/tools/validate_units.py`. Each tool's `args_schema` accepts a single `names: list[str]`. Shared logic (HTTP fetch, normalize-match, LLM-fallback orchestration) lives in a sibling helper module (e.g. `src/robotina/agent/tools/_catalog_match.py`).
- **D-07:** Each tool fetches the full catalog per call via `GET /api/foods` / `GET /api/units` (the household-manager skill already documents that omitting the `name=` param returns the full list). The catalog list is processed entirely client-side. No per-name filtered queries, no per-workflow cache plumbing.
- **D-08:** Direct-match rule = normalized exact match. Apply `unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode("ascii").casefold().strip()` (or equivalent) to both the agent's input name and each catalog entry's name, then compare for equality. Captures common accent/case typos at zero LLM cost.
- **D-09:** Tool return shape (the LangChain tool's `_run` / `_arun` return value, serialized to a `ToolMessage` for the agent):
  ```jsonc
  {
    "matched":   [ {"name": "Cebolla",  "id": "uuid-1"}, ... ],
    "unmatched": [ {"name": "ricotón", "id": null},     ... ]
  }
  ```
  The agent's prompt explains: take `matched[]` → resolved ingredient entries (with `food_id` / `unit_id` set); take `unmatched[].name` → append to `missing_ingredients[]` and drop those ingredients from `ingredients[]`. No `matched_via`, `canonical_name`, `confidence`, or candidate-list fields are emitted by the tool.
- **D-10:** Tool wiring reuses the same httpx-based HTTP + base-URL + auth setup that `HouseholdManagerApiTool` uses today. No `household_id` injection is required (the catalog is shared across households for the v1 single-household setup). The tools register through the same path the other tools register through (in `src/robotina/agent/tools/__init__.py` and the agent-runner's per-job tool-binding flow).

### Semantic Match Fallback

- **D-11:** Library = LangChain's own structured output. The catalog-match helper builds a small `LLMBackend` for the matcher task, calls `backend.model.with_structured_output(SemanticMatchResult).with_retry(stop_after_attempt=2)`, and invokes it with the catalog + the unmatched-names list. No `instructor` dependency. Reuses the project's `LLMBackend` Protocol, the `AGENT_REGISTRY` config path, `overrides/*.json` runtime swap, the Phase 12 middleware (so the matcher's LLM call shows up in LangWatch alongside the agent's other turns).
- **D-12:** The matcher gets its own `AGENT_REGISTRY` entry — `"validate-catalog"` — with its own `model_config` (so it can use a cheap small model in prod and Ollama in dev) and a `VALIDATE_CATALOG_API_TOKEN` env var, mirrored in all three `overrides/*.json` files (per [[feedback_overrides_in_sync]]). Even though it isn't a workflow task type, it is a registered LLM call site, which is exactly what `AGENT_REGISTRY` is for.
- **D-13:** No-match policy is binary. The structured-output Pydantic model is `list[SemanticMatchEntry]` where `SemanticMatchEntry = {name: str, catalog_id: str | None}`. The LLM decides — given a name and the full catalog — whether any catalog entry is a good enough fit; if not, `catalog_id` is `null`. The tool propagates `null`-id rows into `unmatched`. No confidence score, no ranked candidates, no threshold knob to tune.
- **D-14:** The LLM sees the full catalog (name-id pair list) in the prompt — no rapidfuzz / difflib pre-filter, no embedding shortlist. Catalogs of this size (a few hundred Spanish names) fit easily in any modern model's context.
- **D-15:** One batched LLM call per tool invocation. The matcher receives all unmatched names at once and returns the full results list. Catalog is paid once per tool call. Per-item calls are explicitly rejected (N× cost, N× latency, N× LangWatch traces, no cross-item benefit).

### Recipe-load's New Role

- **D-16:** Recipe-load **stays an agent** (in `AGENT_REGISTRY`). Happy path is small: take the resolved artifact, apply the snake_case → camelCase rename, `POST /api/recipes`. The agent is retained so that on a non-2xx response (e.g., a stale `foodId`, a field-rename slip, an enum violation) it can read the error body, fix the request, and retry — preserving the recovery loop already encoded in V004.
- **D-17:** Recipe-load's tool surface = `household-manager-api` + `read-skill` + `validate-foods` + `validate-units`. The two validation tools are added (vs V004) specifically so the agent can re-resolve a food/unit during recovery when the API rejects an id.
- **D-18:** Field renames (snake_case → camelCase: `servings_qty → servingsQty`, etc.) stay inside the recipe-load prompt — same rename table the V004 prompt uses today. The artifact Pydantic models do not get `by_alias` aliases (would couple the artifact shape to the household-manager wire format unnecessarily — workflow_runner, dashboard, and tests all read the snake_case form).
- **D-19:** `RecipeLoadOutput` drops `missing_ingredients`. It carries only API-response fields (`recipe_id`, `recipe_name`, `recipe_description`, `recipe_slug`). The notification step's `_build_notify_text` in `src/robotina/agent/workflows.py` is updated to take both `artifacts["metadata"]` (for `missing_ingredients`) and `artifacts["load"]` (for the API echo fields).

### Out of Scope

- **D-20:** No new RQ task_type for the matcher beyond the `AGENT_REGISTRY` entry (which is consulted by the helper module, not the task-runner). The matcher is invoked synchronously inside a tool call — it does not occupy a workflow step.
- **D-21:** No catalog cache shared across workflow runs. Catalogs are fetched fresh per tool invocation. If catalog-fetch latency becomes painful (it shouldn't for ~hundreds of items), revisit in a later phase.
- **D-22:** No catalog-write path. The tools never POST new foods or units. Unmatched items stay unmatched and are surfaced as `missing_ingredients`. Same posture as today.
- **D-23:** No changes to workflow shape. The 7 steps (acknowledge → gather → instructions → ingredients → metadata → load → notify) and their order are unchanged. `WorkflowStepDef.build_input` callables are updated to thread the accumulating artifact instead of per-step output schemas, but the workflow registry, the task-runner advancement hook, and the step-failure cascade are untouched.

### Claude's Discretion

- Prompt rewrites: every sub-agent prompt needs a structural rewrite for the new "you receive a partial RecipeData; emit a fuller RecipeData" contract. Wording, examples, and the exact "read these fields, populate these fields" framing are at Claude's discretion. Each prompt-version bump (e.g. `recipe-research-ingredients/V003 → V004`) must follow [[feedback_overrides_in_sync]] — prompt + `AGENT_REGISTRY` in `src/robotina/agent/agents.py` + every `overrides/*.json` in one atomic commit.
- Pydantic model layout: which file the new `SemanticMatchEntry` / `SemanticMatchResult` models live in (likely `src/robotina/agent/tools/_catalog_match.py` so they're co-located with the matcher) — Claude's discretion.
- Tool description strings: the `description` text on `validate-foods` / `validate-units` (read by the LLM at tool-binding time) is Claude's discretion. Should be tight, ≤4 sentences, no schema duplication (LangChain renders the `args_schema` automatically).
- Alembic migration: none required — no DB schema change. The artifact shape lives in Pydantic, not in `workflow_run_steps.artifact` which is a JSON column.
- Test surface: unit tests for `_catalog_match` (direct-match edge cases, semantic-fallback contract via a fake LLM), integration test for `validate-foods` / `validate-units` against a mocked household-manager. Recipe-load end-to-end via the existing experiment script. Detailed test plan = Claude's discretion at plan time.
- Whether to deprecate or delete the now-unused intermediate output models (`RecipeResearchGatherOutput`, `RecipeResearchInstructionsOutput`, `RecipeResearchIngredientsOutput`, `RecipeResearchMetadataOutput`) — they all become aliases for `RecipeData` in spirit. Claude's discretion: rename, alias, or delete. The `*Input` models stay (workflow_runner relies on them for `build_input`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project documents
- `.planning/ROADMAP.md` §"Phase 15" — Goal and scope statement (the version after the in-place title cleanup).
- `.planning/PROJECT.md` — Tech stack, concurrency constraint, "Key Decisions" table that lists `RecipeData uses human-readable food/unit names (not IDs)` (this phase explicitly amends that decision — recipe-load now consumes ids).
- `.planning/REQUIREMENTS.md` §"Recipe Research Agent" and §"Recipe Loader Agent" — current RLOAD-* / RRECIPE-* requirements. New requirements for this phase will reference these.

### Prior phase context that shapes Phase 15
- `.planning/phases/11-structured-agent-output-via-response-format/11-CONTEXT.md` — Locks `create_agent(response_format=…)` as the agent shape on every artifact-producing agent. D-01 here builds directly on it: the same RecipeData model becomes the `response_format=` target on all 5 sub-agents.
- `.planning/decisions/response-format-adoption.md` (referenced in CLAUDE.md) — Per-provider strategy (Ollama → ToolStrategy; Anthropic / OpenAI → ProviderStrategy). Applies unchanged to the unified RecipeData target.
- `.planning/phases/12-middleware-based-agent-instrumentation/12-CONTEXT.md` — Middleware-based instrumentation is in place; the matcher LLM call (D-11) reuses LLMBackend so it gets the same middleware treatment automatically.
- `.planning/phases/14-prompt-cleanup-and-structural-standardization/14-CONTEXT.md` — Standardized prompt skeleton (Role / Inputs / Tools / Process / Rules / Output). All Phase 15 prompt rewrites adopt this skeleton.

### Code paths the planner / executor will touch
- `src/robotina/queue/task_types.py` — RecipeData / RecipeIngredient / RecipeStep / all `Recipe*Input` and `Recipe*Output` models. Most edits land here.
- `src/robotina/agent/workflows.py` — `WORKFLOW_REGISTRY["add-recipe"].steps[*].build_input` callables thread the accumulating RecipeData; `_build_notify_text` reads from both `metadata` and `load` artifacts.
- `src/robotina/agent/agents.py` — `AGENT_REGISTRY` gains a `validate-catalog` entry (per D-12); the 5 recipe sub-agents' `prompt_path` values bump to new versions; recipe-load's `tools` list grows.
- `src/robotina/agent/tools/__init__.py` (and the per-job tool-binding flow in the agent runner) — registers `validate-foods` / `validate-units` and wires them into the ingredients and recipe-load agents.
- `src/robotina/agent/tools/household_manager_api.py` — reference implementation for the httpx + auth setup the new tools mirror.
- `src/robotina/agent/prompts/recipe-research-gather/`, `…-instructions/`, `…-ingredients/`, `…-metadata/`, `recipe-load/` — new V*.md prompt versions per the new contract.
- `overrides/anthropic.json`, `overrides/openai.json`, `overrides/staging.ollama.json` — every prompt-path bump and the new `validate-catalog` entry must land in all three in the same commit ([[feedback_overrides_in_sync]]).

### household-manager API references (skill)
- `src/robotina/agent/skills/household-manager/shared.md` §"Filtering reference lists" — confirms `GET /api/foods` / `GET /api/units` with no `name=` param returns the full list as a plain array. This is the contract the new tools depend on.
- `src/robotina/agent/skills/household-manager/recipes_create.md` — `POST /api/recipes` field shapes; foundation for the snake_case → camelCase rename table inside the recipe-load prompt (D-18).

### Memory / non-file references
- [[feedback_overrides_in_sync]] — Every prompt/registry/overrides change must be atomic. Applies to every prompt-version bump and the new `validate-catalog` entry.
- [[feedback_prompts_language]] — System prompts stay in English; user-facing recipe content stays in Argentine/LATAM Spanish.
- [[feedback_avoid_premature_abstraction]] — Justifies "two distinct tools" (D-06) over a single category-parameterized tool, and "agent + tools" over a `category-validator` Protocol.
- [[feedback_env_example]] — The new `VALIDATE_CATALOG_API_TOKEN` env var must be added to `.env.example`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/robotina/agent/tools/household_manager_api.py` — `HouseholdManagerApiTool` is the reference implementation for the httpx + auth pattern the new validation tools mirror. Includes the `args_schema` + `extra='forbid'` pattern that turns LLM-hallucinated extra fields into a recoverable `ToolMessage(status='error')` — `validate-foods` / `validate-units` adopt the same pattern with their tighter `names: list[str]` schema.
- `src/robotina/agent/agents.py` — `AGENT_REGISTRY` and the override-merge logic in `get_agent_config` are the right home for the new `validate-catalog` entry. The `prompt_path` + `model_config` + override pattern is exactly what the matcher needs (even though `validate-catalog` is invoked inside a tool, not as a workflow step).
- `src/robotina/llm/` — `LLMBackend` Protocol + 3 adapter classes. The matcher (D-11) instantiates one via the same path the agent runner uses.
- `src/robotina/queue/task_types.py` — RecipeData/RecipeIngredient/RecipeStep already exist and are the right shape to evolve. Optional-everywhere is a one-line-per-field change.
- `src/robotina/agent/workflows.py` — `WorkflowDefinition.build_input` callables are already the integration point; updating them to thread a single accumulating `RecipeData` is a localized change.

### Established Patterns
- **Per-job tool injection** — Tools are constructed once per job with task-input data (the `HouseholdManagerApiTool(household_id=task_input.household_id)` pattern). `validate-foods` / `validate-units` don't need household_id but should follow the same construction-time-config pattern for consistency.
- **Versioned prompts + `feedback_overrides_in_sync`** — Each prompt version bump is its own atomic commit. With 5 prompts to bump (gather, instructions, ingredients, metadata, recipe-load) and the new `validate-catalog` entry, the planner will likely produce 6 sequential plans.
- **`response_format=` is bound inside `LLMBackend.create_agent()`** — The matcher's `with_structured_output(...)` call is the equivalent path for a non-agent LLM call.
- **Strict args_schema with `extra='forbid'`** — Recovers from LLM tool-arg hallucinations gracefully. The new tools adopt this.
- **Phase 13 dashboard reads `workflow_run_steps.artifact`** — Reinforces D-02 (existing artifact plumbing must keep working). Each step's artifact still needs to be a meaningful, parseable snapshot.

### Integration Points
- `WorkflowStepDef.build_input` (workflows.py): every recipe-research sub-step's `build_input` now reads `artifacts[<prev_step_key>]` and feeds the accumulating RecipeData into the next step's `*Input` model.
- `_extract_task_output` (queue/workflow_runner.py): unchanged — it already reads `result["structured_response"]` from agents with `response_format`. Phase 11 settled that contract.
- Agent runner tool-binding flow: the ingredients agent's tools list grows by 2; recipe-load's tools list grows by 2.
- The Phase 13 dashboard: no changes needed; each step's snapshot is still a JSON dict and the failure_reason / step_input wiring from Phase 13 still works the same way.

</code_context>

<specifics>
## Specific Ideas

- "The artifact should be shaped with whatever data recipe-load needs and nothing more — names are noise for recipe-load." → D-03 / D-19 phrased the way recipe-load actually consumes the artifact.
- "Continue using artifacts plumbing as-is so each step's snapshot remains visible in the DB for troubleshooting." → D-02.
- "Need a field on the artifact for the original gathered data so downstream steps have a source to parse from." → D-04.
- "Match all unmatched items in one LLM call, not one call per item." → D-15 with the reasoning paid up front in the discussion log.
- "Recipe-load still uses an agent so it can recover from API errors even though the happy path is simple." → D-16.

</specifics>

<deferred>
## Deferred Ideas

- **In-memory catalog cache shared across workflow runs.** Currently each tool invocation re-fetches `/api/foods` and `/api/units`. If profiling shows this is a meaningful latency hit, add a TTL cache. Not in Phase 15 because there's no evidence of pressure and concurrency=1 keeps the catalog hot in the household-manager's own cache anyway.
- **`POST /api/foods` / `POST /api/units` from the agent** to auto-onboard truly novel ingredients. Out of scope for Phase 15 — same posture as recipe-load V004 (we never invent catalog entries).
- **Embedding-based semantic match.** D-14 explicitly chose full-catalog-in-prompt; embeddings would only be considered if catalogs grow into the thousands of items (no current evidence of that).
- **Confidence threshold / candidate-ranking on the matcher.** D-13 chose binary. Could be revisited if the matcher starts producing wrong-but-plausible matches in practice.
- **Phase 999.1 (custom state schemas)** — Already in the backlog. The accumulating artifact pattern here is *workflow-runner-level* (artifacts dict); custom agent state schemas are an orthogonal future improvement.

</deferred>

---

*Phase: 15-recipe-artifact-accumulation-and-food-unit-validation*
*Context gathered: 2026-05-14*
