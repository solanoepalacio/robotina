# Phase 1: Developer Tooling and Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-25
**Phase:** 01-developer-tooling-and-infrastructure
**Areas discussed:** Package layout, RQ Dashboard access

---

## Package Layout

| Option | Description | Selected |
|--------|-------------|----------|
| src/robotina/ layout | Single top-level package: robotina.agent, robotina.queue, robotina.gateway. Standard Python convention — one importable package in pyproject.toml. | ✓ |
| src/ flat layout | Each module is its own top-level package: from agent import ..., from queue import .... Matches spec draft literally — multiple packages registered in pyproject.toml. | |

**User's choice:** `src/robotina/` layout
**Notes:** Preferred over the flat layout for standard Python convention compliance.

---

## RQ Dashboard Access

| Option | Description | Selected |
|--------|-------------|----------|
| uv run shortcut | Add rq-dashboard as a dev dependency and expose as `uv run rq-dashboard`. Developer runs manually alongside the stack. | |
| docker-compose service | Add rq-dashboard as a container in docker-compose.yml. Starts automatically with `docker compose up`. | ✓ |
| Manual / README only | Document `pip install rq-dashboard && rq-dashboard` in README. No tooling integration. | |

**User's choice:** docker-compose service
**Notes:** Zero manual steps — starts alongside Postgres and Redis.

---

## Claude's Discretion

- Stub depth for `uv run agent` and experiments — left to Claude
- Redis AOF configuration method (command-line args vs redis.conf) — left to Claude
- Alembic initial migration scope — left to Claude
- `.env.example` template — left to Claude

## Deferred Ideas

None raised during discussion.
