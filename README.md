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

**Task runner (agent worker)**

```bash
uv run agent
```

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
