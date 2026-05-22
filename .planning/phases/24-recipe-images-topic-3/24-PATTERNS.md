# Phase 24: Recipe images (Topic 3) — Pattern Map

**Mapped:** 2026-05-22
**Files analyzed:** 17 new/modified targets
**Analogs found:** 16 / 17 (one no-analog: `StepUnavailableArtifact` is sibling-of-`AddRecipeOutcome`)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/robotina/queue/task_types.py` (extend — `RecipeData.image_url`, `RecipeImageInput`, `RecipeImageOutput`, `StepUnavailableArtifact`) | model | typed-contract | `task_types.py:105` `RecipeData` + `task_types.py:238` `RecipeResearchInstructionsInput` + `task_types.py:352` `AddRecipeOutcome` | exact (existing module — append in place) |
| `src/robotina/agent/workflows.py` (extend — `WorkflowStepDef.non_fatal_on_failure`; `recipe-image` step + `load` key-swap in both registry entries) | workflow-registry | typed-contract | `workflows.py:32` `WorkflowStepDef`; `workflows.py:68` `WORKFLOW_REGISTRY` (the inline-duplicated tails Phase 23 D-01 set up) | exact |
| `src/robotina/queue/workflow_runner.py` (extend — `_finalize_step_unavailable`, exception dispatch, optional `_advance_after_step` refactor) | runner-capability | event-driven (lifecycle) | `workflow_runner.py:608` `on_step_failed` + `workflow_runner.py:462` `on_step_complete` + `workflow_runner.py:52` `_compose_failure_outcome` | exact |
| `src/robotina/queue/jobs.py` (extend — `recipe-image` deterministic branch; `finalize-outcome` `image_present` flip; outer non-fatal exception dispatch) | task-dispatch | request-response | `jobs.py:119` `finalize-outcome` deterministic branch; `jobs.py:90` `send-notification` branch | exact |
| `src/robotina/agent/tasks/recipe_image.py` (NEW module — `acquire_recipe_image`) | deterministic-task | transform | `FetchAndScrapeTool._run` (`src/robotina/agent/tools/fetch_and_scrape.py:100-179`) for the safe_fetch + `recipe_scrapers.scrape_html(..., wild_mode=True)` shape; `jobs.py:119` for the agent-less-task convention | role-match (no prior `agent/tasks/` package exists; closest analog is the deterministic-branch body and `FetchAndScrapeTool` internals) |
| `src/robotina/agent/tasks/__init__.py` (NEW package marker) | package-init | n/a | `src/robotina/agent/tools/__init__.py` | exact |
| `src/robotina/agent/tools/tavily_image_search.py` (NEW) | tool-wrapper | request-response | `src/robotina/agent/tools/web_search.py` (`WebSearchTool`) | exact |
| `src/robotina/url/safe_fetch.py` (verify/assert `image/*` wildcard at lines 213-223; no code change expected) | utility | request-response | `safe_fetch.py:210-226` (existing wildcard sniff) | exact (already implemented) |
| `src/robotina/dashboard/templates/_macros.html` (extend — add `"recipe-image": "Imagen"` to `TASK_TYPE_LABELS`) | dashboard-label | render | `_macros.html:13-23` existing `TASK_TYPE_LABELS` dict (Phase 21 D-11) | exact |
| `experiments/recipe_image.py` (NEW) | experiment-script | batch | `experiments/gather_from_url.py` | exact (richest existing experiment template — load_dotenv → langwatch → per-row iteration → markdown emit with verdict frontmatter) |
| `experiments/robotina_wake.py` (NEW) | experiment-script | batch | `experiments/gather_from_url.py` (CLI + LangWatch); `workflow_runner.py:150-301` `_check_and_dispatch_wake` (for the synthetic `WakeInvocationInput` construction) | role-match |
| `pyproject.toml` (extend `[project.scripts]` — two entries) | config | n/a | `pyproject.toml:44-48` existing `experiments.*` entries | exact |
| `CLAUDE.md` (extend experiment table) | docs | n/a | existing CLAUDE.md table (referenced by EXP-06) | exact |
| `.planning/phases/24-recipe-images-topic-3/24-IMG-EVAL-SET.md` (NEW) | eval-fixture | docs | `.planning/phases/23-url-ingestion-topic-2/23-EVAL-SET.md` | exact |
| `tests/queue/test_workflow_runner_non_fatal.py` (NEW) | test | unit + integration | existing tests under `tests/queue/` testing `workflow_runner` | role-match |
| `tests/agent/tasks/test_recipe_image.py` (NEW) | test | unit | existing `tests/agent/tools/test_fetch_and_scrape.py`-style mock-driven units | role-match |
| `tests/agent/tools/test_tavily_image_search.py` (NEW) | test | unit | existing `tests/agent/tools/` tests around `WebSearchTool` | role-match |

## Pattern Assignments

### `src/robotina/queue/task_types.py` extensions (D-03, D-04, D-01 model)

**Analog:** `src/robotina/queue/task_types.py` itself — append the new models alongside the existing `RecipeData` (line 105), `AddRecipeOutcome` (line 352), `FinalizeOutcomeInput` (line 441).

**`RecipeData.image_url` addition pattern** — mirror the existing accumulator-field ownership doc-block style at `task_types.py:113-120`:

```python
# task_types.py:105-135 (existing — add image_url and update ownership docs)
class RecipeData(BaseModel):
    """Shared accumulating artifact across the recipe-research pipeline.
    ...
    Field ownership (per pipeline step):
    - gather:        ``gathered_sources``
    - instructions:  ``name``, ``description``, ``steps``
    - ingredients:   ``ingredients``, ``missing_ingredients``
    - metadata:      ``servings_qty``, ``servings_unit``, ``prep_time``,
                     ``cook_time``, ``total_time``, ``source_url``; clears
                     ``gathered_sources`` to ``None`` on emit.
    - recipe-image:  ``image_url`` (Phase 24 D-04)        # NEW LINE
    Other fields must be preserved verbatim from the incoming artifact.
    """
    name: str
    # ... existing fields preserved verbatim ...
    image_url: str | None = None      # NEW (Phase 24 / D-04); owned by recipe-image step
    ingredients: list[RecipeIngredient] = []
    # ...
```

**`RecipeImageInput` shape** — copy the existing `RecipeResearchInstructionsInput` block (`task_types.py:238-250`) verbatim, retitle, and drop the `to_user_message` (no LLM consumes this input):

```python
# Per Phase 15 accumulator convention; mirrors RecipeResearchInstructionsInput
class RecipeImageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipe: RecipeData
    reply_context: ReplyContext
    household_id: NonEmptyHouseholdId
    # No to_user_message — deterministic agent-less task; not consumed by an LLM.
```

**`RecipeImageOutput` shape** — per CONTEXT D-03: identical to RecipeData with image_url set. Two valid encodings; planner picks one:
- Option A (CONTEXT D-03 explicit fields): inline all RecipeData fields on the new model (heavy duplication but matches D-03 verbatim).
- Option B (sentinel alias, mirrors Phase 15 pattern at `task_types.py:283-288`): `RecipeImageOutput = RecipeData` — same shape, zero duplication. **Recommend Option B** — matches `RecipeResearchInstructionsOutput = RecipeData` sentinel-alias convention.

**`StepUnavailableArtifact` shape** — sibling of `AddRecipeOutcome` (`task_types.py:352`). Copy its `model_config = ConfigDict(extra="forbid")` + `Literal` discriminator style verbatim:

```python
# Place near AddRecipeOutcome (~line 352). New model; no existing exact analog.
class StepUnavailableArtifact(BaseModel):
    """Phase 24 / D-01 — structured 'unavailable' sentinel artifact.

    Written by workflow_runner._finalize_step_unavailable when a step with
    WorkflowStepDef.non_fatal_on_failure=True raises. Routed through the
    DONE-path advancement (not FAILED-path cancellation).
    """
    model_config = ConfigDict(extra="forbid")
    status: Literal["unavailable"] = "unavailable"
    step_key: str
    reason: str  # ≤ 150 chars; truncated by _finalize_step_unavailable using the
                 # same Pydantic-URL-noise strip + collapse logic as
                 # workflow_runner._compose_failure_outcome (line 52)
```

---

### `src/robotina/agent/workflows.py` extensions (D-01, D-06, D-06b)

**Analog:** `workflows.py:32-47` (`WorkflowStepDef`), `workflows.py:68-209` (existing `WORKFLOW_REGISTRY` with inline-duplicated tails Phase 23 D-01 set up).

**`WorkflowStepDef.non_fatal_on_failure` addition** — add as the 4th field on the existing Pydantic model:

```python
# workflows.py:32-47 — MODIFY in place
class WorkflowStepDef(BaseModel):
    """Definition of a single step within a workflow.

    Fields:
        step_key: Unique identifier within this workflow ...
        task_type: RQ task type string ...
        build_input: Callable(shared_context, accumulated_artifacts) -> Pydantic input model.
        non_fatal_on_failure: When True, exceptions from this step are
            converted to a StepUnavailableArtifact via
            workflow_runner._finalize_step_unavailable and the workflow
            continues. Default False preserves v1.0 strict semantics.
            Only recipe-image opts in (Phase 24 / D-01b).
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    step_key: str
    task_type: str
    build_input: Callable[[dict, dict], object]
    non_fatal_on_failure: bool = False     # NEW (Phase 24 / D-01)
```

**Workflow registry insertion** — duplicate the same WorkflowStepDef literal verbatim into BOTH `WORKFLOW_REGISTRY["add-recipe-from-query"]` (`workflows.py:75-139`) and `WORKFLOW_REGISTRY["add-recipe-from-url"]` (`workflows.py:148-208`) between the existing `metadata` (line 106 / line 181) and `load` (line 115 / line 190) entries. Pattern to copy — the existing `metadata`→`load` pair:

```python
# workflows.py:106-124 — EXISTING add-recipe-from-query metadata → load pair
WorkflowStepDef(
    step_key="metadata",
    task_type="recipe-research-metadata",
    build_input=lambda ctx, artifacts: RecipeResearchMetadataInput(
        recipe=RecipeData(**artifacts["ingredients"]),
        reply_context=ReplyContext(**ctx["reply_context"]),
        household_id=ctx["household_id"],
    ),
),
WorkflowStepDef(
    step_key="load",
    task_type="recipe-load",
    # Phase 15: artifacts["metadata"] IS the RecipeData dump (no "recipe" wrapper).
    build_input=lambda ctx, artifacts: RecipeLoadInput(
        recipe=RecipeData(**artifacts["metadata"]),
        ...
    ),
),
```

**Insert recipe-image between them; swap `load`'s artifact key (D-06b):**

```python
# NEW — drop in after "metadata", before "load" — in BOTH registry entries
WorkflowStepDef(
    step_key="recipe-image",
    task_type="recipe-image",
    build_input=lambda ctx, artifacts: RecipeImageInput(
        recipe=RecipeData(**artifacts["metadata"]),
        reply_context=ReplyContext(**ctx["reply_context"]),
        household_id=ctx["household_id"],
    ),
    non_fatal_on_failure=True,    # D-01b
),
# MODIFY existing "load" build_input — key swap from "metadata" to "recipe-image"
# with the StepUnavailableArtifact fall-through (Pitfall 6 in RESEARCH.md):
WorkflowStepDef(
    step_key="load",
    task_type="recipe-load",
    build_input=lambda ctx, artifacts: RecipeLoadInput(
        recipe=RecipeData(**(
            artifacts["metadata"]
            if artifacts.get("recipe-image", {}).get("status") == "unavailable"
            else artifacts["recipe-image"]
        )),
        reply_context=ReplyContext(**ctx["reply_context"]),
        household_id=ctx["household_id"],
    ),
),
```

Also add the missing import at `workflows.py:19-29` for the new `RecipeImageInput`.

---

### `src/robotina/queue/workflow_runner.py` extensions (D-01)

**Analog (primary):** `workflow_runner.py:52-79` (`_compose_failure_outcome` — copy the reason-truncation logic) + `workflow_runner.py:462-606` (`on_step_complete` — extract the post-step advancement block into `_advance_after_step`) + `workflow_runner.py:608-775` (`on_step_failed` — opposite-polarity sibling of the new `_finalize_step_unavailable`).

**Reason-truncation pattern to reuse (`workflow_runner.py:52-79`):**

```python
# workflow_runner.py:46-79 — EXISTING; reuse via shared helper
_PYDANTIC_URL_NOISE_RE = _re.compile(
    r"\s*For further information visit https?://\S+", _re.IGNORECASE
)
_OUTCOME_FAILURE_REASON_MAX_CHARS = 150

def _compose_failure_outcome(step) -> dict:
    ...
    raw = (step.failure_reason or "").strip()
    raw = _PYDANTIC_URL_NOISE_RE.sub("", raw)
    raw = _re.sub(r"\s+", " ", raw).strip()
    if raw:
        if len(raw) > _OUTCOME_FAILURE_REASON_MAX_CHARS:
            short = raw[:_OUTCOME_FAILURE_REASON_MAX_CHARS].rstrip() + "…"
        else:
            short = raw
        reason = f"{step.step_key}: {short}"
    ...
```

Extract a `_truncate_reason(raw: str) -> str` helper alongside `_compose_failure_outcome` and call it from BOTH (`_compose_failure_outcome` and the new `_finalize_step_unavailable`).

**Advancement-block extraction pattern** — `on_step_complete` lines 530-605 contain (a) artifact write, (b) accumulated_artifacts build, (c) next-step lookup + enqueue OR WorkflowRun DONE. Lines 547-605 are the reusable block:

```python
# workflow_runner.py:547-605 — EXTRACT into _advance_after_step(step, session, queue)
# Both on_step_complete (DONE path) AND _finalize_step_unavailable (unavailable path)
# call this helper after the step's artifact has been written and status set.

done_steps = (
    session.query(WorkflowRunStep).filter(
        WorkflowRunStep.workflow_run_id == step.workflow_run_id,
        WorkflowRunStep.status == WorkflowStepStatus.DONE,
    ).all()
)
accumulated_artifacts: dict[str, dict] = {s.step_key: s.artifact for s in done_steps}

run = session.query(WorkflowRun).filter(WorkflowRun.id == step.workflow_run_id).first()
next_step = (
    session.query(WorkflowRunStep).filter(
        WorkflowRunStep.workflow_run_id == step.workflow_run_id,
        WorkflowRunStep.status == WorkflowStepStatus.PENDING,
    ).order_by(WorkflowRunStep.step_order).first()
)

if next_step is not None:
    workflow_def = WORKFLOW_REGISTRY[run.workflow_type]
    next_step_def = next(s for s in workflow_def.steps if s.step_key == next_step.step_key)
    next_job_id = str(uuid.uuid4())
    task_input = next_step_def.build_input(dict(run.shared_context), accumulated_artifacts)
    if hasattr(task_input, "model_dump"):
        next_step.step_input = task_input.model_dump(mode="json")
    else:
        next_step.step_input = task_input
    queue.enqueue(
        "robotina.queue.jobs.run_task",
        task_input,
        job_id=next_job_id,
        meta={"task_type": next_step.task_type, "queue_name": queue.name},
        result_ttl=-1,
        failure_ttl=-1,
    )
    next_step.task_job_id = next_job_id
    session.commit()
else:
    run.status = WorkflowStatus.DONE
    _check_and_dispatch_wake(run.triggered_by_invocation_id, session, queue)
    session.commit()
```

**`_finalize_step_unavailable` — new helper, modeled on the DONE-path entry section of `on_step_complete` (`workflow_runner.py:462-529`):**

```python
# NEW — place between _compose_failure_outcome and queue_workflow in workflow_runner.py
def _finalize_step_unavailable(
    job_id: str,
    reason: str,
    session: Session,
    queue,
) -> None:
    """Phase 24 / D-01 — write StepUnavailableArtifact + advance through DONE path.

    Mirrors on_step_complete's artifact+status flip, but the artifact is the
    structured `unavailable` sentinel rather than the step's output, and the
    step still transitions to DONE (not FAILED) so the workflow continues.
    Reason is composed via _truncate_reason (shared with _compose_failure_outcome).
    """
    from robotina.queue.task_types import StepUnavailableArtifact
    from robotina.queue.models import WorkflowRunStep, WorkflowStepStatus

    step = (
        session.query(WorkflowRunStep)
        .filter(WorkflowRunStep.task_job_id == job_id)
        .first()
    )
    if step is None:
        logger.debug("_finalize_step_unavailable: no workflow step for job_id=%s", job_id)
        return

    artifact_obj = StepUnavailableArtifact(
        step_key=step.step_key,
        reason=_truncate_reason(reason),  # shared helper extracted from _compose_failure_outcome
    )
    step.artifact = artifact_obj.model_dump(mode="json")
    step.status = WorkflowStepStatus.DONE        # the whole point — DONE, not FAILED
    step.completed_at = datetime.now(timezone.utc)
    session.flush()

    _advance_after_step(step, session, queue)    # extracted from on_step_complete
    logger.info(
        "Step unavailable, advanced | run_id=%s step_key=%s reason=%r",
        step.workflow_run_id, step.step_key, artifact_obj.reason,
    )
```

---

### `src/robotina/queue/jobs.py` extensions (D-02, D-07, D-01 dispatch)

**Analog:** `jobs.py:90-112` `send-notification` branch (closest deterministic shape) + `jobs.py:114-165` `finalize-outcome` branch (the explicit precedent CONTEXT D-02 cites).

**`recipe-image` branch — copy `finalize-outcome` shape verbatim** (`jobs.py:119-165`):

```python
# jobs.py:119-165 — EXISTING finalize-outcome branch (the pattern to copy)
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
                image_present=False,    # D-07: replace with artifact-driven boolean
            )
        else:
            outcome = AddRecipeOutcome(status="failure", failure_reason=...)
        # locate WorkflowRun via step's task_job_id and stamp outcome ...
        artifact = outcome.model_dump(mode="json")
        workflow_runner.on_step_complete(job.id, artifact, _session, _queue)
        return artifact
    except Exception as exc:
        workflow_runner.on_step_failed(job.id, _session, _queue, exc=exc)
        raise
    finally:
        _session.close()
```

**New `recipe-image` branch — insert before the LLM-config lookup (around line 167):**

```python
# NEW — drop in after the finalize-outcome branch
if task_type == "recipe-image":
    from robotina.agent.tasks.recipe_image import acquire_recipe_image
    try:
        # task_input is RecipeImageInput; .recipe is RecipeData (with image_url=None
        # carried from prior steps).
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
        # Outer exception path (see "Non-fatal dispatch" below) reads
        # WorkflowStepDef.non_fatal_on_failure=True and routes through
        # workflow_runner._finalize_step_unavailable. Re-raise so RQ records
        # the job as failed (the step is DONE-unavailable; RQ's record is
        # informational).
        raise
    finally:
        _session.close()
```

**`finalize-outcome` `image_present` flip (D-07)** — modify only the `image_present=` line at `jobs.py:131`. RESEARCH §"Open Questions" 1 recommends extending `FinalizeOutcomeInput` (`task_types.py:441`) with `recipe_image: dict | None = None` and having the registry build_input lambda thread it through; planner picks final form.

**Non-fatal exception dispatch — outer `except Exception as exc:` block of `run_task`** (planner adds at the top of the existing except handler in `jobs.py`; RESEARCH Pattern 2 has the full code shape). Pattern:

```python
# Outer except — NEW dispatch (only applies when WorkflowStepDef.non_fatal_on_failure=True)
except Exception as exc:
    # Look up the step's WorkflowStepDef; if non_fatal_on_failure, route through
    # _finalize_step_unavailable instead of on_step_failed.
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.models import WorkflowRunStep, WorkflowRun

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
                    (s for s in wf_def.steps if s.step_key == step.step_key), None,
                )
                if step_def is not None and step_def.non_fatal_on_failure:
                    is_non_fatal = True
    if is_non_fatal:
        reason = f"{type(exc).__name__}: {exc}"
        workflow_runner._finalize_step_unavailable(job.id, reason, _session, _queue)
    else:
        workflow_runner.on_step_failed(job.id, _session, _queue, exc=exc)
    raise   # always re-raise so RQ records the failure
```

---

### `src/robotina/agent/tasks/recipe_image.py` (NEW — D-02, D-11)

**Analog (primary):** `src/robotina/agent/tools/fetch_and_scrape.py:100-179` — the safe_fetch → bytes.decode → `recipe_scrapers.scrape_html(html, org_url=..., wild_mode=True)` shape; the per-method try/except pattern.

**Imports pattern** — copy the lazy-import style used in `FetchAndScrapeTool._run` and `jobs.py` deterministic branches (imports inside the function, not at module top):

```python
# src/robotina/agent/tasks/recipe_image.py — NEW module
"""Deterministic recipe-image acquisition (Phase 24 / D-02 / D-11).

Mirrors the finalize-outcome agent-less pattern at jobs.py:119. Owns the
fallback ladder:
  1. source-page (when RecipeData.source_url is set): safe_fetch source_url +
     recipe_scrapers.scrape_html(html, wild_mode=True).image()
  2. Tavily image search: tavily_image_search(f"{recipe.name} receta") → top result
  3. miss: raise RecipeImageAcquisitionError (runner's non_fatal_on_failure
     flag converts to StepUnavailableArtifact)
"""
from __future__ import annotations

import logging

from robotina.queue.task_types import RecipeImageInput, RecipeImageOutput

logger = logging.getLogger(__name__)


class RecipeImageAcquisitionError(Exception):
    """No image URL passed safe_fetch validation; runner converts to unavailable."""
```

**Source-page branch — copy `FetchAndScrapeTool._run` lines 100-132 pattern** (`fetch_and_scrape.py`):

```python
# fetch_and_scrape.py:100-132 — EXISTING reference shape
from robotina.url.safe_fetch import safe_fetch
fetched = safe_fetch(url, expected_content_type="text/html")
html = fetched.content_bytes.decode("utf-8", errors="replace")
scraper: Any | None
try:
    scraper = scrape_html(html, org_url=fetched.final_url, wild_mode=True)
except RecipeScrapersExceptions:
    scraper = None
except Exception:
    scraper = None
```

**Per-method try/except (`fetch_and_scrape.py:139-153`) — copy for `.image()`:**

```python
# Wrap scraper.image() identically to how FetchAndScrapeTool wraps per-field calls
try:
    val = getattr(scraper, "image")()
    if val:
        candidate_url = val.strip() if isinstance(val, str) else None
except Exception:
    candidate_url = None
```

**Tavily branch** — call `tavily_image_search` (new sibling tool). Top-result-only (D-11).

**Validation** — call `safe_fetch(candidate_url, expected_content_type="image/*", max_bytes=15_000_000)`; let `SafeFetchError` propagate to the runner's non-fatal flag.

**Full skeleton:** see RESEARCH.md Code Example 3 (lines 575-672); planner copies that body.

---

### `src/robotina/agent/tools/tavily_image_search.py` (NEW — D-12)

**Analog:** `src/robotina/agent/tools/web_search.py` (`WebSearchTool`). Copy: TAVILY_API_KEY bracket-read, `TavilyClient` lazy import, response-shape defensive handling, INFO log line. Drop: `BaseTool` subclass + `name`/`description` (not needed — no LLM agent calls this in v1.1 per D-12).

**Imports + structure pattern** (`web_search.py:1-15`):

```python
# web_search.py:1-15 — EXISTING analog
"""web-search tool for the recipe-research-gather agent.

WebSearchTool wraps TavilyClient.search() from tavily-python. It is instantiated
per-job inside run_task() — never at module level (locked Phase 4 constraint).

The TAVILY_API_KEY env var must be set. This is the Tavily SDK standard name.
"""
from __future__ import annotations
import logging
import os
from langchain_core.tools import BaseTool      # DROP in v1.1 — not needed
logger = logging.getLogger(__name__)
```

**Core Tavily call pattern (`web_search.py:40-70`):**

```python
# web_search.py:40-70 — EXISTING; mirror with include_images=True
def _run(self, query: str) -> list[dict]:
    from tavily import TavilyClient
    api_key = os.environ["TAVILY_API_KEY"]
    client = TavilyClient(api_key=api_key)
    try:
        response = client.search(
            query=query,
            max_results=3,
            search_depth="advanced",
            include_raw_content=True,
        )
    except Exception as exc:
        logger.error("web-search failed | query=%r error=%s", query, exc)
        return [{"error": str(exc)}]
    results = response.get("results", [])
    logger.info("web-search | query=%r results=%d", query, len(results))
    return [{...}]
```

**`tavily_image_search` adaptation** — plain function (not `BaseTool`); read `images` not `results`; propagate exceptions (caller — `acquire_recipe_image` — relies on the non-fatal flag, not a silent error-dict return). Full skeleton in RESEARCH.md Pattern 3 / Code Example at lines 339-389.

---

### `src/robotina/dashboard/templates/_macros.html` (D-21)

**Analog:** `_macros.html:13-23` existing `TASK_TYPE_LABELS` dict (Phase 21 D-11 pattern). Comment at line 11 explicitly anticipates "Future phases (23 gather-from-url, 24 recipe-image) will extend the dict."

**Excerpt (`_macros.html:1-25`):**

```jinja
{# Phase 21 D-11: TASK_TYPE_LABELS Spanish display labels for task badges.
   Future phases (23 gather-from-url, 24 recipe-image) will extend the dict.  #}
{% set TASK_TYPE_LABELS = {
    "gather": "Búsqueda",
    "gather-from-url": "Búsqueda por URL",
    "instructions": "Instrucciones",
    ...
    "send-notification": "Notificación"
} %}
```

**One-line addition** (planner inserts into the dict; placement near siblings — recommend after `"metadata"` to mirror workflow ordering):

```jinja
"recipe-image": "Imagen",
```

---

### `experiments/recipe_image.py` (NEW — D-09, EXP-03)

**Analog:** `experiments/gather_from_url.py` — closest existing experiment template (Phase 23 manual gate; same `verdict: pending` frontmatter pattern; LangWatch instrumentation; per-row iteration; CLI `--backend`/`--limit`/`--out`).

**Imports + boot pattern (`gather_from_url.py:54-78`):**

```python
# gather_from_url.py:54-78 — EXISTING; copy verbatim
from __future__ import annotations
import argparse, json, logging, os, re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

load_dotenv()

import langwatch                                # noqa: E402 — must follow load_dotenv()
import langwatch.langchain                      # noqa: E402
from langwatch.client import Client as LangWatchClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

PHASE = "24"                                    # was "23" in analog
PROMPT_VERSION = "n/a"                          # recipe-image is agent-less; no prompt version
EXPERIMENT_NAME = "recipe-image-eval"
DEFAULT_EVAL_SET = Path(".planning/phases/24-recipe-images-topic-3/24-IMG-EVAL-SET.md")
DEFAULT_OUT_TEMPLATE = ".planning/phases/24-recipe-images-topic-3/24-IMG-EVAL-RESULTS-{backend}.md"
```

**Per-row iteration pattern (`gather_from_url.py:738-789`):**

```python
# gather_from_url.py:741-784 — EXISTING per-row loop; copy structure, swap agent.invoke for acquire_recipe_image direct call
for row in rows:
    logger.info("--- URL %d (%s) %s ---", row.idx, row.coverage_class, row.url)
    tracer = langwatch.langchain.LangChainTracer(
        metadata={
            "experiment": EXPERIMENT_NAME,
            "phase": PHASE,
            "prompt_version": PROMPT_VERSION,
            ...
        }
    )
    result = run_one(agent, row, tracer)
    results.append(result)
    logger.info(...)
if LangWatchClient._tracer_provider is not None:
    LangWatchClient._tracer_provider.force_flush()
write_results(out_path, args.backend, results, config_meta)
```

**Phase 24 difference:** no `build_agent()` (recipe-image is agent-less); the loop calls `acquire_recipe_image(input)` directly. The LangWatch tracer still wraps the call (matches the `with langwatch.trace(...):` wrap in the `recipe-image` jobs.py branch).

**Markdown emit pattern (`gather_from_url.py:416-513`)** — copy the `verdict: pending` frontmatter + "Aggregate" + "Per-URL results" table + "Notes" + "Go / No-Go" sections verbatim; swap the scoring rule for "operator visually inspects image" (no automated pass/fail per D-09).

---

### `experiments/robotina_wake.py` (NEW — D-10, EXP-04)

**Analog (CLI/boot):** `experiments/gather_from_url.py`.
**Analog (synthetic-input construction):** `workflow_runner.py:150-301` `_check_and_dispatch_wake` — the only producer of `WakeInvocationInput` in the codebase. Copy its `WorkflowOutcomeSummary(...)` and `WakeInvocationInput(...)` instantiation pattern:

```python
# workflow_runner.py:236-277 — EXISTING; pattern for synthesizing fixture inputs
outcomes: list[WorkflowOutcomeSummary] = []
for r in sibling_runs:
    run_outcome = AddRecipeOutcome.model_validate(r.outcome) if r.outcome else None
    outcomes.append(
        WorkflowOutcomeSummary(
            workflow_run_id=r.id,
            workflow_type=r.workflow_type,
            status="done" if r.status == WorkflowStatus.DONE else "failed",
            outcome=run_outcome,
            recipe_query=...,
        )
    )
wake_input = WakeInvocationInput(
    previous_invocation_id=parent.id,
    conversation_id=parent.conversation_id,
    outcomes=outcomes,
)
```

**Synthetic fixture builder (NEW, no DB):**

```python
# experiments/robotina_wake.py — synthesize directly, no DB read
def synthetic_wake_input(outcome_specs: list[dict]) -> WakeInvocationInput:
    outcomes = [
        WorkflowOutcomeSummary(
            workflow_run_id=spec.get("workflow_run_id", str(uuid.uuid4())),
            workflow_type=spec.get("workflow_type", "add-recipe-from-query"),
            status=spec["status"],
            outcome=AddRecipeOutcome(**spec["outcome"]) if spec.get("outcome") else None,
            recipe_query=spec.get("recipe_query"),
        )
        for spec in outcome_specs
    ]
    return WakeInvocationInput(
        previous_invocation_id=str(uuid.uuid4()),
        conversation_id=str(uuid.uuid4()),
        outcomes=outcomes,
    )
```

**Required fixture rows (D-08b):**
1. `outcomes=[success(image_present=True)]` — single recipe saved with image
2. `outcomes=[success(image_present=False)]` — load-bearing for D-08 (V007 should NOT surface "sin foto")
3. `outcomes=[failure]` — failure reason in reply
4. multi-outcome batch with mixed `image_present`

**Agent invocation** — call the wake-context Robotina agent directly via `AGENT_REGISTRY["handle-incoming-message"]`'s `_build_*_agent_for_run` factory (RESEARCH §"D-10"); print `respond()` text + LangWatch trace link.

---

### `pyproject.toml` `[project.scripts]` (EXP-06)

**Analog:** `pyproject.toml:44-48` — existing `experiments.*` entries:

```toml
# pyproject.toml:44-48 — EXISTING (copy format verbatim)
[project.scripts]
agent = "robotina.queue.runner:main"
migrate = "robotina.db:run_migrations"
"experiments.recipe_research" = "experiments.recipe_research:main"
"experiments.recipe_load" = "experiments.recipe_load:main"
"experiments.gather_from_url" = "experiments.gather_from_url:main"
```

**Add two lines:**

```toml
"experiments.recipe_image" = "experiments.recipe_image:main"
"experiments.robotina_wake" = "experiments.robotina_wake:main"
```

---

### `.planning/phases/24-recipe-images-topic-3/24-IMG-EVAL-SET.md` (NEW)

**Analog:** `.planning/phases/23-url-ingestion-topic-2/23-EVAL-SET.md` — same markdown-table-of-fixtures shape. Coverage classes per CONTEXT D-09 (source-page hit, source-page-miss → Tavily, query-only Tavily, known-difficult, sanity miss).

---

## Shared Patterns

### Pydantic v2 + `ConfigDict(extra="forbid")` on all new models

**Source:** `src/robotina/queue/task_types.py` — every Phase 18/20/21/22/23 model.
**Apply to:** `RecipeImageInput`, `RecipeImageOutput` (if Option A), `StepUnavailableArtifact`.

```python
# Convention applied across task_types.py
class FooInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ...
```

### Sentinel aliases for output-shape RecipeData reuse

**Source:** `src/robotina/queue/task_types.py:283-288`:

```python
# task_types.py:283-288 — EXISTING; mirror for RecipeImageOutput per D-03 Option B
RecipeResearchGatherOutput = RecipeData
RecipeResearchInstructionsOutput = RecipeData
RecipeResearchIngredientsOutput = RecipeData
RecipeResearchMetadataOutput = RecipeData
# NEW:
RecipeImageOutput = RecipeData  # Phase 24 / D-03 — image_url is now a RecipeData field
```

### Lazy imports inside deterministic branches

**Source:** `src/robotina/queue/jobs.py:91, 92, 120, 121` — all deterministic branches lazy-import inside the branch (never at module top) to avoid cycle risk + startup cost.
**Apply to:** the new `recipe-image` branch in jobs.py and `_finalize_step_unavailable` in workflow_runner.py.

```python
# jobs.py:120-121 — EXISTING
if task_type == "finalize-outcome":
    from robotina.queue.task_types import AddRecipeOutcome
    from robotina.queue.models import WorkflowRun, WorkflowRunStep
    ...
```

### LangWatch trace wrap with ImportError fallback

**Source:** `src/robotina/queue/jobs.py:356-369` (LLM branch's trace wrap) — has the `try: import langwatch / except ImportError:` pattern.
**Apply to:** the new `recipe-image` deterministic branch (RESEARCH Pitfall 8 — the existing `finalize-outcome` and `send-notification` branches do NOT enter the LLM-branch trace wrap, so Phase 24 must add its own).

```python
try:
    import langwatch
    with langwatch.trace(metadata={"task_type": "recipe-image", "phase": 24}):
        output = acquire_recipe_image(task_input)
except ImportError:
    output = acquire_recipe_image(task_input)
```

### TAVILY_API_KEY bracket-read (fail-loud on missing)

**Source:** `src/robotina/agent/tools/web_search.py:44`:

```python
# web_search.py:44 — EXISTING; mirror exactly in tavily_image_search
api_key = os.environ["TAVILY_API_KEY"]      # bracket form — KeyError if missing
client = TavilyClient(api_key=api_key)
```

### `safe_fetch` reuse contract

**Source:** `src/robotina/url/safe_fetch.py:210-226` — wildcard sniff already supports `image/*` (line 216: `elif expected.startswith("image/"): accepted = ("image/",)` + prefix-match at 221).
**Apply to:** `acquire_recipe_image` validation step.

```python
# Reused contract — Phase 24 caller usage:
safe_fetch(candidate_url, expected_content_type="image/*", max_bytes=15_000_000)
```

### Reason-truncation (≤ 150 chars + Pydantic-URL noise strip)

**Source:** `src/robotina/queue/workflow_runner.py:46-79` — `_PYDANTIC_URL_NOISE_RE` + `_OUTCOME_FAILURE_REASON_MAX_CHARS` + the `_compose_failure_outcome` truncation block.
**Apply to:** `StepUnavailableArtifact.reason` composition. Extract a shared `_truncate_reason(raw: str) -> str` helper called from both `_compose_failure_outcome` and the new `_finalize_step_unavailable`.

### Workflow registry inline-duplication (no shared-tail helper — D-06)

**Source:** `src/robotina/agent/workflows.py:68-209` — Phase 23 D-01 inline-duplicated the 5-step tail across `add-recipe-from-query` and `add-recipe-from-url`. Phase 24 D-06 *further defers* the helper extraction.
**Apply to:** ALL `recipe-image` step insertions — duplicate verbatim in both `WORKFLOW_REGISTRY` entries. No `build_recipe_tail()` helper.

### Experiment-script verdict frontmatter (operator gate)

**Source:** `experiments/gather_from_url.py:440-447` — `verdict: pending` YAML frontmatter that operator flips post-run:

```python
# gather_from_url.py:440-447 — EXISTING
lines.append("---")
lines.append("verdict: pending")
lines.append(f"backend: {backend}")
lines.append(f"model: {model}")
lines.append(f"date: {date.today().isoformat()}")
lines.append(f"operator: {operator}")
lines.append("eval_set_version: 1")
lines.append("---")
```

**Apply to:** both `experiments/recipe_image.py` results and `experiments/robotina_wake.py` results files.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | Every new file has a strong analog. `StepUnavailableArtifact` is the only genuinely new model shape, but its Pydantic conventions (ConfigDict + Literal discriminator) are mirrored exactly from `AddRecipeOutcome` (`task_types.py:352`). |

## Metadata

**Analog search scope:**
- `src/robotina/queue/` (jobs.py, workflow_runner.py, task_types.py)
- `src/robotina/agent/workflows.py`
- `src/robotina/agent/tools/` (web_search.py, fetch_and_scrape.py)
- `src/robotina/url/safe_fetch.py`
- `src/robotina/dashboard/templates/_macros.html`
- `experiments/*.py`
- `pyproject.toml`

**Files scanned:** ~12 source files (file-by-file read; no broad glob).

**Pattern extraction date:** 2026-05-22

**Key insight:** Phase 24 is overwhelmingly a *composition* phase — every primitive already exists in the codebase. The two genuinely new shapes (`_finalize_step_unavailable` runner helper, `tavily_image_search` function) have very close opposite-polarity / sibling analogs (`on_step_failed`, `WebSearchTool`). The pattern map is high-fidelity.
