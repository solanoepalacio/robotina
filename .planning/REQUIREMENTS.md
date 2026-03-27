# Requirements: Robotina

**Defined:** 2026-03-25
**Core Value:** Families can delegate household tasks to Robotina in natural language and trust that they get done — even complex multi-step tasks that span multiple agent runs.

## v1 Requirements

Requirements for the initial milestone. All map to roadmap phases.

### Infrastructure

- [x] **INFRA-01**: Developer can spin up Postgres and Redis via `docker compose up`
- [x] **INFRA-02**: Project is managed with uv (`pyproject.toml`, dependency groups, lock file)
- [x] **INFRA-03**: Developer can run the task runner via `uv run agent`
- [x] **INFRA-04**: Developer can run experiments via `uv run experiments.<task_type>` (e.g. `uv run experiments.recipe_research`)
- [x] **INFRA-05**: Developer can run Alembic migrations via `uv run migrate`
- [x] **INFRA-06**: RQ Dashboard is accessible for job inspection

### Gateway

- [x] **GW-01**: Telegram bot receives user messages via webhook and persists them to Postgres (`StoredMessage`)
- [x] **GW-02**: Gateway deduplicates incoming messages using `platform_message_id` unique constraint
- [x] **GW-03**: Gateway fetches the last N conversation messages (N configurable via env var) and attaches them as history
- [x] **GW-04**: Gateway enqueues a `handle-incoming-message` task at the front of the queue (urgent priority)
- [x] **GW-05**: Gateway sends outgoing Telegram messages and persists them to Postgres
- [x] **GW-06**: A `Conversation` record groups all messages for a `(platform, chat_id)` pair with a `@@unique` constraint

### Queue

- [x] **QUEUE-01**: Redis is configured with AOF persistence (`appendfsync always`) — no tasks lost on crash/reboot
- [x] **QUEUE-02**: Task runner processes jobs sequentially with exactly one worker (concurrency = 1)
- [x] **QUEUE-03**: All task inputs and outputs are strongly-typed Pydantic v2 models (`IncomingMessageInput/Output`, `RecipeResearchInput/Output`, `RecipeLoadInput/Output`, `SendNotificationInput/Output`)
- [x] **QUEUE-04**: All jobs have `result_ttl = -1` and `failure_ttl = -1` (infinite retention)
- [x] **QUEUE-05**: Failed jobs are retained in RQ's built-in failed job registry (dead-letter queue)
- [x] **QUEUE-06**: Agent can enqueue follow-up tasks at normal priority (back of queue) or urgent priority (front of queue)
- [x] **QUEUE-07**: All queue state changes are logged to console (task queued, processing started, task finished/failed)

### Workflow Engine

- [x] **WF-01**: `WorkflowRun` and `WorkflowRunStep` SQLAlchemy 2.x models exist in Postgres with Alembic migration
- [x] **WF-02**: `workflows.py` defines a `WorkflowDefinition` registry with `WorkflowStepDef` entries and `build_input` callables
- [x] **WF-03**: The `add-recipe` workflow is registered with three steps: `research` → `load` → `notify`
- [x] **WF-04**: `start-workflow` tool creates a `WorkflowRun` + all `WorkflowRunStep` records (status `PENDING`), enqueues the first step, and returns `workflow_run_id`
- [x] **WF-05**: Task runner marks a `WorkflowRunStep` as `RUNNING` when its job starts processing
- [x] **WF-06**: On step completion, task runner writes output to `WorkflowRunStep.artifact`, builds `accumulated_artifacts`, and enqueues the next `PENDING` step
- [x] **WF-07**: On final step completion, task runner marks the `WorkflowRun` as `DONE`
- [x] **WF-08**: On step failure, task runner marks the step `FAILED`, cancels all remaining `PENDING` steps, and marks the `WorkflowRun` `FAILED`
- [x] **WF-09**: `reply_context` is stored in `WorkflowRun.shared_context` and never appears in intermediate task inputs (`RecipeResearchInput`, `RecipeLoadInput`)

### Agent Infrastructure

- [x] **AGENT-01**: `LLMBackend` Protocol abstraction exists with `model` property and `create_agent()` method
- [x] **AGENT-02**: Three LLM adapters are implemented: Ollama (`langchain-ollama`), Anthropic (`langchain-anthropic`), OpenAI (`langchain-openai`)
- [x] **AGENT-03**: `agents.py` defines per-task-type configuration: model, prompt path, tools, skills
- [x] **AGENT-04**: Agent model API tokens are read from env vars named by task type (e.g. `RECIPE_RESEARCH_API_TOKEN`)
- [x] **AGENT-05**: Developer can override model or prompt per task type at runtime via `AGENT_OVERRIDES_FILEPATH` JSON file without redeploy
- [x] **AGENT-06**: Each skill is a directory under `src/agent/skills/` with an `index.md`; `index_content` is pre-loaded into agent context
- [x] **AGENT-07**: Agent can load skill sub-files on demand via `read-skill` tool using `skill-name/subfile.md` path format; path traversal outside configured skill directories is blocked
- [x] **AGENT-08**: System prompts are versioned markdown files at `src/agent/prompts/<task-type>/V001.md`; old versions are kept
- [x] **AGENT-09**: Debug log level can be enabled independently per module (gateway, scheduler, queue, agent, LLM)
- [x] **AGENT-10**: All agent actions are logged (LLM stream start, tool calls and results)
- [x] **AGENT-11**: `create_react_agent` from `langgraph.prebuilt` is used for all agents

### Notification Agent

- [x] **NOTIF-01**: `send-notification` task type is handled by the Notification agent
- [ ] **NOTIF-02**: `format-telegram-message` skill exists with `index.md` and sub-files covering Telegram MarkdownV2 formatting rules
- [x] **NOTIF-03**: Notification agent applies `format-telegram-message` skill to reformat pre-written text before delivery — it does not compose content
- [x] **NOTIF-04**: `send-notification` tool sends the formatted message to the user via the gateway
- [x] **NOTIF-05**: `send-notification/V001.md` system prompt exists

### Robotina Agent

- [ ] **ROBOT-01**: `handle-incoming-message` task type is handled by the Robotina agent
- [ ] **ROBOT-02**: Robotina agent has access to `household-manager-api` tool (reads/writes household data; auth injected invisibly; `401`/`403` raise hard errors)
- [ ] **ROBOT-03**: Robotina agent has access to `queue` tool (enqueue a single follow-up task directly, e.g. `send-notification` for direct replies)
- [ ] **ROBOT-04**: Robotina agent has access to `start-workflow` tool (initiate multi-step workflows)
- [ ] **ROBOT-05**: `household-manager` skill is updated to remove auth instructions (auth is handled by the tool, not the agent)
- [ ] **ROBOT-06**: `robotina/V001.md` system prompt exists
- [ ] **ROBOT-07**: Robotina agent correctly distinguishes direct-reply intent (→ `queue` tool) from multi-step workflow intent (→ `start-workflow` tool)

### Recipe Research Agent

- [ ] **RRECIPE-01**: `recipe-research` task type is handled by the Recipe Research agent
- [ ] **RRECIPE-02**: `recipe-research` skill exists with instructions for multi-site web search and structured recipe extraction
- [ ] **RRECIPE-03**: `web-search` tool is implemented via the Tavily API
- [ ] **RRECIPE-04**: Agent produces a `RecipeData` output with all fields populated (name, description, servings, times, ingredients with human-readable names, steps, source_url)
- [ ] **RRECIPE-05**: `recipe-research/V001.md` system prompt exists
- [ ] **RRECIPE-06**: A standalone experiment script (`experiments/recipe_research.py`) runs the agent against hardcoded representative inputs and sends traces to LangWatch

### Recipe Loader Agent

- [ ] **RLOAD-01**: `recipe-load` task type is handled by the Recipe Loader agent
- [ ] **RLOAD-02**: `recipe-load` skill exists with instructions for resolving food/unit names to IDs via `GET /api/foods?name=` and `GET /api/units?name=` and creating the recipe via `POST /api/recipes`
- [ ] **RLOAD-03**: Agent resolves human-readable ingredient names to `foodId` and `unitId` before creating the recipe
- [ ] **RLOAD-04**: Agent uses `household-manager-api` tool to create the recipe; returns `recipe_id` and `recipe_name`
- [ ] **RLOAD-05**: `recipe-load/V001.md` system prompt exists
- [ ] **RLOAD-06**: A standalone experiment script (`experiments/recipe_load.py`) runs the agent against hardcoded representative inputs and sends traces to LangWatch

### Observability

- [x] **OBS-01**: LangWatch + OpenTelemetry instrumentation is active on all agents
- [x] **OBS-02**: LangWatch endpoint and API key are read from environment variables
- [ ] **OBS-03**: The same instrumentation used in production is active during experiment runs; traces appear in the correct LangWatch experiment collection
- [ ] **OBS-04**: Each experiment script (`recipe-research`, `recipe-load`, `send-notification`) pins prompt version and model config via LangWatch tags/metadata
- [ ] **OBS-05**: A standalone experiment script (`experiments/send_notification.py`) exists for the send-notification agent

## v2 Requirements

Deferred to a future milestone. Infrastructure (`household_id` field) is already in place.

### Scheduler

- **SCHED-01**: A `scheduled-tasks` queue and dedicated `scheduler-worker` (with `--with-scheduler` flag) moves deferred jobs into `agent-tasks`
- **SCHED-02**: Agent can schedule one-off (`run_at`) and recurring (`cron`) tasks via `scheduler` tool
- **SCHED-03**: Scheduler HTTP API supports CRUD operations on scheduled tasks with Bearer auth
- **SCHED-04**: Scheduled task object includes `task_type`, `input`, `run_at`/`cron`, and `created_at`

### Future Capabilities

- **FUTURE-01**: Multi-household support (per-household API keys, auth routing, conversation isolation)
- **FUTURE-02**: Proactive agent messages (agent-initiated notifications based on scheduled tasks)
- **FUTURE-03**: Conversation-level memory (summarization / vector store beyond window-based history)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Automatic workflow retry | Retry without root cause fix produces same failure; compensating actions (undo half-created recipe) require saga logic not justified for Phase 1 |
| Agent-to-agent chaining | Violates "agents know nothing about the sequence" invariant; breaks centralized orchestration |
| Streaming Telegram responses | Telegram streaming requires open connections through the queue, breaking the decoupled reply model |
| Web UI for task monitoring | RQ Dashboard is sufficient; building custom UI before core functionality is proven wastes time |
| Per-household API keys | Single shared API key for Phase 1; `household_id` field exists as forward-compatibility shim |
| Mobile / additional messaging clients | Telegram-only for Phase 1; gateway design is abstracted for future extension |
| Real-time push notifications | Use scheduler once Phase 1 is stable; don't add proactive logic to Phase 1 agents |
| Inline Telegram formatting in content agents | Couples content agents to presentation layer; `send-notification` owns all Telegram formatting |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 1 | Complete |
| INFRA-04 | Phase 1 | Complete |
| INFRA-05 | Phase 1 | Complete |
| INFRA-06 | Phase 1 | Complete |
| QUEUE-01 | Phase 2 | Complete |
| QUEUE-02 | Phase 2 | Complete |
| QUEUE-03 | Phase 2 | Complete |
| QUEUE-04 | Phase 2 | Complete |
| QUEUE-05 | Phase 2 | Complete |
| QUEUE-06 | Phase 2 | Complete |
| QUEUE-07 | Phase 2 | Complete |
| WF-01 | Phase 2 | Complete |
| GW-01 | Phase 3 | Complete |
| GW-02 | Phase 3 | Complete |
| GW-03 | Phase 3 | Complete |
| GW-04 | Phase 3 | Complete |
| GW-05 | Phase 3 | Complete |
| GW-06 | Phase 3 | Complete |
| AGENT-01 | Phase 4 | Complete |
| AGENT-02 | Phase 4 | Complete |
| AGENT-03 | Phase 4 | Complete |
| AGENT-04 | Phase 4 | Complete |
| AGENT-05 | Phase 4 | Complete |
| AGENT-06 | Phase 4 | Complete |
| AGENT-07 | Phase 4 | Complete |
| AGENT-08 | Phase 4 | Complete |
| AGENT-09 | Phase 4 | Complete |
| AGENT-10 | Phase 4 | Complete |
| AGENT-11 | Phase 4 | Complete |
| OBS-01 | Phase 4 | Complete |
| OBS-02 | Phase 4 | Complete |
| WF-02 | Phase 5 | Complete |
| WF-03 | Phase 5 | Complete |
| WF-04 | Phase 5 | Complete |
| WF-05 | Phase 5 | Complete |
| WF-06 | Phase 5 | Complete |
| WF-07 | Phase 5 | Complete |
| WF-08 | Phase 5 | Complete |
| WF-09 | Phase 5 | Complete |
| NOTIF-01 | Phase 6 | Complete |
| NOTIF-02 | Phase 6 | Pending |
| NOTIF-03 | Phase 6 | Complete |
| NOTIF-04 | Phase 6 | Complete |
| NOTIF-05 | Phase 6 | Complete |
| OBS-03 | Phase 6 | Pending |
| OBS-05 | Phase 6 | Pending |
| ROBOT-01 | Phase 7 | Pending |
| ROBOT-02 | Phase 7 | Pending |
| ROBOT-03 | Phase 7 | Pending |
| ROBOT-04 | Phase 7 | Pending |
| ROBOT-05 | Phase 7 | Pending |
| ROBOT-06 | Phase 7 | Pending |
| ROBOT-07 | Phase 7 | Pending |
| RRECIPE-01 | Phase 8 | Pending |
| RRECIPE-02 | Phase 8 | Pending |
| RRECIPE-03 | Phase 8 | Pending |
| RRECIPE-04 | Phase 8 | Pending |
| RRECIPE-05 | Phase 8 | Pending |
| RRECIPE-06 | Phase 8 | Pending |
| OBS-04 | Phase 8 | Pending |
| RLOAD-01 | Phase 9 | Pending |
| RLOAD-02 | Phase 9 | Pending |
| RLOAD-03 | Phase 9 | Pending |
| RLOAD-04 | Phase 9 | Pending |
| RLOAD-05 | Phase 9 | Pending |
| RLOAD-06 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 68 total
- Mapped to phases: 68
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-25*
*Last updated: 2026-03-25 after roadmap creation — traceability updated with individual requirement-to-phase mappings*
