---
phase: 16
plan: 04
subsystem: workflow-runner
tags:
  - python
  - validation
  - workflow
  - defensive
dependency_graph:
  requires:
    - 16-01 (Wave 0 — RED stubs exist for queue_workflow guard tests)
  provides:
    - queue_workflow last-line-of-defense for empty household_id (REQ-HID-4)
  affects:
    - 16-07 (verification + UAT phase will run the new tests as part of the full suite)
tech_stack:
  added: []
  patterns:
    - "Inline guard at function entry, BEFORE registry lookup and DB writes"
    - "MagicMock-based unit testing of side-effect absence (assert_not_called)"
key_files:
  created: []
  modified:
    - src/robotina/queue/workflow_runner.py
    - tests/test_workflow_runner.py
decisions:
  - "Guard placed BEFORE WORKFLOW_REGISTRY import so an empty household_id short-circuits before the unrelated KeyError-on-unknown-workflow_type path."
  - "Used `if not household_id or not household_id.strip()` to reject both `''` and whitespace-only inputs in the single guard, consistent with the gateway-entrypoint strip-and-check pattern."
  - "Error message explicitly names `household_id` and points operators at the three upstream layers (gateway boot, IncomingMessageInput.household_id, StartWorkflowTool.household_id) so a single failed-job log line tells the operator where to look first."
  - "Used pydantic-native exception type (`ValueError`) per CONTEXT.md Defensive Validation section. `pydantic.ValidationError` inherits from `ValueError`, so test assertions remain compatible with upstream layers if their error type changes later."
metrics:
  duration_seconds: 157
  duration_human: "~2 minutes 37 seconds"
  completed_date: "2026-05-15"
  tasks_completed: 1
  files_modified: 2
  tests_added: 2
  commits: 1
---

# Phase 16 Plan 04: queue_workflow empty-household_id guard Summary

**One-liner:** Inserted a defensive `ValueError` guard at the top of `queue_workflow` that rejects empty / whitespace-only `household_id` before any registry lookup or DB write, with two new unit tests proving DB-safety via `assert_not_called()` on `session.add` / `flush` / `commit` / `queue.enqueue`.

## What was done

### Source change (1 edit)

**`src/robotina/queue/workflow_runner.py`** — added a 13-line guard at the top of `queue_workflow` body, immediately BEFORE the `from robotina.agent.workflows import WORKFLOW_REGISTRY` line. The guard:

- Tests `not household_id or not household_id.strip()` so it rejects both `""` and `"   "`.
- Raises `ValueError` with a message that names `household_id` and points to the three upstream layers expected to catch the empty value first (gateway boot guard in `__init__.py::main`, `IncomingMessageInput.household_id` validation, and `StartWorkflowTool.household_id`).
- Runs BEFORE every side-effectful statement in the function (`WORKFLOW_REGISTRY[workflow_type]` lookup, `session.add(run)`, `session.flush()`, `queue.enqueue(...)`, `session.commit()`).

### Test changes (2 new tests appended to `tests/test_workflow_runner.py`)

1. `test_queue_workflow_rejects_empty_household_id` — passes `household_id=""`, asserts `ValueError`, asserts the error message contains `"household_id"`, and asserts `mock_session.add` / `.flush` / `.commit` AND `mock_queue.enqueue` were never called.
2. `test_queue_workflow_rejects_whitespace_household_id` — same shape with `household_id="   "`. Asserts `ValueError`, message contains `"household_id"`, and no DB or queue writes occurred.

Both tests use `MagicMock()` for queue and session per the existing fixture pattern at the top of the file (`make_session_returning`, `make_step`, `make_run`) — no Postgres/Redis required.

## DB-safety proof

The `mock_session.add.assert_not_called()` + `mock_session.flush.assert_not_called()` + `mock_session.commit.assert_not_called()` triad in `test_queue_workflow_rejects_empty_household_id` is the formal proof that the guard fires before ANY persistent side effect. If a future refactor moves the guard below `session.add(run)`, the test fails immediately.

The corresponding `mock_queue.enqueue.assert_not_called()` covers the RQ-side: no in-flight job for a downstream task type (e.g. `recipe-research-gather`, `recipe-load`) can be enqueued with an unrecoverable empty `household_id`.

## Acceptance criteria — verified

| AC | Result |
| --- | --- |
| `grep -c "queue_workflow refuses empty household_id" src/robotina/queue/workflow_runner.py == 1` | PASS |
| `grep -c "def test_queue_workflow_rejects_empty_household_id" tests/test_workflow_runner.py == 1` | PASS |
| `grep -c "def test_queue_workflow_rejects_whitespace_household_id" tests/test_workflow_runner.py == 1` | PASS |
| Both new tests pass standalone (`uv run pytest ...::test_queue_workflow_rejects_empty_household_id ...::test_queue_workflow_rejects_whitespace_household_id -x -q`) | PASS (2 passed in 0.03s) |
| Full workflow_runner unit suite green (`uv run pytest tests/test_workflow_runner.py -x -q -m "not integration"`) | PASS (25 passed, 1 deselected) |
| Guard appears BEFORE WORKFLOW_REGISTRY import AND BEFORE session.add(run) in line-order | PASS (guard at line 138, registry import at line 144, session.add(run) at line 156 in the post-edit file) |

The one integration test (`test_migration_0005_upgrades_and_downgrades`) that was `-x` flagged as failing is `@pytest.mark.integration`, requires a running Postgres on `localhost:5432`, and is **out of scope for this plan** (pre-existing infrastructure dependency, not caused by this change).

## Deviations from Plan

None — plan executed exactly as written. The TDD cycle (RED on Wave 0 stubs + the new tests appended in this plan; GREEN on the guard insert) ran cleanly:

- RED: tests written before guard. First run failed with `KeyError: 'recipe_query'` inside `WORKFLOW_REGISTRY` lookup (because the guard wasn't there yet to short-circuit) — exactly the failure mode the plan predicted and the reason the guard MUST sit BEFORE the registry import.
- GREEN: guard inserted, both new tests pass + existing 23 unit tests still green.
- REFACTOR: not needed — guard is 13 lines of straight-line code, no abstraction debt.

## Sequencing note (parallel Wave 1 commits)

This plan ran in parallel with 16-02 (Pydantic `NonEmptyHouseholdId` on task-input models), 16-05 (tool-constructor validation), and 16-06 (`.env.example` + `send.py` docstring sweep). The index showed transient races during staging (other agents staged/committed `src/robotina/gateway/__init__.py`, `send.py`, and `task_types.py` while my files were being staged), so I performed the final stage+commit atomically in one shell invocation to land my two files cleanly. Confirmed post-commit: my commit (`1b9f4d5`) contains exactly the two files in `<files_modified>` — no spillover from sibling plans.

## Self-Check: PASSED

- File exists: `src/robotina/queue/workflow_runner.py` — FOUND
- File exists: `tests/test_workflow_runner.py` — FOUND
- Commit exists: `1b9f4d5` — FOUND in `git log --all --oneline`
- Guard text present in source: 1 match
- Both new test functions present in test file: 1 match each
