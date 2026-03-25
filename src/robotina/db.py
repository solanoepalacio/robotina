from alembic.config import Config
from alembic import command


def run_migrations():
    """Entry point for `uv run migrate`."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
