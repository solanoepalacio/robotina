# Phase 24: Recipe images (Topic 3) — Context

**Gathered:** 2026-05-22
**Status:** Ready for planning
**Mode:** `--auto` (Auto Mode active — every D-NN below is Claude's call with rationale; user can redirect any decision before `/gsd:plan-phase 24` runs.)

<domain>
## Phase Boundary

Insert a `recipe-image` step in both add-recipe workflow variants between
`metadata` and `recipe-load`. Acquire an image via a fallback ladder
(source-page `.image()` when URL-sourced → Tavily image search otherwise
→ mark missing). Add a per-step non-fatal-failure capability to the
runner so the recipe still saves on image miss. Validate the candidate
URL via the existing `safe_fetch` helper with `expected_content_type="image/*"`.
Persist the image URL via the household-manager API. Set
`AddRecipeOutcome.image_present`. Ship two new experiment scripts
(`experiments.recipe_image`, `experiments.robotina_wake`) and update
`pyproject.toml` + CLAUDE.md.

Concretely:

1. **`WorkflowStepDef.non_fatal_on_failure: bool = False`** (NEW field) +
   runner extension (`workflow_runner.py`): when a step with
   `non_fatal_on_failure=True` raises, the exception path writes a
   structured `StepUnavailableArtifact(status="unavailable", step_key, reason)`
   and routes through the DONE-path advancement (not FAILED). All other
   steps unchanged. (D-01)
2. **`recipe-image` task type** — DETERMINISTIC, agent-less (mirrors
   `finalize-outcome` at `jobs.py:119`). New branch in `run_task` for
   `task_type == "recipe-image"` that runs the fallback ladder in plain
   Python. (D-02)
3. **Fallback ladder** (deterministic function in
   `src/robotina/agent/tasks/recipe_image.py`, NEW module):
   - If `recipe.source_url` is set: try `recipe_scrapers.scrape_html(html,
     wild_mode=True).image()` first (re-fetch the source page via
     `safe_fetch` + reuse `FetchAndScrapeTool`-style internals — see D-03).
   - Otherwise (or on source-page miss): call a NEW
     `TavilyImageSearchTool` (or `WebSearchTool` extended with
     `include_images=True`); pick top result.
   - In both branches: validate the candidate URL via
     `safe_fetch(url, expected_content_type="image/*", max_bytes=15_000_000)`.
   - On validation failure: raise (the runner's `non_fatal_on_failure`
     flag converts to "unavailable" artifact).
4. **`RecipeData.image_url: str | None = None`** (NEW field) — populated
   by the `recipe-image` step's output artifact. `recipe-load`'s
   `build_input` reads `artifacts["recipe-image"].image_url` and
   forwards to the household-manager POST. (D-04)
5. **Storage = URL pin.** `recipe-load` POSTs `{..., image_url: "https://..."}`
   in the recipe payload; household-manager stores the URL string.
   No backend upload endpoint. No EXIF strip. No image bytes
   redistributed by Robotina. (D-05)
6. **Shared-tail helper extraction** — `build_recipe_tail() -> list[WorkflowStepDef]`
   in `src/robotina/agent/workflows.py`; both `add-recipe-from-query`
   and `add-recipe-from-url` compose `[gather*] + build_recipe_tail()`.
   This is the deferred extraction from Phase 23 D-01. (D-06)
7. **`AddRecipeOutcome.image_present`** — `finalize-outcome` (already
   at `jobs.py:131`, hardcoded `False`) reads
   `artifacts["recipe-image"]`'s status: `True` if `image_url` is a
   non-empty string, `False` if status is "unavailable" or the artifact
   is absent. (D-07)
8. **No wake-reply prompt change** — V007 stays. `outcome.image_present`
   is structural data consumed by the future household UI, not
   user-facing text in v1.1. (D-08)
9. **`experiments.recipe_image`** (EXP-03) — single script
   `experiments/recipe_image.py`. Iterates a small fixture set of
   `(recipe_name, source_url | None)` rows, runs the deterministic
   `recipe-image` function directly (no workflow), captures candidate
   image URL + which-branch-won + safe_fetch result; emits markdown
   table to `.planning/phases/24-recipe-images-topic-3/24-IMG-EVAL-RESULTS-<backend>.md`.
   LangWatch instrumentation active per CLAUDE.md. (D-09)
10. **`experiments.robotina_wake`** (EXP-04) — single script
    `experiments/robotina_wake.py`. Constructs SYNTHETIC
    `WakeInvocationInput` objects in memory (no DB writes); invokes
    the wake-context Robotina agent directly; prints the wake reply +
    LangWatch trace link. (D-10)
11. **`pyproject.toml` `[project.scripts]`** adds
    `experiments.recipe_image` and `experiments.robotina_wake`;
    **CLAUDE.md** experiment table mirrors. (EXP-06)
12. **Pitfall 8 mitigation = top-result + source-page bypass; vision-LLM
    deferred to v1.2.** The Phase 24 manual eval (EXP-03) is the
    empirical gate; if <60% of Tavily images are usable, vision-LLM
    lands as a follow-up phase. (D-11)
13. **REQUIREMENTS.md ticks** for IMG-01..06, EXP-01, EXP-03, EXP-04,
    EXP-06 in the final smoke commit.
14. **`24-IMG-EVAL-SET.md`** (canonical fixture set) +
    **`24-IMG-EVAL-RESULTS-<backend>.md`** (operator-run) +
    **`24-SMOKE.md`** (final verdict) — mirrors Phase 21/22/23.

**Out of scope (deferred):**

- **Vision-LLM "is this the right dish?" check** (Pitfall 8 full
  mitigation) — v1.2 follow-up; gated on eval results.
- **Image download-and-rehost to household-manager** (IMG-05 alternative)
  — requires NEW backend upload endpoint; not committed for v1.1.
  URL pin is the v1.1 stance.
- **EXIF strip + magic-byte validation via PIL** — not needed when we
  URL-pin (we never redistribute bytes); reconsider in the v1.2 rehost
  follow-up.
- **Periodic broken-link sweep** — deferred to scheduler milestone
  (per Pitfall 8 / SUMMARY.md). v1.1 accepts link-rot risk.
- **`recipe-scrapers` site-list expansion** — out of scope; use what
  the library ships with.
- **Wake-reply "guardé X, pero sin foto" surfacing** (V008 fork) —
  deferred. Memory `project_compose_agent_vision` — let the future
  Compose agent own image-aware reply composition.
- **Multi-candidate retry on safe_fetch failure** — top-result only in
  v1.1; if top result fails `safe_fetch`, mark missing. Retry-next is
  a v1.2 refinement.
- **Image acquisition for recipes WITHOUT a `name`** — not possible;
  Tavily query requires a recipe name; `RecipeData.name` is already
  required (`task_types.py:123`).

</domain>

<decisions>
## Implementation Decisions

> **Auto-mode note:** Every D-NN below is Claude's call under the no-stopping
> system reminder. The user can redirect any decision before `/gsd:plan-phase 24` runs.

### Non-fatal runner capability shape (IMG-03, IMG-06)

- **D-01: `WorkflowStepDef.non_fatal_on_failure: bool = False` (definition
  flag) + runner converts exceptions to "unavailable" artifact.**

  Concretely:
  - Add `non_fatal_on_failure: bool = False` to `WorkflowStepDef`
    (`src/robotina/agent/workflows.py:32`).
  - New Pydantic model `StepUnavailableArtifact` in
    `src/robotina/queue/task_types.py`:
    ```python
    class StepUnavailableArtifact(BaseModel):
        model_config = ConfigDict(extra="forbid")
        status: Literal["unavailable"] = "unavailable"
        step_key: str
        reason: str  # short, ≤ 150 chars (matches _OUTCOME_FAILURE_REASON_MAX_CHARS)
    ```
  - In `workflow_runner.py`: new helper `_finalize_step_unavailable(step,
    reason, session)` that writes the structured artifact and routes
    through the DONE-path advancement (calling
    `_finalize_step_completion`'s inner advancement logic).
  - In `run_task` (`jobs.py`): when a step raises and
    `WorkflowStepDef.non_fatal_on_failure` is `True`, call the
    unavailable helper instead of `_finalize_step_failure`. The
    exception type does NOT matter — the flag is the decision.
  - Reason is composed the same way as `_compose_failure_outcome`
    (`workflow_runner.py:52`): strip Pydantic doc URL noise, collapse
    whitespace, truncate to 150 chars, format
    `f"{step_key}: {short}"`.

  **Why not (B) "agent always returns structured output":** doesn't
  satisfy IMG-06's "declared at step definition level" wording, and
  leaves unexpected exceptions (Tavily 503, safe_fetch transient
  timeouts) to FAIL the workflow — exactly the bug IMG-03 prevents.
  Putting the policy on every agent author also drifts; the runner
  is the right enforcement layer (it's the one that transactionally
  cascades FAILED → cancel-remaining).

  **Why not (C) hybrid:** unnecessary. The agent CAN return
  `image_url=None` for the known-miss path (step DONE with a real
  `RecipeImageOutput(image_url=None, status="unavailable")` artifact);
  the runner flag is only for the unexpected-exception path. Those are
  two distinct paths already, not a hybrid policy.

  **Why the flag, not a per-exception-type filter:** the flag is a
  per-step *policy* ("this step's failure is recoverable for the
  workflow"); exception-type filtering inside the step's code is the
  step's choice (e.g. `recipe-image` deterministic function will raise
  cleanly on Tavily 503 or safe_fetch SafeFetchError — both convert to
  "unavailable" via the flag). If a future step wants finer control,
  it can catch internally and return its own structured output.

- **D-01b: Only `recipe-image` sets `non_fatal_on_failure=True` in v1.1.**
  All other steps stay strict. The capability is generic but the
  application is narrow.

### `recipe-image` task type shape (IMG-01, IMG-02, IMG-04)

- **D-02: `recipe-image` is a DETERMINISTIC agent-less task type.**

  - New branch in `run_task` for `task_type == "recipe-image"`
    (mirrors the `finalize-outcome` branch at
    `src/robotina/queue/jobs.py:119`). No LangChain agent, no prompt,
    no `AGENT_REGISTRY` entry.
  - The branch calls `acquire_recipe_image(input: RecipeImageInput) ->
    RecipeImageOutput` (new function in
    `src/robotina/agent/tasks/recipe_image.py`).
  - LangWatch span emission: the deterministic branch wraps the
    function call in an OTel span tagged `task_type="recipe-image"`
    so the LangWatch dashboard still shows the step. No LLM call
    means no LLM-span; that's expected for a deterministic task.

  **Why deterministic over LLM agent:**
  - Memory `feedback_avoid_premature_abstraction` — there's no
    decision an LLM is making in v1.1. Both branches (source-page,
    Tavily) are mechanical. Adding an LLM agent + prompt + tools +
    response_format for a single-string output (`image_url: str | None`)
    is over-engineering.
  - Cost: every recipe save would pay one extra LLM call (~$0.001-0.01)
    for zero decision value. Across the eval set + production traffic,
    that's pure waste.
  - Precedent: `finalize-outcome` (Phase 20) is already agent-less.
    Pattern exists in `jobs.py:119`.
  - When the Pitfall 8 vision-LLM mitigation lands in v1.2, the task
    can convert to an LLM agent or grow a `VisionValidatorTool` —
    that's the right moment to add LLM cost.

  **Why not LLM agent with one branching tool (mirror gather-from-url):**
  in `gather-from-url`, the LLM-extract path NEEDED `response_format`
  for the no-scraper case. Here there's no extraction step — both
  branches return a string. The LLM is a passthrough; pure overhead.

### `RecipeImageInput` / `RecipeImageOutput` contracts

- **D-03: Pydantic models in `src/robotina/queue/task_types.py`:**
  ```python
  class RecipeImageInput(BaseModel):
      model_config = ConfigDict(extra="forbid")
      recipe: RecipeData                    # current RecipeData accumulator
      reply_context: ReplyContext           # for parity with other steps; unused here
      household_id: NonEmptyHouseholdId

  class RecipeImageOutput(BaseModel):
      model_config = ConfigDict(extra="forbid")
      # The merged RecipeData (with image_url set or None).
      # Mirrors how recipe-research-* steps emit the full RecipeData
      # accumulator (Phase 15).
      name: str
      description: str | None = None
      servings_qty: int | None = None
      servings_unit: str | None = None
      prep_time: int | None = None
      cook_time: int | None = None
      total_time: int | None = None
      source_url: str | None = None
      image_url: str | None = None          # NEW; the field this step owns
      ingredients: list[RecipeIngredient] = []
      steps: list[RecipeStep] = []
      gathered_sources: list[dict] | None = None
      missing_ingredients: list[str] = []
  ```

  In practice `RecipeImageOutput` IS the RecipeData shape with
  `image_url` added — to keep the artifact accumulation pattern
  identical to Phase 15. Implementation may simply set
  `image_url` on the incoming `RecipeData` and emit
  `recipe.model_dump(mode='json')`.

- **D-04: Add `image_url: str | None = None` field to `RecipeData`**
  (`src/robotina/queue/task_types.py:105`). Field ownership: owned by
  the `recipe-image` step. All earlier steps preserve `None`.
  `recipe-load` reads it from the incoming `RecipeData` and includes
  it in the household-manager POST payload.

### Fallback ladder + Pitfall 8 mitigation (IMG-02, IMG-04, Pitfall 8)

- **D-11: Top-result only + source-page bypass; vision-LLM check
  deferred to v1.2.**

  - **Source-page branch (preferred when `recipe.source_url is not
    None`):** re-fetch the source page via `safe_fetch(source_url,
    expected_content_type="text/html")`; parse with
    `recipe_scrapers.scrape_html(html, wild_mode=True, org_url=source_url)`;
    call `.image()`. If non-empty, that's the candidate. Source-page
    images are highly trusted (the recipe author's chosen photo) —
    bypass any "right dish?" check.
  - **Tavily branch (otherwise, or on source-page miss):** call
    Tavily image search via `TavilyClient().search(query=f"{recipe.name}
    receta", search_depth="basic", include_images=True, max_results=5)`.
    Tavily returns an `images` list; take `images[0]` as the candidate.
    Spanish-language hint (`"receta"`) biases toward
    Spanish-source food photos.
  - **Validation:** `safe_fetch(candidate_url,
    expected_content_type="image/*", max_bytes=15_000_000)`. If
    `safe_fetch` raises (`SafeFetchError`), the deterministic function
    re-raises; the `non_fatal_on_failure=True` flag on the step
    converts that to an "unavailable" artifact (D-01).
  - **NO multi-candidate retry in v1.1.** If `images[0]` fails
    `safe_fetch`, mark missing. Retrying `images[1..N]` until one
    passes is a v1.2 refinement gated on eval data.
  - **NO vision-LLM "is this the right dish?" check in v1.1.** The
    Phase 24 manual eval (EXP-03) is the empirical gate. If <60% of
    Tavily images are deemed "good enough" by the operator review,
    vision-LLM mitigation lands as a follow-up phase.
  - **NO magic-byte validation via PIL.** When we URL-pin (D-05), we
    never decode the image bytes; trusting the `Content-Type` header
    from `safe_fetch` is sufficient for our threat model (the
    household UI renders the URL in an `<img>` tag — browser-side
    decoding handles malformed bytes safely).

  **Why this ordering:**
  - Source-page hit is the highest-quality outcome (author's photo).
  - Tavily fallback covers query-mode + source-page-miss in one path.
  - Top-result-only + manual-eval-gated is the same pattern as
    Phase 23's URL eval — empirical validation, no premature engineering.
  - The non-fatal flag (D-01) makes "missing image" the recoverable
    outcome that matters; wrong-image is the Pitfall 8 risk the eval
    will quantify.

- **D-12: Tavily image-search wiring — extend `WebSearchTool` or new
  `TavilyImageSearchTool`?**

  - **NEW `TavilyImageSearchTool`** in
    `src/robotina/agent/tools/tavily_image_search.py`. Mirrors
    `WebSearchTool` shape; reads same `TAVILY_API_KEY` env var; calls
    `TavilyClient().search(..., include_images=True)`; returns the
    `images` list (URLs only).
  - **Why a new tool, not extending `WebSearchTool`:** `WebSearchTool`
    is constructor-arg-free and returns text-search results;
    image-search results have a different shape. Keeping them separate
    avoids polymorphism in the existing tool's return type. Memory
    `feedback_avoid_premature_abstraction` — concrete duplication is
    fine for a 2nd Tavily tool; abstract a `TavilyTool` base only when
    a 3rd lands.
  - **No LangChain `BaseTool` wrapping** in v1.1 — the deterministic
    branch calls the tool's underlying `TavilyClient` directly. The
    `BaseTool` wrapping exists for LLM agents only. (The class can
    still inherit from `BaseTool` for symmetry with `WebSearchTool`
    if planner prefers; the deterministic call path bypasses the
    LangChain tool runner regardless.)

  **Planner final call:** simplest shape is a plain function
  `tavily_image_search(query: str) -> list[str]` in
  `src/robotina/agent/tools/tavily_image_search.py`; no `BaseTool`
  class needed if no LLM agent calls it in v1.1. If planner sees a
  reason to keep symmetry with `WebSearchTool`, the BaseTool subclass
  is fine — same wiring, different stylistic call.

- **D-13: `safe_fetch` extension for `image/*` content type.** Phase 23
  D-16 declared `expected_content_type: str = "text/html"` as the
  default. Phase 24 reuses unchanged — caller passes
  `expected_content_type="image/*"`. The content-type sniff in
  `safe_fetch` already supports the wildcard pattern per Phase 23 D-16's
  contract (`for "image/*", any "image/..."`). If the current
  implementation doesn't yet match the wildcard, Phase 24's first
  commit fixes the sniff (tiny extension; no API change).
  - **Caller-side `max_bytes`:** `15_000_000` (15 MB) for images vs
    the default `5_000_000` (5 MB) for HTML. Modern food photos
    routinely exceed 5 MB; 15 MB covers high-res JPEGs without
    inviting bomb attacks (gzip-bomb defense still fires per Phase 23
    D-16).

### Storage strategy (IMG-05)

- **D-05: URL pin — Robotina POSTs `image_url: str | None` in the
  recipe payload; household-manager stores the URL string. No bytes
  transferred; no rehost endpoint required.**

  - `recipe-load` (existing `recipe-load` task) reads
    `recipe.image_url` from its input `RecipeData` and includes it in
    the household-manager POST body. (The HouseholdManagerApiTool
    already serializes the full `RecipeData` payload; adding a new
    field is a JSON-schema concern only.)
  - **Backend coordination signal:** the household-manager `Recipe`
    entity must accept an `image_url: str | null` field on the
    POST. Research (FEATURES.md line 188-191) treats this as a
    "known precondition" — Phase 24 verifies via the eval/smoke run.
    If the backend's POST schema rejects the field, the planner
    flags it as a P0 blocker; Robotina can't ship Phase 24 without
    the field being accepted.
  - **No EXIF strip, no magic-byte validation, no image-format
    enforcement** in Robotina. The image is the source-domain's
    bytes, served by the source-domain CDN, fetched by the user's
    browser. Privacy concerns (EXIF GPS) are the source-domain's
    problem. Robotina never downloads the bytes (except for the
    `safe_fetch` validation read, which discards them).
  - **Legal:** URL-pinning is industry standard for recipe
    aggregators ("we link to your hosted file"). No copy is
    redistributed. Source attribution is implicit in the URL itself.

  **Why not (B) download-and-upload:**
  - Backend team has NOT committed to building a `/recipes/<id>/image`
    upload endpoint. Building one is M-sized backend work.
  - The "image URL becomes a 404 in 6 months" risk (Pitfall 8) is
    real but documented as a v1.1 gap; broken-link sweep is the
    scheduler-milestone mitigation.
  - EXIF strip and magic-byte validation only matter when we
    redistribute. v1.1 doesn't.

  **Why not (C) ENV-gated hybrid:** Memory
  `feedback_avoid_premature_abstraction`. No rehost code in v1.1 →
  no flag to gate. If rehost lands in v1.2, the flag is a 5-line
  addition then.

### Shared-tail helper extraction (Phase 23 D-01 carry-over)

- **D-06: Extract `build_recipe_tail() -> list[WorkflowStepDef]` in
  `src/robotina/agent/workflows.py`.**

  Signature and return shape:
  ```python
  def build_recipe_tail() -> list[WorkflowStepDef]:
      """The 5-step tail shared by both add-recipe workflow variants.

      Steps (in order): instructions, ingredients, metadata,
      recipe-image, load, finalize-outcome.

      Phase 23 D-01 deferred this extraction to Phase 24 (when
      recipe-image insertion forces a 2nd point of variance).
      """
      return [
          WorkflowStepDef(step_key="instructions", ...),
          WorkflowStepDef(step_key="ingredients", ...),
          WorkflowStepDef(step_key="metadata", ...),
          WorkflowStepDef(
              step_key="recipe-image",
              task_type="recipe-image",
              build_input=lambda ctx, artifacts: RecipeImageInput(
                  recipe=RecipeData(**artifacts["metadata"]),
                  reply_context=ReplyContext(**ctx["reply_context"]),
                  household_id=ctx["household_id"],
              ),
              non_fatal_on_failure=True,
          ),
          WorkflowStepDef(step_key="load", ...),  # reads recipe.image_url from artifacts["recipe-image"]
          WorkflowStepDef(step_key="finalize-outcome", ...),
      ]
  ```
  - `add-recipe-from-query` composes `[gather_step] + build_recipe_tail()`.
  - `add-recipe-from-url` composes `[gather_from_url_step] + build_recipe_tail()`.

  **Why now:**
  - Phase 23 D-01 explicitly named Phase 24 as the extraction moment
    ("extract a helper in Phase 24 when `recipe-image` inserts a step
    in both variants").
  - 6 shared steps × 2 variants = 12 places to maintain in lock-step.
    Memory `feedback_avoid_premature_abstraction` is about not
    pre-abstracting before duplication shows; here we have 6 instances
    of shared structure, well past the 3+ threshold.
  - Inserting `recipe-image` in two duplicated places is exactly the
    drift risk the helper prevents.

  **Build-input lambdas stay inline.** No parameterization on the
  helper; the lambdas hold the per-step input-construction logic
  unchanged from current code.

- **D-06b: `recipe-load`'s `build_input` updated to read
  `artifacts["recipe-image"]` instead of `artifacts["metadata"]`.**
  Both shapes are full RecipeData dumps; only the source step key
  changes. (`RecipeImageOutput` is shaped identically to RecipeData
  with `image_url` set — see D-03.) Pure key swap in the helper.

### `AddRecipeOutcome.image_present` wiring (Success Criterion 3)

- **D-07: `finalize-outcome` reads `artifacts["recipe-image"]` and
  sets `image_present` accordingly.**

  In `src/robotina/queue/jobs.py:119` (the `finalize-outcome` branch):
  ```python
  recipe_image_artifact = run.shared_context.get(...)  # actually from accumulated_artifacts
  image_present = (
      recipe_image_artifact is not None
      and recipe_image_artifact.get("status") != "unavailable"
      and bool(recipe_image_artifact.get("image_url"))
  )
  outcome = AddRecipeOutcome(
      status="success",
      recipe_id=...,
      recipe_name=...,
      recipe_slug=...,
      image_present=image_present,
  )
  ```
  - `True` iff the artifact exists, is NOT a `StepUnavailableArtifact`,
    AND has a non-empty `image_url`.
  - `False` for the unavailable case (D-01), the absent case (older
    runs that pre-date Phase 24), or the empty-string edge case.
  - **`finalize-outcome` reads from `accumulated_artifacts`** (the
    same dict the workflow runner passes around per Phase 15) — its
    `FinalizeOutcomeInput` (already defined Phase 20) needs to be
    verified at planning time; if it doesn't already expose
    `accumulated_artifacts`, the planner extends it. Likely already
    has it; verify.

- **D-07b: `AddRecipeOutcome.image_present` field stays as-is** —
  no schema change to the model (`task_types.py:370` already declares
  it). Phase 24 just flips the producer logic.

### Wake-reply update (V007 → V008?)

- **D-08: NO wake-reply prompt change in v1.1. V007 stays.**

  - `outcome.image_present` is structural data consumed by the future
    household UI, not user-facing text in v1.1.
  - The Telegram chat is a notification surface; the household app is
    where the photo absence matters. Users see the gap when they open
    the recipe.
  - Memory `project_compose_agent_vision` — the future Compose agent
    will own image-aware reply composition. Don't churn V007 for a
    marginal v1.1 improvement that a future agent absorbs anyway.
  - Memory `feedback_avoid_premature_abstraction` — V008 fork for one
    optional sentence is exactly the kind of pre-feature churn the
    memory warns against.
  - If user feedback later requests it, V008 is a one-section addition
    (V007 already accepts arbitrary outcome fields).

### Experiment scripts (EXP-03, EXP-04, EXP-06)

- **D-09: `experiments/recipe_image.py` — single script, deterministic-function
  exercise (no workflow round-trip).**

  - Reads `.planning/phases/24-recipe-images-topic-3/24-IMG-EVAL-SET.md`
    (or sibling YAML) — 10-15 fixture rows of
    `{name: str, source_url: str | None, expected_branch:
    "source_page" | "tavily" | "miss_expected"}`.
  - Iterates rows, calls `acquire_recipe_image(...)` directly,
    captures: candidate URL, which branch fired, safe_fetch result,
    Tavily raw response (for the Tavily branch — to manual-review
    relevance).
  - Emits markdown table to
    `.planning/phases/24-recipe-images-topic-3/24-IMG-EVAL-RESULTS-<backend>.md`
    (per-backend, even though the task is deterministic — Tavily
    response varies day-to-day; `backend` here means the timestamp +
    Tavily key used).
  - **LangWatch instrumentation active** per CLAUDE.md (metadata
    tags: `phase=24`, `recipe_name=<name>`, `branch=<which>`).
  - **No automated pass/fail metric for image relevance** — operator
    eyeballs the markdown table; manual verdict in `24-SMOKE.md`.
    Same pattern as Phase 23's manual eval merge gate.

  Coverage classes in the fixture set:
  1. **Source-page hit (5+ rows)** — known recipe-scrapers-supported
     URLs with `.image()` available (Paulina Cocina, AllRecipes-es,
     etc. — reuse a subset of Phase 23's eval URLs).
  2. **Source-page miss → Tavily fallback (3+ rows)** — URLs without
     `.image()` data; exercises the fallback path.
  3. **Query-only → Tavily (3+ rows)** — common Spanish recipe names
     ("milanesa napolitana", "tarta de manzana", "asado") to gauge
     Tavily image quality.
  4. **Known-difficult (1+ row)** — a regional/obscure name where
     Tavily is expected to miss or return irrelevant images
     (documents the v1.1 gap).
  5. **Sanity miss (1 row)** — a name with `safe_fetch` failure
     forced (e.g. `name="__force_404__"` with a synthetic Tavily
     mock returning a 404 URL) — verifies the "unavailable" path
     fires correctly.

- **D-10: `experiments/robotina_wake.py` — synthetic in-memory
  WakeInvocationInput exercise.**

  - Constructs SYNTHETIC `WakeInvocationInput` objects in memory:
    one with `outcomes=[success(image_present=True)]`, one with
    `outcomes=[success(image_present=False)]`, one with
    `outcomes=[failure]`, one with mixed outcomes (multi-recipe
    batch).
  - Invokes the wake-context Robotina agent DIRECTLY (calls the
    AGENT_REGISTRY entry's `_build_*_agent_for_run` factory and
    runs the agent against the synthetic input).
  - No DB writes; no Redis writes; no Telegram round-trip. The
    script's only output is the agent's `respond()` text + LangWatch
    trace link printed to stdout.
  - Memory `feedback_test_before_handoff` — this script IS the
    pre-handoff smoke for V007's wake-context behavior.
  - **Why synthetic over DB-fixture:** synthetic is 5× faster to
    iterate, no DB-fixture teardown complexity, and the
    `WakeInvocationInput` schema is the actual contract (not the DB
    rows). DB-fixture is what
    `_check_and_dispatch_wake` integration tests already cover.

- **D-13: Results files structure (mirrors Phase 21/22/23):**
  - `24-IMG-EVAL-SET.md` — canonical fixture set (10-15 rows) +
    per-row expected branch/outcome. Committed in the eval-harness
    plan.
  - `24-IMG-EVAL-RESULTS-<backend>.md` — operator's per-backend run
    output (table with name, source_url, branch fired, candidate
    URL, safe_fetch verdict, manual "image looks right? Y/N",
    LangWatch trace link). Committed by operator post-run.
  - `24-SMOKE.md` — final verdict. References per-backend results;
    ends with `verdict: pass/fail/needs-revision` line.

### Test strategy (Claude's Discretion)

- **D-14: `WorkflowStepDef.non_fatal_on_failure` + runner integration
  tests are the load-bearing safety net.**

  `tests/queue/test_workflow_runner_non_fatal.py` (NEW):
  - Step with `non_fatal_on_failure=True` raises → step transitions
    to DONE (not FAILED); artifact is a `StepUnavailableArtifact`;
    WorkflowRun continues to next step; WorkflowRun reaches DONE.
  - Step with `non_fatal_on_failure=False` (default) raises → step
    FAILED; remaining steps cancelled; WorkflowRun FAILED (unchanged
    behavior).
  - The unavailable artifact passes through `recipe-load`'s
    `build_input` without error (verifies the artifact-key-swap from
    D-06b).
  - `_compose_failure_outcome`-style reason truncation applies to
    the unavailable artifact's `reason` field.

- **D-15: `acquire_recipe_image` unit tests** (deterministic function):
  - Source-page branch happy path (mocked `recipe_scrapers.scrape_html`
    returning a fake scraper with `.image()` returning a URL).
  - Source-page miss → Tavily branch (mocked scraper `.image()`
    returns None; mocked Tavily returns image URLs).
  - Tavily-only branch when `source_url is None`.
  - Tavily empty result → raises (caught by runner's non-fatal flag).
  - `safe_fetch` failure → raises (caught by runner's non-fatal flag).
  - Source URL that itself fails `safe_fetch` (e.g. private IP) →
    skip source-page branch, fall through to Tavily. **NOTE:** this
    edge case requires the function to catch `SafeFetchError` on the
    *source page fetch* specifically, then continue to Tavily;
    that's a single try/except in the function body — document
    it explicitly in the function docstring.

- **D-16: Tavily tool test** (`tests/agent/tools/test_tavily_image_search.py`):
  - Mocked `TavilyClient` returns an `images` list — function
    returns the list verbatim.
  - Empty `images` list → function returns `[]`.
  - `TAVILY_API_KEY` unset → raises informative `RuntimeError`
    (mirrors `WebSearchTool` behavior).

- **D-17: `safe_fetch` extension test** — verify
  `expected_content_type="image/*"` wildcard accepts `image/jpeg`,
  `image/png`, `image/webp`, rejects `text/html` and `application/pdf`.
  (If `safe_fetch.py` already supports the wildcard per Phase 23 D-16,
  this is just an assertion test; if not, Phase 24 fixes the sniff and
  this test enforces it.)

- **D-18: `finalize-outcome` test extension**
  (`tests/queue/test_finalize_outcome.py`, extend):
  - `image_present=True` when artifact has non-empty `image_url`.
  - `image_present=False` when artifact is `StepUnavailableArtifact`.
  - `image_present=False` when artifact has `image_url=None`.
  - `image_present=False` when no `recipe-image` artifact present
    (legacy/missing — defensive default).

- **D-19: Workflow registry test extension**
  (`tests/agents/test_workflow_registry.py` or similar):
  - Both variants have 7 steps total (gather + 6-step tail).
  - `recipe-image` step has `non_fatal_on_failure=True`.
  - All other steps have `non_fatal_on_failure=False` (default).
  - `build_recipe_tail()` returns the expected 6-step list.

- **D-20: Manual eval is the load-bearing user-facing gate**
  (D-09..D-13 above). Operator-driven. Phase 24 verification routes
  as `human_needed` until the operator commits `24-SMOKE.md` with
  `verdict: pass`. Same pattern as Phase 21/22/23.

### Claude's Discretion

- **`tavily_image_search` query construction:** `f"{recipe.name} receta"`
  (Spanish-language hint biases toward Spanish-source food photos).
  Tunable in v1.2 if eval shows poor relevance (could be `f"{recipe.name}
  food"` or per-locale). Single-string hardcoded in v1.1.
- **Order of plan execution (planner final):**
  - **Plan 24-01 (FIRST commit):** `WorkflowStepDef.non_fatal_on_failure`
    field + `StepUnavailableArtifact` model + runner extension
    (`_finalize_step_unavailable`) + `run_task` exception-handling
    branch + comprehensive tests (D-14). No `recipe-image` step
    yet — the capability lands standalone.
  - **Plan 24-02:** `RecipeData.image_url` field + `RecipeImageInput`
    / `RecipeImageOutput` Pydantic models + `safe_fetch` `image/*`
    wildcard extension (if needed) + tests (D-17).
  - **Plan 24-03:** `tavily_image_search` function (or
    `TavilyImageSearchTool` class) + `TAVILY_API_KEY` test +
    `.env.example` already has the key (Phase 8).
  - **Plan 24-04:** `acquire_recipe_image` deterministic function
    in `src/robotina/agent/tasks/recipe_image.py` + tests (D-15).
  - **Plan 24-05:** `build_recipe_tail()` helper + workflow registry
    composition refactor (D-06) + `recipe-load`'s `build_input`
    artifact-key swap (D-06b) + `recipe-image` `run_task` branch in
    `jobs.py` (D-02) + workflow registry tests (D-19).
  - **Plan 24-06:** `finalize-outcome` reads `recipe-image` artifact
    + `image_present` flip (D-07) + tests (D-18).
  - **Plan 24-07:** `experiments/recipe_image.py` + `24-IMG-EVAL-SET.md`
    (10-15 rows) + `pyproject.toml` entry + CLAUDE.md table update
    (EXP-06).
  - **Plan 24-08:** `experiments/robotina_wake.py` + `pyproject.toml`
    entry + CLAUDE.md table update.
  - **Plan 24-09 (autonomous=false):** Operator runs eval against
    Tavily live; commits `24-IMG-EVAL-RESULTS-<backend>.md` +
    `24-SMOKE.md`; ticks REQUIREMENTS.md IMG-01..06 + EXP-01 +
    EXP-03 + EXP-04 + EXP-06.

- **No new dependency.** `recipe-scrapers` (Phase 8) and `tavily-python`
  (Phase 8) are already declared. `httpx` and `safe_fetch` are reused.
  No PIL needed (we don't decode bytes).
- **No new Alembic revision.** Phase 24 is code + new task type + new
  field on existing JSON shape. `RecipeData.image_url` is a JSON-payload
  field, not a DDL column on a SQL table (RecipeData is the artifact
  shape, not a SQLAlchemy model).
- **EXP-01 satisfaction:** existing experiment scripts
  (`experiments.recipe_research`, `experiments.recipe_load`,
  `experiments.gather_from_url`) remain runnable unchanged because:
  - `RecipeData.image_url` is added with default `None`; old fixtures
    that don't specify it still validate.
  - No task input schema is renamed or restructured (only `RecipeImageInput`
    is NEW; existing inputs are untouched).
- **CLAUDE.md experiment table** (EXP-06) — extend the existing
  "Recommended Stack > Experiment scripts" subsection (if it has a
  table) or add a new "Experiments" section at top-level. Planner
  decides exact placement; entries needed:
  `experiments.recipe_image` and `experiments.robotina_wake` with one-
  line descriptions. Existing entries (`recipe_research`,
  `recipe_load`, `gather_from_url`) listed too if missing.
- **`feedback_overrides_in_sync` does NOT apply** — `recipe-image` is
  agent-less; no `AGENT_REGISTRY` entry, no `overrides/*.json` blocks
  needed. (If planning later decides to wrap the deterministic task
  in an LLM agent for some reason, overrides MUST be added in the
  same commit.)
- **`feedback_env_example` — no new env var** in v1.1. Tavily key is
  already declared (Phase 8). If Pitfall-8 mitigation lands in v1.2
  with a vision model, that adds a new env var.
- **Dashboard `_macros.html` label** — add `"recipe-image": "Imagen"`
  to TASK_TYPE_LABELS (Phase 21 D-11 pattern).
- **Tavily quality risk:** Pitfall 8's "wrong dish" failure mode is
  the largest v1.1 risk. The manual eval is the empirical gate; if
  it fails (<60% relevant images on the eval set), the v1.1 ship is
  blocked pending vision-LLM v1.2 follow-up. Document this in
  `24-SMOKE.md`'s verdict-section template.
- **Memory `feedback_no_task_id_in_code`:** no "Phase 24" tags or
  "quick task NNNNNN-xxx" in code/comments — D-NN refs are durable.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 24: Recipe images (Topic 3)" — phase goal, 5 success criteria, dependency on Phase 23, the `recipe-image` step insertion + non-fatal runner capability.
- `.planning/REQUIREMENTS.md` IMG-01..06 — the six image-acquisition requirements.
- `.planning/REQUIREMENTS.md` EXP-01, EXP-03, EXP-04, EXP-06 — the four experiment-related requirements satisfied in this phase.

### Architecture and pitfalls (load-bearing context)
- `.planning/research/PITFALLS.md` Pitfall 6 "SSRF and resource-exhaustion via user-supplied URL" — `safe_fetch` reuse mandate for image URL validation (D-13).
- `.planning/research/PITFALLS.md` Pitfall 8 "Recipe-image source returns the wrong dish" — Tavily quality risk; D-11 documents the v1.1 stance (top-result + source-page bypass; vision-LLM deferred to v1.2 gated on eval).
- `.planning/research/ARCHITECTURE.md` §"Phase H — recipe-image" (lines ~180-200, ~291, ~419-422, ~492-543) — recipe-image insertion between metadata and load; non-fatal failure handling design; AGENT_REGISTRY rationale for v1; recommended structured "unavailable" artifact pattern.
- `.planning/research/ARCHITECTURE.md` §"Anti-Pattern 3: Make `recipe-image` a regular step that's allowed to fail" — the runner-level non-fatal flag is intentional, NOT a "swallow all exceptions silently" pattern; only marked steps are non-fatal.
- `.planning/research/STACK.md` — `tavily-python` (already declared Phase 8) + `recipe-scrapers>=15.11.0` (already declared Phase 8). No new deps for Phase 24.
- `.planning/research/SUMMARY.md` §"Phase H" (line ~121, ~138, ~158) — Tavily-image-search quality is the largest unknown; Phase 24's eval (D-09..D-13) is the empirical validation. Vision-LLM escalation deferred to <60% usable threshold.
- `.planning/research/FEATURES.md` §"Image URL associated with each saved recipe" (lines 143-209) — must-have feature shape; URL pin vs rehost analysis; `safe_fetch` reuse note.

### Prior phase context (carries forward — do NOT re-decide)
- `.planning/phases/23-url-ingestion-topic-2/23-CONTEXT.md` — Phase 23 decisions. Phase 24 inherits:
  - D-01 per-source workflow variants (rename + paired entries) — extends with `build_recipe_tail()` helper (Phase 24 D-06).
  - D-14..D-17 `safe_fetch` design — Phase 24 reuses unchanged; only extends caller-side usage (`expected_content_type="image/*"`, larger `max_bytes`).
  - D-08 `WorkflowOutcomeSummary.recipe_query` dual semantic — unchanged by Phase 24.
  - D-09 manual eval pattern — Phase 24 mirrors (24-IMG-EVAL-SET, 24-IMG-EVAL-RESULTS-<backend>, 24-SMOKE).
  - D-23 AGENT_REGISTRY ↔ overrides CI guard — N/A for Phase 24 (agent-less task).
- `.planning/phases/22-multi-recipe-per-message-topic-1/22-CONTEXT.md` — D-08 wake helper's `recipe_query` semantic; Phase 24 doesn't touch.
- `.planning/phases/21-tool-surface-flip-remove-acknowledge-notify/21-CONTEXT.md` — D-11 dashboard label map (`_macros.html` TASK_TYPE_LABELS); Phase 24 adds `"recipe-image": "Imagen"`.
- `.planning/phases/20-wake-rule-outcome-plumbing/20-CONTEXT.md` — `finalize-outcome` deterministic agent-less branch pattern (Phase 24 D-02 mirrors); `AddRecipeOutcome` shape; `WorkflowOutcomeSummary` envelope.
- `.planning/phases/18-robotinainvocation-entity/18-CONTEXT.md` D-13 — constructor-injected `invocation_id` on StartWorkflowTool. KEEP unchanged.
- `.planning/phases/17-conversation-fk-closure/17-CONTEXT.md` D-03/D-04 — constructor-injected `conversation_id`. KEEP.
- `.planning/phases/15-…/` — `RecipeData` accumulator pattern (Phase 24 D-03 mirrors for `RecipeImageOutput`); each step emits the full RecipeData dump, never a wrapper.
- `.planning/phases/11-structured-agent-output-via-response-format/11-CONTEXT.md` — `response_format=<Pydantic class>` on `create_agent`. N/A for `recipe-image` (agent-less task in v1.1).
- `.planning/phases/12-middleware-based-agent-instrumentation/12-CONTEXT.md` — middleware-based LangWatch instrumentation; deterministic tasks emit plain OTel spans (no LangChain middleware), which is fine.

### Existing codebase contracts (current state)
- `src/robotina/queue/task_types.py:105` `RecipeData` — Phase 24 D-04 adds `image_url: str | None = None` field.
- `src/robotina/queue/task_types.py:175` `AddRecipeQueryInput`, `task_types.py:187` `AddRecipeUrlInput` — unchanged.
- `src/robotina/queue/task_types.py:352` `AddRecipeOutcome` — Phase 24 keeps `image_present: bool = False` field declaration; flips the producer logic in `jobs.py`.
- `src/robotina/queue/task_types.py:385` `WorkflowOutcomeSummary` — unchanged.
- `src/robotina/agent/workflows.py:32` `WorkflowStepDef` — Phase 24 D-01 adds `non_fatal_on_failure: bool = False` field.
- `src/robotina/agent/workflows.py:50` `WorkflowDefinition` — unchanged.
- `src/robotina/agent/workflows.py:68` `WORKFLOW_REGISTRY` — Phase 24 D-06 refactors both variants to compose `[gather_step] + build_recipe_tail()`.
- `src/robotina/queue/workflow_runner.py` — Phase 24 D-01 adds `_finalize_step_unavailable` helper (mirrors `_finalize_step_failure` but routes through DONE-path advancement); modifies the exception-handling branch of `run_task` (called from `jobs.py`) to dispatch on the flag.
- `src/robotina/queue/workflow_runner.py:52` `_compose_failure_outcome` — Phase 24 D-01 reuses the reason-truncation logic for the unavailable artifact's `reason` field.
- `src/robotina/queue/jobs.py:119` `finalize-outcome` deterministic branch — Phase 24 D-02 mirrors this pattern for `recipe-image`; Phase 24 D-07 extends `finalize-outcome` to read `artifacts["recipe-image"]` and compute `image_present`.
- `src/robotina/queue/jobs.py:131` `image_present=False` hardcoded line — Phase 24 D-07 replaces with the artifact-driven boolean.
- `src/robotina/queue/jobs.py:302` `WebSearchTool` import — Phase 24 D-12 adds a sibling import `from robotina.agent.tools.tavily_image_search import tavily_image_search`.
- `src/robotina/agent/tools/web_search.py` — Phase 24 D-12 adds sibling `src/robotina/agent/tools/tavily_image_search.py`.
- `src/robotina/url/safe_fetch.py` — Phase 24 D-13 reuses (extending if needed: confirm `image/*` wildcard sniff works; add it if it doesn't).
- `src/robotina/agent/tools/fetch_and_scrape.py` — Phase 24 reuses for source-page HTML fetching internally in `acquire_recipe_image` (or duplicates the safe_fetch + recipe_scrapers calls — planner's call; helper extraction may be premature).
- `src/robotina/dashboard/templates/_macros.html` — Phase 24 adds `"recipe-image": "Imagen"` to TASK_TYPE_LABELS.
- `experiments/recipe_research.py`, `experiments/recipe_load.py`, `experiments/gather_from_url.py` — existing experiment script pattern. `experiments/recipe_image.py` + `experiments/robotina_wake.py` follow.
- `pyproject.toml` `[project.scripts]` — Phase 24 adds `experiments.recipe_image` and `experiments.robotina_wake`.
- `pyproject.toml` `[project.dependencies]` — UNCHANGED. `tavily-python` already declared (Phase 8). `recipe-scrapers` already declared (Phase 8).
- `.env.example` — UNCHANGED. `TAVILY_API_KEY` already declared (Phase 8).

### Project conventions
- `CLAUDE.md` "LangWatch instrumentation must be active during both production and experiment runs" — the eval scripts MUST tag traces (`phase=24`, `recipe_name=…`, `branch=…`).
- `CLAUDE.md` experiment table (EXP-06) — Phase 24 adds two entries.
- Memory `feedback_avoid_premature_abstraction` — D-02 (deterministic task, not LLM agent), D-05 (URL pin, no ENV flag), D-08 (no V008 fork), D-11 (no vision-LLM in v1.1), D-12 (concrete TavilyImageSearchTool, not abstract base).
- Memory `feedback_prompts_language` — N/A in v1.1 (no new prompts; `recipe-image` is agent-less; `robotina_wake` exercises existing V007 prompt).
- Memory `feedback_overrides_in_sync` — N/A in v1.1 (no new agent registry entry).
- Memory `feedback_env_example` — N/A in v1.1 (no new env vars).
- Memory `feedback_test_before_handoff` — D-10 `experiments.robotina_wake` IS the pre-handoff smoke for V007 wake-context behavior; D-20 operator runs eval before reporting Phase 24 complete.
- Memory `feedback_queue_at_front` — unchanged; recipe-image doesn't touch the notification path.
- Memory `feedback_no_task_id_in_code` — no "Phase 24" / quick-task tags; D-NN refs in comments are durable.
- Memory `project_compose_agent_vision` — D-08 defers wake-reply image-aware text to the future Compose agent.
- Memory `project_local_dev_setup` — agent runs on host; Ollama dev / OpenAI staging; the eval scripts run from host via `uv run experiments.recipe_image` and `uv run experiments.robotina_wake`. **CRITICAL for safe_fetch:** the Tavily-returned image URLs MUST pass `safe_fetch`'s SSRF defenses — local-network image hosts would be blocked (intentionally).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`safe_fetch` (Phase 23)** — `src/robotina/url/safe_fetch.py` with six SSRF defenses. Phase 24 reuses with `expected_content_type="image/*"` and `max_bytes=15_000_000` (D-13).
- **`WebSearchTool` Tavily wrapper (`src/robotina/agent/tools/web_search.py`)** — Phase 24 mirrors shape for `tavily_image_search` (D-12). Same `TAVILY_API_KEY` env var, same `TavilyClient`.
- **`finalize-outcome` deterministic agent-less branch (`jobs.py:119`)** — Phase 24 D-02 mirrors the pattern for `recipe-image` (no agent, no prompt, no LLM call). Already-existing precedent for agent-less task types.
- **`_compose_failure_outcome` reason-truncation (`workflow_runner.py:52`)** — Phase 24 D-01 reuses the truncation logic for `StepUnavailableArtifact.reason`.
- **`recipe-scrapers` `.image()` method** — already in stack (Phase 8); Phase 24 calls it after `safe_fetch` + `scrape_html` on the recipe's `source_url` (D-11 source-page branch).
- **`FetchAndScrapeTool` (Phase 23)** — internal pattern (safe_fetch → recipe-scrapers) is reusable for the source-page branch; planner decides whether to extract a shared helper or duplicate the few lines.
- **`AddRecipeOutcome.image_present` stub field (`task_types.py:370`)** — Phase 24 keeps the schema; just flips the producer logic.
- **Phase 21 D-11 dashboard label map** — Phase 24 adds `"recipe-image": "Imagen"`.
- **Manual eval pattern (Phase 21/22/23)** — Phase 24 mirrors with 24-IMG-EVAL-SET.md + 24-IMG-EVAL-RESULTS-<backend>.md + 24-SMOKE.md.
- **`RecipeData` accumulator pattern (Phase 15)** — `recipe-image` step emits the full RecipeData dump with `image_url` set, identical to how `recipe-research-*` steps emit each layer.

### Established Patterns
- **Agent-less task types** (`finalize-outcome`) — Phase 24 `recipe-image` follows.
- **Step-level outputs are RecipeData dumps (Phase 15)** — `RecipeImageOutput` follows.
- **`build_input` lambdas in `WORKFLOW_REGISTRY`** — Phase 24 reuses; `build_recipe_tail()` helper returns a list of `WorkflowStepDef` with inline lambdas (no parameterization).
- **Constructor-injected `invocation_id` / `conversation_id` / `household_id` (Phase 17/18 D-13)** — unchanged.
- **Prompt versioning** — no new prompt versions in Phase 24 (recipe-image is agent-less; robotina V007 unchanged).
- **Pydantic v2 with `ConfigDict(extra="forbid")`** — new models follow.
- **One concrete script per experiment** — `experiments/recipe_image.py` and `experiments/robotina_wake.py` are each single files.

### Integration Points
- `src/robotina/agent/workflows.py:32` — D-01 add `non_fatal_on_failure: bool = False` to `WorkflowStepDef`.
- `src/robotina/agent/workflows.py:68` — D-06 refactor both `WORKFLOW_REGISTRY` entries to compose `[gather_step] + build_recipe_tail()`.
- `src/robotina/agent/workflows.py` (new function) — D-06 `build_recipe_tail()` helper.
- `src/robotina/agent/tasks/recipe_image.py` (NEW module) — D-02 `acquire_recipe_image(input) -> RecipeImageOutput` deterministic function.
- `src/robotina/agent/tools/tavily_image_search.py` (NEW) — D-12 `tavily_image_search(query: str) -> list[str]` function (or `TavilyImageSearchTool` class — planner's call).
- `src/robotina/queue/task_types.py:105` — D-04 add `image_url: str | None = None` to `RecipeData`.
- `src/robotina/queue/task_types.py` (new model) — D-03 `RecipeImageInput`, `RecipeImageOutput`; D-01 `StepUnavailableArtifact`.
- `src/robotina/queue/workflow_runner.py` — D-01 `_finalize_step_unavailable` helper; modify exception-handling dispatch to check `non_fatal_on_failure` flag.
- `src/robotina/queue/jobs.py:119` — D-02 new `recipe-image` branch (mirrors `finalize-outcome` shape).
- `src/robotina/queue/jobs.py:131` — D-07 replace hardcoded `image_present=False` with `accumulated_artifacts`-driven boolean.
- `src/robotina/url/safe_fetch.py` — D-13 verify (or extend) `image/*` content-type wildcard sniff.
- `src/robotina/dashboard/templates/_macros.html` — D-21 add `"recipe-image": "Imagen"` to TASK_TYPE_LABELS.
- `experiments/recipe_image.py` (NEW) — D-09.
- `experiments/robotina_wake.py` (NEW) — D-10.
- `pyproject.toml` `[project.scripts]` — D-09, D-10 add entries.
- `CLAUDE.md` experiment list — D-09, D-10 update.
- `.planning/phases/24-recipe-images-topic-3/24-IMG-EVAL-SET.md` (NEW) — D-13.
- `.planning/phases/24-recipe-images-topic-3/24-IMG-EVAL-RESULTS-<backend>.md` (NEW — operator) — D-13.
- `.planning/phases/24-recipe-images-topic-3/24-SMOKE.md` (NEW — operator) — D-13 / D-20.
- `tests/queue/test_workflow_runner_non_fatal.py` (NEW) — D-14.
- `tests/agent/tasks/test_recipe_image.py` (NEW) — D-15.
- `tests/agent/tools/test_tavily_image_search.py` (NEW) — D-16.
- `tests/url/test_safe_fetch.py` (extend) — D-17 (`image/*` wildcard).
- `tests/queue/test_finalize_outcome.py` (extend) — D-18 (`image_present` computation).
- `tests/agent/test_workflow_registry.py` (extend) — D-19 (`build_recipe_tail` + non_fatal flag assertions).
- `.planning/REQUIREMENTS.md` — tick IMG-01..06 + EXP-01 + EXP-03 + EXP-04 + EXP-06 in the final smoke commit.

</code_context>

<specifics>
## Specific Ideas

- **The non-fatal capability is the load-bearing architectural change.**
  IMG-06 calls it out explicitly; D-01 lands it as a runner-level flag
  (declared at step-definition level), with a structured
  `StepUnavailableArtifact` so downstream consumers (`finalize-outcome`,
  `recipe-load`) can distinguish "image unavailable" from "image_url
  is the empty string". Plan 24-01 lands it FIRST, standalone, before
  `recipe-image` exists — same TDD pattern as Phase 23's `safe_fetch`
  FIRST commit.
- **Pitfall 8 is the largest v1.1 risk.** Tavily image-search quality
  on regional Spanish/Argentine/Uruguayan recipe names is unknown.
  D-09's manual eval IS the empirical validation. If <60% relevant,
  vision-LLM mitigation lands as a v1.2 follow-up.
- **The deterministic `recipe-image` task type is intentional simplicity.**
  No LLM, no prompt, no agent registry entry. `feedback_avoid_premature_abstraction`
  prevents adding LLM machinery for a single-string-output mechanical task.
  Convert to LLM agent ONLY when vision-LLM v1.2 mitigation lands.
- **URL pin (D-05) is the v1.1 stance.** Backend coordination is
  minimal (one new field on the recipe entity). Download-and-upload
  needs a NEW backend endpoint that hasn't been committed.
- **Shared-tail helper extraction is a deferred-from-Phase-23 commitment.**
  D-06 acts on the explicit Phase 23 D-01 directive ("extract a helper
  in Phase 24"). 6 shared steps × 2 variants is past the duplication
  threshold.
- **`safe_fetch` reuse is universal.** Same helper, same six defenses,
  with `image/*` content-type and 15 MB cap. The local-dev
  `127.0.0.1` SSRF caveat (`project_local_dev_setup` memory) applies:
  Tavily would never return a private-IP URL in practice, but the
  defense fires anyway.

</specifics>

<deferred>
## Deferred Ideas

- **Vision-LLM "is this the right dish?" check** (Pitfall 8 full
  mitigation) — v1.2 follow-up phase. Gated on Phase 24 eval results
  (<60% Tavily image relevance → escalate; >60% → defer further).
- **Image download-and-rehost to household-manager backend** (IMG-05
  alternative) — needs NEW backend upload endpoint; v1.2 candidate
  when broken-link sweep + EXIF strip become priorities.
- **EXIF strip + magic-byte validation via PIL** — only relevant when
  we redistribute bytes; v1.2 alongside rehost.
- **Periodic broken-link sweep** — deferred to scheduler milestone
  (per Pitfall 8 / SUMMARY.md).
- **Multi-candidate retry on safe_fetch failure** — v1.1 ships with
  top-result only; v1.2 may iterate to `images[1..N]` on miss.
- **Per-locale Tavily query templating** — v1.1 uses
  `f"{recipe.name} receta"` hardcoded; per-locale (`mexicana`,
  `argentina`, `española`) is a tuning knob for v1.2 if eval shows
  regional bias.
- **Wake-reply "guardé X, pero sin foto" sentence (V008 fork)** — v1.2
  candidate; better owned by the future Compose agent
  (`project_compose_agent_vision`).
- **LangWatch-driven A/B testing of Tavily query phrasings** — v1.3.
- **Image quality / resolution filtering** (reject thumbnails <
  400px wide) — Pitfall 8 documents this risk; deferred.
- **AI image generation as a fallback** — explicitly rejected in
  SUMMARY.md / FEATURES.md for v1; cost (~$0.04/image) and "plastic
  food" quality. Not on the v1.x roadmap.
- **`hint` field on RecipeImageInput** (e.g. user-provided "use a
  rustic vibe" context) — not a real user request; speculative.
- **Image source diversification** (Unsplash + Pexels in addition to
  Tavily) — single source in v1.1 is fine; revisit only if Tavily
  hit-rate is poor AND a multi-source orchestration buys clear quality
  improvement.

</deferred>

---

*Phase: 24-Recipe images (Topic 3)*
*Context gathered: 2026-05-22*
