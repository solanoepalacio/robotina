# Phase 7: handle-incoming-message Agent - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the Robotina routing agent end-to-end: register `handle-incoming-message` in `agents.py`, implement the `household-manager-api` tool and `queue` tool, wire both into `run_task()` with constructor injection from `task_input`, write `robotina/V001.md`, and update the `household-manager` skill (`shared.md` full rewrite removing all auth references). `StartWorkflowTool` is already implemented (Phase 5) — just wire it in. No experiment script for this agent (direct-reply path is validated end-to-end by the gateway integration).

</domain>

<decisions>
## Implementation Decisions

### queue tool
- **D-01:** `QueueTool` (or `queue` tool name) takes **text only** as its input (`text: str`). The tool is hardcoded to enqueue a `send-notification` task — no task_type parameter exposed. Recipient context (`chat_id`, `user_id`, `platform`) is injected at construction inside `run_task()`, same pattern as `SendNotificationTool`. The tool builds `SendNotificationInput` internally and enqueues it to the `agent-tasks` queue. Returns `job_id` string so the caller can populate `IncomingMessageOutput.queued_task_ids`.

### household-manager-api tool
- **D-02:** Generic HTTP client: `_run(method: str, path: str, body: dict | None, query: dict | None)`. The agent uses the `household-manager` skill to know which endpoints to call and composes requests accordingly. `household_id` is injected at construction from `task_input.household_id` — agent never sees it. The tool prepends `household_id` as a path or query param automatically where the spec requires it (clarify from skill/spec at implementation time). API token read from `HOUSEHOLD_MANAGER_API_TOKEN` env var (follows the `{TASK_TYPE}_API_TOKEN` convention… but this is a shared tool across multiple agents — implementation should use its own dedicated env var `HOUSEHOLD_MANAGER_API_KEY` to avoid confusion). `401`/`403` → raise hard `RuntimeError` that stops the agent loop; all other non-2xx → return structured error dict to agent so it can recover or report.

### agents.py Registry
- **D-03:** Register `handle-incoming-message` in `AGENT_REGISTRY` with: skills `["household-manager"]`, tools `[]` (all three tools injected per-job in `run_task()`), prompt `src/robotina/agent/prompts/robotina/V001.md`, model config following same env-var pattern (`HANDLE_INCOMING_MESSAGE_API_TOKEN`).

### run_task() wiring
- **D-04:** For `task_type == "handle-incoming-message"`, inject inside `run_task()`:
  1. `HouseholdManagerApiTool(household_id=task_input.household_id)` — constructed per-job
  2. `QueueTool(chat_id=task_input.chat_id, user_id=task_input.user_id, platform=task_input.platform)` — constructed per-job
  3. `StartWorkflowTool()` — already implemented, no per-job injection needed (it reads REDIS_URL and creates its own session)
  All three appended to the local `tools` list before agent creation.

### Routing Prompt (robotina/V001.md)
- **D-05:** The prompt states the general routing principle **and** gives concrete examples of each path:
  - Principle: "If the user's request can be answered directly (questions about household data, current meal plan, recipe lookup) → use the `queue` tool to send the answer. If the request requires a multi-step workflow (researching and saving a new recipe) → use the `start-workflow` tool."
  - Direct-reply examples: "what's on the meal plan?", "find me a pasta recipe", "when does the meal plan end?"
  - Workflow examples: "add a recipe for spaghetti carbonara", "save this recipe", "find and add a new dessert recipe"
  - The prompt does NOT enumerate workflow names by key — that leaks implementation detail. The agent uses the `start-workflow` tool description to know what workflow types are available.

### household-manager skill update
- **D-06:** Full rewrite of `shared.md`. Remove: entire "Authentication" section (auth header instructions), 401 and 403 rows from the error table (agent will never see those — they become hard errors in the tool). Keep: Base URL convention, remaining error codes (400, 404, 422, 500) with their meanings, pagination envelope if present. Restructure to be cleaner without the auth scaffolding. Other skill files (`recipes_get.md`, `meal_plan.md`, etc.) are unchanged — they don't contain auth references.

### Claude's Discretion
- Exact `HouseholdManagerApiTool` field names and how household_id is applied per-request (path prefix, query param, or header — check actual household-manager API spec)
- Whether `QueueTool` returns just the job_id string or a more verbose confirmation
- Exact V001.md prompt wording, tone, and length
- Whether `IncomingMessageOutput` is explicitly constructed in `run_task()` (wrapping the agent result) or left as the raw messages list for Phase 7 — either is acceptable

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Robotina agent spec
- `plans/01-kickoff/spec.md` §"Robotina Agent (handle-incoming-message)" (~line 780) — skills, tools, prompt path
- `plans/01-kickoff/spec.md` §"Tools" (~line 551) — `household-manager-api` tool description (auth injection, 401/403 hard error), `queue` tool description, `start-workflow` already exists
- `plans/01-kickoff/spec.md` §"Skills" (~line 560) — `household-manager` skill description (auth update note)

### Requirements
- `.planning/REQUIREMENTS.md` §ROBOT-01 through ROBOT-07 — all acceptance criteria for this phase

### Existing code the planner must read
- `src/robotina/agent/agents.py` — `AGENT_REGISTRY` and `AgentConfig` pattern; add `handle-incoming-message` entry
- `src/robotina/queue/jobs.py` — `run_task()` tool injection pattern (see Phase 6 block for `send-notification`); extend for `handle-incoming-message`
- `src/robotina/queue/task_types.py` — `IncomingMessageInput` fields (message_id, platform, chat_id, user_id, household_id, text, history) and `IncomingMessageOutput`
- `src/robotina/agent/tools/start_workflow.py` — `StartWorkflowTool` already implemented; use as template for new tools
- `src/robotina/agent/tools/send_notification.py` — constructor injection pattern for per-job context
- `src/robotina/agent/skills/household-manager/shared.md` — file to rewrite (remove auth section + 401/403)
- `src/robotina/agent/skills/household-manager/index.md` — update if it mentions auth instructions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `StartWorkflowTool` (`src/robotina/agent/tools/start_workflow.py`): fully implemented, creates `WorkflowRun` + all steps, enqueues first job, returns `workflow_run_id`. Just add to handle-incoming-message tools list.
- `SendNotificationTool` (`src/robotina/agent/tools/send_notification.py`): constructor injection pattern template for `QueueTool`.
- `run_task()` in `jobs.py`: the Phase 6 `if task_type == "send-notification"` block is the exact pattern to extend for `handle-incoming-message` tool injection.
- `IncomingMessageInput` already has all fields needed for tool construction: `chat_id`, `user_id`, `platform`, `household_id`.
- `household-manager` skill directory (`src/robotina/agent/skills/household-manager/`): 7 files; only `shared.md` (and possibly `index.md`) need updating.

### Established Patterns
- All per-job tools constructed inside `run_task()`, never at module level (locked Phase 4)
- `BaseTool` subclass with constructor fields for per-job state (`chat_id`, `user_id`, etc.)
- `asyncio.run()` for bridging sync tool to async gateway calls (established in SendNotificationTool)
- Skills: `index.md` pre-loaded into prompt; sub-files loaded on demand via `read-skill` tool
- Prompts at `src/robotina/agent/prompts/<task-type>/V001.md`
- Model API token: env var named `{TASK_TYPE_UPPER}_API_TOKEN` — but `household-manager-api` tool uses a shared `HOUSEHOLD_MANAGER_API_KEY` (separate from per-task tokens)

### Integration Points
- `run_task()` dispatches all task types via the same function — new tools for `handle-incoming-message` follow the `if task_type == "handle-incoming-message"` injection block
- `household-manager` skill loaded via `SkillSet` automatically when listed in `AgentConfig.skills` — no special wiring needed for the skill itself
- `AGENT_REGISTRY` lookup in `get_agent_config()` — add `handle-incoming-message` entry with model config, prompt path, skills

</code_context>

<specifics>
## Specific Ideas

- Routing prompt: state principle + examples, but don't enumerate workflow keys by name in the prompt — the `start-workflow` tool description should convey available workflow types
- shared.md rewrite: clean slate removing auth scaffolding; keep base URL, keep error codes for recoverable errors (400, 404, 422, 500)
- `QueueTool` text-only interface: agent calls it like `queue(text="Here is your meal plan: ...")` — recipient context invisible

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 07-handle-incoming-message-agent*
*Context gathered: 2026-03-27*
