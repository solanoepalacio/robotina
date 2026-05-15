# Phase 15: Recipe Artifact Accumulation and Food/Unit Validation — Pattern Map

**Mapped:** 2026-05-14
**Files analyzed:** 13 new/modified edit points
**Analogs found:** 13 / 13 (every edit point has a close in-tree analog)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/robotina/agent/tools/validate_foods.py` (new) | tool (BaseTool subclass) | request-response (HTTP + LLM) | `src/robotina/agent/tools/household_manager_api.py` | exact (same shape: httpx + auth + strict args_schema) |
| `src/robotina/agent/tools/validate_units.py` (new) | tool (BaseTool subclass) | request-response (HTTP + LLM) | `src/robotina/agent/tools/household_manager_api.py` | exact (sibling of `validate_foods.py`) |
| `src/robotina/agent/tools/_catalog_match.py` (new) | utility / helper module + Pydantic structured-output schema | transform (in-process LLM call) | `src/robotina/llm/__init__.py` (LLMBackend usage); `src/robotina/agent/tools/read_skill.py` (helper-module conventions) | role-match |
| AGENT_REGISTRY `validate-catalog` entry (`src/robotina/agent/agents.py`) | config | n/a | existing `recipe-research-*` entries in `AGENT_REGISTRY` | exact |
| 5 new prompts `V*.md` (gather/instructions/ingredients/metadata bump to V004/V005; recipe-load V005) | prompt | n/a | most recent `V*.md` per directory (e.g. `recipe-research-gather/V004.md`, `recipe-load/V004.md`) | exact |
| `src/robotina/queue/task_types.py` — `RecipeData` / `RecipeIngredient` edits | model (Pydantic) | n/a | current `RecipeData` / `RecipeIngredient` in same file | exact (in-place edit) |
| `src/robotina/agent/workflows.py` — `build_input` callables edits | config / wiring | request-response | current `WORKFLOW_REGISTRY["add-recipe"].steps[*].build_input` lambdas | exact (in-place edit) |
| `overrides/anthropic.json`, `overrides/openai.json`, `overrides/staging.ollama.json` | config | n/a | existing entries for current 7 agents | exact |
| `.env.example` — `VALIDATE_CATALOG_API_TOKEN` | config | n/a | existing `*_API_TOKEN` entries | exact |
| `_build_notify_text` (in `workflows.py`) | utility | n/a | current `_build_notify_text` | exact (in-place edit) |

## Pattern Assignments

### `src/robotina/agent/tools/validate_foods.py` and `validate_units.py` (new tools)

**Analog:** `src/robotina/agent/tools/household_manager_api.py`

**Module docstring + per-job injection note** (lines 1-16 of analog):
- Header block: purpose; what the tool returns on success vs error; the "per-job injection pattern" mention; 401/403 hard-stop posture.
- The two new tools have no `household_id` to inject (the catalog is shared per D-10), but should retain the "constructed once per job" phrasing for consistency with the established convention.

**Imports pattern** (lines 17-27 of analog):
```python
from __future__ import annotations

import asyncio
import logging
import os

import httpx
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)
```
Copy verbatim. The new tools additionally import the shared helper module: `from robotina.agent.tools._catalog_match import match_catalog, FoodOrUnit` (or equivalent).

**Strict args_schema pattern** (lines 30-51 of analog):
```python
class HouseholdManagerApiArgs(BaseModel):
    """... ``extra='forbid'`` makes any unknown LLM-emitted field raise
    ``ValidationError`` at ``tool.invoke()`` time. The langgraph ``ToolNode``
    wraps that error in a ``ToolMessage(status='error')`` the agent sees on
    its next turn ..."""

    model_config = ConfigDict(extra="forbid")

    method: str = Field(description="...")
    path: str = Field(description="...")
```
For Phase 15, the args schema is much smaller — a single field:
```python
class ValidateFoodsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    names: list[str] = Field(description="Spanish food names to resolve against the household-manager food catalog.")
```
Adopt the `extra='forbid'` posture verbatim and keep the docstring rationale comment (the recoverable-`ToolMessage(status='error')` explanation).

**BaseTool class skeleton** (lines 54-100 of analog):
```python
class HouseholdManagerApiTool(BaseTool):
    """... Args (via _run): ... Returns: ... Raises: RuntimeError: On 401 or 403 ..."""

    name: str = "household-manager-api"
    description: str = (
        "Call the household-manager REST API. "
        # ≤6 lines, ends with a JSON-literal hint
    )
    args_schema: type[BaseModel] = HouseholdManagerApiArgs
    household_id: str
```
For Phase 15: `name: str = "validate-foods"` / `"validate-units"`, no `household_id` field, and the description string is at Claude's discretion per CONTEXT (≤4 sentences, no schema duplication).

**HTTP + auth + 401/403 pattern** (lines 102-151 of analog) — copy verbatim:
```python
api_key = os.environ["HOUSEHOLD_MANAGER_API_KEY"]
base_url = os.environ.get("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")

async def _call() -> dict | str:
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method=method.upper(),
            url=f"{base_url}{path}",
            headers={"Authorization": f"Bearer {api_key}"},
            params=query,
            json=body,
        )
        if resp.status_code in (401, 403):
            raise RuntimeError(
                f"household-manager-api: unrecoverable auth error "
                f"(status={resp.status_code}). Check HOUSEHOLD_MANAGER_API_KEY env var."
            )
        if not resp.is_success:
            return {"error": resp.status_code, "message": resp.text}
        return resp.json()

try:
    result = asyncio.run(_call())
except RuntimeError:
    raise  # 401/403 must propagate (hard stop)
except Exception as exc:
    logger.error(...)
    return {"error": "request_failed", "message": str(exc)}
```
The new tools fetch `GET /api/foods` (or `/api/units`) with no `name=` param (per D-07 / household-manager skill `shared.md`), then hand the full list to the shared helper. They must keep the same 401/403 `raise RuntimeError(...)` behaviour and the same recoverable-error dict shape on other non-2xx responses.

**`_run` / `_arun` mirror pattern** (lines 102-160 of analog):
```python
def _run(self, ...): ...
async def _arun(self, ...) -> ...: return self._run(...)
```
Adopt verbatim.

**Return shape** (per D-09):
```python
{
    "matched":   [{"name": "Cebolla",  "id": "uuid-1"}, ...],
    "unmatched": [{"name": "ricotón", "id": None},     ...],
}
```
This is the value returned from `_run` (LangChain serializes it into the `ToolMessage` for the agent). No new envelope shape.

---

### `src/robotina/agent/tools/_catalog_match.py` (new helper module)

**Analog (overall module layout):** `src/robotina/agent/tools/read_skill.py`

That file is the closest in-tree example of a "tool-adjacent helper module that lives in `agent/tools/` and is consumed by tools rather than directly by the agent." Use it as the structural template — module docstring at top, logger, small Pydantic models, then helper functions / classes.

**Module docstring pattern** (lines 1-14 of analog):
```python
"""Skill loading infrastructure for Robotina agents.

Provides:
- SkillSet: ...
- ReadSkillTool: ...
- build_read_skill_tool(): factory ...

...
"""
from __future__ import annotations

import logging
from pathlib import Path
...
logger = logging.getLogger(__name__)
```
Phase 15 analogue: enumerate `match_catalog()`, `SemanticMatchEntry`, `SemanticMatchResult` in the docstring up front.

**Analog (LLM invocation):** `src/robotina/llm/__init__.py` — `make_backend()` factory + the `LLMBackend` Protocol.

**Pattern: per-call backend construction + `with_structured_output` + `with_retry`** (per D-11). The convention to follow:
```python
from robotina.agent.agents import get_agent_config
from robotina.llm import make_backend

config = get_agent_config("validate-catalog")
backend = make_backend(config.model_config)
matcher = backend.model.with_structured_output(SemanticMatchResult).with_retry(stop_after_attempt=2)
result = matcher.invoke([
    SystemMessage(content=<prompt with full catalog>),
    HumanMessage(content=<unmatched names>),
])
```
Mirrors the per-job instantiation rule from `src/robotina/llm/__init__.py` line 5-9:
```
IMPORTANT: All adapter instances MUST be created inside job functions (run_task),
never at module level. This is a locked architectural constraint from STATE.md.
```
Here the equivalent rule is: instantiate the matcher backend inside the helper invocation (i.e. on every tool call), never at module-import time. This keeps env-var resolution and overrides-file reload behaving consistently.

**Pydantic structured-output models** (per D-13):
```python
class SemanticMatchEntry(BaseModel):
    name: str
    catalog_id: str | None  # null → unmatched
class SemanticMatchResult(BaseModel):
    matches: list[SemanticMatchEntry]
```
Co-locate with the helper (CONTEXT explicitly notes this is at Claude's discretion). The shape is binary — no `confidence`, no candidate list (D-13).

**Direct-match normalization** (per D-08):
```python
import unicodedata
def _normalize(s: str) -> str:
    return (
        unicodedata.normalize("NFKD", s)
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold()
        .strip()
    )
```
No analog in tree — this is a fresh utility but it is small and self-contained.

---

### AGENT_REGISTRY `validate-catalog` entry (`src/robotina/agent/agents.py`)

**Analog:** the existing `recipe-research-*` entries (lines 90-145 of `agents.py`).

**Pattern to copy** (`recipe-research-instructions`, lines 104-117 — closest because it has `tools=[]` and is non-workflow-tool-flavored):
```python
"recipe-research-instructions": AgentConfig(
    task_type="recipe-research-instructions",
    model_config={
        "provider": "ollama",
        "url": "http://localhost:11434",
        "model": "gpt-oss:20b",
        "api_key_env": "RECIPE_RESEARCH_INSTRUCTIONS_API_TOKEN",
        "reasoning": True,
    },
    prompt_path="src/robotina/agent/prompts/recipe-research-instructions/V003.md",
    skills=[],
    tools=[],
    response_format_model=RecipeResearchInstructionsOutput,
),
```
Phase 15 `validate-catalog` entry follows the same shape with these substitutions:
- `task_type="validate-catalog"`
- `api_key_env="VALIDATE_CATALOG_API_TOKEN"`
- `prompt_path=` either a small dedicated prompt file (`src/robotina/agent/prompts/validate-catalog/V001.md`) or `prompt_path=""` if the matcher is invoked with `with_structured_output` and an inline system prompt. CONTEXT does not pin this — Claude's discretion at plan time.
- `skills=[]`, `tools=[]`
- `response_format_model=SemanticMatchResult`

Even though `validate-catalog` is not consumed by the task-runner (D-12, D-20), registering it here gives the matcher a single source of truth for model_config and the overrides hot-reload path.

**Override merge logic** (lines 179-215) is unchanged — `validate-catalog` participates automatically as soon as it has an entry in each `overrides/*.json`.

---

### Prompt version bumps (5 prompts)

**Analog (most recent prompt revisions, naming + frontmatter convention):**
- `src/robotina/agent/prompts/recipe-research-gather/V004.md` (most recent gather)
- `src/robotina/agent/prompts/recipe-load/V004.md` (most recent loader)

**Naming pattern:** `V{NNN}.md` (zero-padded 3 digits). Bumps are monotonic per agent — Phase 15 advances each of the 5 by exactly one revision. The five files to create:
- `recipe-research-gather/V005.md` (V004 is current)
- `recipe-research-instructions/V004.md` (V003 is current)
- `recipe-research-ingredients/V004.md` (V003 is current)
- `recipe-research-metadata/V004.md` (V003 is current)
- `recipe-load/V005.md` (V004 is current)

**Frontmatter:** None — these files have no YAML frontmatter. The H1 is `# {Agent Display Name} — V{NNN}` (e.g. `# Recipe Load — V004`). Body uses the standardized Phase 14 skeleton:

```markdown
# {Agent Display Name} — V{NNN}

## Role
{1-3 sentences}

## Inputs
- {bullet list of what arrives in the user message}

## Tools
- `{tool-name}` — {one-line purpose; parameter hints when load-bearing}

## Process
1. ...
2. ...

## Rules
- All user-facing recipe content (name, description, step bodies, ingredient names) is in Argentine / Latin American Spanish. Only this instructional prompt stays in English.
- {other agent-specific rules}
```

This skeleton is the Phase 14 cleanup output (CONTEXT §"Prior phase context"). The most recent V004 files all conform to it — copy that structure for every Phase 15 bump.

**Bump wiring (atomic commit per [[feedback_overrides_in_sync]]):** each prompt-version bump is paired with:
1. Updated `prompt_path=` in the corresponding `AGENT_REGISTRY` entry in `src/robotina/agent/agents.py`.
2. (Optional) Updated `prompt_path` override in `overrides/anthropic.json`, `overrides/openai.json`, `overrides/staging.ollama.json` *if* those files currently pin a `prompt_path` for that agent. Inspect each overrides file before editing — only `recipe-load`'s entry in `overrides/openai.json` (and in `anthropic.json`, `staging.ollama.json`) currently lacks a `prompt_path` line, so for the current snapshot the prompt-path bump is a one-file change (just `agents.py`). The atomic-commit rule still applies if any overrides file is later edited to pin one.

---

### `src/robotina/queue/task_types.py` — model edits

**Analog:** the existing `RecipeData` / `RecipeIngredient` / `RecipeStep` block (lines 40-63 of the file).

**Current state:**
```python
class RecipeIngredient(BaseModel):
    food_name: str        # human-readable name — resolved to foodId by recipe-load
    unit_name: str | None = None
    quantity: float | None = None
    note: str | None = None

class RecipeData(BaseModel):
    name: str
    description: str | None = None
    servings_qty: int | None = None
    ...
    ingredients: list[RecipeIngredient]
    steps: list[RecipeStep]
```

**Pattern to follow** (Pydantic v2, snake_case, `| None = None` for every optional, NO `Field(..., alias=...)`):
- Add `food_id: str | None = None` and `unit_id: str | None = None` to `RecipeIngredient` (D-03).
- Loosen `name: str` to keep `str` required (CONTEXT: "name required when the artifact reaches recipe-load") but every other current required field becomes `... | None = None`. `ingredients` and `steps` become `list[...] = []` (default empty list) per D-01.
- Add `gathered_sources: list[dict] | None = None` to `RecipeData` (D-04).
- Add `missing_ingredients: list[str] = []` to `RecipeData` (D-05).
- Drop `missing_ingredients` from `RecipeLoadOutput` (D-19) — keep only `recipe_id`, `recipe_name`, `recipe_description`, `recipe_slug`.
- No `by_alias` / no Pydantic aliases (D-18). Workflow_runner, dashboard, and tests all consume snake_case `model_dump(mode='json')`.

**Re: intermediate `*Output` models** (`RecipeResearchGatherOutput`, `RecipeResearchInstructionsOutput`, `RecipeResearchIngredientsOutput`, `RecipeResearchMetadataOutput`) — every sub-agent now binds `response_format=RecipeData` (D-01). Either:
- Replace each `Recipe*Output` with `RecipeData` directly in `AGENT_REGISTRY.response_format_model=`, then delete the `Recipe*Output` classes; OR
- Alias them: `RecipeResearchGatherOutput = RecipeData` (sentinel only — same class).

CONTEXT marks this as Claude's discretion at plan time. The `Recipe*Input` models stay (workflow_runner relies on them for `build_input`).

---

### `src/robotina/agent/workflows.py` — `build_input` callable edits

**Analog:** the current `WORKFLOW_REGISTRY["add-recipe"].steps[*].build_input` lambdas (lines 108-178).

**Current threading style:**
```python
WorkflowStepDef(
    step_key="metadata",
    task_type="recipe-research-metadata",
    build_input=lambda ctx, artifacts: RecipeResearchMetadataInput(
        query=ctx["recipe_query"],
        draft_name=artifacts["instructions"]["draft_name"],
        draft_description=artifacts["instructions"]["draft_description"],
        draft_instructions=[
            RecipeStep(**s) for s in artifacts["instructions"]["draft_instructions"]
        ],
        ingredients=[
            RecipeIngredient(**i) for i in artifacts["ingredients"]["ingredients"]
        ],
        gathered_recipes=_recipes(artifacts["gather"]),
        source_url=_recipes(artifacts["gather"])[0].get("url") if _recipes(artifacts["gather"]) else None,
    ),
),
```

**Phase 15 pattern (thread accumulating RecipeData):**
```python
WorkflowStepDef(
    step_key="metadata",
    task_type="recipe-research-metadata",
    build_input=lambda ctx, artifacts: RecipeResearchMetadataInput(
        query=ctx["recipe_query"],
        recipe=RecipeData(**artifacts["ingredients"]),  # incoming partial artifact
    ),
),
```
Every research sub-step's `build_input` reads `artifacts[<prev_step_key>]` (the accumulating snapshot) and rehydrates a `RecipeData` for the next step. The current `_recipes(...)` helper for the gather artifact stays — gather emits `gathered_sources` populated; instructions/ingredients/metadata read from `recipe.gathered_sources`. The metadata step's final emit nulls `gathered_sources` (D-04) so the artifact handed to recipe-load is a clean payload.

**Rehydration convention (already present at line 167):**
```python
build_input=lambda ctx, artifacts: RecipeLoadInput(
    recipe=RecipeData(**artifacts["metadata"]["recipe"]),
    household_id=ctx["household_id"],
),
```
For Phase 15, the artifact dict *is* the `RecipeData` (no wrapping `"recipe": ...` key), so:
```python
recipe=RecipeData(**artifacts["metadata"]),
```

This wiring change cascades through every research sub-step's `build_input`. The acknowledge step and notify step are untouched.

---

### `_build_notify_text` (in `workflows.py`)

**Analog:** current `_build_notify_text` (lines 79-94 of `workflows.py`).

**Current signature** (D-07 of an earlier phase):
```python
def _build_notify_text(load_artifact: dict) -> str:
    ...
    missing = load_artifact.get("missing_ingredients", [])
    ...
```

**Phase 15 update** (per D-05 / D-19): signature takes both metadata and load artifacts:
```python
def _build_notify_text(metadata_artifact: dict, load_artifact: dict) -> str:
    base_url = os.environ.get("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")
    name = load_artifact.get("recipe_name", "Unknown recipe")
    description = load_artifact.get("recipe_description")
    slug = load_artifact.get("recipe_slug", "")
    missing = metadata_artifact.get("missing_ingredients", [])  # ← moved from load_artifact
    ...
```

And the notify step's `build_input` (line 174) updates to pass both:
```python
build_input=lambda ctx, artifacts: SendNotificationInput(
    **ctx["reply_context"],
    text=_build_notify_text(artifacts["metadata"], artifacts["load"]),
),
```

---

### `overrides/anthropic.json`, `overrides/openai.json`, `overrides/staging.ollama.json`

**Analog:** existing entries in each file.

**Pattern from `overrides/openai.json`** (lines 16-22 — one entry per agent, model_config only, no prompt_path override at present):
```jsonc
"recipe-research-gather": {
    "model_config": {
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "api_key_env": "API_TOKEN_OPENAI"
    }
}
```

**Pattern from `overrides/staging.ollama.json`** (Ollama variant — adds `url` and `reasoning`, no `api_key_env`):
```jsonc
"recipe-research-gather": {
    "model_config": {
        "provider": "ollama",
        "url": "http://192.168.68.109:11434",
        "model": "gpt-oss:20b",
        "reasoning": true
    }
}
```

**Phase 15 additions (atomic across all 3 files per [[feedback_overrides_in_sync]]):**
- New entry `"validate-catalog": { "model_config": { ... } }` in each file, mirroring the per-file provider/model pattern (Anthropic Haiku for `anthropic.json`, `gpt-4.1-mini` for `openai.json`, `gpt-oss:20b` for `staging.ollama.json`).
- `anthropic.json` is currently missing a `recipe-load` entry (only 6 entries vs 7 in `openai.json`). The audit during Phase 15 should add it for parity — but if intentional drift, leave as-is and document.
- No `prompt_path` lines in any current entry. If a Phase 15 plan decides to pin a prompt path in overrides, it must add it to all 3 files in the same commit.

---

### `.env.example` — new env var

**Analog:** the `LLM API tokens` block (lines 17-26 of `.env.example`):
```
# LLM API tokens (Phase 4+)
RECIPE_RESEARCH_GATHER_API_TOKEN=
RECIPE_RESEARCH_INSTRUCTIONS_API_TOKEN=
RECIPE_RESEARCH_INGREDIENTS_API_TOKEN=
RECIPE_RESEARCH_METADATA_API_TOKEN=
RECIPE_LOAD_API_TOKEN=
HANDLE_INCOMING_MESSAGE_API_TOKEN=
ACKNOWLEDGE_ADD_RECIPE_API_TOKEN=
```

**Phase 15 addition** — append `VALIDATE_CATALOG_API_TOKEN=` to that block. Per [[feedback_env_example]], every new env var must land here in the same commit that introduces its consumer.

## Shared Patterns

### Strict `args_schema` with `extra='forbid'`
**Source:** `src/robotina/agent/tools/household_manager_api.py` lines 30-51.
**Apply to:** every new BaseTool subclass (`validate-foods`, `validate-units`).
```python
class FooArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    names: list[str] = Field(description="...")
```
Keep the docstring rationale block explaining how this turns LLM hallucinations into recoverable `ToolMessage(status='error')`.

### `asyncio.run(_call())` HTTP pattern with 401/403 hard stop
**Source:** `src/robotina/agent/tools/household_manager_api.py` lines 102-151.
**Apply to:** every tool that calls the household-manager API. Same auth header (`Authorization: Bearer {HOUSEHOLD_MANAGER_API_KEY}`), same `HOUSEHOLD_MANAGER_BASE_URL` env var with `localhost:3001` default, same `raise RuntimeError(...)` on 401/403, same `{"error": status, "message": resp.text}` on other non-2xx.

### Per-job tool injection at construction time
**Source:** `src/robotina/agent/tools/queue.py` lines 9-15 and `household_manager_api.py` lines 7-8.
**Apply to:** tools that need per-job config. The new tools have no `household_id` (D-10) but should still be constructed inside `run_task()` (not module-level) for consistency.

### Per-job LLM-backend instantiation
**Source:** `src/robotina/llm/__init__.py` lines 5-9 (module docstring rule) and `make_backend()` (line 348).
**Apply to:** the matcher LLM call inside `_catalog_match.py`. Instantiate the backend on every invocation; never cache at module scope. This preserves the AGENT_OVERRIDES_FILEPATH hot-reload contract (`get_agent_config()` re-reads the override file on every call).

### Standardized prompt skeleton (Role / Inputs / Tools / Process / Rules)
**Source:** `src/robotina/agent/prompts/recipe-load/V004.md` and `recipe-research-gather/V004.md`.
**Apply to:** every prompt-version bump. No frontmatter, H1 = `# {Agent} — V{NNN}`, body uses the 5-section skeleton with `## Rules` always containing the Spanish-output / English-prompt clause.

### Atomic-commit rule for prompt / registry / overrides changes
**Source:** [[feedback_overrides_in_sync]] (memory).
**Apply to:** every prompt-version bump and the new `validate-catalog` entry. One commit = (a) new prompt file, (b) updated `prompt_path` in `agents.py`, (c) overrides-file edits for all 3 environments where applicable. Never split.

### `.env.example` synchronization
**Source:** [[feedback_env_example]] (memory).
**Apply to:** the `VALIDATE_CATALOG_API_TOKEN` addition. Land it in the same commit that introduces the consumer code.

## No Analog Found

Every Phase 15 edit point has at least a partial in-tree analog. The two areas that lean partially on out-of-tree precedent:

| Edit point | What's covered by an analog | What's net-new |
|------------|----------------------------|-----------------|
| Semantic-fallback LLM call (`_catalog_match.match_catalog`) | LLMBackend instantiation, `make_backend`, `get_agent_config` lookup pattern | The specific `backend.model.with_structured_output(...).with_retry(...)` invocation — no existing helper in the codebase calls `with_structured_output` directly (Phase 11 wraps response_format inside `LLMBackend.create_agent()`, not as a free-standing LLM call). RESEARCH.md / Phase 11 decisions doc is the reference for the call shape. |
| NFKD-normalized direct-match utility | None in tree | Self-contained ~5-line utility per D-08. |

## Metadata

**Analog search scope:**
- `src/robotina/agent/tools/` — all 6 existing tool modules
- `src/robotina/agent/agents.py` — AGENT_REGISTRY
- `src/robotina/agent/workflows.py` — WORKFLOW_REGISTRY
- `src/robotina/queue/task_types.py` — Pydantic input/output models
- `src/robotina/llm/__init__.py` — LLMBackend Protocol + adapters
- `src/robotina/agent/prompts/**/V*.md` — all 23 prompt revisions
- `overrides/*.json` — all 3 environment overrides
- `.env.example`

**Files scanned:** ~30 files
**Pattern extraction date:** 2026-05-14
