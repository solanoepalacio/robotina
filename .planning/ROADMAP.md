# Roadmap: Robotina

## Overview

Robotina is built in nine core phases following a strict dependency order: infrastructure and data contracts first, then gateway, then the LLM module and agent infrastructure, then the workflow engine, and finally agents in order of increasing complexity (send-notification -> handle-incoming-message -> recipe-research -> recipe-load). Each phase delivers a complete, verifiable capability that unblocks the next. Nothing in Phase 9 is testable until every prior phase is solid -- the architecture enforces this linearity.

Phases 10-12 are a follow-on track that migrates the agent layer to the LangChain 1.x agent API (`langchain.agents.create_agent`) and uses its new capabilities -- schema-constrained output via `response_format` (Phase 11) and middleware-based instrumentation (Phase 12) -- to retire bug classes that surfaced during real use (notably the 2026-05-13 canelones de choclo parse failure where prose-wrapped JSON defeated `extract_task_output`). These phases run after Phase 9 in strict order: 10 -> 11 -> 12.

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
- [x] **Phase 6: send-notification Agent** - Notification agent formats and delivers Telegram messages with LangWatch traces verified (completed 2026-03-27)
- [x] **Phase 7: handle-incoming-message Agent** - Robotina routing agent handles direct replies and initiates multi-step workflows end-to-end (completed 2026-03-27)
- [x] **Phase 07.1: Deterministic Agent Termination (INSERTED)** - Engine-enforced single-round agent termination via `Command(goto=END)`; eliminates duplicate-message and rare infinite-loop bugs (completed 2026-05-08)
- [x] **Phase 8: recipe-research Agent** - Recipe research agent performs structured web search and produces typed RecipeData output (completed 2026-03-30)
- [x] **Phase 9: recipe-load Agent and End-to-End Integration** - Recipe loader resolves food/unit names and creates recipes; full add-recipe workflow works end-to-end (completed 2026-05-12)
- [x] **Phase 10: LangChain 1.x Agent API Migration** - Replace `langgraph.prebuilt.create_react_agent` with `langchain.agents.create_agent` across all three LLMBackend adapters with strict behavior parity (completed 2026-05-13)
- [x] **Phase 11: Structured Agent Output via response_format** - Replace free-text JSON emission from recipe-research and recipe-load agents with schema-constrained output via `create_agent(response_format=...)` (completed 2026-05-13)
- [x] **Phase 12: Middleware-Based Agent Instrumentation** - Migrate per-agent OTel/LangWatch instrumentation from `langchain_core.callbacks` to `create_agent` middleware (`@before_model`, `@after_model`, `@wrap_model_call`) (completed 2026-05-14)

## Phase Details

### Phase 1: Developer Tooling and Infrastructure
**Goal**: Developer has a working local environment -- Postgres and Redis are running, the uv project is scaffolded, migrations run cleanly, and all dev shortcuts work
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
- [x] 01-01-PLAN.md -- Docker Compose stack (Postgres 15, Redis 7 AOF, RQ Dashboard)
- [x] 01-02-PLAN.md -- uv project scaffold, src/robotina package tree, Alembic configuration
- [x] 01-03-PLAN.md -- uv run agent entrypoint, experiment stubs, automated test scaffold

### Phase 2: Database Models and Queue Layer
**Goal**: All shared data contracts exist -- SQLAlchemy models are migrated to Postgres, all Pydantic task I/O models are defined, and RQ serialization is verified for every task type before any agent is written
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
- [x] 02-01-PLAN.md -- SQLAlchemy models (Conversation, StoredMessage, WorkflowRun, WorkflowRunStep), db.py Base, Alembic migration 0002
- [x] 02-02-PLAN.md -- Pydantic v2 task I/O models (all 8 Input/Output classes) in task_types.py
- [x] 02-03-PLAN.md -- LoggingWorker refactor, pyproject.toml markers, RQ integration tests

### Phase 3: Gateway
**Goal**: The Telegram bot is the live front door -- it receives user messages, persists them with deduplication, fetches conversation history, and enqueues tasks at the front of the queue
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
- [x] 03-01-PLAN.md -- Test scaffold: conftest.py gateway fixtures + test_gateway.py stubs (GW-01 through GW-06)
- [x] 03-02-PLAN.md -- Incoming handler (handler.py, gateway __init__.py), uv run all subprocess launcher, pyproject.toml entries
- [x] 03-03-PLAN.md -- Outgoing send_message() function (send.py)

### Phase 4: LLM Module and Agent Infrastructure
**Goal**: A general-purpose agent execution foundation exists -- LLMBackend abstraction, three provider adapters, agent runner with correct per-job object scoping, skill loading, prompt versioning, runtime overrides, and LangWatch instrumentation initialized
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
- [x] 04-01-PLAN.md -- Wave 0: unit test scaffolds (6 test files) + gateway enqueue string fix (run_task)
- [x] 04-02-PLAN.md -- LLMBackend Protocol + OllamaBackend, AnthropicBackend, OpenAIBackend adapters
- [x] 04-03-PLAN.md -- agents.py registry: AgentConfig dataclass, AGENT_REGISTRY, get_agent_config(), configure_logging()
- [x] 04-04-PLAN.md -- run_task() universal job function + AgentLoggingHandler + runner.py LangWatch init
- [x] 04-05-PLAN.md -- SkillSet + ReadSkillTool + household-manager skill relocation to canonical path
- [x] 04-06-PLAN.md -- hello-world prompt file + full unit suite verification + manual end-to-end checkpoint

### Phase 5: Task Runner and Workflow Engine
**Goal**: The sequential task runner correctly orchestrates workflow state -- marking steps running, persisting artifacts, advancing to the next step, and propagating failures -- before any real agent runs through it
**Depends on**: Phase 4
**Requirements**: QUEUE-01, WF-02, WF-03, WF-04, WF-05, WF-06, WF-07, WF-08, WF-09
**Success Criteria** (what must be TRUE):
  1. `workflows.py` defines the `add-recipe` workflow with three steps (`research` -> `load` -> `notify`) in the `WorkflowDefinition` registry; each `WorkflowStepDef` has a `build_input` callable that never receives a mutable `shared_context`
  2. `start-workflow` tool creates a `WorkflowRun` and all `WorkflowRunStep` records with `PENDING` status, enqueues the first step, and returns a `workflow_run_id`
  3. When a step job starts, its `WorkflowRunStep` transitions to `RUNNING`; on completion, its output is written to `artifact`, accumulated artifacts are built, and the next `PENDING` step is enqueued
  4. When the final step completes, the `WorkflowRun` is marked `DONE`
  5. When a step fails, the failed step is marked `FAILED`, all remaining `PENDING` steps are cancelled, and the `WorkflowRun` is marked `FAILED`; `reply_context` is never present in `RecipeResearchInput` or `RecipeLoadInput`
**Plans**: 4 plans

Plans:
- [x] 05-01-PLAN.md -- Wave 0: test scaffolds (test_workflows.py, test_workflow_runner.py, test_start_workflow_tool.py)
- [x] 05-02-PLAN.md -- workflows.py: WorkflowStepDef, WorkflowDefinition, WORKFLOW_REGISTRY (add-recipe + hello-world-2step)
- [x] 05-03-PLAN.md -- queue/workflow_runner.py: start_workflow, on_step_start, on_step_complete, on_step_failed
- [x] 05-04-PLAN.md -- run_task() workflow hooks + agent/tools/start_workflow.py + integration tests + human checkpoint

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
- [x] 06-01-PLAN.md -- Wave 0+registry: test stubs (test_send_notification_tool.py) + remove hello-world from AGENT_REGISTRY and WORKFLOW_REGISTRY + update existing tests
- [x] 06-02-PLAN.md -- SendNotificationTool implementation + send_message() parse_mode fix + run_task() injection
- [x] 06-03-PLAN.md -- format-telegram-message skill (4 files) + send-notification/V001.md prompt
- [x] 06-04-PLAN.md -- experiments/send_notification.py full implementation + human LangWatch verification checkpoint

### Phase 7: handle-incoming-message Agent
**Goal**: The Robotina routing agent correctly handles natural-language messages -- either enqueuing a direct `send-notification` reply or initiating a multi-step workflow -- closing the direct-reply user story end-to-end
**Depends on**: Phase 6
**Requirements**: ROBOT-01, ROBOT-02, ROBOT-03, ROBOT-04, ROBOT-05, ROBOT-06, ROBOT-07
**Success Criteria** (what must be TRUE):
  1. A Telegram message asking a household question (e.g., "what's on the meal plan?") results in an answer delivered back to the user via the `queue` tool -> `send-notification` agent path
  2. A Telegram message requesting a multi-step task (e.g., "add a recipe for X") results in a `WorkflowRun` being created via the `start-workflow` tool with the correct initial step enqueued
  3. The `household-manager-api` tool is used to read household data; a `401` or `403` response raises a hard error that stops the agent loop rather than being retried as a recoverable error
  4. The `household-manager` skill no longer contains auth instructions (auth is injected by the tool, not the agent)
**Plans**: 4 plans

Plans:
- [x] 07-01-PLAN.md -- Wave 0: test stubs for HouseholdManagerApiTool and QueueTool
- [x] 07-02-PLAN.md -- HouseholdManagerApiTool + QueueTool implementations
- [x] 07-03-PLAN.md -- household-manager skill auth removal + robotina/V001.md routing prompt
- [x] 07-04-PLAN.md -- agents.py registry entry + run_task() injection + human checkpoint

### Phase 07.1: Deterministic Agent Termination (INSERTED)

**Goal:** Make agent termination a runtime guarantee, not a prompt request — eliminates the duplicate-message bug and the (rare) infinite-loop bug captured in `infinite-loop-messages.log`. After this phase, every agent run that successfully emits a side-effecting tool call ends in exactly one round.
**Requirements**: TBD
**Depends on:** Phase 7
**Success Criteria** (what must be TRUE):
  1. `send-notification` task type runs without invoking any LLM (no `LLM stream start` log line for it)
  2. Routing agent emits exactly one tool call per request and terminates immediately after via engine-enforced `Command(goto=END)`
  3. Per-workflow ack agent (`acknowledge-add-recipe`) emits exactly one `queue` call and terminates
  4. `add-recipe` workflow runs end-to-end with one ack at the start and one final notification — no duplicates anywhere
  5. `uv run pytest` is green
**Plans:** 3 plans

Plans:
- [x] 07.1-01-PLAN.md -- Wave 0: replace send-notification agent with deterministic Python (plain text)
- [x] 07.1-02-PLAN.md -- Wave 1: per-workflow acknowledge-add-recipe agent + routing-prompt simplification
- [x] 07.1-03-PLAN.md -- Wave 2: terminal queue and start-workflow tools via Command(goto=END)

### Phase 8: recipe-research Agent
**Goal**: The recipe research pipeline performs structured multi-site web search via Tavily across 4 sequential sub-tasks (gather, instructions, ingredients, metadata) and produces a fully populated `RecipeData` output, with traces pinned to LangWatch experiment collections
**Depends on**: Phase 7
**Requirements**: RRECIPE-01, RRECIPE-02, RRECIPE-03, RRECIPE-04, RRECIPE-05, RRECIPE-06, OBS-04
**Success Criteria** (what must be TRUE):
  1. A `recipe-research` job with a recipe name input results in a `RecipeData` output with all fields populated: name, description, servings, times, ingredients with human-readable food and unit names, steps, and source URL
  2. The `web-search` tool calls the Tavily API with a bounded `max_results` and returns structured results; the agent uses multiple search queries across different recipe sites
  3. The `recipe-research` skill instructions and `recipe-research/V001.md` prompt exist and are loaded by the agent
  4. Running `experiments/recipe_research.py` completes without error, a trace appears in the correct LangWatch experiment collection, and the experiment script pins prompt version and model config via LangWatch tags
**Plans**: 4 plans

Plans:
- [x] 08-01-PLAN.md -- I/O models (8 new Pydantic classes) + workflow registry update (6-step add-recipe) + recipe-scrapers dependency
- [x] 08-02-PLAN.md -- WebSearchTool implementation + recipe-research skill (5 files) + 4 system prompt files
- [x] 08-03-PLAN.md -- 4 AgentConfig registry entries + run_task() elif tool injection + unit tests
- [x] 08-04-PLAN.md -- Combined experiment script (experiments/recipe_research.py) + human pipeline verification

### Phase 9: recipe-load Agent and End-to-End Integration
**Goal**: The recipe loader agent resolves human-readable ingredient names to household-manager IDs and creates the recipe; the full add-recipe workflow runs end-to-end from a Telegram message to a delivered recipe confirmation
**Depends on**: Phase 8
**Requirements**: RLOAD-01, RLOAD-02, RLOAD-03, RLOAD-04, RLOAD-05, RLOAD-06
**Success Criteria** (what must be TRUE):
  1. A `recipe-load` job with a `RecipeData` input resolves all ingredient food names and unit names to `foodId` and `unitId` via `GET /api/foods?name=` and `GET /api/units?name=`, then creates the recipe via `POST /api/recipes`, returning `recipe_id` and `recipe_name`
  2. The agent handles partial and zero name matches gracefully (does not crash; surfaces the issue to the workflow)
  3. Running `experiments/recipe_load.py` completes without error, a trace appears in the correct LangWatch experiment collection, and the experiment script pins prompt version and model config
  4. Sending "add a recipe for carbonara" to the Telegram bot results in a `WorkflowRun` progressing through all three steps (`research` -> `load` -> `notify`) and a formatted recipe confirmation message delivered back to the user
**Plans**: 2 plans

Plans:
- [x] 09-01-PLAN.md -- Core recipe-load agent wiring: RecipeLoadOutput extension, AGENT_REGISTRY entry, run_task() elif, V001.md prompt, workflow notify update, unit tests
- [x] 09-02-PLAN.md -- Experiment script (experiments/recipe_load.py) with 4 edge cases + human verification checkpoint

### Phase 10: LangChain 1.x Agent API Migration
**Goal**: Replace `langgraph.prebuilt.create_react_agent` with `langchain.agents.create_agent` across all three LLMBackend adapters (Ollama, Anthropic, OpenAI) with strict behavior parity. This is the prerequisite unlock for the LangChain 1.x agent features (`response_format`, middleware, custom state schemas) that the project is on but not yet using -- the lockfile pins `langchain 1.2.13` and `langchain-core 1.2.22` while the code still imports the langgraph-prebuilt API.
**Depends on**: Phase 9
**Requirements**: AGENT-12
**Success Criteria** (what must be TRUE):
  1. All three `LLMBackend` adapters in `src/robotina/llm/__init__.py` call `langchain.agents.create_agent` and no longer import `create_react_agent` from `langgraph.prebuilt`; the AGENT-11/D-03 decision record is updated to reference the new API and the rationale for the switch
  2. `return_direct=True` short-circuit semantics are preserved -- `QueueTool` and `StartWorkflowTool` still terminate the agent in one round with a `ToolMessage` as the last state message, and `extract_task_output`'s `tool_message` branch (workflow_runner.py:47-48) continues to fire correctly
  3. All four test files that construct real agents -- `test_queue_tool.py`, `test_start_workflow_tool.py`, `test_household_manager_api_tool.py`, `test_llm_backend.py` -- are updated to use `create_agent` and `uv run pytest` is green
  4. End-to-end `add-recipe` workflow (research -> load -> notify) runs to completion on at least one real recipe query with no semantic regression versus the pre-migration baseline
  5. CLAUDE.md technology stack table is updated -- `langchain >=1.2`, `langchain-core >=1.2`, langgraph entry reflects its new role as a lower-level dependency (not the agent API surface); the "What NOT to Use" table reflects that `create_react_agent` is now superseded by `create_agent` rather than the recommended path
**Plans**: 3 plans

Plans:
**Wave 1**
- [x] 10-01-PLAN.md -- AGENT-12 requirement + source-grep lock test (Wave 1)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 10-02-PLAN.md -- Adapter migration + 4 test files + 7-file comment sweep (Wave 2)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 10-03-PLAN.md -- CLAUDE.md / STATE.md / PROJECT.md / new decision record + end-to-end Telegram checkpoint (Wave 3)

**Notes:**
- Pure mechanical swap with strict parity -- no `response_format`, no middleware, no state-schema changes. Those are Phases 11 and 12.
- Riskiest area: the `return_direct=True` short-circuit semantics. `create_agent` is built on langgraph internally so this should hold, but explicit verification via the existing test_queue_tool / test_start_workflow_tool patterns is part of success criterion 2.

### Phase 11: Structured Agent Output via response_format
**Goal**: Replace free-text JSON emission from the recipe-research sub-agents and the recipe-load agent with schema-constrained output via `create_agent(response_format=...)`, eliminating the prose-wrapping parse failures that today cause workflow dead-letters (see canelones de choclo incident 2026-05-13: agent emitted valid JSON wrapped in preamble + markdown fence + postscript, defeating `extract_task_output`'s parser and cancelling 5 remaining workflow steps).
**Depends on**: Phase 10
**Requirements**: RRECIPE-07, RLOAD-07, WF-10
**Success Criteria** (what must be TRUE):
  1. The four recipe-research sub-agents (`recipe-research-gather`, `-instructions`, `-ingredients`, `-metadata`) and the `recipe-load` agent are configured with `response_format` bound to their respective Pydantic output models; agent outputs come from the structured channel rather than free-text content
  2. The prose-stripping / code-fence / JSON-scan fallbacks in `extract_task_output` (workflow_runner.py:55-76) are removed or reduced to a defensive error -- structured-output agents produce parsable artifacts without that logic
  3. A regression test reproducing the 2026-05-13 canelones parse failure (agent output: prose preamble + ```json fence + postscript) passes on the new pipeline
  4. End-to-end `add-recipe` workflow runs without parse failures across at least three distinct recipe queries with no manual prompt tuning between runs
  5. `uv run pytest` is green; experiments still emit valid LangWatch traces tagged with prompt version and model config
**Plans**: 4 plans

Plans:
**Wave 1**
- [ ] 11-01-PLAN.md -- LLMBackend Protocol + 3 adapters with response_format kwarg + AgentConfig.response_format_model field + REQUIREMENTS.md registration (RRECIPE-07/RLOAD-07/WF-10) + adapter & registry tests

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 11-02-PLAN.md -- workflow_runner refactor: _extract_task_output prefers structured_response, fail-loud on missing, free-text ladder removed; on_step_complete resolves expects_structured from AgentConfig
- [ ] 11-03-PLAN.md -- bind 5 agents to Pydantic Outputs; bump prompts (V003/V002) stripping JSON boilerplate; thread response_format kwarg through run_task

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 11-04-PLAN.md -- decision record + STATE/CLAUDE.md updates + 3-query manual end-to-end checkpoint; flip RRECIPE-07/RLOAD-07/WF-10 to Complete after sign-off

**Notes:**
- This is the phase that retires the canelones-style bug class permanently. Phase 10 makes the API available; this phase uses it where it pays off.
- Each agent's Pydantic output model already exists in `src/robotina/queue/task_types.py` (or wherever the QUEUE-* models live) -- this phase binds them to the agent, not authors new schemas.
- Strategy decision (resolved in 11-CONTEXT.md / 11-RESEARCH.md): Ollama -> `ToolStrategy(Schema)` (correctness — `gpt-oss` is in `FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT`, so AutoStrategy would route to ProviderStrategy on Ollama, which Ollama does not honor). Anthropic / OpenAI -> `ProviderStrategy(Schema)`.
- New requirement ID note: the planning context proposed `WF-08` for the workflow-runner change; `WF-08` was already taken (Phase 5 step-failure handling). Plan 11-01 uses `WF-10` as the next free WF-* slot. Same scope; different number.

### Phase 12: Middleware-Based Agent Instrumentation
**Goal**: Migrate the per-agent instrumentation layer (today implemented as `langchain_core.callbacks` handlers in `src/robotina/agent/callbacks.py`) to `create_agent` middleware (`@before_model`, `@after_model`, `@wrap_model_call`). This aligns Robotina with the LangChain 1.x recommended instrumentation pattern, gives a typed and composable place for span/log enrichment, and clears the way for additional pre/post-model guards (token-budget checks, prompt-injection filters) without further callback bolt-ons. LangWatch traces and the existing per-tool / per-LLM log lines must remain intact.
**Depends on**: Phase 11
**Requirements**: TBD (new -- candidate OBS-06)
**Success Criteria** (what must be TRUE):
  1. Per-agent log lines currently produced by `robotina.agent.callbacks` (`LLM stream start`, `Tool call`, `Tool result`) are emitted by middleware -- the legacy `AgentLoggingHandler` callback is removed or vestigial, and no remaining call site passes it to `create_agent`
  2. LangWatch traces for at least one production run (handle-incoming-message -> queue -> send-notification) and one experiment run (`uv run experiments/recipe_research.py` or equivalent) appear in the correct LangWatch collection with no regression in span content (model name, tool calls, token usage where the provider exposes it)
  3. `uv run pytest` is green; instrumentation-related tests are updated to assert middleware presence and ordering rather than callback registration
  4. No `from langchain_core.callbacks` imports remain in `src/robotina/agent/` except where the LangWatch SDK itself requires them internally (verified by grep + a brief written rationale per remaining import in the phase summary)
  5. The phase summary documents the LangWatch + middleware interaction model -- specifically whether LangWatch's OTel bridge picks up traces independent of callbacks, or whether a thin shim is needed
**Plans**: 2 plans

Plans:
- [x] 12-01-PLAN.md -- Create middleware module + wire into all 3 LLMBackend.create_agent methods (additive only; coexists with legacy callback) + middleware unit tests
- [ ] 12-02-PLAN.md -- Delete callbacks.py + remove AgentLoggingHandler from jobs.py (keep LangWatch tracer) + prune legacy tests + phase summary + manual smoke checkpoint

**Notes:**
- Sequencing matters: this phase runs **after** Phase 11 so middleware sees the `response_format` plumbing already in place. Running them in parallel would create merge friction in `src/robotina/llm/__init__.py`.
- Real risk: LangWatch SDK confidence is LOW per project memory ([[project_robotina]]). Verify whether LangWatch hooks via callbacks or via OTel directly **before** rewriting -- if it depends on callbacks, success criterion 5 grows into a small bridge layer rather than a clean rip-and-replace. A short spike at the start of Phase 12 planning is appropriate.
- This phase does **not** include custom state schemas for `reply_context` / `household_id` -- that work is captured in backlog (Phase D, see .planning/backlog/) and would be promoted to a phase only when at least three tools need ambient context they currently get via kwargs.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10 -> 11 -> 12

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Developer Tooling and Infrastructure | 3/3 | Complete    | 2026-03-25 |
| 2. Database Models and Queue Layer | 3/3 | Complete   | 2026-03-25 |
| 3. Gateway | 3/3 | Complete   | 2026-03-25 |
| 4. LLM Module and Agent Infrastructure | 6/6 | Complete   | 2026-03-26 |
| 5. Task Runner and Workflow Engine | 5/5 | Complete   | 2026-03-27 |
| 6. send-notification Agent | 4/4 | Complete   | 2026-03-27 |
| 7. handle-incoming-message Agent | 4/4 | Complete   | 2026-03-27 |
| 07.1. Deterministic Agent Termination (INSERTED) | 3/3 | Complete   | 2026-05-08 |
| 8. recipe-research Agent | 4/4 | Complete   | 2026-03-30 |
| 9. recipe-load Agent and End-to-End Integration | 2/2 | Complete   | 2026-05-12 |
| 10. LangChain 1.x Agent API Migration | 3/3 | Complete   | 2026-05-13 |
| 11. Structured Agent Output via response_format | 0/4 | Planned | - |
| 12. Middleware-Based Agent Instrumentation | 2/2 | Complete   | 2026-05-14 |

## Backlog

Unsequenced ideas that aren't ready for active planning. Promote with `/gsd-review-backlog` when promotion criteria are met.

### Phase 999.1: Custom state schemas for reply_context and household_id (BACKLOG)

**Goal:** Lift `reply_context: ReplyContext` and `household_id: str` from per-task `*Input` Pydantic models into a typed `AgentState` schema passed to `create_agent(state_schema=...)`. Tools access these via `InjectedState` rather than runtime kwargs. The job dispatcher in `run_task()` (`src/robotina/queue/jobs.py`) maps `WorkflowRun.shared_context` -> agent state at invocation time.

**Why this is a backlog item, not an active phase:** This refactor changes the contract between the workflow runner / job dispatcher and the agent -- a meaningful structural shift. Real ergonomic value (removes the "thread `household_id` through every `*Input` model and every tool signature" plumbing) but no current production pain forces it. Adding new ambient fields today is annoying-but-rare, not blocking.

**Requirements:** TBD

**Depends on:** Phase 10 (requires `langchain.agents.create_agent`; `langgraph.prebuilt.create_react_agent` does not cleanly support `state_schema=`). Independent of Phases 11 and 12 -- they make this phase nicer when promoted, but neither requires it.

**Promotion criteria** -- promote to an active phase via `/gsd-review-backlog` when ANY of:
  1. Three or more tools need ambient context (currently only `household_id` is threaded; if `user_id`, `locale`, or workflow-scoped flags get added, this triggers)
  2. Adding a new ambient field becomes a recurring chore (touched in 2+ phases of work over a quarter)
  3. A future phase wants middleware that needs typed state reads (Phase 12 follow-on, e.g. enriching spans with `reply_context.platform` automatically)

**Scope estimate when promoted:** 1-2 days. Touches: agent construction in `src/robotina/llm/__init__.py` (3 backends); tool signatures (`household_manager_api.py`, `queue.py`, `start_workflow.py`, `web_search.py`); job dispatcher in `src/robotina/queue/jobs.py`; the 4 test files that build real agents.

**Source decision:** Sequencing discussion 2026-05-12, conversation following the canelones de choclo parse failure analysis (2026-05-13 logs). User opted to land A/B/C (Phases 10/11/12) and defer D as backlog.

**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 13: Queue Visibility Dashboard

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 12
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 13 to break down)
