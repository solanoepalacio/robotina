---
phase: 20-wake-rule-outcome-plumbing
plan: 02
subsystem: queue
tags: [wake-rule, outcome, deterministic-task, finalize-outcome]
requires:
  - WorkflowRun.outcome column (Phase 17)
  - AddRecipeOutcome model (Phase 18)
  - send-notification deterministic branch (Phase 07.1) — architectural template
provides:
  - FinalizeOutcomeInput Pydantic model (D-03)
  - finalize-outcome workflow step on add-recipe (D-02)
  - Agent-less finalize-outcome branch in run_task (D-01)
affects:
  - src/robotina/agent/workflows.py
  - src/robotina/queue/jobs.py
  - src/robotina/queue/task_types.py
  - tests/queue/test_finalize_outcome.py
tech-stack:
  added: []
  patterns:
    - "Agent-less run_task branch (same shape as send-notification, line 90)"
    - "Step-output materialization writes to WorkflowRun.outcome before on_step_complete commits"
key-files:
  created:
    - tests/queue/test_finalize_outcome.py
    - tests/queue/__init__.py
  modified:
    - src/robotina/agent/workflows.py
    - src/robotina/queue/jobs.py
    - src/robotina/queue/task_types.py
decisions:
  - "D-01: finalize-outcome is agent-less; mirrors send-notification branch shape"
  - "D-02: appended AFTER notify (not replacing it); preserves legacy user reply"
  - "D-03: FinalizeOutcomeInput shape: metadata | load | failure_reason (all optional)"
metrics:
  duration: ~12 min
  completed_date: 2026-05-19
---

# Phase 20 Plan 02: Wake rule + outcome plumbing — finalize-outcome step Summary

Land the `finalize-outcome` task type as the new terminal step of the `add-recipe`
workflow: append the step to `WORKFLOW_REGISTRY['add-recipe']`, add an agent-less
deterministic branch in `run_task` that composes an `AddRecipeOutcome` from
accumulated artifacts and writes it to `WorkflowRun.outcome`.

## What was built

- **`FinalizeOutcomeInput`** (`src/robotina/queue/task_types.py`): tight Pydantic
  v2 model with `extra="forbid"`. Fields: `metadata: dict | None`, `load: dict | None`,
  `failure_reason: str | None`. This was specified in plan 20-01 as well; both
  plans land the same model — merge will deduplicate.
- **Workflow step append** (`src/robotina/agent/workflows.py`): `add-recipe` step
  list is now `[acknowledge, gather, instructions, ingredients, metadata, load,
  notify, finalize-outcome]`. The build_input lambda pulls `artifacts.get("metadata")`
  and `artifacts.get("load")` into a `FinalizeOutcomeInput`.
- **Agent-less branch in `run_task`** (`src/robotina/queue/jobs.py`): runs
  immediately after the `send-notification` deterministic branch, before the
  LLM `try:` block. Composes `AddRecipeOutcome(status="success", recipe_id, recipe_name,
  recipe_slug, image_present=False)` when `load.recipe_id` is present;
  composes `AddRecipeOutcome(status="failure", failure_reason="...")` otherwise.
  Looks up the `WorkflowRun` via `WorkflowRunStep.task_job_id == job.id`,
  writes `run.outcome = outcome.model_dump(mode="json")`, flushes, then calls
  `workflow_runner.on_step_complete(job.id, artifact, _session, _queue)`. Wraps
  the whole block in `try/except` so exceptions route to `on_step_failed` with
  the `exc=` kwarg before re-raising.
- **Tests** (`tests/queue/test_finalize_outcome.py`): six unit tests covering
  success/failure/propagation/image_present/exception paths. Mock `get_current_job`,
  `SessionLocal`, and workflow_runner hooks per the existing `test_agent_runner.py`
  convention.

## Verification results

- `grep -n "finalize-outcome" src/robotina/agent/workflows.py | wc -l` → 2
  (step_key + task_type)
- `grep -n 'task_type == "finalize-outcome"' src/robotina/queue/jobs.py | wc -l` → 1
- `uv run pytest tests/queue/test_finalize_outcome.py -x -q` → 6 passed in 0.02s
- `uv run pytest tests/unit/ tests/queue/ -x -q` → 148 passed in 2.93s (no regression)

## Deviations from Plan

**1. Rebase to main** — At executor spawn, the worktree branch was several phases
behind main (Phase 17 + Phase 18 commits absent). The plan's `<read_first>` and
`<context>` all reference Phase 17/18 contracts (WorkflowRun.outcome,
triggered_by_invocation_id, AddRecipeOutcome) which weren't in HEAD. Rebased
the worktree branch onto main before starting Task 2.1 so the prerequisites
exist. No code conflicts — clean rebase. Pure environmental setup; not a Rule N
deviation, just an unstated prerequisite.

**2. `FinalizeOutcomeInput` landed here (per plan instruction)** — The plan
prompt explicitly stated: "If 20-01 hasn't merged yet, copy/inline the import
path and trust the model will exist after both worktrees merge." Plan 20-01
runs in parallel and also lands `FinalizeOutcomeInput`; the merge will need to
deduplicate one of the two definitions. The model shape is identical between
both plans (D-03 is load-bearing on both sides).

**3. Tests live at `tests/queue/test_finalize_outcome.py`** — Plan specifies this
exact path. Existing repo convention is mostly `tests/<flat>.py` and
`tests/unit/<file>.py`; `tests/queue/` is a new test sub-package. Added an
`__init__.py` to make it a package. Consistent with `tests/dashboard/`.

## Auth gates

None — all work was deterministic Python + tests; no auth boundary crossed.

## Known Stubs

None. `image_present=False` is the documented Phase 20 default per D-03 — the
recipe-image milestone (Phase 24) flips it. This is intentional, not a stub.

## Commits

- `451b518` — feat(20-02): append finalize-outcome step + FinalizeOutcomeInput model
- `5cf692d` — feat(20-02): add agent-less finalize-outcome branch to run_task

## Self-Check: PASSED

- File `src/robotina/agent/workflows.py` — modified, finalize-outcome appended
- File `src/robotina/queue/jobs.py` — modified, branch present
- File `src/robotina/queue/task_types.py` — modified, FinalizeOutcomeInput present
- File `tests/queue/test_finalize_outcome.py` — created, 6 tests passing
- Commits `451b518` and `5cf692d` exist in `git log`
