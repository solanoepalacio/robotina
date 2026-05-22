# Phase 24: Recipe Images (Topic 3) — Research

**Researched:** 2026-05-22
**Domain:** Recipe image acquisition for Robotina — deterministic task type, runner-level non-fatal-failure capability, Tavily image search, recipe-scrapers `.image()` fallback, `safe_fetch` reuse for image URL validation
**Confidence:** HIGH on existing codebase shape and reuse strategy (verified file-by-file); HIGH on Tavily image-search API shape (verified against docs.tavily.com 2026-05-22); MEDIUM on recipe-scrapers `.image()` exception behavior on per-site scrapers (HIGH on AbstractScraper signature — `raise NotImplementedError`); MEDIUM-LOW on Tavily image relevance quality for Spanish/Argentine regional recipe names (this IS the Phase 24 manual-eval gate per D-09/D-11).

## Summary

Phase 24 layers a recipe image acquisition step into both `add-recipe-from-*` workflow variants between `metadata` and `recipe-load`. The work splits into three architectural concerns plus two product concerns, all of which have strong precedent in the codebase:

1. **Runner-level non-fatal-failure capability** (`WorkflowStepDef.non_fatal_on_failure: bool = False` + `StepUnavailableArtifact` + `_finalize_step_unavailable` helper in `workflow_runner.py`) — NEW reusable runner capability, lands FIRST in standalone commit (mirrors Phase 23 `safe_fetch`-first pattern). Only `recipe-image` opts in for v1.1.
2. **Deterministic `recipe-image` task type** — agent-less Python function `acquire_recipe_image()` mirroring the `finalize-outcome` branch at `jobs.py:119`. No LLM, no prompt, no AGENT_REGISTRY entry. Memory `feedback_avoid_premature_abstraction` is the governing principle: both fallback branches are mechanical.
3. **Fallback ladder + `safe_fetch` reuse:** source-page `recipe_scrapers.scrape_html().image()` when `RecipeData.source_url` is set → Tavily image search (`include_images=True`) otherwise → mark missing. Candidate URL validated through the existing `safe_fetch` with `expected_content_type="image/*"` and `max_bytes=15_000_000`.
4. **Storage = URL pin** (D-05). Robotina posts `image_url: str | null` in the household-manager recipe payload; the backend stores the URL string. No bytes redistributed, no EXIF strip, no rehost endpoint.
5. **Experiments + manual gate.** `experiments.recipe_image` exercises the deterministic function over a 10–15-row fixture set; `experiments.robotina_wake` exercises V007 against synthetic outcomes (including `image_present=True/False/failure` mix) — both write per-backend results files; final `24-SMOKE.md` carries the operator verdict.

**Primary recommendation:** Implement in nine plans following CONTEXT D-21 ordering (24-01 lands the runner capability standalone; 24-02 schema/types; 24-03 Tavily image tool; 24-04 deterministic `acquire_recipe_image`; 24-05 workflow-registry insertion + jobs.py branch + recipe-load key swap; 24-06 `finalize-outcome` `image_present` flip; 24-07/08 experiments; 24-09 operator smoke). No new dependencies. No new env vars. No Alembic migration. Inline-duplicate the `recipe-image` step in BOTH `WORKFLOW_REGISTRY` entries — shared-tail helper extraction is *further* deferred per D-06.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Runner non-fatal-failure flag (capability) | Queue / workflow engine (`workflow_runner.py`, `jobs.py`) | Task-type contracts (`task_types.py` for `StepUnavailableArtifact`) | Policy is per-step `WorkflowStepDef` field; enforcement is in `run_task`'s exception branch + the `_finalize_step_*` helpers. Putting it in the agent layer would (a) miss exceptions from non-agent tasks (Tavily 503, SafeFetchError) and (b) drift across agent authors. |
| `recipe-image` task execution | Agent layer (`src/robotina/agent/tasks/recipe_image.py` — NEW module) | Queue dispatcher (`jobs.py` `run_task` branch) | Mirrors `finalize-outcome` (deterministic, agent-less). The `acquire_recipe_image` function owns the fallback ladder; `run_task` owns lifecycle + OTel span. |
| Tavily image search HTTP | Agent tool layer (`src/robotina/agent/tools/tavily_image_search.py` — NEW) | n/a | Sibling to `web_search.py`; same `TAVILY_API_KEY`, same `TavilyClient`, different param + response shape. Plain function (not BaseTool) is sufficient because no LLM agent calls it in v1.1. |
| Source-page `.image()` extraction | Agent layer (inside `acquire_recipe_image`) | URL utilities (`safe_fetch` for the source-page HTML fetch) | The deterministic function calls `safe_fetch(...)` directly + `recipe_scrapers.scrape_html(html).image()`. Helper extraction (sharing logic with `FetchAndScrapeTool`) is deferred — duplication is two `safe_fetch` + `scrape_html` lines, not a real abstraction. |
| Image URL validation (SSRF defense) | URL utility layer (`safe_fetch`) | n/a | Reused unchanged. Caller passes `expected_content_type="image/*"` (wildcard already supported per `safe_fetch.py:215-217` — `accepted = ("image/",)` prefix-match). `max_bytes=15_000_000`. |
| Image URL persistence | Backend (household-manager API) | Robotina (POST payload via `recipe-load`) | URL pin (D-05). `recipe-load`'s existing `HouseholdManagerApiTool` POST already serializes the full `RecipeData` payload; adding `image_url: str | None` is a JSON-schema concern only. Backend coordination: the recipe entity must accept `image_url` — research treats as known precondition (CONTEXT line 359-365); smoke verifies. |
| `WorkflowRun.outcome.image_present` derivation | Queue dispatcher (`jobs.py` `finalize-outcome` branch) | Task-type contract (`AddRecipeOutcome.image_present` already exists) | Field schema unchanged; just flip the producer logic to read `accumulated_artifacts["recipe-image"]`. |
| Dashboard label | Frontend (`_macros.html` Jinja) | n/a | One-line addition: `"recipe-image": "Imagen"`. |
| LangWatch tracing | Observability layer (existing `langwatch.trace()` in `run_task`) | n/a | Deterministic branch wraps the function call in the existing OTel span. No LLM-span (no LLM call), which is correct. |

## User Constraints (from CONTEXT.md)

### Locked Decisions

(Copying verbatim — the CONTEXT D-NN numbers are the durable references the planner must cite.)

- **D-01** `WorkflowStepDef.non_fatal_on_failure: bool = False` (definition flag) + runner converts exceptions to "unavailable" artifact via `_finalize_step_unavailable(step, reason, session)` helper that routes through the DONE-path advancement. Reason composed via the same Pydantic-URL-noise-stripping + 150-char truncation as `_compose_failure_outcome` (`workflow_runner.py:52`). Exception type does not matter — the flag is the decision.
- **D-01b** Only `recipe-image` sets `non_fatal_on_failure=True` in v1.1. All other steps stay strict.
- **D-02** `recipe-image` is a DETERMINISTIC agent-less task type — new branch in `run_task` mirroring `finalize-outcome` at `jobs.py:119`. No LangChain agent, no prompt, no AGENT_REGISTRY entry. LangWatch span wraps the function call (no LLM-span expected).
- **D-03** New Pydantic models in `src/robotina/queue/task_types.py`: `RecipeImageInput {recipe: RecipeData, reply_context: ReplyContext, household_id: NonEmptyHouseholdId}` and `RecipeImageOutput` (shaped identically to `RecipeData` with `image_url` added; in practice emit `recipe.model_dump(mode='json')` with `image_url` set). Also `StepUnavailableArtifact {status: Literal["unavailable"], step_key: str, reason: str (≤150 chars)}`.
- **D-04** Add `image_url: str | None = None` to `RecipeData` (`task_types.py:105`). Owned by the `recipe-image` step; all earlier steps preserve `None`. `recipe-load` reads it from the incoming `RecipeData` and includes it in the household-manager POST.
- **D-05** **URL pin storage.** Robotina POSTs `image_url: str | None` in the recipe payload; household-manager stores the URL string. No bytes transferred; no rehost endpoint. No EXIF strip, no magic-byte validation, no image-format enforcement in Robotina.
- **D-06** Inline-duplicate the `recipe-image` step insertion in both `add-recipe-from-query` and `add-recipe-from-url` entries of `WORKFLOW_REGISTRY`. NO `build_recipe_tail()` helper. Phase 23 D-01's shared-tail extraction directive is *further deferred* — recipe-quality iteration ahead will churn the tail.
- **D-06b** `recipe-load`'s `build_input` updated to read `artifacts["recipe-image"]` instead of `artifacts["metadata"]` in BOTH variants. Both shapes are full `RecipeData` dumps; only the source step key changes.
- **D-07** `finalize-outcome` reads `accumulated_artifacts["recipe-image"]` and sets `image_present=True` iff the artifact exists, is NOT a `StepUnavailableArtifact`, AND has a non-empty `image_url`. `False` for the unavailable case, absent case, or empty-string edge case.
- **D-07b** `AddRecipeOutcome.image_present` schema unchanged (field already exists at `task_types.py:370`). Phase 24 only flips the producer logic.
- **D-08** **NO wake-reply prompt change in v1.1. V007 stays.** Gated via `experiments.robotina_wake` smoke (D-08b/D-10).
- **D-08b** `experiments.robotina_wake` fixture MUST include `outcome.status=success+image_present=True`, `success+image_present=False`, `failure`, and a mixed multi-outcome batch. Verdict line in `24-SMOKE.md` explicitly records the operator's "V007 acceptable across image_present True/False" decision.
- **D-09** `experiments/recipe_image.py` — single script; iterates a 10–15-row fixture set; calls `acquire_recipe_image(...)` directly (no workflow); emits results to `.planning/phases/24-recipe-images-topic-3/24-IMG-EVAL-RESULTS-<backend>.md`. LangWatch instrumentation active. No automated pass/fail metric for image relevance — operator eyeballs the table.
- **D-10** `experiments/robotina_wake.py` — single script; constructs SYNTHETIC `WakeInvocationInput` in memory; invokes the wake-context Robotina agent directly; no DB writes; per-row operator verdict for `24-WAKE-RESULTS-<backend>.md`.
- **D-11** Top-result only + source-page bypass. Vision-LLM "is this the right dish?" check deferred to v1.2 gated on Phase 24 eval relevance (<60% relevant → escalate). NO multi-candidate retry; NO magic-byte PIL validation; NO image quality/resolution filtering.
- **D-12** NEW `tavily_image_search` function (or `TavilyImageSearchTool` class) in `src/robotina/agent/tools/tavily_image_search.py`. Reads `TAVILY_API_KEY`. The deterministic branch calls the underlying `TavilyClient.search(..., include_images=True)` directly. Plain function is preferred (no LLM agent calls it).
- **D-13** `safe_fetch` reused unchanged: `expected_content_type="image/*"` (wildcard already supported), `max_bytes=15_000_000` (15 MB for images vs 5 MB default for HTML). Eval/results files mirror Phase 21/22/23 pattern.
- **D-14..D-19** Test strategy — non-fatal runner tests, `acquire_recipe_image` unit tests, Tavily tool tests, `safe_fetch` image/* assertion test, `finalize-outcome` extension tests, workflow registry assertions.
- **D-20** Operator manual eval is the load-bearing user-facing gate. Phase 24 verification routes as `human_needed` until `24-SMOKE.md` ends with `verdict: pass`.
- **D-21 (Plan ordering — Planner final call):** 24-01 runner capability → 24-02 schema + safe_fetch image-wildcard verification → 24-03 Tavily image function → 24-04 `acquire_recipe_image` → 24-05 workflow-registry insertion + jobs.py branch + recipe-load key swap → 24-06 `finalize-outcome` flip → 24-07 `experiments.recipe_image` + eval set → 24-08 `experiments.robotina_wake` → 24-09 operator smoke (autonomous=false).

### Claude's Discretion

- Tavily image-search query construction: `f"{recipe.name} receta"` (Spanish-language hint). Tunable in v1.2.
- Whether `tavily_image_search` is a plain function or a `BaseTool` subclass. Plain function is the simpler default in v1.1 since no LLM agent calls it.
- Whether to extract a tiny shared helper for `safe_fetch + scrape_html` (source-page branch) or inline the 4 lines in `acquire_recipe_image`. Inline is the v1.1 stance.
- Dashboard label string: `"recipe-image": "Imagen"`.
- LangWatch metadata tag keys for the eval script (`phase=24`, `recipe_name=…`, `branch=…`).

### Deferred Ideas (OUT OF SCOPE)

- `build_recipe_tail()` shared-tail helper — Phase 23 D-01 named Phase 24 as extraction; D-06 defers further. Revisit when tail stabilizes AND a 3rd workflow variant beyond query/url lands.
- Vision-LLM "is this the right dish?" check (Pitfall 8 full mitigation) — v1.2.
- Image download-and-rehost to household-manager (IMG-05 alternative) — needs NEW backend endpoint; v1.2.
- EXIF strip + magic-byte validation via PIL — only relevant on rehost; v1.2.
- Periodic broken-link sweep — scheduler milestone.
- Multi-candidate retry on `safe_fetch` failure — v1.2.
- Per-locale Tavily query templating (`mexicana`, `argentina`, etc.) — v1.2.
- Wake-reply "guardé X, pero sin foto" sentence (V008 fork) — v1.2; better owned by future Compose agent.
- LangWatch A/B testing of Tavily query phrasings — v1.3.
- Image quality / resolution filtering (reject thumbnails < 400px) — Pitfall 8 risk; deferred.
- AI image generation as fallback — explicitly rejected.
- Image source diversification (Unsplash + Pexels) — single source in v1.1.
- `hint` field on `RecipeImageInput` — speculative.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| IMG-01 | `recipe-image` task type inserted between metadata and `recipe-load`; produces `image_url` (or empty/sentinel) | D-02 (deterministic task), D-06 (inline insertion in both `WORKFLOW_REGISTRY` entries), D-04 (`RecipeData.image_url`), Code Examples §1 (the branch shape), Code Examples §5 (registry insertion) |
| IMG-02 | Fallback ladder: source-page `.image()` (URL-sourced) → Tavily `include_images=True` otherwise → mark missing | D-11 (the ladder + bypass + top-result-only); Code Examples §3 (the ladder function); recipe-scrapers `.image()` semantics §"Recipe-scrapers Behavior"; Tavily images list §"Tavily Image Search" |
| IMG-03 | Image acquisition failure is non-fatal — runner advances; recipe saves; `outcome.image_present=False` | D-01 (runner flag + helper), D-07 (`image_present` derivation); Code Examples §2 (`_finalize_step_unavailable` shape) |
| IMG-04 | Image URL validated via `safe_fetch` reusing SSRF defenses | D-13 (`safe_fetch` reuse, content-type `image/*` already supported in `safe_fetch.py:215-217`); `max_bytes=15_000_000` caller-side |
| IMG-05 | Image URL persisted via household-manager API (storage strategy decided at planning) | D-05 (URL pin); `recipe-load`'s existing `HouseholdManagerApiTool` carries `image_url` in payload; backend precondition (recipe entity accepts `image_url`) verified via smoke |
| IMG-06 | Runner supports per-step non-fatal-failure semantics declared at step-definition level | D-01 (`WorkflowStepDef.non_fatal_on_failure: bool = False`); structured `StepUnavailableArtifact` D-03 |
| EXP-01 | Existing experiment scripts remain runnable | `RecipeData.image_url` added with default `None`; no existing task-input schema renamed; verified by §"Backward Compatibility" |
| EXP-03 | `experiments.recipe_image` exercises Tavily + source-page with LangWatch traces | D-09 (script shape, fixture coverage classes, LangWatch instrumentation); existing `experiments/gather_from_url.py` is the pattern to mirror |
| EXP-04 | `experiments.robotina_wake` exercises wake-context iteration | D-10 (synthetic in-memory `WakeInvocationInput`; no DB writes); D-08b (V007 fixture coverage including `image_present` True/False); existing `_check_and_dispatch_wake` flow + `WakeInvocationInput.to_user_message()` reference |
| EXP-06 | `pyproject.toml [project.scripts]` declarations updated; CLAUDE.md table mirrors | Two entries to add (`experiments.recipe_image`, `experiments.robotina_wake`); existing entries (`experiments.gather_from_url`, `experiments.recipe_research`, `experiments.recipe_load`, `experiments.multi_recipe_eval`) confirm the format |

## Standard Stack

### Core (already in stack — no additions)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `tavily-python` | `>=0.3` (already declared `pyproject.toml:27`) | Image search via `TavilyClient.search(include_images=True)` | Same provider as `WebSearchTool`; same `TAVILY_API_KEY`. No new dep. [VERIFIED: pyproject.toml] |
| `recipe-scrapers` | `>=15.11.0` (already declared `pyproject.toml:33`) | Source-page `.image()` extraction for URL-sourced inputs | Already used by `FetchAndScrapeTool`; `wild_mode=True` matches the existing call site. [VERIFIED: pyproject.toml + `src/robotina/agent/tools/fetch_and_scrape.py:128`] |
| `httpx` | `>=0.27` (already declared) | Transport under `safe_fetch` | Reused unchanged. [VERIFIED: pyproject.toml] |
| `pydantic` | `>=2.7` | New `RecipeImageInput`, `RecipeImageOutput`, `StepUnavailableArtifact` models | `ConfigDict(extra="forbid")` per project convention. [VERIFIED: existing models] |

**Verified versions** (`pyproject.toml` lock — read 2026-05-22):
```
tavily-python>=0.3
recipe-scrapers>=15.11.0
httpx>=0.27
pydantic>=2.7
```
No version bumps required.

### Supporting (already in stack)

| Library | Purpose |
|---------|---------|
| `langwatch` | OTel trace emission on the deterministic branch (matches `finalize-outcome` precedent — the existing `langwatch.trace()` wrap in `jobs.py:359` covers LLM branches; the deterministic branches at `jobs.py:90` and `jobs.py:119` do NOT enter that wrap). For Phase 24, planner decides whether to add an OTel span explicitly around `acquire_recipe_image()` (per D-02 "LangWatch span emission") OR rely on the run_task-level logging. **Recommendation:** add a minimal `with langwatch.trace(metadata={"task_type": "recipe-image", "branch": ...}):` wrap around the function call so the dashboard surfaces the step. |
| `dotenv` | `.env` loading in experiment scripts (existing pattern) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff | Verdict |
|------------|-----------|----------|---------|
| Tavily `include_images=True` | Bing Image Search / Google Custom Search | Different API key, different paid tier, additional vendor relationship | Tavily wins — zero new deps, same key, V1 research (`STACK.md`) already validated. |
| `tavily_image_search` plain function | `TavilyImageSearchTool(BaseTool)` subclass mirroring `WebSearchTool` | BaseTool adds LLM-tool surface; pointless if no LLM agent calls it. | Plain function in v1.1; convert to BaseTool when vision-LLM v1.2 mitigation needs it. |
| LLM agent + `response_format` for `recipe-image` | Deterministic Python function | Adds ~$0.001-0.01 per recipe save for zero decision value; both branches mechanical. | Deterministic — D-02. |
| Download image bytes + rehost via new backend endpoint | URL pin | Backend hasn't built the upload endpoint; EXIF/magic-byte concerns; M-sized backend work | URL pin — D-05. |
| `PIL` magic-byte validation on image bytes | `safe_fetch` Content-Type sniff only | We don't redistribute bytes, so trusting Content-Type is fine; browser-side `<img>` decoding handles malformed bytes | Skip PIL — D-11 + D-05. |
| Helper extraction sharing `safe_fetch + scrape_html` between `FetchAndScrapeTool` and `acquire_recipe_image` | Inline the 4 lines twice | Two callers, mostly the same pattern but `FetchAndScrapeTool` is wrapped in `BaseTool` while `acquire_recipe_image` is a plain function — extraction would force awkward type boundaries | Inline — `feedback_avoid_premature_abstraction` |

**Installation:** No new packages. No changes to `pyproject.toml [project.dependencies]`. Two new entries to `[project.scripts]`:
```
"experiments.recipe_image" = "experiments.recipe_image:main"
"experiments.robotina_wake" = "experiments.robotina_wake:main"
```

## Architecture Patterns

### System Architecture Diagram

```
                       add-recipe-from-{query,url} workflow
                                       │
   ┌─────────┐   ┌──────────────┐   ┌────────────┐   ┌──────────┐   ┌──────────────┐   ┌──────────┐   ┌──────────────────┐
   │ gather  │ → │ instructions │ → │ ingredients│ → │ metadata │ → │ recipe-image │ → │ load     │ → │ finalize-outcome │
   │ (LLM)   │   │ (LLM)        │   │ (LLM)      │   │ (LLM)    │   │ (DETERMIN.   │   │ (LLM)    │   │ (DETERMIN. —     │
   │         │   │              │   │            │   │          │   │  NEW — D-02) │   │          │   │  jobs.py:119)    │
   └─────────┘   └──────────────┘   └────────────┘   └──────────┘   └──────┬───────┘   └────┬─────┘   └────────┬─────────┘
       │                                                                    │                │                  │
       │       RecipeData accumulator across all steps (Phase 15 pattern)   │                │                  │
       │       — recipe-image owns image_url; preserves all upstream fields │                │                  │
       │                                                                    │                │                  │
       ▼                                                                    ▼                ▼                  ▼
   shared_context["recipe_query"]                                  recipe-image          household-mgr      WorkflowRun.outcome
       OR ["recipe_url"]                                              ladder:            POST /recipes      .image_present read
       (Phase 23)                                                     1. source-page    (image_url IN       from artifacts["recipe-image"]
                                                                         (URL-sourced)   payload — D-05)    (D-07)
                                                                      2. Tavily image
                                                                         search
                                                                      3. mark missing

                                              ┌─────────────────────────────────────────────────┐
                                              │  Non-fatal-failure capability (D-01 — NEW)      │
                                              │                                                  │
                                              │  WorkflowStepDef.non_fatal_on_failure=True       │
                                              │                                                  │
                                              │  Exception → _finalize_step_unavailable(...)     │
                                              │    writes StepUnavailableArtifact                │
                                              │    routes through DONE-path advancement          │
                                              │  All other steps unchanged (default False).      │
                                              └─────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
src/robotina/
├── agent/
│   ├── tasks/                   # NEW directory? Or inline in src/robotina/queue/jobs.py?
│   │   └── recipe_image.py      # NEW (D-02) — acquire_recipe_image() deterministic fn
│   ├── tools/
│   │   ├── tavily_image_search.py   # NEW (D-12) — plain function or BaseTool subclass
│   │   ├── fetch_and_scrape.py      # EXISTING — reference for source-page pattern
│   │   └── web_search.py            # EXISTING — reference for Tavily wiring
│   └── workflows.py             # MODIFIED — add `recipe-image` step inline in BOTH variants
├── queue/
│   ├── task_types.py            # MODIFIED — add RecipeImageInput/Output, StepUnavailableArtifact, RecipeData.image_url
│   ├── workflow_runner.py       # MODIFIED — _finalize_step_unavailable helper, exception dispatch
│   └── jobs.py                  # MODIFIED — new "recipe-image" branch in run_task; "finalize-outcome" reads artifact
├── url/
│   └── safe_fetch.py            # UNCHANGED (image/* wildcard already supported; verify in test)
└── dashboard/templates/
    └── _macros.html             # MODIFIED — add "recipe-image": "Imagen"

experiments/
├── recipe_image.py              # NEW (D-09)
└── robotina_wake.py             # NEW (D-10)

.planning/phases/24-recipe-images-topic-3/
├── 24-IMG-EVAL-SET.md           # NEW (canonical fixture set, 10-15 rows)
├── 24-IMG-EVAL-RESULTS-<backend>.md   # NEW (operator-run)
├── 24-WAKE-RESULTS-<backend>.md       # NEW (operator-run)
└── 24-SMOKE.md                  # NEW (operator final verdict)
```

**Note on `src/robotina/agent/tasks/` directory:** It doesn't exist yet. The CONTEXT references it (D-02). Alternative: place `acquire_recipe_image` directly in `src/robotina/queue/jobs.py` near the `finalize-outcome` branch. Recommendation: new `src/robotina/agent/tasks/` package for clean separation (mirrors the precedent of `tools/` being its own subpackage); the deterministic function is more "agent-y task logic" than "queue lifecycle."

### Pattern 1: Deterministic agent-less task branch (mirrors `finalize-outcome`)

**What:** A `task_type` is dispatched in `run_task` via an `if task_type == "X":` branch BEFORE the LLM-config lookup; the branch runs plain Python and calls `workflow_runner.on_step_complete(job.id, artifact, ...)` itself.
**When to use:** The task is mechanical (no LLM decision), and adding an LLM agent for a single-string output is over-engineering.
**Example (the existing `finalize-outcome` branch):**

```python
# Source: src/robotina/queue/jobs.py:119-165 (existing)
if task_type == "finalize-outcome":
    from robotina.queue.task_types import AddRecipeOutcome
    from robotina.queue.models import WorkflowRun, WorkflowRunStep
    try:
        load = task_input.load or {}
        recipe_id = load.get("recipe_id") if isinstance(load, dict) else None
        if recipe_id:
            outcome = AddRecipeOutcome(
                status="success",
                recipe_id=recipe_id,
                recipe_name=load.get("recipe_name"),
                recipe_slug=load.get("recipe_slug") or None,
                image_present=False,  # <-- Phase 24 D-07 flips this
            )
        else:
            outcome = AddRecipeOutcome(
                status="failure",
                failure_reason=task_input.failure_reason or "...",
            )
        # ... locate WorkflowRunStep + WorkflowRun, write outcome to run.outcome ...
        artifact = outcome.model_dump(mode="json")
        workflow_runner.on_step_complete(job.id, artifact, _session, _queue)
        return artifact
    except Exception as exc:
        workflow_runner.on_step_failed(job.id, _session, _queue, exc=exc)
        raise
    finally:
        _session.close()
```

### Pattern 2: Non-fatal-failure runner branch (NEW — D-01)

**What:** In the outer `except Exception as exc` block of `run_task` (`jobs.py:389-397`), check the step's `WorkflowStepDef.non_fatal_on_failure` flag. When True, call `workflow_runner._finalize_step_unavailable(step, reason, session, queue)` INSTEAD OF `_finalize_step_failure`. The helper writes a `StepUnavailableArtifact` to `step.artifact`, transitions the step DONE (not FAILED), and runs the DONE-path advancement (enqueue next step or mark WorkflowRun DONE).
**When to use:** Only on steps that opt in via `non_fatal_on_failure=True`. Default is False (strict), preserving v1.0 behavior.

**Conceptual shape (NEW code — planner writes):**

```python
# In src/robotina/queue/workflow_runner.py — NEW helper
def _finalize_step_unavailable(
    job_id: str,
    reason: str,
    session: Session,
    queue,
) -> None:
    """D-01: write StepUnavailableArtifact, advance through DONE path.

    Mirrors on_step_complete's artifact-write + advancement, but the
    artifact is a structured `unavailable` sentinel rather than the
    step's normal output. Reason is composed identically to
    _compose_failure_outcome (Pydantic-URL-noise strip + 150-char cap).
    """
    from robotina.queue.task_types import StepUnavailableArtifact
    from robotina.queue.models import WorkflowRunStep, WorkflowStepStatus

    step = session.query(WorkflowRunStep).filter(
        WorkflowRunStep.task_job_id == job_id
    ).first()
    if step is None:
        return

    artifact_obj = StepUnavailableArtifact(
        step_key=step.step_key,
        reason=_truncate_unavailable_reason(reason),  # 150-char cap
    )
    artifact = artifact_obj.model_dump(mode="json")
    step.artifact = artifact
    step.status = WorkflowStepStatus.DONE  # NOT FAILED — that's the whole point
    step.completed_at = datetime.now(timezone.utc)
    session.flush()
    # Reuse on_step_complete's advancement logic from here — extract into
    # a private _advance_after_step(step, session, queue) helper, called
    # by both on_step_complete AND _finalize_step_unavailable.
    _advance_after_step(step, session, queue)


# In run_task (jobs.py) — MODIFIED exception branch
except Exception as exc:
    # NEW dispatch: look up the step's WorkflowStepDef and check flag
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.models import WorkflowRunStep

    step = _session.query(WorkflowRunStep).filter(
        WorkflowRunStep.task_job_id == job.id
    ).first()
    is_non_fatal = False
    if step is not None:
        run = _session.query(WorkflowRun).filter(WorkflowRun.id == step.workflow_run_id).first()
        if run is not None:
            wf_def = WORKFLOW_REGISTRY.get(run.workflow_type)
            if wf_def is not None:
                step_def = next(
                    (s for s in wf_def.steps if s.step_key == step.step_key),
                    None,
                )
                if step_def is not None and step_def.non_fatal_on_failure:
                    is_non_fatal = True

    if is_non_fatal:
        reason = f"{type(exc).__name__}: {exc}"
        workflow_runner._finalize_step_unavailable(job.id, reason, _session, _queue)
    else:
        workflow_runner.on_step_failed(job.id, _session, _queue, exc=exc)
        if task_type == "handle-incoming-message":
            _write_invocation_terminal_status(_session, job, terminal="failed")
    raise  # re-raise so RQ moves the job to FailedJobRegistry
```

*The `_advance_after_step` helper extraction is the cleanest refactor of `on_step_complete` for reuse between the DONE path and the unavailable path; planner can name it differently if preferred.*

### Pattern 3: Tavily image search

**What:** Call `TavilyClient().search(query=..., include_images=True, ...)`. The response top-level `images` field is `list[str]` (image URLs only) when `include_images=True` and `include_image_descriptions=False`. Setting `include_image_descriptions=True` changes the shape to `list[{url, description}]` — NOT needed in v1.1 (top-result-only per D-11).
**Source:** [Tavily Python SDK Reference](https://docs.tavily.com/sdk/python/reference) (verified 2026-05-22).
**Example (NEW code — planner writes):**

```python
# src/robotina/agent/tools/tavily_image_search.py (NEW)
"""Tavily image search — plain function used by acquire_recipe_image (D-12).

No BaseTool wrapping in v1.1 — only the deterministic recipe-image task
calls this; no LLM agent uses it. Mirrors WebSearchTool's TAVILY_API_KEY
env var and TavilyClient lazy-import pattern.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def tavily_image_search(query: str, *, max_results: int = 5) -> list[str]:
    """Return a list of image URLs from Tavily image search.

    Args:
        query: Search query. v1.1 callers use f"{recipe.name} receta" (Spanish-language
               hint per Claude's discretion).
        max_results: Tavily max_results param. Default 5; only the top result is used
               in v1.1 (top-result-only per D-11).

    Raises:
        KeyError: If TAVILY_API_KEY env var not set.
        Exception: Any TavilyClient error propagates (caller — acquire_recipe_image —
               relies on non-fatal-failure flag to absorb it).
    """
    from tavily import TavilyClient
    api_key = os.environ["TAVILY_API_KEY"]
    client = TavilyClient(api_key=api_key)
    response = client.search(
        query=query,
        max_results=max_results,
        search_depth="basic",
        include_images=True,
        # include_image_descriptions=False — default; keeps response shape list[str]
    )
    images = response.get("images", []) or []
    logger.info("tavily-image-search | query=%r results=%d", query, len(images))
    # When include_image_descriptions=False, images is list[str] of URLs.
    # Defensive: if someone flips the flag later and the entries become dicts,
    # extract .url; otherwise pass through as strings.
    out: list[str] = []
    for entry in images:
        if isinstance(entry, str):
            out.append(entry)
        elif isinstance(entry, dict) and "url" in entry:
            out.append(entry["url"])
    return out
```

### Pattern 4: Recipe-scrapers `.image()` behavior

**What:** `AbstractScraper.image()` raises `NotImplementedError` by default ([VERIFIED: github.com/hhursev/recipe-scrapers `_abstract.py`](https://github.com/hhursev/recipe-scrapers/blob/main/recipe_scrapers/_abstract.py)). Per-site scrapers override it to return a URL string or raise. With `wild_mode=True` + the OpenGraph plugin, `image()` falls back to `<meta property="og:image">` on the page when the site-specific method is unimplemented or raises. **Practical contract for Phase 24:** wrap the call in `try/except` and treat both exceptions AND empty-string returns as "miss" (fall through to Tavily).

**Defensive call pattern:**

```python
try:
    raw_image = scraper.image()
    image_url = raw_image.strip() if raw_image else None
except Exception:
    image_url = None
```

### Anti-Patterns to Avoid

- **Anti-pattern 1: Swallow all exceptions on every step "in case it's transient."** D-01b: only `recipe-image` is non-fatal in v1.1. The runner flag is per-step policy; never broaden it without a new D-NN decision.
- **Anti-pattern 2: Add an LLM agent + prompt for `recipe-image` "to be consistent with other steps."** Memory `feedback_avoid_premature_abstraction` + D-02 — the task is mechanical; LLM is pure overhead. Vision-LLM lands in v1.2 as a deliberate v1.1 → v1.2 transition.
- **Anti-pattern 3: Use a helper to share `safe_fetch + scrape_html` between `FetchAndScrapeTool` and `acquire_recipe_image`.** Two call sites with mostly-the-same shape but different wrapping (BaseTool vs plain fn). D-06 + memory `feedback_avoid_premature_abstraction` — inline.
- **Anti-pattern 4: Validate image URL by downloading bytes + PIL magic-byte check.** D-11 + D-05 — we URL-pin; we don't redistribute; Content-Type sniff is the contract.
- **Anti-pattern 5: Multi-candidate retry on `safe_fetch` failure ("just try `images[1]`").** D-11 — top-result-only in v1.1. Retry is v1.2 if eval demands it.
- **Anti-pattern 6: Surface "guardé X, pero sin foto" in the wake reply.** D-08 — V007 stays unchanged; absence is structural data for the household UI.
- **Anti-pattern 7: Add an `image_url` column on a SQL table.** `RecipeData` is the artifact shape (JSON), not a SQLAlchemy model. No Alembic revision needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSRF/abuse defense on image URL | A custom IP allowlist or scheme check | `safe_fetch(url, expected_content_type="image/*", max_bytes=15_000_000)` | Six defenses already in place; wildcard sniff already supported (`safe_fetch.py:215-217`). |
| Tavily HTTP client | Custom `httpx` call to Tavily | `tavily.TavilyClient` | Same client used by `WebSearchTool`; auth + retry handled. |
| `og:image` fallback | Custom BeautifulSoup parse of `<meta property="og:image">` | `recipe_scrapers.scrape_html(html, wild_mode=True).image()` | Recipe-scrapers `wild_mode` includes the OpenGraph plugin which exactly does this. |
| Pydantic URL string validation | Custom regex | `pydantic.HttpUrl` if strict typing needed; v1.1 keeps `str` since the contract is "whatever passed safe_fetch is fine" | `safe_fetch` is the validation gate; double-validation adds noise. |
| Workflow non-fatal-failure semantics | Per-agent `try/except` swallowing | `WorkflowStepDef.non_fatal_on_failure=True` (D-01) | Runner-level policy is the single enforcement layer; agents stay strict and predictable. |
| LangWatch span emission for the deterministic task | Custom OTel spans | Wrap `acquire_recipe_image()` call in `with langwatch.trace(metadata={...}):` mirroring existing pattern | Project convention. |

**Key insight:** Phase 24 is mostly a *composition* phase — every primitive (safe_fetch, recipe-scrapers wild_mode, Tavily, RecipeData accumulator, finalize-outcome agent-less pattern, manual eval) already exists. The two genuinely new pieces are (a) the runner non-fatal-failure capability and (b) the Tavily image-search wrapper. Everything else is wiring.

## Runtime State Inventory

> Phase 24 is a forward-additive feature — no renames, no migrations, no string replacements. Most categories are N/A.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | **None.** `RecipeData.image_url` adds a new optional field on a JSON artifact shape. Existing `WorkflowRunStep.artifact` rows without it remain valid (Pydantic field has default `None`). | None — verified by `RecipeData` field-ownership doc + existing model evolution pattern from Phase 15 (`task_types.py:113-120`). |
| Live service config | **None.** No new agent registry entry; no `overrides/*.json` change (`recipe-image` is agent-less per D-02). | None — verified by memory `feedback_overrides_in_sync` N/A note in CONTEXT line 826. |
| OS-registered state | **None.** No new RQ queue, no new systemd unit, no new cron. | None. |
| Secrets / env vars | **None.** `TAVILY_API_KEY` already declared in `.env.example` (Phase 8); no new env var per memory `feedback_env_example` (CONTEXT line 829). | None. |
| Build artifacts / installed packages | **None.** No new package; no rename of an installed module. | None. |

**Backend coordination (NOT a Robotina-side runtime state item, but a precondition the planner must surface):** the household-manager `Recipe` entity POST body must accept `image_url: str | null`. If the backend rejects the field at smoke time, Phase 24's 24-05 / 24-09 are blocked (not by Robotina code, but by backend coordination). The smoke is the empirical gate (CONTEXT line 359-365).

## Common Pitfalls

### Pitfall 1: Tavily returns an empty `images` list (regional recipes)

**What goes wrong:** `tavily_image_search("milanesa criolla salteña receta")` returns `images=[]` for niche regional names.
**Why it happens:** Tavily indexes a finite slice of the public web; rare Spanish/Argentine/Uruguayan recipe names may have no indexed images.
**How to avoid:** `acquire_recipe_image` treats empty list as "miss" → raises → non-fatal flag converts to `StepUnavailableArtifact`. Operator-driven eval (D-09 / D-13) quantifies how often this fires; if >40% on the eval set, vision-LLM v1.2 escalates.
**Warning signs:** `24-IMG-EVAL-RESULTS-<backend>.md` shows empty `candidate URL` rows on multiple fixture entries; eval verdict trips the <60% gate.

### Pitfall 2: Tavily returns an irrelevant image (Pitfall 8 from research)

**What goes wrong:** `tavily_image_search("canelones de choclo receta")` returns the URL of a corn-on-the-cob photo (not the dish).
**Why it happens:** Tavily ranks by query relevance, not "is this the dish in the recipe." The "wrong dish" failure mode is the headline v1.1 risk.
**How to avoid (v1.1):** Source-page bypass (D-11) means URL-sourced recipes use the recipe author's chosen photo, which is highly trusted. For query-only recipes, top-result-only is accepted as the v1.1 stance; the manual eval quantifies. **No code-level mitigation in v1.1.**
**Warning signs:** Operator review of `24-IMG-EVAL-RESULTS-*.md` marks "image looks right? N" on >40% of Tavily-branch rows.

### Pitfall 3: `safe_fetch` blocks a perfectly-good image URL on a CDN that resolves to a private IP

**What goes wrong:** Some CDNs (rare) route through addresses that look private to `ipaddress.is_private`; legit image URL blocked.
**Why it happens:** `safe_fetch._is_blocked_ip` is strict by design (Phase 23 SSRF defense).
**How to avoid:** The non-fatal flag absorbs the error — image marked unavailable, recipe saves. Eval surfaces if specific source domains hit this; planner can document but NOT loosen `safe_fetch` defenses for v1.1.
**Warning signs:** Operator log triage shows `SafeFetchError("Host X resolved to blocked IP: ...")` for a known-public image domain.

### Pitfall 4: `safe_fetch` `image/*` wildcard regression

**What goes wrong:** A future `safe_fetch` refactor breaks the `image/*` prefix sniff; image URLs that legitimately serve `image/jpeg` are rejected.
**Why it happens:** The wildcard is implemented as a special case in `safe_fetch.py:215-217` (`accepted = ("image/",)` + prefix match at line 220). Refactor risk if someone "cleans up" the special case.
**How to avoid:** D-17 — explicit assertion test in `tests/url/test_safe_fetch.py` that `expected_content_type="image/*"` accepts `image/jpeg`, `image/png`, `image/webp` and rejects `text/html`, `application/pdf`.
**Warning signs:** Image step suddenly marks unavailable for previously-passing fixture URLs.

### Pitfall 5: `recipe_scrapers.scrape_html(html).image()` raises `NotImplementedError` on a site without OpenGraph

**What goes wrong:** Site-specific scraper doesn't override `image()`, AND no `og:image` meta tag, AND `wild_mode=True`'s OpenGraph plugin can't recover → `NotImplementedError`.
**Why it happens:** `AbstractScraper.image()` is `raise NotImplementedError` by default ([VERIFIED: github source]); the wild-mode chain doesn't guarantee a fallback for every site.
**How to avoid:** Wrap `scraper.image()` in `try/except Exception` (broad catch is appropriate — recipe-scrapers raises a mix of `NotImplementedError`, `SchemaOrgException`, and custom errors); treat any exception as "miss" → fall through to Tavily branch.
**Warning signs:** Eval rows where `expected_branch=source_page` end up firing Tavily branch unexpectedly; log inspection reveals exceptions.

### Pitfall 6: `accumulated_artifacts["recipe-image"]` is the unavailable artifact, not a RecipeData dump

**What goes wrong:** `recipe-load`'s `build_input` does `RecipeData(**artifacts["recipe-image"])` → fails because the unavailable artifact has shape `{status, step_key, reason}`, not `{name, ingredients, ...}`.
**Why it happens:** D-06b says "swap `artifacts["metadata"]` → `artifacts["recipe-image"]`" — but on the unavailable path the artifact shape differs.
**How to avoid:** `recipe-load`'s `build_input` must detect the unavailable shape and FALL BACK to `artifacts["metadata"]`. Pattern:

```python
build_input=lambda ctx, artifacts: RecipeLoadInput(
    recipe=RecipeData(**(
        artifacts["metadata"]
        if (artifacts.get("recipe-image", {}).get("status") == "unavailable")
        else artifacts["recipe-image"]
    )),
    reply_context=ReplyContext(**ctx["reply_context"]),
    household_id=ctx["household_id"],
),
```

Alternative: `acquire_recipe_image` ALWAYS emits a full RecipeData dump (with `image_url=None` on miss-but-no-exception); the unavailable artifact only happens when the deterministic function raises. In that case `recipe-load`'s build_input gets the unavailable artifact when the runner converts an exception. Either way the planner must explicitly handle this dispatch.
**Warning signs:** Test `test_unavailable_artifact_passes_through_recipe_load_build_input` (D-14) catches it; without that test, a `recipe-image` exception breaks the workflow at `recipe-load`'s input construction.

### Pitfall 7: Duplicate registry insertion drift between query and url variants

**What goes wrong:** Plan 24-05 adds `recipe-image` to `add-recipe-from-query` but forgets `add-recipe-from-url` (or vice versa).
**Why it happens:** Inline duplication (D-06) means two near-identical step lists. Easy to skip one.
**How to avoid:** D-19 — workflow registry test asserting BOTH variants have the `recipe-image` step with `non_fatal_on_failure=True`. Test is the load-bearing defense against drift.
**Warning signs:** `test_workflow_registry.py` fails after 24-05 lands.

### Pitfall 8: LangWatch trace doesn't appear in the dashboard for `recipe-image`

**What goes wrong:** The deterministic branch in `jobs.py:119` doesn't enter the `with langwatch.trace():` wrap at `jobs.py:359`; if Phase 24 doesn't explicitly add a trace, the step is invisible in LangWatch.
**Why it happens:** The existing `finalize-outcome` and `send-notification` branches return BEFORE the LLM branch's trace wrap.
**How to avoid:** D-02 explicitly calls out "the deterministic branch wraps the function call in an OTel span tagged `task_type='recipe-image'`". Planner must add `with langwatch.trace(metadata={...}):` (or equivalent OTel API) around the `acquire_recipe_image()` call in the `recipe-image` branch.
**Warning signs:** `24-IMG-EVAL-RESULTS-*.md` LangWatch trace URLs are empty/404 on the operator review.

## Code Examples

### Code Example 1: `recipe-image` branch in `run_task` (NEW — D-02)

```python
# src/robotina/queue/jobs.py — NEW branch, placed after the finalize-outcome branch
# (around line 167, before the LLM-config lookup at line 167).
#
# NOTE: This branch ALSO illustrates how the non-fatal-failure flag interacts.
# If acquire_recipe_image() raises, the OUTER except block (lines 389-397 with
# Phase 24's NEW dispatch — see Pattern 2) routes through _finalize_step_unavailable.

if task_type == "recipe-image":
    from robotina.agent.tasks.recipe_image import acquire_recipe_image
    try:
        # task_input is RecipeImageInput; .recipe is RecipeData with image_url=None
        try:
            import langwatch
            with langwatch.trace(metadata={"task_type": "recipe-image", "phase": 24}):
                output = acquire_recipe_image(task_input)
        except ImportError:
            output = acquire_recipe_image(task_input)

        artifact = output.model_dump(mode="json")
        workflow_runner.on_step_complete(job.id, artifact, _session, _queue)
        return artifact
    except Exception as exc:
        # Outer dispatch (Pattern 2) reads WorkflowStepDef.non_fatal_on_failure=True
        # and routes through _finalize_step_unavailable. Re-raise so RQ records
        # the job as failed (even though the step is DONE-unavailable).
        # NOTE: planner may choose to handle the dispatch inside this branch
        # rather than the outer except — see Pattern 2 for the recommended
        # placement.
        raise
    finally:
        _session.close()
```

### Code Example 2: `StepUnavailableArtifact` model (NEW — D-01 / D-03)

```python
# src/robotina/queue/task_types.py — add near AddRecipeOutcome (line 352)
class StepUnavailableArtifact(BaseModel):
    """Structured sentinel artifact written by _finalize_step_unavailable.

    Phase 24 / D-01: when a step with non_fatal_on_failure=True raises, the
    runner converts the exception into this artifact and routes through
    DONE-path advancement. Downstream consumers (recipe-load build_input,
    finalize-outcome) detect this shape by `status == "unavailable"` and
    fall back to the previous step's artifact / set image_present=False.
    """
    model_config = ConfigDict(extra="forbid")
    status: Literal["unavailable"] = "unavailable"
    step_key: str
    reason: str  # ≤ 150 chars; matches _OUTCOME_FAILURE_REASON_MAX_CHARS
```

### Code Example 3: `acquire_recipe_image` deterministic fallback ladder (NEW — D-11)

```python
# src/robotina/agent/tasks/recipe_image.py — NEW module
"""Deterministic recipe-image acquisition (Phase 24 / D-02 / D-11).

Mirrors the finalize-outcome deterministic pattern (no LLM agent). Owns the
fallback ladder:
  1. source-page (when RecipeData.source_url is set): safe_fetch source_url +
     recipe_scrapers.scrape_html(html, wild_mode=True).image()
  2. Tavily image search: tavily_image_search(f"{recipe.name} receta") → top result
  3. miss: raise (runner's non_fatal_on_failure flag converts to unavailable)

In both branches the candidate URL is validated through safe_fetch with
expected_content_type="image/*", max_bytes=15_000_000.
"""
from __future__ import annotations

import logging

from robotina.queue.task_types import RecipeImageInput, RecipeImageOutput, RecipeData

logger = logging.getLogger(__name__)


class RecipeImageAcquisitionError(Exception):
    """Raised when no image URL passed safe_fetch validation.

    Caught by run_task's outer except → routed through
    _finalize_step_unavailable when the step has non_fatal_on_failure=True.
    """


def acquire_recipe_image(input: RecipeImageInput) -> RecipeImageOutput:
    """Run the fallback ladder; return the recipe with image_url set (or raise).

    Raises:
        RecipeImageAcquisitionError: no candidate URL passed validation. The
            runner converts this to a StepUnavailableArtifact via the
            non_fatal_on_failure=True flag on the WorkflowStepDef.
        SafeFetchError: not caught here — let it propagate; the same non-fatal
            flag absorbs it.
    """
    from robotina.url.safe_fetch import safe_fetch, SafeFetchError

    recipe = input.recipe
    candidate_url: str | None = None

    # Branch 1: source-page (when URL-sourced).
    if recipe.source_url:
        try:
            html_fetched = safe_fetch(recipe.source_url, expected_content_type="text/html")
            html = html_fetched.content_bytes.decode("utf-8", errors="replace")
            from recipe_scrapers import scrape_html
            scraper = scrape_html(html, org_url=html_fetched.final_url, wild_mode=True)
            try:
                raw = scraper.image()
                candidate_url = raw.strip() if raw else None
            except Exception:
                candidate_url = None
            if candidate_url:
                logger.info(
                    "recipe-image source-page hit | recipe=%r url=%s",
                    recipe.name, candidate_url,
                )
        except SafeFetchError as exc:
            # Source-page fetch hit SSRF/abuse defense — explicit fall-through
            # to Tavily branch is documented behavior (CONTEXT D-15 edge case).
            logger.info(
                "recipe-image source-page fetch blocked, falling back to Tavily | reason=%s",
                exc,
            )
            candidate_url = None

    # Branch 2: Tavily image search (when source-page missed or no source_url).
    if not candidate_url:
        from robotina.agent.tools.tavily_image_search import tavily_image_search
        query = f"{recipe.name} receta"
        images = tavily_image_search(query, max_results=5)
        if images:
            candidate_url = images[0]
            logger.info(
                "recipe-image tavily hit | recipe=%r query=%r url=%s",
                recipe.name, query, candidate_url,
            )

    # No candidate at all.
    if not candidate_url:
        raise RecipeImageAcquisitionError(
            f"No image candidate for recipe={recipe.name!r}"
        )

    # Validation: image URL must pass safe_fetch with image/* content type.
    # safe_fetch raises SafeFetchError on any defense violation; let it
    # propagate (the runner's non_fatal_on_failure absorbs it).
    safe_fetch(candidate_url, expected_content_type="image/*", max_bytes=15_000_000)

    # Build the output RecipeData dump with image_url set.
    output_recipe = recipe.model_copy(update={"image_url": candidate_url})
    return RecipeImageOutput(**output_recipe.model_dump(mode="json"))
```

### Code Example 4: `WorkflowStepDef.non_fatal_on_failure` field (NEW — D-01)

```python
# src/robotina/agent/workflows.py:32 — MODIFY
class WorkflowStepDef(BaseModel):
    """Definition of a single step within a workflow."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    step_key: str
    task_type: str
    build_input: Callable[[dict, dict], object]
    # Phase 24 / D-01: when True and the step raises, the runner writes a
    # StepUnavailableArtifact and routes through DONE-path advancement
    # instead of FAILED-path cancellation. Default False preserves v1.0
    # behavior for every existing step. Only recipe-image opts in (D-01b).
    non_fatal_on_failure: bool = False
```

### Code Example 5: Workflow registry insertion (NEW — D-06 / D-06b)

```python
# src/robotina/agent/workflows.py:68 WORKFLOW_REGISTRY — modify BOTH entries
# (inline-duplicated per D-06; no helper)

# In add-recipe-from-query entry, between "metadata" and "load" steps:
WorkflowStepDef(
    step_key="recipe-image",
    task_type="recipe-image",
    build_input=lambda ctx, artifacts: RecipeImageInput(
        recipe=RecipeData(**artifacts["metadata"]),
        reply_context=ReplyContext(**ctx["reply_context"]),
        household_id=ctx["household_id"],
    ),
    non_fatal_on_failure=True,  # D-01b
),

# Then the "load" step's build_input changes (D-06b — key swap):
WorkflowStepDef(
    step_key="load",
    task_type="recipe-load",
    build_input=lambda ctx, artifacts: RecipeLoadInput(
        # On the unavailable path artifacts["recipe-image"] has
        # {status, step_key, reason} shape — fall back to metadata.
        recipe=RecipeData(**(
            artifacts["metadata"]
            if artifacts.get("recipe-image", {}).get("status") == "unavailable"
            else artifacts["recipe-image"]
        )),
        reply_context=ReplyContext(**ctx["reply_context"]),
        household_id=ctx["household_id"],
    ),
),

# IDENTICAL insertion + load-key swap in add-recipe-from-url entry.
# (Duplicated verbatim — D-06.)
```

### Code Example 6: `finalize-outcome` `image_present` derivation (NEW — D-07)

```python
# src/robotina/queue/jobs.py:119 — finalize-outcome branch MODIFIED

if task_type == "finalize-outcome":
    from robotina.queue.task_types import AddRecipeOutcome
    from robotina.queue.models import WorkflowRun, WorkflowRunStep, WorkflowStepStatus
    try:
        load = task_input.load or {}
        recipe_id = load.get("recipe_id") if isinstance(load, dict) else None

        # D-07: read recipe-image artifact from done steps via accumulated_artifacts.
        # FinalizeOutcomeInput needs extension to expose the artifact OR we
        # query the DB directly. Direct DB query is simpler — mirrors how the
        # branch already locates WorkflowRun via task_job_id.
        recipe_image_artifact = None
        step = (
            _session.query(WorkflowRunStep)
            .filter(WorkflowRunStep.task_job_id == job.id)
            .first()
        )
        if step is not None:
            sibling = (
                _session.query(WorkflowRunStep)
                .filter(
                    WorkflowRunStep.workflow_run_id == step.workflow_run_id,
                    WorkflowRunStep.step_key == "recipe-image",
                    WorkflowRunStep.status == WorkflowStepStatus.DONE,
                )
                .first()
            )
            if sibling is not None:
                recipe_image_artifact = sibling.artifact

        image_present = bool(
            recipe_image_artifact is not None
            and recipe_image_artifact.get("status") != "unavailable"
            and recipe_image_artifact.get("image_url")
        )

        if recipe_id:
            outcome = AddRecipeOutcome(
                status="success",
                recipe_id=recipe_id,
                recipe_name=load.get("recipe_name"),
                recipe_slug=load.get("recipe_slug") or None,
                image_present=image_present,  # D-07: flipped from hardcoded False
            )
        else:
            outcome = AddRecipeOutcome(
                status="failure",
                failure_reason=(task_input.failure_reason or "..."),
            )
        # ... rest unchanged (locate run, write outcome, advance) ...
```

**Alternative (cleaner):** extend `FinalizeOutcomeInput` to carry `recipe_image: dict | None = None` and have the workflow's build_input lambda pass it through:
```python
build_input=lambda ctx, artifacts: FinalizeOutcomeInput(
    metadata=artifacts.get("metadata"),
    load=artifacts.get("load"),
    recipe_image=artifacts.get("recipe-image"),
),
```
Planner decides — the DB-query form is slightly less coupled to the workflow registry; the input-extension form is cleaner. Recommendation: extend the input model (avoids a second query inside the deterministic branch).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-roll SSRF defense per URL caller | `safe_fetch` shared helper (Phase 23) | 2026-05-20 | Phase 24 reuses unchanged |
| Per-agent `try/except` swallowing | Runner-level `non_fatal_on_failure` flag | Phase 24 (NEW) | Single enforcement layer; agents stay strict |
| AI image generation fallback | URL pin (real images) | Research milestone 2026-05-18 | Cost + quality both favor real images |
| `langgraph.prebuilt.create_react_agent` | `langchain.agents.create_agent` | Phase 10 | N/A for recipe-image (agent-less) |
| Free-text LLM parse fallback ladder | `response_format=<Pydantic>` | Phase 11 | N/A for recipe-image (agent-less); applies if vision-LLM lands in v1.2 |
| `acknowledge-add-recipe` workflow tail step | `RespondTool` + `TerminateTool` | Phase 21 | Phase 24's wake-eval (D-08b) verifies V007's behavior on `image_present` variants |

**Deprecated / outdated:**
- `AGENT_REGISTRY` entry for `recipe-image` — NEVER add one in v1.1 (D-02 deterministic task). If vision-LLM v1.2 lands, the task converts to an LLM agent then; only at that point do `overrides/*.json` entries get added (memory `feedback_overrides_in_sync`).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Tavily `include_image_descriptions=False` (default) yields `images: list[str]` (URLs only). | Standard Stack §"Tavily" + Code Example 3 | [VERIFIED: docs.tavily.com/sdk/python/reference 2026-05-22 — explicit "If `include_image_descriptions` is set to True, each entry will be an `ImageResult`"]. Defensive code in `tavily_image_search` handles both shapes regardless. **Resolved → not actually an assumption.** |
| A2 | `recipe_scrapers.scrape_html(...).image()` raises `NotImplementedError` (or similar) on miss when no override is provided. | Pitfall 5 + Code Example 3 | [VERIFIED: GitHub `_abstract.py`]. Broad `except Exception` covers all known variants. |
| A3 | The household-manager backend's recipe POST schema accepts (or will accept) `image_url: str | null`. | D-05 / IMG-05 row | **[ASSUMED]** — CONTEXT line 359-365 explicitly notes this is a "known precondition" to verify via smoke. If backend rejects: Plan 24-05 is blocked on backend work. **Mitigation:** Plan 24-05 verification step pings the staging backend with a payload containing the field; flags as P0 blocker if rejected. |
| A4 | `safe_fetch` already supports the `image/*` wildcard correctly. | D-13, Code Example 3 | [VERIFIED: `src/robotina/url/safe_fetch.py:213-223` — `expected.startswith("image/")` → `accepted = ("image/",)` prefix-match]. D-17 enforces with a test. |
| A5 | `WorkflowStepDef.non_fatal_on_failure` being a per-step Pydantic field is enough — no migration needed because the model is in-memory only (not persisted). | D-01 + Code Example 4 | [VERIFIED: `WorkflowStepDef` is a Pydantic in-memory model in `src/robotina/agent/workflows.py`; not a SQLAlchemy entity. Adding a field with default `False` is backward-compatible.] |
| A6 | Existing `experiments/gather_from_url.py` pattern (load_dotenv → langwatch trace wrap → backend selection → per-row iteration) translates cleanly to `experiments/recipe_image.py`. | EXP-03 design | [VERIFIED: `experiments/gather_from_url.py:1-80` read]. The recipe-image script is simpler (no LLM agent — direct function call) but shares the LangWatch instrumentation pattern. |
| A7 | The `WorkflowOutcomeSummary.outcome` field already carries `image_present` (since the AddRecipeOutcome schema already has the field at `task_types.py:370`). | Wake-eval (D-10) wiring | [VERIFIED: `task_types.py:370`]. Existing wake summaries serialize the field as `False`. Phase 24 flips the producer; the consumer side is already wired. |
| A8 | The `tavily_image_search` query `f"{recipe.name} receta"` produces meaningful results for Spanish recipe names. | D-11, Code Example 3 | **[ASSUMED]** — exact relevance percentage unknown. **This is the explicit Phase 24 manual-eval gate.** If <60%, vision-LLM v1.2 escalates. |
| A9 | Adding LangWatch trace wrap inside the `recipe-image` deterministic branch is straightforward — same `langwatch.trace()` API used elsewhere in `run_task`. | D-02, Pitfall 8 | [VERIFIED: `jobs.py:356-368` uses `langwatch.trace()` + `ImportError` fallback]. Phase 24 mirrors. |

**Decisions that need user confirmation before execution (A3 only):**
- **A3 — backend `image_url` field acceptance.** Suggest pre-flight check during Plan 24-02 (or earlier): POST a test payload to the staging household-manager API with `image_url` present and confirm 2xx. If rejected, backend coordination becomes a P0 blocker before Plan 24-05 lands.

All other claims are verified or empirical-gate (A8).

## Open Questions

1. **Should `FinalizeOutcomeInput` be extended to carry the recipe-image artifact, or should `finalize-outcome` query the DB?**
   - **What we know:** Current `FinalizeOutcomeInput` has `metadata: dict | None` and `load: dict | None`. The clean parallel is to add `recipe_image: dict | None = None`.
   - **What's unclear:** Which is more aligned with the project's current conventions? Both work.
   - **Recommendation:** Extend the input model (planner final). One-line schema addition; the workflow registry's build_input lambda already has the same artifact shape pattern.

2. **Where does `acquire_recipe_image` live — `src/robotina/agent/tasks/` (NEW package) or inline in `src/robotina/queue/jobs.py`?**
   - **What we know:** CONTEXT D-02 says "new module `src/robotina/agent/tasks/recipe_image.py`". The `tasks/` directory does not exist yet.
   - **What's unclear:** Naming consistency — should it be `agent/tasks/` or `agent/deterministic/` or `queue/tasks/`?
   - **Recommendation:** `src/robotina/agent/tasks/recipe_image.py` per CONTEXT D-02 (planner final). Creates a new package that future deterministic agent-less logic can join (the `finalize-outcome` composer could migrate there later, but that's out of scope).

3. **Does the planner introduce a small `_advance_after_step(step, session, queue)` helper in `workflow_runner.py` for reuse between `on_step_complete` and `_finalize_step_unavailable`?**
   - **What we know:** Both code paths need to (a) build accumulated_artifacts, (b) find next PENDING step, (c) enqueue OR mark WorkflowRun DONE. Inlining duplicates ~30 lines.
   - **Recommendation:** Yes — small private helper avoids duplication of non-trivial advancement logic. Memory `feedback_avoid_premature_abstraction` is about user-visible abstractions, not internal helper functions inside a single module.

4. **Does plan 24-01 need an `_advance_after_step` refactor first, before the unavailable helper exists?**
   - **Recommendation:** Yes — Plan 24-01 does (i) refactor `on_step_complete` to call `_advance_after_step`, (ii) add `WorkflowStepDef.non_fatal_on_failure`, (iii) add `StepUnavailableArtifact` model, (iv) add `_finalize_step_unavailable`, (v) modify `run_task` exception dispatch. All shipped in one plan with comprehensive tests (D-14). Standalone, before `recipe-image` exists.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `tavily-python` | `tavily_image_search` | ✓ | `>=0.3` | — |
| `recipe-scrapers` | `acquire_recipe_image` source-page branch | ✓ | `>=15.11.0` | — |
| `httpx` | `safe_fetch` transport | ✓ | `>=0.27` | — |
| `pydantic` | New models | ✓ | `>=2.7` | — |
| `langwatch` | Trace wrap | ✓ | `>=0.1` | `ImportError` fallback (existing pattern in `jobs.py:369`) |
| `TAVILY_API_KEY` env var | Tavily search | ✓ | declared in `.env.example` (Phase 8) | None — fail loud (KeyError) is the contract |
| `URL_INGESTION_ALLOW_HTTP` env var | `safe_fetch` (image URL validation) | ✓ | declared `.env.example` (Phase 23) | Default `false` (https-only) for production |
| household-manager API recipe POST accepting `image_url` field | `recipe-load` | **? (assumed)** | — | Smoke-time verification (Plan 24-05); blocks if backend rejects |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** household-manager backend `image_url` acceptance — **must be verified at smoke time**, not at code-write time. Planner flags as Plan 24-05's first verification step.

## Validation Architecture

> `.planning/config.json` does not explicitly set `workflow.nyquist_validation: false`. Treating as enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` + `pytest-asyncio` (declared `pyproject.toml:68-70`) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/queue/test_workflow_runner_non_fatal.py tests/agent/tasks/test_recipe_image.py -x -q` (Phase 24 fast lane) |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| IMG-01 | `recipe-image` step appears in both workflow variants | unit (registry assertion) | `uv run pytest tests/queue/test_workflow_registry.py::test_recipe_image_step_present_in_both_variants -x` | ❌ Wave 0 (extends existing `test_workflow_registry.py`) |
| IMG-02 | Fallback ladder: source-page → Tavily → miss | unit | `uv run pytest tests/agent/tasks/test_recipe_image.py -x` | ❌ Wave 0 |
| IMG-03 | Non-fatal: failed step DONE-unavailable, recipe still saves | integration | `uv run pytest tests/queue/test_workflow_runner_non_fatal.py -x` | ❌ Wave 0 |
| IMG-04 | `safe_fetch` validates image URL with `image/*` | unit | `uv run pytest tests/url/test_safe_fetch.py::test_image_wildcard_accepts_jpeg_png_webp -x` | ❌ Wave 0 (extends existing) |
| IMG-05 | `image_url` flows into household-manager POST | manual smoke | (operator runs end-to-end on staging) | n/a (manual gate) |
| IMG-06 | Runner respects `non_fatal_on_failure` flag | integration | `uv run pytest tests/queue/test_workflow_runner_non_fatal.py::test_strict_step_still_fails_workflow -x` | ❌ Wave 0 |
| EXP-01 | Existing experiments still run | smoke | `uv run experiments.recipe_research --help` (and similar) | ✓ (existing scripts unchanged) |
| EXP-03 | `experiments.recipe_image` exists + runs against fixture set | manual smoke | `uv run experiments.recipe_image --backend ollama` | ❌ Wave 0 |
| EXP-04 | `experiments.robotina_wake` exercises V007 across `image_present` variants | manual smoke | `uv run experiments.robotina_wake --backend ollama` | ❌ Wave 0 |
| EXP-06 | `pyproject.toml` + CLAUDE.md updated | grep | `grep -q "experiments.recipe_image" pyproject.toml` | ❌ Wave 0 (edits to existing files) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/queue/test_workflow_runner_non_fatal.py tests/agent/tasks/test_recipe_image.py tests/agent/tools/test_tavily_image_search.py tests/url/test_safe_fetch.py tests/queue/test_finalize_outcome.py -x -q` (Phase 24's load-bearing test set)
- **Per wave merge:** `uv run pytest tests/ -q` (full regression — confirms Phase 24's changes don't break existing tests)
- **Phase gate:** Full suite green AND operator smoke verdict `pass` in `24-SMOKE.md` before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/queue/test_workflow_runner_non_fatal.py` — covers D-14 (non-fatal runner integration)
- [ ] `tests/agent/tasks/__init__.py` + `tests/agent/tasks/test_recipe_image.py` — covers D-15 (`acquire_recipe_image` units)
- [ ] `tests/agent/tools/test_tavily_image_search.py` — covers D-16 (Tavily tool)
- [ ] `tests/url/test_safe_fetch.py` extension — covers D-17 (`image/*` wildcard assertion)
- [ ] `tests/queue/test_finalize_outcome.py` extension — covers D-18 (`image_present` derivation, includes the absent-artifact and unavailable-artifact cases)
- [ ] `tests/queue/test_workflow_registry.py` extension — covers D-19 (both variants have `recipe-image` with `non_fatal_on_failure=True`)
- [ ] Framework already installed — no install step needed.

## Security Domain

> `security_enforcement` is enabled (no explicit `false` in config).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes (`TAVILY_API_KEY` env var) | `os.environ["TAVILY_API_KEY"]` bracket read — fail loud on missing (mirrors `WebSearchTool` pattern); never log the key |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a (server-to-server flow) |
| V5 Input Validation | yes | `RecipeImageInput` uses `ConfigDict(extra="forbid")`; `safe_fetch` validates the URL string before any HTTP I/O; `RecipeData.image_url: str | None` carries the validated URL |
| V6 Cryptography | no (TLS via httpx default) | `safe_fetch` requires HTTPS unless `URL_INGESTION_ALLOW_HTTP=true` (dev/testing only) |
| V10 Malicious Code | yes (image URL is third-party) | URL pin (D-05) means we never execute or even decode the image bytes; the household UI's browser does that with browser-level sandboxing |
| V12 Files & Resources | yes (image fetch could be a DoS vector) | `safe_fetch` 15 MB cap (`max_bytes=15_000_000`); 20:1 gzip ratio cap; connect/read timeout |
| V14 Configuration | yes | `TAVILY_API_KEY` documented in `.env.example`; no new env var in Phase 24 |

### Known Threat Patterns for {Python + Tavily + recipe-scrapers + httpx + safe_fetch}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Tavily returns image URL pointing at RFC1918 / loopback / link-local IP | Spoofing/Tampering | `safe_fetch._is_blocked_ip` rejects ([VERIFIED: `safe_fetch.py:42-65`]) — accepted v1.1 risk: in dev (`HOUSEHOLD_ID="dev-os"`), local-image-host URLs would fire the defense; intentional. |
| Source-page HTML containing prompt-injection text | Information disclosure | n/a — `recipe-image` is agent-less, no LLM in v1.1; injection vector is closed by D-02. (If vision-LLM v1.2 lands, this becomes a real threat.) |
| Tavily image URL pointing at a multi-GB file (DoS) | Denial of Service | `safe_fetch` 15 MB cap + Content-Length pre-check + gzip-bomb defense |
| Image URL is `data:` URI (XSS / smuggling) | XSS | `safe_fetch._check_scheme` rejects (only https / http-with-flag) |
| Image URL points at an attacker-controlled server tracking the household UI's GET (privacy leak) | Information disclosure | Accepted — URL pin means the household browser fetches the image; no Robotina-side mitigation possible without rehosting. Documented v1.2 follow-up. |
| Tavily key compromised + cost run-up | Spoofing/Repudiation | Key rotation is the standard control; rate-limit on Tavily side bounds blast radius |
| Source-page redirect chain to an internal IP | SSRF | `safe_fetch` manual redirect handling with per-hop re-validation ([VERIFIED: `safe_fetch.py:176-186`]) |
| Source page returns `Content-Type: text/html` but malformed UTF-8 | Information disclosure | `bytes.decode("utf-8", errors="replace")` (pattern from `FetchAndScrapeTool._run`) |
| Image URL with credentials in query string | Information disclosure | `safe_fetch` INFO log strips query string ([VERIFIED: `safe_fetch.py:229-233`]); the URL persists in the household-manager DB with credentials intact — operator risk, accepted |
| recipe-scrapers raises an uncaught exception breaking the workflow | Denial of Service | `try/except Exception` around `scraper.image()` in `acquire_recipe_image` (Pitfall 5); plus the runner's non-fatal flag absorbs the whole step |

## Sources

### Primary (HIGH confidence)
- `src/robotina/queue/task_types.py` (read 2026-05-22) — current `RecipeData`, `AddRecipeOutcome`, `WorkflowOutcomeSummary`, `WakeInvocationInput` shapes
- `src/robotina/queue/jobs.py` (read 2026-05-22) — current `run_task` flow including `send-notification` (line 90) and `finalize-outcome` (line 119) deterministic branches; `recipe-image` will mirror
- `src/robotina/queue/workflow_runner.py` (read 2026-05-22) — current `on_step_complete`, `on_step_failed`, `_check_and_dispatch_wake`, `_compose_failure_outcome`; Phase 24 extends with `_finalize_step_unavailable`
- `src/robotina/agent/workflows.py` (read 2026-05-22) — `WorkflowStepDef`, `WorkflowDefinition`, both `WORKFLOW_REGISTRY` entries with the inline-duplicated tails
- `src/robotina/url/safe_fetch.py` (read 2026-05-22) — six SSRF defenses + `image/*` wildcard support at line 215-223; Phase 24 reuses unchanged
- `src/robotina/agent/tools/web_search.py` (read 2026-05-22) — Tavily SDK wiring pattern that `tavily_image_search` mirrors
- `src/robotina/agent/tools/fetch_and_scrape.py` (read 2026-05-22) — `recipe_scrapers.scrape_html(..., wild_mode=True)` + per-field try/except pattern
- `.planning/phases/24-recipe-images-topic-3/24-CONTEXT.md` (read 2026-05-22) — user decisions D-01..D-21
- `.planning/REQUIREMENTS.md` (read 2026-05-22) — IMG-01..IMG-06, EXP-01, EXP-03, EXP-04, EXP-06
- `.planning/ROADMAP.md` Phase 24 section (read 2026-05-22) — 5 success criteria + depends-on
- `.planning/phases/23-url-ingestion-topic-2/23-{01,02,03,04}-SUMMARY.md` (read 2026-05-22) — `safe_fetch`, workflow registry, FetchAndScrapeTool, gather-from-url patterns Phase 24 inherits
- `.planning/phases/22-multi-recipe-per-message-topic-1/22-01-SUMMARY.md` (read 2026-05-22) — wake-helper ordering + recipe_query/recipe_url fallback Phase 24 doesn't modify
- `pyproject.toml` (read 2026-05-22) — confirms `tavily-python>=0.3`, `recipe-scrapers>=15.11.0`, `httpx>=0.27` all in place
- `.env.example` (read 2026-05-22) — `TAVILY_API_KEY` already present; no new env vars
- `src/robotina/dashboard/templates/_macros.html` (read 2026-05-22) — existing TASK_TYPE_LABELS map; Phase 24 appends `"recipe-image": "Imagen"`
- [Tavily Python SDK Reference](https://docs.tavily.com/sdk/python/reference) (fetched 2026-05-22) — `include_images=True` response shape verification
- [recipe-scrapers `_abstract.py`](https://github.com/hhursev/recipe-scrapers/blob/main/recipe_scrapers/_abstract.py) (fetched 2026-05-22) — `image()` base class signature
- `.planning/research/SUMMARY.md` (read 2026-05-22, header only) — milestone-level summary of Phase 24's place

### Secondary (MEDIUM confidence)
- [Tavily docs main](https://docs.tavily.com/) (fetched 2026-05-22) — corroborates parameter naming
- [recipe-scrapers getting started](https://docs.recipe-scrapers.com/) (fetched 2026-05-22) — corroborates that `image()` returns "URL to the main image"; doesn't specify miss behavior (covered by direct GitHub source above)
- [Tavily PyPI page](https://pypi.org/project/tavily-python/0.5.3/) (fetched 2026-05-22) — version corroboration

### Tertiary (LOW confidence — flagged for validation by manual eval)
- Tavily image-search relevance percentage on Spanish/Argentine regional recipe names — **this IS the Phase 24 manual-eval gate per D-09/D-11**; no source can resolve it pre-execution.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every package already declared in `pyproject.toml`; verified file paths and versions.
- Architecture: HIGH — every primitive (safe_fetch, finalize-outcome agent-less pattern, RecipeData accumulator, WorkflowStepDef Pydantic model, manual-eval pattern) exists in the codebase and is read verbatim above.
- Pitfalls: HIGH on the runner / artifact-shape pitfalls (6, 7, 8) — direct reading of code. MEDIUM on Tavily quality pitfalls (1, 2) — empirical and eval-driven by design.
- New code shapes (`_finalize_step_unavailable`, `acquire_recipe_image`, `tavily_image_search`): HIGH — fully grounded in existing patterns; the code examples are consumable starting points for the planner.

**Research date:** 2026-05-22
**Valid until:** ~ 2026-06-22 (30 days for stable stack with no announced breaking releases for Tavily or recipe-scrapers; sooner if Phase 24 eval surfaces quality issues that change the storage strategy).
