# Robotina

## What This Is

Robotina is the AI agent component of a household management system. It listens for Telegram messages from family members, interprets their intent, and executes household tasks on their behalf — answering questions about recipes and meal plans, or orchestrating multi-step workflows like researching and saving a new recipe. It connects to the household-manager backend API as its source of truth and operates as a task queue consuming a single sequential worker.

## Core Value

Families can delegate household tasks to Robotina in natural language and trust that they get done — even complex multi-step tasks that span multiple agent runs.

## Requirements

### Validated

- ✓ household-manager skill (index + sub-files) — existing

### Active

- [x] Gateway: Telegram bot receives messages, persists conversations, enqueues `handle-incoming-message` tasks — Validated in Phase 3: gateway
- [x] Queue: Redis + RQ task queue with sequential worker (concurrency = 1), all task input/output Pydantic models — Validated in Phase 2: Database Models and Queue Layer
- [x] Workflow infrastructure: `WorkflowRun` / `WorkflowRunStep` Postgres models — Validated in Phase 2: Database Models and Queue Layer (registry + task-runner hook pending Phase 5)
- [x] Workflow registry + task-runner advancement hook + `start-workflow` tool — Validated in Phase 5: task-runner-and-workflow-engine
- [x] Agent infrastructure: LLM module + adapters (Ollama, Anthropic, OpenAI), `agents.py` scaffold, skill loading, prompt versioning, LangWatch + OTel instrumentation — Validated in Phase 4: llm-module-and-agent-infrastructure
- [x] Notification agent (`send-notification`): format-telegram-message skill, prompt, tool, experiment — Validated in Phase 6: send-notification-agent
- [x] Robotina agent (`handle-incoming-message`): household-manager skill (auth update), prompt, tools (household-manager-api, queue, start-workflow) — Validated in Phase 7: handle-incoming-message-agent
- [x] Recipe Research agent (`recipe-research`): skill, prompt, web-search tool, experiment — Validated in Phase 8: recipe-research-agent
- [x] Recipe Loader agent (`recipe-load`): skill reuse (household-manager), prompt, household-manager-api tool, experiment — Validated in Phase 9: recipe-load-agent-and-end-to-end-integration
- [ ] Scheduler: scheduled-tasks queue + worker, RQ cron/enqueue_at, scheduler tool, Scheduler HTTP API
- [x] Developer tooling: Docker Compose (Postgres + Redis), uv project setup, uv run shortcuts — Validated in Phase 1: Developer Tooling and Infrastructure

### Out of Scope

- Multi-household support — single household_id from env var for now; `household_id` field exists in models to be future-proof
- Per-household API keys — single shared API key for Phase 1
- Mobile or web client — Telegram only for Phase 1
- Automatic workflow retry / compensation — failed workflows land in RQ's failed registry for manual inspection only
- Prompt quality tuning — prompts are scaffolded in Phase 1; experimentation infrastructure enables iteration post-Phase 1

## Context

- Robotina is one of three components: client app, household-manager backend (source of truth), and Robotina. This repo covers only Robotina.
- The household-manager skill (`agent/skills/household-manager/`) is already implemented and covers recipes CRUD, meal plan, and shared API conventions. Minor update needed: remove auth instructions (auth is handled by the `household-manager-api` tool, not the agent).
- Agents are implemented with LangChain using a `LLMBackend` Protocol abstraction, making it easy to swap providers per task type.
- Skills are markdown directories with an `index.md` and sub-files. Index content is pre-loaded into agent context; sub-files are loaded on demand via `read-skill` tool.
- Prompts are markdown files, versioned (V001.md, V002.md...), and can be swapped at runtime via `AGENT_OVERRIDES_FILEPATH` without a redeploy.
- LangWatch + OpenTelemetry instrumentation is required on all agents. Each task type (except `handle-incoming-message`) needs a standalone experiment script.

## Constraints

- **Tech Stack**: Python, LangChain, Postgres (SQLAlchemy + Alembic), Redis + RQ, uv — no deviations from these in Phase 1
- **Concurrency**: Task runner must process jobs sequentially (concurrency = 1) — this is an intentional architectural constraint, not a limitation
- **LLM**: Full connection details (url, model, api_token) required per task type; API tokens read from env vars named by task type (e.g. `RECIPE_RESEARCH_API_TOKEN`)
- **Redis persistence**: AOF with `appendfsync always` — no tasks lost on crash/reboot
- **Observability**: LangWatch instrumentation must be active during both production and experiment runs so traces appear in the correct experiment collection

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Centralized task-runner orchestrates workflows (not agents chaining themselves) | Separates concerns — agents know only their task, not the sequence they belong to | — Pending |
| `reply_context` lives in `WorkflowRun.shared_context`, never in intermediate task inputs | Prevents coupling intermediate agents to UI concerns | — Pending |
| `RecipeData` uses human-readable food/unit names (not IDs) | Recipe-research agent has no access to household-manager IDs; recipe-load resolves them | — Pending |
| Two separate RQ workers: scheduler-worker (`--with-scheduler`) and task-runner | Keeps scheduling concerns decoupled from agent execution | — Pending |
| Skills use lazy loading (index pre-loaded, sub-files on demand) | Avoids context bloat for tasks that only need part of a skill | — Pending |
| `create_agent` from `langchain.agents` is used for all agents | LangGraph deprecated `create_react_agent` (V1.0; removal in V2.0). The new factory is required to unlock `response_format` (Phase 11) and middleware (Phase 12). Behavior parity verified empirically during Phase 10. | — Active |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-31 after Phase 9 completion (recipe-load-agent-and-end-to-end-integration) — all v1.0 milestone phases complete*
