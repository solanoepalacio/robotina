import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from alembic.config import Config
from alembic import command


class Base(DeclarativeBase):
    pass


DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://robotina:robotina@localhost:5432/robotina")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def run_migrations():
    """Entry point for `uv run migrate`."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
