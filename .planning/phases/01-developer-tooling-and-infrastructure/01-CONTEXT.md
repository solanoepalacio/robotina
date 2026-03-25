# Phase 1: Developer Tooling and Infrastructure - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Set up the local development environment so every developer can run the full stack immediately: Docker Compose brings up Postgres 15 and Redis 7, the uv project is scaffolded with the correct package layout, Alembic is configured for migrations, and all dev shortcuts work (`uv run agent`, `uv run migrate`, `uv run experiments.<task_type>`). RQ Dashboard is accessible via the same `docker compose up` command. Creating models, defining task types, or implementing any agent logic is out of scope — Phase 2 onwards.

</domain>

<decisions>
## Implementation Decisions

### Package Layout
- **D-01:** Use `src/robotina/` layout — single top-level package with sub-packages matching the spec draft structure: `robotina.agent`, `robotina.queue`, `robotina.gateway`, `robotina.llm`, `robotina.scheduler`
- **D-02:** `pyproject.toml` declares one package (`robotina`) with `packages = [{include = "robotina", from = "src"}]` (or equivalent uv/hatch discovery)

### RQ Dashboard
- **D-03:** RQ Dashboard is a docker-compose service — starts automatically with `docker compose up`, no manual step required. Use the `eoranged/rq-dashboard` image, expose on port 9181, connect to the Redis container via internal network.

### Claude's Discretion
- Stub depth for `uv run agent` — should import the queue module and attempt to start an RQ worker (fails gracefully if Redis is unreachable), not a bare `print` stub
- Stub depth for `uv run experiments.<task_type>` — minimal stubs that can be invoked without error; actual agent logic added in later phases
- Redis AOF configuration method — command-line args in docker-compose (`command: redis-server --appendonly yes --appendfsync always`) vs mounted `redis.conf`; either is acceptable as long as `appendfsync always` is set
- Alembic initial migration — create an empty "init" migration to verify the toolchain works; Phase 2 adds real model migrations
- `.env.example` — include a documented template of all expected env vars; developers copy to `.env` for local runs

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project spec
- `plans/01-kickoff/spec.md` §"Draft Project Structure" — authoritative directory layout and module naming
- `plans/01-kickoff/spec.md` §"Developer Tooling Requirements" — the five tooling requirements this phase implements

### Requirements
- `.planning/REQUIREMENTS.md` §INFRA-01 through INFRA-06 — acceptance criteria for each tooling requirement

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent/skills/household-manager/` — existing skill directory that will move to `src/robotina/agent/skills/household-manager/` as part of the scaffold; no code changes needed, just relocation

### Established Patterns
- No existing Python patterns yet — this phase establishes them
- CLAUDE.md specifies SQLAlchemy 2.x `Mapped` + `mapped_column` style; pyproject.toml must include `sqlalchemy>=2.0` in runtime deps even though models are Phase 2 work

### Integration Points
- Docker Compose network: Postgres and Redis must be reachable from both the app container and from local `uv run` commands (expose ports 5432 and 6379 to host)
- uv scripts in `[project.scripts]` are the entry points for `uv run agent`, `uv run migrate`, `uv run experiments.recipe_research`, etc.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-developer-tooling-and-infrastructure*
*Context gathered: 2026-03-25*
