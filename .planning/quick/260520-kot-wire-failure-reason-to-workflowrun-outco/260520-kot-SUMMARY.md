---
quick_id: 260520-kot
slug: wire-failure-reason-to-workflowrun-outco
completed: 2026-05-20
one_liner: Stamp AddRecipeOutcome(status="failure", failure_reason="<step_key>: <short>") onto WorkflowRun.outcome inside on_step_failed so the wake-context Robotina turn has something concrete to render
tasks_completed: 2
tasks_total: 2
files_modified:
  - src/robotina/queue/workflow_runner.py
  - tests/queue/test_wake_dispatch.py
commits:
  - e387cf5 feat(quick): wire failure_reason to WorkflowRun.outcome on FAILED workflows
  - bc95aa3 test(quick): cover FAILED-side outcome stamp and Pydantic URL stripping
---

# Quick Task 260520-kot — wire failure_reason → WorkflowRun.outcome on FAILED workflows

## Context

This is Backlog A from the Phase 20/21 manual verification round. Before this change, `on_step_failed` cancelled all remaining PENDING steps (including `finalize-outcome` per Phase 20 D-03), leaving `WorkflowRun.outcome` NULL on every FAILED workflow. The wake-context Robotina turn (V005) then had no concrete reason to interpolate and fell back to "no tengo más información."

The infrastructure already existed: `AddRecipeOutcome` has `failure_reason: str | None`, and `WorkflowRunStep.failure_reason` is populated by the existing D-16 format string in `on_step_failed`. The gap was pure wiring.

## What changed

### `src/robotina/queue/workflow_runner.py`

1. New module-level helper `_compose_failure_outcome(step) -> dict`:
   - Reads `step.failure_reason`
   - Strips Pydantic doc-URL trailers (`For further information visit https://errors.pydantic.dev/...`) via a precompiled regex
   - Collapses whitespace / newlines to single spaces
   - Truncates to 150 chars with `…` ellipsis (`_OUTCOME_FAILURE_REASON_MAX_CHARS`)
   - Shapes as `f"{step.step_key}: {short}"` so V005 can reference the failed step explicitly
   - Falls back to `f"{step.step_key}: failed"` if `failure_reason` is None/blank
   - Returns `AddRecipeOutcome(status="failure", failure_reason=...).model_dump()`

2. `on_step_failed` now stamps `run.outcome = _compose_failure_outcome(step)` immediately before `run.status = WorkflowStatus.FAILED`, guarded by `if run.outcome is None` to preserve any pre-existing outcome (e.g. a `finalize-outcome` race). The single happy-path `session.commit()` covers the FAILED step write, the cancelled-PENDING writes, the outcome stamp, the run-status flip, and the wake-helper INSERT — Phase 20 D-08 single-commit invariant preserved.

3. The except-branch rollback path mirrors the same write on the refetched `run` so all FAILED exit paths leave `WorkflowRun.outcome` non-null.

### `tests/queue/test_wake_dispatch.py`

Added 7 tests (covering 5 helper-unit cases + 2 integration cases):

- `test_compose_failure_outcome_plain` — plain reason → `"step_key: reason"`
- `test_compose_failure_outcome_empty` — None / whitespace-only → `"step_key: failed"`
- `test_compose_failure_outcome_strips_pydantic_url` — `https://errors.pydantic.dev/...` trailer stripped while diagnostic body retained
- `test_compose_failure_outcome_truncates_long_reason` — >150-char reason gets `…` ellipsis with bounded length
- `test_compose_failure_outcome_collapses_newlines` — `\n`, `\t`, runs of spaces collapse to single spaces
- `test_on_step_failed_stamps_failure_outcome` — drives `on_step_failed` end-to-end: outcome stamped, wake fires, URL noise stripped, length bounded
- `test_on_step_failed_preserves_existing_outcome` — defensive: pre-existing `run.outcome` is not overwritten

## Verification

```
DATABASE_URL=postgresql://robotina:robotina@localhost:5433/robotina uv run pytest tests/queue/test_wake_dispatch.py -q
17 passed in 0.11s

DATABASE_URL=postgresql://robotina:robotina@localhost:5433/robotina uv run pytest tests/queue/ tests/unit/ -q --ignore=tests/queue/test_workflow_runner.py --ignore=tests/queue/test_reconcile.py
189 passed, 23 warnings in 2.57s
```

Manual-sanity grep:

```
$ grep -n "_compose_failure_outcome" src/robotina/queue/workflow_runner.py
# def + 2 call sites (happy path + rollback path) — 3 hits

$ grep -n "run.outcome = " src/robotina/queue/workflow_runner.py
697:        if run.outcome is None:
698:            run.outcome = _compose_failure_outcome(step)
756:            if run_refetch.outcome is None and step_refetch is not None:
757:                run_refetch.outcome = _compose_failure_outcome(step_refetch)
```

`run.outcome` is written BEFORE the happy-path `session.commit()` at line 714. Single commit. Phase 20 D-08 holds.

## Deviations

None — plan executed as written. The two changes outside the literal plan snippet:

1. Used a precompiled module-level regex (`_PYDANTIC_URL_NOISE_RE`) instead of inlining `_re.sub(...)` inside the helper — micro-perf and readability; same semantics.
2. The plan snippet shows `short = short + "…"` after `rstrip()`. I kept the same behavior but expressed it as a single conditional: when `len(raw) > 150`, slice + rstrip + append `…`; otherwise keep raw. Identical output, slightly tidier.

## Self-Check: PASSED

- `src/robotina/queue/workflow_runner.py` exists with `_compose_failure_outcome` at module scope (3 occurrences)
- `run.outcome = _compose_failure_outcome(...)` present on both happy-path and rollback-path
- Commit `e387cf5` (feat) verified via `git log`
- Commit `bc95aa3` (test) verified via `git log`
- `tests/queue/test_wake_dispatch.py` contains the 7 new test names (`test_compose_failure_outcome_*`, `test_on_step_failed_stamps_failure_outcome`, `test_on_step_failed_preserves_existing_outcome`)
- All exit-criteria tests pass (17 in wake_dispatch.py + 189 in broader regression suite)
