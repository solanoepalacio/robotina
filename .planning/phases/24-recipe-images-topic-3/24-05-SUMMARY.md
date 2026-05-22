---
phase: 24-recipe-images-topic-3
plan: 05
subsystem: queue
tags: [workflow-registry, jobs-dispatch, recipe-image, non-fatal-step, langwatch-trace, inline-duplication]

# Dependency graph
requires:
  - phase: 24-recipe-images-topic-3
    plan: 01
    provides: "WorkflowStepDef.non_fatal_on_failure field + _finalize_step_unavailable helper + outer-except dispatch in run_task"
  - phase: 24-recipe-images-topic-3
    plan: 02
    provides: "RecipeImageInput / RecipeImageOutput task-types + RecipeData.image_url field"
  - phase: 24-recipe-images-topic-3
    plan: 04
    provides: "acquire_recipe_image deterministic function (fallback ladder + safe_fetch image/* validation)"
provides:
  - "WORKFLOW_REGISTRY[add-recipe-from-query] and [add-recipe-from-url] both carry the recipe-image step + load-key swap (inline-duplicated per D-06)"
  - "run_task deterministic branch for task_type=='recipe-image' with own langwatch.trace wrap (Pitfall 8)"
  - "Pitfall 6 fallback at load.build_input: artifacts['metadata'] when recipe-image artifact has status=='unavailable'"
  - "Inline non-fatal dispatch in the recipe-image branch's except (registry-lookup → _finalize_step_unavailable)"
  - "D-19 workflow-registry tests (6 new parametrized functions covering both variants)"
affects: [24-06, 24-07, 24-08, 24-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Inline-duplicated workflow tail across both registry variants (D-06 — NO shared helper, recipe-quality iteration churns the tail)"
    - "Deterministic agent-less branch with its own LangWatch trace wrap (Pitfall 8 — branches that return before the LLM-path wrap need their own)"
    - "Inline non-fatal dispatch in deterministic branch except (registry-lookup → _finalize_step_unavailable) — agent-less branches sit outside the outer try where 24-01's dispatch lives"

key-files:
  modified:
    - "src/robotina/agent/workflows.py"
    - "src/robotina/queue/jobs.py"
    - "tests/queue/test_workflow_registry.py"
    - "tests/queue/test_workflow_runner_non_fatal.py"
    - "tests/test_workflows.py"

key-decisions:
  - "Inlined the Phase 24 / D-01 non-fatal dispatch directly inside the recipe-image branch's except. Rationale: deterministic agent-less branches sit OUTSIDE the outer try where 24-01 lives, so a plain `raise` bypasses the dispatch. Inlining preserves the contract (StepUnavailableArtifact + DONE-path advancement when non_fatal_on_failure=True) without restructuring run_task. Diverges from the plan's verbatim code (which had a bare `raise` with a comment claiming the outer except would handle it — that comment was a documented bug)."
  - "Extended tests/queue/test_workflow_registry.py rather than creating tests/agent/test_workflow_registry.py — the plan explicitly directs 'extend it' when an existing workflow_registry test file is found via Grep."
  - "Updated three pre-existing tests broken by the index shift (test_url_variant_has_six_steps, test_url_variant_load_reads_metadata_artifact, the four step-count tests in tests/test_workflows.py, and test_strict_step_still_fails_workflow). Auto-fixed under Rule 1 — they were correct against the pre-24-05 workflow shape and stale against the post-24-05 shape."

patterns-established:
  - "Deterministic branches that return before the bottom LLM-path LangWatch wrap MUST add their own langwatch.trace wrap (Pitfall 8 — applies prospectively to any future agent-less task_type)"
  - "Deterministic branches that respect non_fatal_on_failure MUST inline the registry-lookup → _finalize_step_unavailable dispatch in their except, because the outer-except dispatch in 24-01 only fires for code inside the outer try"

requirements-completed:
  - IMG-01
  - IMG-03
  - IMG-05

# Metrics
duration: ~25min
completed: 2026-05-22
---

# Phase 24 Plan 05: Workflow registry wiring + jobs dispatch Summary

**recipe-image inserted inline-duplicated into both add-recipe variants (D-06), recipe-load.build_input swapped to read recipe-image artifact with Pitfall-6 fallback (D-06b), and run_task gained the deterministic recipe-image branch with its own LangWatch trace wrap and inline non-fatal dispatch.**

## Performance

- **Duration:** ~25 minutes
- **Tasks:** 3 / 3
- **Files modified:** 2 source files + 3 test files
- **Commits:** 2 task commits

## A3 Pre-flight

**Verdict: A3 DEFERRED — gate at 24-09 operator smoke.**

Required env vars (`HOUSEHOLD_MANAGER_BASE_URL`, `HOUSEHOLD_MANAGER_API_KEY`, `HOUSEHOLD_ID`) are unset in the executor environment (no `.env` file in this worktree). Default fallback (`http://localhost:3001`) is also unreachable from the executor environment (connection refused).

Per the plan's verdict table:

| Status | Verdict | Action |
|--------|---------|--------|
| 5xx / network unreachable | A3 DEFERRED | Document; proceed; gate at 24-09 |

**Action taken:** Proceeded with Tasks 2 and 3. The 24-09 operator-driven manual smoke MUST verify that the live household-manager dev backend accepts `image_url: str | null` on the recipe POST. If the backend rejects the field, 24-09 surfaces a P0 blocker.

**Notes for 24-09 operator:**
- Send a minimal POST `/api/recipes` body that includes `"image_url": "https://example.com/test.jpg"` (camelCase keys per `CreateRecipeBody` schema in `household_manager_api.py`: `name`, `description`, `servingsQty`, `servingsUnit`, `prepTime`, `cookTime`, `totalTime`, `sourceUrl`, `ingredients`, `steps`).
- Use the `Authorization: Bearer $HOUSEHOLD_MANAGER_API_KEY` header (the tool uses `Bearer`, not `Token`).
- Expected outcome: 2xx (preferably with the saved recipe row carrying the URL).
- If 4xx with body mentioning `image_url` as an unknown / unexpected field → P0 blocker; halt Phase 24 deploy.

## Accomplishments

### Task 1 — A3 pre-flight verification

- Inspected `src/robotina/agent/tools/household_manager_api.py` to confirm POST `/api/recipes` payload shape (`CreateRecipeBody` Pydantic model with camelCase keys, `Authorization: Bearer` auth).
- Confirmed `.env.example` declares `HOUSEHOLD_MANAGER_BASE_URL` and `HOUSEHOLD_MANAGER_API_KEY`.
- Probed default `http://localhost:3001/api/recipes` from the executor environment — connection refused.
- Recorded A3 DEFERRED verdict (see `## A3 Pre-flight` above).
- No source file changes; no commit.

### Task 2 — Workflow registry inline-duplication (commit `a40b30c`)

- Added `RecipeImageInput` to the `from robotina.queue.task_types import (...)` block.
- Inserted `recipe-image` `WorkflowStepDef` VERBATIM between `metadata` and `load` in BOTH `add-recipe-from-query` and `add-recipe-from-url` registry entries (`task_type="recipe-image"`, `non_fatal_on_failure=True`, `build_input=lambda ... RecipeImageInput(recipe=RecipeData(**artifacts["metadata"]), ...)`).
- Updated each variant's `load` `build_input` to read `artifacts["recipe-image"]` on the happy path, with a Pitfall-6 fallback to `artifacts["metadata"]` when the upstream artifact has `status == "unavailable"`.
- Both variants now have exactly 7 steps: `gather` (or `gather-from-url`) → `instructions` → `ingredients` → `metadata` → `recipe-image` → `load` → `finalize-outcome`.
- No `build_recipe_tail()` helper extracted (D-06 — `grep -c 'build_recipe_tail\|build_tail'` returns 0).

### Task 3 — jobs.py dispatch + D-19 tests (commit `fc30836`)

- **src/robotina/queue/jobs.py** — new `if task_type == "recipe-image":` branch between `finalize-outcome` (line ~119) and the LLM-path outer `try:`. Mirrors the agent-less branch shape (no LLM, no skills, no prompt) and:
  - Calls `acquire_recipe_image(task_input)` inside its OWN `langwatch.trace(metadata={"task_type": "recipe-image", "phase": 24})` wrap with `try / except ImportError` fallback (Pitfall 8 — deterministic branches return before the bottom LLM-path LangWatch wrap, so they need their own).
  - On exception, inlines the Phase 24 / D-01 non-fatal dispatch (look up the step's `WorkflowStepDef.non_fatal_on_failure` in `WORKFLOW_REGISTRY`; when True call `workflow_runner._finalize_step_unavailable` and re-raise; otherwise call `workflow_runner.on_step_failed` and re-raise). The lookup is itself wrapped in `try/except` so lookup failures cannot mask the original exception.
- **tests/queue/test_workflow_registry.py** — extended with 6 new `@pytest.mark.parametrize("variant", _VARIANTS)` test functions (12 test cases total) covering D-19:
  1. `test_recipe_image_step_present_in_both_variants` — between metadata and load.
  2. `test_recipe_image_step_has_non_fatal_on_failure_true` — only opt-in.
  3. `test_only_recipe_image_opts_in_to_non_fatal` — no other step opts in.
  4. `test_load_build_input_falls_back_to_metadata_on_unavailable_artifact` — Pitfall 6.
  5. `test_load_build_input_uses_recipe_image_artifact_on_happy_path` — happy path.
  6. `test_each_variant_has_exactly_seven_steps` — count check.
- Updated `test_url_variant_has_six_steps` → `test_url_variant_has_seven_steps` (with new expected step list) and `test_url_variant_load_reads_metadata_artifact` → `test_url_variant_load_reads_recipe_image_artifact` (now at index 5; reads recipe-image).
- **tests/queue/test_workflow_runner_non_fatal.py** — updated `test_strict_step_still_fails_workflow` to except the legitimate `recipe-image` opt-in (this test was scoped to "no opt-ins exist at 24-01 timestamp"; 24-05 lands the first registered opt-in).
- **tests/test_workflows.py** — bumped step-count assertions 6 → 7; updated step-list expectation to include `recipe-image` between metadata and load; updated `load` happy-path test to use index 5 and read `recipe-image` artifact; updated `finalize-outcome` test to use index 6.

## Test Results

- `tests/test_workflows.py + tests/queue/test_workflow_registry.py + tests/queue/test_workflow_runner_non_fatal.py`: **35 passed**, 0 failed.
- Full repo suite: **413 passed**, 38 failed, 74 errors (baseline before this plan: 394 passed, 45 failed, 74 errors). My changes: +19 passing, -7 failures, 0 new failures.
- All 38 remaining failures are pre-existing infrastructure issues (Postgres unreachable for db/gateway/migration tests, langwatch credentials, dashboard auth). None are regressions from 24-05.

## Acceptance grep counts

| Check | Expected | Actual |
|-------|----------|--------|
| `grep -c 'step_key="recipe-image"' src/robotina/agent/workflows.py` | 2 | 2 |
| `grep -c 'non_fatal_on_failure=True' src/robotina/agent/workflows.py` | 2 | 2 |
| `grep -c 'artifacts\["recipe-image"\]' src/robotina/agent/workflows.py` | ≥2 | 2 |
| `grep -c 'status.*== "unavailable"' src/robotina/agent/workflows.py` | 2 | 2 |
| `grep -c 'build_recipe_tail\|build_tail' src/robotina/agent/workflows.py` | 0 | 0 |
| `grep -n 'RecipeImageInput' src/robotina/agent/workflows.py` | ≥3 | 3 |
| `grep -c 'if task_type == "recipe-image"' src/robotina/queue/jobs.py` | ≥1 | 1 |
| `grep -c 'langwatch.trace(' src/robotina/queue/jobs.py` | ≥2 | 3 |
| `grep -n 'metadata={"task_type": "recipe-image"' src/robotina/queue/jobs.py` | 1 | 1 |
| `grep -rn "recipe-image" src/robotina/agent/agents.py` | 0 | 0 (no AGENT_REGISTRY entry — D-02) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Plan's verbatim recipe-image branch had a non-functional `raise` with misleading comment**

- **Found during:** Task 3 placement analysis.
- **Issue:** The plan's verbatim code (24-05-PLAN.md lines 267-293) placed the new recipe-image branch OUTSIDE the outer `try:` block in `run_task`, then claimed via comment that "the outer except (Phase 24 / D-01 dispatch in 24-01) reads `WorkflowStepDef.non_fatal_on_failure=True` for this step and routes through `workflow_runner._finalize_step_unavailable`". That comment is incorrect — the outer except is at line 459 (`except Exception as exc:  # DASH-03 / Phase 13`), which only catches exceptions from code INSIDE the outer try. A plain `raise` from the recipe-image branch would propagate straight to RQ, bypassing the 24-01 non-fatal dispatch entirely. The `non_fatal_on_failure=True` flag set in Task 2 would have been silently ignored at runtime.
- **Fix:** Inlined the Phase 24 / D-01 dispatch directly inside the recipe-image branch's except (registry-lookup → `_finalize_step_unavailable` when True; `on_step_failed` otherwise; lookup itself wrapped in try/except so failures cannot mask the original exception path). Documented the divergence in the branch's banner comment.
- **Files modified:** `src/robotina/queue/jobs.py`
- **Commit:** `fc30836`

**2. [Rule 1 — Bug] Pre-existing tests stale against post-24-05 workflow shape**

- **Found during:** Task 3 full-suite verification.
- **Issue:** Adding recipe-image at index 4 shifted load to index 5 and finalize-outcome to index 6 in both variants. Six pre-existing assertions (in `tests/test_workflows.py` and `tests/queue/test_workflow_registry.py`) referenced the pre-24-05 indices and were now broken by design. One assertion in `tests/queue/test_workflow_runner_non_fatal.py` was scoped to "no opt-ins exist at 24-01 timestamp" and required updating to except the new legitimate `recipe-image` opt-in.
- **Fix:** Updated the affected tests to reflect the new 7-step shape and to recognize the new opt-in. Each updated test carries a Phase 24 comment explaining the shift.
- **Files modified:** `tests/test_workflows.py`, `tests/queue/test_workflow_registry.py`, `tests/queue/test_workflow_runner_non_fatal.py`
- **Commit:** `fc30836`

### Deferred Items

- **A3 backend pre-flight is DEFERRED.** Live verification gated to 24-09 operator smoke. See `## A3 Pre-flight` above for the exact verification instructions to run.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1    | (no code change) | A3 pre-flight DEFERRED verdict recorded above |
| 2    | `a40b30c` | feat(24-05): insert recipe-image step in both WORKFLOW_REGISTRY variants |
| 3    | `fc30836` | feat(24-05): add recipe-image deterministic branch in run_task + D-19 tests |

## Self-Check: PASSED

- File `src/robotina/agent/workflows.py` modified: FOUND
- File `src/robotina/queue/jobs.py` modified: FOUND
- File `tests/queue/test_workflow_registry.py` modified: FOUND
- File `tests/queue/test_workflow_runner_non_fatal.py` modified: FOUND
- File `tests/test_workflows.py` modified: FOUND
- Commit `a40b30c`: FOUND
- Commit `fc30836`: FOUND
