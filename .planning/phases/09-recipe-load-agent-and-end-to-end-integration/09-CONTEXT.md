# Phase 9: recipe-load Agent and End-to-End Integration - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the recipe-load agent end-to-end: register `recipe-load` in `agents.py`, wire `HouseholdManagerApiTool` injection in `run_task()`, write `recipe-load/V001.md` prompt, extend `RecipeLoadOutput` with additional fields for richer notifications, update the workflow notify step text, and implement the `experiments/recipe_load.py` experiment script. The agent resolves human-readable food/unit names to household-manager IDs and creates recipes via the compound `POST /api/recipes` endpoint. The full add-recipe workflow runs end-to-end from a Telegram message to a delivered recipe confirmation.

</domain>

<decisions>
## Implementation Decisions

### Name Resolution Strategy
- **D-01:** Exact-first matching — when `GET /api/foods?name=` or `GET /api/units?name=` returns multiple results, pick the one whose name matches exactly (case-insensitive). If no exact match exists, the agent uses its common sense to pick the most reasonable result from the returned list.
- **D-02:** Zero matches — if a food name returns zero results, the ingredient is unresolvable (see D-03 for handling).

### Missing Ingredient Handling
- **D-03:** Skip unresolvable ingredients — drop them from the recipe payload and continue creating the recipe with the ingredients that resolved successfully. The recipe is always created (even if some ingredients are missing).
- **D-04:** Track skipped ingredients — add a `missing_ingredients: list[str]` field to `RecipeLoadOutput`. Populate it with the food names that could not be resolved. This is for troubleshooting/analytics; handling will be improved in a future iteration.

### Notification Content
- **D-05:** Richer notification — the confirmation message includes the recipe description and a link to the recipe in the app, not just the name.
- **D-06:** Extend `RecipeLoadOutput` with additional fields beyond `recipe_id` and `recipe_name`: add `recipe_description: str | None`, `recipe_slug: str`, and `missing_ingredients: list[str]` (default empty).
- **D-07:** Update the workflow notify step's `build_input` lambda to compose richer text from the load artifact: recipe name, description, and app link (using `HOUSEHOLD_MANAGER_BASE_URL` + `/recipe/{slug}`).

### Skill Design
- **D-08:** Reuse existing `household-manager` skill — no dedicated `recipe-load` skill directory. The agent's `AgentConfig` will list `skills=["household-manager"]`. The agent reads `recipes_create.md` sub-file for compound create documentation, name resolution endpoints, and examples. RLOAD-02's intent (agent has instructions for resolving names and creating recipes) is satisfied by the household-manager skill's comprehensive API docs.

### Unit Edge Cases
- **D-09:** Claude's discretion — general principle: don't lose ingredients over a missing unit. If `unit_name` is null or returns zero matches, omit `unitId` from the ingredient payload. The API accepts ingredients without `unitId`.

### Experiment Design
- **D-10:** Live API — experiment hits the real household-manager API (same pattern as recipe-research experiment). Requires `HOUSEHOLD_MANAGER_BASE_URL` and `HOUSEHOLD_MANAGER_API_KEY` env vars.
- **D-11:** Four edge cases to cover: (1) happy path with resolvable ingredients, (2) missing foods that return zero matches — verify they're tracked in `missing_ingredients`, (3) ambiguous names returning multiple matches — verify agent picks reasonably, (4) ingredients with null `unit_name` — verify `unitId` is omitted.

### agents.py & run_task() Wiring
- **D-12:** Register `recipe-load` in `AGENT_REGISTRY` with: `skills=["household-manager"]`, `tools=[]` (HouseholdManagerApiTool injected per-job), `prompt_path="src/robotina/agent/prompts/recipe-load/V001.md"`, model config following env-var pattern (`RECIPE_LOAD_API_TOKEN`).
- **D-13:** `run_task()` gets an `elif` block for `recipe-load` that injects `HouseholdManagerApiTool(household_id=task_input.household_id)` — same pattern as `recipe-research-ingredients`.

### Claude's Discretion
- Unit handling specifics (when to move unresolvable unit text to the ingredient `note` field)
- Exact compound create payload construction from `RecipeData` fields
- `recipe-load/V001.md` prompt wording, tone, and structure
- Experiment evaluation criteria and output formatting
- Error handling for API failures during name resolution (rate limits, timeouts)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Recipe loader spec
- `plans/01-kickoff/spec.md` §"recipe-load" (~line 335) — `RecipeLoadInput` / `RecipeLoadOutput` original definitions
- `plans/01-kickoff/spec.md` §"Tools" (~line 553) — `household-manager-api` tool description
- `plans/01-kickoff/spec.md` §"Skills" (~line 565) — `household-manager` skill description
- `plans/01-kickoff/spec.md` §"Agents" (~line 784) — Recipe Loader agent config: skill, prompt, tools, experiment

### Requirements
- `.planning/REQUIREMENTS.md` §RLOAD-01 through RLOAD-06 — recipe loader acceptance criteria
- `.planning/REQUIREMENTS.md` §OBS-04 — LangWatch experiment pinning prompt version and model config

### Household-manager API docs (skill sub-files)
- `src/robotina/agent/skills/household-manager/recipes_create.md` — Compound create endpoint, name resolution endpoints (`GET /api/foods?name=`, `GET /api/units?name=`), request/response shapes, recommended sequence
- `src/robotina/agent/skills/household-manager/shared.md` — Base URL, error codes, filtering reference lists behavior, data language (Spanish)
- `src/robotina/agent/skills/household-manager/recipes_get.md` — RecipeDetailResponse shape (matches POST /api/recipes response)

### Prior context (locked decisions)
- `.planning/phases/04-llm-module-and-agent-infrastructure/04-CONTEXT.md` — D-03 (per-job objects inside run_task), D-07 (API token env var pattern)
- `.planning/phases/06-send-notification-agent/06-CONTEXT.md` — D-06/D-07 (experiment pattern: representative inputs, LangWatch tags)
- `.planning/phases/07-handle-incoming-message-agent/07-CONTEXT.md` — D-02 (HouseholdManagerApiTool pattern), D-04 (run_task tool injection)
- `.planning/phases/08-recipe-research-agent/08-CONTEXT.md` — D-19 (RecipeData as final output), D-21 (Spanish food names in API)

### Existing code the planner must read
- `src/robotina/queue/task_types.py` — `RecipeLoadInput/Output` (output needs extension per D-06), `RecipeData`, `RecipeIngredient`
- `src/robotina/agent/agents.py` — `AGENT_REGISTRY` pattern for adding `recipe-load` entry
- `src/robotina/agent/workflows.py` — `add-recipe` workflow: `load` and `notify` steps need updates
- `src/robotina/queue/jobs.py` — `run_task()` tool injection point for HouseholdManagerApiTool
- `src/robotina/agent/tools/household_manager_api.py` — `HouseholdManagerApiTool` to reuse directly
- `experiments/recipe_load.py` — stub to replace with real implementation
- `experiments/recipe_research.py` — full experiment pattern to follow

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/robotina/agent/tools/household_manager_api.py`: `HouseholdManagerApiTool` — reuse directly. Already handles auth injection, 401/403 hard errors, and structured error responses.
- `src/robotina/queue/task_types.py`: `RecipeLoadInput(recipe: RecipeData, household_id: str)` and `RecipeLoadOutput(recipe_id, recipe_name)` — output needs extension per D-06.
- `src/robotina/agent/workflows.py`: `load` step `build_input` already wired: reconstructs `RecipeData` from metadata artifact.
- `experiments/recipe_research.py`: Full 4-step experiment with LangWatch tracing — direct template for recipe_load experiment.
- `src/robotina/agent/skills/household-manager/recipes_create.md`: Complete API documentation for compound create, name resolution, and examples.

### Established Patterns
- All per-job objects instantiated inside `run_task()`, never at module level (locked Phase 4)
- `HouseholdManagerApiTool(household_id=task_input.household_id)` injection in `run_task()` — same as Phase 7 and Phase 8 ingredients step
- Skills at `src/robotina/agent/skills/<skill-name>/` with `index.md` + sub-files
- Prompts at `src/robotina/agent/prompts/<task-type>/V001.md`
- LangWatch experiment: `langwatch.trace()` + `LangChainTracer()` path (same as production)
- All output text in Spanish (locked Phase 8)

### Integration Points
- `agents.py` needs `recipe-load` entry in `AGENT_REGISTRY`
- `run_task()` needs `elif` block for `recipe-load` to inject `HouseholdManagerApiTool`
- `task_types.py` `RecipeLoadOutput` needs 3 new fields: `recipe_description`, `recipe_slug`, `missing_ingredients`
- `workflows.py` notify step `build_input` needs update to compose richer notification text
- `.env.example` needs `RECIPE_LOAD_API_TOKEN` entry

</code_context>

<specifics>
## Specific Ideas

- Name resolution: exact-first, then agent judgment for multiple matches — the agent sees the full list of results and picks intelligently, not mechanically.
- Missing ingredients are tracked but not blocking — recipe always gets created. Future iteration will improve handling.
- Notification text: recipe description + app link (`{base_url}/recipe/{slug}`). Clean and actionable.
- Experiment follows the recipe-research experiment pattern but is single-step (not a pipeline). Four test cases exercising different resolution scenarios.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 09-recipe-load-agent-and-end-to-end-integration*
*Context gathered: 2026-03-30*
