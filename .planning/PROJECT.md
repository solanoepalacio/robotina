# Robotina

## What This Is

Robotina is the AI agent component of a household management system. It listens for Telegram messages from family members, interprets their intent, and executes household tasks on their behalf — answering questions about recipes and meal plans, or orchestrating multi-step workflows like researching and saving a new recipe. It connects to the household-manager backend API as its source of truth and operates as a task queue consuming a single sequential worker.

## Core Value

Families can delegate household tasks to Robotina in natural language and trust that they get done — even complex multi-step tasks that span multiple agent runs.

## Current Milestone: v1.1 Workflows Abstraction Refinement

**Goal:** Polish the recipe-adding capability into something genuinely useful by closing three product gaps (multi-recipe per message, URL-pointed recipes, recipe images) and the architectural cleanup that closing them cleanly requires (Robotina-as-decider outside the work graph; new RobotinaInvocation entity; Conversation↔WorkflowRun FK closure; remove `acknowledge-add-recipe` workaround and `StartWorkflowTool.return_direct=True`).

**Target features:**
- Multi-recipe in one message (fan-out to N workflows; one consolidated final reply)
- URL-pointed recipe ingestion (new `gather-from-url` first step; rest of pipeline reused)
- Recipe images saved alongside each recipe (non-fatal failure)
- Architectural refactor: Robotina-as-decider, `RobotinaInvocation` entity, wake-when-all-workflows-done rule, immutable workflows once created

**Reference:** `plans/02-workflow-refinement/description.md` — full architectural direction and out-of-scope items.

## Requirements

### Validated

- ✓ household-manager skill (index + sub-files) — existing
- ✓ Developer tooling: Docker Compose (Postgres + Redis), uv project setup, uv run shortcuts — v1.0 (Phase 1)
- ✓ Queue: Redis + RQ task queue with sequential worker (concurrency = 1), all task input/output Pydantic models — v1.0 (Phase 2)
- ✓ Workflow infrastructure: `WorkflowRun` / `WorkflowRunStep` Postgres models — v1.0 (Phase 2)
- ✓ Gateway: Telegram bot receives messages, persists conversations, enqueues `handle-incoming-message` tasks — v1.0 (Phase 3)
- ✓ Agent infrastructure: LLM module + adapters (Ollama, Anthropic, OpenAI), `agents.py` scaffold, skill loading, prompt versioning, LangWatch + OTel instrumentation — v1.0 (Phase 4)
- ✓ Workflow registry + task-runner advancement hook + `start-workflow` tool — v1.0 (Phase 5)
- ✓ Notification agent (`send-notification`): format-telegram-message skill, prompt, tool — v1.0 (Phase 6; retired as LLM agent in Phase 07.1, now deterministic Python path)
- ✓ Robotina agent (`handle-incoming-message`): household-manager skill, prompt, tools (household-manager-api, queue, start-workflow) — v1.0 (Phase 7)
- ✓ Deterministic agent termination via `return_direct=True` on terminal tools — v1.0 (Phase 07.1)
- ✓ Recipe Research agent (`recipe-research`): 4-step pipeline (gather/instructions/ingredients/metadata), Tavily web-search, Spanish prompts — v1.0 (Phase 8)
- ✓ Recipe Loader agent (`recipe-load`): household-manager-api tool, name resolution, end-to-end add-recipe Telegram → backend recipe — v1.0 (Phase 9)
- ✓ LangChain 1.x agent API migration: `create_react_agent` → `langchain.agents.create_agent` across 3 LLMBackend adapters — v1.0 (Phase 10)
- ✓ Structured agent output via `response_format=PydanticModel` on 5 named agents; canelones-class parse failures structurally eliminated — v1.0 (Phase 11)
- ✓ Middleware-based agent instrumentation (`@before_model`/`@after_model`/`@wrap_model_call`); legacy callbacks removed — v1.0 (Phase 12)
- ✓ Queue visibility dashboard: independent FastAPI + Jinja2 + HTMX module with persisted `step_input` and `failure_reason` — v1.0 (Phase 13)
- ✓ Prompt cleanup: single Role/Inputs/Tools/Process/Rules/Output skeleton across 7 active prompts — v1.0 (Phase 14)
- ✓ Recipe artifact accumulation: single growing `RecipeData` through pipeline + food/unit semantic validation via `validate-foods` / `validate-units` tools — v1.0 (Phase 15)
- ✓ 4-layer `household_id` validation: gateway fail-fast + Pydantic `NonEmptyHouseholdId` + tool-constructor guards + `queue_workflow` pre-DB check — v1.0 (Phase 16)

### Active

<!-- Milestone v1.1 in progress — requirements minted during /gsd:new-milestone, see REQUIREMENTS.md -->

- [ ] Scheduler: scheduled-tasks queue + worker, RQ cron/enqueue_at, scheduler tool, Scheduler HTTP API (deferred — moved to a later milestone after v1.1)

### Out of Scope

- Multi-household support — single household_id from env var for now; `household_id` field exists in models to be future-proof
- Per-household API keys — single shared API key for Phase 1
- Mobile or web client — Telegram only for Phase 1
- Automatic workflow retry / compensation — failed workflows land in RQ's failed registry for manual inspection only
- Prompt quality tuning — prompts are scaffolded in Phase 1; experimentation infrastructure enables iteration post-Phase 1

## Context

- Robotina is one of three components: client app, household-manager backend (source of truth), and Robotina. This repo covers only Robotina.
- The household-manager skill (`agent/skills/household-manager/`) is already implemented and covers recipes CRUD, meal plan, and shared API conventions. Minor update needed: remove auth instructions (auth is handled by the `household-manager-api` tool, not the agent).
- Agents are implemented with LangChain using a `LLMBackend` Protocol abstraction, making it easy to swap providers per task type. As of v1.0 all agents run on `langchain.agents.create_agent` (LangChain 1.x); 5 named agents bind `response_format=PydanticModel` for schema-constrained output.
- Skills are markdown directories with an `index.md` and sub-files. Index content is pre-loaded into agent context; sub-files are loaded on demand via `read-skill` tool.
- Prompts are markdown files, versioned (V001.md, V002.md...), and can be swapped at runtime via `AGENT_OVERRIDES_FILEPATH` without a redeploy. As of v1.0 all 7 active prompts share a common Role/Inputs/Tools/Process/Rules/Output skeleton (Phase 14).
- LangWatch + OpenTelemetry instrumentation is required on all agents — wired via `create_agent` middleware as of Phase 12. Each task type (except `handle-incoming-message`) has a standalone experiment script in `experiments/`.
- v1.0 codebase: 3,990 LOC `src/` Python (32 files), 5,742 LOC tests (38 files), 135 unit tests green at milestone close.

## Constraints

- **Tech Stack**: Python, LangChain, Postgres (SQLAlchemy + Alembic), Redis + RQ, uv — no deviations from these in Phase 1
- **Concurrency**: Task runner must process jobs sequentially (concurrency = 1) — this is an intentional architectural constraint, not a limitation
- **LLM**: Full connection details (url, model, api_token) required per task type; API tokens read from env vars named by task type (e.g. `RECIPE_RESEARCH_API_TOKEN`)
- **Redis persistence**: AOF with `appendfsync always` — no tasks lost on crash/reboot
- **Observability**: LangWatch instrumentation must be active during both production and experiment runs so traces appear in the correct experiment collection

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Centralized task-runner orchestrates workflows (not agents chaining themselves) | Separates concerns — agents know only their task, not the sequence they belong to | ✓ Good — validated through Phases 5–16; agents stayed sequence-agnostic and the workflow registry remained the single source of truth |
| `reply_context` lives in `WorkflowRun.shared_context`, never in intermediate task inputs | Prevents coupling intermediate agents to UI concerns | ✓ Good — held across all 7 add-recipe steps; revisit alongside Phase 999.1 (custom `AgentState` schemas) if promoted |
| `RecipeData` uses human-readable food/unit names (not IDs) | Recipe-research agent has no access to household-manager IDs; recipe-load resolves them | ✓ Good — Phase 15 doubled down on this by moving food/unit semantic-match into the ingredients step (still name-based); recipe-load remains the single resolution point |
| Two separate RQ workers: scheduler-worker (`--with-scheduler`) and task-runner | Keeps scheduling concerns decoupled from agent execution | — Pending — scheduler track deferred to next milestone; task-runner alone shipped v1.0 |
| Skills use lazy loading (index pre-loaded, sub-files on demand) | Avoids context bloat for tasks that only need part of a skill | ✓ Good — `SkillSet`/`ReadSkillTool` pattern stable since Phase 4 |
| `create_agent` from `langchain.agents` is used for all agents | LangGraph deprecated `create_react_agent` (V1.0; removal in V2.0). The new factory is required to unlock `response_format` (Phase 11) and middleware (Phase 12). Behavior parity verified empirically during Phase 10. | — Active |
| `household_id` is required and validated end-to-end (Phase 16) | A missing `HOUSEHOLD_ID` env var silently propagated as `""` through Conversation, IncomingMessageInput, WorkflowRun, and the household-manager-api tool, surfacing only as confusing 4xx responses from the backend. Phase 16 added defensive validation at four layers: gateway entrypoint (`sys.exit(1)` on missing/empty/whitespace), Pydantic task-input models (`NonEmptyHouseholdId` alias on 7 models), tool constructors (`HouseholdManagerApiTool`, `StartWorkflowTool` reject empty), and `queue_workflow` (raises ValueError before any DB write). | — Active |

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
*Last updated: 2026-05-18 after starting milestone v1.1 — workflows abstraction refinement (multi-recipe, URL ingestion, images + Robotina-as-decider refactor)*
