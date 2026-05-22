---
phase: 24-recipe-images-topic-3
plan: 04
subsystem: agent

tags: [recipe-image, deterministic-task, safe-fetch, tavily, recipe-scrapers, fallback-ladder, agent-less]

# Dependency graph
requires:
  - phase: 24-recipe-images-topic-3
    provides: "24-01 — StepUnavailableArtifact + non_fatal_on_failure flag; 24-02 — RecipeImageInput/Output + RecipeData.image_url + safe_fetch image/* wildcard sniff; 24-03 — tavily_image_search plain function"
provides:
  - "acquire_recipe_image(input) deterministic function — owns the IMG-02 fallback ladder (source-page .image() → Tavily → miss raises RecipeImageAcquisitionError)"
  - "RecipeImageAcquisitionError exception type — wraps the all-branches-missed condition; runner converts to StepUnavailableArtifact via non_fatal_on_failure (24-01)"
  - "Validation contract — safe_fetch(image/*, max_bytes=15_000_000); SafeFetchError propagates unmodified (Pitfall 6 / D-11)"
  - "src/robotina/agent/tasks/ package — new home for deterministic agent-less task functions; mirrors finalize-outcome pattern"
affects: [24-05, 24-06, recipe-load, finalize-outcome, recipe-image]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Agent-less deterministic task (D-02): plain function under src/robotina/agent/tasks/, no AGENT_REGISTRY entry, no LLM, no prompt"
    - "Lazy intra-function imports for heavy deps (recipe_scrapers, safe_fetch, tavily) — matches FetchAndScrapeTool convention"
    - "Asymmetric SafeFetchError handling — source-page fetch wraps try/except (fall-through to Tavily); validation safe_fetch is bare (propagates so runner's non_fatal flag absorbs it generically)"
    - "Test mocking targets source modules (robotina.url.safe_fetch.safe_fetch, robotina.agent.tools.tavily_image_search.tavily_image_search, recipe_scrapers.scrape_html) because the consumer uses lazy imports"

key-files:
  created:
    - "src/robotina/agent/tasks/__init__.py — package marker"
    - "src/robotina/agent/tasks/recipe_image.py — acquire_recipe_image + RecipeImageAcquisitionError"
    - "tests/agent/tasks/__init__.py — test-package marker"
    - "tests/agent/tasks/test_recipe_image.py — six D-15 unit tests"
  modified: []

key-decisions:
  - "Validation safe_fetch is intentionally NOT inside try/except — SafeFetchError propagates so the runner's non_fatal_on_failure flag handles it generically (D-11). RecipeImageAcquisitionError is reserved for the all-branches-missed condition only."
  - "Source-page SafeFetchError IS caught and falls through to Tavily — the RFC1918 / blocked-IP edge case must not break the workflow when a fallback exists (D-15 case 6)."
  - "Lazy imports inside acquire_recipe_image — matches FetchAndScrapeTool._run convention and keeps the module import light. Test mocks therefore target source modules, not consumer modules."

patterns-established:
  - "agent-less deterministic task: function lives under src/robotina/agent/tasks/, dispatches happen in workflow_runner / run_task (24-05), no AGENT_REGISTRY entry, no LLM, no prompt"
  - "asymmetric SafeFetchError handling — fetch-stage catches (fall-through to next branch); validation-stage propagates (runner absorbs)"
  - "Spanish-language Tavily query convention: f\"{recipe.name} receta\" (matches the family-of-Spanish-speakers product context)"

requirements-completed: [IMG-02, IMG-04]

# Metrics
duration: 8min
completed: 2026-05-22
---

# Phase 24 Plan 04: acquire_recipe_image Summary

**Deterministic agent-less recipe-image acquisition with source-page → Tavily fallback ladder and safe_fetch image/* validation (15 MB cap)**

## Performance

- **Duration:** ~8 min
- **Completed:** 2026-05-22T21:17:43Z
- **Tasks:** 2
- **Files created:** 4

## Accomplishments
- `acquire_recipe_image(input)` deterministic function owning the IMG-02 fallback ladder
- `RecipeImageAcquisitionError` for the all-branches-missed condition (runner converts to `StepUnavailableArtifact`)
- IMG-04 validation contract pinned: `safe_fetch(image/*, max_bytes=15_000_000)`; `SafeFetchError` propagates unmodified
- Six D-15 unit tests covering every branch of the ladder (happy path, source-page miss, Tavily-only, Tavily-empty, validation-error-propagates, source-page-blocked-falls-through)
- New `src/robotina/agent/tasks/` package marker — home for future deterministic agent-less tasks

## Task Commits

Each task was committed atomically:

1. **Task 1: Create agent/tasks package + acquire_recipe_image function** — `a0c4962` (feat)
2. **Task 2: Create D-15 unit tests for acquire_recipe_image** — `8f85c7a` (test)

## Files Created/Modified
- `src/robotina/agent/tasks/__init__.py` — package marker (empty)
- `src/robotina/agent/tasks/recipe_image.py` — `acquire_recipe_image` deterministic function + `RecipeImageAcquisitionError` exception (108 lines)
- `tests/agent/tasks/__init__.py` — test-package marker (empty)
- `tests/agent/tasks/test_recipe_image.py` — six D-15 unit tests (187 lines)

## Decisions Made
- **Validation-stage SafeFetchError propagates intentionally.** The validation `safe_fetch(image/*)` call is NOT wrapped in try/except. The runner's `non_fatal_on_failure` flag (24-01) absorbs both `SafeFetchError` and `RecipeImageAcquisitionError` into a `StepUnavailableArtifact` generically. This keeps the function's exception surface explicit (one class for "nothing found"; raw `SafeFetchError` for "candidate rejected").
- **Source-page SafeFetchError DOES fall through to Tavily.** A recipe whose `source_url` lives on an RFC1918 / blocked IP must not break the workflow when a perfectly valid Tavily fallback exists. Documented as D-15 case 6.
- **Lazy imports throughout.** `safe_fetch`, `tavily_image_search`, and `scrape_html` are all imported inside the function body — matches `FetchAndScrapeTool._run` (Phase 23) convention and keeps module import-time light.

## Deviations from Plan

None - plan executed exactly as written. The verbatim function body provided in the plan compiled cleanly and the six tests passed on the first run.

## Issues Encountered

None.

## Verification

- `uv run python -c "from robotina.agent.tasks.recipe_image import acquire_recipe_image, RecipeImageAcquisitionError; ..."` → `ok`
- `uv run pytest tests/agent/tasks/test_recipe_image.py -x -q` → 6 passed in 0.53s
- `uv run pytest tests/agent/ -q` → 10 passed (full agent suite green)
- `grep -rn "recipe-image" src/robotina/agent/agents.py` → 0 matches (D-02 agent-less confirmed; no AGENT_REGISTRY entry added)

## User Setup Required

None - no external service configuration required (TAVILY_API_KEY already provisioned in 24-03).

## Next Phase Readiness

- **24-05 (workflow_runner wiring):** `acquire_recipe_image` is ready to be dispatched as a deterministic branch in `run_task`. Function signature `(input: RecipeImageInput) -> RecipeImageOutput` matches the runner's other agent-less task callsites (`finalize_outcome`).
- **Step config:** the recipe-image step should be registered with `WorkflowStepDef.non_fatal_on_failure=True` so both `RecipeImageAcquisitionError` and `SafeFetchError` are converted to `StepUnavailableArtifact` via `_finalize_step_unavailable`.
- **Downstream consumers (recipe-load, finalize-outcome):** can rely on `recipe.image_url` being set to a safe_fetch-validated URL OR the artifact being a `StepUnavailableArtifact` (then `image_present=False` in `AddRecipeOutcome`).

## Self-Check: PASSED

Verified files exist:
- `src/robotina/agent/tasks/__init__.py` — FOUND
- `src/robotina/agent/tasks/recipe_image.py` — FOUND
- `tests/agent/tasks/__init__.py` — FOUND
- `tests/agent/tasks/test_recipe_image.py` — FOUND

Verified commits exist:
- `a0c4962` — FOUND (Task 1)
- `8f85c7a` — FOUND (Task 2)

---
*Phase: 24-recipe-images-topic-3*
*Completed: 2026-05-22*
