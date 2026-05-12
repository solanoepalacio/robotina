# Phase 7: handle-incoming-message Agent - Research

**Researched:** 2026-03-27
**Domain:** LangChain ReAct agent, HTTP tool implementation, RQ job injection, skill maintenance
**Confidence:** HIGH

## Summary

Phase 7 is the final wiring phase that makes Robotina a functional end-to-end system. All infrastructure is already in place from Phases 1-6: the agent runner (`run_task`), the skill loading system, the workflow engine (`StartWorkflowTool`), and the notification delivery path (`SendNotificationTool`). This phase adds exactly three new artifacts — `HouseholdManagerApiTool`, `QueueTool`, and `robotina/V001.md` — plus two registry/wiring changes (`agents.py` and `run_task()`) and one skill file rewrite (`shared.md`).

The implementation is straightforward extension of the patterns established in Phase 6. Both new tools follow the `BaseTool` subclass pattern with constructor injection, and both are injected per-job inside `run_task()`. The routing prompt (V001.md) is the design-sensitive deliverable: it must correctly calibrate the agent's routing decision between the `queue` tool path (direct-reply) and the `start-workflow` tool path (multi-step workflow) without leaking workflow key names.

The `household-manager-api` tool has one critical behavior: `401`/`403` responses must raise a `RuntimeError` that propagates out of the tool (stops the agent loop via exception), while all other non-2xx responses return a structured error dict for agent recovery. This hard-stop semantics is a spec requirement.

**Primary recommendation:** Implement both tools modeled directly on `SendNotificationTool` and `StartWorkflowTool` respectively. Wire `run_task()` with an `elif task_type == "handle-incoming-message"` block. Write the prompt last, after all mechanical wiring is verified.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 — QueueTool input interface:**
`QueueTool` takes `text: str` only. Hardcoded to enqueue `send-notification` task. Recipient context (`chat_id`, `user_id`, `platform`) injected at construction inside `run_task()`. Builds `SendNotificationInput` internally and enqueues to `agent-tasks` queue. Returns `job_id` string.

**D-02 — HouseholdManagerApiTool interface:**
Generic HTTP client: `_run(method: str, path: str, body: dict | None, query: dict | None)`. `household_id` injected at construction from `task_input.household_id`. Tool prepends `household_id` automatically where spec requires. API token from `HOUSEHOLD_MANAGER_API_KEY` env var (dedicated, not per-task-type). `401`/`403` → raise hard `RuntimeError`. All other non-2xx → return structured error dict to agent.

**D-03 — agents.py Registry:**
Register `handle-incoming-message` in `AGENT_REGISTRY` with: skills `["household-manager"]`, tools `[]` (all three tools injected per-job), prompt `src/robotina/agent/prompts/robotina/V001.md`, model config following same env-var pattern (`HANDLE_INCOMING_MESSAGE_API_TOKEN`).

**D-04 — run_task() wiring:**
For `task_type == "handle-incoming-message"`, inject:
1. `HouseholdManagerApiTool(household_id=task_input.household_id)` — constructed per-job
2. `QueueTool(chat_id=task_input.chat_id, user_id=task_input.user_id, platform=task_input.platform)` — constructed per-job
3. `StartWorkflowTool()` — already implemented, no per-job injection needed

**D-05 — Routing Prompt (robotina/V001.md):**
States general routing principle with concrete examples for each path. Direct-reply examples: "what's on the meal plan?", "find me a pasta recipe". Workflow examples: "add a recipe for spaghetti carbonara". Does NOT enumerate workflow names by key. Agent uses `start-workflow` tool description for available workflow types.

**D-06 — household-manager skill update:**
Full rewrite of `shared.md`. Remove: entire "Authentication" section, 401 and 403 rows from error table. Keep: Base URL convention, remaining error codes (400, 404, 422, 500) with meanings, pagination envelope. Other skill files unchanged.

### Claude's Discretion

- Exact `HouseholdManagerApiTool` field names and how `household_id` is applied per-request (path prefix, query param, or header — check actual household-manager API spec)
- Whether `QueueTool` returns just the job_id string or a more verbose confirmation
- Exact V001.md prompt wording, tone, and length
- Whether `IncomingMessageOutput` is explicitly constructed in `run_task()` or left as raw messages list for Phase 7

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ROBOT-01 | `handle-incoming-message` task type is handled by the Robotina agent | D-03: Register in AGENT_REGISTRY; D-04: inject tools in run_task() |
| ROBOT-02 | Robotina agent has `household-manager-api` tool (auth injected; 401/403 hard errors) | D-02: HouseholdManagerApiTool implementation; httpx async→sync bridge pattern from SendNotificationTool |
| ROBOT-03 | Robotina agent has `queue` tool (enqueue single follow-up task) | D-01: QueueTool implementation; enqueue pattern from gateway handler.py |
| ROBOT-04 | Robotina agent has `start-workflow` tool | StartWorkflowTool already exists in tools/start_workflow.py; just add to injection block |
| ROBOT-05 | `household-manager` skill updated (auth removed) | D-06: Rewrite shared.md; remove auth section and 401/403 rows |
| ROBOT-06 | `robotina/V001.md` system prompt exists | D-05: Create prompts/robotina/V001.md with routing principle and examples |
| ROBOT-07 | Agent correctly distinguishes direct-reply from workflow intent | D-05: Prompt design; tool descriptions disambiguate the two paths |
</phase_requirements>

## Standard Stack

### Core (already installed — no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langchain-core | `>=0.3` | `BaseTool` base class for new tools | Already in project; established pattern |
| httpx | `>=0.27` | Async HTTP client for `HouseholdManagerApiTool` | Already in project; project standard for async HTTP (see CLAUDE.md) |
| rq | `>=2.5` | `Queue` for `QueueTool` enqueue call | Already in project |
| redis | `>=5.0` | `Redis.from_url()` connection in `QueueTool` | Already in project |
| pydantic | `v2 (>=2.7)` | `SendNotificationInput` built inside `QueueTool` | Already in project |

**No new packages required for Phase 7.** All dependencies are already declared in `pyproject.toml`.

### Existing Code Assets (HIGH confidence — verified by direct file read)

| Asset | Location | Role in Phase 7 |
|-------|----------|-----------------|
| `StartWorkflowTool` | `src/robotina/agent/tools/start_workflow.py` | Wire into handle-incoming-message injection block — no changes needed |
| `SendNotificationTool` | `src/robotina/agent/tools/send_notification.py` | Template for `QueueTool` constructor injection pattern |
| `run_task()` Phase 6 block | `src/robotina/queue/jobs.py:104-110` | Template for `elif task_type == "handle-incoming-message"` block |
| `IncomingMessageInput` | `src/robotina/queue/task_types.py:69-77` | Has `chat_id`, `user_id`, `platform`, `household_id` — all fields needed for tool construction |
| `IncomingMessageOutput` | `src/robotina/queue/task_types.py:80-83` | `action`, `queued_task_ids`, `workflow_run_id` — output shape |
| `SendNotificationInput` | `src/robotina/queue/task_types.py:119-124` | Built inside `QueueTool._run()` |
| `household-manager/shared.md` | `src/robotina/agent/skills/household-manager/shared.md` | File to rewrite (remove auth section + 401/403 rows) |
| `household-manager/index.md` | `src/robotina/agent/skills/household-manager/index.md` | Check and update if auth references present (currently references `shared.md` for auth) |
| `AGENT_REGISTRY` | `src/robotina/agent/agents.py:51-65` | Add `handle-incoming-message` entry |
| Gateway enqueue pattern | `src/robotina/gateway/handler.py:117-125` | Shows how `at_front`, `meta={'task_type': ...}`, `result_ttl=-1`, `failure_ttl=-1` are set |

## Architecture Patterns

### Tool Construction Pattern (from Phase 6 — HIGH confidence)

```python
# Source: src/robotina/agent/tools/send_notification.py
class SendNotificationTool(BaseTool):
    name: str = "send-notification"
    description: str = "..."

    # Per-job state injected at construction
    chat_id: str
    user_id: str
    platform: str

    def _run(self, formatted_text: str) -> str:
        # asyncio.run() bridges sync BaseTool._run to async gateway
        result = asyncio.run(send_message(...))
        return f"Notification Successfully Delivered. Notification ID = {result.message_id}"

    async def _arun(self, formatted_text: str) -> str:
        return self._run(formatted_text)
```

### QueueTool Pattern (derived from SendNotificationTool + gateway enqueue)

```python
# New file: src/robotina/agent/tools/queue.py
class QueueTool(BaseTool):
    name: str = "queue"
    description: str = (
        "Enqueue a send-notification task to deliver a reply to the user. "
        "Use this when the user's request can be answered directly. "
        "Args: text (str) — the reply text to send."
    )

    # Per-job recipient context — agent never sees these
    chat_id: str
    user_id: str
    platform: str

    def _run(self, text: str) -> str:
        import os
        from redis import Redis
        from rq import Queue
        from robotina.queue.task_types import SendNotificationInput

        task_input = SendNotificationInput(
            platform=self.platform,
            chat_id=self.chat_id,
            user_id=self.user_id,
            text=text,
        )
        q = Queue(
            "agent-tasks",
            connection=Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379")),
        )
        job = q.enqueue(
            "robotina.queue.jobs.run_task",
            task_input,
            result_ttl=-1,
            failure_ttl=-1,
            meta={"task_type": "send-notification"},
        )
        return job.id  # caller uses to populate IncomingMessageOutput.queued_task_ids

    async def _arun(self, text: str) -> str:
        return self._run(text)
```

### HouseholdManagerApiTool Pattern

```python
# New file: src/robotina/agent/tools/household_manager_api.py
class HouseholdManagerApiTool(BaseTool):
    name: str = "household-manager-api"
    description: str = (
        "Call the household-manager REST API. "
        "Args: method (str) — HTTP method (GET/POST/PATCH/DELETE). "
        "path (str) — API path relative to base URL (e.g. /api/recipes). "
        "body (dict | None) — JSON request body. "
        "query (dict | None) — URL query parameters."
    )

    household_id: str  # injected at construction; applied per-request

    def _run(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        query: dict | None = None,
    ) -> dict | str:
        import os
        import asyncio
        import httpx

        api_key = os.environ["HOUSEHOLD_MANAGER_API_KEY"]
        base_url = os.environ.get("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")

        async def _call():
            async with httpx.AsyncClient() as client:
                resp = await client.request(
                    method=method.upper(),
                    url=f"{base_url}{path}",
                    headers={"Authorization": f"Bearer {api_key}"},
                    params=query,
                    json=body,
                )
                if resp.status_code in (401, 403):
                    raise RuntimeError(
                        f"Unrecoverable auth error: {resp.status_code} {resp.text}"
                    )
                if not resp.is_success:
                    return {"error": resp.status_code, "detail": resp.json()}
                return resp.json()

        return asyncio.run(_call())

    async def _arun(self, method, path, body=None, query=None):
        return self._run(method, path, body, query)
```

**Note on household_id application:** The CONTEXT.md leaves this to Claude's discretion ("check actual household-manager API spec"). The skill files (`recipes_get.md`, `meal_plan.md`) must be read at implementation time to determine whether `household_id` is a path component or query parameter. The tool should handle this internally so the agent never sees it.

### run_task() Injection Block (extension of Phase 6 pattern)

```python
# Source: src/robotina/queue/jobs.py — extend existing if-block
if task_type == "send-notification":
    from robotina.agent.tools.send_notification import SendNotificationTool
    tools.append(SendNotificationTool(
        chat_id=task_input.chat_id,
        user_id=task_input.user_id,
        platform=task_input.platform,
    ))
elif task_type == "handle-incoming-message":
    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    from robotina.agent.tools.queue import QueueTool
    from robotina.agent.tools.start_workflow import StartWorkflowTool
    tools.append(HouseholdManagerApiTool(household_id=task_input.household_id))
    tools.append(QueueTool(
        chat_id=task_input.chat_id,
        user_id=task_input.user_id,
        platform=task_input.platform,
    ))
    tools.append(StartWorkflowTool())
```

### AGENT_REGISTRY Entry Pattern

```python
# Source: src/robotina/agent/agents.py — extend AGENT_REGISTRY dict
AGENT_REGISTRY: dict[str, AgentConfig] = {
    "send-notification": AgentConfig(...),  # existing
    "handle-incoming-message": AgentConfig(
        task_type="handle-incoming-message",
        model_config={
            "provider": "ollama",
            "url": "http://localhost:11434",
            "model": "gpt-oss:20b",
            "api_key_env": "HANDLE_INCOMING_MESSAGE_API_TOKEN",
            "reasoning": True,
        },
        prompt_path="src/robotina/agent/prompts/robotina/V001.md",
        skills=["household-manager"],
        tools=[],  # all tools injected per-job in run_task()
    ),
}
```

### Prompt Architecture (V001.md pattern from send-notification)

The send-notification prompt demonstrates the pattern: state the role, give numbered instructions, include critical rules, add failure mode examples. The routing prompt must accomplish two things:
1. Make the routing decision unambiguous (direct-reply vs. workflow)
2. Instruct the agent how to compose the correct tool arguments for each path

The prompt structure should follow: Role → When to use `queue` vs `start-workflow` → Tool usage instructions → Critical Rules.

### shared.md Rewrite

Current `shared.md` has: Base URL, Authentication section (to REMOVE), Error codes table (remove 401/403 rows), Error response shape, Pagination, Filtering reference lists.

Rewritten `shared.md` keeps: Base URL, Error codes (400, 404, 422, 500 only), Error response shapes, Pagination, Filtering reference lists.

The `index.md` currently says "Before any operation, read `shared.md` to set up authentication and understand error handling." — this line must be updated to remove the auth reference (e.g., "Before any operation, read `shared.md` to understand base URL, error handling, and pagination.").

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client with auth injection | Custom requests wrapper | `httpx.AsyncClient` with `Authorization` header | Single line; handles connection pooling, timeout, redirects |
| Async-to-sync bridge in tool | Thread executor, nested loops | `asyncio.run()` | Already established in `SendNotificationTool` (Phase 6 decision: safe in RQ worker subprocess) |
| Queue enqueue with correct meta | Custom serialization | `rq.Queue.enqueue()` with `meta={'task_type': ...}` | Exact pattern already in gateway handler.py |
| Tool argument schema | Manual JSON schema | LangChain `BaseTool` + type hints in `_run` signature | LangChain infers schema from `_run` type annotations |

## Common Pitfalls

### Pitfall 1: 401/403 Swallowed by Agent
**What goes wrong:** Tool returns error dict instead of raising — agent retries with different params, loops, and eventually fails in a confusing way.
**Why it happens:** Using the same "return error dict" pattern for all non-2xx responses.
**How to avoid:** Explicit `if resp.status_code in (401, 403): raise RuntimeError(...)` BEFORE the generic non-2xx check. The exception propagates out of `asyncio.run()`, out of `_run()`, through the agent tool call, and causes `on_step_failed()` to be called.
**Warning signs:** Agent retrying after seeing an auth error in the tool result.

### Pitfall 2: Module-Level Tool Instantiation
**What goes wrong:** Tool created at import time or in `AGENT_REGISTRY.tools = [...]` — shares state across jobs.
**Why it happens:** It looks simpler. `StartWorkflowTool()` has no constructor args so it's tempting to put it in the registry.
**How to avoid:** ALWAYS instantiate tools inside the `elif task_type == ...` block in `run_task()`. This is a locked architectural constraint from Phase 4.
**Warning signs:** `StartWorkflowTool()` appearing in `AgentConfig.tools` rather than the injection block.

### Pitfall 3: household_id Leaked to Agent
**What goes wrong:** `household_id` appears in tool description or return value — agent starts reasoning about household IDs in prompts.
**Why it happens:** Including `household_id` in the tool's schema (either description or as a `_run` parameter).
**How to avoid:** `household_id` is a constructor field only (`self.household_id`), injected via `run_task()`. The `_run` signature never has a `household_id` parameter.
**Warning signs:** Test asserting agent can call `household-manager-api` with a `household_id` argument.

### Pitfall 4: Prompt Enumerates Workflow Keys
**What goes wrong:** Prompt says "use `add-recipe` workflow" — couples prompt version to workflow registry. Adding a new workflow type requires a prompt update.
**Why it happens:** Wanting to give the agent concrete guidance.
**How to avoid:** Prompt states routing principle. The `start-workflow` tool description enumerates available workflow types (already done in `StartWorkflowTool.description`).
**Warning signs:** Workflow type name (e.g. "add-recipe") appearing as a literal in V001.md.

### Pitfall 5: QueueTool Priority Mismatch
**What goes wrong:** `QueueTool` enqueues `send-notification` at the front (`at_front=True`) — it preempts the currently executing `handle-incoming-message` job (impossible in single worker, but logically wrong).
**Why it happens:** Copying the gateway's `at_front=True` pattern without thinking about its purpose.
**How to avoid:** `QueueTool` enqueues at the BACK of the queue (no `at_front=True`). The gateway uses `at_front=True` because it's enqueueing from outside the worker. Follow-up tasks from within agents should go to the back.
**Warning signs:** `at_front=True` appearing in `QueueTool._run()`.

### Pitfall 6: asyncio.run() Inside Already-Running Event Loop
**What goes wrong:** `RuntimeError: This event loop is already running` if tool is invoked in an async context.
**Why it happens:** Future callers (tests, async code paths) might call `_arun()`.
**How to avoid:** Implement `_arun()` as a true async method (`await asyncio.to_thread(self._run, ...)` or inline async with `httpx`) rather than calling `self._run()` directly if the codebase moves to async tool invocation. For Phase 7, `_arun()` delegating to `_run()` via `return self._run(...)` is acceptable because RQ workers are synchronous (Phase 6 decision).
**Warning signs:** Tests failing with "event loop already running" errors.

## Code Examples

### Correct Hard-Error Pattern for 401/403
```python
# Source: spec.md §Tools, D-02 from CONTEXT.md
if resp.status_code in (401, 403):
    raise RuntimeError(
        f"household-manager-api: unrecoverable auth error "
        f"(status={resp.status_code}). Check HOUSEHOLD_MANAGER_API_KEY env var."
    )
# Recoverable non-2xx — agent can handle
if not resp.is_success:
    return {"error": resp.status_code, "message": resp.text}
return resp.json()
```

### Correct QueueTool Enqueue (back of queue, correct meta)
```python
# Derived from: src/robotina/gateway/handler.py:117-125
job = q.enqueue(
    "robotina.queue.jobs.run_task",
    task_input,                    # SendNotificationInput
    result_ttl=-1,
    failure_ttl=-1,
    meta={"task_type": "send-notification"},
    # NO at_front=True — follow-up tasks go to back of queue
)
return job.id
```

### Skill File Rewrite — shared.md Section to Remove
```markdown
# REMOVE THIS ENTIRE SECTION from shared.md:
## Authentication

Every request must include the header:
Authorization: Bearer <token>
...
| 401 | Not authenticated ... |
| 403 | Forbidden ...         |
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Auth in skill (`shared.md`) | Auth injected by tool | Phase 7 design decision | Agent never sees auth token; 401/403 never reaches agent |
| Tools registered in `AgentConfig.tools` | Per-job tools injected in `run_task()` | Phase 4 locked decision | No shared state between job executions |
| `AgentExecutor` | `create_react_agent` from `langgraph.prebuilt` | Phase 4 locked decision | AGENT-11 requirement |

## Open Questions

1. **How does `household_id` attach to API requests?**
   - What we know: D-02 says "tool prepends household_id automatically where spec requires"
   - What's unclear: Is it a path component (`/api/households/{id}/recipes`) or query param (`?household_id=...`) or request header?
   - Recommendation: Read `recipes_get.md`, `meal_plan.md` skill files during Wave 0 (pre-implementation check). If endpoints take `household_id` as a path prefix, tool can prepend to all paths. If query param, inject into `query` dict.

2. **Should `IncomingMessageOutput` be explicitly constructed?**
   - What we know: CONTEXT.md marks this as Claude's discretion; raw `messages` list is acceptable
   - What's unclear: Whether the workflow engine's `on_step_complete` requires a specific output format
   - Recommendation: Return the raw agent result for Phase 7 (same as `send-notification`). `IncomingMessageOutput` construction can be added when a downstream consumer needs it.

3. **What model configuration for handle-incoming-message?**
   - What we know: CONTEXT.md D-03 says "model config following same env-var pattern"
   - What's unclear: Which model provider and model name (Ollama vs Anthropic vs OpenAI, which model)
   - Recommendation: Mirror the `send-notification` config (Ollama, `gpt-oss:20b`, `reasoning: True`) as the default. Developer can override via `AGENT_OVERRIDES_FILEPATH`.

## Environment Availability

> Step 2.6 — this phase has no new external dependencies. All tools are internal (RQ, Redis, httpx) and already verified as available from earlier phases.

Step 2.6: SKIPPED (no new external dependencies — all required tools are already in use in earlier phases).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/unit/ -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ROBOT-01 | `handle-incoming-message` registered in AGENT_REGISTRY | unit | `uv run pytest tests/unit/test_agents_registry.py -x -q` | ✅ (extend) |
| ROBOT-01 | `run_task()` dispatches tools for `handle-incoming-message` | unit | `uv run pytest tests/unit/test_agent_runner.py -x -q` | ✅ (extend) |
| ROBOT-02 | `HouseholdManagerApiTool` construction with `household_id` | unit | `uv run pytest tests/unit/test_household_manager_api_tool.py -x -q` | ❌ Wave 0 |
| ROBOT-02 | `HouseholdManagerApiTool._run()` injects Bearer token header | unit | `uv run pytest tests/unit/test_household_manager_api_tool.py -x -q` | ❌ Wave 0 |
| ROBOT-02 | `HouseholdManagerApiTool._run()` raises `RuntimeError` on 401/403 | unit | `uv run pytest tests/unit/test_household_manager_api_tool.py -x -q` | ❌ Wave 0 |
| ROBOT-02 | `HouseholdManagerApiTool._run()` returns error dict for other non-2xx | unit | `uv run pytest tests/unit/test_household_manager_api_tool.py -x -q` | ❌ Wave 0 |
| ROBOT-03 | `QueueTool` construction with `chat_id`, `user_id`, `platform` | unit | `uv run pytest tests/unit/test_queue_tool.py -x -q` | ❌ Wave 0 |
| ROBOT-03 | `QueueTool._run()` enqueues `send-notification` with correct meta | unit | `uv run pytest tests/unit/test_queue_tool.py -x -q` | ❌ Wave 0 |
| ROBOT-03 | `QueueTool._run()` returns `job_id` string | unit | `uv run pytest tests/unit/test_queue_tool.py -x -q` | ❌ Wave 0 |
| ROBOT-04 | `run_task()` injects `StartWorkflowTool` for `handle-incoming-message` | unit | `uv run pytest tests/unit/test_agent_runner.py -x -q` | ✅ (extend) |
| ROBOT-05 | `shared.md` does not contain "Authentication" section | unit | `uv run pytest tests/unit/test_skills.py -x -q` | ✅ (extend) |
| ROBOT-05 | `shared.md` does not contain 401 or 403 rows | unit | `uv run pytest tests/unit/test_skills.py -x -q` | ✅ (extend) |
| ROBOT-06 | `src/robotina/agent/prompts/robotina/V001.md` exists and non-empty | unit | `uv run pytest tests/unit/test_prompts.py -x -q` | ✅ (extend) |
| ROBOT-07 | Routing logic — manual validation only (requires live LLM) | manual | N/A | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_household_manager_api_tool.py` — covers ROBOT-02 (construction, auth injection, 401/403 hard error, non-2xx recovery)
- [ ] `tests/unit/test_queue_tool.py` — covers ROBOT-03 (construction, enqueue call, job_id return)
- [ ] Extend `tests/unit/test_agents_registry.py` — add test that `handle-incoming-message` is in `AGENT_REGISTRY` with correct skill and prompt path
- [ ] Extend `tests/unit/test_agent_runner.py` — add test that `run_task()` injects all three tools for `handle-incoming-message` (mirrors `test_run_task_injects_send_notification_tool_for_task_type`)
- [ ] Extend `tests/unit/test_prompts.py` — add test that `src/robotina/agent/prompts/robotina/V001.md` exists
- [ ] Extend `tests/unit/test_skills.py` — add tests that `shared.md` no longer contains auth section or 401/403 rows

## Sources

### Primary (HIGH confidence)
- `src/robotina/agent/tools/send_notification.py` — constructor injection pattern; `asyncio.run()` bridge
- `src/robotina/agent/tools/start_workflow.py` — `BaseTool` subclass with own session management; template for new tools
- `src/robotina/queue/jobs.py` — `run_task()` tool injection block; Phase 6 pattern to extend
- `src/robotina/agent/agents.py` — `AGENT_REGISTRY` and `AgentConfig` structure
- `src/robotina/queue/task_types.py` — `IncomingMessageInput` fields; `SendNotificationInput` shape
- `src/robotina/gateway/handler.py:117-125` — correct RQ enqueue call pattern (meta, ttl, at_front semantics)
- `src/robotina/agent/skills/household-manager/shared.md` — current state; section to remove documented above
- `plans/01-kickoff/spec.md §Tools` — authoritative description of `household-manager-api` and `queue` tool requirements
- `.planning/phases/07-handle-incoming-message-agent/07-CONTEXT.md` — all locked decisions D-01 through D-06

### Secondary (MEDIUM confidence)
- `tests/unit/test_send_notification_tool.py` — test patterns for tool unit tests; ROBOT-02/03 tests should mirror this file's structure
- `src/robotina/agent/prompts/send-notification/V001.md` — prompt structure template for V001.md

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all existing infrastructure verified by direct code read
- Architecture: HIGH — both new tools are direct extensions of verified Phase 6 patterns
- Pitfalls: HIGH — 401/403 hard-error requirement is spec-documented; other pitfalls derived from existing architectural constraints
- Prompt design (ROBOT-07): MEDIUM — routing calibration requires LLM testing; structure is clear but exact wording needs iteration

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable domain — no fast-moving dependencies)
