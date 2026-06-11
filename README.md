# Robotina

AI agent component of a household management system. Listens for Telegram messages, interprets intent, and executes household tasks — answering questions about recipes, meal plans, and orchestrating multi-step workflows.

## Requirements

- [uv](https://docs.astral.sh/uv/) >= 0.4
- Docker + Docker Compose
- Python 3.12 (managed by uv via `.python-version`)

## Setup

**1. Install dependencies**

```bash
uv sync --dev
```

**2. Configure environment**

```bash
cp .env.example .env
# Edit .env — DATABASE_URL and REDIS_URL work out of the box with docker compose
```

**3. Start infrastructure**

```bash
docker compose up -d
```

**4. Run migrations**

```bash
uv run migrate
```

## Running

**Full system (Telegram gateway + task runner worker)**

```bash
uv run all
```

This launches both the Telegram bot polling loop and the RQ task runner as concurrent child processes. Use this command for end-to-end operation. Stop with Ctrl+C.

**Task runner only**

```bash
uv run agent
```

Starts the sequential RQ worker on the `agent-tasks` queue. Does NOT start Telegram polling. Use this when running the gateway separately or when processing queued jobs without an active bot session.

**Telegram gateway only**

```bash
uv run gateway
```

Starts the Telegram bot in polling mode. Incoming messages are persisted and enqueued to `agent-tasks`. Requires `TELEGRAM_BOT_TOKEN` env var. Does NOT process the queue — requires `uv run agent` running concurrently.

**Run experiments**

```bash
uv run experiments.recipe_research
uv run experiments.recipe_load
uv run experiments.send_notification
```

**RQ Dashboard** — inspect job queues at http://localhost:9181

## Service Ports

Ports exposed by the stack. Docker Compose services bind on the host; `uv run`
processes are listed for completeness even when they bind no port.

| Service | URL / Port | Runs in | Configurable via |
|---------|------------|---------|------------------|
| Dashboard (queue visibility) | http://localhost:8001 | `docker compose` | `DASHBOARD_PORT` / `DASHBOARD_HOST` |
| RQ Dashboard (job inspector) | http://localhost:9181 | `docker compose` | image default |
| Gateway (Telegram bot) | — (long-poll, no port) | `uv run gateway` | — |
| Task runner (RQ worker) | — (no port) | `uv run agent` | — |
| Redis (queue backing store) | `localhost:6379` | `docker compose` | `REDIS_URL` |
| Postgres (database) | `localhost:5433` → container `5432` | `docker compose` | `DATABASE_URL` |
| Household-manager backend API | `http://localhost:3001` (external) | external service | `HOUSEHOLD_MANAGER_BASE_URL` |

> **Note:** Postgres is published on host port **5433** (container `5432`) to avoid
> colliding with a local Postgres. `.env.example` ships `DATABASE_URL` pointing at
> `5432`, so adjust it to `5433` when connecting from a host process to the
> Compose database.

## Development

**Run tests**

```bash
uv run pytest
```

**Stop infrastructure**

```bash
docker compose down
```
