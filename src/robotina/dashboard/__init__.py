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
    uvicorn.run(
        "robotina.dashboard.app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
