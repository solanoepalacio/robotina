<!-- GSD:project-start source:PROJECT.md -->
## Project

**Robotina**

Robotina is the AI agent component of a household management system. It listens for Telegram messages from family members, interprets their intent, and executes household tasks on their behalf — answering questions about recipes and meal plans, or orchestrating multi-step workflows like researching and saving a new recipe. It connects to the household-manager backend API as its source of truth and operates as a task queue consuming a single sequential worker.

**Core Value:** Families can delegate household tasks to Robotina in natural language and trust that they get done — even complex multi-step tasks that span multiple agent runs.

### Constraints

- **Tech Stack**: Python, LangChain, Postgres (SQLAlchemy + Alembic), Redis + RQ, uv — no deviations from these in Phase 1
- **Concurrency**: Task runner must process jobs sequentially (concurrency = 1) — this is an intentional architectural constraint, not a limitation
- **LLM**: Full connection details (url, model, api_token) required per task type; API tokens read from env vars named by task type (e.g. `RECIPE_RESEARCH_API_TOKEN`)
- **Redis persistence**: AOF with `appendfsync always` — no tasks lost on crash/reboot
- **Observability**: LangWatch instrumentation must be active during both production and experiment runs so traces appear in the correct experiment collection
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12+ | Runtime | 3.12 is stable, has improved performance over 3.11, and full support for typing features used by SQLAlchemy 2.x and Pydantic v2. 3.13 released Oct 2024 but 3.12 has wider ecosystem compatibility. |
| LangChain | `langchain>=1.2`, `langchain-core>=1.2` | Agent orchestration via `langchain.agents.create_agent` | LangChain 1.x is the current major. `create_agent` (the agent factory) lives in `langchain.agents`, not `langgraph.prebuilt`. `LLMBackend.create_agent()` wraps this factory. As of Phase 11, `create_agent(response_format=Schema)` is in active use on the 5 artifact-producing agents (recipe-research-gather/instructions/ingredients/metadata + recipe-load). See `.planning/decisions/response-format-adoption.md`. |
| langchain-core | `>=1.2` | Base abstractions (`BaseChatModel`, `BaseTool`) | `langchain-core` is the stable, minimal dependency. Agent code should import from `langchain_core` wherever possible; `langchain` provides higher-level constructs. |
| langgraph | `>=1.0` | Underlying graph engine for `create_agent` | `create_agent` is built on `langgraph` (`CompiledStateGraph`, `ToolNode`, `StateGraph`). Pinned as a direct dep to document the floor; not the agent API surface anymore. |
| Redis | `7.x` | Job queue backing store, AOF persistence | Mature, stable. Version 7 adds multi-part AOF and improved persistence. AOF with `appendfsync always` satisfies the spec's no-lost-tasks requirement. |
| RQ (python-rq) | `>=2.5` | Task queue, built-in scheduler | 2.5 introduced native `enqueue_at` and cron scheduling, eliminating the `rq-scheduler` add-on. `--with-scheduler` flag activates it on the worker. Spec explicitly requires RQ 2.5+. |
| PostgreSQL | `15+` | Persistent storage for conversations, workflow state | JSON columns (`WorkflowRun.shared_context`, `WorkflowRunStep.artifact`) work well on Postgres 14+. 15/16 adds better JSON performance. |
| SQLAlchemy | `2.x` (currently `2.0.x`) | ORM for Conversation, WorkflowRun models | 2.x `Mapped` + `mapped_column` declarative style used verbatim in the spec. The old 1.x `Column` style must not be used — the spec models use 2.x syntax exclusively. |
| Alembic | `>=1.13` | Schema migrations | Standard companion to SQLAlchemy. 1.13+ supports SQLAlchemy 2.x cleanly. |
| uv | `>=0.4` | Python packaging, project management, script shortcuts | Replaces pip+virtualenv+pip-tools. `uv run` scripts satisfy the spec's shortcut requirements (`uv run agent`, `uv run migrate`, etc.). Fast, deterministic, single binary. |
### LLM Provider Adapters
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| langchain-anthropic | `>=0.3` | `ChatAnthropic` adapter | When using Claude (Anthropic) as LLM backend |
| langchain-openai | `>=0.2` | `ChatOpenAI` adapter | When using OpenAI (GPT-4, etc.) or any OpenAI-compatible endpoint |
| langchain-ollama | `>=0.2` | `ChatOllama` adapter | Local/self-hosted models via Ollama. Useful for development. |
### Observability
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| langwatch | `>=0.1` | LLM trace collection, experiment tracking | Required on all agents. Sends traces directly to LangWatch cloud; no external collector required. |
| opentelemetry-sdk | `>=1.25` | OTel SDK, trace/span primitives | LangWatch uses OTel underneath. Direct OTel spans for non-LLM instrumentation (queue events, workflow transitions). |
| opentelemetry-api | `>=1.25` | OTel API surface | Separate from SDK; agent code imports from `opentelemetry.trace` API, not SDK. |
### Telegram Gateway
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-telegram-bot | `>=21` | Telegram Bot API wrapper | V21+ is async-native, matches Python 3.12 async patterns. Used for receiving messages and sending replies. |
### Web Search Tool
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tavily-python | `>=0.3` | Tavily web search API client | Used by the `web-search` tool in the recipe-research agent. The spec names Tavily explicitly. |
### HTTP / API
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastAPI | `>=0.115` | Scheduler HTTP API | Lightweight ASGI framework for the `POST /api/scheduled-tasks` endpoints. Pydantic v2 integration is native. |
| uvicorn | `>=0.30` | ASGI server for FastAPI | Standard development and production server for FastAPI. |
| httpx | `>=0.27` | Async HTTP client | Used by `household-manager-api` tool for calling the backend API. Preferred over `requests` for async contexts. |
### Validation / Serialization
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | `v2` (`>=2.7`) | All task input/output models, ScheduledTask | Spec models are idiomatic Pydantic v2. `BaseModel` subclasses with `Literal`, `list[...]` annotations. Never mix Pydantic v1 and v2 in the same project. |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| rq-dashboard | RQ job inspection UI | `pip install rq-dashboard`. The spec requires this for developer job inspection. Run alongside the workers in development. |
| Docker Compose | Local Postgres + Redis | Spec requires it. Pin Postgres 15 and Redis 7 images in `docker-compose.yml`. |
| pytest | Test runner | Standard Python testing. `pytest-asyncio` needed if testing async gateway/agent code. |
| pytest-asyncio | Async test support | Required for testing async Telegram handler or FastAPI endpoints. |
## Installation
# Initialize project with uv
# Core runtime dependencies
# Dev dependencies
# pyproject.toml scripts (enables uv run shortcuts)
# Add to [project.scripts]:
# agent = "robotina.task_runner:main"
# migrate = "robotina.db:run_migrations"
# "experiments.recipe_research" = "experiments.recipe_research:main"
# "experiments.recipe_image" = "experiments.recipe_image:main"  # Phase 24 / EXP-03 — manual eval harness for deterministic recipe-image acquisition (Tavily image search + source-page fallback). LangWatch traces tagged experiment=recipe-image-eval, phase=24.
# "experiments.robotina_wake" = "experiments.robotina_wake:main"  # Phase 24 / EXP-04 — synthetic wake-context Robotina eval (D-08b fixture set: image_present True/False + failure + mixed batch). LangWatch traces tagged experiment=robotina-wake-eval, phase=24.
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| RQ 2.5 native scheduler | `rq-scheduler` (add-on) | Never for this project — rq-scheduler is superseded by native RQ 2.5 scheduling. Only needed for RQ < 2.5. |
| LangChain `langchain.agents.create_agent` | LangGraph `create_react_agent` | Never — `create_react_agent` is deprecated in LangGraph V1.0 (emits `LangGraphDeprecatedSinceV10`, removal in V2.0). `LLMBackend.create_agent()` must use `langchain.agents.create_agent`. `AgentExecutor` is still forbidden (long-standing). |
| SQLAlchemy 2.x `Mapped` + `mapped_column` | SQLAlchemy 1.x `Column` style | Only if stuck on Python 3.8 or very old ecosystems. This project uses 3.12 and the 2.x style is already in the spec verbatim. |
| `httpx` (async) | `requests` (sync) | `requests` if you have no async context. But the Telegram handler and FastAPI routes will be async; use `httpx` throughout. |
| `python-telegram-bot` v21 | `aiogram`, `telebot` | `aiogram` is a valid alternative with better async ergonomics; however, `python-telegram-bot` v21 is async and has larger community/docs surface. Stick with it unless migrating. |
| FastAPI | Flask, Aiohttp | Flask is sync-first and adds friction in an async codebase. FastAPI has native Pydantic v2 integration which the spec's models already use. |
| `psycopg2-binary` | `asyncpg` | `asyncpg` for purely async Postgres. Since SQLAlchemy is used with sync sessions in the task-runner context (sequential worker), `psycopg2-binary` is simpler. If you later need async DB access, use `sqlalchemy[asyncio]` + `asyncpg`. |
| Pydantic v2 | Pydantic v1 | Never — spec models use v2 syntax (`list[...]`, `Literal[...]` without quotes). |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `AgentExecutor` (langchain legacy) | Deprecated since LangChain 0.2, slated for removal. Unreliable tool-call retry semantics. | `langgraph.prebuilt.create_react_agent` |
| `langgraph.prebuilt.create_react_agent` | Deprecated in LangGraph V1.0, removal in V2.0. Emits `LangGraphDeprecatedSinceV10` at call time. | `langchain.agents.create_agent` |
| `rq-scheduler` (PyPI package) | Superseded by native RQ 2.5 scheduler. Two schedulers in one project creates confusion and race conditions. | `rq>=2.5` native `enqueue_at` / cron |
| Celery | Overkill for single-worker, sequential task queue. Adds broker config complexity (beat scheduler, separate broker/backend). | RQ — simpler, Redis-only, sufficient for this use case. |
| `requests` library in async handlers | Blocks the event loop. | `httpx` with `async with httpx.AsyncClient()` |
| LangChain callbacks for observability | Deprecated path; fragile, hard to correlate with OTel spans. | LangWatch + OTel native instrumentation |
| Pydantic v1 | LangChain 0.3 and SQLAlchemy 2.x both require or strongly prefer v2. Mixing versions causes silent serialization bugs. | Pydantic v2 exclusively |
| `aioredis` (standalone) | Merged into `redis-py` since `redis>=4.2`. Using both creates version conflicts. | `redis>=5.0` (includes async support) |
| `dotenv` loaded manually per module | Inconsistent env loading order. | Single `load_dotenv()` at entrypoint, or rely on Docker Compose environment injection. |
| Custom output parser that scans for prose, fences, JSON | This is exactly the canelones-class bug. LangChain's structured-output path (`response_format=`) is token-level (provider) or tool-arg-validated (Ollama). See `.planning/decisions/response-format-adoption.md`. | `response_format=<Pydantic class>` on `langchain.agents.create_agent` (Phase 11) |
## Stack Patterns by Variant
- Use `docker-compose up` for Postgres 15 + Redis 7
- Use `uv run agent` / `uv run scheduler` shortcuts
- Use Ollama adapter (`langchain-ollama`) to avoid API costs during development
- Set `LANGWATCH_ENDPOINT` to a dev project to keep experiment traces separate
- Switch Redis AOF config to `appendfsync always` (not `everysec`) — spec requirement
- Set `result_ttl=-1` and `failure_ttl=-1` on all RQ jobs — spec requirement
- Run two workers as separate processes: `scheduler-worker` (with `--with-scheduler`) and `task-runner` (concurrency=1, without `--with-scheduler`)
- Use `psycopg2-binary` in dev; switch to `psycopg2` (compiled) in production for performance
- Add a new adapter class implementing `LLMBackend` Protocol
- Only need to implement `.model` property and `.create_agent()` method
- Register in `agents.py` — no changes elsewhere
- Experiment scripts import the same `LLMBackend` + agent setup used in production
- Set `LANGWATCH_ENDPOINT` / `LANGWATCH_API_KEY` to the desired LangWatch project
- Pin prompt version and model config in experiment metadata tags
- Do NOT use a separate observability pipeline for experiments — same instrumentation as production is the requirement
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `langchain>=0.3` | `langchain-core>=0.3`, `pydantic>=2.0` | LangChain 0.3 dropped Pydantic v1 support entirely. |
| `langgraph>=0.2` | `langchain-core>=0.3` | LangGraph depends on `langchain-core`, not full `langchain`. |
| `sqlalchemy>=2.0` | `alembic>=1.13`, `psycopg2>=2.9` | Alembic 1.13 added full SQLAlchemy 2.x support. |
| `rq>=2.5` | `redis>=4.0` | RQ 2.5 native scheduler requires Redis server 6+. |
| `python-telegram-bot>=21` | `httpx` (internal), Python 3.8+ | V21 is async-native; do not mix with `v13.x` sync patterns. |
| `opentelemetry-sdk>=1.25` | `langwatch>=0.1` | LangWatch's OTel integration targets the stable OTel SDK API surface (not alpha). |
| `pydantic>=2.7` | `fastapi>=0.115`, `langchain>=0.3` | FastAPI 0.115 dropped Pydantic v1 support. |
## Confidence Notes
| Area | Confidence | Notes |
|------|------------|-------|
| LangChain package split (core / langgraph / agents) | HIGH | `langchain.agents.create_agent` is the current factory as of LangChain 1.x (verified empirically against installed `langchain 1.2.13`, 2026-05-12). `create_react_agent` is deprecated in `langgraph.prebuilt`. |
| RQ 2.5 native scheduler | HIGH | Spec explicitly states "RQ 2.5+" and describes `enqueue_at` + cron. This is accurate per RQ changelog. |
| SQLAlchemy 2.x `Mapped` syntax | HIGH | Code in spec uses it verbatim; syntax is stable since SQLAlchemy 2.0 (Jan 2023). |
| Exact package versions (numbers) | LOW-MEDIUM | No network access to verify PyPI. Versions stated are conservative lower bounds from training data (Aug 2025 cutoff). Run `uv add <package>` to resolve to actual latest at install time. |
| LangWatch SDK API | LOW | LangWatch is a newer product. SDK surface may have evolved. Verify against official LangWatch docs before implementation. |
| python-telegram-bot v21 async API | MEDIUM | V20/V21 async rewrite is well-documented, but Telegram Bot API changes frequently. Verify handler patterns at implementation time. |
## Sources
- Spec file: `/plans/01-kickoff/spec.md` — authoritative for all technology choices; versions explicitly referenced: Python, RQ 2.5+, SQLAlchemy 2.x, Alembic, LangChain, LangWatch, OTel
- LangChain 1.x agent API: `create_agent` lives in `langchain.agents` as of LangChain 1.x; `langgraph.prebuilt.create_react_agent` is the prior-generation API that this project migrated away from in Phase 10.
- RQ changelog (training data): native scheduler added in RQ 2.0, matured in 2.5
- SQLAlchemy 2.0 release notes (training data): `Mapped` / `mapped_column` declarative API introduced Jan 2023
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
