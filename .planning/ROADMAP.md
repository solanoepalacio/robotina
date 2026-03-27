# Roadmap: Robotina

## Overview

Robotina is built in nine phases following a strict dependency order: infrastructure and data contracts first, then gateway, then the LLM module and agent infrastructure, then the workflow engine, and finally agents in order of increasing complexity (send-notification → handle-incoming-message → recipe-research → recipe-load). Each phase delivers a complete, verifiable capability that unblocks the next. Nothing in Phase 9 is testable until every prior phase is solid — the architecture enforces this linearity.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Developer Tooling and Infrastructure** - Docker Compose, uv project, Alembic, and dev shortcuts are fully operational (completed 2026-03-25)
- [x] **Phase 2: Database Models and Queue Layer** - All SQLAlchemy models, Alembic migrations, Pydantic task I/O models, and RQ basics in place (completed 2026-03-25)
- [x] **Phase 3: Gateway** - Telegram bot receives, deduplicates, persists messages, and enqueues tasks (completed 2026-03-25)
- [x] **Phase 4: LLM Module and Agent Infrastructure** - LLMBackend abstraction, adapters, agent runner, skill loading, prompt versioning, and LangWatch instrumentation (completed 2026-03-26)
- [x] **Phase 5: Task Runner and Workflow Engine** - Sequential RQ worker with workflow state transitions, artifact persistence, and next-step advancement (completed 2026-03-26)
- [ ] **Phase 6: send-notification Agent** - Notification agent formats and delivers Telegram messages with LangWatch traces verified
- [ ] **Phase 7: handle-incoming-message Agent** - Robotina routing agent handles direct replies and initiates multi-step workflows end-to-end
- [ ] **Phase 8: recipe-research Agent** - Recipe research agent performs structured web search and produces typed RecipeData output
- [ ] **Phase 9: recipe-load Agent and End-to-End Integration** - Recipe loader resolves food/unit names and creates recipes; full add-recipe workflow works end-to-end

## Phase Details

### Phase 1: Developer Tooling and Infrastructure
**Goal**: Developer has a working local environment — Postgres and Redis are running, the uv project is scaffolded, migrations run cleanly, and all dev shortcuts work
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06
**Success Criteria** (what must be TRUE):
  1. `docker compose up` starts Postgres 15 and Redis 7 with no errors and Redis has AOF persistence enabled (`appendfsync always`)
  2. `uv run migrate` runs Alembic migrations to completion with no errors
  3. `uv run agent` starts the task runner process without crashing
  4. `uv run experiments.<task_type>` entry points are registered (scripts can be invoked even if they are stubs)
  5. RQ Dashboard is accessible at its configured URL when the stack is running
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Docker Compose stack (Postgres 15, Redis 7 AOF, RQ Dashboard)
- [x] 01-02-PLAN.md — uv project scaffold, src/robotina package tree, Alembic configuration
- [x] 01-03-PLAN.md — uv run agent entrypoint, experiment stubs, automated test scaffold

### Phase 2: Database Models and Queue Layer
**Goal**: All shared data contracts exist — SQLAlchemy models are migrated to Postgres, all Pydantic task I/O models are defined, and RQ serialization is verified for every task type before any agent is written
**Depends on**: Phase 1
**Requirements**: QUEUE-01, QUEUE-02, QUEUE-03, QUEUE-04, QUEUE-05, QUEUE-06, QUEUE-07, WF-01
**Success Criteria** (what must be TRUE):
  1. `Conversation`, `StoredMessage`, `WorkflowRun`, and `WorkflowRunStep` SQLAlchemy models exist and their Alembic migration applies cleanly to a fresh database
  2. All four Pydantic task input/output models (`IncomingMessageInput/Output`, `RecipeResearchInput/Output`, `RecipeLoadInput/Output`, `SendNotificationInput/Output`) are defined with Pydantic v2 and round-trip through pickle serialization without error
  3. RQ worker starts with `concurrency=1` and processes a test job sequentially
  4. Jobs with `result_ttl=-1` and `failure_ttl=-1` are retained in the job registry after completion and failure; failed jobs appear in the built-in failed job registry
  5. Queue state changes (queued, started, finished, failed) are logged to console
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — SQLAlchemy models (Conversation, StoredMessage, WorkflowRun, WorkflowRunStep), db.py Base, Alembic migration 0002
- [x] 02-02-PLAN.md — Pydantic v2 task I/O models (all 8 Input/Output classes) in task_types.py
- [x] 02-03-PLAN.md — LoggingWorker refactor, pyproject.toml markers, RQ integration tests

### Phase 3: Gateway
**Goal**: The Telegram bot is the live front door — it receives user messages, persists them with deduplication, fetches conversation history, and enqueues tasks at the front of the queue
**Depends on**: Phase 2
**Requirements**: GW-01, GW-02, GW-03, GW-04, GW-05, GW-06
**Success Criteria** (what must be TRUE):
  1. Sending a Telegram message to the bot results in a `StoredMessage` row in Postgres and a `handle-incoming-message` job at the front of the RQ queue
  2. Resending the same Telegram message (same `platform_message_id`) does not create a duplicate `StoredMessage` row or enqueue a second job
  3. The bot returns HTTP 200 to Telegram on all outcomes, including internal errors
  4. Conversation history up to the configured N messages is attached to the enqueued task input
  5. A `Conversation` record groups all messages for a `(platform, chat_id)` pair and enforces the `@@unique` constraint
**Plans**: 3 plans
**UI hint**: yes

Plans:
- [x] 03-01-PLAN.md — Test scaffold: conftest.py gateway fixtures + test_gateway.py stubs (GW-01 through GW-06)
- [x] 03-02-PLAN.md — Incoming handler (handler.py, gateway __init__.py), uv run all subprocess launcher, pyproject.toml entries
- [x] 03-03-PLAN.md — Outgoing send_message() function (send.py)

### Phase 4: LLM Module and Agent Infrastructure
**Goal**: A general-purpose agent execution foundation exists — LLMBackend abstraction, three provider adapters, agent runner with correct per-job object scoping, skill loading, prompt versioning, runtime overrides, and LangWatch instrumentation initialized
**Depends on**: Phase 3
**Requirements**: AGENT-01, AGENT-02, AGENT-03, AGENT-04, AGENT-05, AGENT-06, AGENT-07, AGENT-08, AGENT-09, AGENT-10, AGENT-11, OBS-01, OBS-02
**Success Criteria** (what must be TRUE):
  1. `LLMBackend` Protocol is defined; Ollama, Anthropic, and OpenAI adapters each create a working `create_react_agent` instance when given valid connection details
  2. `agents.py` registry drives per-task-type configuration (model, prompt path, tools, skills) and reads API tokens from env vars named by task type
  3. A skill directory under `src/robotina/agent/skills/` with an `index.md` is pre-loaded into agent context; a sub-file is loaded on demand via `read-skill` tool; path traversal outside the configured skill directory is blocked
  4. System prompts are loaded from versioned markdown files; switching the active version via `AGENT_OVERRIDES_FILEPATH` at runtime (without redeploy) selects the new prompt on the next job
  5. LangWatch + OTel instrumentation initializes at process startup, reads endpoint and API key from env vars, and produces a trace for a test agent invocation
**Plans**: 6 plans

Plans:
- [x] 04-01-PLAN.md — Wave 0: unit test scaffolds (6 test files) + gateway enqueue string fix (run_task)
- [x] 04-02-PLAN.md — LLMBackend Protocol + OllamaBackend, AnthropicBackend, OpenAIBackend adapters
- [x] 04-03-PLAN.md — agents.py registry: AgentConfig dataclass, AGENT_REGISTRY, get_agent_config(), configure_logging()
- [x] 04-04-PLAN.md — run_task() universal job function + AgentLoggingHandler + runner.py LangWatch init
- [x] 04-05-PLAN.md — SkillSet + ReadSkillTool + household-manager skill relocation to canonical path
- [x] 04-06-PLAN.md — hello-world prompt file + full unit suite verification + manual end-to-end checkpoint

### Phase 5: Task Runner and Workflow Engine
**Goal**: The sequential task runner correctly orchestrates workflow state — marking steps running, persisting artifacts, advancing to the next step, and propagating failures — before any real agent runs through it
**Depends on**: Phase 4
**Requirements**: QUEUE-01, WF-02, WF-03, WF-04, WF-05, WF-06, WF-07, WF-08, WF-09
**Success Criteria** (what must be TRUE):
  1. `workflows.py` defines the `add-recipe` workflow with three steps (`research` → `load` → `notify`) in the `WorkflowDefinition` registry; each `WorkflowStepDef` has a `build_input` callable that never receives a mutable `shared_context`
  2. `start-workflow` tool creates a `WorkflowRun` and all `WorkflowRunStep` records with `PENDING` status, enqueues the first step, and returns a `workflow_run_id`
  3. When a step job starts, its `WorkflowRunStep` transitions to `RUNNING`; on completion, its output is written to `artifact`, accumulated artifacts are built, and the next `PENDING` step is enqueued
  4. When the final step completes, the `WorkflowRun` is marked `DONE`
  5. When a step fails, the failed step is marked `FAILED`, all remaining `PENDING` steps are cancelled, and the `WorkflowRun` is marked `FAILED`; `reply_context` is never present in `RecipeResearchInput` or `RecipeLoadInput`
**Plans**: 4 plans

Plans:
- [x] 05-01-PLAN.md — Wave 0: test scaffolds (test_workflows.py, test_workflow_runner.py, test_start_workflow_tool.py)
- [x] 05-02-PLAN.md — workflows.py: WorkflowStepDef, WorkflowDefinition, WORKFLOW_REGISTRY (add-recipe + hello-world-2step)
- [x] 05-03-PLAN.md — queue/workflow_runner.py: start_workflow, on_step_start, on_step_complete, on_step_failed
- [x] 05-04-PLAN.md — run_task() workflow hooks + agent/tools/start_workflow.py + integration tests + human checkpoint

### Phase 6: send-notification Agent
**Goal**: The notification agent correctly formats and delivers Telegram messages using the `format-telegram-message` skill, with LangWatch traces verified via a standalone experiment script
**Depends on**: Phase 5
**Requirements**: NOTIF-01, NOTIF-02, NOTIF-03, NOTIF-04, NOTIF-05, OBS-03, OBS-05
**Success Criteria** (what must be TRUE):
  1. A `send-notification` job placed in the queue results in a correctly formatted Telegram MarkdownV2 message delivered to the target chat
  2. The `format-telegram-message` skill `index.md` and sub-files exist and are loaded by the agent; the agent applies the skill to reformat pre-written text without composing new content
  3. The `send-notification` tool sends the formatted message via the gateway and persists the outgoing message to Postgres
  4. Running `experiments/send_notification.py` completes without error and a trace appears in the correct LangWatch experiment collection
**Plans**: 4 plans

Plans:
- [ ] 06-01-PLAN.md — Wave 0+registry: test stubs (test_send_notification_tool.py) + remove hello-world from AGENT_REGISTRY and WORKFLOW_REGISTRY + update existing tests
- [ ] 06-02-PLAN.md — SendNotificationTool implementation + send_message() parse_mode fix + run_task() injection
- [ ] 06-03-PLAN.md — format-telegram-message skill (4 files) + send-notification/V001.md prompt
- [ ] 06-04-PLAN.md — experiments/send_notification.py full implementation + human LangWatch verification checkpoint

### Phase 7: handle-incoming-message Agent
**Goal**: The Robotina routing agent correctly handles natural-language messages — either enqueuing a direct `send-notification` reply or initiating a multi-step workflow — closing the direct-reply user story end-to-end
**Depends on**: Phase 6
**Requirements**: ROBOT-01, ROBOT-02, ROBOT-03, ROBOT-04, ROBOT-05, ROBOT-06, ROBOT-07
**Success Criteria** (what must be TRUE):
  1. A Telegram message asking a household question (e.g., "what's on the meal plan?") results in an answer delivered back to the user via the `queue` tool → `send-notification` agent path
  2. A Telegram message requesting a multi-step task (e.g., "add a recipe for X") results in a `WorkflowRun` being created via the `start-workflow` tool with the correct initial step enqueued
  3. The `household-manager-api` tool is used to read household data; a `401` or `403` response raises a hard error that stops the agent loop rather than being retried as a recoverable error
  4. The `household-manager` skill no longer contains auth instructions (auth is injected by the tool, not the agent)
**Plans**: TBD

### Phase 8: recipe-research Agent
**Goal**: The recipe research agent performs structured multi-site web search via Tavily and produces a fully populated `RecipeData` output, with traces pinned to LangWatch experiment collections
**Depends on**: Phase 7
**Requirements**: RRECIPE-01, RRECIPE-02, RRECIPE-03, RRECIPE-04, RRECIPE-05, RRECIPE-06, OBS-04
**Success Criteria** (what must be TRUE):
  1. A `recipe-research` job with a recipe name input results in a `RecipeData` output with all fields populated: name, description, servings, times, ingredients with human-readable food and unit names, steps, and source URL
  2. The `web-search` tool calls the Tavily API with a bounded `max_results` and returns structured results; the agent uses multiple search queries across different recipe sites
  3. The `recipe-research` skill instructions and `recipe-research/V001.md` prompt exist and are loaded by the agent
  4. Running `experiments/recipe_research.py` completes without error, a trace appears in the correct LangWatch experiment collection, and the experiment script pins prompt version and model config via LangWatch tags
**Plans**: TBD

### Phase 9: recipe-load Agent and End-to-End Integration
**Goal**: The recipe loader agent resolves human-readable ingredient names to household-manager IDs and creates the recipe; the full add-recipe workflow runs end-to-end from a Telegram message to a delivered recipe confirmation
**Depends on**: Phase 8
**Requirements**: RLOAD-01, RLOAD-02, RLOAD-03, RLOAD-04, RLOAD-05, RLOAD-06
**Success Criteria** (what must be TRUE):
  1. A `recipe-load` job with a `RecipeData` input resolves all ingredient food names and unit names to `foodId` and `unitId` via `GET /api/foods?name=` and `GET /api/units?name=`, then creates the recipe via `POST /api/recipes`, returning `recipe_id` and `recipe_name`
  2. The agent handles partial and zero name matches gracefully (does not crash; surfaces the issue to the workflow)
  3. Running `experiments/recipe_load.py` completes without error, a trace appears in the correct LangWatch experiment collection, and the experiment script pins prompt version and model config
  4. Sending "add a recipe for carbonara" to the Telegram bot results in a `WorkflowRun` progressing through all three steps (`research` → `load` → `notify`) and a formatted recipe confirmation message delivered back to the user

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Developer Tooling and Infrastructure | 3/3 | Complete    | 2026-03-25 |
| 2. Database Models and Queue Layer | 3/3 | Complete   | 2026-03-25 |
| 3. Gateway | 3/3 | Complete   | 2026-03-25 |
| 4. LLM Module and Agent Infrastructure | 6/6 | Complete   | 2026-03-26 |
| 5. Task Runner and Workflow Engine | 5/5 | Complete   | 2026-03-27 |
| 6. send-notification Agent | 0/4 | Not started | - |
| 7. handle-incoming-message Agent | 0/TBD | Not started | - |
| 8. recipe-research Agent | 0/TBD | Not started | - |
| 9. recipe-load Agent and End-to-End Integration | 0/TBD | Not started | - |
