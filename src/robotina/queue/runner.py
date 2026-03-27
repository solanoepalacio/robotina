"""RQ worker entrypoint for `uv run agent`.

Starts the task-runner worker that processes jobs from the "agent-tasks" queue.
Fails gracefully when Redis is unreachable — exits with code 1, no unhandled traceback.

IMPORTANT: All jobs enqueued to this worker MUST set result_ttl=-1 and
failure_ttl=-1 (CLAUDE.md requirement: no tasks lost on crash/reboot).
"""
import logging
import os
import sys

from rq import Queue
from rq.worker import SimpleWorker

from robotina.agent.agents import configure_logging

logger = logging.getLogger(__name__)


class LoggingWorker(SimpleWorker):
    """RQ SimpleWorker subclass that emits structured log lines for job lifecycle events.

    Log format: [<queue>] job <id> starting|finished|failed | task_type=<type>

    Runs jobs in-process (no os.fork()) — connection pools, OTel tracer, and other
    global resources are shared directly without post-fork reinitialization.
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


def _setup_langwatch() -> None:
    """Initialize LangWatch once at worker startup.

    Called in main() before worker.work(). No fork-workaround resets needed —
    SimpleWorker runs in-process.
    """
    api_key = os.getenv("LANGWATCH_API_KEY")
    endpoint_url = os.getenv("LANGWATCH_ENDPOINT")
    if not api_key or not endpoint_url:
        logger.warning(
            "LangWatch credentials not set (LANGWATCH_API_KEY, LANGWATCH_ENDPOINT) "
            "— traces will not be sent"
        )
        return

    import langwatch

    # No LangChainInstrumentor — we use the explicit get_langchain_callback()
    # approach in run_task() instead (per LangWatch docs). The callback is
    # passed directly to agent.invoke() RunnableConfig, which captures spans
    # correctly without needing OTel auto-instrumentation.
    langwatch.setup(api_key=api_key, endpoint_url=endpoint_url)
    logger.info("LangWatch initialized (endpoint=%s)", endpoint_url)


def main() -> None:
    """Entry point for `uv run agent`. Starts the sequential RQ task runner."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
        configure_logging()
        # SimpleWorker runs in-process — langwatch.setup() is safe here (no fork).
        _setup_langwatch()
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
