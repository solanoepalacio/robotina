# Phase 15: Recipe Artifact Accumulation and Food/Unit Validation - Research

**Researched:** 2026-05-14
**Domain:** LangChain 1.x agent pipeline refactor — accumulating Pydantic artifact across 5 sub-agents + 2 catalog-validation tools with structured-output LLM fallback
**Confidence:** HIGH

## Summary

Phase 15 is a structural refactor of an existing, well-instrumented pipeline. Every primitive it needs (`create_agent(response_format=...)`, ToolStrategy/ProviderStrategy selection per provider, middleware-based logging, per-job tool injection, the `_RetryingChatOllama` subclass, the `workflow_run_steps.artifact` JSON column) is already in place from Phases 10–12 and was empirically verified against the installed `langchain 1.2.13` codebase. There are no new libraries to add and no schema migrations.

The only genuinely new infrastructure is the matcher's `with_structured_output(...)` call inside the `validate-foods` / `validate-units` tools. That API surface was verified directly via `inspect.signature` against the installed `langchain-core` (signature: `with_structured_output(schema, *, include_raw=False, **kwargs) -> Runnable[..., dict|BaseModel]`) and `langchain-ollama` (Ollama-specific signature: `with_structured_output(schema, *, method='json_schema'|'function_calling'|'json_mode', include_raw=False, **kwargs)`). When `schema` is a Pydantic class and `include_raw=False`, the runnable returns a Pydantic instance and parsing/validation errors raise rather than swallow — which is exactly what we want, layered under `with_retry(stop_after_attempt=2)`.

**Primary recommendation:** Build `validate-foods` and `validate-units` as two narrow `BaseTool` subclasses backed by a shared helper module `src/robotina/agent/tools/_catalog_match.py`. Inside the helper, instantiate the matcher `LLMBackend` lazily (inside `_run`, not `__init__`) so the tool object stays pickle-friendly for RQ and the env-var read fails loudly per invocation rather than per process. Keep the agent-side artifact contract simple: every sub-agent receives the previous step's `RecipeData` snapshot in its user message and emits a fuller one via `response_format=RecipeData`, with all-Optional fields except `name` (which is required by `RecipeData` for the load step). Every prompt explicitly instructs "preserve fields you don't change; only set fields that this step is responsible for."

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Artifact shape evolution (Optional fields, accumulation contract) | Pydantic models (`task_types.py`) | — | One mutable model is the contract; tier owns the schema |
| Each sub-agent's "in: partial RecipeData, out: fuller RecipeData" loop | LangChain agent (`create_agent`) + `response_format=RecipeData` | Prompt files | `response_format` enforces shape; prompt enforces semantics |
| Catalog lookup via HTTP | Tool layer (`BaseTool._run`) → httpx async | household-manager API | Tools own external I/O, agents own reasoning |
| Programmatic NFKD direct match | Tool helper (`_catalog_match`) | — | Zero-cost path; cheaper than an LLM call |
| Semantic match fallback | `LLMBackend.model.with_structured_output(SemanticMatchResult)` inside `_catalog_match` | `AGENT_REGISTRY['validate-catalog']` for config | Reuses the same provider-swap infra production agents use |
| Per-job tool wiring | `run_task()` in `src/robotina/queue/jobs.py` | `AgentConfig.tools` | Tools needing job-scoped state are built inline; static tools live in registry |
| Workflow step ordering and `build_input` plumbing | `WORKFLOW_REGISTRY` in `workflows.py` | `workflow_runner.on_step_complete` | Registry owns shape; runner owns transitions |
| Artifact snapshot persistence | `workflow_run_steps.artifact` (JSON column) | `_extract_task_output` | Each step's row carries that step's incremental RecipeData |
| Recipe-load happy path POST + recovery | LangChain agent (still `recipe-load` in registry) | Validation tools (re-resolve on 400) | Agent is retained for error recovery loop |
| snake_case → camelCase field rename | Recipe-load prompt (V005) | — | Wire-format coupling stays at the boundary, not in shared Pydantic |

## User Constraints

> Phase 15 was discussed extensively; CONTEXT.md locks 23 decisions plus a Claude-discretion list. The constraints below are the binding subset.

### Locked Decisions (D-01..D-23 from CONTEXT.md)

- **D-01:** Single mutable `RecipeData` is the shared artifact across all 5 sub-agents. All current required fields become Optional except `name` (required when the artifact reaches recipe-load). Every sub-agent binds `response_format=RecipeData` on `create_agent`.
- **D-02:** Existing `workflow_run_steps.artifact` plumbing is unchanged. Each sub-agent's full RecipeData snapshot lands in that row.
- **D-03:** `RecipeIngredient` gains `food_id: str | None` and `unit_id: str | None`. Recipe-load reads ids only.
- **D-04:** Add `gathered_sources: list[dict] | None = None` to `RecipeData`. Gather populates it; metadata step's final emit sets it back to `None` so recipe-load's input is clean.
- **D-05:** Add `missing_ingredients: list[str] = []` to `RecipeData`. Ingredients step populates it; notification step reads it from the metadata-step artifact.
- **D-06:** Two distinct LangChain `BaseTool` classes — `validate-foods`, `validate-units` — with shared logic in `src/robotina/agent/tools/_catalog_match.py`. Args schema accepts `names: list[str]`.
- **D-07:** Each tool fetches the full catalog per call via `GET /api/foods` / `GET /api/units` (no `name=` param). Processed client-side. No cache.
- **D-08:** Direct-match rule = `unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode("ascii").casefold().strip()` on both sides, then equality.
- **D-09:** Tool return shape: `{"matched": [{"name","id"}], "unmatched": [{"name","id":null}]}`.
- **D-10:** Tool wiring reuses the same httpx + base-URL + auth setup as `HouseholdManagerApiTool`. No `household_id` injection. Registered through the same path as other tools.
- **D-11:** Matcher = `backend.model.with_structured_output(SemanticMatchResult).with_retry(stop_after_attempt=2)`. No `instructor`. Reuses `LLMBackend` + middleware so the call shows up in LangWatch.
- **D-12:** Matcher gets its own `AGENT_REGISTRY` entry — `"validate-catalog"` — with its own `model_config`, env var `VALIDATE_CATALOG_API_TOKEN`, and entries in all three `overrides/*.json`. Not a workflow task_type.
- **D-13:** Binary no-match policy. `SemanticMatchEntry = {name: str, catalog_id: str | None}`. Null = unmatched.
- **D-14:** LLM sees the full catalog inline. No rapidfuzz / difflib / embedding pre-filter.
- **D-15:** One batched LLM call per tool invocation.
- **D-16:** Recipe-load stays an agent. Happy path = rename + POST. Recovery loop on non-2xx is preserved.
- **D-17:** Recipe-load tools = `household-manager-api` + `read-skill` + `validate-foods` + `validate-units`.
- **D-18:** Field renames stay in the recipe-load prompt. No `by_alias` on Pydantic models.
- **D-19:** `RecipeLoadOutput` drops `missing_ingredients`. Notify step reads it from `artifacts["metadata"]`.
- **D-20:** No new RQ task_type for the matcher.
- **D-21:** No cross-workflow catalog cache.
- **D-22:** No catalog-write path.
- **D-23:** Workflow shape unchanged (7 steps).

### Claude's Discretion

- Prompt rewrites for all 5 sub-agents + recipe-load (wording, examples, "read these fields / populate these fields" framing). Each prompt-version bump must follow `feedback_overrides_in_sync` — atomic commit of prompt + `AGENT_REGISTRY` + every `overrides/*.json`.
- File location for `SemanticMatchEntry` / `SemanticMatchResult` (recommended: co-located in `_catalog_match.py`).
- Tool `description` strings for the two new tools (tight, ≤4 sentences, no schema duplication).
- Test surface: unit tests for `_catalog_match` (direct-match edges + fake-LLM semantic-fallback contract); integration tests for the two tools against a mocked household-manager.
- Whether to delete / alias the now-vestigial `RecipeResearch*Output` models (they all become equivalent to `RecipeData`).

### Deferred Ideas (OUT OF SCOPE)

- TTL catalog cache shared across workflow runs.
- `POST /api/foods` / `POST /api/units` agent-driven catalog onboarding.
- Embedding-based semantic match.
- Confidence threshold / candidate ranking on the matcher.
- Phase 999.1 (custom state schemas) — already in backlog.

## Phase Requirements

> Phase 15 has not yet had requirement IDs assigned in REQUIREMENTS.md. The phase introduces:
> - **RRECIPE-08** (proposed): Each recipe-research sub-agent emits a fuller `RecipeData` than it received, never the reverse.
> - **RRECIPE-09** (proposed): The ingredients step resolves `food_id` / `unit_id` for every emitted ingredient via the two validation tools; unresolved items go to `missing_ingredients` and are dropped from `ingredients[]`.
> - **RLOAD-08** (proposed): Recipe-load no longer issues `/api/foods?name=` or `/api/units?name=` on the happy path; it consumes pre-resolved ids.
> - **RLOAD-09** (proposed): On a non-2xx `POST /api/recipes`, recipe-load uses `validate-foods` / `validate-units` to re-resolve and retry.
> - **TOOLS-01** (proposed): `validate-foods` and `validate-units` return `{matched, unmatched}` and never crash on empty input or empty catalog.
>
> The plan should formalize these IDs in REQUIREMENTS.md as part of plan 15-01.

## Standard Stack

### Core (all already pinned in pyproject.toml — no changes)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langchain | `>=1.2` (installed: 1.2.13) `[VERIFIED: source grep + decisions doc]` | `langchain.agents.create_agent` agent factory + `langchain.agents.structured_output.{ProviderStrategy,ToolStrategy}` | Already wired through `LLMBackend` adapters. Phase 10 migrated, Phase 11 added `response_format`. |
| langchain-core | `>=1.2` `[VERIFIED]` | `BaseChatModel.with_structured_output(...)`, `BaseTool`, `Runnable.with_retry(...)` | Stable surface; `with_structured_output` returns a Pydantic instance when schema is a Pydantic class. |
| langchain-ollama | `>=0.2` `[VERIFIED via inspect]` | `ChatOllama.with_structured_output(method='json_schema'|'function_calling'|'json_mode')` | Ollama-specific; method selection matters for gpt-oss. |
| langchain-openai / langchain-anthropic | `>=0.2` / `>=0.3` | Provider adapters | Strict-schema native via ProviderStrategy. |
| pydantic | `>=2.7` | RecipeData, RecipeIngredient, new SemanticMatchEntry, SemanticMatchResult | Already the project standard. |
| httpx | `>=0.27` | Catalog fetch in the two new tools | Same client used by `HouseholdManagerApiTool`. |

### Supporting (already present)

| Library | Purpose |
|---------|---------|
| langwatch | Trace coverage extends to the matcher call automatically because it reuses `LLMBackend.model` + middleware. |
| sqlalchemy 2.x / alembic | No schema migration needed for Phase 15 (`workflow_run_steps.artifact` is already a JSON column). |
| pytest + pytest-asyncio | Existing test infrastructure; add new test files only. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `with_structured_output` | `instructor` library | Adds a dependency and a second structured-output code path for no functional gain. `with_structured_output` already returns Pydantic instances and integrates with `with_retry`. |
| Per-name `GET /api/foods?name=X` | Full-list fetch | Per-name requires N round trips per recipe; full-list is one. Catalogs are hundreds of items at most. `[CITED: shared.md > Filtering reference lists]` |
| Single category-parameterized tool | Two distinct tools | Per `feedback_avoid_premature_abstraction.md`, prefer concrete duplication until ≥3 instances exist. Two tools also let the agent pick exactly the one relevant at each turn. |
| Pydantic `by_alias` for camelCase | Prompt-side rename table | Rename table keeps the artifact wire-format-agnostic; `workflow_runner`, dashboard, and tests all read snake_case. |

### Installation

```bash
# No new packages. Verify pinned versions:
uv tree | rg 'langchain|pydantic|httpx'
```

**Version verification:** Pins already in pyproject.toml. `uv lock` is the source of truth. `langchain 1.2.13` / `langchain-core 1.2.22` confirmed installed (matches Phase 10/11/12 verification).

## Architecture Patterns

### System Architecture Diagram

```
Telegram message
  ↓ (gateway, Phase 3)
handle-incoming-message agent → start-workflow tool
  ↓
WORKFLOW_REGISTRY["add-recipe"].steps:
  ┌─ acknowledge ─────── acknowledge-add-recipe agent (unchanged)
  │
  ├─ gather ──────────── recipe-research-gather agent
  │                       response_format=RecipeData
  │                       emit: RecipeData(name?, gathered_sources=[...])
  │                       artifact row: full RecipeData snapshot
  │
  ├─ instructions ─────  recipe-research-instructions agent
  │                       in:  RecipeData from gather (via build_input)
  │                       response_format=RecipeData
  │                       emit: prior + (description?, steps[], maybe servings hints)
  │
  ├─ ingredients ──────  recipe-research-ingredients agent
  │                       in:  RecipeData from instructions
  │                       tools: [validate-foods, validate-units]
  │                       process:
  │                         1. extract raw {food_name, unit_name, quantity, note}[]
  │                         2. call validate-foods(names=[...])
  │                              → tool fetches full catalog
  │                              → NFKD-normalized exact match (free)
  │                              → unmatched → with_structured_output(SemanticMatchResult)
  │                              → returns {matched, unmatched}
  │                         3. call validate-units similarly
  │                         4. fold ids back, drop unmatched, append names to missing_ingredients[]
  │                       response_format=RecipeData
  │                       emit: prior + ingredients[](w/ food_id+unit_id), missing_ingredients[]
  │
  ├─ metadata ─────────  recipe-research-metadata agent
  │                       in:  RecipeData from ingredients
  │                       response_format=RecipeData
  │                       emit: prior + (servings_qty?, prep_time?, cook_time?, total_time?,
  │                                       source_url?, description?) and gathered_sources=None
  │
  ├─ load ─────────────  recipe-load agent
  │                       in:  RecipeData from metadata (with food_id/unit_id resolved)
  │                       tools: [household-manager-api, read-skill,
  │                               validate-foods, validate-units]
  │                       process:
  │                         1. apply snake_case → camelCase rename (in prompt)
  │                         2. POST /api/recipes with ingredients[](foodId/unitId)
  │                         3. on non-2xx: read error, optionally re-resolve via
  │                            validate-foods/validate-units, retry
  │                       response_format=RecipeLoadOutput  (api echo fields only)
  │
  └─ notify ───────────  send-notification (deterministic Python, no LLM)
                          input.text = _build_notify_text(metadata_artifact, load_artifact)
                          missing_ingredients comes from metadata; api echo from load
```

External services: household-manager API (`/api/foods`, `/api/units`, `/api/recipes`), Tavily, Telegram, LangWatch.

### Recommended Project Structure

```
src/robotina/
├── queue/
│   └── task_types.py          # RecipeData / RecipeIngredient: add fields, make Optional
├── agent/
│   ├── agents.py              # AGENT_REGISTRY: bump prompt_paths, add validate-catalog
│   ├── workflows.py           # WORKFLOW_REGISTRY["add-recipe"]: thread RecipeData via build_input
│   ├── tools/
│   │   ├── _catalog_match.py  # NEW: shared helper (HTTP fetch + NFKD + matcher LLM call)
│   │   ├── validate_foods.py  # NEW: BaseTool subclass
│   │   ├── validate_units.py  # NEW: BaseTool subclass
│   │   └── household_manager_api.py    # unchanged, reference pattern
│   └── prompts/
│       ├── recipe-research-gather/V005.md      # NEW (V004 → V005)
│       ├── recipe-research-instructions/V004.md  # NEW (V003 → V004)
│       ├── recipe-research-ingredients/V004.md   # NEW (V003 → V004)
│       ├── recipe-research-metadata/V004.md      # NEW (V003 → V004)
│       └── recipe-load/V005.md                 # NEW (V004 → V005)
overrides/
├── anthropic.json     # update 5 prompt_paths + add validate-catalog block
├── openai.json        # same
└── staging.ollama.json # same
.env.example           # add VALIDATE_CATALOG_API_TOKEN=
```

### Pattern 1: `with_structured_output` for the semantic-match LLM call

**What:** Bypass the agent loop for a single round-trip "given full catalog and a list of names, emit list of (name, catalog_id|null)" call. Returns a Pydantic instance directly.

**When to use:** Inside `_catalog_match` after the NFKD pass has reduced the input list to only unmatched names.

**Example:**
```python
# Source: VERIFIED via `inspect.signature(BaseChatModel.with_structured_output)`
# Returns: Runnable[LanguageModelInput, dict | BaseModel]
# When schema is a Pydantic class, returns a Pydantic instance.

from pydantic import BaseModel
from robotina.agent.agents import get_agent_config
from robotina.llm import make_backend

class SemanticMatchEntry(BaseModel):
    name: str           # original input name, echoed back so we can pair results
    catalog_id: str | None  # None = LLM judged no entry is a good fit

class SemanticMatchResult(BaseModel):
    matches: list[SemanticMatchEntry]

def semantic_match(category: str, catalog: list[dict], unmatched: list[str]) -> list[SemanticMatchEntry]:
    """One batched LLM call. `catalog` and `unmatched` go in the prompt; result is Pydantic-validated."""
    config = get_agent_config("validate-catalog")
    backend = make_backend(config.model_config)

    runnable = (
        backend.model
            .with_structured_output(SemanticMatchResult)  # Pydantic schema → Pydantic out
            .with_retry(stop_after_attempt=2)             # parse / Ollama-500 / transient HTTP
    )

    catalog_text = "\n".join(f"- {c['id']}: {c['name']}" for c in catalog)
    names_text = "\n".join(f"- {n}" for n in unmatched)
    user_message = (
        f"You are matching Spanish {category} names against the household catalog.\n"
        f"For each input name, choose the catalog id that best fits, or null if no entry is a good fit.\n\n"
        f"Catalog ({len(catalog)} entries):\n{catalog_text}\n\n"
        f"Names to match:\n{names_text}\n\n"
        f"Return a SemanticMatchResult with one entry per input name, echoing the name verbatim."
    )

    result: SemanticMatchResult = runnable.invoke(user_message)
    return result.matches
```

**Confidence:** HIGH `[VERIFIED: inspect.signature on langchain-core BaseChatModel + langchain-ollama ChatOllama]`.

### Pattern 2: NFKD normalized exact-match (D-08)

**What:** Strip accents and case to convert "Cebolla", "cebolla", "CEBOLLA" all into "cebolla". `ñ → n`. `ü → u`.

**Example (verified live in the project's Python env):**
```python
import unicodedata
def normalize(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").casefold().strip()

# Verified results (Python 3.12):
#   'Cebolla'      -> 'cebolla'
#   'Jamón'        -> 'jamon'
#   'ñoqui'        -> 'noqui'    ← ñ collapses to n (intended per D-08)
#   'güemes'       -> 'guemes'
#   'espárragos'   -> 'esparragos'
```

**Confidence:** HIGH `[VERIFIED: executed `uv run python -c ...` against installed CPython 3.12]`. The recipe handles every Spanish letter the project cares about — accented vowels, ñ, ü.

**Caveat — mojibake input:** If the catalog or agent output is double-encoded UTF-8 (e.g. `Ã±` instead of `ñ`), NFKD will produce wrong matches (`Ã±oqui → aoqui`). The household-manager response shape (`shared.md`) is documented as Spanish-native UTF-8 and the agent's output is also a Pydantic `str`, so this should not occur in practice. **Defensive:** if any test produces a mojibake mismatch, add a `.encode('latin-1').decode('utf-8')` repair step. Not in scope for Phase 15.

### Pattern 3: Per-job tool injection adapted for ingredients + load

**What:** `run_task()` in `src/robotina/queue/jobs.py` already has an `elif task_type == ...:` block per task type that constructs job-scoped tools. Phase 15 extends two existing branches.

**Today (verified at jobs.py:~138-168):**
```python
elif task_type == "recipe-research-ingredients":
    tools.append(HouseholdManagerApiTool(household_id=task_input.household_id))
elif task_type == "recipe-load":
    tools.append(HouseholdManagerApiTool(household_id=task_input.household_id))
```

**Phase 15 change:**
```python
elif task_type == "recipe-research-ingredients":
    from robotina.agent.tools.validate_foods import ValidateFoodsTool
    from robotina.agent.tools.validate_units import ValidateUnitsTool
    tools.append(ValidateFoodsTool())
    tools.append(ValidateUnitsTool())
    # NOTE: HouseholdManagerApiTool removed from this branch — ingredients
    # no longer hits the API directly (the validation tools own that I/O).
elif task_type == "recipe-load":
    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    from robotina.agent.tools.validate_foods import ValidateFoodsTool
    from robotina.agent.tools.validate_units import ValidateUnitsTool
    tools.append(HouseholdManagerApiTool(household_id=task_input.household_id))
    tools.append(ValidateFoodsTool())
    tools.append(ValidateUnitsTool())
```

**Matcher instantiation timing:** Inside `ValidateFoodsTool._run`, call `_catalog_match.semantic_match(...)` which constructs `make_backend(config.model_config)` lazily. **Do not** construct the backend in `__init__` — `BaseTool` instances are reused per agent invocation, and the env-var read should fail at first call (loud, recoverable per-job) rather than at process startup (silent, blocks the whole worker). `[VERIFIED: `LLMBackend` adapter docstrings: "All adapter instances MUST be created inside job functions (run_task), never at module level"]`.

### Pattern 4: `AGENT_REGISTRY` entry for a non-workflow LLM call site

**What:** `AGENT_REGISTRY` is keyed by `task_type` but its semantic role is "every LLM call site that needs config + prompt + override support". The `validate-catalog` entry registers the matcher without making it an RQ task.

**Example registry entry:**
```python
"validate-catalog": AgentConfig(
    task_type="validate-catalog",
    model_config={
        "provider": "ollama",
        "url": "http://localhost:11434",
        "model": "gpt-oss:20b",
        "api_key_env": "VALIDATE_CATALOG_API_TOKEN",
        "reasoning": False,  # speed > reasoning for a list-matching task
    },
    prompt_path="src/robotina/agent/prompts/validate-catalog/V001.md",  # OPTIONAL — see note
    skills=[],
    tools=[],                       # not used; this is a direct .invoke() call
    response_format_model=None,     # not used; with_structured_output is invoked manually
),
```

**Side-effect check on `run_task`:** `run_task()` looks up the registry only when an RQ job's `task_type` matches — there is no enumeration that would try to enqueue `validate-catalog`. The registry shape is keyed by `dict[str, AgentConfig]` and `get_agent_config("validate-catalog")` works for the matcher helper without any other code path noticing. **Confirmed by inspection of `jobs.py` and `workflow_runner.py`.**

**Prompt path:** Two options. (1) Define a stable V001 prompt file even though `with_structured_output` doesn't need a system prompt the same way an agent does — the helper can prepend it to the user message. (2) Use a literal string built in `_catalog_match.py`. **Recommendation:** option 1 — keeps the override system uniform and lets the matcher's wording be tuned without code changes. The `feedback_overrides_in_sync` rule then naturally applies.

### Pattern 5: Workflow `build_input` threading the accumulating artifact

**Today (verified at workflows.py:~119-160):** Each step's `build_input` reads disjoint fields out of prior artifacts and constructs a step-specific `*Input` model.

**Phase 15 change:** Each step's `build_input` reconstructs a `RecipeData` from `artifacts[<prev_key>]` and packs it into the step's `*Input`.

```python
# instructions step build_input — Phase 15 shape
build_input=lambda ctx, artifacts: RecipeResearchInstructionsInput(
    query=ctx["recipe_query"],
    recipe=RecipeData(**artifacts["gather"]),   # was: gathered_recipes=_recipes(artifacts["gather"])
)
```

The 5 `RecipeResearch*Input` models stay (workflow_runner needs them for `build_input`), but their internal shape simplifies to `{query, recipe: RecipeData, household_id?}`. `to_user_message` serializes the partial RecipeData to JSON for the user message — the agent reads it from there. `[CITED: workflows.py docstring "build_input callables receive shared_context + accumulated_artifacts"]`.

### Pattern 6: `response_format=RecipeData` with deeply Optional fields

**What:** ProviderStrategy (Anthropic/OpenAI) and ToolStrategy (Ollama) both accept Pydantic models with arbitrary nesting and `Optional` fields. Pydantic v2 generates JSON Schema with `"type": ["string","null"]` (or `anyOf`) for `str | None`, which both strict-mode providers and the ToolStrategy emit-tool path accept. `[CITED: response-format-adoption.md + Phase 11 RESEARCH.md]`.

**Risk — model omits or fabricates fields:** With `RecipeData` becoming `name: str` + everything-else Optional, the LLM must understand "preserve fields you don't change". Two failure modes to guard in prompts:
1. **Overwriting with `None`:** The model decides a field "doesn't apply to this step" and emits `null`, blowing away upstream work.
2. **Hallucinating values:** The model invents `cook_time` from thin air just because the schema offers the slot.

**Prompt-engineering implication:** Every sub-agent prompt must include an explicit rule like:
> "You are given a partial RecipeData. For every field already populated in the input, emit the same value unchanged unless this step is explicitly responsible for it. For fields this step is not responsible for, emit `null` only if the input already has `null`."

This is the single largest source of execution risk in Phase 15. Confirmed by reasoning about how Pydantic-strict-mode behaves: strict mode constrains the *shape*, not the *semantics* — it cannot tell "this field was set by an upstream agent" from "this field is unset and I should leave it alone".

**OpenAI strict mode + `list[dict]` caveat:** `RecipeData.gathered_sources: list[dict] | None` has the same shape concern as Phase 11's `recipes: list[dict]` issue (Pitfall 2 in 11-RESEARCH.md) — OpenAI strict mode rejects `additionalProperties: true`. Since `gathered_sources` is intended to be `None` everywhere except gather → instructions → ingredients → metadata (and even there only as opaque scratch data), it's fine on the Anthropic/Ollama path. **If OpenAI is ever activated:** type it more precisely (`list[GatheredSource]` with named fields) or accept that the OpenAI override will 400. Document in the prompt. Phase 15 does not need to solve this — the production path is Ollama.

### Anti-Patterns to Avoid

- **Building `make_backend("validate-catalog")` at module import time** — fails the locked Phase 4 constraint that adapters are job-scoped. Build inside `_run`.
- **Letting the matcher prompt mention the agent's name/task** — it's a generic catalog matcher; coupling it to recipe-research wording makes it harder to reuse if a second category ever needs matching.
- **Passing `force_tool=True` or similar tool-call-forcing kwargs to `create_agent` on the ingredients agent to "make sure validate-foods is called"** — defeats the agent loop. Trust the prompt and the Pydantic schema.
- **Mixing `response_format` and `with_structured_output` in the same call** — they target different surfaces. The matcher uses `with_structured_output` on `backend.model` directly; the agents use `response_format` on `create_agent`. No interaction.
- **Sharing one `BaseTool` instance across jobs** — Phase 4 constraint. Construct fresh per job, even if the tool has no per-job state (consistency).
- **Recipe-load fetching `/api/foods?name=` on the happy path** — D-03 + D-17 explicitly remove this. The artifact arrives with ids resolved. Only the recovery branch invokes validation tools.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pydantic-validated LLM output | Custom JSON-mode parsing + retry loop | `BaseChatModel.with_structured_output(Schema)` + `.with_retry(stop_after_attempt=2)` | Built-in: handles provider-native strict mode, tool-call validation on Ollama, retries on parse failure. Returns a Pydantic instance. |
| Accent-insensitive string match | Custom Unicode table | `unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode("ascii")` | Stdlib; verified to handle every accent the project sees. |
| HTTP catalog fetch with bearer auth | New httpx wrapper | Copy `HouseholdManagerApiTool`'s pattern, drop the args_schema flexibility (validate-foods takes only `names`). | One reference impl already used by every other tool. |
| LangChain provider routing for the matcher | New provider switch | `make_backend(config.model_config)` reads provider from registry; `with_structured_output` works on `backend.model` regardless of provider. | Reuse Phase 11/12 infrastructure. |
| Cataloging "unmatched" items into the artifact | Custom output schema | `missing_ingredients: list[str]` on `RecipeData` (D-05) | One place to put unmatched names. Notify reads it. |
| LangWatch instrumentation for the matcher call | New tracing hook | Reuse the existing middleware on `LLMBackend.create_agent` — but **note:** `with_structured_output` on `backend.model` does **not** go through `create_agent`, so middleware does **not** automatically apply to it. See Pitfall 5 below. |

**Key insight:** Phase 15 is almost entirely composition. The biggest "do not hand-roll" is: do not build a parallel structured-output path. The library returns Pydantic instances on success and raises on parse failure — that's the entire contract.

## Runtime State Inventory

> Phase 15 is a code-and-config refactor. There is no rename, no string-replacement, no migration. This section is included for completeness; nothing in any category requires a parallel data action.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `workflow_run_steps.artifact` is a JSON column that already accepts the new RecipeData shape per row. No data migration needed; old failed runs keep their historical shape. | none |
| Live service config | None — household-manager API contract is unchanged. Telegram, LangWatch, Tavily configs untouched. | none |
| OS-registered state | None. RQ queue/worker definitions unchanged. | none |
| Secrets / env vars | NEW env var `VALIDATE_CATALOG_API_TOKEN` must be added to `.env.example` and any deployed `.env` files. Code change reads it via `os.environ[config["api_key_env"]]` per existing pattern — no special handling. | add to `.env.example`; document in deploy docs |
| Build artifacts | None. `uv build` regenerates from `pyproject.toml`; no version-pinned external resources. | none |

**Nothing found in 4 of 5 categories:** verified by reading `workflow_runner.py`, `jobs.py`, household-manager skill files, and the existing `.env.example`.

## Common Pitfalls

### Pitfall 1: Sub-agent "forgets" upstream fields on emit

**What goes wrong:** With `response_format=RecipeData` and all-Optional fields, the LLM emits a structurally valid `RecipeData` that drops fields populated by prior steps (e.g. the metadata step emits `ingredients=None` because the prompt focuses on metadata).

**Why it happens:** `response_format` enforces shape, not semantics. The model has no notion of "preserve unless changed" unless the prompt insists.

**How to avoid:**
- Every sub-agent's prompt includes a "Field preservation rule" section: *"You receive a partial RecipeData in the user message. Emit a copy in which the only changed fields are the ones your step owns. For every other field, emit the same value you received (including `null` if the input had `null`)."*
- The instructions step owns `description`, `steps[]`. The ingredients step owns `ingredients[]`, `missing_ingredients`. The metadata step owns `servings_qty`, `servings_unit`, `prep_time`, `cook_time`, `total_time`, `source_url` and clears `gathered_sources`. Document these ownership tables inside each prompt.
- Add a regression test: build a fully populated RecipeData, run it through one sub-agent with a mocked LLM that returns the same fields, verify nothing dropped. Then run with the real model on a known recipe and diff input vs output: only the owned fields should differ.

**Warning signs:** A workflow run where step 3 has fewer populated RecipeData fields than step 2. The dashboard makes this visible because each step's artifact is a full snapshot.

### Pitfall 2: Matcher LLM call doesn't show in LangWatch

**What goes wrong:** The matcher uses `backend.model.with_structured_output(...)`, not `backend.create_agent(...)`, so the Phase 12 middleware (`log_around_model_call`, `log_after_model`, `log_wrap_tool_call`) — which is bound to `create_agent` — does not run for the matcher call.

**Why it happens:** Middleware is a `create_agent` concern. `with_structured_output` wraps the chat model in a Runnable, not a graph; middleware doesn't intercept Runnable.invoke.

**How to avoid:**
- LangWatch's OTel integration hooks into LangChain at the callback bus level via `LangChainTracer`. As long as the matcher invoke is wrapped in `langwatch.trace()` (same context manager the agent uses) and the runnable is invoked with `config=RunnableConfig(callbacks=[langwatch.langchain.LangChainTracer()])`, the LLM call still emits a span. `[CITED: jobs.py:~176-184 — the existing pattern]`.
- Verify in the plan that `_catalog_match.semantic_match` accepts an optional `RunnableConfig` and threads the LangChain tracer through. The cleanest implementation: when called from inside an active `langwatch.trace()` context (which the agent's `agent.invoke` already opens), get the current tracer from `langwatch.get_current_trace()` and attach.
- Alternative: rely on LangWatch's OTel auto-instrumentation if enabled — but this is LOW confidence (LangWatch SDK confidence is LOW per project memory). Plan should include a manual smoke check that the matcher call appears as a child span in the LangWatch UI.

**Warning signs:** The ingredients-step LangWatch trace shows tool calls to `validate-foods` and `validate-units` but no nested LLM call beneath them. That means the matcher invocation is invisible.

### Pitfall 3: Ollama `with_structured_output(method='json_schema')` returns malformed output on gpt-oss

**What goes wrong:** Ollama `ChatOllama.with_structured_output` defaults to `method='json_schema'` (`[VERIFIED: source inspection]`). Some gpt-oss variants are known to emit prose alongside the structured output (the same class of bug Phase 11 fixed with ToolStrategy on the agent path).

**Why it happens:** `json_schema` method uses Ollama's structured-output API; gpt-oss has documented issues with that path for complex schemas.

**How to avoid:**
- For the matcher, explicitly pass `method='function_calling'` (which uses Ollama tool-calling) when the backend is Ollama. The matcher's schema (`SemanticMatchResult.matches: list[SemanticMatchEntry]`) is simple enough that either method works in principle, but the tool-calling path has been load-tested by Phase 11.
- A clean way to do this without leaking provider info to the helper: detect at call time —
  ```python
  from langchain_ollama import ChatOllama
  kwargs = {}
  if isinstance(backend.model, ChatOllama):
      kwargs["method"] = "function_calling"
  runnable = backend.model.with_structured_output(SemanticMatchResult, **kwargs).with_retry(stop_after_attempt=2)
  ```
- Already wrapped in `_RetryingChatOllama` which retries 5xx ("error parsing tool call") at the lower layer. `with_retry(stop_after_attempt=2)` retries parse errors at the higher layer. Together: 3 × 2 = up to 6 attempts on a transient Ollama hiccup.

**Warning signs:** `ValidationError` raised from inside `_catalog_match` on the first matcher call. The traceback will reference `SemanticMatchResult`.

### Pitfall 4: Catalog payload exceeds Ollama gpt-oss context window when piped through the agent's user message

**What goes wrong:** The catalog itself is small (hundreds of items, ~10KB serialized). But if the ingredients agent's prompt includes the full catalog text AND the matcher's prompt also includes it, and the agent has 4-5 prior turns in its message history, the gpt-oss 20b context can come under pressure.

**Why it happens:** The matcher is a separate LLM call inside the tool — the agent never sees the catalog. So this only fires if the prompt mistakenly inlines the catalog into the agent's system prompt or user message.

**How to avoid:**
- The catalog is **only** visible inside `_catalog_match.semantic_match`. The agent's view of the matching action is: call `validate-foods(names=[...])` → receive `{matched, unmatched}`. The catalog never enters the agent's context.
- Document this explicitly in the `validate-foods` / `validate-units` tool descriptions: "Returns `{matched, unmatched}`. Do not call this tool with the catalog as input — the tool fetches the catalog internally."
- For the matcher's own prompt: catalog text is ~150 items × ~50 chars = ~7.5KB. With unmatched-list (typically 0-3 items) + system instructions, comfortably within gpt-oss 20b's 8k+ context.

**Warning signs:** Ollama 500 on the matcher invocation with a context-length error in the body. Look for "context length exceeded" in the message.

### Pitfall 5: Recipe-load's recovery loop double-resolves

**What goes wrong:** Recipe-load receives an artifact with `food_id`/`unit_id` already resolved. It POSTs, gets a 400 ("food not found"), then re-resolves via `validate-foods`. The agent may then **also** drop and re-add an ingredient that was actually fine, or call `validate-foods` for every ingredient instead of just the rejected one.

**Why it happens:** The error body from household-manager (`shared.md`) is a generic 400 with a message string. The recipe-load prompt has to be explicit about "only re-resolve the food/unit named in the error".

**How to avoid:**
- The recipe-load V005 prompt's recovery section explicitly lists the steps: parse the error body for the `foodId` or `unitId` mentioned → look up the original `food_name` / `unit_name` from the input ingredient with that id → call `validate-foods(names=[that_name])` → swap in the new id → retry POST.
- If the error body doesn't name a specific id, the prompt should fail to recovery-by-calling-everyone and instead surface the failure (mark all currently-unresolved items as `missing_ingredients` and continue with the rest).

**Warning signs:** Recipe-load takes 4+ turns to succeed on a recipe that should be a one-shot. LangWatch traces show repeat `validate-foods` calls with overlapping inputs.

### Pitfall 6: Mixing snake_case Pydantic field names with camelCase API body when the LLM rewrites the dict

**What goes wrong:** Recipe-load receives `RecipeData` (snake_case Python). The prompt instructs it to rewrite to camelCase for the API. The LLM sometimes leaves keys snake_case in the POST body, or applies the rename inconsistently.

**Why it happens:** Without an explicit table, the LLM substitutes ad-hoc.

**How to avoid:**
- Keep the V004 rename table verbatim in V005 (already correct in the current prompt: `servings_qty → servingsQty`, etc.).
- For ingredient items: input has `food_id` / `unit_id` (Phase 15 new fields). API expects `foodId` / `unitId`. Add to the table:
  ```
  | food_id        | foodId         |
  | unit_id        | unitId         |
  ```
- API also expects: `quantity` (unchanged), `note` (unchanged). `food_name` and `unit_name` are NOT sent (the API doesn't accept them on `POST /api/recipes`).

**Warning signs:** 400 from household-manager with a body like `"foodId must be a string"` — the model sent `food_id`.

## Code Examples

### Example 1: ValidateFoodsTool skeleton

```python
# Source: pattern derived from src/robotina/agent/tools/household_manager_api.py
#         and src/robotina/agent/tools/_catalog_match.py (new in Phase 15)

from __future__ import annotations
import os, asyncio
import httpx
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from robotina.agent.tools._catalog_match import resolve_catalog


class ValidateFoodsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    names: list[str] = Field(description="Spanish food names to resolve, e.g. ['cebolla', 'tomate perita'].")


class ValidateFoodsTool(BaseTool):
    name: str = "validate-foods"
    description: str = (
        "Resolve a list of Spanish food names against the household-manager food catalog. "
        "Returns {matched: [{name, id}], unmatched: [{name, id: null}]}. "
        "Drop unmatched items from your ingredients list and add their names to missing_ingredients[]."
    )
    args_schema: type[BaseModel] = ValidateFoodsArgs

    def _run(self, names: list[str]) -> dict:
        api_key = os.environ["HOUSEHOLD_MANAGER_API_KEY"]
        base_url = os.environ.get("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")

        async def fetch() -> list[dict]:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{base_url}/api/foods",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                return resp.json()

        catalog = asyncio.run(fetch())
        return resolve_catalog(category="food", catalog=catalog, names=names)

    async def _arun(self, names: list[str]) -> dict:
        return self._run(names)
```

### Example 2: `_catalog_match.resolve_catalog`

```python
# Source: Phase 15 new module

from __future__ import annotations
import unicodedata
from pydantic import BaseModel
from langchain_ollama import ChatOllama


def _normalize(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").casefold().strip()


class SemanticMatchEntry(BaseModel):
    name: str
    catalog_id: str | None


class SemanticMatchResult(BaseModel):
    matches: list[SemanticMatchEntry]


def resolve_catalog(category: str, catalog: list[dict], names: list[str]) -> dict:
    """Return {matched, unmatched} for `names` against `catalog`.

    catalog item shape: {"id": str, "name": str, ...}
    """
    if not names:
        return {"matched": [], "unmatched": []}

    # Build index for O(N) match
    norm_to_entry = {_normalize(c["name"]): c for c in catalog}

    matched: list[dict] = []
    remaining: list[str] = []
    for n in names:
        hit = norm_to_entry.get(_normalize(n))
        if hit:
            matched.append({"name": n, "id": hit["id"]})
        else:
            remaining.append(n)

    if not remaining:
        return {"matched": matched, "unmatched": []}

    # Semantic fallback (one batched LLM call)
    from robotina.agent.agents import get_agent_config
    from robotina.llm import make_backend

    config = get_agent_config("validate-catalog")
    backend = make_backend(config.model_config)
    kwargs = {}
    if isinstance(backend.model, ChatOllama):
        kwargs["method"] = "function_calling"  # Pitfall 3
    runnable = (
        backend.model
            .with_structured_output(SemanticMatchResult, **kwargs)
            .with_retry(stop_after_attempt=2)
    )

    catalog_text = "\n".join(f"- {c['id']}: {c['name']}" for c in catalog)
    names_text = "\n".join(f"- {n}" for n in remaining)
    user_message = (
        f"You match Spanish {category} names against a household catalog.\n"
        f"For each input name choose the catalog id that best fits, or null if no entry is a good fit.\n\n"
        f"Catalog:\n{catalog_text}\n\n"
        f"Names to match:\n{names_text}\n\n"
        f"Return SemanticMatchResult with one entry per input name, echoing each name verbatim."
    )

    result: SemanticMatchResult = runnable.invoke(user_message)

    unmatched: list[dict] = []
    for entry in result.matches:
        if entry.catalog_id:
            matched.append({"name": entry.name, "id": entry.catalog_id})
        else:
            unmatched.append({"name": entry.name, "id": None})

    return {"matched": matched, "unmatched": unmatched}
```

### Example 3: New `RecipeData` shape

```python
# src/robotina/queue/task_types.py — Phase 15 edits

class RecipeIngredient(BaseModel):
    food_name: str | None = None        # was: required; now optional for partial artifacts
    food_id: str | None = None          # NEW (D-03)
    unit_name: str | None = None
    unit_id: str | None = None          # NEW (D-03)
    quantity: float | None = None
    note: str | None = None


class RecipeData(BaseModel):
    name: str                                    # ONLY required field (per D-01 contract at recipe-load entry)
    description: str | None = None
    servings_qty: int | None = None
    servings_unit: str | None = None
    prep_time: int | None = None
    cook_time: int | None = None
    total_time: int | None = None
    source_url: str | None = None
    ingredients: list[RecipeIngredient] = []     # was: required list; now optional/empty
    steps: list[RecipeStep] = []                 # same
    gathered_sources: list[dict] | None = None   # NEW (D-04)
    missing_ingredients: list[str] = []          # NEW (D-05)
```

**Note on `name`:** D-01 says `name` is required only "when the artifact reaches recipe-load". The gather step may legitimately emit RecipeData before the recipe name has been canonicalized. **Two implementation options:**
1. Make `name` required on `RecipeData` and have the gather step populate it from the user's query verbatim (then instructions/metadata may refine it). Simpler; recommended.
2. Make `name: str | None = None` on `RecipeData` and validate at recipe-load entry. More flexible but adds a custom validator.

Recommend option 1 — `gather` always populates `name` from `shared_context.recipe_query` if it can't extract a better one from web results.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Disjoint per-step output schemas (5 different `*Output` models) | Single accumulating `RecipeData` artifact, all sub-agents bind `response_format=RecipeData` | Phase 15 (this phase) | Each step's DB row is now a meaningful snapshot of the recipe in progress. Dashboard "diff between steps" becomes trivial. |
| Recipe-load fetches `/api/foods?name=` and `/api/units?name=` per ingredient | Recipe-load receives pre-resolved ids; validation tools own catalog lookups | Phase 15 | Removes 2N+1 HTTP calls per recipe; localizes the matching complexity to the ingredients step. |
| Per-name catalog filter API (`?name=substring`) | Full-list fetch + client-side NFKD normalize | Phase 15 | One HTTP call instead of N. The substring filter (`shared.md`) is still a valid fallback in recipe-load's recovery path. |
| Free-text JSON output + parse ladder | `create_agent(response_format=...)` token-level enforcement (Phase 11) | Phase 11 (already shipped) | Carries unchanged into Phase 15. |
| Callbacks-based agent instrumentation | Middleware-based (Phase 12) | Phase 12 (already shipped) | Carries unchanged. **But:** middleware does NOT cover `with_structured_output` calls — see Pitfall 2. |

**Deprecated / outdated for Phase 15:**
- `RecipeData uses human-readable food/unit names (not IDs)` (PROJECT.md Key Decisions) — Phase 15 amends this. The artifact now carries both names AND ids on each ingredient.
- The recipe-load V004 prompt's "for every distinct `food_name`, call GET /api/foods?name=..." procedure — no longer the happy path. V005 keeps the procedure only inside the recovery branch.
- `RecipeResearchGatherOutput`, `RecipeResearchInstructionsOutput`, `RecipeResearchIngredientsOutput`, `RecipeResearchMetadataOutput` — all become equivalent in shape to `RecipeData`. Claude's discretion to alias, rename, or delete.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `GET /api/foods` (no `name=` param) returns a plain JSON array of `[{id, name, ...}, ...]` shape | Pattern 2 / Example 1 | `[VERIFIED via shared.md > Filtering reference lists; CITED]` — but if there's a paginated envelope `{items, total, ...}` for foods/units like other endpoints, code needs adjustment. Manual smoke recommended in plan 15-XX. |
| A2 | `GET /api/units` returns the same shape with an additional `abbreviation` field | Pattern 2 | `[CITED: shared.md example response]`. Same caveat as A1. |
| A3 | gpt-oss `with_structured_output(method='function_calling')` works for the `SemanticMatchResult` schema | Pitfall 3 | LOW. Function-calling on gpt-oss has been load-tested in Phase 11 (ToolStrategy on agents), which uses the same Ollama tool-call channel. But `with_structured_output` doesn't go through `create_agent`. **Recommend a spike: run a 10-line script against staging Ollama with `make_backend({"provider":"ollama",...}).model.with_structured_output(SemanticMatchResult, method='function_calling').invoke(...)` before committing the implementation.** |
| A4 | LangWatch traces capture `with_structured_output` invocations when `RunnableConfig(callbacks=[LangChainTracer()])` is passed | Pitfall 2 | LOW. LangWatch SDK confidence is LOW per project memory ([[project_robotina]]). Plan should include a manual LangWatch-UI verification step. |
| A5 | The household-manager API never returns a 401/403 for `GET /api/foods` or `GET /api/units` with a valid bearer token | Example 1 | HIGH. Verified by the existing `HouseholdManagerApiTool` pattern; the auth layer is unchanged. |
| A6 | Catalog size stays in the "hundreds of items" range — well within gpt-oss 20b's context | Pitfall 4 | MEDIUM. No size sampling done in this research. If a household scales to ~5k catalog items, the matcher prompt would need rethinking (deferred per D-14). |
| A7 | Adding a non-task-type entry to `AGENT_REGISTRY` does not break any iteration or enumeration | Pattern 4 | HIGH. Grep of `jobs.py` and `workflow_runner.py` shows registry access is always keyed lookup, never iteration. |
| A8 | The `to_user_message` for each sub-agent can serialize the partial `RecipeData` as JSON without hitting any non-serializable types | Pattern 5 | HIGH. RecipeData and all its fields are JSON-friendly Pydantic v2. |
| A9 | `_RetryingChatOllama`'s 5xx retry composes correctly under `Runnable.with_retry(stop_after_attempt=2)` — the inner retry handles transport-level failures, the outer retry handles parse-level failures | Pitfall 3 | MEDIUM. Reasoning sound (inner is `_generate` override, outer is Runnable composition) but not load-tested in this combination. Plan should include a fault-injection test where the matcher LLM emits malformed output once, then valid output on retry. |

## Open Questions (RESOLVED)

1. **Should the matcher have its own prompt file or an inline string?**
   - What we know: D-12 puts it in `AGENT_REGISTRY` with `prompt_path`. The override system expects a path.
   - What's unclear: `with_structured_output` doesn't take a system prompt as cleanly as `create_agent` does. The system message can be prepended to the user message before `.invoke(...)`, or passed as a list of messages.
   - RESOLVED: Recommendation: V001 prompt file under `src/robotina/agent/prompts/validate-catalog/`. The helper builds `[{"role":"system","content":<file>}, {"role":"user","content":<formatted>}]` and invokes the runnable with that list. Keeps the override pattern uniform.

2. **What happens when the matcher returns an entry for a name not in the input list (hallucinated name)?**
   - What we know: D-13 wants binary results. The Pydantic model enforces shape only.
   - What's unclear: If the LLM "improves" a name (e.g. user said "Cebolla colorada", LLM echoes "Cebolla") the pairing breaks.
   - RESOLVED: Recommendation: in `resolve_catalog`, post-process: drop any returned entry whose `name` isn't in `remaining` (case-sensitive exact match). Document this as a defensive filter in the test plan.

3. **Should `gathered_sources` be typed more strictly?**
   - What we know: D-04 says `list[dict] | None`. Loose.
   - What's unclear: With strict-mode OpenAI, `list[dict]` triggers `additionalProperties: true` rejection (Phase 11 Pitfall 2).
   - RESOLVED: Recommendation: keep `list[dict] | None` for the Ollama production path. If OpenAI override is ever activated, type as `list[GatheredSource]` where `GatheredSource` has the gather agent's emit fields explicitly listed. Document in Phase 15 verification notes — not a blocker for Ollama-first execution.

4. **`name` required vs Optional at `RecipeData`?**
   - RESOLVED: Recommendation (Code Examples Note): keep `name: str` required at the model level; gather populates it verbatim from the user query if it can't get a better one. Strictly enforces D-01's "name required when reaching recipe-load" without a custom validator.

5. **Should the gather step's emit include `name` populated, or can the instructions step refine it?**
   - RESOLVED: Recommendation: both. Gather emits `name = query`. Instructions may emit a better-formatted `name`. Field preservation rule (Pitfall 1) allows it.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All code | ✓ | 3.12.x | — |
| uv | Build / install | ✓ | (locked) | — |
| langchain | agents, tools, structured output | ✓ | 1.2.13 | — |
| langchain-core | BaseChatModel, BaseTool, Runnable.with_retry | ✓ | 1.2.22 | — |
| langchain-ollama | ChatOllama.with_structured_output | ✓ | (pinned) | — |
| langchain-anthropic / langchain-openai | Provider adapters | ✓ | (pinned) | — |
| httpx | catalog fetch | ✓ | (pinned) | — |
| pydantic | all models | ✓ | 2.x | — |
| Ollama (local) | dev path for matcher | depends on dev box | gpt-oss:20b | Use staging.ollama.json override to point at the shared dev Ollama at `192.168.68.109:11434` |
| household-manager API | catalog endpoints | depends on dev/staging | n/a | None — required at runtime; tests mock via httpx-mock |
| LangWatch | trace verification | depends on env vars | n/a | Tests can run without; verification step requires a real LANGWATCH_API_KEY |

**Missing dependencies with no fallback:** None for code execution. LangWatch is the only one whose absence affects verification, not function.

**Missing dependencies with fallback:** All catalog HTTP calls are mockable in tests via `httpx-mock` or a small `monkeypatch` of `httpx.AsyncClient.get`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio (already in pyproject.toml) `[VERIFIED]` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_catalog_match.py tests/test_validate_foods.py tests/test_validate_units.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID (proposed) | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RRECIPE-08 | Each sub-agent emits fuller RecipeData than received | unit + integration | `uv run pytest tests/test_workflows.py::test_artifact_grows_monotonically -x` | ❌ Wave 0 |
| RRECIPE-09 | Ingredients step resolves food_id/unit_id and surfaces missing | unit + integration | `uv run pytest tests/test_validate_foods.py::test_ingredient_resolution_happy_path -x` | ❌ Wave 0 |
| RLOAD-08 | Recipe-load no longer hits `/api/foods?name=` on happy path | integration (record API calls) | `uv run pytest tests/test_recipe_load.py::test_happy_path_no_catalog_fetch -x` | ❌ Wave 0 |
| RLOAD-09 | Recipe-load recovers via validate-foods on 400 | integration | `uv run pytest tests/test_recipe_load.py::test_recovery_on_400_food_not_found -x` | ❌ Wave 0 |
| TOOLS-01 | Validation tools handle empty input / empty catalog without crash | unit | `uv run pytest tests/test_catalog_match.py::test_empty_inputs -x` | ❌ Wave 0 |
| NFKD-01 | Normalization handles all relevant Spanish accents | unit | `uv run pytest tests/test_catalog_match.py::test_nfkd_spanish -x` | ❌ Wave 0 |
| SEMANTIC-01 | Matcher uses one LLM call regardless of unmatched-count | unit (with fake LLM, count invocations) | `uv run pytest tests/test_catalog_match.py::test_single_batched_call -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_catalog_match.py tests/test_validate_foods.py tests/test_validate_units.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green + manual end-to-end "add recipe for X" against staging.ollama before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_catalog_match.py` — NFKD edges, single-batched-call, empty inputs, hallucinated-name filter
- [ ] `tests/test_validate_foods.py` — happy path, all-matched, all-unmatched, partial, HTTP error
- [ ] `tests/test_validate_units.py` — same shape as foods
- [ ] `tests/test_recipe_load.py::test_happy_path_no_catalog_fetch` — mock household-manager, assert zero `/api/foods?name=` calls
- [ ] `tests/test_recipe_load.py::test_recovery_on_400_food_not_found` — inject a 400 once, then 201
- [ ] `tests/test_workflows.py::test_artifact_grows_monotonically` — run a mocked pipeline, assert no field shrinkage across steps
- [ ] Update existing test_agents.py to assert `validate-catalog` is registered and not overridable for `response_format_model`

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | partial | Bearer token via `HOUSEHOLD_MANAGER_API_KEY` — unchanged from existing pattern. New `VALIDATE_CATALOG_API_TOKEN` is an LLM API token, same handling as the other 6 task tokens. |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a (single-household v1) |
| V5 Input Validation | yes | Pydantic v2 on all tool args (`args_schema` with `extra='forbid'`) — same pattern as `HouseholdManagerApiTool`. Mitigates LLM-hallucinated tool args. |
| V6 Cryptography | no | n/a |

### Known Threat Patterns for LangChain + httpx pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| LLM-hallucinated extra tool args | Tampering | `model_config = ConfigDict(extra="forbid")` on `ValidateFoodsArgs` / `ValidateUnitsArgs` — yields `ValidationError` → `ToolMessage(status='error')` per existing pattern |
| API key leaking into LLM trace | Information disclosure | `HOUSEHOLD_MANAGER_API_KEY` is read inside the tool's `_run`, never passed in tool args. LangWatch middleware sees the tool **call** and **result**, not the secrets used inside the call. Same posture as `HouseholdManagerApiTool`. |
| Catalog fetch retried indefinitely on transient error | Denial of service | `with_retry(stop_after_attempt=2)` on the matcher; raw httpx call has no retry but resp.raise_for_status() bubbles up to the agent as a tool error, which the agent can interpret. Tasks have RQ-level failure boundaries. |
| Prompt-injected catalog entry (e.g. food name `'; DROP TABLE'`) flows through to API body | Injection | The matcher returns ids only (`SemanticMatchEntry.catalog_id`), not free-text names. The POST body uses the id. Names flow only into the `missing_ingredients[]` list — strings, no SQL surface. |

## Sources

### Primary (HIGH confidence)
- `src/robotina/queue/task_types.py` — current Pydantic shape
- `src/robotina/agent/workflows.py` — current `WORKFLOW_REGISTRY` and `build_input` plumbing
- `src/robotina/agent/agents.py` — `AGENT_REGISTRY`, `AgentConfig`, `get_agent_config`
- `src/robotina/llm/__init__.py` — `LLMBackend` Protocol + 3 adapters with `response_format` + middleware wiring (Phase 12)
- `src/robotina/queue/jobs.py` — `run_task` flow, per-job tool injection points
- `src/robotina/queue/workflow_runner.py` — `_extract_task_output`, `on_step_complete` artifact persistence
- `src/robotina/agent/tools/household_manager_api.py` — reference httpx + auth + `args_schema(extra='forbid')` pattern
- `src/robotina/agent/skills/household-manager/shared.md` — `GET /api/foods` / `GET /api/units` full-list contract `[CITED]`
- `src/robotina/agent/skills/household-manager/recipes_create.md` — `POST /api/recipes` request body shape `[CITED]`
- `.planning/decisions/response-format-adoption.md` — per-provider Strategy selection rationale `[CITED]`
- `.planning/phases/15-.../15-CONTEXT.md` — locked decisions D-01..D-23
- Live introspection: `uv run python -c "import inspect; ..."` against installed `langchain-core` and `langchain-ollama` for `with_structured_output` signature and `Runnable.with_retry` signature `[VERIFIED]`
- Live execution: NFKD normalization tested on the project's installed CPython 3.12 against 14 Spanish strings including ñ, ü, accented vowels and mojibake edge case `[VERIFIED]`

### Secondary (MEDIUM confidence)
- LangChain reference site redirect chain (https://reference.langchain.com/python/langchain_core/) — referenced for `BaseChatModel.with_structured_output` doc only; live introspection took precedence
- Project memory `feedback_overrides_in_sync`, `feedback_avoid_premature_abstraction`, `feedback_env_example`, `feedback_prompts_language` — applied to atomicity, two-tool-vs-one decision, env var, prompt language

### Tertiary (LOW confidence)
- gpt-oss with `with_structured_output(method='function_calling')` reliability for `SemanticMatchResult` schema — flagged A3, recommend a one-script spike before committing the matcher implementation
- LangWatch span capture for `with_structured_output` calls outside `create_agent` — flagged A4, recommend manual LangWatch-UI verification during plan execution

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every library pinned and verified installed
- Architecture: HIGH — built from existing patterns; no novel structure
- Pitfalls: HIGH for field-preservation (Pitfall 1) and rename consistency (Pitfall 6); MEDIUM for matcher LangWatch coverage (Pitfall 2) and Ollama structured-output method (Pitfall 3); LOW for catalog-size assumption (Pitfall 4 / A6)
- API endpoints: HIGH for happy path; MEDIUM for envelope shape (A1, A2)

**Research date:** 2026-05-14
**Valid until:** 2026-06-13 (30 days; LangChain 1.x is stable, household-manager API is stable)

---

*Phase: 15-recipe-artifact-accumulation-and-food-unit-validation*
*Researched: 2026-05-14*
