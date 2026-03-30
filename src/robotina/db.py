import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from alembic.config import Config
from alembic import command


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL", "postgresql://robotina:robotina@localhost:5432/robotina")
        _engine = create_engine(url)
    return _engine


def SessionLocal() -> Session:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=_get_engine())
    return _session_factory()


def run_migrations():
    """Entry point for `uv run migrate`."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
