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

from robotina.agent.agents import configure_logging

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
        # This runs in the forked work-horse subprocess.
        # Ensure the root logger has a handler at INFO level — without this,
        # logger.info() calls are silently dropped (Python's last-resort handler
        # only outputs WARNING+). No-op if handlers are already configured.
        import logging as _logging
        _logging.basicConfig(level=_logging.INFO)
        _setup_langwatch_in_workhorse()
        task_type = job.meta.get("task_type", job.func_name)
        logger.info("[%s] job %s starting | task_type=%s", job.origin, job.id, task_type)
        success = super().perform_job(job, queue)
        if success:
            logger.info("[%s] job %s finished | task_type=%s", job.origin, job.id, task_type)
        else:
            logger.error("[%s] job %s failed | task_type=%s", job.origin, job.id, task_type)
        return success


def _setup_langwatch_in_workhorse() -> None:
    """Initialize LangWatch in the forked work-horse subprocess.

    Must be called in the work-horse (perform_job), NOT in the parent (main).

    Why: BatchSpanProcessor uses a background thread to flush spans. Python's
    os.fork() does not copy threads — only the calling thread survives. If
    langwatch.setup() runs in the parent, the child inherits a TracerProvider
    whose export thread is dead, and all spans are silently dropped.

    Why the resets: The LangWatch Client is a singleton with ClassVar state.
    The child inherits the parent's already-initialized singleton and the OTel
    global tracer provider (set via a Once guard). We must clear both before
    calling langwatch.setup() so it creates a fresh provider with a live thread,
    rather than hitting the "attach exporter to existing provider" warning path.
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
    import opentelemetry.trace
    from langwatch.client import Client
    from opentelemetry.util._once import Once

    # Reset LangWatch singleton so setup() re-runs fully instead of entering
    # the partial-update path that causes the "existing global tracer" warning.
    Client._reset_instance()

    # Reset OTel global tracer provider. The Once guard prevents
    # set_tracer_provider() from being called twice in one process lifetime.
    # After a fork the guard is inherited in the already-fired state, so we
    # clear it here to allow the fresh provider to be registered.
    opentelemetry.trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]
    opentelemetry.trace._TRACER_PROVIDER_SET_ONCE = Once()  # type: ignore[attr-defined]

    # No LangChainInstrumentor — we use the explicit get_langchain_callback()
    # approach in run_task() instead (per LangWatch docs). The callback is
    # passed directly to agent.invoke() RunnableConfig, which captures spans
    # correctly without needing OTel auto-instrumentation.
    langwatch.setup(api_key=api_key, endpoint_url=endpoint_url)
    logger.info("LangWatch initialized in work-horse (endpoint=%s)", endpoint_url)


def main() -> None:
    """Entry point for `uv run agent`. Starts the sequential RQ task runner."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
        configure_logging()
        # NOTE: Do NOT call langwatch.setup() here. LangWatch must be initialized
        # in the work-horse subprocess (perform_job), not in the parent. If
        # initialized in the parent, the forked child inherits a TracerProvider
        # with a dead BatchSpanProcessor thread and all traces are silently dropped.
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
