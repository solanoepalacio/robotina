# Architecture Research

**Domain:** Python AI agent system with task queue, multi-step workflow orchestration, and Telegram gateway
**Researched:** 2026-03-25
**Confidence:** HIGH (spec is authoritative and fully prescriptive; research validates and deepens)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          INGRESS LAYER                               │
│  ┌─────────────────────────┐   ┌─────────────────────────────────┐  │
│  │  Gateway (Telegram bot) │   │  Scheduler API (HTTP, Bearer)   │  │
│  │  - receive messages     │   │  - POST/GET/DELETE scheduled     │  │
│  │  - persist conversation │   │    tasks                        │  │
│  │  - enqueue task         │   │                                 │  │
│  └────────────┬────────────┘   └──────────────┬──────────────────┘  │
└───────────────┼────────────────────────────────┼────────────────────┘
                │                                │
                ▼                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          QUEUE LAYER                                 │
│  ┌──────────────────────────────┐  ┌────────────────────────────┐   │
│  │  agent-tasks queue (Redis)   │  │  scheduled-tasks queue     │   │
│  │  - AOF persistence           │  │  - RQ scheduler            │   │
│  │  - result_ttl = -1           │  │  - fires → agent-tasks     │   │
│  │  - failed job registry       │  │                            │   │
│  └──────────────┬───────────────┘  └────────────────────────────┘   │
└─────────────────┼───────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     TASK RUNNER (concurrency=1)                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Pre-job hook: check WorkflowRunStep → mark RUNNING            │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │  Agent Dispatch                                          │  │ │
│  │  │  agents.py lookup → load prompt, tools, skills, LLM     │  │ │
│  │  │  LLMBackend.create_agent() → LangChain agent executor   │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  │  Post-job hook: persist artifact → build next input → enqueue  │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          AGENT LAYER                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │ handle-      │  │ recipe-      │  │ recipe-load │  │ send-    │ │
│  │ incoming-    │  │ research     │  │             │  │ notif-   │ │
│  │ message      │  │              │  │             │  │ ication  │ │
│  └──────────────┘  └──────────────┘  └─────────────┘  └──────────┘ │
│  Each agent = prompt + tools + skills + LLMBackend instance         │
└─────────────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        PERSISTENCE LAYER                             │
│  ┌────────────────────────────┐  ┌───────────────────────────────┐  │
│  │  Postgres (SQLAlchemy)     │  │  Redis (AOF)                  │  │
│  │  - Conversation            │  │  - agent-tasks queue          │  │
│  │  - StoredMessage           │  │  - scheduled-tasks queue      │  │
│  │  - WorkflowRun             │  │  - RQ job result backend      │  │
│  │  - WorkflowRunStep         │  │  - RQ failed job registry     │  │
│  └────────────────────────────┘  └───────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SERVICES                             │
│  ┌──────────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ Household Manager│  │  Tavily API  │  │  LLM Providers         │ │
│  │ API (backend)    │  │ (web search) │  │  Ollama / Anthropic /  │ │
│  │                  │  │              │  │  OpenAI                │ │
│  └──────────────────┘  └──────────────┘  └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| **Gateway** | Receives Telegram messages; persists conversation; fetches history; enqueues `handle-incoming-message`; sends replies to users | Telegram API, Postgres, agent-tasks queue |
| **Scheduler API** | HTTP interface for creating/reading/deleting scheduled tasks | scheduled-tasks queue (Redis) |
| **agent-tasks queue** | Durable FIFO queue for all agent work. Single source of truth for pending/active jobs. | Redis (AOF), Task Runner |
| **scheduled-tasks queue** | Separate RQ queue managed by scheduler-worker. Fires jobs into agent-tasks on schedule. | Redis, agent-tasks queue |
| **Task Runner** | Sole consumer of agent-tasks (concurrency=1). Dispatches agent, wraps job lifecycle with workflow advancement hooks. | agent-tasks queue, Postgres (WorkflowRun/Step), Agent layer |
| **Workflow Engine** | Embedded in Task Runner. Advances workflow state on job start/complete/fail. Persists artifacts. Enqueues next step. | Postgres, agent-tasks queue |
| **Agent (per task type)** | Executes LLM inference with dynamic prompt, tools, skills. Returns typed output. Has no knowledge of workflow membership. | LLM Provider, Tools (HM API, web-search, queue, etc.) |
| **LLMBackend** | Protocol abstraction. Each adapter wraps a LangChain model class. Exposes `model` and `create_agent()`. | LangChain, LLM providers |
| **agents.py** | Registry: maps task type → {LLMBackend config, prompt path, tools, skills}. Supports runtime override via `AGENT_OVERRIDES_FILEPATH`. | Read by Task Runner at dispatch time |
| **workflows.py** | Registry: maps workflow type → ordered `WorkflowStepDef` list with `build_input` callables. | Read by Workflow Engine at advancement time |
| **Skills** | Markdown files providing domain knowledge to agents. Lazy-loaded (index pre-loaded, sub-files on demand via `read-skill` tool). | Agent context |
| **Scheduler Worker** | Separate RQ worker process with `--with-scheduler`. Moves fired jobs from scheduled-tasks → agent-tasks. | Redis queues |
| **Household Manager API** | External backend. Source of truth for household data. Accessed via `household-manager-api` tool. | Agent tool calls |

## Recommended Project Structure

```
robotina/
├── src/
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── protocol.py          # LLMBackend Protocol definition
│   │   ├── adapters/
│   │   │   ├── ollama.py        # OllamaBackend(LLMBackend)
│   │   │   ├── anthropic.py     # AnthropicBackend(LLMBackend)
│   │   │   └── openai.py        # OpenAIBackend(LLMBackend)
│   ├── agent/
│   │   ├── agent.py             # Agent runner (spawned per task)
│   │   ├── agents.py            # Task-type → config registry
│   │   ├── workflows.py         # Workflow definitions & registry
│   │   ├── prompts/
│   │   │   ├── robotina/
│   │   │   │   └── V001.md
│   │   │   ├── recipe-research/
│   │   │   │   └── V001.md
│   │   │   ├── recipe-load/
│   │   │   │   └── V001.md
│   │   │   └── send-notification/
│   │   │       └── V001.md
│   │   ├── skills/
│   │   │   ├── household-manager/
│   │   │   │   ├── index.md     # pre-loaded at agent startup
│   │   │   │   └── *.md         # lazy-loaded via read-skill tool
│   │   │   ├── recipe-research/
│   │   │   ├── recipe-load/
│   │   │   └── format-telegram-message/
│   │   └── tools/
│   │       ├── household_manager_api.py
│   │       ├── read_skill.py
│   │       ├── web_search.py
│   │       ├── queue_tool.py
│   │       ├── start_workflow.py
│   │       ├── send_notification.py
│   │       └── scheduler_tool.py
│   ├── queue/
│   │   ├── __init__.py
│   │   ├── models.py            # Pydantic input/output models for all task types
│   │   ├── task_runner.py       # RQ worker + workflow advancement hooks
│   │   └── connection.py        # Redis connection factory
│   ├── gateway/
│   │   ├── __init__.py
│   │   ├── bot.py               # Telegram bot (python-telegram-bot)
│   │   ├── models.py            # Conversation, StoredMessage (SQLAlchemy)
│   │   └── service.py           # Message persistence + history fetch
│   └── scheduler/
│       ├── __init__.py
│       ├── api.py               # FastAPI/Flask HTTP endpoints
│       ├── models.py            # ScheduledTask Pydantic model
│       └── worker.py            # scheduler-worker entry point
├── db/
│   ├── models.py                # WorkflowRun, WorkflowRunStep + gateway models
│   └── migrations/              # Alembic
│       ├── env.py
│       └── versions/
├── experiments/
│   ├── recipe_research.py       # standalone LangWatch experiment script
│   ├── recipe_load.py
│   └── send_notification.py
├── tests/
├── pyproject.toml               # uv project, uv run shortcuts
└── docker-compose.yml           # Postgres + Redis
```

### Structure Rationale

- **llm/**: Isolated from everything else. Pure protocol + adapters. Nothing imports from here except agent dispatcher. Easy to add new providers.
- **agent/**: Contains everything specific to agent execution — config registries, prompts, skills, tools. `agents.py` and `workflows.py` are the authoritative definition files that must be updated when adding task types or workflow steps.
- **queue/**: Queue infrastructure separate from agent logic. `task_runner.py` is the only file that couples queue consumption to agent execution.
- **gateway/**: Self-contained ingress module. Its only output is enqueuing tasks. Its only input is Telegram webhooks.
- **scheduler/**: Self-contained scheduling module. HTTP API + worker. Can be deployed independently.
- **db/**: Shared Postgres models (gateway conversations + workflow state share one database and one Alembic migration chain). Keeps schema evolution centralized.
- **experiments/**: Outside `src/` — these are developer tooling, not production code.

## Architectural Patterns

### Pattern 1: Centralized Orchestrator (chosen)

**What:** A single component (Task Runner) is responsible for all workflow state transitions. Individual agents know only their own task — they accept typed input, run, and return typed output. The Task Runner reads the workflow registry to determine what comes next, persists artifacts, and enqueues the next step.

**When to use:** When agents are specialized and should remain decoupled from sequence logic. When workflow structure needs to change without touching agent code. When auditability of multi-step state is important (each step's artifact is persisted independently).

**Trade-offs:**
- Pro: Agent code is simple and testable in isolation. Adding a new workflow step requires only a new `WorkflowStepDef` in `workflows.py` — no existing agent code changes.
- Pro: `reply_context` (UI concern) never leaks into intermediate task inputs.
- Pro: All workflow state is inspectable in Postgres at any point.
- Con: Task Runner is a critical component — it couples queue consumption with workflow advancement logic. A bug in the hook affects all workflow jobs.
- Con: Workflow definitions are static Python code, not database-driven; modifying a workflow requires a redeploy.

```python
# Task Runner advancement hook (post-job)
def advance_workflow(job, step_record, workflow_run):
    step_record.artifact = job.result.model_dump()
    step_record.status = WorkflowStepStatus.DONE

    accumulated = {s.step_key: s.artifact for s in workflow_run.steps if s.status == DONE}
    workflow_def = WORKFLOW_REGISTRY[workflow_run.workflow_type]
    next_step = next((s for s in workflow_def.steps if s.step_key not in accumulated), None)

    if next_step is None:
        workflow_run.status = WorkflowStatus.DONE
    else:
        task_input = next_step.build_input(workflow_run.shared_context, accumulated)
        job_id = queue.enqueue(run_task, task_type=next_step.task_type, input=task_input)
        step_record_next = get_step(workflow_run, next_step.step_key)
        step_record_next.task_job_id = job_id
```

### Pattern 2: Agent-Chaining (rejected)

**What:** Each agent, upon completing its task, decides and enqueues the next task itself. Agents are aware of the sequence they belong to.

**When to use:** Simple two-step pipelines where sequence logic is trivially obvious and will never change.

**Trade-offs:**
- Pro: No separate orchestrator component needed.
- Con: `reply_context` and other cross-cutting concerns must flow through every intermediate task input, coupling agents to UI details they don't logically own.
- Con: Adding or removing a step from a sequence requires modifying the agent that currently enqueues the next step — changes ripple through agent prompts and tool definitions.
- Con: Workflow state is implicit (reconstructed from RQ job history, not explicitly tracked).
- Con: Harder to audit or resume partial workflow runs.

**Why rejected for Robotina:** The project explicitly requires `reply_context` to stay out of intermediate task inputs. The centralized orchestrator pattern enforces this structurally — no discipline required.

### Pattern 3: LLMBackend Protocol Abstraction

**What:** Define a Python Protocol for the LLM integration surface. Concrete adapters implement this protocol. The Task Runner and agents import only the Protocol type.

**When to use:** When multiple LLM providers must be supported and per-task-type provider selection is required.

**Trade-offs:**
- Pro: Swap providers per task type or at experiment time without changing agent code.
- Pro: Protocol is mockable in tests.
- Con: Thin abstraction — if a provider requires non-standard initialization or has novel tool-calling semantics, the adapter must handle impedance mismatch.

```python
@runtime_checkable
class LLMBackend(Protocol):
    @property
    def model(self) -> BaseChatModel: ...

    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
    ) -> Any: ...
```

The adapter factory is invoked once per agent dispatch by reading `agents.py` config and instantiating the matching adapter class. Each agent run holds its own `LLMBackend` instance — no shared state between concurrent (or sequential) runs.

### Pattern 4: Skill Lazy Loading

**What:** Each skill's `index.md` is pre-loaded into the agent's system prompt at startup. Sub-files are fetched on demand via the `read-skill` tool when the agent determines it needs deeper detail.

**When to use:** Any time skill content is large relative to what a specific task actually needs.

**Trade-offs:**
- Pro: Agent starts with awareness of all available skills and their sub-file map. Can decide what to load.
- Pro: Context window stays lean for tasks that only need overview-level knowledge.
- Con: Requires agents to invoke `read-skill` explicitly, adding one round-trip per sub-file needed.

## Data Flow

### Flow 1: Direct Reply (Question about household)

```
User (Telegram)
    │ message
    ▼
Gateway
    │ persist message, fetch history
    │ enqueue handle-incoming-message {message_id, text, history, ...}
    ▼
agent-tasks queue (Redis)
    │ job dequeued
    ▼
Task Runner
    │ no WorkflowRunStep found → pure job, no workflow hook
    │ lookup agents.py → load prompt, tools=[HM-api, queue], skills=[HM]
    ▼
handle-incoming-message Agent (LangChain)
    │ tool call: household-manager-api → GET /api/...
    │ tool call: queue → enqueue send-notification {chat_id, text}
    ▼
agent-tasks queue (Redis)
    │ job dequeued
    ▼
Task Runner → send-notification Agent
    │ skill: format-telegram-message
    │ tool call: send-notification → Gateway → Telegram
    ▼
User (Telegram reply)
    │
    ▼
Gateway persists outgoing message to Postgres
```

### Flow 2: Multi-Step Workflow (Research and add recipe)

```
User (Telegram)
    │ "add carbonara"
    ▼
Gateway → enqueue handle-incoming-message
    ▼
Task Runner → handle-incoming-message Agent
    │ tool call: start-workflow "add-recipe"
    │   - Creates WorkflowRun {type="add-recipe", shared_context={query, household_id, reply_context}}
    │   - Creates WorkflowRunStep for each step (all PENDING)
    │   - Enqueues recipe-research {query, household_id}
    │   - Sets WorkflowRunStep[research].task_job_id = RQ job ID
    │   - Returns workflow_run_id
    ▼
agent-tasks queue: recipe-research job
    ▼
Task Runner (pre-hook): lookup WorkflowRunStep by job ID → mark RUNNING
    ▼
recipe-research Agent
    │ tool call: web-search (Tavily) → recipe data
    │ returns RecipeResearchOutput {recipe: RecipeData}
    ▼
Task Runner (post-hook):
    │ persist artifact to WorkflowRunStep[research].artifact
    │ mark step DONE
    │ build_input("load", shared_context, accumulated_artifacts)
    │ enqueue recipe-load {recipe: RecipeData, household_id}
    ▼
agent-tasks queue: recipe-load job
    ▼
Task Runner (pre-hook): mark WorkflowRunStep[load] RUNNING
    ▼
recipe-load Agent
    │ tool call: household-manager-api → resolve food/unit names → POST /api/recipes
    │ returns RecipeLoadOutput {recipe_id, recipe_name}
    ▼
Task Runner (post-hook):
    │ persist artifact to WorkflowRunStep[load].artifact
    │ build_input("notify", shared_context, accumulated_artifacts)
    │   - resolves reply_context from shared_context (only here, not in prior steps)
    │   - text = "Recipe added: {recipe_name}"
    │ enqueue send-notification {platform, chat_id, user_id, text}
    ▼
send-notification Agent → Gateway → Telegram → User
    ▼
Task Runner (post-hook): mark WorkflowRun DONE
```

### Flow 3: Workflow Failure

```
Task Runner (post-hook on failure):
    │ mark WorkflowRunStep[current] FAILED
    │ mark all PENDING steps CANCELLED
    │ mark WorkflowRun FAILED
    │ failed RQ job retained in RQ failed registry
    ▼
(No automatic retry. Developer inspects via RQ Dashboard.)
```

### Key Data Flow Rules

1. **reply_context never passes through intermediate task inputs.** It lives in `WorkflowRun.shared_context` and is injected only by the Task Runner when building `send-notification` input at the final step.
2. **RecipeData flows via artifacts, not via RecipeLoadInput.** The Task Runner reads `artifacts["research"]["recipe"]` and injects it when building the load step input. The recipe-load agent receives it as its input — it does not reach back into the workflow store.
3. **Agents never know their workflow membership.** They receive a typed input, produce a typed output, and return. No `workflow_run_id` appears in any task input model.
4. **Workflow link is established by job ID.** `start-workflow` stores the first step's RQ job ID in `WorkflowRunStep.task_job_id`. Task Runner resolves this on job pickup to find the associated step record.

## Build Order Dependencies

The components form a strict dependency chain. Building out of order creates integration dead-ends.

```
Level 0 (no dependencies):
    Developer tooling (Docker Compose: Postgres + Redis, uv project)

Level 1 (depends on Level 0 infrastructure):
    DB layer: SQLAlchemy Base, Alembic setup, Conversation/StoredMessage models
    Queue layer: Redis connection, Pydantic task input/output models, RQ basics

Level 2 (depends on Level 1):
    Gateway: depends on Postgres (Conversation model) and Redis (queue enqueue)
    LLM module: depends on nothing except LangChain — buildable in parallel with Gateway
    Task Runner scaffold: depends on Redis (queue consumer) — agent dispatch stubbed

Level 3 (depends on Level 2):
    Workflow infrastructure: depends on DB (WorkflowRun/Step models) and Task Runner scaffold
    Agent infrastructure: depends on LLM module, queue models, skill loading

Level 4 (depends on Level 3):
    Individual agents: each depends on agent infrastructure + their tools + skills
    First agent to build: send-notification (simplest — no workflow, no HM API)
    Second: handle-incoming-message (triggers others, but can be built before they exist)
    Third: recipe-research (needs web-search tool)
    Fourth: recipe-load (needs HM API tool + recipe-load skill)

Level 5 (depends on Level 4):
    Scheduler: depends on Redis, queue models; can be deferred until after agents work
    End-to-end integration: all agents + workflow infrastructure in place
```

**Critical path:** Developer tooling → DB + Queue layer → Gateway + LLM module → Task Runner + Workflow infrastructure → Agent infrastructure → Individual agents → Integration.

**Why Gateway before agents:** Gateway is the trigger for all work. Building it first allows Telegram → queue integration to be validated before any agent logic exists (the enqueued job can initially be a no-op).

**Why send-notification first among agents:** It has no workflow dependency and no household-manager-api dependency. It validates the full agent execution path (LLMBackend, prompt loading, skill loading, tool dispatch) before the more complex agents are built.

## Integration Points

### External Services

| Service | Integration Pattern | Component | Notes |
|---------|---------------------|-----------|-------|
| Telegram | Long-polling or webhook via python-telegram-bot | Gateway | Deduplication via `platform_message_id` unique constraint |
| Household Manager API | REST, `Authorization: Bearer` header injected by `household-manager-api` tool | Agent tool | 401/403 = hard error, not passed to LLM. Single shared API key in Phase 1. |
| Tavily | REST via `web-search` tool | recipe-research agent | API key from env var |
| Ollama | LangChain ChatOllama via HTTP | LLMBackend adapter | Local or remote; full URL in config |
| Anthropic | LangChain ChatAnthropic | LLMBackend adapter | API token per task type from env var |
| OpenAI | LangChain ChatOpenAI | LLMBackend adapter | API token per task type from env var |
| LangWatch | OTel SDK, direct push (no collector) | All agents | Endpoint + API key from env vars; active in both production and experiment runs |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Gateway ↔ Queue | `rq.Queue.enqueue()` call | Gateway imports Queue connection; one-way |
| Task Runner ↔ Workflow Engine | Function call (inline, same process) | Workflow engine is not a separate service; it is logic embedded in the task runner job lifecycle |
| Task Runner ↔ agents.py | Python module import + dict lookup by task type | Runtime override: JSON file at `AGENT_OVERRIDES_FILEPATH` |
| Task Runner ↔ workflows.py | Python module import + dict lookup by workflow type | WORKFLOW_REGISTRY is a module-level dict |
| Agent ↔ LLMBackend | Protocol method calls: `backend.model`, `backend.create_agent()` | Adapter is instantiated per agent run; no shared state |
| Agent ↔ Tools | LangChain tool invocation | Tools are injected at agent creation; error recovery is agent-side |
| Scheduler Worker ↔ agent-tasks queue | `rq.Queue.enqueue()` after scheduled job fires | Strips scheduling metadata; enqueues base task input |
| Scheduler API ↔ scheduled-tasks queue | `rq.Queue.enqueue_at()` or `enqueue_job_at()` | Bearer token auth at API layer |

## Centralized Orchestrator vs Agent-Chaining: Decision Rationale

| Concern | Centralized Orchestrator | Agent-Chaining |
|---------|--------------------------|----------------|
| reply_context isolation | Enforced structurally — never in task inputs | Requires discipline; leaks naturally |
| Adding workflow steps | Add `WorkflowStepDef` in workflows.py only | Modify the agent that currently enqueues next step |
| Agent testability | Agent ignorant of sequence — pure input → output | Agent must be tested with sequence context |
| Workflow state visibility | Explicit: Postgres WorkflowRun/Step rows | Implicit: reconstruct from RQ job history |
| Failure propagation | Centralized: Task Runner marks remaining steps CANCELLED | Distributed: must be built into each agent |
| Complexity location | Task Runner hook logic | Each participating agent |

**Verdict:** Centralized orchestrator is the correct choice for this system. The isolation of `reply_context` and the clean `build_input` callables in `WorkflowStepDef` are the primary structural advantages. The main cost is that `task_runner.py` is now a load-bearing component; bugs there affect all workflow jobs. This is acceptable because it is well-bounded and fully testable.

## Anti-Patterns

### Anti-Pattern 1: Agents Self-Advancing Workflows

**What people do:** The recipe-research agent, upon completing, calls `queue.enqueue("recipe-load", ...)` directly, including `reply_context` in the payload.

**Why it's wrong:** Couples agent to sequence. `reply_context` leaks into intermediate inputs. Adding or removing steps requires changing agent code. Workflow state is invisible.

**Do this instead:** Use the centralized Task Runner advancement hook. Agents return their output model; the Task Runner handles everything else.

### Anti-Pattern 2: reply_context in Intermediate Task Inputs

**What people do:** Add `reply_context: ReplyContext` fields to `RecipeResearchInput` and `RecipeLoadInput` so the final step can always find it.

**Why it's wrong:** These agents have no logical need to know who triggered the request. It creates artificial coupling between the messaging layer (Telegram) and domain task agents. It also means every time the reply mechanism changes, all intermediate input models must change.

**Do this instead:** Store `reply_context` once in `WorkflowRun.shared_context` at workflow creation. The Task Runner injects it when building the `send-notification` input at the final step only.

### Anti-Pattern 3: Importing WorkflowRun Models in Agent Code

**What people do:** Agents read from `WorkflowRun` directly to check their position in the sequence or fetch prior artifacts.

**Why it's wrong:** Agents gain awareness of the workflow system. The clean separation between "agent does its task" and "task runner manages sequence" collapses.

**Do this instead:** Build all necessary context into the task input model. The Task Runner's `build_input` callables pull from `shared_context` and `accumulated_artifacts` and materialize everything the agent needs into its typed input before enqueueing.

### Anti-Pattern 4: Global/Shared LLMBackend Instance

**What people do:** Instantiate one `LLMBackend` at module load and share it across agent runs.

**Why it's wrong:** Different task types must use different LLM configs (different models, API keys, base URLs). A shared instance means all task types use the same model. It also creates potential state contamination between sequential runs.

**Do this instead:** Instantiate a fresh `LLMBackend` adapter per agent dispatch, reading config from `agents.py` by task type.

### Anti-Pattern 5: Implicit Queue Coupling via Module-Level Connection

**What people do:** Multiple modules call `redis.Redis()` with hardcoded connection details at import time.

**Why it's wrong:** Breaks testability (cannot inject mock Redis). Makes connection configuration inconsistent across modules.

**Do this instead:** Create a single `connection.py` factory in the `queue/` module. All components that need Redis import the factory and call it to get a connection.

## Scaling Considerations

This system is designed for a single household (concurrency=1 is an intentional constraint, not a limitation). Scaling is out of scope for Phase 1.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Single household (Phase 1) | Sequential worker (concurrency=1), single Redis, single Postgres instance — correct by design |
| Multiple households (future) | Introduce per-household queues or a queue-per-household routing layer; `household_id` field is already on all models |
| Higher throughput | Increase concurrency only if sequential constraint is lifted; consider separate queues per task type priority |

**First bottleneck if scaling is needed:** The sequential worker. RQ supports increasing concurrency trivially (`rq worker --concurrency N`), but this would require reviewing the "exactly one agent at a time" constraint.

## Sources

- Project spec: `/plans/01-kickoff/spec.md` (HIGH confidence — authoritative, fully prescriptive)
- Project context: `/.planning/PROJECT.md` (HIGH confidence — authoritative)
- Architectural diagrams: `/plans/01-kickoff/layers.png`, `/plans/01-kickoff/components.png` (HIGH confidence — first-party)
- RQ documentation (training data, MEDIUM confidence): sequential worker, failed job registry, `result_ttl`, `at_front` parameter, `--with-scheduler` flag all match documented RQ 2.x behavior
- LangChain Protocol pattern (training data, MEDIUM confidence): `BaseChatModel`, `BaseTool`, `create_react_agent` are stable LangChain Core APIs as of LangChain 0.2+

---
*Architecture research for: Robotina — Python AI agent system with task queue and workflow orchestration*
*Researched: 2026-03-25*
