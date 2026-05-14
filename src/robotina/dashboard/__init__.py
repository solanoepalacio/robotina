"""Robotina Queue Dashboard — read-only FastAPI surface over Postgres.

Phase 13 / D-01: this package is independent of all robotina.* modules
except robotina.db, robotina.queue.models, robotina.queue.task_types.
Other robotina.* modules MUST NOT import from this package.
"""
# main() is defined here so `uv run dashboard` resolves to this module.
# The FastAPI app object lives in robotina.dashboard.app and is imported
# lazily inside main() to keep this module's import side-effect-free
# (so test_app_starts.py can import robotina.dashboard without spinning
# up uvicorn).


def main() -> None:
    """Entry point for `uv run dashboard`."""
    import os
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv()
    port = int(os.environ.get("DASHBOARD_PORT", "8001"))
    # WR-01: default to loopback. The dashboard has no auth (SPEC out of
    # scope) and exposes shared_context / step_input / failure_reason —
    # binding to 0.0.0.0 by default would leak data on any reachable
    # interface. Compose sets DASHBOARD_HOST=0.0.0.0 explicitly because
    # uvicorn must accept connections from outside its container.
    host = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
    uvicorn.run(
        "robotina.dashboard.app:app",
        host=host,
        port=port,
        log_level="info",
    )
