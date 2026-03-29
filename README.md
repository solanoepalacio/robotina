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

## Development

**Run tests**

```bash
uv run pytest
```

**Stop infrastructure**

```bash
docker compose down
```
