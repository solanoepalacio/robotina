import sys
import os
from logging.config import fileConfig
from alembic import context

# Ensure src/ is on path for future model imports (Phase 2+)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

config = context.config

# Allow DATABASE_URL env var to override alembic.ini value
_db_url = os.environ.get("DATABASE_URL")
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from robotina.db import Base
import robotina.gateway.models   # noqa: F401 — registers Conversation, StoredMessage with Base.metadata
import robotina.queue.models     # noqa: F401 — registers WorkflowRun, WorkflowRunStep with Base.metadata
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    from sqlalchemy import engine_from_config, pool
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
                                     prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
