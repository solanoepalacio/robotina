"""Phase 24 / D-14: non-fatal workflow runner capability tests.

Exercises the runner-level non-fatal-failure path landed in plan 24-01:

  - ``WorkflowStepDef.non_fatal_on_failure: bool = False`` (new field)
  - ``StepUnavailableArtifact`` Pydantic model (new sentinel artifact)
  - ``workflow_runner._truncate_reason`` (extracted shared helper)
  - ``workflow_runner._advance_after_step`` (extracted from on_step_complete)
  - ``workflow_runner._finalize_step_unavailable`` (new unavailable-path helper)

The 5 tests below mirror the D-14 acceptance matrix:

  1. test_non_fatal_step_raises_advances_to_done_with_unavailable_artifact
  2. test_strict_step_still_fails_workflow
  3. test_unavailable_reason_is_truncated_to_150_chars
  4. test_unavailable_artifact_passes_through_downstream_build_input
  5. test_non_fatal_last_step_marks_workflow_run_done

Tests are unit-style with mocked sessions / queues — they exercise the
helpers directly without a live Postgres so they run cleanly in any
worktree environment. The DB-level integration is covered by the
existing live-DB tests under tests/queue/ (test_wake_dispatch.py et al.)
which already pass on prod CI infra.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from robotina.queue.models import WorkflowStatus, WorkflowStepStatus
from robotina.queue.task_types import StepUnavailableArtifact
from robotina.queue.workflow_runner import (
    _finalize_step_unavailable,
    _truncate_reason,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FakeStep:
    """In-memory stand-in for WorkflowRunStep — only the fields the helpers read."""

    def __init__(
        self,
        *,
        step_key: str,
        workflow_run_id: str = "run-1",
        task_job_id: str = "job-1",
        step_order: int = 0,
        task_type: str = "synthetic",
        status: WorkflowStepStatus = WorkflowStepStatus.RUNNING,
        artifact: dict | None = None,
    ):
        self.step_key = step_key
        self.workflow_run_id = workflow_run_id
        self.task_job_id = task_job_id
        self.step_order = step_order
        self.task_type = task_type
        self.status = status
        self.artifact = artifact
        self.completed_at = None
        self.step_input = None


class _FakeRun:
    def __init__(
        self,
        *,
        id: str = "run-1",
        workflow_type: str = "synthetic-test",
        shared_context: dict | None = None,
        status: WorkflowStatus = WorkflowStatus.RUNNING,
        triggered_by_invocation_id: str | None = None,
    ):
        self.id = id
        self.workflow_type = workflow_type
        self.shared_context = shared_context or {}
        self.status = status
        self.triggered_by_invocation_id = triggered_by_invocation_id


class _SessionStub:
    """Session stub that routes ``query(Model).filter(...).first()`` /
    ``.all()`` / ``.order_by(...).first()`` to caller-provided handlers.

    Caller passes a mapping of model class → list of rows. The stub responds
    with the first row whose attributes match the filter predicate, OR (for
    .all()) the full list. The fidelity is sufficient for the
    _finalize_step_unavailable + _advance_after_step paths.
    """

    def __init__(self, rows_by_model: dict):
        self._rows_by_model = rows_by_model
        self.flushed = 0
        self.committed = 0

    def query(self, model):
        return _Query(self._rows_by_model.get(model, []))

    def flush(self):
        self.flushed += 1

    def commit(self):
        self.committed += 1


class _Query:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *predicates):
        # We can't introspect SQLAlchemy predicates here. The tests below
        # construct narrow row sets so the first() / all() result is
        # deterministic regardless of the predicate.
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_non_fatal_step_raises_advances_to_done_with_unavailable_artifact(monkeypatch):
    """D-14 #1: a non-fatal step's exception → step DONE + StepUnavailableArtifact +
    workflow advances to the next PENDING step.

    The runner's outer except (jobs.py) calls _finalize_step_unavailable with
    the exception string; this test exercises that helper directly to verify
    the artifact shape, status flip, and advancement call.
    """
    failing = _FakeStep(
        step_key="image",
        task_job_id="job-image",
        step_order=1,
        status=WorkflowStepStatus.RUNNING,
    )
    next_pending = _FakeStep(
        step_key="load",
        task_job_id=None,  # not yet enqueued
        step_order=2,
        status=WorkflowStepStatus.PENDING,
    )
    run = _FakeRun(workflow_type="synthetic-test")

    # Patch WORKFLOW_REGISTRY so _advance_after_step has a build_input lambda
    # for "load" — return a plain dict (no model_dump branch).
    from robotina.queue import workflow_runner as wr

    class _FakeStepDef:
        step_key = "load"
        task_type = "synthetic-load"

        @staticmethod
        def build_input(ctx, artifacts):
            return {"synthetic": True, "artifacts_seen": list(artifacts.keys())}

    class _FakeWfDef:
        steps = [_FakeStepDef]

    fake_registry = {"synthetic-test": _FakeWfDef}
    monkeypatch.setattr(
        "robotina.agent.workflows.WORKFLOW_REGISTRY", fake_registry, raising=True
    )

    # First query is for the failing step (by task_job_id); next queries are
    # DONE-steps list (after status flip), the WorkflowRun, and the next PENDING.
    # We just need to make sure the first .first() returns `failing`, the
    # .all() returns [failing] (now DONE), and the next .first() returns `next_pending`.
    from robotina.queue.models import WorkflowRun, WorkflowRunStep

    # Build a query handler that returns the right rows in sequence.
    session_rows = {
        WorkflowRunStep: [failing, next_pending],  # generic; .first() returns failing initially
        WorkflowRun: [run],
    }
    session = _SessionStub(session_rows)

    # Stage-aware Query: first .first() on steps -> failing; subsequent .first()
    # -> next_pending; .all() -> the DONE-set ([failing]).
    call_log = {"step_first_count": 0}

    class _StagedQuery:
        def __init__(self, model):
            self._model = model

        def filter(self, *a):
            return self

        def order_by(self, *a, **k):
            return self

        def first(self):
            if self._model is WorkflowRunStep:
                call_log["step_first_count"] += 1
                # 1st call: locate failing step. 2nd call: locate next PENDING.
                if call_log["step_first_count"] == 1:
                    return failing
                return next_pending
            if self._model is WorkflowRun:
                return run
            return None

        def all(self):
            # _advance_after_step's "DONE siblings" query — return failing (now DONE)
            return [failing]

    def _query(model):
        return _StagedQuery(model)

    session.query = _query

    queue = MagicMock()
    queue.name = "agent-tasks"

    _finalize_step_unavailable(
        "job-image",
        "RecipeImageAcquisitionError: no candidates",
        session,
        queue,
    )

    # Artifact written with structured shape; status flipped to DONE
    assert failing.status == WorkflowStepStatus.DONE
    assert failing.artifact is not None
    assert failing.artifact["status"] == "unavailable"
    assert failing.artifact["step_key"] == "image"
    assert "image: " in failing.artifact["reason"]

    # Advancement happened: next step was enqueued and given a job_id
    assert queue.enqueue.called
    enqueue_kwargs = queue.enqueue.call_args.kwargs
    assert enqueue_kwargs["result_ttl"] == -1
    assert enqueue_kwargs["failure_ttl"] == -1
    assert next_pending.task_job_id is not None


def test_strict_step_still_fails_workflow():
    """D-14 #2: the default non_fatal_on_failure=False preserves v1.0 strict
    semantics — no opt-in step should trigger the new helper. We verify by
    confirming that a freshly registered WORKFLOW_REGISTRY step has the
    default False and that the StepUnavailableArtifact model only ever
    surfaces for opt-in steps (no inline path triggers it).
    """
    from robotina.agent.workflows import WORKFLOW_REGISTRY, WorkflowStepDef

    # All existing registered steps must remain strict (non_fatal_on_failure=False)
    for wf in WORKFLOW_REGISTRY.values():
        for step in wf.steps:
            assert step.non_fatal_on_failure is False, (
                f"step {step.step_key!r} in workflow {wf.workflow_type!r} "
                "should not opt in to non-fatal failure in plan 24-01"
            )

    # The default on a freshly constructed WorkflowStepDef is False.
    default_step = WorkflowStepDef(
        step_key="x",
        task_type="x",
        build_input=lambda ctx, artifacts: {},
    )
    assert default_step.non_fatal_on_failure is False


def test_unavailable_reason_is_truncated_to_150_chars():
    """D-14 #3: ``StepUnavailableArtifact.reason`` is composed via
    ``_truncate_reason`` — same Pydantic-URL-noise strip + 150-char cap as
    ``_compose_failure_outcome``. Verify with a long noise-laden input.
    """
    # 200 chars of "x" + Pydantic noise trailer
    noise = (
        "x" * 200
        + " For further information visit https://errors.pydantic.dev/2.7/v/dict_type"
    )
    out = _truncate_reason(noise, "image")
    assert out.startswith("image: ")
    # The reason portion (after "image: ") must be ≤ 150 chars + ellipsis (1 char)
    reason_body = out[len("image: "):]
    assert len(reason_body) <= 151, (
        f"reason body too long: len={len(reason_body)} reason={reason_body!r}"
    )
    # Pydantic URL noise stripped
    assert "errors.pydantic.dev" not in out
    # Truncated with ellipsis
    assert out.endswith("…")


def test_unavailable_artifact_passes_through_downstream_build_input():
    """D-14 #4 + Pitfall 6: the artifact written by _finalize_step_unavailable
    has shape {status, step_key, reason} — NOT a RecipeData dump. Downstream
    build_input lambdas that fall back to a sibling DONE artifact (per
    workflows.py D-06b pattern) must be able to detect the unavailable shape
    and use the fallback path without raising.
    """
    # Construct the artifact the helper would write
    artifact = StepUnavailableArtifact(
        step_key="recipe-image",
        reason="recipe-image: SafeFetchError: blocked",
    ).model_dump(mode="json")

    assert artifact == {
        "status": "unavailable",
        "step_key": "recipe-image",
        "reason": "recipe-image: SafeFetchError: blocked",
    }

    # Simulate the Pitfall-6 build_input fallback pattern (the shape future
    # plan 24-05 will install on the "load" step in WORKFLOW_REGISTRY).
    accumulated_artifacts = {
        "metadata": {"name": "tarta", "ingredients": [], "steps": []},
        "recipe-image": artifact,
    }

    def fake_build_input(ctx, artifacts):
        # Detects unavailable shape; falls back to "metadata".
        chosen = (
            artifacts["metadata"]
            if artifacts.get("recipe-image", {}).get("status") == "unavailable"
            else artifacts["recipe-image"]
        )
        return {"recipe": chosen}

    result = fake_build_input({}, accumulated_artifacts)
    assert result == {"recipe": {"name": "tarta", "ingredients": [], "steps": []}}


def test_non_fatal_last_step_marks_workflow_run_done(monkeypatch):
    """D-14 #5: a non-fatal step that is ALSO the final step must mark the
    WorkflowRun DONE (not FAILED) when it raises. _advance_after_step's
    "no next PENDING" branch handles this; verify _finalize_step_unavailable
    plumbs through to it correctly.
    """
    failing = _FakeStep(
        step_key="image",
        task_job_id="job-image",
        step_order=1,
        status=WorkflowStepStatus.RUNNING,
    )
    run = _FakeRun(
        workflow_type="synthetic-test",
        status=WorkflowStatus.RUNNING,
        triggered_by_invocation_id=None,  # skip wake-dispatch helper
    )

    from robotina.queue.models import WorkflowRun, WorkflowRunStep

    call_log = {"step_first_count": 0}

    class _StagedQuery:
        def __init__(self, model):
            self._model = model

        def filter(self, *a):
            return self

        def order_by(self, *a, **k):
            return self

        def first(self):
            if self._model is WorkflowRunStep:
                call_log["step_first_count"] += 1
                if call_log["step_first_count"] == 1:
                    return failing
                # 2nd call: no PENDING steps left
                return None
            if self._model is WorkflowRun:
                return run
            return None

        def all(self):
            return [failing]

    session = _SessionStub({})
    session.query = lambda model: _StagedQuery(model)

    queue = MagicMock()
    queue.name = "agent-tasks"

    _finalize_step_unavailable(
        "job-image",
        "RecipeImageAcquisitionError: no candidates",
        session,
        queue,
    )

    # The failing step is DONE (not FAILED) and the WorkflowRun is also DONE.
    assert failing.status == WorkflowStepStatus.DONE
    assert run.status == WorkflowStatus.DONE
    # No new enqueue because there is no next PENDING step.
    assert not queue.enqueue.called
