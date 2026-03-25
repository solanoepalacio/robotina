"""Tests for uv run agent entrypoint (INFRA-03).

Verifies that the agent runner fails gracefully when Redis is unreachable
(exits with sys.exit(1), no unhandled exception propagates).
"""
import subprocess
import sys


def test_agent_entrypoint_graceful_failure():
    """uv run agent must exit non-zero but not traceback when Redis is unreachable.

    Uses an invalid Redis URL to guarantee connection failure in any environment.
    """
    result = subprocess.run(
        ["uv", "run", "agent"],
        capture_output=True,
        text=True,
        env={**__import__('os').environ, "REDIS_URL": "redis://localhost:19999"},  # invalid port
        cwd=str(__import__('pathlib').Path(__file__).parent.parent),
    )
    # Must exit non-zero (connection failed, worker could not start)
    assert result.returncode != 0, (
        f"Expected non-zero exit when Redis unreachable, got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # Must NOT contain an unhandled Python traceback
    assert "Traceback (most recent call last)" not in result.stderr, (
        f"Unhandled traceback detected — runner must catch exceptions gracefully.\n"
        f"stderr: {result.stderr}"
    )


def test_agent_queue_name():
    """The runner must use the 'agent-tasks' queue name (downstream phases depend on this)."""
    from robotina.queue.runner import main
    import inspect
    source = inspect.getsource(main)
    assert "agent-tasks" in source, (
        "runner.main() must use queue name 'agent-tasks' — downstream phases enqueue to this queue"
    )
