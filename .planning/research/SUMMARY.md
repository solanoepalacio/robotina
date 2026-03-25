# Project Research Summary

**Project:** Robotina — Python AI home assistant agent
**Domain:** Telegram-triggered AI agent with task queue, multi-step workflow orchestration, and LLM observability
**Researched:** 2026-03-25
**Confidence:** HIGH (spec is fully authoritative; stack versions MEDIUM due to knowledge cutoff)

## Executive Summary

Robotina is a household AI assistant that receives natural-language requests via Telegram, processes them through a durable task queue backed by Redis and RQ, and executes multi-step workflows using specialized LangChain/LangGraph agents persisted in Postgres. The recommended approach is a centralized orchestrator pattern: a single task runner manages all workflow state transitions while individual agents remain ignorant of sequence logic. This separation is non-negotiable — it enforces that Telegram-specific context (`reply_context`) never leaks into domain agents, and it allows workflow steps to be added, removed, or reordered by modifying only `workflows.py`. Agents are pure input-to-output functions dispatched by task type, with LLM provider, prompt, tools, and skills configured per-task-type in `agents.py`.

The two primary user stories driving Phase 1 are: (1) answer household questions in real time, and (2) research and add a recipe end-to-end. Both require the full pipeline — gateway, queue, task runner, workflow engine, and at minimum four specialized agents — to be in place before either delivers value. The architecture research specifies a strict build order: infrastructure (Docker Compose, DB, queue) first, then gateway and LLM module in parallel, then workflow engine, then agents in order of increasing complexity (send-notification first, handle-incoming-message second, recipe-research third, recipe-load fourth). Building out of this order creates dead ends.

The critical risks are: (1) transactional consistency between Redis job enqueue and Postgres workflow state updates — a crash between these two operations leaves the workflow in an irrecoverable state; (2) LangChain tool exceptions being silently swallowed by the agent loop, causing unrecoverable errors to appear recoverable; and (3) Telegram webhook re-delivery creating duplicate agent executions. All three must be prevented architecturally from the first implementation — they cannot be retrofitted cleanly.

## Key Findings

### Recommended Stack

The stack is almost entirely specified by the project spec and is non-negotiable. Python 3.12 with uv for project management, LangChain 0.3+ with LangGraph `create_react_agent` (the deprecated `AgentExecutor` must not be used), RQ 2.5+ with native scheduler (the `rq-scheduler` add-on is superseded), Redis 7 with AOF persistence (`appendfsync always`), PostgreSQL 15 with SQLAlchemy 2.x (`Mapped`/`mapped_column` syntax required), and Alembic for migrations. Pydantic v2 is used everywhere — LangChain 0.3 dropped v1 support entirely, and mixing versions causes silent serialization bugs.

LLM provider flexibility is built in via the `LLMBackend` Protocol: Anthropic (`langchain-anthropic`), OpenAI (`langchain-openai`), and Ollama (`langchain-ollama`) adapters are all supported with per-task-type configuration. LangWatch + OpenTelemetry SDK is the mandatory observability layer, active in both production and experiment runs. FastAPI powers the scheduler HTTP API, `python-telegram-bot` v21 (async-native) handles the gateway, and `tavily-python` provides web search for the recipe-research agent.

**Core technologies:**
- Python 3.12 + uv: runtime and project management — `uv run` shortcuts replace Make targets
- LangGraph `create_react_agent`: agent execution — `AgentExecutor` is deprecated, must not be used
- RQ 2.5 + Redis 7 (AOF): task queue and scheduler — native scheduler eliminates the `rq-scheduler` add-on
- PostgreSQL 15 + SQLAlchemy 2.x + Alembic: persistence — `Mapped`/`mapped_column` syntax required throughout
- Pydantic v2: all task input/output models — no v1 code anywhere in the project
- LangWatch + OTel SDK: observability — must be active in both production and experiment scripts
- python-telegram-bot v21: gateway — async-native; v13.x sync patterns must not be used
- FastAPI + httpx: scheduler API and async HTTP client

### Expected Features

The spec fully defines all Phase 1 features. All 13 table-stakes features must be present before either user story delivers value. The most architecturally significant is the workflow step isolation requirement: intermediate agents (`recipe-research`, `recipe-load`) must never receive `reply_context`, which belongs to Telegram and not to domain logic. This is enforced by storing `reply_context` in `WorkflowRun.shared_context` and injecting it only when building the `send-notification` input.

**Must have (table stakes):**
- Telegram message receive, persist, and deduplicate — entry point; duplicates cause double side effects
- Redis + RQ task queue (AOF persistence, single worker, concurrency=1) — backbone; nothing works without it
- `handle-incoming-message` agent — intent routing and direct answer or workflow initiation
- `send-notification` agent + `format-telegram-message` skill — closes the user feedback loop; Telegram MarkdownV2 is unforgiving
- `household-manager-api` tool with hard auth error handling — connects agents to household data
- `start-workflow` tool + `WorkflowRun`/`WorkflowRunStep` models + task runner advancement hook — the orchestration layer
- `recipe-research` agent (Tavily) + `recipe-load` agent (name→ID resolution) — the primary workflow capability
- LangWatch + OTel instrumentation on all agents — debugging LLM failures requires traces
- Prompt versioning (versioned markdown files + `AGENT_OVERRIDES_FILEPATH` runtime override) — iterate without redeploy

**Should have (competitive):**
- Centralized workflow orchestration via `WorkflowDefinition` registry in `workflows.py` — keeps agents dumb and reusable; adding a step requires only a new `WorkflowStepDef`
- Accumulated artifacts pattern — each step's output persisted independently; enables clean data flow without coupling
- Per-task LLM configuration — route cheap tasks to local Ollama, expensive to frontier APIs; cost optimization without architectural change
- Experiment scripts per agent type (3 scripts) — evaluate prompt quality without end-to-end testing
- User message enqueued at front of queue (`at_front=True`) — real-time messages never wait behind background tasks
- Immediate acknowledgement message when starting a multi-step workflow — prevents 30-60 second user silence

**Defer (v2+):**
- Multi-household support — `household_id` field exists as a shim; implement only after single-household model is validated
- Scheduler worker + API — infrastructure exists but add only when proactive/recurring tasks are explicitly needed
- Streaming responses — Telegram streaming complexity not justified for household assistant latency requirements
- Conversation-level memory (summarization, embeddings) — window-based history is sufficient for Phase 1

### Architecture Approach

The system is structured as five distinct layers: ingress (Gateway + Scheduler API), queue (Redis agent-tasks and scheduled-tasks queues), task runner with embedded workflow engine (concurrency=1), agent layer (four specialized agents), and persistence (Postgres + Redis). The task runner is the critical coupling point — it is the only component that connects queue consumption to workflow advancement and agent dispatch. The workflow engine is embedded in the task runner as pre/post-job hooks, not a separate service. This keeps the system simple at the cost of making `task_runner.py` a load-bearing file that must be correct.

**Major components:**
1. Gateway — receives Telegram webhooks, persists messages with deduplication, fetches conversation history, enqueues tasks at front of queue
2. Task Runner (concurrency=1) — sole consumer of agent-tasks queue; dispatches agents; wraps job lifecycle with workflow advancement hooks; persists step artifacts; enqueues next steps
3. Workflow Engine (embedded in Task Runner) — reads `WORKFLOW_REGISTRY` from `workflows.py`; advances workflow state; resolves `reply_context` from `shared_context` only at the send-notification step
4. Agent layer (4 agents) — each is a pure typed-input to typed-output function; no workflow awareness; LLMBackend, prompt, tools, and skills configured per-task-type in `agents.py`
5. Scheduler API + Scheduler Worker — separate FastAPI HTTP API for creating scheduled tasks; separate RQ worker process with `--with-scheduler`; fires into agent-tasks queue on schedule

### Critical Pitfalls

1. **Workflow advancement race between Redis enqueue and Postgres commit** — Enqueue the next RQ job before committing the Postgres transaction; use a pre-assigned deterministic job ID; write that ID to `WorkflowRunStep.task_job_id` in the same commit. Never commit `DONE` status without also having written the next step's `task_job_id`.

2. **LangChain tool exceptions swallowed by the agent loop** — `create_react_agent` catches tool exceptions and returns them as string observations by default, turning unrecoverable errors (401/403) into retry loops. Use `ToolException` with `handle_tool_error=False` for hard errors; define explicit recoverable vs. unrecoverable error categories in all tool wrappers before writing any domain tool.

3. **RQ job args must be Pydantic-only — no ORM objects** — Never pass SQLAlchemy model instances or session objects as RQ job args. Serialize to `.model_dump()` at the call site; deserialize with `Model.model_validate()` inside the job function. Test all task types for round-trip pickle serialization before writing any agent.

4. **Telegram duplicate webhook delivery** — Telegram retries on non-200 or timeout. Use `INSERT ... ON CONFLICT DO NOTHING RETURNING` on `StoredMessage`; skip enqueue if no row returned. Always return 200 to Telegram even on internal errors; handle failures asynchronously.

5. **Agent state leaks between sequential RQ jobs** — All per-job objects (LLM client, callbacks, agent, skills) must be instantiated inside the job function, never at module level. LangWatch spans must be opened and closed within job function scope. Verify with a two-job sequential integration test.

6. **Shared context mutation corrupts downstream workflow steps** — Pass a deep copy of `shared_context` to `build_input` callables, or freeze it as `MappingProxyType`. The `build_input` contract is: pure function, reads inputs, returns a new model, never mutates arguments.

7. **Alembic autogenerate misses enum type changes** — Set `compare_type=True` in Alembic's `env.py` before the first migration. `ALTER TYPE ... ADD VALUE` cannot run inside a Postgres transaction; handle this explicitly in any migration that adds enum values.

## Implications for Roadmap

Based on the architecture build order dependencies and pitfall-to-phase mapping, the following phase structure is recommended:

### Phase 1: Developer Tooling and Infrastructure

**Rationale:** Nothing else can be built without Redis, Postgres, and the project scaffold. This phase has no dependencies and unblocks everything. Zero risk of wasted work — these choices are fully specified.

**Delivers:** Docker Compose (Postgres 15 + Redis 7), uv project with `pyproject.toml` scripts (`uv run agent`, `uv run migrate`), Alembic setup with `compare_type=True` in `env.py`, base SQLAlchemy `Base`, Redis connection factory in `queue/connection.py`.

**Addresses:** Table stakes — Redis AOF persistence, project scaffold, migration foundation.

**Avoids:** Alembic enum mutation pitfall (set `compare_type=True` from day one); implicit queue coupling pitfall (single Redis connection factory from day one).

### Phase 2: Database Models and Queue Layer

**Rationale:** DB models and Pydantic task models are the shared contract between all subsequent components. Building these before gateway or agents prevents data model churn. Task model serialization must be verified before any agent is wired up.

**Delivers:** All SQLAlchemy models (`Conversation`, `StoredMessage`, `WorkflowRun`, `WorkflowRunStep`) with Alembic migrations; all Pydantic task input/output models (`IncomingMessageInput`, `RecipeResearchInput`, `RecipeLoadInput`, `SendNotificationInput`); RQ basics with serialization test for all task types.

**Addresses:** Table stakes — task queue contracts, workflow state persistence.

**Avoids:** RQ job serialization pitfall (verify all task types pickle cleanly before any agent work begins); shared context mutation pitfall (define typed `SharedContext` Pydantic model instead of raw dict string literals).

### Phase 3: Gateway

**Rationale:** Gateway is the trigger for all user-facing work. Building it before any agent exists allows Telegram-to-queue integration to be validated with a no-op job handler. Deduplication and idempotency must be built in from the start.

**Delivers:** Telegram bot (`python-telegram-bot` v21) receiving messages, persisting to Postgres with `INSERT ... ON CONFLICT DO NOTHING` deduplication, fetching bounded conversation history, enqueuing `handle-incoming-message` at front of queue. Returns 200 to Telegram on all outcomes.

**Addresses:** Table stakes — message receipt, deduplication, conversation persistence.

**Avoids:** Telegram duplicate webhook pitfall (idempotency at enqueue time, not just storage); conversation history unbounded growth pitfall (cap history with configurable `LIMIT`).

### Phase 4: LLM Module and Agent Infrastructure

**Rationale:** The LLM module and base agent runner have no dependency on specific domain logic. Building these in a general form before any domain agent prevents copy-paste patterns and establishes the scoping rules (module-level vs. job-level instantiation) that must hold for all agents.

**Delivers:** `LLMBackend` Protocol in `llm/protocol.py`; Ollama, Anthropic, OpenAI adapters; base agent runner with per-job object instantiation; tool error handling policy (recoverable vs. unrecoverable exception categories); `agents.py` config registry structure; `AGENT_OVERRIDES_FILEPATH` runtime override support; LangWatch + OTel initialization (called once at process startup).

**Addresses:** Table stakes — LLM provider abstraction, per-task-type system prompts, skill lazy loading, LangWatch instrumentation.

**Avoids:** LangChain tool exception swallowing pitfall; agent state leaks between sequential jobs pitfall; LangWatch trace context lost across RQ boundaries pitfall (trace propagation strategy must be decided here before multi-agent workflow is wired up).

### Phase 5: Task Runner and Workflow Infrastructure

**Rationale:** The task runner is the most complex and load-bearing component. It couples queue consumption, workflow state management, artifact persistence, and next-step enqueueing. It must be solid and tested before any domain workflow runs through it. Transactional advancement logic is the critical correctness requirement.

**Delivers:** Task runner with `concurrency=1` RQ worker; pre/post-job workflow hooks; `WorkflowRunStep` status transitions (`PENDING` → `RUNNING` → `DONE`/`FAILED`); artifact persistence; `accumulated_artifacts` accumulation; `workflows.py` registry with `WorkflowDefinition` and `WorkflowStepDef`; `advance_workflow` function with transactional enqueue-then-commit logic; workflow failure propagation (marks remaining `PENDING` steps `CANCELLED`, marks `WorkflowRun` `FAILED`); `build_input` callables receiving deep-copied `shared_context`.

**Addresses:** Table stakes — workflow step isolation, failure propagation, dead letter queue retention.

**Avoids:** Workflow advancement race condition pitfall (enqueue before commit, pre-assigned job ID); shared context mutation pitfall (deep copy enforced in task runner).

### Phase 6: send-notification Agent

**Rationale:** The simplest agent — no workflow dependency, no household-manager API, no Tavily. It validates the full agent execution path (LLMBackend instantiation, prompt loading, skill loading, tool dispatch, LangWatch trace) before any complexity is added. Telegram MarkdownV2 formatting must be validated here via an experiment script before the full workflow is wired.

**Delivers:** `send-notification` agent with `format-telegram-message` skill; `send-notification` tool in gateway; agent experiment script with LangWatch trace verification; Telegram MarkdownV2 escaping validated with representative messages including bold, lists, and links.

**Addresses:** Table stakes — Telegram-safe message formatting, agent-responds-to-user loop closure.

**Avoids:** Telegram formatting silent rejection (test before wiring full workflow); LangWatch orphaned traces (verify traces link correctly).

### Phase 7: handle-incoming-message Agent

**Rationale:** The routing brain of the system. Can be built before recipe agents exist — it can acknowledge intent and route to a not-yet-built workflow. Validates that the gateway-to-agent-to-user loop works end-to-end for the direct-reply user story.

**Delivers:** `handle-incoming-message` agent with `household-manager-api` tool, `queue` tool for enqueuing `send-notification`, `start-workflow` tool creating `WorkflowRun` + steps; agent experiment script. End-to-end direct-reply user story works after this phase.

**Addresses:** Table stakes — intent routing, household-manager API integration, `start-workflow` tool, `WorkflowRun` creation.

**Avoids:** 401/403 hard error handling (must be verified before wiring to real household-manager API).

### Phase 8: recipe-research Agent

**Rationale:** Adds the research capability needed for the add-recipe workflow. Depends on the Tavily web search tool and `RecipeData` model defined in Phase 2. The workflow infrastructure from Phase 5 enables step execution without the load agent existing yet.

**Delivers:** `recipe-research` agent with `web-search` (Tavily, `max_results` bounded) tool, `RecipeData` structured output, `source_url` attribution; agent experiment script with LangWatch trace; `recipe-research` skill files.

**Addresses:** Table stakes — web search recipe research, structured `RecipeData` output.

**Avoids:** Tavily `max_results` unbounded context inflation; Telegram context not present in research input.

### Phase 9: recipe-load Agent and End-to-End Integration

**Rationale:** The most complex agent — requires household-manager API name-to-ID resolution, graceful handling of partial and zero matches, and integration with the accumulated artifacts from recipe-research. This is the last piece for the add-recipe user story to work end-to-end.

**Delivers:** `recipe-load` agent with `household-manager-api` tool for name→ID resolution (`/api/foods?name=`, `/api/units?name=`), graceful partial/zero match handling, `POST /api/recipes` creation; `recipe-load` skill files; agent experiment script; full add-recipe workflow integration test.

**Addresses:** Table stakes — food/unit name resolution, recipe creation, full add-recipe workflow end-to-end.

**Avoids:** Ambiguous name matching (case-insensitive substring match with specific enough query terms); 401/403 propagated to LLM as recoverable signal (enforce hard error).

### Phase 10: Scheduler Worker and API (P2)

**Rationale:** Defer until Phase 1 user stories are validated. The two-worker architecture (scheduler-worker with `--with-scheduler`, task-runner without) is already designed; this phase implements the HTTP API and wires the separate worker process.

**Delivers:** FastAPI scheduler API with `POST/GET/DELETE /api/scheduled-tasks` and Bearer auth; `ScheduledTask` Pydantic model; `scheduler-worker` entry point; `rq.Queue.enqueue_at()` integration.

**Addresses:** Differentiator — separate scheduler worker keeps scheduled tasks from blocking real-time agent processing.

**Avoids:** Two schedulers in one project (uses RQ 2.5 native scheduler only; `rq-scheduler` add-on not used).

### Phase Ordering Rationale

- Infrastructure before everything: Docker Compose, uv, Alembic setup have no dependencies and unblock all subsequent phases.
- DB models and queue models before gateway or agents: these are the shared contracts; changing them later causes cascade rework.
- Gateway before agents: validates Telegram-to-queue integration; the enqueued job can be a no-op until agents exist.
- LLM module and agent infrastructure before any specific agent: establishes scoping rules and tool error policy that must hold for all agents; cannot be retrofitted.
- Task runner and workflow infrastructure before domain agents: workflow advancement logic must be solid and tested before any workflow-dependent agent runs through it.
- send-notification first among agents: simplest path through the agent execution system; validates LLMBackend, prompts, skills, LangWatch, and Telegram delivery before complexity is added.
- handle-incoming-message second: closes the direct-reply user story and validates the start-workflow tool before recipe agents exist.
- recipe-research before recipe-load: research produces `RecipeData`; load consumes it; strict dependency.
- Scheduler last: infrastructure designed for it; defer until core user stories are validated.

### Research Flags

Phases with standard, well-documented patterns (research-phase likely not needed):
- **Phase 1 (Infrastructure):** Docker Compose, uv, Alembic are fully specified and well-documented.
- **Phase 2 (DB + Queue models):** SQLAlchemy 2.x `Mapped` syntax and Pydantic v2 models are stable, fully specified by the spec.
- **Phase 3 (Gateway):** `python-telegram-bot` v21 patterns are well-documented; webhook handler is a standard pattern.
- **Phase 6 (send-notification):** Simplest agent; no novel integration points.

Phases likely to benefit from deeper research during planning:
- **Phase 4 (Agent Infrastructure):** LangWatch SDK API surface may have evolved since training cutoff (LOW confidence in STACK.md). Verify initialization and OTel trace propagation patterns against official LangWatch docs before implementation.
- **Phase 5 (Task Runner + Workflow):** Transactional enqueue-before-commit pattern with pre-assigned RQ job IDs is the key correctness decision. Verify RQ's `job_id` parameter behavior and any edge cases with the version of RQ used.
- **Phase 7 (handle-incoming-message):** `start-workflow` tool integration with `WorkflowRun` creation is the first end-to-end test of workflow infrastructure. Plan for integration debugging time.
- **Phase 9 (recipe-load + Integration):** Household-manager API name resolution behavior (case-insensitive substring match, partial/zero match handling) needs validation against the actual API before the agent is written.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Technology choices are HIGH confidence (spec-specified, well-documented). Exact version numbers are MEDIUM — verified as conservative lower bounds from training data (Aug 2025 cutoff); run `uv add <package>` at install time to resolve to actual latest. LangWatch SDK specifically is LOW — newer product, API may have evolved. |
| Features | HIGH | Derived directly from the authoritative spec and existing skill implementation files. All table-stakes features, differentiators, and defer decisions are fully specified. No ambiguity. |
| Architecture | HIGH | Spec is fully prescriptive. Centralized orchestrator pattern, data flow rules, component boundaries, and build order are all explicitly defined in spec + architecture diagrams. |
| Pitfalls | HIGH (spec-driven) / MEDIUM (library-specific) | Spec-derived pitfalls (transactional advancement, tool error handling, `reply_context` isolation) are HIGH confidence. Library-specific behaviors (LangGraph exception handling, OTel propagation across RQ boundaries, Alembic enum handling) are MEDIUM — consistent with documented behavior but not verified against live systems. |

**Overall confidence:** HIGH

### Gaps to Address

- **LangWatch SDK initialization and OTel trace propagation API:** Verify official LangWatch documentation for Python SDK initialization pattern, span lifecycle in RQ worker processes, and cross-process W3C `traceparent` propagation before starting Phase 4. Training knowledge on LangWatch is LOW confidence.
- **RQ `job_id` parameter behavior for pre-assigned IDs:** Confirm that `queue.enqueue(func, job_id=predetermined_id, ...)` works as expected in the RQ version used, and that a pre-assigned ID prevents duplicate job registration if the same ID is reused after a crash recovery. Verify before implementing Phase 5 transactional advancement.
- **Household-manager API actual endpoint behavior:** The `GET /api/foods?name=` case-insensitive substring match behavior is described in the spec but should be verified against the real API before recipe-load agent implementation (Phase 9). Edge cases (zero matches, multiple ambiguous matches) need concrete handling strategy.
- **python-telegram-bot v21 long-polling vs. webhook choice:** The spec does not dictate long-polling vs. webhook. For production, webhook is preferred (lower latency, no polling overhead). For development, long-polling is simpler (no public URL needed). This choice should be made explicit in Phase 3 and the gateway should support both modes via configuration.

## Sources

### Primary (HIGH confidence)
- `/plans/01-kickoff/spec.md` — Authoritative source for all technology choices, model definitions, agent behavior, tool contracts, and workflow structure
- `/agent/skills/household-manager/index.md` + `shared.md` — Existing skill implementation confirming household-manager API conventions
- `/.planning/PROJECT.md` — Project scope, constraints, out-of-scope decisions
- `/plans/01-kickoff/layers.png`, `/plans/01-kickoff/components.png` — First-party architecture diagrams

### Secondary (MEDIUM confidence)
- RQ 2.5 changelog and documentation (training data) — Native scheduler, `result_ttl`, `failure_ttl`, `at_front`, `--with-scheduler` flag, failed job registry behavior
- LangChain 0.2→0.3 migration guide (training data) — `create_react_agent` moved to `langgraph.prebuilt`; `AgentExecutor` deprecation
- SQLAlchemy 2.0 release notes (training data) — `Mapped`/`mapped_column` declarative API
- OpenTelemetry documentation (training data) — W3C `traceparent`, cross-process context propagation
- Alembic documentation (training data) — `compare_type=True`, Postgres `ALTER TYPE ... ADD VALUE` transaction restriction
- Telegram Bot API documentation (training data) — Webhook retry behavior, `update_id` deduplication, MarkdownV2 escape requirements

### Tertiary (LOW confidence)
- LangWatch SDK documentation (training data) — Initialization pattern, OTel integration surface; verify against official LangWatch docs before Phase 4 implementation

---
*Research completed: 2026-03-25*
*Ready for roadmap: yes*
