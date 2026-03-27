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
