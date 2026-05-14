# Phase 12: Middleware-Based Agent Instrumentation - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Migrate the per-agent instrumentation layer (currently `langchain_core.callbacks.BaseCallbackHandler` in `src/robotina/agent/callbacks.py`) to `create_agent` middleware (`@before_model`, `@after_model`, `@wrap_model_call`). Preserve the existing log lines (`LLM stream start`, `Tool call`, `Tool result`, `Thinking`) and keep LangWatch traces intact. Out of scope: token-budget guards, prompt-injection filters, custom state schemas — those are future work this migration only unblocks.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase (migration / refactor with technical success criteria only, no user-facing behavior). Use the ROADMAP phase goal, success criteria, and the LangChain 1.x middleware docs to guide decisions.

Key constraints carried from ROADMAP notes:
- This is a rip-and-replace migration in principle, but the LangWatch interaction model needs verification first. If LangWatch's tracing depends on LangChain callbacks (rather than OTel directly), a thin bridge layer may be required and success criterion 5 (phase summary documents the interaction model) becomes the place to record the finding.
- A short research spike at the start of plan-phase is appropriate, before committing to the migration shape.
- Out of scope: custom state schemas for `reply_context` / `household_id` (backlog item 999.1).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/robotina/agent/callbacks.py` — the file being migrated. Single class `AgentLoggingHandler` with 4 callback methods (`on_chat_model_start`, `on_llm_end`, `on_tool_start`, `on_tool_end`). 44 lines.
- `src/robotina/agent/agents.py` — agent registry; check here for where `AgentLoggingHandler` is wired into `create_agent` calls.
- `src/robotina/llm/__init__.py` — `LLMBackend.create_agent()` wrapper; likely where callbacks are passed through.

### Established Patterns
- LangChain 1.x `create_agent` is in active use (Phase 10 migration completed).
- `response_format=` is in active use on 5 artifact-producing agents (Phase 11 just completed).
- LangWatch + OTel are initialized at agent-runner startup per Phase 4.

### Integration Points
- Every `create_agent(...)` call site that currently passes the callback handler must switch to passing middleware.
- Tests that assert callback registration must be updated to assert middleware presence/ordering.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase. Plan-phase should begin with a brief research spike on LangChain 1.x middleware (`@before_model`, `@after_model`, `@wrap_model_call`) and the LangWatch–callback interaction model before committing to the migration shape.

</specifics>

<deferred>
## Deferred Ideas

- Token-budget pre-model guard (mentioned in ROADMAP goal as future work this phase unblocks).
- Prompt-injection filter middleware (same — future, not this phase).
- Custom state schemas for `reply_context` / `household_id` — captured in backlog Phase 999.1.

</deferred>
