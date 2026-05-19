"""Unit tests for LoggingWorker structure (QUEUE-02, QUEUE-07).

No Docker required — all tests are pure Python source inspection.
Run: uv run pytest tests/test_queue_models.py -x -q
"""
import inspect


def test_logging_worker_is_worker_subclass():
    """LoggingWorker must be a subclass of rq.worker.SimpleWorker."""
    from rq.worker import SimpleWorker
    from robotina.queue.runner import LoggingWorker
    assert issubclass(LoggingWorker, SimpleWorker), (
        "LoggingWorker must subclass rq.worker.SimpleWorker — runs in-process without os.fork() (QUEUE-02)"
    )


def test_logging_worker_overrides_perform_job():
    """LoggingWorker must override perform_job (not inherit it from SimpleWorker)."""
    from robotina.queue.runner import LoggingWorker
    assert "perform_job" in LoggingWorker.__dict__, (
        "LoggingWorker must override perform_job — inherited SimpleWorker.perform_job has no lifecycle logging"
    )


def test_main_uses_logging_worker():
    """runner.main() must instantiate LoggingWorker, not bare Worker."""
    from robotina.queue.runner import main
    source = inspect.getsource(main)
    assert "LoggingWorker" in source, (
        "runner.main() must use LoggingWorker([queue], ...) not Worker([queue], ...)"
    )


def test_main_uses_agent_tasks_queue():
    """runner.main() must use 'agent-tasks' queue name (downstream phases depend on this)."""
    from robotina.queue.runner import main
    source = inspect.getsource(main)
    assert "agent-tasks" in source, (
        "runner.main() must use queue name 'agent-tasks' — all downstream phases enqueue to this exact name"
    )


def test_logging_worker_emits_starting_log():
    """LoggingWorker.perform_job must log 'starting' on job start."""
    from robotina.queue.runner import LoggingWorker
    source = inspect.getsource(LoggingWorker.perform_job)
    assert "starting" in source, (
        "LoggingWorker.perform_job must emit a 'starting' log line (QUEUE-07)"
    )


def test_logging_worker_emits_finished_log():
    """LoggingWorker.perform_job must log 'finished' on job success."""
    from robotina.queue.runner import LoggingWorker
    source = inspect.getsource(LoggingWorker.perform_job)
    assert "finished" in source, (
        "LoggingWorker.perform_job must emit a 'finished' log line (QUEUE-07)"
    )


def test_logging_worker_emits_failed_log():
    """LoggingWorker.perform_job must log 'failed' on job failure."""
    from robotina.queue.runner import LoggingWorker
    source = inspect.getsource(LoggingWorker.perform_job)
    assert "failed" in source, (
        "LoggingWorker.perform_job must emit a 'failed' log line (QUEUE-07)"
    )


def test_logging_worker_reads_task_type_from_meta():
    """LoggingWorker.perform_job must read task_type from job.meta (for structured logging)."""
    from robotina.queue.runner import LoggingWorker
    source = inspect.getsource(LoggingWorker.perform_job)
    assert 'job.meta.get("task_type"' in source or "job.meta.get('task_type'" in source, (
        "LoggingWorker must read task_type from job.meta — not just job.func_name — for structured log output"
    )


# ---------------------------------------------------------------------------
# Phase 18 / ARCH-02 + ARCH-03 — RED introspection tests (Wave 0)
# ---------------------------------------------------------------------------
# These tests will be GREEN after Wave 1 lands the RobotinaInvocation model and
# the WorkflowRun.triggered_by_invocation_id column.


def test_invocation_trigger_enum_has_full_value_set():
    """D-06: InvocationTrigger must include USER_MESSAGE, WORKFLOW_COMPLETION, CRON
    upfront — Phase 18 only writes USER_MESSAGE rows but the full set ships now to
    avoid ALTER TYPE ADD VALUE in Phase 20."""
    from robotina.queue.models import InvocationTrigger
    values = {e.value for e in InvocationTrigger}
    assert values == {"user_message", "workflow_completion", "cron"}


def test_invocation_status_enum_has_full_value_set():
    """D-07: InvocationStatus must include PENDING, RUNNING, DONE, FAILED upfront."""
    from robotina.queue.models import InvocationStatus
    values = {e.value for e in InvocationStatus}
    assert values == {"pending", "running", "done", "failed"}


def test_robotina_invocation_model_has_required_columns():
    """D-04, D-05, D-10: RobotinaInvocation lives in robotina.queue.models with the
    full Phase-20-ready schema. Phase 18 only WRITES id/conversation_id/trigger/
    trigger_ref_id/status; the rest are nullable slots for Phase 20."""
    from robotina.queue.models import RobotinaInvocation
    cols = RobotinaInvocation.__table__.columns
    assert RobotinaInvocation.__tablename__ == "robotina_invocations"

    # PK
    assert cols["id"].primary_key is True
    # FK to conversations
    assert cols["conversation_id"].nullable is False
    assert any(
        fk.target_fullname == "conversations.id"
        for fk in cols["conversation_id"].foreign_keys
    )
    # trigger (enum, NOT NULL)
    assert cols["trigger"].nullable is False
    # trigger_ref_id (nullable string — CRON variant has no ref initially)
    assert cols["trigger_ref_id"].nullable is True
    # rq_job_id (nullable — populated in Phase 20)
    assert cols["rq_job_id"].nullable is True
    # status (enum, NOT NULL, default PENDING)
    assert cols["status"].nullable is False
    # Phase 20 lifecycle columns (all nullable in Phase 18)
    assert cols["wake_dispatched_at"].nullable is True
    assert cols["started_at"].nullable is True
    assert cols["completed_at"].nullable is True
    # standard timestamps
    assert cols["created_at"] is not None
    assert cols["updated_at"] is not None


def test_robotina_invocation_has_unique_constraint_on_trigger_ref_and_trigger():
    """D-08: UniqueConstraint("trigger_ref_id", "trigger",
    name="ux_invocation_workflow_completion_once") ships in Phase 18 even though
    Phase 18 only writes USER_MESSAGE rows — it is the load-bearing wake-rule
    idempotency guard for Phase 20."""
    from sqlalchemy import UniqueConstraint
    from robotina.queue.models import RobotinaInvocation
    uniques = [
        c for c in RobotinaInvocation.__table__.constraints
        if isinstance(c, UniqueConstraint)
    ]
    matching = [
        c for c in uniques
        if c.name == "ux_invocation_workflow_completion_once"
        and {col.name for col in c.columns} == {"trigger_ref_id", "trigger"}
    ]
    assert len(matching) == 1, f"expected the named unique constraint, got {uniques}"


def test_workflow_run_has_triggered_by_invocation_id_column():
    """ARCH-03 / D-02: WorkflowRun.triggered_by_invocation_id is a NULLABLE FK to
    robotina_invocations.id (no backfill in v1.1)."""
    from robotina.queue.models import WorkflowRun
    col = WorkflowRun.__table__.columns["triggered_by_invocation_id"]
    assert col.nullable is True, "ARCH-03 / D-02: must be nullable in v1.1"
    assert any(
        fk.target_fullname == "robotina_invocations.id"
        for fk in col.foreign_keys
    ), "must FK to robotina_invocations.id"
