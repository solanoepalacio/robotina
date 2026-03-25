# Pitfalls Research

**Domain:** Python LangChain agent with RQ task queue, multi-step workflow orchestration, Postgres state, Telegram gateway, LangWatch observability
**Researched:** 2026-03-25
**Confidence:** HIGH (spec-driven analysis) / MEDIUM (library-specific behaviors from domain knowledge)

---

## Critical Pitfalls

### Pitfall 1: RQ Job Arguments Must Be Pickle-Serializable — Pydantic Models Are Not Automatically Safe

**What goes wrong:**
RQ serializes job arguments using Python's `pickle` by default. Pydantic v2 models are generally picklable, but the serialization breaks silently when arguments contain: lambda functions, database session objects, open file handles, or objects that hold references to unpicklable attributes. The spec passes `build_input` as a `Callable` on `WorkflowStepDef` — if this callable is a lambda defined in a module-level dict, it serializes fine. But if any tool or agent object is accidentally included in job args, the worker will fail with a `PicklingError` that only surfaces at enqueue time, not at definition time.

**Why it happens:**
Developers enqueue tasks passing rich objects (SQLAlchemy model instances, entire config objects) instead of plain serializable inputs. The gateway code fetches a `Conversation` ORM object and then passes it directly into job args instead of serializing it to a Pydantic model first.

**How to avoid:**
- Job function signatures must accept only Pydantic model instances or plain Python primitives (`str`, `int`, `dict`, `list`).
- Never pass SQLAlchemy ORM instances, database sessions, or connection objects as RQ job args.
- Serialize to `.model_dump()` at the call site and deserialize with `Model.model_validate()` inside the job function.
- Use RQ's `serializer` parameter to switch to JSON if strict safety is required — this makes serialization failures explicit and immediate instead of hidden.
- Write a test that enqueues every task type and verifies the job reaches `queued` status without errors.

**Warning signs:**
- `PicklingError` or `AttributeError: Can't pickle` in RQ worker logs at job enqueue time.
- Jobs enter `failed` state immediately without ever reaching `started`.
- Unit tests pass but integration tests (with a real Redis) fail.

**Phase to address:** Queue infrastructure phase (before any agent work begins). All task input/output Pydantic models must be tested for round-trip serialization before the first agent is wired up.

---

### Pitfall 2: Workflow Advancement Race Between Task Completion and Next-Step Enqueueing

**What goes wrong:**
The task runner must: (1) write `WorkflowRunStep.artifact`, (2) mark the step `DONE`, (3) build the next step's input, (4) enqueue the next RQ job, and (5) write the new `task_job_id` to `WorkflowRunStep` — all atomically. If the process crashes between steps 4 and 5, the next job is running in RQ but the `WorkflowRunStep` has no `task_job_id`, so when that job completes the task runner cannot link it back to its workflow step. Subsequent advancement fails silently.

**Why it happens:**
The natural implementation writes to Postgres and enqueues to Redis as two separate operations with no transaction boundary around them. Developers assume they are "close enough" in time to be safe.

**How to avoid:**
- Enqueue the next RQ job *before* committing the Postgres transaction. Use RQ's `job_id` parameter to pre-assign a deterministic or UUIDbased job ID. Write that ID to `WorkflowRunStep.task_job_id` in the same Postgres commit. If the commit fails, the enqueued job is orphaned in Redis but the workflow row is consistent and can be re-advanced.
- Alternatively: use a database-side outbox pattern — write the "enqueue next step" intent to a Postgres table row, commit, then have a separate thread poll the outbox and enqueue. For concurrency=1 sequential processing, the simpler approach (pre-assign job ID, commit atomically) is sufficient.
- Never commit `DONE` state to a step without also having already written `task_job_id` to the next step.

**Warning signs:**
- Workflow runs stuck in `RUNNING` with the last step `DONE` but no subsequent step enqueued.
- `WorkflowRunStep.task_job_id` is `NULL` for a step that has an RQ job in the queue.
- Workflows only fail during testing when a debugger or slow I/O is introduced between Postgres and Redis operations.

**Phase to address:** Workflow infrastructure phase. Transactional advancement logic must be implemented and integration-tested before any workflow-dependent agent is built.

---

### Pitfall 3: LangChain Tool Exceptions Swallowed by the Agent Loop

**What goes wrong:**
When a LangChain tool raises an exception, the default behavior of `create_react_agent` (LangGraph) is to catch the exception and return its string representation as a tool observation. This means: a `401 Unauthorized` from the household-manager API becomes an agent observation saying "Error: 401 Unauthorized", and the agent proceeds to retry or hallucinate a workaround. For hard errors (auth failure, network down) the agent should abort — instead it spins in a retry loop burning LLM tokens, potentially exhausting max_iterations and leaving the job in a non-recoverable state without a clear error.

**Why it happens:**
Developers write tools that raise `Exception` and assume this will stop the agent. LangGraph's tool executor intercepts exceptions unless the tool is configured with `handle_tool_error=False` or the exception is re-raised as a specific interrupt type.

**How to avoid:**
- For the `household-manager-api` tool, a `401` or `403` response must raise an exception that bypasses the agent loop, not return a string error. Use LangChain's `ToolException` with `handle_tool_error=False` on the tool definition, or raise a Python exception that propagates past the agent executor entirely. The spec explicitly states: "A `401` or `403` response is unrecoverable and must raise a hard error."
- Define two exception categories: **recoverable** (e.g. rate limit, transient HTTP 500) which return a string observation to let the agent retry, and **unrecoverable** (auth failure, missing resource, schema mismatch) which raise and abort the job.
- Set a `max_iterations` cap on the agent (e.g. 10) to prevent infinite retry loops even for recoverable errors.
- Log all tool exceptions at `ERROR` level before deciding to surface or swallow them.

**Warning signs:**
- Agent logs show repeated identical tool calls with the same parameters.
- LangWatch traces show many tool calls for a single job that should have completed in 2-3.
- Jobs finish with `success` status but the actual household operation was never performed.

**Phase to address:** Agent infrastructure phase. Tool error handling policy must be established in the base tool wrappers before any domain tool (`household-manager-api`, `web-search`) is implemented.

---

### Pitfall 4: LangWatch Trace Context Lost Across RQ Job Boundaries

**What goes wrong:**
LangWatch uses OpenTelemetry to propagate trace context. When an agent runs inside an RQ worker, the OTel span context is NOT automatically propagated from the enqueuing process to the worker process. Each RQ job starts a new OTel context, creating orphaned traces that are not linked to the originating request. The Telegram message → handle-incoming-message → recipe-research → recipe-load → send-notification chain appears as five disconnected traces in LangWatch rather than one correlated session.

**Why it happens:**
OTel trace propagation relies on context managers that live in process memory. Cross-process boundaries (Telegram gateway → RQ worker → next RQ worker) require explicit serialization of the trace context (W3C `traceparent` header format) and injection into the job payload. Developers instrument each agent individually but miss the propagation linkage.

**How to avoid:**
- Serialize the current OTel trace context (`W3C traceparent`) into every task's input model or as a job metadata field when enqueuing. At job start, extract and restore the parent trace context before creating the child span.
- For experiment runs: start a fresh trace root span at the experiment entry point and instrument from there — no propagation needed.
- Store `workflow_run_id` as a trace attribute on every span within a workflow. Even without parent-child linkage, all spans with the same `workflow_run_id` can be correlated in LangWatch.
- Use LangWatch's native session/thread ID feature to group traces by `workflow_run_id` or `conversation_id`.

**Warning signs:**
- LangWatch shows traces for individual agents but no higher-level view of a full workflow run.
- Trace durations look short (missing the full agent reasoning chain) because the parent span context was never propagated.
- Experiment script traces appear in the wrong LangWatch project collection.

**Phase to address:** Agent infrastructure and observability phase. Trace propagation strategy must be decided before the first multi-agent workflow is wired up. Retroactively adding it requires changes to all task input models.

---

### Pitfall 5: Telegram Bot Receives Duplicate Webhooks Under Load or Reconnect

**What goes wrong:**
Telegram's webhook delivery does not guarantee exactly-once delivery. On reconnect, network timeout, or if the gateway returns a non-200 response, Telegram will retry the webhook. The gateway will persist the message and enqueue a `handle-incoming-message` task twice. The agent will process the same user message twice, potentially creating duplicate recipes or sending duplicate replies.

**Why it happens:**
Developers implement the webhook handler without idempotency checks, relying on Telegram's best-effort deduplication. The `StoredMessage.platform_message_id` unique constraint exists in the spec, but it is only used when inserting the message — not checked before enqueueing the task.

**How to avoid:**
- Use `platform_message_id` as an idempotency key at the enqueue step, not just for storage. Before calling `queue.enqueue(handle-incoming-message)`, check whether a job with this `message_id` was already enqueued or completed (via RQ job ID stored against `platform_message_id`, or by checking `StoredMessage.created_at` vs just-inserted).
- In the gateway webhook handler: use a database `INSERT ... ON CONFLICT DO NOTHING` with `RETURNING` — if no row is returned, the message was already processed; skip enqueue and return 200 to Telegram immediately.
- Never return a non-200 response to Telegram unless the request is fundamentally malformed. Return 200 even on internal errors; let the task queue handle retries asynchronously. A non-200 will trigger Telegram to re-deliver.

**Warning signs:**
- Duplicate `StoredMessage` insert attempts raising `UniqueViolation` in Postgres logs.
- Two `handle-incoming-message` jobs in RQ with the same `message_id` in their input.
- Users receiving duplicate replies to a single message.

**Phase to address:** Gateway infrastructure phase. Idempotency must be built into the initial webhook handler design — it cannot be bolted on after the fact without risk of race conditions.

---

### Pitfall 6: Alembic Autogenerate Misses SQLAlchemy Enum Type Changes

**What goes wrong:**
When a `WorkflowStatus` or `WorkflowStepStatus` Python enum is modified (a new value added, a value renamed), `alembic revision --autogenerate` does NOT reliably detect the change to the underlying Postgres `ENUM` type. Alembic compares Python enum members with the Postgres type definition only in specific configurations. Without explicit Alembic `op.execute("ALTER TYPE ... ADD VALUE ...")` calls, the migration is silently incomplete. The application starts, but any row written with the new enum value will cause a `LookupError: <value> is not among the valid values` in SQLAlchemy.

**Why it happens:**
Developers rely on autogenerate for all schema changes and assume that changing a Python `enum.Enum` class is reflected automatically in the migration. Alembic's PostgreSQL dialect does detect enum changes in recent versions, but only when `compare_type=True` is set in the `env.py` configuration — it defaults to `False`.

**How to avoid:**
- Set `compare_type=True` in Alembic's `env.py` `configure()` call from the start of the project.
- After autogenerating any migration touching enum types, manually inspect the generated migration script and verify that `op.execute("ALTER TYPE ...")` statements are present if enum members changed.
- For adding enum values: `ALTER TYPE ... ADD VALUE` in Postgres cannot be run inside a transaction. Alembic migrations default to running inside a transaction. Any migration adding an enum value must use `op.execute("COMMIT")` before the `ALTER TYPE` statement and `op.execute("BEGIN")` after — or set `transactional_ddl = False` for that migration.
- Treat enum additions as a two-migration process: first add the Postgres type value, then use it in application code.

**Warning signs:**
- `alembic upgrade head` completes without error but the Postgres enum type definition does not match the Python enum.
- `psycopg2.errors.InvalidTextRepresentation` errors in logs when inserting rows with new enum values.
- `alembic revision --autogenerate` generates an empty migration even though enum members were added.

**Phase to address:** Database/migrations setup phase. `compare_type=True` must be set in `env.py` before any migrations are authored. Enum mutation discipline must be established as a team convention at the start.

---

### Pitfall 7: Shared Context Mutation Corrupts Downstream Workflow Steps

**What goes wrong:**
`WorkflowRun.shared_context` is defined as a JSON column set once at workflow creation and never mutated. If the `build_input` callable or the task runner code ever writes back to `shared_context` (even accidentally, via Python dict mutation of the deserialized object), subsequent steps see modified context. For example, if `build_input` for `recipe-load` accidentally adds a key to the `ctx` dict, that dict is the deserialized `shared_context` and is reflected in subsequent artifact builds.

**Why it happens:**
Python dicts passed to lambdas are mutable. The `build_input` callables receive `shared_context` as a plain `dict` and there is nothing preventing in-place modification. Developers modify the dict to "merge" it with artifact data for convenience.

**How to avoid:**
- Pass a deep copy of `shared_context` to `build_input` callables: `build_input(copy.deepcopy(shared_context), accumulated_artifacts)`.
- Alternatively, freeze `shared_context` as a `types.MappingProxyType` before passing it to lambdas — any write attempt raises `TypeError` immediately.
- Add an assertion in the task runner: after calling `build_input`, compare the `shared_context` object to its pre-call snapshot and raise `AssertionError` if it has changed (useful in tests, removable in production).
- Document the `build_input` contract explicitly: callables are pure functions — they read inputs and return a new model; they never mutate arguments.

**Warning signs:**
- The `send-notification` step receives incorrect `reply_context` values for the second or third workflow run.
- `WorkflowRun.shared_context` in Postgres has keys that were not present at workflow creation.
- Intermittent failures only on second+ steps of a workflow but not on the first step.

**Phase to address:** Workflow infrastructure phase. The immutability contract must be encoded in the task runner implementation before any workflow is tested end-to-end.

---

### Pitfall 8: LangChain Agent State Leaks Between Sequential RQ Jobs

**What goes wrong:**
When RQ processes sequential jobs in the same worker process, Python module-level state, LangChain callback objects, and LLM client connection objects persist between job executions. If the LangChain `create_react_agent` or any LangWatch callback handler stores state (e.g., in-progress trace ID, previous message history) at the module level rather than per-invocation, that state bleeds into the next job. The most common symptom: conversation history from job N appears in job N+1's agent context.

**Why it happens:**
Developers test agents in isolation (one process, one invocation) and never encounter inter-job contamination. In production, the single RQ worker processes job after job in the same process. Any object instantiated at import time rather than at job invocation time becomes shared state.

**How to avoid:**
- Instantiate all per-job objects (LLM client, callbacks, agent, skill sets) inside the job function itself, not at module level.
- LangWatch instrumentation: ensure the trace/span is opened and closed within the job function scope. Use Python context managers or `try/finally` blocks to guarantee span closure even on exception.
- Explicitly clear or re-initialize any LangChain message history objects at the start of each job — do not rely on object garbage collection timing.
- Write an integration test that executes two jobs back-to-back in the same process and asserts the second job's agent context contains no artifacts from the first job.

**Warning signs:**
- Agent responses for job N+1 reference information that only exists in job N's input.
- LangWatch traces for different jobs appear merged or contain more tool calls than expected.
- Unit tests pass but end-to-end tests with multiple sequential jobs fail intermittently.

**Phase to address:** Agent infrastructure phase. Scoping rules (module-level vs. job-level instantiation) must be established in the base agent runner before any domain agents are implemented.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Returning tool errors as strings instead of raising structured exceptions | Faster initial tool implementation | Agent silently retries unrecoverable errors, burns tokens | Never — establish error categories from the start |
| Hardcoding `shared_context` dict keys as string literals across `build_input` lambdas | Quick to write | Typos cause silent `KeyError` at runtime mid-workflow; no type safety | Never — define a typed `SharedContext` Pydantic model instead |
| Using RQ's default `result_ttl=500` (8 minutes) during development | Fewer Redis keys | Job results expire before post-hoc debugging or experiment inspection | Only if explicitly resetting to `-1` before production |
| Storing full conversation history in every `handle-incoming-message` input indefinitely | Simpler gateway code | Input payload grows unbounded; RQ job serialization slows; context window fills | Never — cap history at the gateway with a configurable max |
| Single Alembic `Base` metadata shared between gateway and workflow models | Simpler migrations | Migrations become hard to reason about as model count grows; circular imports risk | Acceptable for Phase 1; plan to split at Phase 2+ |
| Inline `build_input` lambdas for simple steps | Readable in `workflows.py` | Lambdas cannot be unit-tested in isolation | Acceptable for Phase 1; refactor to named functions when workflow count grows |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Telegram webhooks | Returning 200 only on success; returning error codes on partial failures | Always return 200 to Telegram; handle errors asynchronously in the task queue |
| Telegram webhooks | Not setting a webhook secret token | Set `secret_token` on `setWebhook` and verify it on every incoming request |
| RQ + Redis AOF | Using `appendfsync everysec` instead of `appendfsync always` as specified | Verify Redis config file explicitly; Docker defaults do not set AOF mode |
| Alembic + SQLAlchemy enums | Not setting `compare_type=True` in `env.py` | Set `compare_type=True` before the first `autogenerate` run |
| LangWatch + OTel | Calling `langwatch.setup()` multiple times (once per experiment, once in production code) | Initialize once at process startup; guard with a module-level sentinel |
| Tavily web search | Not setting `max_results` — default returns too many results, inflating context | Always bound `max_results`; for recipe research 3-5 results is sufficient |
| Household-manager API | Agent receiving raw API error details it can act on (retry auth, modify request) | Auth errors must raise hard exceptions; the agent must never see a 401/403 |
| RQ Dashboard | Running dashboard without authentication in a network-accessible environment | Add basic auth or restrict to `localhost` only in Docker Compose |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading all skill sub-files eagerly into agent context | Long time-to-first-token; context window fills; cost per run inflates | Load only `index.md` upfront; lazy-load sub-files via `read-skill` tool as specified | From the first run if skills have more than 2-3 sub-files |
| Fetching full Postgres conversation history without a limit | Gateway slows down for active users; RQ job payload grows large | Always apply `LIMIT N` (configurable env var) when fetching history | When a conversation exceeds ~50 messages |
| RQ worker holding open a SQLAlchemy connection between jobs | Postgres connection pool exhaustion during sustained load | Use `scoped_session` or explicit session close in a `finally` block after every job | When running multiple workers or under sustained message load |
| LLM streaming without a timeout | Worker hangs indefinitely if the LLM provider stalls mid-stream | Set `request_timeout` on the LangChain model and a job `timeout` on the RQ job | Immediately — any LLM provider outage or rate limit can trigger this |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging full task input payloads at DEBUG level | Exposes conversation text, household IDs, and API tokens in log files | Redact `text`, `history`, and any field ending in `_token` or `_key` before logging |
| Exposing RQ job args (which contain full task inputs) in RQ Dashboard without auth | Anyone with network access reads all household data | Restrict RQ Dashboard to localhost in Docker Compose; add auth for production |
| Telegram webhook endpoint has no secret token verification | Any external party can inject arbitrary messages into the system | Validate `X-Telegram-Bot-Api-Secret-Token` header on every webhook request |
| API tokens read from env vars logged at startup for debugging | Secrets in application logs | Log only the first 4 chars + `***` of any token at startup for confirmation |
| `WorkflowRun.shared_context` stored in plaintext JSON | Telegram user IDs and chat IDs stored in plaintext | Acceptable for Phase 1; note it as a future encryption candidate |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No acknowledgement message when starting a multi-step workflow | User sends "add carbonara" and hears nothing for 30–60 seconds while the workflow runs | Have `handle-incoming-message` send an immediate acknowledgement ("Got it, researching the recipe...") before starting the workflow |
| Telegram formatting applied by the notification agent fails silently | User receives a wall of Markdown syntax characters (`*`, `_`, `[`) instead of formatted text | Test `send-notification` with representative messages including bold, lists, and links before shipping |
| Error in mid-workflow step gives no user notification | Recipe research fails; user never finds out their request was not completed | On workflow failure, emit a `send-notification` task with a user-facing error message before marking the workflow `FAILED` — even though auto-retry is out of scope |
| Conversation history includes assistant-side task orchestration messages | Agent context is polluted with internal "starting workflow..." messages; response quality degrades | Only persist messages with `role=user` and `role=assistant` for actual user-facing turns; do not store internal tool outputs in conversation history |

---

## "Looks Done But Isn't" Checklist

- [ ] **RQ Job Serialization:** Pydantic models are instantiated inside job functions, not passed as class references — verify all task types can be pickled and unpickled without data loss.
- [ ] **Workflow Advancement:** Task runner writes `task_job_id` for the next step in the same Postgres commit as `artifact` write — verify with a forced crash test between enqueue and DB commit.
- [ ] **LangWatch Instrumentation:** Traces appear in LangWatch UI with correct parent-child relationships, not as isolated orphans — verify by running a full workflow end-to-end and inspecting in the UI.
- [ ] **Telegram Deduplication:** The gateway returns 200 on duplicate webhook delivery and does NOT enqueue a second job — verify by replaying a webhook request with the same `update_id`.
- [ ] **Alembic Migrations:** `alembic upgrade head` runs cleanly on a fresh Postgres instance — verify in CI with a disposable Postgres container, not just against a developer's existing database.
- [ ] **Agent State Isolation:** Running two sequential jobs in the same worker process does not contaminate the second job's context with the first job's data — verify with a sequential integration test.
- [ ] **Tool Hard Errors:** A `401` from household-manager API causes the RQ job to fail with a clear error message and does NOT cause the agent to retry — verify by pointing the tool at a server returning 401.
- [ ] **Redis AOF Config:** Redis is actually running with `appendfsync always`, not just `appendonly yes` — verify with `redis-cli CONFIG GET appendfsync`.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| RQ job serialization failure discovered after deployment | MEDIUM | Audit all job arg types; refactor to Pydantic-only inputs; re-enqueue failed jobs from the failed registry |
| Workflow advancement race leaves orphaned RQ job | LOW | Add a reconciliation query: find `WorkflowRunStep` rows where `task_job_id` IS NULL but previous step is DONE; re-enqueue manually |
| LangWatch traces disconnected (no propagation) | LOW | Add `workflow_run_id` as a trace tag retroactively; traces cannot be re-linked but future runs will be correlated |
| Duplicate messages processed due to missing idempotency | MEDIUM | Identify duplicates by `platform_message_id`; cancel or delete the second RQ job from the dashboard; no data recovery needed if household-manager API is idempotent |
| Alembic enum migration applied without `ALTER TYPE` | HIGH | Run `ALTER TYPE ... ADD VALUE` manually in Postgres; generate a corrective migration; restore consistency between Python enum and DB type |
| `shared_context` mutated mid-workflow | HIGH | Inspect `workflow_runs` rows in Postgres for unexpected keys; mark affected workflow runs `FAILED`; re-initiate from user message |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| RQ job serialization (pickle) | Queue infrastructure | Test: enqueue + deserialize all task types in a real Redis |
| Workflow advancement race | Workflow infrastructure | Test: forced crash between Redis enqueue and Postgres commit; reconciliation audit |
| LangChain tool exceptions swallowed | Agent infrastructure | Test: tool returning 401 causes job failure, not agent retry loop |
| LangWatch trace propagation | Agent infrastructure + observability | Verify: full workflow trace appears in LangWatch as linked spans |
| Telegram duplicate webhooks | Gateway infrastructure | Test: replay same `update_id` twice; assert single job in RQ |
| Alembic enum mutation | Database/migrations setup | Verify: `alembic upgrade head` on fresh DB + `compare_type=True` in env.py |
| Shared context mutation | Workflow infrastructure | Test: two sequential workflow runs with frozen `shared_context` |
| Agent state leaks between jobs | Agent infrastructure | Test: two sequential jobs in same worker process with context assertions |

---

## Sources

- Spec analysis: `/plans/01-kickoff/spec.md` — transactional advancement, task input models, tool error requirements
- Project context: `/.planning/PROJECT.md` — concurrency constraints, Redis AOF requirement, LangWatch mandate
- RQ documentation domain knowledge: job serialization with pickle, `result_ttl`, `failure_ttl`, `at_front`, failed registry behavior
- LangChain / LangGraph domain knowledge: `create_react_agent` exception handling, `handle_tool_error`, `max_iterations`
- OpenTelemetry / LangWatch domain knowledge: cross-process context propagation, W3C `traceparent`, span lifecycle in worker processes
- Alembic domain knowledge: `compare_type=True`, Postgres `ALTER TYPE ... ADD VALUE` transaction restriction
- Telegram Bot API domain knowledge: webhook retry behavior, `secret_token`, `update_id` deduplication field
- Python domain knowledge: pickle limitations, dict mutability, module-level vs. call-level object scoping

---
*Pitfalls research for: Robotina — Python LangChain agent with RQ task queue and workflow orchestration*
*Researched: 2026-03-25*
