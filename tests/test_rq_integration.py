"""Integration tests for RQ queue behavior (QUEUE-04, QUEUE-05, QUEUE-06).

Requires: docker compose up (live Redis at REDIS_URL or redis://localhost:6379).
Run: uv run pytest tests/test_rq_integration.py -x -q

These tests spin up a short-lived LoggingWorker in a background thread.
Each test uses a unique queue name to avoid cross-test pollution.
"""
import os
import uuid

import pytest


def _redis_conn():
    from redis import Redis
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return Redis.from_url(redis_url)


def _run_worker_once(queue_name: str, conn) -> None:
    """Start a LoggingWorker and process jobs until the queue is empty."""
    from robotina.queue.runner import LoggingWorker
    from rq import Queue
    q = Queue(queue_name, connection=conn)
    worker = LoggingWorker([q], connection=conn)
    # burst=True: process all queued jobs then exit — safe for tests
    worker.work(burst=True)


def _no_op_job():
    """Trivial job function — used to test queue plumbing without agent logic."""
    return "ok"


def _failing_job():
    """Job that always raises — used to test FailedJobRegistry."""
    raise RuntimeError("intentional failure for test")


@pytest.mark.integration
def test_job_retention_result_ttl(tmp_path):
    """Jobs with result_ttl=-1 must appear in FinishedJobRegistry after completion (QUEUE-04)."""
    from rq import Queue
    from rq.registry import FinishedJobRegistry

    conn = _redis_conn()
    queue_name = f"test-retention-{uuid.uuid4().hex[:8]}"
    q = Queue(queue_name, connection=conn)

    job = q.enqueue(
        _no_op_job,
        result_ttl=-1,
        failure_ttl=-1,
        meta={"task_type": "test-no-op"},
    )

    # Run worker in foreground (burst mode exits after processing)
    _run_worker_once(queue_name, conn)

    finished = FinishedJobRegistry(queue_name, connection=conn)
    job_ids = finished.get_job_ids()
    assert job.id in job_ids, (
        f"Job {job.id} not in FinishedJobRegistry after completion with result_ttl=-1. "
        f"Found: {job_ids}. This violates QUEUE-04 (no tasks lost)."
    )

    # Cleanup
    conn.delete(f"rq:registry:finished:{queue_name}")


@pytest.mark.integration
def test_failed_job_registry(tmp_path):
    """Failed jobs must appear in FailedJobRegistry after failure (QUEUE-05)."""
    from rq import Queue
    from rq.registry import FailedJobRegistry

    conn = _redis_conn()
    queue_name = f"test-failed-{uuid.uuid4().hex[:8]}"
    q = Queue(queue_name, connection=conn)

    job = q.enqueue(
        _failing_job,
        result_ttl=-1,
        failure_ttl=-1,
        meta={"task_type": "test-failing"},
    )

    _run_worker_once(queue_name, conn)

    failed = FailedJobRegistry(queue_name, connection=conn)
    job_ids = failed.get_job_ids()
    assert job.id in job_ids, (
        f"Failed job {job.id} not in FailedJobRegistry. "
        f"Found: {job_ids}. This violates QUEUE-05 (dead-letter queue)."
    )


@pytest.mark.integration
def test_at_front_enqueue(tmp_path):
    """at_front=True must enqueue a job at the front of the queue (QUEUE-06)."""
    from rq import Queue

    conn = _redis_conn()
    queue_name = f"test-atfront-{uuid.uuid4().hex[:8]}"
    q = Queue(queue_name, connection=conn)

    # Enqueue normal job first (back of queue)
    job_normal = q.enqueue(
        _no_op_job,
        result_ttl=-1,
        failure_ttl=-1,
        meta={"task_type": "test-normal"},
    )
    # Enqueue urgent job second (at_front=True → should be processed first)
    job_urgent = q.enqueue(
        _no_op_job,
        result_ttl=-1,
        failure_ttl=-1,
        at_front=True,
        meta={"task_type": "test-urgent"},
    )

    # Verify queue ordering: urgent job should be first in queue
    job_ids = q.job_ids
    assert job_ids[0] == job_urgent.id, (
        f"Urgent job should be first in queue. Queue order: {job_ids}. "
        f"Urgent: {job_urgent.id}, Normal: {job_normal.id}"
    )

    # Run both jobs
    _run_worker_once(queue_name, conn)
