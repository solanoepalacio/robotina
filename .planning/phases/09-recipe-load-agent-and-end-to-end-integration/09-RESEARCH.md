# Phase 9: recipe-load Agent and End-to-End Integration - Research

**Researched:** 2026-03-30
**Domain:** LangChain agent implementation, household-manager API integration, workflow orchestration
**Confidence:** HIGH

## Summary

Phase 9 completes the final agent in Robotina's add-recipe workflow. The recipe-load agent takes a `RecipeData` object (produced by the recipe-research pipeline in Phase 8), resolves human-readable food and unit names to household-manager IDs via `GET /api/foods?name=` and `GET /api/units?name=`, then creates the recipe atomically via `POST /api/recipes` with compound create. The agent also needs to handle edge cases: zero matches (skip ingredient), multiple matches (pick best via agent judgment), and missing units (omit `unitId`).

This phase is primarily an assembly task: every building block already exists. The `HouseholdManagerApiTool` is implemented and tested. The `AGENT_REGISTRY` pattern, `run_task()` tool injection, skill loading, prompt loading, LangWatch experiment pattern, and workflow step wiring are all proven across Phases 6-8. The new work is: (1) register `recipe-load` in the registry, (2) add the `elif` block in `run_task()`, (3) write the V001.md prompt, (4) extend `RecipeLoadOutput` with 3 new fields, (5) update the workflow notify step's `build_input` for richer text, (6) implement the experiment script, and (7) add `.env.example` entry.

**Primary recommendation:** Follow the exact patterns established in Phases 7-8. The recipe-load agent is simpler than recipe-research (single step, one tool, one skill) -- the main complexity is in the prompt engineering for name resolution edge cases.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Exact-first matching -- when GET /api/foods?name= or GET /api/units?name= returns multiple results, pick the one whose name matches exactly (case-insensitive). If no exact match exists, the agent uses its common sense to pick the most reasonable result from the returned list.
- **D-02:** Zero matches -- if a food name returns zero results, the ingredient is unresolvable (see D-03 for handling).
- **D-03:** Skip unresolvable ingredients -- drop them from the recipe payload and continue creating the recipe with the ingredients that resolved successfully. The recipe is always created (even if some ingredients are missing).
- **D-04:** Track skipped ingredients -- add a `missing_ingredients: list[str]` field to `RecipeLoadOutput`. Populate it with the food names that could not be resolved. This is for troubleshooting/analytics; handling will be improved in a future iteration.
- **D-05:** Richer notification -- the confirmation message includes the recipe description and a link to the recipe in the app, not just the name.
- **D-06:** Extend `RecipeLoadOutput` with additional fields beyond `recipe_id` and `recipe_name`: add `recipe_description: str | None`, `recipe_slug: str`, and `missing_ingredients: list[str]` (default empty).
- **D-07:** Update the workflow notify step's `build_input` lambda to compose richer text from the load artifact: recipe name, description, and app link (using `HOUSEHOLD_MANAGER_BASE_URL` + `/recipe/{slug}`).
- **D-08:** Reuse existing `household-manager` skill -- no dedicated `recipe-load` skill directory. The agent's `AgentConfig` will list `skills=["household-manager"]`. The agent reads `recipes_create.md` sub-file for compound create documentation, name resolution endpoints, and examples. RLOAD-02's intent (agent has instructions for resolving names and creating recipes) is satisfied by the household-manager skill's comprehensive API docs.
- **D-09:** If `unit_name` is null or returns zero matches, omit `unitId` from the ingredient payload. The API accepts ingredients without `unitId`.
- **D-10:** Live API -- experiment hits the real household-manager API (same pattern as recipe-research experiment). Requires `HOUSEHOLD_MANAGER_BASE_URL` and `HOUSEHOLD_MANAGER_API_KEY` env vars.
- **D-11:** Four edge cases to cover in experiment: (1) happy path with resolvable ingredients, (2) missing foods that return zero matches, (3) ambiguous names returning multiple matches, (4) ingredients with null `unit_name`.
- **D-12:** Register `recipe-load` in `AGENT_REGISTRY` with: `skills=["household-manager"]`, `tools=[]` (HouseholdManagerApiTool injected per-job), `prompt_path="src/robotina/agent/prompts/recipe-load/V001.md"`, model config following env-var pattern (`RECIPE_LOAD_API_TOKEN`).
- **D-13:** `run_task()` gets an `elif` block for `recipe-load` that injects `HouseholdManagerApiTool(household_id=task_input.household_id)` -- same pattern as `recipe-research-ingredients`.

### Claude's Discretion
- Unit handling specifics (when to move unresolvable unit text to the ingredient `note` field)
- Exact compound create payload construction from `RecipeData` fields
- `recipe-load/V001.md` prompt wording, tone, and structure
- Experiment evaluation criteria and output formatting
- Error handling for API failures during name resolution (rate limits, timeouts)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RLOAD-01 | `recipe-load` task type is handled by the Recipe Loader agent | Registry entry in `agents.py` (D-12), `elif` block in `run_task()` (D-13), existing `RecipeLoadInput`/`RecipeLoadOutput` models |
| RLOAD-02 | `recipe-load` skill exists with instructions for resolving food/unit names to IDs and creating the recipe | Satisfied by reusing `household-manager` skill (D-08) with `recipes_create.md` sub-file containing full compound create docs, name resolution endpoints, and examples |
| RLOAD-03 | Agent resolves human-readable ingredient names to `foodId` and `unitId` before creating the recipe | Prompt instructs agent to call `GET /api/foods?name=` and `GET /api/units?name=` per ingredient; exact-first matching (D-01); missing handling (D-02/D-03) |
| RLOAD-04 | Agent uses `household-manager-api` tool to create the recipe; returns `recipe_id` and `recipe_name` | HouseholdManagerApiTool injected per-job; compound `POST /api/recipes` with resolved IDs; extended output model (D-06) |
| RLOAD-05 | `recipe-load/V001.md` system prompt exists | New prompt file at `src/robotina/agent/prompts/recipe-load/V001.md`; follows existing prompt patterns |
| RLOAD-06 | Standalone experiment script runs agent against hardcoded inputs with LangWatch traces | `experiments/recipe_load.py` replacing stub; follows `recipe_research.py` pattern but single-step; 4 edge cases (D-11) |
</phase_requirements>

## Standard Stack

No new dependencies are required. All libraries are already installed and proven in Phases 4-8.

### Core (already installed)
| Library | Purpose | Used Since |
|---------|---------|------------|
| langchain-core | BaseTool, BaseChatModel, RunnableConfig | Phase 4 |
| langgraph | create_react_agent | Phase 4 |
| langwatch | Trace collection, experiment tracking | Phase 4 |
| pydantic v2 | Task I/O models | Phase 2 |
| httpx | HouseholdManagerApiTool HTTP calls | Phase 7 |

### No New Packages
This phase only writes new Python files and modifies existing ones. No `uv add` needed.

## Architecture Patterns

### Relevant Project Structure (existing)
```
src/robotina/
  agent/
    agents.py           # AGENT_REGISTRY -- add recipe-load entry
    workflows.py        # WORKFLOW_REGISTRY -- update notify build_input
    prompts/
      recipe-load/
        V001.md         # NEW -- system prompt
    skills/
      household-manager/
        index.md        # EXISTING -- skill bundle index
        recipes_create.md  # EXISTING -- compound create docs
    tools/
      household_manager_api.py  # EXISTING -- reuse directly
  queue/
    jobs.py             # run_task() -- add elif for recipe-load
    task_types.py       # RecipeLoadOutput -- extend with 3 new fields
experiments/
  recipe_load.py        # EXISTING stub -- replace with full implementation
tests/
  unit/
    test_agents_registry.py  # Add recipe-load registry test
    test_prompts.py          # Add recipe-load prompt existence test
```

### Pattern 1: Agent Registration (copy from Phase 8)
**What:** Add `recipe-load` entry to `AGENT_REGISTRY` dict in `agents.py`.
**Source:** `src/robotina/agent/agents.py` line 51+ (existing entries)

```python
"recipe-load": AgentConfig(
    task_type="recipe-load",
    model_config={
        "provider": "ollama",
        "url": "http://localhost:11434",
        "model": "gpt-oss:20b",
        "api_key_env": "RECIPE_LOAD_API_TOKEN",
        "reasoning": True,
    },
    prompt_path="src/robotina/agent/prompts/recipe-load/V001.md",
    skills=["household-manager"],
    tools=[],  # HouseholdManagerApiTool injected per-job in run_task()
),
```

### Pattern 2: Tool Injection in run_task() (copy from recipe-research-ingredients)
**What:** Add `elif` block in `run_task()` for `recipe-load` to inject HouseholdManagerApiTool.
**Source:** `src/robotina/queue/jobs.py` line 131-133 (existing recipe-research-ingredients block)

```python
elif task_type == "recipe-load":
    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    tools.append(HouseholdManagerApiTool(household_id=task_input.household_id))
```

### Pattern 3: RecipeLoadOutput Extension (D-06)
**What:** Add 3 new fields to `RecipeLoadOutput` in `task_types.py`.
**Constraint:** Must remain backward-compatible (new fields have defaults).

```python
class RecipeLoadOutput(BaseModel):
    recipe_id: str
    recipe_name: str
    recipe_description: str | None = None
    recipe_slug: str = ""
    missing_ingredients: list[str] = []
```

### Pattern 4: Workflow Notify Step Update (D-07)
**What:** Update the `notify` step's `build_input` lambda in `workflows.py` to compose richer text.
**Source:** `src/robotina/agent/workflows.py` line 139-142 (current simple version)

The current lambda:
```python
build_input=lambda ctx, artifacts: SendNotificationInput(
    **ctx["reply_context"],
    text=f"Recipe added: {artifacts['load']['recipe_name']}",
),
```

Must be updated to include description and app link using `HOUSEHOLD_MANAGER_BASE_URL`:
```python
import os

build_input=lambda ctx, artifacts: SendNotificationInput(
    **ctx["reply_context"],
    text=_build_notify_text(artifacts["load"]),
),
```

The helper function should read `HOUSEHOLD_MANAGER_BASE_URL` and compose:
- Recipe name
- Recipe description (if present)
- App link: `{base_url}/recipe/{slug}`
- Missing ingredients note (if any)

### Pattern 5: Experiment Script (single-step, follows send_notification pattern)
**What:** Replace `experiments/recipe_load.py` stub with full implementation.
**Key difference from recipe_research.py:** Single step (not a 4-step pipeline). Closer to `send_notification.py` in structure but hits the live API.

The experiment:
1. Builds agent using same infrastructure as `run_task()` (minus RQ)
2. Constructs `RecipeData` test inputs for 4 edge cases
3. Invokes agent with LangWatch tracing per case
4. Extracts JSON output, validates against `RecipeLoadOutput` fields
5. Reports summary

### Anti-Patterns to Avoid
- **Instantiating HouseholdManagerApiTool at module level:** Must be inside `run_task()` per locked Phase 4 constraint.
- **Creating a separate recipe-load skill directory:** D-08 explicitly says reuse `household-manager` skill.
- **Hardcoding base URL in notification text:** Must read from `HOUSEHOLD_MANAGER_BASE_URL` env var.
- **Making `recipe_slug` required without default:** Would break any existing serialized `RecipeLoadOutput` dicts in workflow artifacts.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP calls to household-manager | Raw httpx in prompt/agent | `HouseholdManagerApiTool` | Auth injection, error handling, 401/403 hard stops already implemented |
| Name resolution logic | Custom Python code | Agent + prompt instructions | The LLM handles fuzzy matching, ambiguity resolution, and decision-making naturally |
| JSON output parsing | Custom parser | `_extract_task_output()` in `workflow_runner.py` | Handles markdown fences, list content blocks, and leading prose -- proven in Phases 5-8 |
| LangWatch experiment infra | Custom tracing | `langwatch.langchain.LangChainTracer` pattern | Same pattern used in 3 existing experiments |

## Common Pitfalls

### Pitfall 1: Compound Create Atomicity
**What goes wrong:** If any `foodId` or `unitId` in the `ingredients[]` array is invalid, `POST /api/recipes` returns 400 and the entire request is rolled back -- no recipe is created.
**Why it happens:** The household-manager API validates all ingredient references atomically.
**How to avoid:** The agent MUST resolve all food/unit IDs FIRST, then call POST /api/recipes only with verified IDs. Unresolvable ingredients must be dropped from the payload (D-03), not sent with placeholder IDs.
**Warning signs:** 400 errors with "Invalid ingredient data: food or unit not found" message.

### Pitfall 2: Substring Matching Returns Too Many Results
**What goes wrong:** `GET /api/foods?name=aceite` might return "Aceite de oliva", "Aceite de girasol", "Aceite de coco". The agent picks the wrong one.
**Why it happens:** The API uses case-insensitive substring matching, not exact matching.
**How to avoid:** D-01 prescribes exact-first matching: pick the result whose name matches exactly (case-insensitive). If no exact match, agent uses judgment to pick the most reasonable result. The prompt must instruct this behavior.
**Warning signs:** Recipe ingredients have wrong food types.

### Pitfall 3: Agent Output Format Mismatch
**What goes wrong:** `_extract_task_output()` in `workflow_runner.py` expects the agent's final message to be parseable JSON. If the agent outputs prose with JSON embedded, extraction might fail.
**Why it happens:** The create_react_agent sometimes wraps responses in explanatory text.
**How to avoid:** The prompt must explicitly instruct the agent to output ONLY valid JSON as its final response, with the exact schema matching `RecipeLoadOutput`. The `_extract_task_output()` function handles markdown fences and leading prose, but clean JSON is always better.
**Warning signs:** `ValueError: Could not parse JSON from agent output` in workflow_runner logs.

### Pitfall 4: Missing HOUSEHOLD_MANAGER_BASE_URL in Notification Lambda
**What goes wrong:** The notify step `build_input` lambda reads `HOUSEHOLD_MANAGER_BASE_URL` at workflow step execution time, but if the env var is unset, the app link is wrong (falls back to localhost).
**Why it happens:** The lambda executes inside `workflow_runner.on_step_complete()`, not at workflow definition time. The env var must be set in the task runner environment.
**How to avoid:** Use `os.environ.get("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")` in the helper function. Document the env var in `.env.example`.
**Warning signs:** Notification contains `http://localhost:3001/recipe/...` in production.

### Pitfall 5: .env.example Naming Inconsistency
**What goes wrong:** `.env.example` has `HOUSEHOLD_MANAGER_API_URL` but the code uses `HOUSEHOLD_MANAGER_BASE_URL`. A developer sets the wrong one.
**Why it happens:** Historical naming mismatch -- `.env.example` was created before the tool was implemented.
**How to avoid:** The `RECIPE_LOAD_API_TOKEN` entry already exists in `.env.example`. Note: `HOUSEHOLD_MANAGER_BASE_URL` is the canonical name used in code. The `HOUSEHOLD_MANAGER_API_URL` entry in `.env.example` appears to be a legacy name that should ideally be aligned, but this is outside Phase 9 scope.
**Warning signs:** Tool falls back to localhost default unexpectedly.

### Pitfall 6: Forgetting to Update Workflow Step Count
**What goes wrong:** The `add-recipe` workflow already has 6 steps (gather, instructions, ingredients, metadata, load, notify) registered in `workflows.py`. Phase 9 does NOT add new steps -- it only modifies the existing `load` and `notify` steps. However, the `load` step already exists and points to `recipe-load` task type.
**Why it happens:** Misunderstanding that Phase 9 needs to add the `load` step. It's already there from Phase 5.
**How to avoid:** Review `workflows.py` carefully. The `load` step `build_input` already reconstructs `RecipeData` from `artifacts["metadata"]["recipe"]`. Only the `notify` step's `build_input` needs updating (D-07).

### Pitfall 7: RecipeData Field Name Mapping
**What goes wrong:** `RecipeData` uses Python snake_case field names (`servings_qty`, `prep_time`, `cook_time`, `total_time`, `source_url`) but the household-manager API uses camelCase (`servingsQty`, `prepTime`, `cookTime`, `totalTime`, `sourceUrl`). The agent must map correctly.
**Why it happens:** The agent reads `RecipeData` from the user message (snake_case) but must construct the API request body in camelCase.
**How to avoid:** The prompt should instruct the agent about the field mapping, or the `recipes_create.md` skill file already documents the API field names. The agent reads the skill before calling the API.
**Warning signs:** API returns 400 because it doesn't recognize snake_case field names.

## Code Examples

### Example 1: RecipeLoadOutput Extended Model
```python
# Source: task_types.py -- extend existing model per D-06
class RecipeLoadOutput(BaseModel):
    recipe_id: str
    recipe_name: str
    recipe_description: str | None = None
    recipe_slug: str = ""
    missing_ingredients: list[str] = []
```

### Example 2: Notify Step Helper Function
```python
# Source: workflows.py -- new helper for richer notification text (D-07)
import os

def _build_notify_text(load_artifact: dict) -> str:
    """Compose notification text from recipe-load step artifact."""
    base_url = os.environ.get("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")
    name = load_artifact.get("recipe_name", "Unknown recipe")
    description = load_artifact.get("recipe_description")
    slug = load_artifact.get("recipe_slug", "")
    missing = load_artifact.get("missing_ingredients", [])

    parts = [f"Recipe added: {name}"]
    if description:
        parts.append(description)
    if slug:
        parts.append(f"{base_url}/recipe/{slug}")
    if missing:
        parts.append(f"Missing ingredients: {', '.join(missing)}")
    return "\n".join(parts)
```

### Example 3: Experiment Test Cases (D-11)
```python
# Source: experiments/recipe_load.py -- 4 edge cases
TEST_CASES = [
    {
        "label": "Case 1: Happy path",
        "recipe": RecipeData(
            name="Tortilla Espanola",
            description="Receta clasica",
            # ... all ingredients resolvable
        ),
    },
    {
        "label": "Case 2: Missing food (zero matches)",
        "recipe": RecipeData(
            name="Test Recipe Missing",
            # ... includes ingredient with food_name that won't match
        ),
    },
    {
        "label": "Case 3: Ambiguous food name",
        "recipe": RecipeData(
            name="Test Recipe Ambiguous",
            # ... includes ingredient with food_name returning multiple matches
        ),
    },
    {
        "label": "Case 4: Null unit_name",
        "recipe": RecipeData(
            name="Test Recipe No Unit",
            # ... includes ingredient with unit_name=None
        ),
    },
]
```

### Example 4: Agent Prompt Structure (recipe-load/V001.md)
```markdown
You are an agent that loads a recipe into the household-manager system.

## Your role
Resolve human-readable ingredient names to system IDs and create the recipe.

## Available tools
- `household-manager-api`: Call the household-manager REST API
- `read-skill`: Read detailed API documentation

## Process
1. Read `household-manager/recipes_create.md` for compound create documentation
2. Read `household-manager/shared.md` for base URL and error handling
3. For each ingredient food_name: GET /api/foods?name={food_name}
   - If exactly one result with exact name match: use its id
   - If multiple results: pick the one whose name matches exactly (case-insensitive)
   - If no exact match among multiple: pick the most reasonable one
   - If zero results: skip this ingredient, track as missing
4. For each ingredient unit_name (if not null): GET /api/units?name={unit_name}
   - Same matching logic as foods
   - If null or zero results: omit unitId from ingredient
5. Build the POST /api/recipes payload with resolved IDs
6. Call POST /api/recipes with compound create

## Output
Your final response MUST be a valid JSON with this structure:
{
  "recipe_id": "...",
  "recipe_name": "...",
  "recipe_description": "...",
  "recipe_slug": "...",
  "missing_ingredients": ["food_name_1", ...]
}
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/unit/ -x -q` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RLOAD-01 | recipe-load registered in AGENT_REGISTRY | unit | `uv run pytest tests/unit/test_agents_registry.py::test_recipe_load_registered -x` | Wave 0 |
| RLOAD-02 | household-manager skill used for recipe-load (via registry config) | unit | `uv run pytest tests/unit/test_agents_registry.py::test_recipe_load_uses_household_manager_skill -x` | Wave 0 |
| RLOAD-03 | Agent resolves names (covered by experiment -- manual validation) | manual-only | Experiment: `uv run experiments.recipe_load` | N/A |
| RLOAD-04 | Agent creates recipe via API (covered by experiment -- manual validation) | manual-only | Experiment: `uv run experiments.recipe_load` | N/A |
| RLOAD-05 | recipe-load/V001.md prompt exists and is non-empty | unit | `uv run pytest tests/unit/test_prompts.py::test_prompt_file_exists_for_recipe_load -x` | Wave 0 |
| RLOAD-06 | Experiment script runs without error | smoke | `uv run experiments.recipe_load` (requires live API) | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green + experiment run completes

### Wave 0 Gaps
- [ ] `tests/unit/test_agents_registry.py::test_recipe_load_registered` -- covers RLOAD-01
- [ ] `tests/unit/test_agents_registry.py::test_recipe_load_uses_household_manager_skill` -- covers RLOAD-02
- [ ] `tests/unit/test_prompts.py::test_prompt_file_exists_for_recipe_load` -- covers RLOAD-05

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Spec originally planned a dedicated `recipe-load` skill directory | Reuse `household-manager` skill (D-08) | Phase 9 discuss | Simpler -- no new skill files needed, `recipes_create.md` already has everything |
| Spec's `RecipeLoadOutput` had only `recipe_id` + `recipe_name` | Extended with `recipe_description`, `recipe_slug`, `missing_ingredients` (D-06) | Phase 9 discuss | Richer notifications, better troubleshooting for unresolved ingredients |
| Spec's `build_input` for load step used `artifacts["research"]["recipe"]` | Actual code uses `artifacts["metadata"]["recipe"]` | Phase 8 implementation | Recipe research was split into 4 sub-steps; final RecipeData comes from metadata step |

## Open Questions

1. **Experiment test recipes may create persistent data**
   - What we know: The experiment hits the live household-manager API and creates real recipes.
   - What's unclear: Whether there's a cleanup mechanism or test household.
   - Recommendation: Use `TEST_HOUSEHOLD_ID = "experiment-household"` (matching recipe-research experiment pattern) and document that experiment creates real data. Cleanup is manual.

2. **API response shape for recipe `slug`**
   - What we know: The `POST /api/recipes` response includes a `slug` field per `recipes_get.md` and `recipes_create.md` example response.
   - What's unclear: The exact slug generation algorithm (e.g., does it handle Unicode, duplicate names).
   - Recommendation: Read `slug` directly from the API response. The agent outputs it in `RecipeLoadOutput.recipe_slug`. HIGH confidence this works.

## Sources

### Primary (HIGH confidence)
- `src/robotina/agent/agents.py` -- existing AGENT_REGISTRY pattern (6 entries)
- `src/robotina/queue/jobs.py` -- existing run_task() tool injection pattern
- `src/robotina/queue/task_types.py` -- existing RecipeLoadInput/Output models
- `src/robotina/agent/workflows.py` -- existing add-recipe workflow with load + notify steps
- `src/robotina/agent/tools/household_manager_api.py` -- HouseholdManagerApiTool implementation
- `src/robotina/agent/skills/household-manager/recipes_create.md` -- compound create API docs
- `src/robotina/agent/skills/household-manager/shared.md` -- API conventions, name filtering
- `src/robotina/agent/skills/household-manager/recipes_get.md` -- RecipeDetailResponse shape (includes slug)
- `experiments/recipe_research.py` -- 4-step experiment template
- `experiments/send_notification.py` -- single-agent experiment template
- `plans/01-kickoff/spec.md` -- original RecipeLoadInput/Output spec, agent config

### Secondary (MEDIUM confidence)
- `.planning/phases/09-recipe-load-agent-and-end-to-end-integration/09-CONTEXT.md` -- all 13 locked decisions
- `.planning/phases/08-recipe-research-agent/08-CONTEXT.md` -- Phase 8 decisions affecting data flow

## Project Constraints (from CLAUDE.md)

- **Tech Stack:** Python, LangChain, Postgres (SQLAlchemy + Alembic), Redis + RQ, uv -- no deviations
- **Concurrency:** Sequential worker (concurrency = 1)
- **LLM:** Full connection details per task type; API token from env var named by task type (RECIPE_LOAD_API_TOKEN)
- **Redis:** AOF with `appendfsync always`
- **Observability:** LangWatch instrumentation active in production and experiment runs
- **Per-job objects:** All instantiated inside run_task(), never at module level
- **Agent:** create_react_agent from langgraph.prebuilt (not AgentExecutor)
- **Pydantic:** v2 exclusively
- **Output language:** All text in Spanish (locked Phase 8)
- **Env vars:** New env vars must always be added to .env.example

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new packages, all proven in prior phases
- Architecture: HIGH -- all patterns are direct copies of existing Phase 7-8 code
- Pitfalls: HIGH -- based on reading actual API docs and existing codebase patterns

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable -- all patterns are established and locked)
