---
phase: 24-recipe-images-topic-3
plan: 06
subsystem: queue
tags: [finalize-outcome, image-present, recipe-image-artifact, derive-helper, d-07, d-18]

# Dependency graph
requires:
  - phase: 24-recipe-images-topic-3
    plan: 05
    provides: "WORKFLOW_REGISTRY carries recipe-image step inline-duplicated in both variants + jobs.py deterministic branch produces the recipe-image artifact"
provides:
  - "FinalizeOutcomeInput.recipe_image: dict | None = None (Phase 24 / D-07 wire path per RESEARCH Open Question 1)"
  - "Both add-recipe-from-query and add-recipe-from-url finalize-outcome build_input lambdas thread artifacts.get('recipe-image') into FinalizeOutcomeInput"
  - "_derive_image_present(recipe_image: dict | None) -> bool module-level helper in jobs.py covering the D-18 truth table"
  - "finalize-outcome success branch stamps image_present=_derive_image_present(task_input.recipe_image) instead of hardcoded False"
  - "4 named D-18 tests + parametrized sweep in tests/queue/test_finalize_outcome.py"
affects: [24-08, 24-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Artifact-driven outcome field derivation via small module-level helper (testable in isolation, no DB / no LLM / no run_task plumbing required)"
    - "Defensive type narrowing in artifact consumers — isinstance check + .get() pattern tolerates the StepUnavailableArtifact shape (D-01) alongside the happy-path RecipeData dump"

key-files:
  modified:
    - "src/robotina/queue/task_types.py"
    - "src/robotina/agent/workflows.py"
    - "src/robotina/queue/jobs.py"
    - "tests/queue/test_finalize_outcome.py"

key-decisions:
  - "Adopted RESEARCH Open Question 1 recommendation: extend FinalizeOutcomeInput with `recipe_image: dict | None` (workflow registry threads the artifact via build_input) rather than re-querying the artifact from the DB inside the finalize-outcome branch. Single source of truth, no extra session reads, mirrors the existing metadata/load fields."
  - "Implemented derivation as a pure module-level helper (_derive_image_present) so D-18 can be unit-tested without standing up the run_task mock stack. The integration test test_finalize_outcome_image_present_is_false continues to cover the wire path (artifact threaded from registry → input → outcome)."
  - "Updated the docstring on the pre-existing test_finalize_outcome_image_present_is_false to reflect post-D-07 derivation semantics. The test still passes (default None recipe_image → _derive_image_present returns False) — only the explanatory comment drifted, not the behavior."

patterns-established:
  - "Outcome-stamping fields driven by artifacts threaded through the workflow-input model (not re-queried from DB) — the same shape extends naturally to future outcome fields"

requirements-completed:
  - IMG-03

# Metrics
duration: ~2min
completed: 2026-05-22
---

# Phase 24 Plan 06: finalize-outcome image_present derivation Summary

**Replaced hardcoded `image_present=False` in the finalize-outcome success branch with an artifact-driven boolean; recipe-image artifact now flows registry → FinalizeOutcomeInput.recipe_image → _derive_image_present → AddRecipeOutcome.image_present.**

## Performance

- **Duration:** ~2 minutes
- **Tasks:** 3 / 3
- **Files modified:** 3 source files + 1 test file
- **Commits:** 3 task commits

## Accomplishments

### Task 1 — Extend FinalizeOutcomeInput + thread recipe_image through both workflow lambdas (commit `d5dedbc`)

- **src/robotina/queue/task_types.py** — added `recipe_image: dict | None = None` field to `FinalizeOutcomeInput` (positioned between `load` and `failure_reason`, preserving existing ordering). Docstring extended with the D-07 contract describing the three possible shapes (full RecipeData dump with image_url, StepUnavailableArtifact `{status, step_key, reason}`, None for legacy).
- **src/robotina/agent/workflows.py** — both `add-recipe-from-query` and `add-recipe-from-url` finalize-outcome `WorkflowStepDef.build_input` lambdas now pass `recipe_image=artifacts.get("recipe-image")` (inline-duplicated per D-06; no shared tail helper).
- Verification via the plan's inline Python snippet: FinalizeOutcomeInput accepts the field, defaults to None, and both variants' lambdas thread the artifact through.

### Task 2 — Flip finalize-outcome to compute image_present from recipe_image (commit `bce115a`)

- **src/robotina/queue/jobs.py** — added module-level `_derive_image_present(recipe_image: dict | None) -> bool` helper covering:
  1. `recipe_image is None` → False (legacy / no recipe-image step)
  2. `recipe_image.status == "unavailable"` → False (StepUnavailableArtifact from D-01)
  3. `recipe_image.image_url` is `None` / empty string / missing key → False
  4. `recipe_image.image_url` is a populated string → True
- Replaced the hardcoded `image_present=False` line in the `finalize-outcome` success branch with `image_present=_derive_image_present(task_input.recipe_image)`. The `status="failure"` branch is untouched — `AddRecipeOutcome.image_present` defaults to False there.
- Verification via the plan's inline Python snippet: all four boolean cases produce the correct result.

### Task 3 — Add D-18 finalize-outcome tests (commit `15e7b58`)

- **tests/queue/test_finalize_outcome.py** — added the four D-18 named tests required by the acceptance gate:
  1. `test_image_present_true_when_artifact_has_image_url`
  2. `test_image_present_false_when_artifact_unavailable`
  3. `test_image_present_false_when_image_url_is_none`
  4. `test_image_present_false_when_recipe_image_artifact_absent`
- Plus a `@pytest.mark.parametrize` sweep (`test_derive_image_present`) covering the full truth table — adds defensive coverage for `image_url == ""` and `image_url` key absent.
- Refreshed the docstring on the pre-existing `test_finalize_outcome_image_present_is_false` (test still passes — default None recipe_image derives to False — but the prior docstring incorrectly claimed "image_present is always False until the recipe-image milestone").

## Test Results

- `tests/queue/test_finalize_outcome.py`: **16 passed** (6 pre-existing finalize-outcome integration tests + 4 named D-18 + 6 parametrized D-18 cases).
- Full repo suite: **423 passed**, 38 failed, 74 errors (baseline from 24-05: 413 passed, 38 failed, 74 errors). My changes: **+10 passing, 0 new failures, 0 new errors.** All remaining failures/errors are pre-existing infrastructure issues (Postgres unreachable for db/gateway tests, langwatch credentials, dashboard auth) — none introduced by 24-06.

## Acceptance grep counts

| Check | Expected | Actual |
|-------|----------|--------|
| `grep -n "recipe_image: dict \| None" src/robotina/queue/task_types.py` | 1 match | 1 |
| `grep -c 'recipe_image=artifacts.get("recipe-image")' src/robotina/agent/workflows.py` | 2 | 2 |
| `grep -n "def _derive_image_present" src/robotina/queue/jobs.py` | 1 match | 1 |
| `grep -n "image_present=False" src/robotina/queue/jobs.py` (success branch) | 0 | 0 |
| `grep -n "image_present=_derive_image_present" src/robotina/queue/jobs.py` | ≥1 | 1 |
| `grep -c "^def test_image_present" tests/queue/test_finalize_outcome.py` | 4 | 4 |

## Deviations from Plan

### Cosmetic refresh (not a Rule 1 fix — behavior unchanged)

**1. Refreshed stale docstring on `test_finalize_outcome_image_present_is_false`**

- **Found during:** Task 3.
- **Issue:** The pre-existing test's docstring claimed "image_present is always False until the recipe-image milestone" — accurate before this plan, stale after. The test continues to pass without code change (default `recipe_image=None` derives to False via `_derive_image_present`), so the test body's behavioral assertion is still correct; only the comment drifted.
- **Fix:** Updated the docstring to explain that the test now exercises the legacy / no-recipe-image-artifact branch of the D-07 derivation.
- **Files modified:** `tests/queue/test_finalize_outcome.py`
- **Commit:** `15e7b58`

### Deferred Items

None.

## Commits

| Task | Commit    | Description |
|------|-----------|-------------|
| 1    | `d5dedbc` | feat(24-06): extend FinalizeOutcomeInput.recipe_image + thread artifact in both workflows |
| 2    | `bce115a` | feat(24-06): derive image_present from recipe-image artifact in finalize-outcome |
| 3    | `15e7b58` | test(24-06): add D-18 image_present derivation tests for finalize-outcome |

## Self-Check: PASSED

- File `src/robotina/queue/task_types.py` modified: FOUND (recipe_image field at line 525)
- File `src/robotina/agent/workflows.py` modified: FOUND (2 `recipe_image=artifacts.get("recipe-image")` occurrences)
- File `src/robotina/queue/jobs.py` modified: FOUND (`_derive_image_present` at line 29, derivation call at line 147)
- File `tests/queue/test_finalize_outcome.py` modified: FOUND (4 named D-18 tests + parametrized sweep)
- Commit `d5dedbc`: FOUND
- Commit `bce115a`: FOUND
- Commit `15e7b58`: FOUND
