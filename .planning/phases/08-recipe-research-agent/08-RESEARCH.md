# Phase 8: recipe-research Agent - Research

**Researched:** 2026-03-30
**Domain:** Recipe research pipeline (web search, scraping, LLM extraction, workflow orchestration)
**Confidence:** HIGH

## Summary

Phase 8 implements a 4-step recipe research pipeline that replaces the single `recipe-research` task type with four sequential sub-tasks: `recipe-research-gather`, `recipe-research-instructions`, `recipe-research-ingredients`, and `recipe-research-metadata`. Each sub-task is a separate agent with its own `AgentConfig`, I/O models, and prompt. They share a single `recipe-research` skill directory with sub-files.

The implementation follows well-established patterns from Phases 6 and 7: `BaseTool` subclass with constructor injection (for `WebSearchTool`), `AgentConfig` registry entries, `elif` tool injection in `run_task()`, and skill directory with `index.md` + sub-files. The workflow registry must be updated from 3 steps to 6 steps. The combined experiment follows the `send_notification.py` pattern with LangWatch instrumentation.

Two new external dependencies are needed: `recipe-scrapers` (v15.11.0, Python package for structured recipe extraction from HTML/schema markup) and the already-installed `tavily-python` (v0.7.23, for web search). The `WebSearchTool` wraps `TavilyClient.search()` directly rather than using `langchain-tavily` (which is not installed and not needed -- the project uses `tavily-python` directly per `pyproject.toml`).

**Primary recommendation:** Build the phase incrementally: (1) I/O models + workflow update, (2) WebSearchTool, (3) 4 AgentConfig entries + skill files + prompts, (4) run_task() elif wiring, (5) experiment script. Each step has clear acceptance criteria from the prior step's output.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: The original single `recipe-research` task type is replaced by 4 sequential sub-tasks: `recipe-research-gather`, `recipe-research-instructions`, `recipe-research-ingredients`, `recipe-research-metadata`. Each is a separate task type with its own `AgentConfig` entry in `agents.py`.
- D-02: The `add-recipe` workflow in `workflows.py` is updated from 3 steps to 6 steps (`gather` -> `instructions` -> `ingredients` -> `metadata` -> `load` -> `notify`). Each step has its own `WorkflowStepDef` with a `build_input` callable.
- D-03: Each step writes output to `WorkflowRunStep.artifact`. Subsequent steps read from `accumulated_artifacts` dict. No changes to `shared_context` needed.
- D-04: 4 new Pydantic I/O model pairs are needed in `task_types.py` to replace `RecipeResearchInput/Output`. The existing `RecipeData`, `RecipeIngredient`, and `RecipeStep` shared models are reused in the final output.
- D-05: Constructs 3 Spanish search terms around the meal name. Argentina-based recipe sites are prioritized.
- D-06: Uses `web-search` tool (Tavily API) for each search term, retrieving the top 3 results per query.
- D-07: Uses the `recipe-scrapers` Python package to extract structured recipe data from search result URLs. If `recipe-scrapers` fails for a URL, falls back to LLM extraction from the Tavily-indexed content.
- D-08: If a source yields no usable data from either method, skip it and continue. The step fails only if ALL sources are unusable.
- D-09: Stores all scraped/extracted recipes in the step's artifact output.
- D-10: Reads all recipes found by the gather step from accumulated artifacts.
- D-11: Creates baseline recipe instructions using consensus approach.
- D-12: Stores the resulting instructions on the draft recipe artifact.
- D-13: Extracts all ingredients and quantities mentioned in the draft recipe instructions.
- D-14: Verifies each ingredient exists in household-manager API using `GET /api/foods?name=` with Spanish food names.
- D-15: If an ingredient doesn't exist in household-manager, checks other gathered recipe drafts for a substitute. If no substitute is found, leaves the ingredient out entirely.
- D-16: Produces a final ingredients list and adds it to the draft recipe artifact.
- D-17: Reads recipe metadata from all gathered recipes and the draft recipe instructions.
- D-18: Produces estimates for cooking time, prep time, and servings. The LLM always estimates from instructions -- fields are never null.
- D-19: Adds metadata to the draft recipe artifact. The final output conforms to the `RecipeData` model.
- D-20: All search terms are in Spanish. All output text is in Spanish.
- D-21: Ingredient verification against household-manager API uses Spanish food names directly.
- D-22: One shared `recipe-research` skill directory with `index.md` + sub-files.
- D-23: One combined experiment script at `experiments/recipe_research.py`.
- D-24: Experiment pins prompt version and model config for each sub-task via LangWatch tags/metadata.
- D-25: 4 new entries in `AGENT_REGISTRY`.
- D-26: `run_task()` gets `elif` blocks for `recipe-research-gather` (inject `WebSearchTool`) and `recipe-research-ingredients` (inject `HouseholdManagerApiTool`).
- D-27: `recipe-scrapers` added as a project dependency via `uv add recipe-scrapers`.

### Claude's Discretion
- WebSearchTool implementation details (Tavily API parameters: max_results, search_depth, include_domains)
- Exact Pydantic I/O model field names for the 4 new task types
- Prompt wording for all 4 V001.md files
- Skill sub-file content depth and formatting
- How recipe-scrapers results are structured and passed to artifact
- Experiment evaluation criteria and output formatting
- Error handling details in WebSearchTool (rate limits, API errors)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RRECIPE-01 | `recipe-research` task type is handled by the Recipe Research agent | Replaced by 4 sub-task types per D-01; each gets its own AgentConfig in agents.py following existing registry pattern |
| RRECIPE-02 | `recipe-research` skill exists with instructions for multi-site web search and structured recipe extraction | Skill directory structure at `src/robotina/agent/skills/recipe-research/` with index.md + 4 sub-files (gather.md, instructions.md, ingredients.md, metadata.md) per D-22 |
| RRECIPE-03 | `web-search` tool is implemented via the Tavily API | WebSearchTool wraps `TavilyClient.search()` (tavily-python 0.7.23 already installed); BaseTool subclass pattern from SendNotificationTool |
| RRECIPE-04 | Agent produces a `RecipeData` output with all fields populated | Final metadata step produces `RecipeData` conforming to existing model in task_types.py; fields never null per D-18 |
| RRECIPE-05 | `recipe-research/V001.md` system prompt exists | 4 prompt files needed: one per sub-task at `src/robotina/agent/prompts/<task-type>/V001.md` |
| RRECIPE-06 | A standalone experiment script runs the agent against hardcoded inputs and sends traces to LangWatch | Combined experiment at `experiments/recipe_research.py` following `send_notification.py` pattern per D-23 |
| OBS-04 | Each experiment pins prompt version and model config via LangWatch tags/metadata | Uses `langwatch.langchain.LangChainTracer(metadata={...})` pattern from send_notification experiment per D-24 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tavily-python | 0.7.23 (installed) | Web search API client | Already in pyproject.toml; `TavilyClient.search()` provides structured results with content, URLs, scores |
| recipe-scrapers | 15.11.0 (latest on PyPI) | Structured recipe extraction from URLs | 624 supported sites, extracts title/ingredients/instructions/times/yields from Schema.org markup; MIT license |
| langwatch | 0.17.0 (installed) | LLM trace collection, experiment tracking | Already wired in run_task() and send_notification experiment |
| pydantic | >=2.7 (installed) | I/O model definitions | All task types use Pydantic v2 BaseModel |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | >=0.27 (installed) | HTTP fetching for recipe-scrapers HTML input | When using `scrape_html()` with pre-fetched HTML from Tavily raw_content |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tavily-python direct | langchain-tavily (TavilySearch) | langchain-tavily is not installed and adds unnecessary abstraction; direct TavilyClient gives more control over parameters |
| recipe-scrapers | beautifulsoup4 manual parsing | recipe-scrapers handles 624 sites with Schema.org parsing; manual BS4 parsing would require per-site logic |
| scrape_html() | scrape_me(url) | scrape_me() fetches the URL itself; since Tavily already returns content, use scrape_html() with Tavily's raw_content to avoid double-fetching |

**Installation:**
```bash
uv add recipe-scrapers
```

**Version verification:**
- tavily-python: 0.7.23 (verified via `uv pip show`)
- recipe-scrapers: 15.11.0 (verified via PyPI, Dec 2025 release)
- langwatch: 0.17.0 (verified via `uv pip show`)
- langgraph: 1.1.3 (verified via `uv pip show`)

## Architecture Patterns

### Recommended Project Structure
```
src/robotina/
  agent/
    tools/
      web_search.py              # NEW: WebSearchTool (BaseTool subclass)
    skills/
      recipe-research/
        index.md                 # NEW: skill bundle index
        gather.md                # NEW: gather step instructions
        instructions.md          # NEW: instructions step instructions
        ingredients.md           # NEW: ingredients step instructions
        metadata.md              # NEW: metadata step instructions
    prompts/
      recipe-research-gather/
        V001.md                  # NEW: gather prompt
      recipe-research-instructions/
        V001.md                  # NEW: instructions prompt
      recipe-research-ingredients/
        V001.md                  # NEW: ingredients prompt
      recipe-research-metadata/
        V001.md                  # NEW: metadata prompt
    agents.py                    # MODIFIED: 4 new AgentConfig entries
    workflows.py                 # MODIFIED: 6-step add-recipe workflow
  queue/
    task_types.py                # MODIFIED: 4 new I/O model pairs, keep RecipeResearchInput/Output
    jobs.py                      # MODIFIED: 2 new elif branches
experiments/
  recipe_research.py             # MODIFIED: replace stub with combined experiment
```

### Pattern 1: WebSearchTool (BaseTool Subclass with Constructor Injection)
**What:** `WebSearchTool` wraps `TavilyClient.search()` with per-job API key injection.
**When to use:** Only for `recipe-research-gather` task type.
**Example:**
```python
# Source: Existing SendNotificationTool pattern + Tavily SDK reference
from langchain_core.tools import BaseTool
from tavily import TavilyClient
import os

class WebSearchTool(BaseTool):
    name: str = "web-search"
    description: str = (
        "Search the web for recipe information. "
        "Args: query (str) -- the search query in Spanish. "
        "max_results (int, optional) -- max results to return (default 3)."
    )

    def _run(self, query: str, max_results: int = 3) -> list[dict]:
        api_key = os.environ["TAVILY_API_KEY"]
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_raw_content="markdown",
        )
        return response.get("results", [])
```

### Pattern 2: recipe-scrapers Usage
**What:** Extract structured recipe data from HTML content using `scrape_html()`.
**When to use:** Inside the gather step prompt logic or as a tool.
**Example:**
```python
# Source: recipe-scrapers docs + PyPI README
from recipe_scrapers import scrape_html
from recipe_scrapers import NoSchemaFoundInWildMode, WebsiteNotImplementedError

def extract_recipe_from_html(html: str, url: str) -> dict | None:
    """Try to extract structured recipe data from HTML content."""
    try:
        scraper = scrape_html(html=html, org_url=url)
        return {
            "title": scraper.title(),
            "ingredients": scraper.ingredients(),       # list[str]
            "instructions": scraper.instructions(),     # str
            "instructions_list": scraper.instruction_list(),  # list[str]
            "total_time": scraper.total_time(),         # int (minutes)
            "prep_time": scraper.prep_time(),           # int (minutes) -- optional
            "cook_time": scraper.cook_time(),           # int (minutes) -- optional
            "yields": scraper.yields(),                 # str e.g. "4 servings"
            "image": scraper.image(),                   # str URL
            "host": scraper.host(),                     # str domain
        }
    except (NoSchemaFoundInWildMode, WebsiteNotImplementedError, Exception):
        return None  # fallback to LLM extraction
```

### Pattern 3: Workflow Step build_input with Artifact Accumulation
**What:** Each workflow step reads from `accumulated_artifacts` keyed by prior step_keys.
**When to use:** In `workflows.py` `build_input` lambdas.
**Example:**
```python
# Source: Existing workflows.py pattern
# artifacts dict grows: {"gather": {...}, "instructions": {...}, ...}
WorkflowStepDef(
    step_key="instructions",
    task_type="recipe-research-instructions",
    build_input=lambda ctx, artifacts: RecipeResearchInstructionsInput(
        query=ctx["recipe_query"],
        gathered_recipes=artifacts["gather"]["recipes"],
    ),
),
```

### Pattern 4: Combined Experiment Script
**What:** Run all 4 sub-tasks sequentially with LangWatch tracing per step.
**When to use:** In `experiments/recipe_research.py`.
**Example:**
```python
# Source: Existing send_notification.py experiment pattern
tracer = langwatch.langchain.LangChainTracer(
    metadata={
        "experiment": "recipe-research",
        "prompt_version": "V001",
        "run_name": run_name,
        "step": "gather",
        "model": config.model_config.get("model"),
    }
)
with tracer:
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config=RunnableConfig(callbacks=[tracer]),
    )
```

### Anti-Patterns to Avoid
- **Module-level tool instantiation:** Tools must be created inside `run_task()` per locked Phase 4 constraint. Never add tool instances to AgentConfig.tools directly.
- **Mutating shared_context:** `shared_context` is frozen at workflow creation. The 4 sub-tasks communicate via `accumulated_artifacts` only.
- **Double-fetching URLs:** Tavily's `include_raw_content` provides HTML/markdown; pass this to `scrape_html()` instead of fetching URLs separately with `scrape_me()`.
- **Mixing Pydantic v1 and v2:** All models use Pydantic v2 syntax (`list[...]`, `str | None`).
- **Using langchain-tavily:** Not installed, not needed. Use `tavily-python` `TavilyClient` directly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Recipe HTML parsing | Custom BeautifulSoup parsers per site | `recipe-scrapers` `scrape_html()` | 624 sites supported, handles Schema.org/JSON-LD/Microdata/RDFa, maintained by 219 contributors |
| Web search | Custom HTTP scraping | `tavily-python` `TavilyClient.search()` | Handles rate limiting, returns structured results with content and relevance scores |
| Workflow artifact passing | Custom shared state management | Existing `accumulated_artifacts` pattern in `workflow_runner.py` | Already implemented and tested in Phase 5; `on_step_complete` builds the dict automatically |
| LangWatch experiment tracing | Manual OTel span creation | `langwatch.langchain.LangChainTracer(metadata={...})` | Already proven in send_notification experiment; handles trace lifecycle |

**Key insight:** The entire agent infrastructure (registry, tool injection, skill loading, prompt loading, workflow advancement, experiment tracing) already exists. This phase is primarily about adding content (models, tools, skills, prompts) within the established framework.

## Common Pitfalls

### Pitfall 1: recipe-scrapers Failing Silently on Unsupported Sites
**What goes wrong:** `scrape_html()` raises `NoSchemaFoundInWildMode` or `WebsiteNotImplementedError` for sites without Schema.org markup, or returns empty/None values for optional fields.
**Why it happens:** Not all recipe sites embed structured data; Argentine recipe sites may have less Schema.org adoption than US sites.
**How to avoid:** Wrap every `scrape_html()` call in try/except. Fall back to LLM extraction from Tavily's `content` field (which is always present). Per D-08, skip sources with no usable data and only fail if ALL sources are unusable.
**Warning signs:** `None` return values from `prep_time()`, `cook_time()`, empty ingredients list.

### Pitfall 2: Tavily raw_content Not Always Available
**What goes wrong:** `include_raw_content` may return `None` for some results (paywall sites, JavaScript-rendered pages).
**Why it happens:** Tavily cannot always extract full page content.
**How to avoid:** Always check if `raw_content` is `None` before passing to `scrape_html()`. Use the `content` field (always present, usually a summary) as fallback input for LLM extraction.
**Warning signs:** `result.get("raw_content")` is `None` while `result.get("content")` has text.

### Pitfall 3: Workflow Registry build_input Type Mismatches
**What goes wrong:** `build_input` lambdas receive `accumulated_artifacts` as raw dicts (from `model_dump(mode='json')`), not Pydantic model instances. Accessing nested fields requires dict key access, not attribute access.
**Why it happens:** `on_step_complete` serializes output via `model_dump(mode='json')` to a JSON column. Deserialized artifacts are plain dicts.
**How to avoid:** Use dict key access in `build_input` lambdas: `artifacts["gather"]["recipes"]` not `artifacts["gather"].recipes`. Reconstruct Pydantic models explicitly where needed (see existing `RecipeData(**artifacts["research"]["recipe"])` pattern in current workflows.py).
**Warning signs:** `AttributeError: 'dict' object has no attribute 'recipes'` at runtime.

### Pitfall 4: Agent Output Not Matching Expected Artifact Schema
**What goes wrong:** The workflow runner stores `output.model_dump(mode='json')` or `{"result": str(output)}` depending on output type. If the agent returns a messages dict (from `create_react_agent`) instead of a typed output model, the artifact is a messages list, not the expected typed dict.
**Why it happens:** `create_react_agent` returns `{"messages": [...]}` by default. The workflow runner currently stores whatever `output` is passed to `on_step_complete`.
**How to avoid:** The agent's final response must be parsed/extracted from the messages to produce the expected output model. Either: (a) extract the structured data from the last assistant message and construct the output model in a post-processing step, or (b) have the agent return the structured output via a dedicated tool call. The planner must decide the extraction approach.
**Warning signs:** `accumulated_artifacts["gather"]` contains `{"messages": [...]}` instead of `{"recipes": [...]}`.

### Pitfall 5: Missing TAVILY_API_KEY Environment Variable
**What goes wrong:** `TavilyClient(api_key=os.environ["TAVILY_API_KEY"])` raises KeyError if not set.
**Why it happens:** New env var not documented or not set in development environment.
**How to avoid:** Follow the existing pattern: `api_key_env` in model_config for LLM tokens. For the Tavily API key, read from `TAVILY_API_KEY` (standard Tavily env var name). Document the requirement.
**Warning signs:** `KeyError: 'TAVILY_API_KEY'` on first gather step execution.

### Pitfall 6: Keeping Old RecipeResearchInput/Output vs Removing
**What goes wrong:** If old `RecipeResearchInput/Output` are removed from `task_types.py`, the existing workflow `build_input` lambda that references `RecipeResearchInput` will break until the workflow is updated.
**Why it happens:** The old 3-step workflow uses `RecipeResearchInput` in its `build_input`.
**How to avoid:** Update both `task_types.py` (add new models) and `workflows.py` (update workflow) in the same plan/wave. Keep old models until the workflow is updated, then remove.
**Warning signs:** Import errors in workflows.py after removing old models.

### Pitfall 7: recipe-scrapers prep_time/cook_time Are Optional Methods
**What goes wrong:** Calling `scraper.prep_time()` or `scraper.cook_time()` may raise `FieldNotProvidedByWebsiteException` or return `None` if the site doesn't provide that data.
**Why it happens:** These are optional methods in recipe-scrapers -- not all sites provide them.
**How to avoid:** Wrap each optional method call in a try/except and default to None. The metadata step (D-18) always estimates from instructions, so scraper values are just hints.
**Warning signs:** `FieldNotProvidedByWebsiteException` at runtime.

## Code Examples

### WebSearchTool (Full Implementation Pattern)
```python
# Source: tavily-python SDK reference + existing BaseTool patterns in project
from __future__ import annotations
import logging
import os
from langchain_core.tools import BaseTool
from tavily import TavilyClient

logger = logging.getLogger(__name__)

class WebSearchTool(BaseTool):
    name: str = "web-search"
    description: str = (
        "Search the web for recipes. Returns a list of results with "
        "title, url, content (summary), and raw_content (full page). "
        "Args: query (str) -- search query in Spanish."
    )

    def _run(self, query: str) -> list[dict]:
        api_key = os.environ["TAVILY_API_KEY"]
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            max_results=3,
            search_depth="advanced",
            include_raw_content="markdown",
        )
        results = response.get("results", [])
        logger.info("web-search | query=%r results=%d", query, len(results))
        # Return simplified results for the agent
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "raw_content": r.get("raw_content"),
                "score": r.get("score", 0),
            }
            for r in results
        ]

    async def _arun(self, query: str) -> list[dict]:
        return self._run(query)
```

### I/O Models for Sub-Tasks (Pattern)
```python
# Source: existing task_types.py patterns
# Each sub-task has its own Input/Output pair

class RecipeResearchGatherInput(BaseModel):
    query: str  # meal name, e.g. "Pasta Bolognesa"
    household_id: str
    def to_user_message(self) -> str:
        return self.query

class RecipeResearchGatherOutput(BaseModel):
    recipes: list[dict]  # list of scraped/extracted recipe dicts

class RecipeResearchInstructionsInput(BaseModel):
    query: str
    gathered_recipes: list[dict]  # from gather step artifact
    def to_user_message(self) -> str:
        return f"Create instructions for: {self.query}"

class RecipeResearchInstructionsOutput(BaseModel):
    draft_instructions: list[RecipeStep]

# ... similar for Ingredients and Metadata
```

### Workflow Registry Update (6 Steps)
```python
# Source: existing workflows.py pattern
# Old: research -> load -> notify
# New: gather -> instructions -> ingredients -> metadata -> load -> notify
"add-recipe": WorkflowDefinition(
    workflow_type="add-recipe",
    steps=[
        WorkflowStepDef(
            step_key="gather",
            task_type="recipe-research-gather",
            build_input=lambda ctx, _: RecipeResearchGatherInput(
                query=ctx["recipe_query"],
                household_id=ctx["household_id"],
            ),
        ),
        WorkflowStepDef(
            step_key="instructions",
            task_type="recipe-research-instructions",
            build_input=lambda ctx, artifacts: RecipeResearchInstructionsInput(
                query=ctx["recipe_query"],
                gathered_recipes=artifacts["gather"]["recipes"],
            ),
        ),
        # ... ingredients, metadata, load, notify
    ],
)
```

### run_task() Tool Injection
```python
# Source: existing elif pattern in jobs.py
elif task_type == "recipe-research-gather":
    from robotina.agent.tools.web_search import WebSearchTool
    tools.append(WebSearchTool())
elif task_type == "recipe-research-ingredients":
    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    tools.append(HouseholdManagerApiTool(household_id=task_input.household_id))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single recipe-research task | 4 sub-tasks (gather/instructions/ingredients/metadata) | Phase 8 (D-01) | Each step has focused prompts and cleaner I/O contracts |
| TavilySearchResults (langchain) | TavilyClient.search() (tavily-python) | Project convention | Direct SDK gives more control over parameters |
| AgentExecutor | create_react_agent (langgraph.prebuilt) | Locked per CLAUDE.md | All agents use langgraph.prebuilt.create_react_agent |

**Deprecated/outdated:**
- `langchain.agents.AgentExecutor`: Deprecated since LangChain 0.2; never use in this project (locked CLAUDE.md constraint).
- `rq-scheduler` add-on: Superseded by native RQ 2.5 scheduling.
- `scrape_me()` for this use case: Fetches URL internally; since Tavily already provides content, use `scrape_html()` to avoid double-fetching.

## Open Questions

1. **Agent output extraction from create_react_agent messages**
   - What we know: `create_react_agent` returns `{"messages": [...]}`, but `on_step_complete` needs a Pydantic model (or dict) that matches the expected artifact schema. The existing workflow stores whatever is returned.
   - What's unclear: Whether to parse the agent's last message for structured output, or to have the agent produce output via a dedicated output tool.
   - Recommendation: Post-process the agent result in `run_task()` -- extract the structured content from the last assistant message (which the prompt instructs to be JSON-formatted), deserialize it into the output model, and pass the output model to `on_step_complete`. This matches how the agent's messages dict is currently handled (the workflow runner calls `model_dump(mode='json')` on the output if it has that method).

2. **recipe-scrapers with Tavily raw_content format**
   - What we know: `scrape_html()` expects HTML; Tavily `include_raw_content="markdown"` returns markdown, not HTML.
   - What's unclear: Whether `scrape_html()` works with markdown input or needs actual HTML.
   - Recommendation: Use `include_raw_content=True` (default HTML) instead of `"markdown"`, or attempt `scrape_html()` and fall back to LLM extraction if it fails. The `scrape_html()` function parses Schema.org markup from HTML, so it needs actual HTML. If Tavily provides cleaned HTML via `include_raw_content=True`, it may strip the Schema.org tags. In that case, use `scrape_me(url)` for the actual scraping of the top result URLs (separate HTTP calls), and use Tavily's `content` field as fallback for LLM extraction. Verify at implementation time.

3. **TAVILY_API_KEY environment variable naming**
   - What we know: Tavily's standard env var is `TAVILY_API_KEY`. The project convention for LLM tokens is `{TASK_TYPE_UPPER}_API_TOKEN`.
   - What's unclear: Whether to use `TAVILY_API_KEY` (Tavily convention) or a custom name.
   - Recommendation: Use `TAVILY_API_KEY` -- it is the Tavily SDK's standard name and keeps configuration simpler. This is different from LLM tokens because it is a shared service key, not a per-task-type token.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| tavily-python | WebSearchTool | Yes | 0.7.23 | -- |
| recipe-scrapers | Gather step extraction | No | -- | Must install: `uv add recipe-scrapers` |
| langwatch | Experiment tracing | Yes | 0.17.0 | -- |
| langgraph | Agent creation | Yes | 1.1.3 | -- |
| TAVILY_API_KEY env var | WebSearchTool | Unknown | -- | Must be set by developer |
| HOUSEHOLD_MANAGER_API_KEY env var | HouseholdManagerApiTool | Unknown | -- | Already required by Phase 7 |

**Missing dependencies with no fallback:**
- `recipe-scrapers` must be installed via `uv add recipe-scrapers`
- `TAVILY_API_KEY` must be set in the environment

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/unit/ -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RRECIPE-01 | 4 AgentConfig entries registered for sub-task types | unit | `uv run pytest tests/unit/test_agents_registry.py -x -q -k recipe` | Wave 0 |
| RRECIPE-02 | recipe-research skill exists with index.md + sub-files | unit | `uv run pytest tests/unit/test_skills.py -x -q -k recipe` | Wave 0 |
| RRECIPE-03 | WebSearchTool calls Tavily API, returns structured results | unit | `uv run pytest tests/unit/test_web_search_tool.py -x -q` | Wave 0 |
| RRECIPE-04 | Final metadata output conforms to RecipeData model | unit | `uv run pytest tests/unit/test_task_types.py -x -q -k recipe` | Wave 0 |
| RRECIPE-05 | 4 prompt files exist at expected paths | unit | `uv run pytest tests/unit/test_prompts.py -x -q -k recipe` | Wave 0 |
| RRECIPE-06 | Experiment script runs without error | manual | `uv run experiments.recipe_research` | Wave 0 |
| OBS-04 | Experiment pins prompt version and model config via LangWatch tags | manual | `uv run experiments.recipe_research` (verify in LangWatch UI) | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_web_search_tool.py` -- covers RRECIPE-03 (WebSearchTool construction, _run with mocked TavilyClient)
- [ ] `tests/unit/test_task_types.py` -- add tests for 4 new I/O model pairs (RRECIPE-04)
- [ ] `tests/unit/test_agents_registry.py` -- add tests for 4 new AgentConfig entries (RRECIPE-01)
- [ ] `tests/unit/test_prompts.py` -- add tests for 4 new prompt paths (RRECIPE-05)
- [ ] `tests/unit/test_skills.py` -- add tests for recipe-research skill (RRECIPE-02)
- [ ] `tests/test_workflows.py` -- add tests for updated 6-step add-recipe workflow

## Project Constraints (from CLAUDE.md)

- **Tech Stack:** Python, LangChain, Postgres (SQLAlchemy + Alembic), Redis + RQ, uv -- no deviations
- **Concurrency:** Task runner processes jobs sequentially (concurrency = 1)
- **LLM:** Full connection details (url, model, api_token) required per task type; API tokens read from env vars named by task type
- **Agent pattern:** `create_react_agent` from `langgraph.prebuilt` required; `AgentExecutor` must NOT be used
- **Per-job objects:** All per-job objects must be instantiated inside the job function, never at module level
- **Pydantic:** v2 exclusively; never mix v1 and v2
- **Redis persistence:** AOF with `appendfsync always`
- **RQ jobs:** `result_ttl=-1` and `failure_ttl=-1` on all jobs
- **Queue name:** `agent-tasks` for all task enqueues
- **Observability:** LangWatch instrumentation active during both production and experiment runs

## Sources

### Primary (HIGH confidence)
- `src/robotina/queue/task_types.py` -- existing RecipeData, RecipeIngredient, RecipeStep models (verified by reading source)
- `src/robotina/agent/agents.py` -- AGENT_REGISTRY pattern, AgentConfig dataclass (verified by reading source)
- `src/robotina/agent/workflows.py` -- WORKFLOW_REGISTRY, WorkflowStepDef, build_input pattern (verified by reading source)
- `src/robotina/queue/jobs.py` -- run_task() tool injection pattern with elif blocks (verified by reading source)
- `src/robotina/agent/tools/send_notification.py` -- BaseTool subclass pattern with constructor injection (verified by reading source)
- `experiments/send_notification.py` -- LangWatch experiment pattern with LangChainTracer (verified by reading source)
- `src/robotina/queue/workflow_runner.py` -- on_step_complete artifact serialization, accumulated_artifacts building (verified by reading source)
- tavily-python 0.7.23 installed SDK -- `TavilyClient.search()` method signature verified via `help()`

### Secondary (MEDIUM confidence)
- [Tavily SDK Python Reference](https://docs.tavily.com/sdk/python/reference) -- search() parameters, response structure
- [recipe-scrapers PyPI](https://pypi.org/project/recipe-scrapers/) -- v15.11.0, 624 supported sites
- [recipe-scrapers docs](https://docs.recipe-scrapers.com/) -- scrape_html API, available methods (title, ingredients, instructions, etc.)
- [recipe-scrapers in-depth guide](https://docs.recipe-scrapers.com/contributing/in-depth-guide-scraper-functions/) -- full method list including optional prep_time, cook_time

### Tertiary (LOW confidence)
- recipe-scrapers exception handling details (NoSchemaFoundInWildMode, WebsiteNotImplementedError) -- inferred from GitHub source and issue tracker; exact behavior should be verified at implementation time
- `scrape_html()` compatibility with Tavily's raw_content format -- untested; should be verified at implementation time

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries either already installed or well-documented on PyPI; patterns established in prior phases
- Architecture: HIGH -- follows exact same patterns as Phases 6 and 7 (tools, agents, skills, prompts, experiments); workflow engine already proven
- Pitfalls: HIGH -- identified from reading existing codebase patterns and understanding the recipe-scrapers/Tavily API contracts
- I/O model design: MEDIUM -- exact field names are Claude's discretion; the pattern is clear but specific names need to be chosen at planning time
- recipe-scrapers + Tavily integration: MEDIUM -- both libraries are well-documented but their interplay (raw_content format, Schema.org preservation) needs verification at implementation time

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable -- all libraries are mature; recipe-scrapers and tavily-python have stable APIs)
