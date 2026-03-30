# Phase 8: recipe-research Agent - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the recipe research pipeline as 4 sequential workflow sub-tasks: `recipe-research-gather`, `recipe-research-instructions`, `recipe-research-ingredients`, and `recipe-research-metadata`. Each sub-task gets its own task type, I/O models, and prompt. They share a single `recipe-research` skill with sub-files. The `add-recipe` workflow registry is updated from 3 steps to 6 steps (gather -> instructions -> ingredients -> metadata -> load -> notify). A combined experiment script tests the full 4-step pipeline. `recipe-load` remains a stub (Phase 9).

</domain>

<decisions>
## Implementation Decisions

### Workflow Architecture
- **D-01:** The original single `recipe-research` task type is replaced by 4 sequential sub-tasks: `recipe-research-gather`, `recipe-research-instructions`, `recipe-research-ingredients`, `recipe-research-metadata`. Each is a separate task type with its own `AgentConfig` entry in `agents.py`.
- **D-02:** The `add-recipe` workflow in `workflows.py` is updated from 3 steps (`research` -> `load` -> `notify`) to 6 steps (`gather` -> `instructions` -> `ingredients` -> `metadata` -> `load` -> `notify`). Each step has its own `WorkflowStepDef` with a `build_input` callable.
- **D-03:** Each step writes output to `WorkflowRunStep.artifact`. Subsequent steps read from `accumulated_artifacts` dict. No changes to `shared_context` needed — uses the existing workflow engine artifact accumulation pattern.
- **D-04:** 4 new Pydantic I/O model pairs are needed in `task_types.py` to replace `RecipeResearchInput/Output`. The existing `RecipeData`, `RecipeIngredient`, and `RecipeStep` shared models are reused in the final output.

### recipe-research-gather (Step 1)
- **D-05:** Constructs 3 Spanish search terms around the meal name (e.g., "Pasta Bolognesa facil de preparar", "pasta bolognesa deliciosa", "receta casera de salsa bolognesa"). Argentina-based recipe sites are prioritized.
- **D-06:** Uses `web-search` tool (Tavily API) for each search term, retrieving the top 3 results per query.
- **D-07:** Uses the `recipe-scrapers` Python package to extract structured recipe data from search result URLs. If `recipe-scrapers` fails for a URL, falls back to LLM extraction from the Tavily-indexed content.
- **D-08:** If a source yields no usable data from either method, skip it and continue. The step fails only if ALL sources are unusable. At least 1 usable source is sufficient to proceed.
- **D-09:** Stores all scraped/extracted recipes in the step's artifact output.

### recipe-research-instructions (Step 2)
- **D-10:** Reads all recipes found by the gather step from accumulated artifacts.
- **D-11:** Creates baseline recipe instructions using steps present in the majority of gathered recipes (consensus approach — e.g., if 6 out of 10 recipes mention salting the meat beforehand, include it).
- **D-12:** Stores the resulting instructions on the draft recipe artifact.

### recipe-research-ingredients (Step 3)
- **D-13:** Extracts all ingredients and quantities mentioned in the draft recipe instructions.
- **D-14:** Verifies each ingredient exists in the household-manager API using `GET /api/foods?name=` with Spanish food names directly. Reuses the existing `HouseholdManagerApiTool` from Phase 7 (injected in `run_task()`).
- **D-15:** If an ingredient doesn't exist in household-manager, checks the other gathered recipe drafts for a substitute. If no substitute is found, leaves the ingredient out entirely.
- **D-16:** Produces a final ingredients list and adds it to the draft recipe artifact.

### recipe-research-metadata (Step 4)
- **D-17:** Reads recipe metadata (prep time, servings) from all gathered recipes and the draft recipe instructions.
- **D-18:** Produces estimates for cooking time, prep time, and servings. The LLM always estimates from instructions — fields are never null. Even without scraped metadata, the LLM estimates from instruction complexity (e.g., pasta dish with 10 ingredients -> ~30 min cook time).
- **D-19:** Adds metadata to the draft recipe artifact. The final output conforms to the `RecipeData` model.

### Language & Locale
- **D-20:** All search terms are in Spanish. All output text (ingredient names, step instructions, description, recipe name) is in Spanish. Consistent with Robotina's recently added Spanish language support.
- **D-21:** Ingredient verification against household-manager API uses Spanish food names directly (e.g., `GET /api/foods?name=cebolla`). Assumes household-manager stores food names in Spanish.

### Skill Structure
- **D-22:** One shared `recipe-research` skill directory at `src/robotina/agent/skills/recipe-research/` with `index.md` + sub-files for each step (`gather.md`, `instructions.md`, `ingredients.md`, `metadata.md`). Each agent config references the same skill; agents load the relevant sub-file via `read-skill` tool.

### Experiment
- **D-23:** One combined experiment script at `experiments/recipe_research.py` that runs all 4 steps in sequence with a test recipe name. Tests the full pipeline end-to-end.
- **D-24:** Experiment pins prompt version and model config for each sub-task via LangWatch tags/metadata. Uses the same LangWatch instrumentation path as `run_task()` (per OBS-04).

### agents.py & run_task() Wiring
- **D-25:** 4 new entries in `AGENT_REGISTRY`: `recipe-research-gather`, `recipe-research-instructions`, `recipe-research-ingredients`, `recipe-research-metadata`. Each has its own prompt path, skill reference, and tool configuration.
- **D-26:** `run_task()` gets `elif` blocks for `recipe-research-gather` (inject `WebSearchTool`) and `recipe-research-ingredients` (inject `HouseholdManagerApiTool`). Other sub-tasks need only the `read-skill` tool (already injected generically).
- **D-27:** `recipe-scrapers` added as a project dependency via `uv add recipe-scrapers`.

### Claude's Discretion
- WebSearchTool implementation details (Tavily API parameters: max_results, search_depth, include_domains)
- Exact Pydantic I/O model field names for the 4 new task types
- Prompt wording for all 4 V001.md files
- Skill sub-file content depth and formatting
- How recipe-scrapers results are structured and passed to artifact
- Experiment evaluation criteria and output formatting
- Error handling details in WebSearchTool (rate limits, API errors)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Recipe research spec
- `plans/01-kickoff/spec.md` §"recipe-research" (line ~335) — `RecipeResearchInput` / `RecipeResearchOutput` original definitions (being replaced by 4 sub-task I/O models)
- `plans/01-kickoff/spec.md` §"Tools" (line ~553) — `web-search` tool description: Tavily API
- `plans/01-kickoff/spec.md` §"Skills" (line ~565) — `recipe-research` skill description
- `plans/01-kickoff/spec.md` §"Agents" (line ~784) — Recipe Research agent config: skill, prompt, tools, experiment
- `plans/01-kickoff/spec.md` §"Workflow Registry" (line ~386) — WorkflowStepDef and build_input pattern

### Requirements
- `.planning/REQUIREMENTS.md` §RRECIPE-01 through RRECIPE-06 — recipe research acceptance criteria (note: original requirements assume single task; implementation splits into 4 sub-tasks that collectively satisfy these requirements)
- `.planning/REQUIREMENTS.md` §OBS-04 — LangWatch experiment pinning prompt version and model config

### Prior context (locked decisions)
- `.planning/phases/04-llm-module-and-agent-infrastructure/04-CONTEXT.md` — D-03 (per-job objects inside run_task), D-07 (API token env var: `RECIPE_RESEARCH_GATHER_API_TOKEN`, etc.)
- `.planning/phases/06-send-notification-agent/06-CONTEXT.md` — D-06/D-07 (experiment pattern: representative inputs, LangWatch tags)
- `.planning/phases/07-handle-incoming-message-agent/07-CONTEXT.md` — HouseholdManagerApiTool pattern (reused by recipe-research-ingredients)

### Existing code the planner must read
- `src/robotina/queue/task_types.py` — `RecipeResearchInput/Output`, `RecipeData`, `RecipeIngredient`, `RecipeStep` (models to update/extend)
- `src/robotina/agent/agents.py` — `AGENT_REGISTRY` + `AgentConfig` pattern for adding 4 new entries
- `src/robotina/agent/workflows.py` — `WORKFLOW_REGISTRY` and `add-recipe` workflow definition to update
- `src/robotina/queue/jobs.py` — `run_task()` tool injection point for WebSearchTool and HouseholdManagerApiTool
- `src/robotina/agent/tools/household_manager_api.py` — `HouseholdManagerApiTool` to reuse for ingredients step
- `experiments/recipe_research.py` — stub to replace with combined experiment
- `src/robotina/agent/tools/send_notification.py` — BaseTool subclass pattern to follow for WebSearchTool

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/robotina/agent/tools/household_manager_api.py`: `HouseholdManagerApiTool` — reuse directly for recipe-research-ingredients to verify food names against `GET /api/foods?name=`
- `src/robotina/queue/task_types.py`: `RecipeData`, `RecipeIngredient`, `RecipeStep` shared models — the final metadata step output conforms to `RecipeData`
- `src/robotina/agent/tools/start_workflow.py`: `BaseTool` subclass with constructor injection — template for `WebSearchTool`
- `src/robotina/queue/jobs.py`: `run_task()` with `elif` tool injection pattern — extend for 2 new tool injection branches
- `experiments/send_notification.py`: Full experiment implementation — pattern for the combined recipe research experiment

### Established Patterns
- All per-job objects instantiated inside `run_task()`, never at module level (locked Phase 4)
- `BaseTool` subclass with constructor injection for tool state
- Skills at `src/robotina/agent/skills/<skill-name>/` with `index.md` + sub-files
- Prompts at `src/robotina/agent/prompts/<task-type>/V001.md`
- Workflow step `build_input` callables read from `(shared_context, accumulated_artifacts)`
- LangWatch experiment: `langwatch.trace()` + `LangChainTracer()` (same as production)

### Integration Points
- `workflows.py` `add-recipe` workflow must be expanded from 3 to 6 steps with new `build_input` callables
- `task_types.py` needs 4 new I/O model pairs (one per sub-task)
- `agents.py` needs 4 new `AgentConfig` entries
- `run_task()` needs `elif` branches for `recipe-research-gather` (WebSearchTool) and `recipe-research-ingredients` (HouseholdManagerApiTool)
- `pyproject.toml` needs `recipe-scrapers` dependency added

</code_context>

<specifics>
## Specific Ideas

- Search terms should be natural Spanish phrases that an Argentine cook would search for (e.g., "Pasta Bolognesa facil de preparar", "receta casera de salsa bolognesa") — not literal translations from English.
- Ingredient consensus: recipe-research-instructions uses a "majority rules" approach — if most scraped recipes include a step or technique, it gets included in the baseline.
- `recipe-scrapers` is tried first for structured extraction; LLM extraction from Tavily content is the fallback, not the primary method.
- The combined experiment should test with a real recipe name like "Pasta Bolognesa" or "Empanadas" to exercise the full pipeline including Spanish search and Argentine recipe sites.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 08-recipe-research-agent*
*Context gathered: 2026-03-30*
