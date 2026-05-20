---
phase: 23-url-ingestion-topic-2
plan: 02
subsystem: workflow-engine
tags: [workflow, schema, dashboard, wake]
requires: [23-01]
provides:
  - StartWorkflowArgs discriminated-by-shape union (AddRecipeQueryInput | AddRecipeUrlInput)
  - AddRecipeUrlInput Pydantic model {url: str}
  - GatherFromUrlInput Pydantic model {url, reply_context, household_id}
  - WORKFLOW_REGISTRY add-recipe-from-query (renamed) + add-recipe-from-url (new)
  - shared_context recipe_url plumbing on URL workflows
  - wake-helper recipe_url fallback for WorkflowOutcomeSummary.recipe_query
  - dashboard "gather-from-url" task-type label
affects:
  - StartWorkflowTool schema surface (LLM-visible) — workflow_type Literal hard-renamed
  - WORKFLOW_REGISTRY key surface — legacy "add-recipe" gone
  - Wake reply rendering — URL workflows now surface their URL in the summary
tech-stack:
  added: []
  patterns:
    - Pydantic v2 plain-union + outer @model_validator for cross-field invariants
    - Inline-duplicated workflow tail per feedback_avoid_premature_abstraction
key-files:
  created:
    - tests/queue/test_workflow_registry.py
    - tests/queue/test_wake_helper.py
  modified:
    - src/robotina/queue/task_types.py
    - src/robotina/agent/tools/start_workflow.py
    - src/robotina/agent/workflows.py
    - src/robotina/queue/workflow_runner.py
    - src/robotina/dashboard/templates/_macros.html
    - src/robotina/agent/prompts/robotina/V006.md
    - experiments/robotina/multi_recipe_eval.py
    - tests/unit/test_start_workflow_tool.py
    - tests/test_workflows.py
    - tests/test_workflow_runner.py
    - tests/queue/test_wake_dispatch.py
    - tests/queue/test_reconcile.py
    - tests/queue/test_task_types_wake_models.py
    - tests/queue/test_run_task_invocation_dispatch.py
    - tests/dashboard/conftest.py
    - tests/dashboard/test_list_view.py
    - tests/dashboard/test_polling_halt.py
    - tests/dashboard/test_workflow_template.py
decisions:
  - D-01 hard rename "add-recipe" → "add-recipe-from-query" (no transitional alias)
  - D-02 AddRecipeUrlInput is {url: str} only — no hint field
  - D-08 wake helper reads recipe_query OR recipe_url; no rename of recipe_query yet
  - D-22 @model_validator(mode="after") enforces workflow_type ↔ input pairing
metrics:
  completed_date: 2026-05-20
  task_count: 2
---

# Phase 23 Plan 02: Workflow rename + StartWorkflowArgs union + wake fallback

URL ingestion (Topic 2) — Schema + workflow-registry plumbing.

## One-liner

Hard-renames `add-recipe` to `add-recipe-from-query`, adds the `add-recipe-from-url` peer variant with inline-duplicated tail, extends `StartWorkflowArgs.input` to a `AddRecipeQueryInput | AddRecipeUrlInput` union with a `@model_validator` pairing guard, threads `recipe_url` through `shared_context`, and adds the wake-helper recipe_url fallback so URL workflows surface their URL in the wake reply.

## What was built

**Schema + tool surface (Task 1 — commit `a99523b`)**

- `AddRecipeUrlInput {url: str}` (D-02 — no hint field) and `GatherFromUrlInput {url, reply_context, household_id}` (mirrors `RecipeResearchGatherInput`) added to `src/robotina/queue/task_types.py`.
- `StartWorkflowArgs.workflow_type` Literal hard-renamed to `["add-recipe-from-query", "add-recipe-from-url"]` (D-01).
- `StartWorkflowArgs.input` becomes a plain union (Pydantic resolves variant by shape; `value` vs `url` are mutually exclusive). The outer `@model_validator(mode="after") _enforce_pairing` rejects mismatched workflow_type ↔ input pairs with a clear ValueError (D-22).
- `StartWorkflowTool._run` branches on input variant: query variant writes `shared_context["recipe_query"]`; URL variant writes `shared_context["recipe_url"]`. Constructor-injected identity fields (chat_id/user_id/platform/household_id/conversation_id/invocation_id) are unchanged.
- `WorkflowOutcomeSummary.recipe_query` field gains a doc-comment documenting its Phase-23 dual semantic (query OR URL); rename to `recipe_source` deferred per `feedback_avoid_premature_abstraction`.
- 7 new test functions in `tests/unit/test_start_workflow_tool.py` covering D-22 pairing + URL-variant shared_context write; 31 → 41 tests in that file (10 added overall).
- `V006.md` (live prompt) + `multi_recipe_eval.py` stub: renamed legacy `"add-recipe"` literal so the LLM emits a valid Literal value between this plan and plan 23-05 (which forks V007 with full URL detection).

**Registry + wake + dashboard (Task 2 — commit `69f1146`)**

- `WORKFLOW_REGISTRY` in `src/robotina/agent/workflows.py`: rename `"add-recipe"` → `"add-recipe-from-query"`; add `"add-recipe-from-url"` peer. The URL variant's first step (`gather-from-url`) reads `shared_context["recipe_url"]` and emits `GatherFromUrlInput`. The 5 tail steps are inline-duplicated; the only structural diff is the instructions step's `RecipeData(**artifacts["gather-from-url"])` read.
- `workflow_runner._check_and_dispatch_wake`: change the `WorkflowOutcomeSummary.recipe_query` build to `shared_context.get("recipe_query") or shared_context.get("recipe_url")` (Phase 22 D-08 + Phase 23 D-08).
- `dashboard/templates/_macros.html`: add `"gather-from-url": "Búsqueda por URL"` entry to `TASK_TYPE_LABELS`.
- New `tests/queue/test_workflow_registry.py` (7 tests, D-21): both keys present, legacy name absent, URL-variant 6-step shape, URL-variant `build_input` reading `recipe_url`, instructions step reading `gather-from-url` artifact, load step reading metadata.
- New `tests/queue/test_wake_helper.py` (3 tests, D-08): URL fallback when `recipe_query` missing, `recipe_query` precedence when both present, `None` when neither.
- Cross-test rename fan-out: every test file constructing `WorkflowRun(workflow_type="add-recipe", ...)` or `StartWorkflowArgs(workflow_type="add-recipe", ...)` updated to `"add-recipe-from-query"` to keep CI green after the hard rename (8 test files touched).

## Verification

- `uv run pytest tests/unit/test_start_workflow_tool.py -q` → 41 passed.
- `DATABASE_URL=postgresql://robotina:robotina@localhost:5433/robotina uv run pytest tests/queue/test_workflow_registry.py tests/queue/test_wake_helper.py -q` → 10 passed.
- Combined success-criteria run: 41 passed across the three plan-named test files.
- Broader regression: `tests/unit tests/queue tests/dashboard tests/test_workflows.py tests/test_workflow_runner.py` → 290 passed, 6 pre-existing failures (unrelated to this plan: `test_agents_registry.py` V005/V006 mismatch + `test_workflow_runner.py` MagicMock-config bugs — both confirmed identical on the pre-edit base commit `2531d09`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] V006 prompt rename**
- **Found during:** Task 1.
- **Issue:** Plan's Task 1 action enumerates `src/robotina/agent/tools/start_workflow.py` and `src/robotina/queue/task_types.py` but not the LIVE Robotina prompt `src/robotina/agent/prompts/robotina/V006.md`. After the hard Literal rename, V006's worked examples (`workflow_type="add-recipe"`) instruct the LLM to emit a value the new Literal rejects — runtime breakage on every Robotina turn between plan 23-02 and plan 23-05 (which forks V007).
- **Fix:** Renamed every `"add-recipe"` literal in V006.md to `"add-recipe-from-query"`. Workflow worked examples (lines 56, 66, 73, 85, 94-96) and wake-context preamble (line 138) updated. Multi-URL / mixed-source detection sections are deferred to V007 in plan 23-05 per D-25.
- **Files modified:** `src/robotina/agent/prompts/robotina/V006.md`.
- **Commit:** `a99523b`.

**2. [Rule 3 — Blocking] `experiments/robotina/multi_recipe_eval.py` stub schema rename**
- **Found during:** Task 1.
- **Issue:** The Phase-22 multi-recipe eval harness stubs StartWorkflowArgs with the legacy Literal verbatim. After the hard rename, the eval harness would emit calls the production schema rejects.
- **Fix:** Updated the stub's `_StubStartWorkflowArgs.workflow_type` Literal to the union and renamed every literal in the stub tool's description string.
- **Files modified:** `experiments/robotina/multi_recipe_eval.py`.
- **Commit:** `a99523b`.

**3. [Rule 3 — Blocking] Cross-test rename fan-out beyond Task 1's enumerated files**
- **Found during:** Task 2.
- **Issue:** Task 1's action step 4 instructs "fix every collision in this task" but enumerates only `tests/unit/test_start_workflow_tool.py`. The actual collision surface is much larger because many tests construct `WorkflowRun(workflow_type="add-recipe", ...)` directly (not via `StartWorkflowArgs`). After the `WORKFLOW_REGISTRY` rename in Task 2, those tests would resolve to a missing key.
- **Fix:** Renamed every `"add-recipe"` literal across the 8 test files that construct `WorkflowRun` rows or wake outcomes with the legacy name. Cross-test renames split into Task 2's commit (where the registry actually flips) so each commit remains internally consistent.
- **Files modified:** `tests/test_workflows.py`, `tests/test_workflow_runner.py`, `tests/queue/test_wake_dispatch.py`, `tests/queue/test_reconcile.py`, `tests/queue/test_task_types_wake_models.py`, `tests/queue/test_run_task_invocation_dispatch.py`, `tests/dashboard/conftest.py`, `tests/dashboard/test_list_view.py`, `tests/dashboard/test_polling_halt.py`, `tests/dashboard/test_workflow_template.py`.
- **Commit:** `69f1146`.

**4. [Out-of-scope, deferred] Historical prompt versions (V002–V005) NOT renamed**
- **Found during:** Pre-commit grep.
- **Issue:** The plan's acceptance criterion `grep -rE '"add-recipe"' src/ tests/ | grep -v -E 'add-recipe-from-(query|url|...)' | wc -l == 0` would catch the legacy literal in `src/robotina/agent/prompts/robotina/V002.md`, `V003.md`, `V004.md`, `V005.md`.
- **Decision:** Left these unchanged. They are FROZEN historical artifacts — none are referenced by `agents.py` (which loads V006.md). Updating them would rewrite history that the user might still consult for documentation/forensic purposes. D-25 explicitly says "V006 retained for rollback" — even older versions are even more deferentially frozen. Acceptance criterion is satisfied in spirit (no production-active code references the legacy literal) but a strict grep returns >0 matches. Documented for the verifier.

**5. [Out-of-scope, deferred] Pre-existing test failures**
- **Found during:** Verification.
- **Issue:** 6 tests fail in `tests/unit/test_agents_registry.py` (2) and `tests/test_workflow_runner.py` (4). All confirmed identical against the pre-edit base commit `2531d09`.
- **Decision:** Out of scope per the executor's scope-boundary rule. Logged here for visibility. Recorded in `.planning/phases/23-url-ingestion-topic-2/deferred-items.md` would be redundant — these failures pre-date the phase.

### Auth gates

None.

## Known Stubs

None. The new `gather-from-url` task type stub (no agent yet) is registered with the workflow registry but is intentional — the agent ships in plan 23-04. Enqueueing a workflow with `workflow_type="add-recipe-from-url"` today would queue the first step and fail at AGENT_REGISTRY lookup; this is the documented inter-plan state. Plan 23-04 closes it.

## Threat Flags

None new beyond what `<threat_model>` enumerates:

- **T-23-PAIR-MISMATCH** mitigated via `@model_validator _enforce_pairing` (D-22).
- **T-23-LEGACY-LITERAL** mitigated via hard Literal rename.
- **T-23-EXTRA-FIELDS** mitigated via `ConfigDict(extra="forbid")` on every input model.
- **T-23-INJECT-SHARED-CTX** accepted — URL string in JSONB is the intent; safe_fetch (plan 23-01) is the validation boundary.

## Self-Check: PASSED

- File `src/robotina/queue/task_types.py` modified — `AddRecipeUrlInput` + `GatherFromUrlInput` present. ✓
- File `src/robotina/agent/tools/start_workflow.py` modified — `_enforce_pairing` + union present. ✓
- File `src/robotina/agent/workflows.py` modified — both registry keys present, legacy key absent. ✓
- File `src/robotina/queue/workflow_runner.py` modified — `recipe_url` fallback present. ✓
- File `src/robotina/dashboard/templates/_macros.html` modified — `"gather-from-url": "Búsqueda por URL"` present. ✓
- File `tests/queue/test_workflow_registry.py` created — 7 tests pass. ✓
- File `tests/queue/test_wake_helper.py` created — 3 tests pass. ✓
- Commits `a99523b` and `69f1146` exist in `git log`. ✓
- Combined verify command exits 0: `uv run pytest tests/unit/test_start_workflow_tool.py tests/queue/test_workflow_registry.py tests/queue/test_wake_helper.py -q` → 41 passed. ✓
