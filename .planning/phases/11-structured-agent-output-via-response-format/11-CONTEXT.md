# Phase 11: Structured Agent Output via response_format - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase wires `response_format=` into `langchain.agents.create_agent` for the 5 agents whose final artifact is a Pydantic-shaped JSON payload — the 4 recipe-research sub-agents (`recipe-research-gather`, `-instructions`, `-ingredients`, `-metadata`) and `recipe-load`. The goal is to retire the canelones-class parse failures (2026-05-13 incident: free-text JSON wrapped in prose + markdown fence + postscript defeated `_extract_task_output`'s scanner and cancelled 5 downstream workflow steps).

In scope:
- Add an optional `response_format=` parameter through `LLMBackend.create_agent()` and into each adapter (Ollama / Anthropic / OpenAI).
- Bind each of the 5 named agents to its existing Pydantic Output model in `src/robotina/queue/task_types.py`. No new schemas — the models already exist.
- Adapt `_extract_task_output` in `src/robotina/queue/workflow_runner.py` to prefer `result["structured_response"]` and drop the prose-strip / code-fence / JSON-scan fallbacks.
- Bump system prompt versions for the affected agents to remove "respond with JSON" boilerplate (schema is now token-enforced).

Out of scope (deferred):
- `handle-incoming-message` — current tool-message artifact path stays.
- `acknowledge-add-recipe` — `return_direct=True` short-circuit conflicts with structured response; left as-is.
- `send-notification` — already deterministic Python post-07.1, not an agent.
- Middleware-based instrumentation (Phase 12).
- Custom state schemas / reply_context plumbing (Phase 999.1).

</domain>

<decisions>
## Implementation Decisions

### Strategy Selection per Provider
- Ollama backend → `ToolStrategy`. Ollama has no provider-native strict-schema mode; ToolStrategy (synthesized final-emit tool) is the only viable option.
- Anthropic backend → `ProviderStrategy`. Uses Claude's tool-use strict schemas (token-level guarantee).
- OpenAI backend → `ProviderStrategy`. Uses OpenAI strict mode (`response_format={"type":"json_schema",...}`); the canonical use case.
- Strategy is selected inside each `LLMBackend.create_agent()` adapter. The adapter already knows its provider; pass `response_format=` as a new optional kwarg from `jobs.py`. The adapter is responsible for wrapping it in the correct Strategy.

### Agent Scope
- The 5 named agents get `response_format` bound to their existing Pydantic Output models:
  - `recipe-research-gather` → `RecipeResearchGatherOutput`
  - `recipe-research-instructions` → `RecipeResearchInstructionsOutput`
  - `recipe-research-ingredients` → `RecipeResearchIngredientsOutput`
  - `recipe-research-metadata` → `RecipeResearchMetadataOutput`
  - `recipe-load` → `RecipeLoadOutput`
- `handle-incoming-message`, `acknowledge-add-recipe`, `send-notification` are NOT in scope (see <domain> for reasons).
- The mapping from `task_type` → Output model is needed at agent-construction time. Suggest a lookup table in `agents.py` (one extra optional field on `AgentConfig`, e.g., `response_format_model: type[BaseModel] | None = None`) so `run_task()` can pass it through.

### Workflow Runner / Artifact Extraction
- `result.get("structured_response")` is the authoritative artifact source for response_format agents. When present and a `BaseModel`, return `instance.model_dump(mode="json")`.
- Remove the prose-strip / markdown-code-fence / first-`{`-or-`[`-scan / JSON.loads fallback ladder. With structured output bound, this logic is unreachable for the 5 named agents.
- For agents WITHOUT `response_format` (handle-incoming-message, acknowledge-add-recipe), keep the existing tool-message branch (`{"tool_message": str(last.content)}`). That path still has no structured response by design.
- If a response_format agent returns no `structured_response`, fail loudly with a `ValueError("structured_response missing for {task_type}")`. That's a regression, not a recoverable case — silent free-text fallback would defeat the phase goal.

### Prompts and Tests
- Bump system prompt versions for the 5 affected agents (e.g., `recipe-research-gather/V003.md`, `-instructions/V002.md`, `-ingredients/V002.md`, `-metadata/V002.md`, `recipe-load/V002.md`). Remove "respond with valid JSON only" / schema-mirroring boilerplate — schema is now token-enforced. Prompts should describe semantics (what each field means, how to ground answers) rather than restate field names.
- Per repo convention (CLAUDE.md / feedback memory): system prompts stay in English; only user-facing reply text is Spanish. The affected prompts here are sub-agents that don't produce user-facing replies, so this is automatic.
- Tests live in `tests/queue/test_workflow_runner.py`:
  - Positive: `_extract_task_output` receives a result whose `structured_response` is a Pydantic model instance; assert the returned dict equals `instance.model_dump(mode="json")`.
  - Negative: response_format agent returns `structured_response=None` (or missing key); assert `ValueError`.
  - **Adapt existing tests** that previously fed prose-wrapped or fenced JSON: populate `structured_response` in the mock and assert the artifact comes from there. We do NOT need a separate synthetic canelones-shape (prose + ```json fence + postscript) reproduction test — with structured output, free-text content is irrelevant to artifact extraction, so the canelones bug class is impossible by construction.
- E2E "three distinct recipe queries with no manual prompt tuning between runs": manual checkpoint. Run `uv run agent` against 3 distinct queries via live Telegram path; human signs off in VERIFICATION.md. Not automated (live LLM + live household-manager API; too expensive/brittle for CI).

### Success Criterion Reinterpretation
- ROADMAP success criterion #3 ("regression test reproducing the 2026-05-13 canelones parse failure") is satisfied by the adapted existing tests above, not a literal prose+fence+postscript synthetic test. Rationale: with `response_format` bound, the `_extract_task_output` path never reads free-text agent content for these agents; the canelones failure mode (free-text prose defeating the parser) is structurally eliminated. The plan should reflect this re-reading rather than treat the literal test as required.

### Claude's Discretion
- Exact name of the new field on `AgentConfig` (`response_format_model` vs. `output_model` vs. similar).
- Exact field/attr to read on the Anthropic/OpenAI strategy in case `langchain 1.2.13` exposes them differently than expected — verify against the installed library during planning.
- Whether to also bump `RecipeResearchOutput` to be the response_format for the higher-level `recipe-research` agent if/when it's a single-agent path. Today the pipeline is 4 sub-agents + a synthesizer; if there's no `recipe-research` LLM agent in the registry, this is moot. (Registry shows only the 4 sub-agents + recipe-load — confirmed.)
- Whether to delete or keep the temp diagnostic logger.error in `_extract_task_output` (lines 80-85). Recommendation: delete — its purpose was diagnosing the canelones case, which is now structurally fixed.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- All 5 Output models already exist in `src/robotina/queue/task_types.py`:
  - `RecipeResearchGatherOutput` (line 118) — `recipes: list[dict]`
  - `RecipeResearchInstructionsOutput` (line 135) — `draft_name`, `draft_description`, `draft_instructions`
  - `RecipeResearchIngredientsOutput` (line 157) — `ingredients: list[RecipeIngredient]`
  - `RecipeResearchMetadataOutput` (line 188) — `recipe: RecipeData`
  - `RecipeLoadOutput` (line 209) — `recipe_id`, `recipe_name`, `recipe_description`, `recipe_slug`, `missing_ingredients`
- `langchain.agents.create_agent` is already imported as `_create_agent` in `src/robotina/llm/__init__.py:32` (Phase 10 work).
- `AgentConfig` dataclass at `src/robotina/agent/agents.py:24` is the natural place to declare `response_format_model` per agent.
- Existing `_extract_task_output` at `src/robotina/queue/workflow_runner.py:29` is the single integration point — already handles a `tool_message` branch and falls through to free-text parsing; the second half is what gets replaced.

### Established Patterns
- All agents are constructed inside `run_task()` in `src/robotina/queue/jobs.py:175` via `backend.create_agent(system_prompt=..., tools=...)`. New `response_format=` kwarg threads through the same call site.
- Per STATE.md / D-09: adapters must be instantiated inside the job function, never at module level. This phase keeps that constraint.
- Tool injection per-job (QueueTool, WebSearchTool, HouseholdManagerApiTool, StartWorkflowTool) happens in `run_task()` before agent construction — the response_format kwarg is sibling to this.
- Versioned prompts live under `src/robotina/agent/prompts/{task-type}/V###.md` and are referenced via `AgentConfig.prompt_path`. Prompt bumps follow the existing V001→V002→V003 pattern.

### Integration Points
- `LLMBackend` Protocol in `src/robotina/llm/__init__.py:175` — signature must grow `response_format: type[BaseModel] | None = None`.
- The three adapters (`OllamaBackend.create_agent`, `AnthropicBackend.create_agent`, `OpenAIBackend.create_agent`) each pass through to `_create_agent(...)` with the appropriate Strategy.
- `run_task()` reads `AgentConfig.response_format_model` (new field) and threads it into `backend.create_agent(...)`.
- `_extract_task_output` in `workflow_runner.py:29` updated to prefer `result.get("structured_response")` and remove the free-text parse ladder.

</code_context>

<specifics>
## Specific Ideas

- The ROADMAP brief explicitly notes the ToolStrategy vs ProviderStrategy question; decisions in Area 1 resolve it per provider.
- Existing log message at `workflow_runner.py:81-85` (TEMP DIAGNOSTIC for canelones parse failure) should be removed in this phase — its job is done.
- `RecipeResearchGatherOutput.recipes: list[dict]` is intentionally loose (untyped list[dict]). ToolStrategy on Ollama should handle this; ProviderStrategy may need a stricter schema if/when an OpenAI/Anthropic backend is ever used for this sub-agent. Flag during planning; not blocking for the Ollama-only present state.

</specifics>

<deferred>
## Deferred Ideas

- Bind `IncomingMessageOutput` as `response_format` on `handle-incoming-message` so the workflow root artifact is a clean structured record of "what was decided." Costs a prompt rewrite and double-tool-call risk; revisit when we audit message-level decisions across runs.
- Tighten `RecipeResearchGatherOutput.recipes` from `list[dict]` to a stricter schema once a non-Ollama backend is used for the gather sub-agent — ProviderStrategy will reward stricter shapes.
- Add response_format also to `acknowledge-add-recipe` if `return_direct=True` is ever removed from `QueueTool` in that path. Currently the short-circuit makes structured response unreachable.

</deferred>
