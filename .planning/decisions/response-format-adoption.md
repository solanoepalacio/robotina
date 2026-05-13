# Decision: Adopt response_format on the 5 artifact-producing agents

**Status:** Adopted (Phase 11)
**Date:** 2026-05-13

## Context

The 2026-05-13 canelones-de-choclo incident exposed a structural weakness in
Robotina's artifact-extraction pipeline. The recipe-research-gather agent
emitted valid recipe JSON wrapped in a prose preamble + ```json fence + a
closing remark. `_extract_task_output` in
`src/robotina/queue/workflow_runner.py` ran a four-step fallback ladder —
`content.strip("```")`, `json.loads(content)`, scan-for-first-`{`,
`json.loads(content[idx:])` — and still could not recover the JSON. The
workflow dead-lettered 5 downstream steps and the user got a Spanish apology
instead of the recipe.

The same parse ladder lives in every other artifact-producing agent
(recipe-research-instructions, recipe-research-ingredients,
recipe-research-metadata, recipe-load). Any one of them can emit
prose-wrapped JSON on any run, and the failure mode is silent — the
workflow runner cannot tell "agent emitted garbage" from "agent emitted
legitimate output the parser couldn't read."

LangChain 1.x ships `response_format=` on `langchain.agents.create_agent`,
which populates `state["structured_response"]` with a Pydantic instance
instead of relying on free-text content. Phase 10 (`AGENT-12`) unblocked
this API surface — Phase 11 puts it to work.

## What the free-text parse ladder actually buys us

- It works most of the time. Defensive scanning recovered ~99% of well-formed
  LLM outputs across Phases 6–10.
- It is provider-agnostic — every backend (Ollama, Anthropic, OpenAI) emits
  the same free-text shape, so one parser covers all three.
- No new dependencies. The schema lives in `task_types.py`; the parser is
  pure Python.

## Why those benefits don't apply here

- The ~1% prose-wrap failure rate is not a tail risk; in production it
  manifested as a dead-lettered workflow within a week of Phase 9 ship.
  Every additional recipe query is another lottery ticket.
- LangChain 1.x natively wraps the schema concern. `ProviderStrategy` uses
  OpenAI/Anthropic strict mode (token-level enforcement); `ToolStrategy`
  uses a synthesized emit tool whose args are validated against the Pydantic
  schema (tool-call-level enforcement on Ollama). Both replace the parser
  with an enforcement guarantee — the agent CAN'T emit prose-wrapped JSON
  because the channel that carries the artifact is not free text.
- The schemas already exist (`RecipeResearchGatherOutput`,
  `RecipeResearchInstructionsOutput`, `RecipeResearchIngredientsOutput`,
  `RecipeResearchMetadataOutput`, `RecipeLoadOutput` in
  `src/robotina/queue/task_types.py`). Binding them costs one field on
  `AgentConfig`, one kwarg on `LLMBackend.create_agent`, and one branch on
  `_extract_task_output`.

## Proposed change

1. **Per-provider Strategy mapping.** Ollama → `ToolStrategy`. Anthropic /
   OpenAI → `ProviderStrategy`. Strategy is selected INSIDE each
   `LLMBackend.create_agent()` adapter — `run_task` passes a raw Pydantic
   class, the adapter wraps it.

   **Why explicit per-provider mapping.** `gpt-oss` is in
   `FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT`
   (`langchain/agents/factory.py:148–158`), so AutoStrategy on Ollama
   resolves to ProviderStrategy and calls
   `model.bind_tools(strict=True, response_format={...})` on ChatOllama —
   which Ollama does not honor. ToolStrategy is the correctness path on
   Ollama, not an aesthetic preference. Anthropic and OpenAI have
   provider-native strict-schema support, so ProviderStrategy is correct
   there.

2. **`AgentConfig.response_format_model: type[BaseModel] | None = None`.**
   New optional field. NOT overridable via `AGENT_OVERRIDES_FILEPATH` —
   schema is a code contract, not config. Populated for the 5 named
   artifact-producing agents.

3. **Workflow-runner refactor.** `_extract_task_output` reads
   `result["structured_response"]` when the executing agent has
   `response_format_model` bound; raises `ValueError` on missing. The
   prose-strip / markdown-fence / first-`{`-scan ladder is removed. The
   `return_direct` tool-message branch (Phase 07.1, used by
   handle-incoming-message and acknowledge-add-recipe) is preserved.

4. **Prompt bumps.** 5 new prompt versions (V003 for gather; V002 for the
   other four) strip "respond with valid JSON only" / schema-mirroring
   boilerplate — schema is now token-enforced; instructing the model to
   also "respond with JSON" can confuse the model into wrapping the
   structured emit in extra prose or double-emitting.

## Alternatives considered

- **Tighten the existing parser (e.g. add a more aggressive prose-strip
  heuristic).** Rejected: every heuristic addition is another lottery
  ticket, not a closed loop. Token-level / tool-arg-level enforcement is
  categorically stronger.
- **Centralize Strategy selection in `run_task` based on
  `config.model_config["provider"]`.** Rejected: the adapter already knows
  its provider; centralizing the decision in `jobs.py` leaks provider
  knowledge into the caller and creates two-place coupling.
- **Add `response_format_model` to the overridable fields in
  `get_agent_config`.** Rejected: an override file could break artifact
  extraction silently. Schema is a code contract — the override system
  should not touch it.

## Risks

- **Ollama 500 "error parsing tool call" on the synthesized emit tool.**
  Existing risk class (Phase 10 documented `_RetryingChatOllama` for this).
  With ToolStrategy adding a structured-emit tool whose args are large,
  gpt-oss has more opportunity to emit malformed tool-call JSON. Mitigation:
  the retry wrapper already covers this path (the emit-tool call is a
  normal `model.invoke` step). If retries are exhausted the existing
  FAILED-step + dead-letter flow runs — same behavior as today.
- **OpenAI strict mode rejects `additionalProperties: true`.**
  `RecipeResearchGatherOutput.recipes: list[dict]` is intentionally loose;
  if the OpenAI override is ever activated for gather, the API will 400 at
  first invoke. Inert under Ollama-only deployment. Documented in
  Phase 11 RESEARCH.md Pitfall 2.
- **Schema validation failure raises late, not at construction.**
  `create_agent(response_format=BadSchema)` does not raise at build time;
  a typo'd schema only surfaces at first invoke. The 5 schemas are
  battle-tested; mitigation is documented but no construction-time guard
  added (out of phase scope).

## Verification

- Unit: `tests/test_llm_backend.py` (5 tests, adapter Strategy-wrap);
  `tests/test_agents.py` (10 tests, registry bindings + non-overridability);
  `tests/test_workflow_runner.py` (4 new tests, structured branch +
  defensive fail-loud).
- Manual: 3 distinct Telegram add-recipe queries complete end-to-end with
  no dead-lettered steps, LangWatch traces tagged with prompt version and
  model. Captured in `.planning/phases/11-.../11-VERIFICATION.md`.

## References

- Phase 11 CONTEXT.md (`.planning/phases/11-.../11-CONTEXT.md`) — locked decisions
- Phase 11 RESEARCH.md (`.planning/phases/11-.../11-RESEARCH.md`) — verified API surface, pitfalls
- `langchain.agents.factory.py:148–158` — `FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT`
- `langchain.agents.structured_output.py:194–304` — ToolStrategy / ProviderStrategy
- `agent-12-migrate-to-create-agent.md` — Phase 10 prerequisite
