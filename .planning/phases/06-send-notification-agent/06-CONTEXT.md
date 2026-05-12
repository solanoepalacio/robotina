# Phase 6: send-notification Agent - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the `send-notification` agent end-to-end: register it in `agents.py`, create the `format-telegram-message` skill, write the `send-notification/V001.md` prompt, implement `SendNotificationTool`, and implement the `experiments/send_notification.py` experiment script. The `hello-world` agent config and `hello-world-2step` workflow registry entries are removed here. No other agents change in this phase.

</domain>

<decisions>
## Implementation Decisions

### SendNotificationTool Interface
- **D-01:** `SendNotificationTool` uses **constructor injection** for recipient info. `run_task()` builds the tool as `SendNotificationTool(chat_id=task_input.chat_id, user_id=task_input.user_id, platform=task_input.platform)` before agent setup. The tool's input schema exposes only `formatted_text: str` — the agent's sole job is to apply the formatting skill and call the tool with the result. The agent never sees or reasons about routing.
- **D-02:** `SendNotificationTool._run(formatted_text: str)` calls `asyncio.run(send_message(chat_id=self.chat_id, text=formatted_text, user_id=self.user_id))` to bridge the sync tool context to the async `robotina.gateway.send.send_message()`. Returns the `platform_message_id` string. `asyncio.run()` is safe here — RQ workers have no running event loop.

### agents.py Registry Update
- **D-03:** Remove the `"hello-world"` entry from `AGENT_REGISTRY` (Phase 4 placeholder, per D-06 in Phase 4 context). Register `"send-notification"` in its place with: skill `["format-telegram-message"]`, tool `[SendNotificationTool]` (instantiated inside `run_task()` — not at module level), prompt `src/robotina/agent/prompts/send-notification/V001.md`.
- **D-04:** Remove the `"hello-world-2step"` entry from `WORKFLOW_REGISTRY` in `agent/workflows.py` (Phase 5 test placeholder, per D-04 in Phase 5 context). The `"add-recipe"` workflow entry stays unchanged.

### run_task() Wiring
- **D-05:** `run_task()` must handle `SendNotificationInput` specifically: before building tools, check if `task_type == "send-notification"` and instantiate `SendNotificationTool` with recipient fields from `task_input`. Pass this instance in `config.tools` list override or inject directly into the `tools` list before agent creation. The `_extract_user_message()` fallback (`task_input.text`) already works for `SendNotificationInput` — no change needed there.

### Experiment Script
- **D-06:** `experiments/send_notification.py` hardens to a real implementation that runs the agent against **four representative inputs**, each targeting a different failure mode:
  1. Short plain text — `"The recipe has been saved successfully."` — baseline happy path
  2. Recipe notification — `"Recipe added: Spaghetti Carbonara. Servings: 4, prep 10 min, cook 20 min."` — structured data formatting
  3. Bullet list — `"This week's meal plan: Monday pasta, Tuesday soup, Wednesday salad, Thursday stir fry, Friday pizza."` — list formatting
  4. Special chars stress test — `"Ready in 30 min! (serves 4) — cost: ~€8.50"` — MarkdownV2 escaping of `.`, `!`, `(`, `)`, `-`, `~`
- **D-07:** Experiment pins prompt version and model config via LangWatch tags/metadata on each trace (per OBS-04). Uses the same LangWatch instrumentation path as `run_task()` (not a separate pipeline).

### Claude's Discretion
- `format-telegram-message` skill sub-files: what sub-files to create beyond `index.md` (e.g., `rules.md`, `examples.md`, `special-chars.md`) and their content depth
- `send-notification/V001.md` prompt content — tone, instructions for reformatting-only behavior
- Exact `SendNotificationTool` field names and `asyncio.run()` error handling
- Experiment evaluation criteria wording and how to surface pass/fail in output

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### send-notification spec
- `plans/01-kickoff/spec.md` §"send-notification" (line ~358) — `SendNotificationInput` / `SendNotificationOutput` verbatim definitions
- `plans/01-kickoff/spec.md` §"Tools" (line ~550) — `send-notification` tool description: sends message via gateway
- `plans/01-kickoff/spec.md` §"Skills" (line ~560) — `format-telegram-message` skill description: formatting instructions for Telegram
- `plans/01-kickoff/spec.md` §"Agents" (line ~773) — Notification agent config: skill, prompt, tool, experiment

### Requirements
- `.planning/REQUIREMENTS.md` §NOTIF-01 through NOTIF-05 — all notification agent acceptance criteria
- `.planning/REQUIREMENTS.md` §OBS-03, OBS-04, OBS-05 — LangWatch experiment requirements: same instrumentation as production, LangWatch tags, standalone script

### Prior context (locked decisions)
- `.planning/phases/04-llm-module-and-agent-infrastructure/04-CONTEXT.md` — D-06 (remove hello-world when send-notification added), D-07 (API token env var pattern: `SEND_NOTIFICATION_API_TOKEN`)
- `.planning/phases/05-task-runner-and-workflow-engine/05-CONTEXT.md` — D-04 (remove hello-world-2step workflow entry), D-03 (add-recipe workflow build_input uses `SendNotificationInput` — already in task_types.py)

### Existing code the planner must read
- `src/robotina/queue/task_types.py` — `SendNotificationInput` / `SendNotificationOutput` already defined
- `src/robotina/gateway/send.py` — `send_message(chat_id, text, user_id) -> str` already implemented; async function
- `src/robotina/agent/agents.py` — hello-world entry to remove; send-notification to add
- `src/robotina/agent/workflows.py` — hello-world-2step entry to remove
- `src/robotina/queue/jobs.py` — `run_task()` and `_extract_user_message()` — tool injection point for SendNotificationTool
- `src/robotina/agent/tools/start_workflow.py` — `BaseTool` subclass pattern to follow for `SendNotificationTool`
- `experiments/send_notification.py` — stub to replace with real implementation

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/robotina/gateway/send.py`: `send_message(chat_id, text, user_id) -> str` — fully implemented, async. Sends Telegram message, persists `StoredMessage` with `role=ASSISTANT`. Returns `platform_message_id`.
- `src/robotina/agent/tools/start_workflow.py`: `StartWorkflowTool` — `BaseTool` subclass with constructor injection pattern. Direct template for `SendNotificationTool`.
- `src/robotina/queue/task_types.py`: `SendNotificationInput(platform, chat_id, user_id, text)` and `SendNotificationOutput(message_id)` — ready to use, no changes needed.
- `src/robotina/queue/jobs.py`: `_extract_user_message()` returns `task_input.text` — works for `SendNotificationInput.text` without modification.

### Established Patterns
- All per-job objects instantiated inside `run_task()`, never at module level (locked Phase 4)
- `BaseTool` subclass with constructor injection for tool state (from `StartWorkflowTool`)
- Skills at `src/robotina/agent/skills/<skill-name>/` with `index.md` + sub-files
- Prompts at `src/robotina/agent/prompts/<task-type>/V001.md`
- `asyncio.run()` is safe from RQ worker context (no event loop running)
- LangWatch experiment traces: same `langwatch.trace()` + `LangChainTracer()` path used in `run_task()`

### Integration Points
- `run_task()` in `jobs.py` must inject `SendNotificationTool` instance into the tools list before agent creation — only for `task_type == "send-notification"` (or handled via a tool-factory pattern in `agents.py`)
- `format-telegram-message` skill is loaded via `SkillSet` by `run_task()` when `config.skills` lists it — no special wiring needed
- `SEND_NOTIFICATION_API_TOKEN` env var provides the API token (env var name convention from D-07, Phase 4)

</code_context>

<specifics>
## Specific Ideas

- Tool injection: `SendNotificationTool` requires `task_input` fields at construction — `run_task()` needs a way to pass them. The simplest approach: after `get_agent_config()`, if `task_type == "send-notification"`, instantiate `SendNotificationTool` from `task_input` and append it to a local `tools` list override (don't mutate the `AgentConfig`).
- `asyncio.run()` bridges the sync tool to the async `send_message()` — this is the canonical bridge for RQ workers.
- Experiment should print a summary of each run (input, formatted output, pass/fail on character escaping) — makes evaluation legible without opening LangWatch.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 06-send-notification-agent*
*Context gathered: 2026-03-27*
