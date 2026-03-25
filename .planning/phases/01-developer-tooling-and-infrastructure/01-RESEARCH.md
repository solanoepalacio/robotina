# Phase 1: Developer Tooling and Infrastructure - Research

**Researched:** 2026-03-25
**Domain:** Python project scaffolding (uv), Docker Compose (Postgres 15 + Redis 7 + RQ Dashboard), Alembic migrations, RQ task-runner stub
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Use `src/robotina/` layout — single top-level package with sub-packages matching the spec draft structure: `robotina.agent`, `robotina.queue`, `robotina.gateway`, `robotina.llm`, `robotina.scheduler`
- **D-02:** `pyproject.toml` declares one package (`robotina`) with `packages = [{include = "robotina", from = "src"}]` (or equivalent uv/hatch discovery)
- **D-03:** RQ Dashboard is a docker-compose service — starts automatically with `docker compose up`, no manual step required. Use the `eoranged/rq-dashboard` image, expose on port 9181, connect to the Redis container via internal network.

### Claude's Discretion

- Stub depth for `uv run agent` — should import the queue module and attempt to start an RQ worker (fails gracefully if Redis is unreachable), not a bare `print` stub
- Stub depth for `uv run experiments.<task_type>` — minimal stubs that can be invoked without error; actual agent logic added in later phases
- Redis AOF configuration method — command-line args in docker-compose (`command: redis-server --appendonly yes --appendfsync always`) vs mounted `redis.conf`; either is acceptable as long as `appendfsync always` is set
- Alembic initial migration — create an empty "init" migration to verify the toolchain works; Phase 2 adds real model migrations
- `.env.example` — include a documented template of all expected env vars; developers copy to `.env` for local runs

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | Developer can spin up Postgres and Redis via `docker compose up` | Docker Compose v2 service definitions with postgres:15 and redis:7 images; Redis AOF via command-line args |
| INFRA-02 | Project is managed with uv (`pyproject.toml`, dependency groups, lock file) | uv 0.10.7 available; src layout via `[tool.uv.sources]` or hatch discovery; `uv sync` generates lock file |
| INFRA-03 | Developer can run the task runner via `uv run agent` | `[project.scripts]` entry in pyproject.toml mapping to `robotina.queue.runner:main`; graceful Redis-unreachable handling |
| INFRA-04 | Developer can run experiments via `uv run experiments.<task_type>` | Script aliases like `experiments.recipe_research` pointing to `experiments/recipe_research.py:main`; stub bodies only |
| INFRA-05 | Developer can run Alembic migrations via `uv run migrate` | `[project.scripts]` entry calling `alembic upgrade head`; empty init migration verifies toolchain |
| INFRA-06 | RQ Dashboard is accessible for job inspection | `eoranged/rq-dashboard:latest` Docker image on port 9181; connects to Redis container on internal network |
</phase_requirements>

---

## Summary

Phase 1 is a pure scaffolding phase: no business logic, no models, no agent behavior. The deliverable is a working local developer environment where every toolchain command executes without error against the fully pinned stack (Python 3.12, uv, Docker Compose, Postgres 15, Redis 7 with AOF, Alembic, RQ Dashboard).

The critical decisions are already locked: `src/robotina/` package layout with five sub-packages, RQ Dashboard as a Docker Compose service using the `eoranged/rq-dashboard` Docker image, and Redis AOF configured via docker-compose command-line args. The planner's job is to sequence file creation tasks so that each task leaves the repo in a runnable state.

The main pitfall at this phase is pyproject.toml script mapping: uv's `[project.scripts]` only supports `module:function` syntax, not arbitrary shell commands. Alembic's `upgrade head` must be wrapped in a thin Python function that calls `alembic.config.main(argv=["upgrade", "head"])`. Similarly, the `uv run agent` stub must import the rq worker entrypoint and call it programmatically, not via subprocess.

**Primary recommendation:** Wire all five `uv run` entry points to thin Python wrapper functions, stub experiment scripts with `if __name__ == "__main__": main()` bodies, configure Redis AOF with docker-compose command args (not a mounted redis.conf), and create a single empty Alembic "init" migration to prove the migration toolchain works end-to-end.

---

## Project Constraints (from CLAUDE.md)

All CLAUDE.md directives apply. Key constraints for this phase:

| Directive | Impact on Phase 1 |
|-----------|-------------------|
| Python 3.12+ | Pin `requires-python = ">=3.12"` in pyproject.toml; use uv to install 3.12 interpreter |
| SQLAlchemy 2.x `Mapped` + `mapped_column` | Include `sqlalchemy>=2.0` in runtime deps even though no models yet |
| Redis AOF `appendfsync always` | Set in docker-compose `command:` args, not default config |
| `result_ttl=-1` and `failure_ttl=-1` | Relevant to Phase 2, but worker stub should document this pattern |
| No `AgentExecutor` | Not relevant to Phase 1; document in code comments for Phase 4 |
| uv for all package management | No pip usage; all installs via `uv add` / `uv sync` |

---

## Standard Stack

### Core (Phase 1 scope)

| Library | Verified Version | Purpose | Why Standard |
|---------|-----------------|---------|--------------|
| Python | 3.12 (pin; 3.12.12 available via uv) | Runtime | CLAUDE.md specifies 3.12+; 3.12 has wider ecosystem compat than 3.13 |
| uv | 0.10.7 (installed) | Project management, scripts | CLAUDE.md mandates uv; replaces pip/virtualenv |
| SQLAlchemy | 2.0.48 (PyPI verified) | ORM (no models yet, dep pinned) | CLAUDE.md mandates 2.x `Mapped` style |
| Alembic | 1.18.4 (PyPI verified) | Migrations | Standard SQLAlchemy companion |
| RQ | 2.7.0 (PyPI verified) | Task queue | CLAUDE.md requires RQ 2.5+; 2.7 has native scheduler |
| redis (py) | 7.4.0 (PyPI verified) | RQ backing store client | Bundled with RQ; `redis>=4.0` required |
| psycopg2-binary | 2.9.11 (PyPI verified) | Postgres driver | Simpler than asyncpg for sync SQLAlchemy context |
| pydantic | 2.12.5 (PyPI verified) | Input/output models (stubs) | CLAUDE.md mandates v2 exclusively |

### Supporting (declared in pyproject.toml but not exercised in Phase 1)

| Library | Verified Version | Purpose | When to Use |
|---------|-----------------|---------|-------------|
| langchain | 1.2.13 | Agent orchestration | Phase 4+ |
| langchain-core | 1.2.22 | Base abstractions | Phase 4+ |
| langgraph | 1.1.3 | `create_react_agent` | Phase 4+ |
| langchain-anthropic | 1.4.0 | Claude adapter | Phase 4+ |
| langchain-openai | 1.1.12 | OpenAI adapter | Phase 4+ |
| langchain-ollama | 1.0.1 | Ollama adapter | Phase 4+ dev |
| langwatch | 0.17.0 | LLM trace collection | Phase 4+ |
| opentelemetry-sdk | 1.40.0 | OTel SDK | Phase 4+ |
| opentelemetry-api | 1.40.0 | OTel API | Phase 4+ |
| python-telegram-bot | 22.7 | Telegram bot | Phase 3+ |
| tavily-python | 0.7.23 | Web search | Phase 8+ |
| fastapi | 0.135.2 | Scheduler HTTP API | Phase v2 |
| uvicorn | 0.42.0 | ASGI server | Phase v2 |
| httpx | 0.28.1 | Async HTTP client | Phase 3+ |

**Version verification:** All versions confirmed against PyPI on 2026-03-25.

**Installation (Phase 1 runtime deps):**
```bash
uv add sqlalchemy>=2.0 alembic>=1.13 rq>=2.5 redis>=4.0 psycopg2-binary pydantic>=2.7
```

**Installation (Phase 1 dev deps):**
```bash
uv add --dev pytest pytest-asyncio rq-dashboard
```

**Declare future deps now so lock file is stable across phases:**
```bash
uv add langchain>=0.3 langchain-core>=0.3 langgraph>=0.2 \
  langchain-anthropic>=0.3 langchain-openai>=0.2 langchain-ollama>=0.2 \
  langwatch>=0.1 opentelemetry-sdk>=1.25 opentelemetry-api>=1.25 \
  python-telegram-bot>=21 tavily-python>=0.3 httpx>=0.27 fastapi>=0.115 uvicorn>=0.30
```

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `eoranged/rq-dashboard` Docker image | `rq-dashboard` pip package run separately | Docker image is simpler (locked decision D-03); pip approach requires extra process management |
| Redis command-line AOF args | Mounted `redis.conf` file | CLI args are simpler for Docker Compose; mounted config is more portable. CONTEXT.md says either is acceptable — CLI args chosen for simplicity |
| Empty Alembic init migration | No migration at all in Phase 1 | Empty migration proves toolchain (env, alembic.ini, migration directory) works before Phase 2 adds real models |

---

## Architecture Patterns

### Recommended Project Structure

This matches spec §"Draft Project Structure" plus the D-01/D-02 decisions:

```
robotina/
├── src/
│   └── robotina/              # D-01: single top-level package
│       ├── __init__.py
│       ├── agent/             # Phase 4+ content, empty sub-package now
│       │   ├── __init__.py
│       │   ├── skills/        # household-manager skill moved here
│       │   │   └── household-manager/
│       │   └── ...
│       ├── queue/             # Phase 2 content; runner stub here
│       │   ├── __init__.py
│       │   └── runner.py      # uv run agent entrypoint
│       ├── gateway/           # Phase 3 content, empty sub-package now
│       │   └── __init__.py
│       ├── llm/               # Phase 4 content, empty sub-package now
│       │   └── __init__.py
│       └── scheduler/         # Phase v2 content, empty sub-package now
│           └── __init__.py
├── experiments/               # Stub scripts for INFRA-04
│   ├── recipe_research.py
│   ├── recipe_load.py
│   └── send_notification.py
├── tests/
│   └── __init__.py
├── migrations/                # Alembic migration directory
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_init.py       # empty "init" migration
├── alembic.ini
├── docker-compose.yml
├── .env.example
├── pyproject.toml
└── README.md
```

### Pattern 1: uv Script Entry Points

**What:** `[project.scripts]` in pyproject.toml maps `uv run <name>` to `module:function`.
**When to use:** For every `uv run` shortcut; uv does NOT support shell string commands — only `module:callable` format.

```toml
# Source: https://docs.astral.sh/uv/concepts/projects/config/#project-scripts
[project.scripts]
agent = "robotina.queue.runner:main"
migrate = "robotina.db:run_migrations"
"experiments.recipe_research" = "experiments.recipe_research:main"
"experiments.recipe_load" = "experiments.recipe_load:main"
"experiments.send_notification" = "experiments.send_notification:main"
```

**Critical:** The `experiments` package must be importable. Either add `experiments/` as a second package in pyproject.toml, or place experiment scripts outside `src/` and use `tool.hatch.build.targets.wheel.packages` / `tool.uv` source discovery. The simplest approach is to add `experiments` as a non-installed script directory and reference via `scripts` or place `experiments/` at root (not under `src/`) and declare it as a separate package.

**Concrete pyproject.toml approach:**
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "robotina"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [...]

[project.scripts]
agent = "robotina.queue.runner:main"
migrate = "robotina.db:run_migrations"
"experiments.recipe_research" = "experiments.recipe_research:main"
"experiments.recipe_load" = "experiments.recipe_load:main"
"experiments.send_notification" = "experiments.send_notification:main"

[tool.hatch.build.targets.wheel]
packages = ["src/robotina", "experiments"]
```

### Pattern 2: Alembic Wrapper for `uv run migrate`

**What:** Since `[project.scripts]` requires a Python callable, Alembic's CLI cannot be called directly. A thin wrapper calls `alembic.config.main`.
**When to use:** Always for the `migrate` script entry point.

```python
# src/robotina/db.py
from alembic.config import Config
from alembic import command

def run_migrations():
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
```

### Pattern 3: RQ Worker Stub with Graceful Failure

**What:** The `uv run agent` entrypoint should attempt to connect to Redis and start the worker, but not crash with an unhandled traceback if Redis is unreachable. This satisfies INFRA-03 at Phase 1 without requiring Redis to be up during the test.
**When to use:** For the `robotina.queue.runner:main` stub.

```python
# src/robotina/queue/runner.py
import sys
import logging

logger = logging.getLogger(__name__)

def main():
    try:
        from redis import Redis
        from rq import Worker, Queue
        redis_conn = Redis.from_url("redis://localhost:6379")
        redis_conn.ping()
        queue = Queue("agent-tasks", connection=redis_conn)
        worker = Worker([queue], connection=redis_conn)
        logger.info("Starting task runner worker (concurrency=1)...")
        worker.work()
    except Exception as exc:
        logger.error("Task runner failed to start: %s", exc)
        sys.exit(1)
```

### Pattern 4: Docker Compose with Redis AOF

**What:** Redis AOF configured via `command:` args in docker-compose — no mounted redis.conf required.
**When to use:** This is the locked approach per CONTEXT.md discretion guidance.

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: robotina
      POSTGRES_USER: robotina
      POSTGRES_PASSWORD: robotina
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    command: redis-server --appendonly yes --appendfsync always
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  rq-dashboard:
    image: eoranged/rq-dashboard:latest
    ports:
      - "9181:9181"
    environment:
      RQ_DASHBOARD_REDIS_URL: redis://redis:6379
    depends_on:
      - redis

volumes:
  postgres_data:
  redis_data:
```

### Pattern 5: Alembic Configuration for src layout

**What:** `alembic.ini` and `migrations/env.py` must be configured for the `src/` package layout.
**When to use:** Always when models live under `src/robotina/`.

```ini
# alembic.ini
[alembic]
script_location = migrations
sqlalchemy.url = postgresql://robotina:robotina@localhost:5432/robotina
```

```python
# migrations/env.py — relevant excerpt
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# target_metadata = Base.metadata  # Phase 2 will set this
target_metadata = None  # Phase 1: empty migration only
```

### Anti-Patterns to Avoid

- **Shell string in `[project.scripts]`:** `agent = "python -m robotina.queue.runner"` does NOT work. Only `module:callable` format is supported by uv/pip entry points.
- **Importing models in `migrations/env.py` before they exist:** Causes import errors in Phase 1. Set `target_metadata = None` until Phase 2 creates models.
- **Relying on Docker internal hostname from host machine:** `redis://redis:6379` only works inside Docker network. `uv run agent` on the host must use `redis://localhost:6379`. Use env var `REDIS_URL` defaulting to `redis://localhost:6379`.
- **`appendonly yes` without `appendfsync always`:** `appendonly yes` enables AOF but defaults to `appendfsync everysec`. Both flags must be set: `--appendonly yes --appendfsync always`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RQ Dashboard UI | Custom job monitoring web app | `eoranged/rq-dashboard` Docker image | Full-featured, zero config, Docker-native |
| Migration runner | Custom schema migration script | Alembic + thin wrapper | Auto-generates migrations, handles upgrade/downgrade, version history |
| Redis connection pooling | Custom connection manager | `redis-py` built-in connection pool | Thread-safe, configurable, tested at scale |
| Worker process management | Custom process spawner | `rq.Worker` | Handles SIGTERM, job lifecycle, retry semantics built in |
| Environment variable loading | Per-module `os.environ` reads | `python-dotenv` / Docker Compose env injection | Consistent load order, `.env.example` documents all vars |

**Key insight:** This phase is infrastructure scaffolding — every component has a battle-tested standard tool. The only custom code is thin wrapper functions that bridge uv's entry point format to library CLIs.

---

## Common Pitfalls

### Pitfall 1: uv Script Format Mismatch

**What goes wrong:** Developer writes `agent = "python -m robotina.queue.runner"` or `migrate = "alembic upgrade head"` in `[project.scripts]`. Running `uv run agent` fails with a confusing error.
**Why it happens:** `[project.scripts]` follows the Python entry_points specification which only supports `module:callable` format. It is not a shell command runner.
**How to avoid:** Every script value must be `"some.module.path:function_name"`. Wrap CLI tools (alembic, rq) in thin Python functions.
**Warning signs:** `uv run agent` exits with `ModuleNotFoundError` or `AttributeError: module has no attribute`.

### Pitfall 2: experiments/ Package Not Importable

**What goes wrong:** `uv run experiments.recipe_research` fails with `ModuleNotFoundError: No module named 'experiments'`.
**Why it happens:** uv resolves `[project.scripts]` entries by importing the module. If `experiments/` is not declared as a package in pyproject.toml, it is not on the Python path.
**How to avoid:** Declare `experiments` as a package in `[tool.hatch.build.targets.wheel] packages` (or equivalent). Alternatively, use `uv run python -m experiments.recipe_research` pattern — but the locked requirement is `uv run experiments.recipe_research` so package declaration is required.
**Warning signs:** Works with `python experiments/recipe_research.py` but fails with `uv run experiments.recipe_research`.

### Pitfall 3: Alembic Cannot Find src/ Models

**What goes wrong:** Phase 2 adds models; Alembic autogenerate finds nothing because `sys.path` doesn't include `src/`.
**Why it happens:** Alembic's `env.py` runs in the project root context where `src/` is not automatically on the path.
**How to avoid:** Add `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))` in `migrations/env.py`. Do this in Phase 1 so it's correct from the start.
**Warning signs:** `alembic revision --autogenerate` produces empty migration when models clearly exist.

### Pitfall 4: Redis AOF Incomplete Configuration

**What goes wrong:** Redis loses tasks on crash/reboot despite AOF being "enabled".
**Why it happens:** `--appendonly yes` enables AOF but defaults to `appendfsync everysec` (data loss up to 1 second). The CLAUDE.md requirement is `appendfsync always`.
**How to avoid:** Always set both: `command: redis-server --appendonly yes --appendfsync always`.
**Warning signs:** `CONFIG GET appendfsync` returns `everysec` instead of `always` when exec'd inside the container.

### Pitfall 5: Alembic Database URL Hardcoded

**What goes wrong:** `alembic.ini` has a hardcoded connection string. CI/CD and other developers cannot override it without editing a checked-in file.
**Why it happens:** Default `alembic init` output puts the URL directly in `alembic.ini`.
**How to avoid:** In `migrations/env.py`, override the URL from `DATABASE_URL` environment variable: `config.set_main_option("sqlalchemy.url", os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url")))`.
**Warning signs:** Alembic works locally but fails in CI because the Docker Compose hostname differs.

### Pitfall 6: Python 3.13 on System vs 3.12 Pinned

**What goes wrong:** `uv run agent` uses the system Python 3.13 instead of the pinned 3.12, causing subtle incompatibilities with some langchain internals.
**Why it happens:** System Python is 3.13.7; uv picks up system interpreter unless `.python-version` file or `requires-python` pins it.
**How to avoid:** Create `.python-version` file with `3.12` at project root. uv respects this file. Alternatively, uv will respect `requires-python = ">=3.12,<3.13"` strictly.
**Warning signs:** `uv run python --version` reports 3.13 instead of 3.12.

---

## Code Examples

### pyproject.toml skeleton (Phase 1)

```toml
# Source: https://docs.astral.sh/uv/concepts/projects/config/
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "robotina"
version = "0.1.0"
description = "AI agent component of the household management system"
requires-python = ">=3.12,<3.13"
dependencies = [
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "rq>=2.5",
    "redis>=4.0",
    "psycopg2-binary",
    "pydantic>=2.7",
    "langchain>=0.3",
    "langchain-core>=0.3",
    "langgraph>=0.2",
    "langchain-anthropic>=0.3",
    "langchain-openai>=0.2",
    "langchain-ollama>=0.2",
    "langwatch>=0.1",
    "opentelemetry-sdk>=1.25",
    "opentelemetry-api>=1.25",
    "python-telegram-bot>=21",
    "tavily-python>=0.3",
    "httpx>=0.27",
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "python-dotenv",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio",
    "rq-dashboard",
]

[project.scripts]
agent = "robotina.queue.runner:main"
migrate = "robotina.db:run_migrations"
"experiments.recipe_research" = "experiments.recipe_research:main"
"experiments.recipe_load" = "experiments.recipe_load:main"
"experiments.send_notification" = "experiments.send_notification:main"

[tool.hatch.build.targets.wheel]
packages = ["src/robotina", "experiments"]
```

### Minimal experiment stub

```python
# experiments/recipe_research.py
import logging

logger = logging.getLogger(__name__)

def main():
    """Stub for recipe research experiment. Implemented in Phase 8."""
    logger.info("recipe_research experiment: not yet implemented")

if __name__ == "__main__":
    main()
```

### Alembic env.py for src layout

```python
# migrations/env.py — key additions vs alembic default
import sys
import os
from alembic import context

# Ensure src/ is on path for future model imports (Phase 2+)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

config = context.config

# Allow DATABASE_URL env var to override alembic.ini value
import os as _os
_db_url = _os.environ.get("DATABASE_URL")
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)

# Phase 1: no models yet
target_metadata = None
```

### .env.example template

```bash
# Database
DATABASE_URL=postgresql://robotina:robotina@localhost:5432/robotina

# Redis
REDIS_URL=redis://localhost:6379

# LangWatch (Phase 4+)
LANGWATCH_API_KEY=
LANGWATCH_ENDPOINT=

# Telegram (Phase 3+)
TELEGRAM_BOT_TOKEN=

# LLM API tokens (Phase 4+)
RECIPE_RESEARCH_API_TOKEN=
RECIPE_LOAD_API_TOKEN=
HANDLE_INCOMING_MESSAGE_API_TOKEN=
SEND_NOTIFICATION_API_TOKEN=

# Household Manager API (Phase 3+)
HOUSEHOLD_MANAGER_API_URL=
HOUSEHOLD_MANAGER_API_KEY=

# Agent overrides (Phase 4+)
AGENT_OVERRIDES_FILEPATH=
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-----------------|--------------|--------|
| `pip` + `requirements.txt` + `virtualenv` | `uv` with `pyproject.toml` + lockfile | 2023-2024 | Single binary, 10-100x faster installs, reproducible |
| `rq-scheduler` add-on package | Native RQ scheduler (RQ >= 2.0, matured in 2.5) | RQ 2.0 (2022) | No separate process; `--with-scheduler` flag on worker |
| `AgentExecutor` (LangChain legacy) | `create_react_agent` from `langgraph.prebuilt` | LangChain 0.2 (2024) | `AgentExecutor` deprecated; LangGraph approach is the current standard |
| `aioredis` standalone | `redis-py` with async support (redis >= 4.2) | 2022 | `aioredis` merged into redis-py; no separate package needed |
| Pydantic v1 field syntax | Pydantic v2 (`list[...]`, `Literal[...]` without quotes) | Pydantic v2.0 (2023) | LangChain 0.3 requires v2; v1 compat shim removed |

**Deprecated/outdated:**
- `rq-scheduler` PyPI package: superseded by native RQ scheduler; do not install
- `aioredis` PyPI package: merged into `redis` package; do not install separately
- LangChain `AgentExecutor`: deprecated in 0.2; use `langgraph.prebuilt.create_react_agent`

---

## Open Questions

1. **`eoranged/rq-dashboard` image stability**
   - What we know: Image exists on Docker Hub with tags `latest`, `v0.6.3`, `v0.6.2`; decision D-03 locks this image
   - What's unclear: Whether `eoranged/rq-dashboard:latest` is maintained and compatible with RQ 2.7 — this is a community image, not the official `rq-dashboard` PyPI package maintainer's image
   - Recommendation: Use `eoranged/rq-dashboard:latest` as decided; if it fails to connect or crashes, fall back to the `rq-dashboard` pip package run as a separate docker-compose service using the official Python base image

2. **`experiments/` as an importable package vs script directory**
   - What we know: `uv run experiments.recipe_research` requires `experiments` to be importable as a package
   - What's unclear: Whether hatchling's `packages = ["src/robotina", "experiments"]` correctly handles the root-level (non-src) experiments directory in all uv versions
   - Recommendation: Add `experiments/__init__.py` and verify `uv run experiments.recipe_research` works immediately after pyproject.toml is created; adjust package discovery if needed

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| uv | INFRA-02, all scripts | Yes | 0.10.7 | None required |
| Docker | INFRA-01, INFRA-06 | Yes | 29.3.0 | None required |
| Docker Compose (v2) | INFRA-01, INFRA-06 | Yes | v5.1.1 | None required |
| Python 3.12 | All Python code | Yes (via uv) | 3.12.12 available via uv | uv installs on demand |
| postgres:15 Docker image | INFRA-01 | Yes (image cached) | postgres:15 | Pull on first use |
| redis:7 Docker image | INFRA-01 | Not confirmed cached | 7.x (will pull) | Auto-pull on `docker compose up` |
| eoranged/rq-dashboard Docker image | INFRA-06 | Not confirmed cached | latest | Auto-pull on `docker compose up` |

**Missing dependencies with no fallback:** None — all required tools are available.

**Missing dependencies with fallback:** None at this phase.

**Note:** System Python is 3.13.7. uv must be configured to use 3.12 via `.python-version` file — this is a task in Wave 0.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (no config file yet — Wave 0 gap) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` section — Wave 0 |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | `docker compose up` starts Postgres 15 + Redis 7 with AOF | smoke / manual | Manual: `docker compose up -d && docker exec robotina-redis-1 redis-cli CONFIG GET appendfsync` | Wave 0 gap |
| INFRA-02 | uv project valid: pyproject.toml parses, lock file generated | smoke | `uv sync --dry-run` | Wave 0 gap |
| INFRA-03 | `uv run agent` exits with non-zero (Redis unreachable) but does not traceback | unit | `uv run pytest tests/test_runner.py::test_agent_entrypoint_graceful_failure -x` | Wave 0 gap |
| INFRA-04 | `uv run experiments.recipe_research` exits 0 | smoke | `uv run experiments.recipe_research` | Wave 0 gap |
| INFRA-05 | `uv run migrate` runs Alembic to completion | integration | `uv run pytest tests/test_migrations.py::test_migrate_runs -x` (requires Postgres) | Wave 0 gap |
| INFRA-06 | RQ Dashboard responds at port 9181 | smoke / manual | Manual: `curl -s -o /dev/null -w "%{http_code}" http://localhost:9181` — expect 200 | Wave 0 gap |

**Note on INFRA-01 and INFRA-06:** These require Docker services running; they are best verified manually or as part of integration test environment. Unit tests can verify config file correctness (AOF args present in docker-compose.yml) as a proxy.

### Sampling Rate

- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** All tests green + manual smoke (`docker compose up`, all `uv run` commands, `curl localhost:9181`)

### Wave 0 Gaps

- [ ] `tests/__init__.py` — make tests an importable package
- [ ] `tests/test_runner.py` — covers INFRA-03 (graceful Redis failure)
- [ ] `tests/test_migrations.py` — covers INFRA-05 (requires Postgres connection)
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` section with `testpaths = ["tests"]`
- [ ] Framework install: `uv add --dev pytest pytest-asyncio` — not installed yet

---

## Sources

### Primary (HIGH confidence)

- PyPI verified 2026-03-25 — all package versions confirmed via `https://pypi.org/pypi/{pkg}/json`
- Docker Hub API verified 2026-03-25 — `eoranged/rq-dashboard` tags confirmed
- uv 0.10.7 — installed and `--version` confirmed on this machine
- Docker 29.3.0, Docker Compose v5.1.1 — installed and confirmed on this machine
- Python 3.13.7 (system) / 3.12.12 (available via uv) — confirmed via `uv python list`
- `plans/01-kickoff/spec.md` §"Draft Project Structure" and §"Developer Tooling Requirements" — read directly
- `.planning/phases/01-developer-tooling-and-infrastructure/01-CONTEXT.md` — locked decisions D-01, D-02, D-03
- `CLAUDE.md` — all technology constraints and mandatory patterns

### Secondary (MEDIUM confidence)

- uv `[project.scripts]` format: `module:callable` only — standard Python entry_points spec, widely documented
- Alembic `env.py` `sys.path` pattern for src layouts — standard pattern, multiple tutorials confirm

### Tertiary (LOW confidence)

- `eoranged/rq-dashboard` Docker image compatibility with RQ 2.7 — not explicitly verified; image tags suggest maintenance but RQ 2.7 may be newer than the image was last tested against

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against PyPI 2026-03-25
- Architecture: HIGH — locked decisions from CONTEXT.md + spec §"Draft Project Structure" are authoritative
- Pitfalls: HIGH — script entry point format and src layout issues are well-documented, AOF config verified from Redis docs
- Environment availability: HIGH — all tools probed locally

**Research date:** 2026-03-25
**Valid until:** 2026-04-24 (30 days — stable infrastructure, versions unlikely to change)
