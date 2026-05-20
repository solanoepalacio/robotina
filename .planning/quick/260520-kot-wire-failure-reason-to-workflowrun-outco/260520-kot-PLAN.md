---
quick_id: 260520-kot
slug: wire-failure-reason-to-workflowrun-outco
created: 2026-05-20
description: Wire failure_reason through to WorkflowRun.outcome on FAILED workflows
files_modified:
  - src/robotina/queue/workflow_runner.py
  - tests/queue/test_wake_dispatch.py
must_haves:
  truths:
    - On a FAILED workflow, WorkflowRun.outcome is non-null and contains a dumped AddRecipeOutcome with status="failure"
    - The failure_reason field contains "<step_key>: <short reason>" where short reason is the first ~150 chars of WorkflowRunStep.failure_reason
    - Pydantic URL noise ("For further information visit https://...") is stripped from the short reason
    - The outcome write happens in the SAME session/commit as the run.status=FAILED flip — no separate commit
    - The wake-context Robotina reply can now interpolate outcome.failure_reason instead of saying "no tengo más información"
---

<objective>
Backlog A from Phase 20/21 manual verification: when a workflow step fails, `on_step_failed` cancels remaining steps (including `finalize-outcome`), leaving `WorkflowRun.outcome` NULL. The wake-context agent then has nothing to interpolate. Wire a sentinel `AddRecipeOutcome(status="failure", failure_reason=...)` to `WorkflowRun.outcome` inside `on_step_failed` so the wake-context Robotina reply can reference the failure concretely.

This is a UX layer above the existing fail-loud semantics. No retry, no recovery — just rendering.
</objective>

<task id="1" autonomous="true">
<summary>Stamp AddRecipeOutcome(status="failure", failure_reason=...) onto WorkflowRun.outcome in on_step_failed before the atomic commit</summary>

<read_first>
- src/robotina/queue/workflow_runner.py (on_step_failed lines ~404-533 — the FAILED status flip and the try/except around _check_and_dispatch_wake)
- src/robotina/queue/task_types.py (AddRecipeOutcome shape — verify status: Literal["success","failure"] + failure_reason: str | None fields exist)
- src/robotina/queue/models.py (WorkflowRun.outcome JSON column, WorkflowRunStep.failure_reason field)
- .planning/phases/20-wake-rule-outcome-plumbing/20-CONTEXT.md (D-03 — finalize-outcome ONLY runs on DONE workflows; this gap is exactly what Backlog A fills)
</read_first>

<action>
In `src/robotina/queue/workflow_runner.py::on_step_failed`:

1. Add a small helper at module scope (above `on_step_failed`) — call it `_compose_failure_outcome(step: WorkflowRunStep) -> dict`:
   ```python
   def _compose_failure_outcome(step) -> dict:
       """Compose an AddRecipeOutcome(status='failure', ...) dict for a failed step.

       Backlog A — the wake-context Robotina turn renders outcome.failure_reason
       when present; without it the agent fallback is "no tengo más información".
       Keep the reason short and reference-friendly; V005 prompt does the user-facing
       humanization on top.
       """
       from robotina.queue.task_types import AddRecipeOutcome

       raw = (step.failure_reason or "").strip()
       # Strip Pydantic doc URL noise (single-line and multi-line forms)
       import re as _re
       raw = _re.sub(r"\s*For further information visit https?://\S+", "", raw)
       # Collapse whitespace / newlines
       raw = _re.sub(r"\s+", " ", raw).strip()
       short = raw[:150].rstrip()
       if len(raw) > 150:
           short = short + "…"
       reason = f"{step.step_key}: {short}" if short else f"{step.step_key}: failed"
       return AddRecipeOutcome(status="failure", failure_reason=reason).model_dump()
   ```

2. In `on_step_failed`, locate the section where `run.status = WorkflowStatus.FAILED` is set (the Phase 20 D-08 atomic-commit shape — single commit at the end of the happy path, with the try/except around `_check_and_dispatch_wake`). RIGHT BEFORE `run.status = WorkflowStatus.FAILED`, add:
   ```python
   # Backlog A — wire failure context into WorkflowRun.outcome so the wake-context
   # Robotina turn can reference a concrete reason instead of "no tengo más
   # información". finalize-outcome step is cancelled here (Phase 20 D-03), so
   # this is the only producer of outcome on the FAILED side.
   if run.outcome is None:
       run.outcome = _compose_failure_outcome(step)
   ```
   The `if run.outcome is None` guard preserves any outcome that finalize-outcome may have stamped on a race (defensive; finalize-outcome wouldn't have run if we're in on_step_failed for an earlier step, but it's cheap insurance).

3. **Atomicity constraint**: the existing commit ordering stays. The `run.outcome = ...` line must execute BEFORE the existing `session.commit()` that follows `run.status = WorkflowStatus.FAILED` + `_check_and_dispatch_wake(...)`. Per Phase 20 D-08, that commit is the single happy-path commit covering the FAILED flip + wake row + (now) the outcome write. Do NOT add a separate commit. Do NOT move the `_check_and_dispatch_wake` call.

4. **Failure path inside on_step_failed**: when the existing except branch fires (wake helper raised), the rollback + re-mark-FAILED + commit code stays. The `run.outcome` assignment must also re-stamp inside that except branch, OR be set early enough that the rollback recovers it. Cleanest shape: set `run.outcome` immediately after the step.failure_reason write (which happens at the top of on_step_failed), so it's part of the same in-memory state that gets re-marked after rollback. Reorganize if needed — but verify ALL paths through on_step_failed leave WorkflowRun.outcome non-null when status is FAILED.
</action>

<acceptance_criteria>
- `grep -c "_compose_failure_outcome" src/robotina/queue/workflow_runner.py` returns >= 2 (one def, one call)
- `grep -c "run.outcome = " src/robotina/queue/workflow_runner.py` returns >= 1 (the FAILED-path stamp; finalize-outcome's stamp is in jobs.py, not workflow_runner.py)
- `grep -n "run.outcome" src/robotina/queue/workflow_runner.py` shows the assignment line BEFORE the `session.commit()` line of the on_step_failed happy path
- The helper strips Pydantic URL noise: a test input `"validation error\n\nFor further information visit https://errors.pydantic.dev/2.12/v/dict_type."` produces a `failure_reason` that does NOT contain `https://`
- Single-commit invariant from Phase 20 D-08 still holds: between `run.status = WorkflowStatus.FAILED` and the function returning, there is exactly one `session.commit()` on the happy path
</acceptance_criteria>
</task>

<task id="2" autonomous="true">
<summary>Add a unit test asserting failed workflows stamp AddRecipeOutcome(status="failure", failure_reason=...) onto WorkflowRun.outcome</summary>

<read_first>
- tests/queue/test_wake_dispatch.py (existing wake helper unit tests + the `test_wake_fires_on_failed` test pattern)
- src/robotina/queue/workflow_runner.py (the new on_step_failed shape from Task 1)
- src/robotina/queue/task_types.py (AddRecipeOutcome shape — for assertion construction)
</read_first>

<action>
Add a new test to `tests/queue/test_wake_dispatch.py` (or create a sibling `tests/queue/test_failure_outcome.py` if the file is getting unwieldy). The test exercises the same on_step_failed path the existing `test_wake_fires_on_failed` uses, with these additional assertions on the WorkflowRun:

```python
def test_on_step_failed_stamps_failure_outcome():
    """Backlog A — on_step_failed writes AddRecipeOutcome(status='failure', failure_reason=...)
    to WorkflowRun.outcome so the wake-context Robotina turn can reference it.
    Single-commit invariant from Phase 20 D-08 still holds.
    """
    # Reuse the fake-session + fake-queue scaffolding from the existing wake tests.
    # Set up: a WorkflowRun (status RUNNING, triggered_by_invocation_id=parent_inv.id),
    # a WorkflowRunStep (status RUNNING, step_key="gather", failure_reason=None).
    # Call on_step_failed with a structured-validation-style exception:
    #   exc = StructuredOutputValidationError(
    #       "validation error\n\nFor further information visit https://errors.pydantic.dev/2.12/v/dict_type."
    #   )
    # Or simulate by manually setting step.failure_reason = "<the long error text>" before
    # calling on_step_failed, depending on how the failure_reason field is populated in the
    # current code path.
    #
    # Assertions:
    # 1. run.status == WorkflowStatus.FAILED
    # 2. run.outcome is not None
    # 3. run.outcome["status"] == "failure"
    # 4. run.outcome["failure_reason"].startswith("gather: ")
    # 5. "https://" not in run.outcome["failure_reason"]   # URL noise stripped
    # 6. "For further information" not in run.outcome["failure_reason"]
    # 7. len(run.outcome["failure_reason"]) <= 200          # truncation
    # 8. parent_inv.wake_dispatched_at is not None         # wake still fires
    # 9. fake_queue.enqueued has exactly one entry         # wake invocation enqueued
    pass  # implement per the existing test scaffold pattern
```

Also add a small unit test for `_compose_failure_outcome` directly (input → expected dict), covering:
- Plain failure_reason → "step_key: reason"
- None / empty failure_reason → "step_key: failed"
- failure_reason with Pydantic URL → URL stripped
- failure_reason > 150 chars → truncated with "…"
- failure_reason with embedded newlines → collapsed to spaces
</action>

<acceptance_criteria>
- New test name(s) present in `tests/queue/test_wake_dispatch.py` (or new file)
- `uv run pytest tests/queue/ -k "failure_outcome or compose_failure" -q` returns >= 5 passing tests (1 integration-style on_step_failed + 4 unit tests of the helper)
- Existing wake-dispatch tests still pass: `uv run pytest tests/queue/test_wake_dispatch.py -q` shows all pre-existing tests green
- No regressions in the broader unit suite: `uv run pytest tests/queue/ tests/unit/ -q --ignore=tests/queue/test_workflow_runner.py --ignore=tests/queue/test_reconcile.py` is green (those 2 are env-dependent integration tests)
</acceptance_criteria>
</task>

<verify>
- `uv run pytest tests/queue/test_wake_dispatch.py -q` → all tests pass
- `uv run pytest tests/queue/ tests/unit/ -q --ignore=tests/queue/test_workflow_runner.py --ignore=tests/queue/test_reconcile.py` → no regressions
- Manual sanity grep: `grep -n "run.outcome" src/robotina/queue/workflow_runner.py` shows the new assignment line
- Phase 20 D-08 single-commit invariant: review the diff of on_step_failed and confirm only one `session.commit()` on the happy path
</verify>

<done>
- Task 1 commit: `feat(quick): wire failure_reason to WorkflowRun.outcome on FAILED workflows`
- Task 2 commit: `test(quick): cover FAILED-side outcome stamp and Pydantic URL stripping`
- SUMMARY.md written at `.planning/quick/260520-kot-wire-failure-reason-to-workflowrun-outco/260520-kot-SUMMARY.md`
- STATE.md NOT modified by the executor (orchestrator handles it after)
</done>
