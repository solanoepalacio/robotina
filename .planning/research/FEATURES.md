# Feature Research

**Domain:** AI home assistant agent — Telegram bot + task queue + multi-step workflow orchestration
**Researched:** 2026-03-25
**Confidence:** HIGH (derived from authoritative spec and existing skill implementation; no web search available)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that must exist for the system to function at all. Missing any of these means the system does not deliver its core value.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Receive and parse Telegram messages | The entire system triggers on user messages; no message = no agent | LOW | Gateway persists message, fetches history, enqueues task — three atomic operations |
| Deduplicate incoming messages | Telegram can redeliver webhooks; processing twice causes duplicate side effects | LOW | `platform_message_id` unique constraint on `StoredMessage` handles this at the DB layer |
| Persist conversation history | Agent needs context across turns; stateless = feels like talking to amnesia | LOW | Postgres `Conversation` + `StoredMessage` models; history length configurable via env var |
| Task queue with exactly-one concurrency | Multiple concurrent agent runs would corrupt shared state and create race conditions on workflow advancement | MEDIUM | RQ + single worker; not a limitation — an architectural invariant |
| Task input/output as typed Pydantic models | Strong contracts between producer and consumer; prevents silent data corruption across task handoffs | LOW | All four task types (`IncomingMessageInput`, `RecipeResearchInput`, `RecipeLoadInput`, `SendNotificationInput`) fully specified |
| Redis AOF persistence | A crash with pending tasks should not silently lose work | LOW | `appendfsync always` — every enqueue acknowledged only after disk flush |
| Agent responds to user in Telegram | If the loop doesn't close back to the user, the system is invisible | LOW | `send-notification` task + Telegram send via gateway |
| Telegram-safe message formatting | Telegram's MarkdownV2 rejects unescaped special characters and silently drops messages | MEDIUM | `send-notification` agent applies `format-telegram-message` skill before delivery; a dedicated agent step prevents formatting errors from corrupting content agents |
| LLM provider abstraction | Different task types may need different models; hardcoding one provider blocks experimentation | MEDIUM | `LLMBackend` Protocol; adapters for Ollama, Anthropic, OpenAI; config per task type in `agents.py` |
| Per-task-type system prompts | Each agent specialization needs its own focused prompt; one global prompt produces incoherent behavior | LOW | Versioned markdown prompts at `prompts/<task-type>/V001.md`; swappable at runtime |
| Skill lazy loading | Full context bloat on every agent run degrades performance and wastes tokens | LOW | Index pre-loaded; sub-files fetched on demand via `read-skill` tool |
| Household Manager API tool | Agents need to read/write household data; hard-coding HTTP in agents couples them to auth details | LOW | Tool handles Bearer auth invisibly; `401`/`403` raise hard errors — not passed back to LLM |
| Workflow step isolation (no reply_context in intermediate tasks) | Intermediate agents (recipe-research, recipe-load) must not know about Telegram; coupling breaks reusability | MEDIUM | `reply_context` stored once in `WorkflowRun.shared_context`; task runner injects it only into `send-notification` input |
| Workflow failure propagation | A failed step must not leave the workflow in a zombie "running" state indefinitely | LOW | On step failure: mark step `FAILED`, cancel remaining `PENDING` steps, mark `WorkflowRun` `FAILED` |
| Failed job retention (dead letter queue) | Developers need to inspect failures post-mortem | LOW | RQ's built-in failed registry; `result_ttl = -1` and `failure_ttl = -1` on all jobs |
| LangWatch + OTel instrumentation | Without traces, debugging LLM failures is guesswork | MEDIUM | Must be active in both production and experiment runs; traces scoped to experiment collection |

### Differentiators (Competitive Advantage)

Features that make this system good rather than mediocre. These align with the core value: "Families can delegate household tasks in natural language and trust that they get done."

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Centralized task-runner workflow orchestration | Individual agents stay dumb and reusable; sequence logic lives in one place (`workflows.py`), not scattered across agents | HIGH | `WorkflowDefinition` registry with `build_input` callables; agent independence is the payoff — adding a new workflow step only requires a new `WorkflowStepDef`, not changes to existing agent inputs |
| Human-readable ingredient resolution (name → ID) | Recipe-research agent can name "Huevo" without knowing database IDs; recipe-load resolves names against `/api/foods?name=` and `/api/units?name=` lookups | MEDIUM | `RecipeData` uses `food_name`/`unit_name` strings; resolution happens at load time with targeted name-filter API calls |
| Prompt versioning with runtime override | Swap prompts without a redeploy; keep old versions for regression comparison | LOW | `AGENT_OVERRIDES_FILEPATH` JSON file; version files named `V001.md`, `V002.md`, etc. |
| Standalone experiment scripts per task type | Evaluate prompt quality independently from the full system; iterate without manual end-to-end testing | MEDIUM | One script per task type (recipe-research, recipe-load, send-notification); LangWatch traces scoped to named experiment collection |
| Separate scheduler worker | Scheduled tasks don't compete with or block real-time agent processing | LOW | Two workers: `scheduler-worker` (moves jobs into `agent-tasks`) and `task-runner` (processes agent jobs); decoupled by design |
| User messages enqueued at front of queue (urgent priority) | User messages are never delayed by background tasks already in queue | LOW | RQ `at_front=True` for `handle-incoming-message` tasks enqueued by gateway |
| Accumulated artifacts pattern | Each workflow step's output is persisted and accessible to all subsequent steps; no re-fetching or re-computing data | MEDIUM | `WorkflowRunStep.artifact` → `accumulated_artifacts` dict keyed by `step_key`; enables clean data flow without coupling |
| Per-task LLM configuration | Route cheap tasks to a small local model (Ollama), expensive tasks to a frontier API; optimize cost without architectural change | LOW | Full connection details (url, model, api_token) per task type in `agents.py`; env var convention: `RECIPE_RESEARCH_API_TOKEN` |
| `source_url` on recipe data | Users can verify the original recipe source; preserves attribution | LOW | `RecipeData.source_url: str | None` — populated by recipe-research if the web source is found |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem useful but would harm the system in Phase 1 — either through scope creep, hidden complexity, or violating proven architectural decisions.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Automatic workflow retry on failure | Failed workflows look like bugs, not permanent failures | Retry without fixing the underlying cause (bad recipe query, API 500) produces the same failure again; compensating actions (undo a half-created recipe) require saga logic not justified in Phase 1 | Manual inspection via RQ Dashboard + failed registry; fix and re-enqueue manually |
| Agent-to-agent chaining (agents enqueue their own successors) | Seems more autonomous | Couples agents to workflow topology; adding a step requires editing multiple agents; breaks "agents know nothing about the sequence" invariant | Centralized task-runner advancement via `workflows.py` registry |
| Prompt content embedded in `agents.py` / code | Feels simpler initially | Prompts can't be iterated without a redeploy; no version history; evaluation infrastructure can't pin a version | Versioned markdown files + `AGENT_OVERRIDES_FILEPATH` runtime swap |
| Streaming responses back to Telegram | Real-time feedback feels polished | Telegram Bot API streaming is complex, requires maintaining open connections through the task queue, and breaks the queue's decoupled reply model | Send a complete formatted message via `send-notification`; acceptable latency for household tasks |
| Multi-household support | Needed eventually | Requires per-household API keys, auth routing, and conversation isolation; adds non-trivial complexity before the single-household model is validated | `household_id` field exists in all models as a forward-compatibility shim; static from env var in Phase 1 |
| Inline formatting in content agents | Content agents (recipe-research, recipe-load) could format their own output for Telegram | Couples content agents to the presentation layer; format changes require re-testing all agents | `send-notification` agent owns all Telegram formatting via `format-telegram-message` skill |
| Conversation-level memory (summarization / vector store) | Long-running household context | Adds a retrieval layer before the core pipeline is validated; over-engineering for Phase 1 | Window-based history (last X messages, configurable); sufficient for household question/answer and recipe addition |
| Web UI for task monitoring | RQ Dashboard is a dev tool | Building a custom UI before core functionality is proven wastes engineering time | RQ Dashboard (`rq-dashboard`) ships with RQ; zero implementation cost for job inspection |
| Real-time push notifications (proactive agent messages) | Agent could notify family about expiring groceries | Scheduler tool and scheduler API are designed for this; the infrastructure exists but requires planned scheduled tasks, not ad-hoc push | Use scheduler once Phase 1 is stable; don't bolt proactive logic onto Phase 1 agents |

---

## Feature Dependencies

```
[Telegram message receipt (Gateway)]
    └──requires──> [Message persistence (Postgres)]
    └──requires──> [handle-incoming-message task enqueue (Queue)]
                       └──requires──> [Redis + RQ queue (Task Runner)]
                                          └──requires──> [LLM Backend abstraction]
                                                             └──requires──> [Per-task prompt versioning]
                                                             └──requires──> [Skill lazy loading (read-skill tool)]

[Multi-step workflow (add-recipe)]
    └──requires──> [handle-incoming-message agent]
    └──requires──> [WorkflowRun / WorkflowRunStep models (Postgres)]
    └──requires──> [Workflow Registry (workflows.py)]
    └──requires──> [Task Runner workflow advancement hook]
                       └──requires──> [Accumulated artifacts persistence]
                                          └──requires──> [recipe-research agent]
                                          └──requires──> [recipe-load agent]
                                                             └──requires──> [Food/unit name resolution (household-manager-api tool)]
                                          └──requires──> [send-notification agent]
                                                             └──requires──> [format-telegram-message skill]
                                                             └──requires──> [send-notification tool (gateway)]

[LangWatch experiment scripts]
    └──requires──> [LangWatch + OTel instrumentation (on all agents)]
    └──requires──> [Prompt versioning (version pinned per experiment run)]

[Scheduler]
    └──enhances──> [Task Queue] (adds deferred and recurring trigger capability)
    └──requires──> [Two separate RQ workers (scheduler-worker + task-runner)]
```

### Dependency Notes

- **Workflow advancement requires Task Runner hook:** The task runner must wrap job execution — not just run it — to persist artifacts and enqueue next steps. This is the most critical integration point in the entire system.
- **send-notification requires reply_context from WorkflowRun.shared_context:** The task runner builds `SendNotificationInput` from shared context, not from prior step outputs. This is a deliberate decoupling — intermediate agents must not carry reply context.
- **format-telegram-message skill requires send-notification agent:** Formatting is applied by the Notification agent at delivery time. If the formatting skill is wrong, all notifications break. It must be validated via an experiment script before wiring the full workflow.
- **recipe-load requires food/unit name resolution:** The recipe-load agent must call `/api/foods?name=` and `/api/units?name=` before creating a recipe. If the household-manager API lacks a food or unit, the load either fails or creates a recipe with missing ingredient details. The agent must handle both gracefully.
- **LangWatch instrumentation must be active during experiments:** Experiments that bypass instrumentation produce traces invisible to the experiment collection in LangWatch, making evaluation meaningless. Instrumentation is a hard dependency for the experiment infrastructure.

---

## MVP Definition

### Launch With (v1 — Phase 1)

Everything needed for both user stories to work end-to-end.

- [ ] Gateway: receive Telegram message, persist, fetch history, enqueue `handle-incoming-message` — the entry point for all user interaction
- [ ] Task queue: Redis + RQ, single worker, Pydantic input/output models, AOF persistence — the backbone; nothing works without it
- [ ] `handle-incoming-message` agent: understands intent, answers directly or starts workflow — the main routing brain
- [ ] `send-notification` agent: formats and sends Telegram reply — closes the user feedback loop
- [ ] `format-telegram-message` skill: correct Telegram MarkdownV2 escaping — prevents silently dropped messages
- [ ] `household-manager-api` tool: authenticated API calls to household-manager — enables recipe/meal-plan queries
- [ ] `start-workflow` tool: creates `WorkflowRun` + steps, enqueues first step — enables multi-step delegation
- [ ] `WorkflowRun` / `WorkflowRunStep` models + workflow advancement hook in task runner — the orchestration layer
- [ ] `recipe-research` agent: web search via Tavily, produces structured `RecipeData` — the research capability
- [ ] `recipe-load` agent: resolves food/unit names to IDs, creates recipe via API — persists the research output
- [ ] LangWatch + OTel instrumentation on all agents — required for debugging LLM failures in production

### Add After Validation (v1.x)

- [ ] Scheduler worker + scheduler API — add when users need proactive or recurring tasks (triggered by need, not speculation)
- [ ] Experiment scripts for recipe-research, recipe-load, send-notification — technically Phase 1 deliverables but don't block the user-facing workflows; add during agent implementation phases
- [ ] RQ Dashboard — zero-implementation (just install); add when first debugging session reveals the need

### Future Consideration (v2+)

- [ ] Multi-household support — defer until single-household model is validated; `household_id` field is already a shim
- [ ] Additional workflow types (grocery ordering, meal plan generation) — defer until add-recipe workflow is proven
- [ ] Streaming responses — defer indefinitely; complexity not justified for household assistant use case
- [ ] Conversation-level memory (summarization, embeddings) — defer until window-based history proves insufficient
- [ ] Additional messaging platforms (WhatsApp, Slack) — gateway abstraction supports it; don't implement until there is a concrete user need

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Gateway: Telegram receive + persist | HIGH | LOW | P1 |
| Task queue (Redis + RQ, single worker) | HIGH | LOW | P1 |
| `handle-incoming-message` agent | HIGH | MEDIUM | P1 |
| `send-notification` agent + format skill | HIGH | LOW | P1 |
| `household-manager-api` tool (authenticated) | HIGH | LOW | P1 |
| Workflow infrastructure (WorkflowRun models + advancement hook) | HIGH | HIGH | P1 |
| `recipe-research` agent (Tavily web search) | HIGH | MEDIUM | P1 |
| `recipe-load` agent (name→ID resolution + API create) | HIGH | MEDIUM | P1 |
| LangWatch instrumentation | MEDIUM | MEDIUM | P1 |
| Prompt versioning + runtime override | MEDIUM | LOW | P1 |
| Skill lazy loading | MEDIUM | LOW | P1 |
| `start-workflow` tool | HIGH | LOW | P1 |
| Redis AOF persistence | HIGH | LOW | P1 |
| Message deduplication (`platform_message_id`) | HIGH | LOW | P1 |
| Scheduler worker + API | LOW | MEDIUM | P2 |
| Experiment scripts (3 task types) | MEDIUM | MEDIUM | P2 |
| RQ Dashboard | MEDIUM | LOW | P2 |
| Multi-household support | LOW | HIGH | P3 |
| Streaming responses | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for Phase 1 launch
- P2: Should have, add during Phase 1 agent implementation phases
- P3: Future consideration (v2+)

---

## Competitor Feature Analysis

This is an internal household assistant, not a commercial product. "Competitors" are patterns from comparable AI assistant systems rather than market competitors.

| Feature | Generic ChatGPT wrapper | LangChain ReAct agent (no queue) | Robotina approach |
|---------|------------------------|----------------------------------|-------------------|
| Multi-step task execution | Relies on single-run tool chaining; brittle on long tasks | Single agent run with many tool calls; fails on timeout or context limit | Sequential task queue with specialized per-step agents; each step is independently recoverable |
| Observability | Black box unless vendor provides tracing | Depends on LangSmith or manual logging | LangWatch + OTel on every agent; per-experiment trace collection |
| Prompt iteration | Redeploy required | Redeploy required | Runtime override via `AGENT_OVERRIDES_FILEPATH`; versioned prompt files |
| Message platform coupling | Usually hardcoded | Usually hardcoded | Gateway abstraction; `platform` field in models; only gateway knows about Telegram |
| Data persistence | Ephemeral or vendor-managed | Ephemeral in-memory | Postgres for conversations + workflow state; Redis AOF for task queue |
| Workflow failure handling | Retry everything or fail silently | No concept of multi-run workflows | Explicit FAILED status propagation; dead-letter queue for inspection |

---

## Behavioral Expectations by Subsystem

### Agent Reliability

- An agent that calls a tool and receives a 400 validation error **must** attempt to correct its request using the error message and retry — not surface the error to the user raw. The spec explicitly states "the agent can recover by understanding the mistake and retrying with different parameters or a different tool."
- A `401` or `403` from the household-manager API is **unrecoverable** — the tool raises a hard error immediately; this response must never be passed back to the LLM as a recoverable signal.
- An agent that exhausts retries or encounters an unrecoverable error fails the job, landing it in RQ's failed registry.

### Workflow Observability

- Every `WorkflowRunStep` carries `started_at`, `completed_at`, and `status` — sufficient to diagnose where a workflow stalled.
- `artifact` on each completed step is the full structured output, enabling post-mortem inspection of what data flowed through the workflow.
- The task runner must log workflow state transitions (step started, step completed, step failed, workflow done, workflow failed) at the same verbosity level as task queue events.

### Telegram Formatting Quirks

- Telegram MarkdownV2 requires escaping of: `. ! ( ) - _ * [ ] { } # + = | ~ > ^`
- Unescaped special characters in MarkdownV2 cause the entire message to be rejected silently (the API returns success but the message is not displayed).
- The `format-telegram-message` skill must be a standalone verification step (the `send-notification` agent) — content agents must not attempt to format their own output.
- Links in Telegram MarkdownV2 use `[text](url)` format; parentheses in URLs must be escaped.
- The `send-notification` agent receives pre-written text and only reformats it — it does not compose content. This separation means format bugs don't corrupt content.

### Recipe Data Quality

- `RecipeData` uses human-readable names (`food_name`, `unit_name`) not IDs. The recipe-load agent is responsible for the name→ID resolution step.
- Food and unit names from web-scraped recipes may not match household-manager's canonical names (e.g., "egg" vs. "Huevo"). The recipe-load agent must handle partial matches and zero matches gracefully.
- `GET /api/foods?name=` is a case-insensitive substring match — use specific enough names to avoid ambiguous matches (e.g., "tomate" matches both "Tomate" and "Tomate cherry").
- `source_url` is optional but important for recipe attribution; the recipe-research agent should populate it when the web source URL is clearly identifiable.
- `RecipeStep.title` is optional; the research agent should populate it when the recipe source has titled steps, leave it null otherwise.
- `servings_qty` + `servings_unit` should be extracted as separate fields (e.g., `4` + `"porciones"`), not merged into a single string.

---

## Sources

- `plans/01-kickoff/spec.md` — Primary authoritative source; all feature descriptions derive directly from this spec (HIGH confidence)
- `agent/skills/household-manager/index.md` + `shared.md` — Existing skill implementation confirming household-manager API conventions (HIGH confidence)
- `.planning/PROJECT.md` — Project scope, constraints, and out-of-scope decisions (HIGH confidence)
- Training knowledge on RQ, LangChain, Telegram Bot API MarkdownV2 behavior, and LangWatch patterns (MEDIUM confidence — consistent with spec design decisions)

---
*Feature research for: Robotina — AI home assistant agent (Phase 1)*
*Researched: 2026-03-25*
