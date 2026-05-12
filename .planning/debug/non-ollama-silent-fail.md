---
status: resolved
trigger: "OpenAI/Anthropic models silently fail in staging — message received, agent run reports complete, but no tool was invoked so nothing happens downstream. Ollama works."
created: 2026-05-12T20:00:00Z
updated: 2026-05-12T22:08:00Z
---

# Debug Session: non-ollama-silent-fail

## Symptoms

- **Expected behavior:** Sending a Telegram message in staging triggers handle-incoming-message → agent decides on a tool (`queue` for replies, `start-workflow` for workflows) → downstream jobs get enqueued and execute, ending with a Telegram reply.
- **Actual behavior:** Only the `handle-incoming-message` job runs. The agent makes ONE LLM call (HTTP 200 OK from provider), then logs `Agent run complete` and exits cleanly. No `Thinking | ...` callback, no `Tool call | ...` callback, no follow-up job enqueued. Redis shows zero jobs after the initial one. User receives no Telegram reply.
- **Error messages:** None. Job is marked `Job OK`. Completely silent. Worker keeps polling, no exception, no traceback.
- **Timeline:** Discovered while attempting to use OpenAI models in staging. Confirmed reproducible with Anthropic (`ChatAnthropic`) as well. Ollama works fine in the same staging environment.
- **Reproduction:** Configure agent in staging with per-task-type `overrides/*.json` pointing to an OpenAI or Anthropic model. Send any short greeting Telegram message (`Hola`, `gracias`, `ok`, `Buenos días`). Observe: one LLM call, immediate completion, no further work.
- **Working baseline:** Local Ollama (and Ollama in staging when configured).

## Key observations from logs

Anthropic run (from user 2026-05-12 20:57:12):
```
INFO robotina.agent.callbacks: LLM stream start | model=ChatAnthropic
INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
INFO robotina.queue.jobs: Agent run complete | task_type=handle-incoming-message
```

Ollama run (working): same shape but with intervening `Thinking | ...` and `Tool call | tool=start-workflow` callbacks.

## Initial hypothesis space

1. **Tool binding not applied to non-Ollama backends.** ELIMINATED.
2. **System prompt formatted for Ollama's quirks.** CONFIRMED — root cause.
3. **Tool schemas incompatible with provider's tool-calling spec.** ELIMINATED.
4. **`stop` / streaming config disables tool calling.** ELIMINATED.
5. **Recent commits changed agent wiring.** ELIMINATED.

## Root Cause

The `handle-incoming-message` system prompt at `src/robotina/agent/prompts/robotina/V001.md` does not enforce unconditional tool use. It frames `queue` as "use it for direct replies (answers)" — Anthropic's `claude-haiku-4-5-20251001` and OpenAI's `gpt-4o-mini` correctly conclude that a chit-chat opener (`Hola`, `gracias`, `ok`, `Buenos días`, `¿Cómo estás?`) does not require fetching household data, and reply with plain assistant text. `create_react_agent` sees a final assistant message with `tool_calls == []` and terminates. The plain text is never delivered: the only Telegram output path is `queue` → `send-notification`. Result: silent fail.

Ollama's `gpt-oss:20b` is reflexively "agentic" — it picks a tool every turn, so it called `queue` even for greetings, which is why the prompt weakness never surfaced in local Ollama testing.

## Evidence

- timestamp: 2026-05-12T20:57:13Z
  observation: ChatAnthropic LLM stream starts then `Agent run complete` fires <0.07s after HTTP 200. No `Thinking` callback, no `Tool call` callback.
  source: user-pasted staging logs (Anthropic run, message_id=109).
  interpretation: AIMessage returned by Anthropic had empty `tool_calls`. The ReAct loop terminated because there was no tool to dispatch.
- timestamp: 2026-05-12T21:55:00Z
  observation: Live Anthropic request body via httpx interception contains a fully-formed `tools: [...]` array with `household-manager-api`, `queue`, `start-workflow` (correct names, descriptions, valid Anthropic-format `input_schema`). The same tools convert cleanly via `convert_to_openai_tool` for OpenAI.
  source: local reproduction harness against real `API_TOKEN_ANTHROPIC`.
  interpretation: Tool binding is working; `create_react_agent` (langgraph 1.1.3) calls `model.bind_tools(tools)` at `chat_agent_executor.py:586`. H1 and H3 eliminated.
- timestamp: 2026-05-12T22:00:00Z
  observation: Invoked the production handle-incoming-message agent live against Anthropic with five conversational messages. All five returned an AIMessage with `tool_calls == []` and plain Spanish text. The same agent against `Agrega guiso de lentejas` correctly called `start-workflow`; against `¿Qué hay en el plan de comidas?` it chained `household-manager-api` then `queue`.
  source: local reproduction harness.
  interpretation: H2 confirmed.
- timestamp: 2026-05-12T22:05:00Z
  observation: After bumping prompt to V002 (unconditional "every turn ends in a tool call") and updating the registry, all five chit-chat messages now produce `tool_calls=['queue']` against BOTH `claude-haiku-4-5-20251001` AND `gpt-4o-mini`. Workflow ("Agrega guiso de lentejas") still produces `['start-workflow']`. Data lookup ("¿Qué hay en el plan de comidas?") still produces `['household-manager-api']`.
  source: local reproduction harness via raw `model.bind_tools(tools)` against live Anthropic and OpenAI APIs.
  interpretation: Fix verified end-to-end. Symmetric resolution across both providers. No regression on the unambiguous workflow/data-question paths that were already working.

## Eliminated

- H1 (Tool binding missing on non-Ollama adapters) — Anthropic request body contains the full bound tools list.
- H3 (Tool schemas incompatible with Anthropic spec) — schemas converted cleanly and Anthropic does call tools when the message is unambiguous.
- H4 (streaming/stop-token config disables tools) — request body shows no stop config and `tool_choice` is not forced.
- H5 (recent commits changed wiring) — args_schema strictness from `b529c96` is unrelated to the no-tool-call path; it only affects argument-validation behavior AFTER a tool call has been emitted.

## Resolution

- **Root cause:** `src/robotina/agent/prompts/robotina/V001.md` was missing an absolute rule that every assistant turn must end in a tool call. Anthropic and OpenAI honored the literal reading ("use `queue` when you have an answer") and replied conversationally to greetings with plain text, which was silently dropped. Ollama masked the bug by being reflexively agentic.
- **Fix:**
  1. Added `src/robotina/agent/prompts/robotina/V002.md` with an explicit "Absolute output rule": every turn ends in a `queue` or `start-workflow` call; chit-chat goes through `queue` with the greeting as its `text` argument; plain assistant text is explicitly described as "dropped on the floor". The routing rule is reframed from "use `queue` for direct replies" to a single yes/no question on whether the request needs multi-step orchestration. Examples explicitly cover greetings.
  2. Updated `src/robotina/agent/agents.py` `AGENT_REGISTRY["handle-incoming-message"].prompt_path` to point at `V002.md`.
  3. Updated `tests/unit/test_agents_registry.py` and `tests/unit/test_prompts.py` to assert V002 (the prompt the agent now uses). V001 is preserved on disk for history.
- **Verification:**
  - Live against `claude-haiku-4-5-20251001`: `Hola`, `gracias`, `ok`, `Buenos días`, `¿Cómo estás?` → `tool_calls=['queue']`; `Agrega guiso de lentejas` → `['start-workflow']`; `¿Qué hay en el plan de comidas?` → `['household-manager-api']`.
  - Live against `gpt-4o-mini`: identical pattern. Before V002 the four chit-chat messages all silently failed; after V002 all produce `['queue']`.
  - Full non-integration test suite: `uv run pytest tests/ -m "not integration"` → 149 passed, 14 deselected (deselected = pre-existing live-Postgres tests, unaffected). No regressions.
- **No env-var changes:** no additions to `.env.example` required for this fix.

## Relevant context

- Each task type has its own LLM config via `overrides/*.json` and an env-var-named API token.
- `LLMBackend` Protocol with concrete implementations for Ollama (`langchain-ollama`), OpenAI (`langchain-openai`), Anthropic (`langchain-anthropic`). Each implements `.model` and `.create_agent()`.
- Agent runtime: LangGraph 1.1.3 `create_react_agent`. Tools are bound automatically inside `create_react_agent` via `model.bind_tools(tool_classes + llm_builtin_tools)`.
- Models verified: Anthropic `claude-haiku-4-5-20251001` and OpenAI `gpt-4o-mini`.
- Memory: Architecture immature; prefer concrete duplicated adapters over generic ones. The fix respects this — no new abstractions; only a per-prompt content change and a registry pointer update.
