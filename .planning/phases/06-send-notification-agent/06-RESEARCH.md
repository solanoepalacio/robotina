# Phase 6: send-notification Agent - Research

**Researched:** 2026-03-27
**Domain:** LangChain agent implementation, Telegram MarkdownV2 formatting, LangWatch experiment scripting
**Confidence:** HIGH

## Summary

Phase 6 is a focused implementation phase with minimal discovery risk. The infrastructure built in Phases 4 and 5 handles everything except the three new artifacts: `SendNotificationTool`, the `format-telegram-message` skill, and the `send-notification/V001.md` prompt. All integration points are already established and the canonical code patterns (BaseTool constructor injection, SkillSet loading, run_task tool injection) exist in the repo.

The single non-trivial technical concern is Telegram MarkdownV2 escaping. The agent's job is to transform plain text into valid MarkdownV2 — this means the skill must teach escaping rules precisely, and the experiment must stress-test the four failure modes identified in D-06. The `send_message()` gateway function already sends via `Bot.send_message(text=..., parse_mode=...)` with no parse_mode argument currently set, which means the planner must verify whether MarkdownV2 parse_mode needs to be added to the gateway call or passed as a parameter.

The second concern is tool injection: `SendNotificationTool` requires `chat_id`, `user_id`, and `platform` from the `task_input` at construction time, but `AgentConfig.tools` is a static list. The locked decision (D-05) is to instantiate `SendNotificationTool` inside `run_task()` after `get_agent_config()` returns, when `task_type == "send-notification"`, then append it to the local `tools` list before agent creation. This is safe, clean, and does not mutate `AgentConfig`.

**Primary recommendation:** Follow the `StartWorkflowTool` constructor-injection pattern exactly for `SendNotificationTool`. Keep the skill sub-files lean: `index.md` (overview + file list), `escaping.md` (MarkdownV2 character rules), `formatting.md` (bold, italic, code, links, bullets in MarkdownV2), and `examples.md` (before/after pairs for common notification messages).

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: SendNotificationTool Interface**
`SendNotificationTool` uses constructor injection for recipient info. `run_task()` builds the tool as `SendNotificationTool(chat_id=task_input.chat_id, user_id=task_input.user_id, platform=task_input.platform)` before agent setup. The tool's input schema exposes only `formatted_text: str` — the agent's sole job is to apply the formatting skill and call the tool with the result. The agent never sees or reasons about routing.

**D-02: SendNotificationTool._run**
`SendNotificationTool._run(formatted_text: str)` calls `asyncio.run(send_message(chat_id=self.chat_id, text=formatted_text, user_id=self.user_id))` to bridge the sync tool context to the async `robotina.gateway.send.send_message()`. Returns the `platform_message_id` string. `asyncio.run()` is safe here — RQ workers have no running event loop.

**D-03: agents.py Registry Update**
Remove the `"hello-world"` entry from `AGENT_REGISTRY`. Register `"send-notification"` in its place with: skill `["format-telegram-message"]`, tool `[SendNotificationTool]` (instantiated inside `run_task()` — not at module level), prompt `src/robotina/agent/prompts/send-notification/V001.md`.

**D-04: workflows.py Registry Update**
Remove the `"hello-world-2step"` entry from `WORKFLOW_REGISTRY` in `agent/workflows.py`.

**D-05: run_task() Wiring**
`run_task()` must handle `SendNotificationInput` specifically: before building tools, check if `task_type == "send-notification"` and instantiate `SendNotificationTool` with recipient fields from `task_input`. Pass this instance in the tools list override. The `_extract_user_message()` fallback (`task_input.text`) already works for `SendNotificationInput` — no change needed there.

**D-06: Experiment Script Inputs**
`experiments/send_notification.py` runs the agent against four representative inputs:
1. `"The recipe has been saved successfully."` — baseline happy path
2. `"Recipe added: Spaghetti Carbonara. Servings: 4, prep 10 min, cook 20 min."` — structured data formatting
3. `"This week's meal plan: Monday pasta, Tuesday soup, Wednesday salad, Thursday stir fry, Friday pizza."` — list formatting
4. `"Ready in 30 min! (serves 4) — cost: ~€8.50"` — MarkdownV2 escaping of `.`, `!`, `(`, `)`, `-`, `~`

**D-07: LangWatch Experiment Tags**
Experiment pins prompt version and model config via LangWatch tags/metadata on each trace (per OBS-04). Uses the same LangWatch instrumentation path as `run_task()` (not a separate pipeline).

### Claude's Discretion
- `format-telegram-message` skill sub-files: what sub-files to create beyond `index.md` (e.g., `rules.md`, `examples.md`, `special-chars.md`) and their content depth
- `send-notification/V001.md` prompt content — tone, instructions for reformatting-only behavior
- Exact `SendNotificationTool` field names and `asyncio.run()` error handling
- Experiment evaluation criteria wording and how to surface pass/fail in output

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NOTIF-01 | `send-notification` task type is handled by the Notification agent | `"send-notification"` added to `AGENT_REGISTRY` in `agents.py`; `hello-world` removed |
| NOTIF-02 | `format-telegram-message` skill exists with `index.md` and sub-files covering Telegram MarkdownV2 formatting rules | New skill directory at `src/robotina/agent/skills/format-telegram-message/`; SkillSet infrastructure already handles loading |
| NOTIF-03 | Notification agent applies `format-telegram-message` skill to reformat pre-written text before delivery — it does not compose content | Enforced via the V001.md prompt instruction; `SendNotificationInput.text` carries the pre-written text; `_extract_user_message()` already returns it |
| NOTIF-04 | `send-notification` tool sends the formatted message to the user via the gateway | `SendNotificationTool._run()` calls `asyncio.run(send_message(...))` which sends and persists; already implemented in `gateway/send.py` |
| NOTIF-05 | `send-notification/V001.md` system prompt exists | New file at `src/robotina/agent/prompts/send-notification/V001.md` |
| OBS-03 | The same instrumentation used in production is active during experiment runs; traces appear in the correct LangWatch experiment collection | Experiment uses `langwatch.trace()` + `LangChainTracer()` identical to `run_task()` path |
| OBS-05 | A standalone experiment script (`experiments/send_notification.py`) exists for the send-notification agent | Existing stub at `experiments/send_notification.py` replaced with full implementation |
</phase_requirements>

---

## Standard Stack

### Core (all pre-installed via Phase 4)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `langchain-core` | `>=0.3` | `BaseTool` base class for `SendNotificationTool` | Already installed |
| `langgraph` | `>=0.2` | `create_react_agent` — agent runtime | Already in use |
| `langwatch` | `>=0.1` | `langwatch.trace()` context manager for experiment traces | Already instrumented in `run_task()` |
| `python-telegram-bot` | `>=21` | `Bot.send_message()` called by `gateway/send.py` | Already installed; used via `asyncio.run()` bridge |
| `pydantic` | `v2 (>=2.7)` | Field declarations on `SendNotificationTool` | Already in use |

No new dependencies are required for this phase.

**Installation:** No `uv add` needed — all dependencies already in `pyproject.toml`.

---

## Architecture Patterns

### Recommended Project Structure Additions
```
src/robotina/agent/
├── skills/
│   ├── household-manager/     # existing
│   └── format-telegram-message/   # NEW
│       ├── index.md           # overview + sub-file map
│       ├── escaping.md        # MarkdownV2 character escape rules (full table)
│       ├── formatting.md      # bold, italic, code, links, bullets, block syntax
│       └── examples.md        # before/after pairs for notification messages
├── prompts/
│   ├── hello-world/           # REMOVE in Phase 6
│   └── send-notification/     # NEW
│       └── V001.md
└── tools/
    ├── start_workflow.py      # existing — canonical pattern to follow
    └── send_notification.py   # NEW — SendNotificationTool

experiments/
└── send_notification.py      # REPLACE stub with full implementation
```

### Pattern 1: BaseTool with Constructor Injection (for SendNotificationTool)

This pattern is already used by `StartWorkflowTool` in `src/robotina/agent/tools/start_workflow.py`. Follow it exactly.

```python
# src/robotina/agent/tools/send_notification.py
import asyncio
import logging
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class SendNotificationTool(BaseTool):
    name: str = "send-notification"
    description: str = (
        "Send the formatted message to the user via the gateway. "
        "Call this after applying the format-telegram-message skill. "
        "Args: formatted_text (str) — the MarkdownV2-formatted message to send."
    )

    # Injected at construction — agent never sees these
    chat_id: str
    user_id: str
    platform: str  # "telegram"

    def _run(self, formatted_text: str) -> str:
        """Send formatted_text via gateway. Returns platform_message_id."""
        from robotina.gateway.send import send_message
        platform_message_id = asyncio.run(
            send_message(chat_id=self.chat_id, text=formatted_text, user_id=self.user_id)
        )
        logger.info("send-notification tool | message_id=%s", platform_message_id)
        return platform_message_id

    async def _arun(self, formatted_text: str) -> str:
        return self._run(formatted_text)
```

**Confirmed safe:** `asyncio.run()` in the sync `_run()` context is safe because RQ workers run in forked processes with no event loop (confirmed decision D-02, CONTEXT.md).

### Pattern 2: Tool Injection in run_task() for Recipient-Bound Tools

`AgentConfig.tools` is a static list — it cannot hold per-job state. The correct injection point is inside `run_task()` after `get_agent_config()`:

```python
# In run_task(), after: tools = list(config.tools)
if task_type == "send-notification":
    from robotina.agent.tools.send_notification import SendNotificationTool
    tools.append(SendNotificationTool(
        chat_id=task_input.chat_id,
        user_id=task_input.user_id,
        platform=task_input.platform,
    ))
```

This does NOT mutate `AgentConfig`. The local `tools` list is used only for this job invocation.

### Pattern 3: SkillSet Loading (no changes required)

`SkillSet` loads `index.md` automatically when the skill name is in `config.skills`. No code changes needed — just create the `format-telegram-message/` skill directory with the right files, and list it in the `AgentConfig`.

```python
# In agents.py AGENT_REGISTRY:
"send-notification": AgentConfig(
    task_type="send-notification",
    model_config={
        "provider": "ollama",  # or anthropic/openai per deployment
        "url": "http://localhost:11434",
        "model": "...",
        "api_key_env": "SEND_NOTIFICATION_API_TOKEN",
    },
    prompt_path="src/robotina/agent/prompts/send-notification/V001.md",
    skills=["format-telegram-message"],
    tools=[],  # SendNotificationTool is injected per-job in run_task()
),
```

Note: `tools=[]` in `AgentConfig` for `send-notification` because `SendNotificationTool` is per-job (has `chat_id`, `user_id`). The tool is injected in `run_task()` instead.

### Pattern 4: LangWatch Experiment Script

The experiment script must use the same `langwatch.trace()` + `LangChainTracer()` path as `run_task()`. The OBS-03 requirement is that experiment instrumentation is **identical to production** — no separate pipeline.

```python
# experiments/send_notification.py
import langwatch
import langwatch.langchain
from langchain_core.runnables import RunnableConfig

def run_experiment_case(agent, text: str, label: str) -> dict:
    """Run one case and return result dict."""
    with langwatch.trace() as trace:
        trace.update(metadata={
            "prompt_version": "V001",
            "experiment_label": label,
        })
        result = agent.invoke(
            {"messages": [{"role": "user", "content": text}]},
            config=RunnableConfig(
                callbacks=[langwatch.langchain.LangChainTracer()]
            ),
        )
    return result
```

Tags/metadata pinning follows `langwatch.trace().update(metadata={...})` — same approach as production would use for experiment collections.

### Anti-Patterns to Avoid

- **Module-level tool instantiation:** `SendNotificationTool(chat_id="...")` at module load time is forbidden (Phase 4 architectural constraint). Always instantiate inside `run_task()`.
- **Mutating `AgentConfig.tools`:** Append to a local `tools = list(config.tools)` copy; never mutate the registry object.
- **Calling `asyncio.get_event_loop().run_until_complete()`:** Use `asyncio.run()` — it creates a fresh event loop each call and is safe in the RQ worker subprocess.
- **Sending message without `parse_mode`:** If the skill instructs the agent to produce MarkdownV2, the gateway call must pass `parse_mode="MarkdownV2"` to `bot.send_message()`. The current `gateway/send.py` does NOT include `parse_mode` — this is an open question (see below).
- **Removing `hello-world` from AGENT_REGISTRY without updating tests:** Tests in `test_agents_registry.py` and `test_prompts.py` currently reference `hello-world`. These tests must be updated to reference `send-notification` instead.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async-to-sync bridge | Custom event loop management | `asyncio.run()` | Safe, stdlib, idiomatic for RQ workers |
| Skill file loading | Custom file reader | `SkillSet` + `ReadSkillTool` | Already implemented in `src/robotina/agent/__init__.py` |
| LLM agent execution | Custom chain | `create_react_agent` from `langgraph.prebuilt` | Locked per AGENT-11 |
| MarkdownV2 escaping at tool level | Escape logic in `SendNotificationTool._run()` | Teach it via the skill, have the agent apply it | The agent's job is formatting — the tool just sends |
| LangWatch trace context | Manual OTel span creation | `langwatch.trace()` context manager | Matches production instrumentation path |

**Key insight:** The escaping logic belongs in the skill (as LLM instructions), not in the tool. The tool is a dumb delivery mechanism — it sends whatever `formatted_text` it receives. Placing escape logic in the tool would bypass the agent's formatting responsibility.

---

## Common Pitfalls

### Pitfall 1: send_message() lacks parse_mode argument
**What goes wrong:** `bot.send_message(chat_id=..., text=...)` defaults to no parse mode. If the agent returns MarkdownV2-formatted text with backslash escapes, Telegram renders them literally as `\.` or `\!` instead of parsing them as MarkdownV2.
**Why it happens:** `gateway/send.py` was written before MarkdownV2 was in scope. It has no `parse_mode` parameter.
**How to avoid:** Either (a) add `parse_mode: str | None = None` parameter to `send_message()` and pass `parse_mode="MarkdownV2"` from `SendNotificationTool._run()`, or (b) hardcode `parse_mode="MarkdownV2"` inside `send_message()` (acceptable if gateway is always Telegram/MarkdownV2 in Phase 1). Decision left to planner per Claude's Discretion.
**Warning signs:** Messages appear with literal backslashes in Telegram; `BadRequest: Can't parse entities` error from Telegram API.

### Pitfall 2: Existing tests reference "hello-world" agent
**What goes wrong:** `tests/unit/test_agents_registry.py` has four tests that call `get_agent_config("hello-world")`. `tests/unit/test_prompts.py` has two tests referencing the `hello-world` prompt path. After `hello-world` is removed from `AGENT_REGISTRY`, these tests fail with `KeyError`.
**Why it happens:** The Phase 4 tests were written for the placeholder entry.
**How to avoid:** Update all `hello-world` references in the test files to `send-notification` as part of the same plan that removes the registry entry.

### Pitfall 3: SendNotificationTool in agents.py tools list
**What goes wrong:** If `SendNotificationTool` is instantiated at `AgentConfig` level (e.g., `tools=[SendNotificationTool()]`), it lacks `chat_id`/`user_id`, will fail at construction, or will be shared across jobs (violating the per-job constraint).
**Why it happens:** Natural tendency to put tool instances in the config where other tools would go.
**How to avoid:** Keep `tools=[]` in the `AgentConfig` for `send-notification`. The tool is injected per-job inside `run_task()`.

### Pitfall 4: MarkdownV2 special characters in experiment inputs
**What goes wrong:** The experiment input `"Ready in 30 min! (serves 4) — cost: ~€8.50"` contains `.`, `!`, `(`, `)`, `-`, `~` — all of which require MarkdownV2 escaping. If the skill doesn't teach this correctly, the agent may pass through unescaped characters, causing Telegram to return `BadRequest: Can't parse entities`.
**Why it happens:** MarkdownV2 has 18 characters that must be escaped: `_ * [ ] ( ) ~ ` > # + - = | { } . !` — more than most developers expect.
**How to avoid:** The `escaping.md` sub-file in the `format-telegram-message` skill must include a complete table of all 18 characters with their escaped forms (`\char`). The experiment is designed to surface this failure mode explicitly (D-06 case 4).

### Pitfall 5: asyncio.run() called from within an event loop
**What goes wrong:** If `SendNotificationTool._run()` is called from within an already-running async context (e.g., in a test using `pytest-asyncio`), `asyncio.run()` raises `RuntimeError: This event loop is already running`.
**Why it happens:** Test code may accidentally call `_run()` inside an async test function.
**How to avoid:** Keep tool tests synchronous. `asyncio.run()` is safe in the RQ worker subprocess (no event loop). For unit tests, mock `send_message` directly rather than calling the real async function.

---

## Code Examples

### Verified Pattern: gateway/send.py signature (existing)
```python
# Source: src/robotina/gateway/send.py (read 2026-03-27)
async def send_message(chat_id: str, text: str, user_id: str) -> str:
    """Returns platform_message_id (str)."""
    bot = Bot(token=token)
    async with bot:
        sent = await bot.send_message(chat_id=int(chat_id), text=text)
    # NOTE: parse_mode is NOT currently passed — must add for MarkdownV2
```

### Verified Pattern: BaseTool subclass with constructor fields (existing)
```python
# Source: src/robotina/agent/tools/start_workflow.py (read 2026-03-27)
class StartWorkflowTool(BaseTool):
    name: str = "start-workflow"
    description: str = "..."
    # No constructor-injected fields in StartWorkflowTool itself
    # SendNotificationTool adds: chat_id: str, user_id: str, platform: str
    def _run(self, ...): ...
    async def _arun(self, ...): ...
```

### Verified Pattern: run_task() tool list assembly (existing)
```python
# Source: src/robotina/queue/jobs.py lines 121-125 (read 2026-03-27)
tools = list(config.tools)
if skill_sets:
    tools.append(build_read_skill_tool(skill_sets))
# Phase 6 adds before agent creation:
# if task_type == "send-notification":
#     tools.append(SendNotificationTool(chat_id=..., user_id=..., platform=...))
```

### Verified Pattern: SendNotificationInput fields (existing)
```python
# Source: src/robotina/queue/task_types.py (read 2026-03-27)
class SendNotificationInput(BaseModel):
    platform: Literal["telegram"]
    chat_id: str
    user_id: str
    text: str  # pre-written; agent reformats, does not compose
```

### Verified Pattern: household-manager skill index.md structure (existing)
```markdown
# recipe-manager skill bundle
## Files
| File | Description |
|------|-------------|
| `shared.md` | ... |
## Usage
Read the relevant file before each operation class. Do not load all files at once.
```
The `format-telegram-message` skill `index.md` should follow this same structure.

### Telegram MarkdownV2 Characters Requiring Escape
All 18 characters must be escaped with `\` when they appear as literal text (not as formatting markers):
```
_ * [ ] ( ) ~ ` > # + - = | { } . !
```
Example: `"Ready in 30 min! (serves 4) — cost: ~€8.50"` becomes:
`"Ready in 30 min\! \(serves 4\) — cost: \~€8\.50"`

Source: Telegram Bot API official documentation (https://core.telegram.org/bots/api#markdownv2-style), HIGH confidence.

---

## Open Questions

1. **parse_mode for send_message()**
   - What we know: `gateway/send.py::send_message()` has no `parse_mode` parameter. The agent will produce MarkdownV2-formatted text. Telegram requires `parse_mode="MarkdownV2"` to interpret it.
   - What's unclear: Should `parse_mode` be added as a parameter to `send_message()` (more flexible), or hardcoded inside `send_message()` (simpler for Phase 1)?
   - Recommendation: Add `parse_mode: str = "MarkdownV2"` as a keyword-argument to `send_message()` with a default. Pass `parse_mode="MarkdownV2"` from `SendNotificationTool._run()`. This is backward-compatible (no callers currently pass it).

2. **LangWatch experiment collection vs. project — how to pin**
   - What we know: D-07 requires pinning prompt version and model config via LangWatch tags/metadata. `langwatch.trace()` supports `.update(metadata={...})`.
   - What's unclear: The exact API call to set experiment collection vs. trace metadata is version-dependent. LangWatch SDK is LOW confidence per prior research.
   - Recommendation: Use `langwatch.trace() as trace; trace.update(metadata={"prompt_version": "V001", "model": ...})` — this is the pattern documented by prior Phase 4 research. Verify against `langwatch` package installed version at implementation time.

---

## Environment Availability

All dependencies are pre-installed from Phases 1–5. This phase adds no new packages.

| Dependency | Required By | Available | Notes |
|------------|-------------|-----------|-------|
| `langchain-core` | `SendNotificationTool` (BaseTool) | Yes | Phase 4 |
| `langgraph` | `create_react_agent` | Yes | Phase 4 |
| `langwatch` | Experiment traces | Yes | Phase 4 |
| `python-telegram-bot` | `gateway/send.py` | Yes | Phase 3 |
| `redis`, `rq` | Task queue | Yes | Phase 2 |
| `sqlalchemy` | Session in send_message() | Yes | Phase 2 |

Step 2.6: No new external dependencies. All tooling pre-installed.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/unit/ -q` |
| Full suite command | `uv run pytest tests/ -q` |

### Current Test Baseline
100 tests collected; 96 passing, 4 failing (pre-existing failures unrelated to Phase 6):
- `test_gateway.py::test_history_window` — pre-existing
- `test_observability.py` x3 — pre-existing (LangWatch runner test)

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NOTIF-01 | `get_agent_config("send-notification")` returns valid `AgentConfig` | unit | `uv run pytest tests/unit/test_agents_registry.py -q` | Yes (needs update) |
| NOTIF-01 | `get_agent_config("hello-world")` raises `KeyError` (removed) | unit | `uv run pytest tests/unit/test_agents_registry.py -q` | Yes (needs update) |
| NOTIF-02 | `format-telegram-message` skill dir and `index.md` exist | unit | `uv run pytest tests/unit/test_skills.py -q` | Yes (existing skill tests cover infra; new test file needed for the skill file) |
| NOTIF-03 | `_extract_user_message(SendNotificationInput(...))` returns `task_input.text` | unit | `uv run pytest tests/unit/test_agent_runner.py -q` | Yes (logic exists; test may need update) |
| NOTIF-04 | `SendNotificationTool._run(formatted_text)` calls `send_message()` with correct args | unit | `uv run pytest tests/unit/test_send_notification_tool.py -q` | No — Wave 0 gap |
| NOTIF-04 | `run_task()` injects `SendNotificationTool` for `task_type="send-notification"` | unit | `uv run pytest tests/unit/test_agent_runner.py -q` | Partial — needs new test case |
| NOTIF-05 | `src/robotina/agent/prompts/send-notification/V001.md` exists and is non-empty | unit | `uv run pytest tests/unit/test_prompts.py -q` | Yes (needs update from hello-world) |
| OBS-03 | Experiment uses same `langwatch.trace()` path as `run_task()` | manual | run `uv run experiments.send_notification` and verify trace in LangWatch | manual-only (live LangWatch needed) |
| OBS-05 | `experiments/send_notification.py` runs without error | smoke | `uv run experiments.send_notification` | Yes (stub exists; needs full impl) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/ -q`
- **Per wave merge:** `uv run pytest tests/ -q`
- **Phase gate:** Full suite green (excluding pre-existing failures) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_send_notification_tool.py` — covers NOTIF-04 (`SendNotificationTool` construction, `_run()` calls `send_message`, `asyncio.run()` bridge)
- [ ] Update `tests/unit/test_agents_registry.py` — replace `hello-world` references with `send-notification`
- [ ] Update `tests/unit/test_prompts.py` — replace `hello-world` prompt path test with `send-notification/V001.md`
- [ ] Update `tests/unit/test_agent_runner.py` — update `mock_job.meta = {"task_type": "hello-world"}` references if they break after registry swap (the mock doesn't call `get_agent_config` against the real registry, so this may be a no-op; verify at implementation time)

---

## Project Constraints (from CLAUDE.md)

All of the following directives apply to Phase 6 implementation:

| Directive | Impact on Phase 6 |
|-----------|-------------------|
| Tech Stack: Python, LangChain, Postgres, Redis+RQ, uv — no deviations | No new libraries; `SendNotificationTool` uses `langchain-core.BaseTool` |
| Concurrency: task runner sequential (concurrency=1) | No async agent invocation; `asyncio.run()` in tool is correct |
| LLM: Full connection details per task type; API tokens from env vars named by task type | `SEND_NOTIFICATION_API_TOKEN` env var (D-07, Phase 4 context) |
| Redis: AOF with `appendfsync always` | No change; already configured |
| Observability: LangWatch active in production AND experiment runs | Experiment must use identical `langwatch.trace()` + `LangChainTracer()` path |
| All per-job objects instantiated inside `run_task()` — never module level | `SendNotificationTool` instantiated inside `run_task()`, not in `AgentConfig` |
| `create_react_agent` from `langgraph.prebuilt` required; `AgentExecutor` forbidden | No change to agent creation; already correct |
| SQLAlchemy 2.x `Mapped` + `mapped_column` style | No new models in Phase 6 |
| `result_ttl=-1` and `failure_ttl=-1` on all RQ jobs | No new job enqueueing in Phase 6 |

---

## Sources

### Primary (HIGH confidence)
- `src/robotina/agent/tools/start_workflow.py` (read 2026-03-27) — canonical `BaseTool` constructor-injection pattern
- `src/robotina/gateway/send.py` (read 2026-03-27) — `send_message()` signature and current missing `parse_mode`
- `src/robotina/queue/jobs.py` (read 2026-03-27) — `run_task()` tool assembly and LangWatch invocation pattern
- `src/robotina/agent/agents.py` (read 2026-03-27) — `AgentConfig` fields, `hello-world` entry to remove
- `src/robotina/agent/workflows.py` (read 2026-03-27) — `hello-world-2step` entry to remove
- `src/robotina/queue/task_types.py` (read 2026-03-27) — `SendNotificationInput` / `SendNotificationOutput` field names
- `src/robotina/agent/__init__.py` (read 2026-03-27) — `SkillSet` / `ReadSkillTool` implementation
- `.planning/phases/06-send-notification-agent/06-CONTEXT.md` (read 2026-03-27) — locked decisions D-01 through D-07
- Telegram Bot API (https://core.telegram.org/bots/api#markdownv2-style) — 18 special characters requiring escape

### Secondary (MEDIUM confidence)
- WebSearch result (2026-03-27): Telegram MarkdownV2 special chars `_ * [ ] ( ) ~ \` > # + - = | { } . !` — confirmed consistent across multiple sources

### Tertiary (LOW confidence)
- LangWatch `trace().update(metadata=...)` API for experiment pinning — LOW; verify against installed `langwatch` version before implementation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all pre-installed; no new dependencies
- Architecture patterns: HIGH — BaseTool injection pattern verified in existing code
- Pitfalls: HIGH — `hello-world` test breakage and `parse_mode` gap verified by reading actual source files
- MarkdownV2 escaping rules: HIGH — confirmed via official Telegram Bot API docs
- LangWatch experiment tags API: LOW — LangWatch SDK surface can change; verify at implementation

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable domain; only LOW-confidence LangWatch API might shift)
