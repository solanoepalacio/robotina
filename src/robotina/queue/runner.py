"""RQ worker entrypoint for `uv run agent`.

Starts the task-runner worker that processes jobs from the "agent-tasks" queue.
Fails gracefully when Redis is unreachable — exits with code 1, no unhandled traceback.

IMPORTANT: All jobs enqueued to this worker MUST set result_ttl=-1 and
failure_ttl=-1 (CLAUDE.md requirement: no tasks lost on crash/reboot).
"""
import logging
import os
import sys

from rq import Queue, Worker

logger = logging.getLogger(__name__)


class LoggingWorker(Worker):
    """RQ Worker subclass that emits structured log lines for job lifecycle events.

    Log format: [<queue>] job <id> starting|finished|failed | task_type=<type>

    This is the single location for all job lifecycle logging — individual job
    functions do NOT need to emit start/finish/fail log lines.

    Note: perform_job() runs inside the forked work-horse subprocess.
    Do not access parent-process state (DB connections, cached objects) here.
    """

    def perform_job(self, job, queue) -> bool:
        task_type = job.meta.get("task_type", job.func_name)
        logger.info("[%s] job %s starting | task_type=%s", job.origin, job.id, task_type)
        success = super().perform_job(job, queue)
        if success:
            logger.info("[%s] job %s finished | task_type=%s", job.origin, job.id, task_type)
        else:
            logger.error("[%s] job %s failed | task_type=%s", job.origin, job.id, task_type)
        return success


def main() -> None:
    """Entry point for `uv run agent`. Starts the sequential RQ task runner."""
    try:
        from redis import Redis

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        redis_conn = Redis.from_url(redis_url)
        redis_conn.ping()
        queue = Queue("agent-tasks", connection=redis_conn)
        worker = LoggingWorker([queue], connection=redis_conn)
        logger.info("Starting task runner worker (concurrency=1)...")
        # IMPORTANT: All jobs enqueued to this worker MUST set result_ttl=-1 and
        # failure_ttl=-1 (CLAUDE.md requirement — no tasks lost on crash/reboot).
        worker.work()
    except Exception as exc:
        logger.error("Task runner failed to start: %s", exc)
        sys.exit(1)
