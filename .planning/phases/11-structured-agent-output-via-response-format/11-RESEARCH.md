# Phase 11: Structured Agent Output via response_format - Research

**Researched:** 2026-05-13
**Domain:** LangChain 1.x structured-output (`response_format` on `create_agent`); Pydantic JSON-schema constraints under provider-strict mode; Robotina agent + workflow-runner integration
**Confidence:** HIGH (everything load-bearing was empirically verified against the installed `langchain==1.2.13` / `langchain-core==1.2.22` / `langgraph==1.1.3` site-packages and against the Robotina source tree)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Strategy Selection per Provider**
- Ollama backend → `ToolStrategy`. Ollama has no provider-native strict-schema mode; ToolStrategy (synthesized final-emit tool) is the only viable option.
- Anthropic backend → `ProviderStrategy`. Uses Claude's tool-use strict schemas (token-level guarantee).
- OpenAI backend → `ProviderStrategy`. Uses OpenAI strict mode (`response_format={"type":"json_schema",...}`); the canonical use case.
- Strategy is selected inside each `LLMBackend.create_agent()` adapter. The adapter already knows its provider; pass `response_format=` as a new optional kwarg from `jobs.py`. The adapter is responsible for wrapping it in the correct Strategy.

**Agent Scope** — the 5 named agents bind to their existing Pydantic Output models:
- `recipe-research-gather` → `RecipeResearchGatherOutput`
- `recipe-research-instructions` → `RecipeResearchInstructionsOutput`
- `recipe-research-ingredients` → `RecipeResearchIngredientsOutput`
- `recipe-research-metadata` → `RecipeResearchMetadataOutput`
- `recipe-load` → `RecipeLoadOutput`

`handle-incoming-message`, `acknowledge-add-recipe`, `send-notification` are NOT in scope.

Mapping `task_type` → Output model lives in `agents.py` as a new optional field on `AgentConfig` (e.g., `response_format_model: type[BaseModel] | None = None`), so `run_task()` can pass it through.

**Workflow Runner / Artifact Extraction**
- `result.get("structured_response")` is the authoritative artifact source for response_format agents. When present and a `BaseModel`, return `instance.model_dump(mode="json")`.
- Remove the prose-strip / markdown-code-fence / first-`{`-or-`[`-scan / JSON.loads fallback ladder. With structured output bound, this logic is unreachable for the 5 named agents.
- For agents WITHOUT `response_format` (handle-incoming-message, acknowledge-add-recipe), keep the existing tool-message branch (`{"tool_message": str(last.content)}`). That path still has no structured response by design.
- If a response_format agent returns no `structured_response`, fail loudly with a `ValueError("structured_response missing for {task_type}")`. That's a regression, not a recoverable case — silent free-text fallback would defeat the phase goal.

**Prompts and Tests**
- Bump system prompt versions for the 5 affected agents. Remove "respond with valid JSON only" / schema-mirroring boilerplate — schema is now token-enforced. Prompts should describe semantics (what each field means, how to ground answers) rather than restate field names.
- Per repo convention (CLAUDE.md / feedback memory): system prompts stay in English; only user-facing reply text is Spanish. The affected prompts here are sub-agents that don't produce user-facing replies, so this is automatic.
- Tests live in `tests/test_workflow_runner.py`:
  - Positive: `_extract_task_output` receives a result whose `structured_response` is a Pydantic model instance; assert the returned dict equals `instance.model_dump(mode="json")`.
  - Negative: response_format agent returns `structured_response=None` (or missing key); assert `ValueError`.
  - **Adapt existing tests** that previously fed prose-wrapped or fenced JSON: populate `structured_response` in the mock and assert the artifact comes from there. NO separate canelones-shape (prose + ```json fence + postscript) reproduction test.
- E2E "three distinct recipe queries with no manual prompt tuning between runs": manual checkpoint, human signs off in VERIFICATION.md.

### Claude's Discretion
- Exact name of the new field on `AgentConfig` (`response_format_model` vs. `output_model` vs. similar).
- Exact field/attr to read on the Anthropic/OpenAI strategy in case `langchain 1.2.13` exposes them differently than expected — verify against the installed library during planning.
- Whether to also bump `RecipeResearchOutput` to be the response_format for the higher-level `recipe-research` agent if/when it's a single-agent path. (Registry confirmed: no `recipe-research` agent exists, only the 4 sub-agents + recipe-load — moot.)
- Whether to delete or keep the temp diagnostic `logger.error` in `_extract_task_output` (lines 81–85). Recommendation: delete — its purpose was diagnosing the canelones case, which is now structurally fixed.

### Deferred Ideas (OUT OF SCOPE)
- Bind `IncomingMessageOutput` as `response_format` on `handle-incoming-message`.
- Tighten `RecipeResearchGatherOutput.recipes` from `list[dict]` to a stricter schema once a non-Ollama backend is used for the gather sub-agent.
- Add `response_format` also to `acknowledge-add-recipe` if `return_direct=True` is ever removed from `QueueTool` in that path.
</user_constraints>

<phase_requirements>
## Phase Requirements

Phase 11 introduces a new requirements cluster. Per locked decision, the phase plan must propose IDs and add them to `REQUIREMENTS.md`. The existing convention uses `RRECIPE-*` for recipe-research family and `RLOAD-*` for recipe-load (see REQUIREMENTS.md lines 85–99). Continuing the numbering:

| Proposed ID | Description | Research Support |
|----|-------------|------------------|
| **RRECIPE-07** | Each recipe-research sub-agent (`recipe-research-gather`, `-instructions`, `-ingredients`, `-metadata`) binds `response_format=` on `langchain.agents.create_agent` so its final artifact is delivered via `state["structured_response"]` and never depends on free-text parsing. | "Standard Stack" → `langchain.agents.structured_output.ToolStrategy` / `ProviderStrategy`; "Architecture Patterns" → Pattern 1 + Pattern 2. |
| **RLOAD-07** | The `recipe-load` agent binds `response_format=RecipeLoadOutput`; the workflow runner reads `structured_response` and persists it as the step artifact. | Same as above; the agent path is the simplest of the five (single tool, single emit). |
| **WF-08** *(workflow-runner family)* | `_extract_task_output` prefers `result["structured_response"]` for response_format agents and raises `ValueError` if it is missing on a response_format agent; the prose/fence/JSON-scan fallback is removed. | "Architecture Patterns" → Pattern 3. |

*(WF-** is the existing prefix used by Phase 5/6 workflow-runner work; verified by inspecting REQUIREMENTS.md — `WF-06` / `WF-07` are used in `test_on_step_complete_*` docstrings. The plan author may pick a different prefix if WF numbering has drifted; the important thing is one ID covers the runner-side change.)*
</phase_requirements>

## Summary

LangChain 1.x ships a first-class `response_format=` parameter on `langchain.agents.create_agent` (verified at `factory.py:679`). It accepts three shapes: `ToolStrategy(Schema)`, `ProviderStrategy(Schema)`, or a bare schema (which is wrapped in `AutoStrategy` and resolved at first model invocation by `_supports_provider_strategy`). When set, the agent state acquires a `structured_response: NotRequired[ResponseT]` key (verified at `middleware/types.py:355` and `:368`). When `ProviderStrategy` is in effect the field holds the parsed `BaseModel` instance directly; when `ToolStrategy` is in effect the same field is populated after the model emits a tool call matching the schema (verified at `factory.py:1052` and `:1108`). For the Robotina case this means we get a real Pydantic instance back in `result["structured_response"]` regardless of which strategy ran.

**The auto-resolution trap.** Robotina runs `gpt-oss:20b` on Ollama. The string `"gpt-oss"` is in LangChain's `FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT` list (`factory.py:148–158`). I confirmed empirically that `_supports_provider_strategy(ChatOllama(model='gpt-oss:20b'), tools=[])` returns `True`. That means if we pass a raw `RecipeResearchGatherOutput` class (rather than wrapping it in `ToolStrategy(...)`) on the Ollama adapter, LangChain will try to bind OpenAI-style `response_format={"type":"json_schema",...}` to a `ChatOllama` instance via `model.bind_tools(..., strict=True, response_format={...})` — which Ollama does not honor, and which would either silently fall through to free-text or raise at first invoke. **The locked decision to explicitly wrap in `ToolStrategy(Schema)` inside `OllamaBackend.create_agent` is therefore not a stylistic preference; it is a correctness requirement.** Anthropic and OpenAI adapters can safely use `ProviderStrategy(Schema)` because both report `structured_output: True` in their model profiles (verified empirically with `ChatAnthropic("claude-sonnet-4-5")` and `ChatOpenAI(model_name="gpt-4.1-mini")`).

**The strict-mode schema trap.** `RecipeResearchGatherOutput.recipes: list[dict]` generates JSON schema `items: {type: "object", additionalProperties: true}` (verified by calling `.model_json_schema()`). OpenAI strict mode rejects `additionalProperties: true` on nested objects and rejects optional fields not present in the `required` list. The `ToolStrategy` path on Ollama is tolerant of this (the synthesized emit tool is bound without `strict=True`), so the locked decision to use ToolStrategy on Ollama also incidentally insulates the loose `list[dict]` shape from strict-mode rejection. If the OpenAI override is ever activated for `recipe-research-gather`, that single schema will need tightening; the other four are clean.

**Primary recommendation:** (1) Extend the `LLMBackend` Protocol with `response_format: type[BaseModel] | None = None`; (2) inside each adapter, branch on provider to construct the right strategy wrapper before calling `_create_agent`; (3) add `response_format_model` to `AgentConfig` and populate it for the 5 named agents; (4) thread the kwarg through `run_task`; (5) replace the free-text parse ladder in `_extract_task_output` with a `structured_response` read; (6) bump prompts and adapt the four existing on_step_complete tests so they exercise the new path. All findings are verified against the installed library and source tree.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Strategy selection (Tool vs Provider) | LLM adapter (`robotina.llm.*Backend`) | — | Adapter is the only layer that knows its provider; the locked decision puts the wrap there, not in `jobs.py`. |
| Schema declaration per agent | Agent registry (`robotina.agent.agents.AGENT_REGISTRY` / `AgentConfig.response_format_model`) | — | Same locus as model_config and prompt_path; identical override semantics. |
| Kwarg plumbing | `run_task()` in `robotina.queue.jobs` | — | Already builds the `backend.create_agent(...)` call; one extra kwarg. |
| Artifact extraction | `_extract_task_output` in `robotina.queue.workflow_runner` | `on_step_complete` (caller) | Same function, redirected to read `structured_response`; downstream behavior unchanged. |
| Validation errors on schema mismatch | LangChain (`StructuredOutputValidationError`) | `run_task` exception path → `on_step_failed` | LangChain raises, the existing try/except in `run_task` catches and marks the step FAILED — no new error path needed. |

## Standard Stack

### Core

| Library | Version (verified installed) | Purpose | Why Standard |
|---------|------------------------------|---------|--------------|
| `langchain` | `1.2.13` | `create_agent`, `ToolStrategy`, `ProviderStrategy` | Already in use post-Phase 10. The structured-output API lives entirely in this package: `langchain.agents.create_agent` and `langchain.agents.structured_output.{ToolStrategy,ProviderStrategy,AutoStrategy}`. [VERIFIED: `.venv/lib/python3.12/site-packages/langchain/agents/__init__.py:3` and `.venv/.../structured_output.py:194,260,447`] |
| `langchain-core` | `1.2.22` | `BaseChatModel`, `AIMessage`, `ToolMessage`, callback base | No new usage. Existing imports cover everything needed. [VERIFIED: `from importlib.metadata import version`] |
| `langgraph` | `1.1.3` | Underlying graph + `CompiledStateGraph.invoke` | No direct API surface change for this phase. [VERIFIED] |
| `langchain-anthropic` | `1.4.0` | `ChatAnthropic` — model profile reports `structured_output: True` | ProviderStrategy on Anthropic uses Claude's tool-use strict schema. Profile verified empirically. [VERIFIED] |
| `langchain-openai` | `1.1.12` | `ChatOpenAI` — model profile reports `structured_output: True` | ProviderStrategy on OpenAI translates to `response_format={"type":"json_schema","json_schema":{...}}` via `ProviderStrategy.to_model_kwargs()` (`structured_output.py:285–304`). Profile verified empirically. [VERIFIED] |
| `langchain-ollama` | `1.0.1` | `ChatOllama` — no profile, no native structured output | Must use `ToolStrategy` explicitly. [VERIFIED: `getattr(ChatOllama(...), 'profile', None) == None`] |
| `pydantic` | `>=2.7` (existing) | Schema source — `model_json_schema()` is what LangChain converts to provider format | All 5 Output models already use Pydantic v2. [CITED: `src/robotina/queue/task_types.py`] |

### Supporting

No new supporting libraries. The phase adds zero dependencies.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Per-adapter strategy wrapping inside `create_agent()` | Pass strategy from `run_task()` based on `config.model_config["provider"]` | Putting the branch in `jobs.py` means `jobs.py` knows about ToolStrategy vs ProviderStrategy. Locked decision (correctly, IMO) keeps that knowledge inside the adapter; `jobs.py` passes a raw schema class and the adapter wraps. |
| `AgentConfig.response_format_model` field | Separate `TASK_TYPE_TO_OUTPUT_MODEL` map in `task_types.py` | The map approach skips the override pipeline. Putting it on `AgentConfig` keeps the override surface uniform (today only `model_config` + `prompt_path` are overridable per `agents.py:175–183`; we should NOT add `response_format_model` to the overridable set — the schema is a code contract, not config). [VERIFIED: `agents.py:175–183`] |
| Raw `BaseModel` class as `response_format=` value | Wrap explicitly | LangChain wraps a bare class in `AutoStrategy(schema=raw)` at `factory.py:850`, then at first model call resolves via `_supports_provider_strategy`. On Ollama with `gpt-oss:20b` this resolves to `ProviderStrategy` because `"gpt-oss"` is in `FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT` — **wrong for Ollama**. Explicit wrapping is mandatory. [VERIFIED empirically with `_supports_provider_strategy(ChatOllama(model='gpt-oss:20b'), tools=[]) == True`] |

**Installation:** No package changes. `pyproject.toml` already pins `langchain>=1.2`.

**Version verification:** All versions above are the *currently installed* versions in `.venv` as of 2026-05-13 (queried via `importlib.metadata.version`). No pin bumps are required.

## Architecture Patterns

### System Architecture Diagram

```
                    +-----------------+
   RQ job  ────►    |  run_task       |
   (jobs.py)        |  (jobs.py)      |
                    +--------+--------+
                             |
                             | 1. get_agent_config(task_type)
                             |    → AgentConfig.response_format_model  [NEW field]
                             v
                    +-----------------+
                    |  make_backend   |   (provider dispatch)
                    +--------+--------+
                             |
            +----------------+-------------------+
            v                v                   v
     +-------------+  +---------------+   +--------------+
     | OllamaBack. |  | AnthropicBack |   | OpenAIBack.  |
     | create_agent|  | create_agent  |   | create_agent |
     | wraps in    |  | wraps in      |   | wraps in     |
     | ToolStrategy|  | ProviderStrat |   | ProviderStrat|
     +------+------+  +-------+-------+   +-------+------+
            |                 |                   |
            +-----------------+-------------------+
                              |
                              v 2. langchain.agents.create_agent(
                                       model, tools,
                                       response_format=<Strategy(...)>)
                              |
                              v
                    +---------+---------+
                    | CompiledStateGraph |
                    |  .invoke(...)      |
                    +---------+----------+
                              |
                              | 3. result is dict-like AgentState:
                              |    {"messages": [...],
                              |     "structured_response": <BaseModel|None>}
                              v
                    +---------+---------+
                    | on_step_complete  |   ── _extract_task_output ──►
                    | (workflow_runner) |     • if "structured_response"
                    +-------------------+       in result and a BaseModel:
                                                  return .model_dump("json")
                                                • elif last msg is tool:
                                                  return {"tool_message": ...}
                                                • else (response_format
                                                  agent, missing key):
                                                  raise ValueError
```

Entry point is the existing RQ worker call to `run_task`. The single change to the flow is the kwarg `response_format=` threaded through `backend.create_agent`, and the artifact-extraction branch reading `structured_response`. Everything else — tool injection, prompt loading, LangWatch tracing, callback handler — is unchanged.

### Recommended Project Structure

No new directories. Files touched:

```
src/robotina/
├── llm/__init__.py             # LLMBackend Protocol + 3 adapters: add response_format kwarg
├── agent/
│   ├── agents.py               # AgentConfig: add response_format_model field; populate for 5 agents
│   └── prompts/
│       ├── recipe-research-gather/V003.md         # NEW (was V002.md)
│       ├── recipe-research-instructions/V002.md    # NEW (was V001.md)
│       ├── recipe-research-ingredients/V002.md     # NEW (was V001.md)
│       ├── recipe-research-metadata/V002.md        # NEW (was V001.md)
│       └── recipe-load/V002.md                     # NEW (was V001.md)
└── queue/
    ├── jobs.py                 # thread response_format through backend.create_agent call
    └── workflow_runner.py      # rewrite _extract_task_output

tests/
└── test_workflow_runner.py     # adapt extract + on_step_complete tests, add positive/negative
```

`overrides/*.json` is NOT touched (see "Override file format" below).

### Pattern 1: ProviderStrategy for Anthropic / OpenAI

**What:** Wrap the Pydantic schema in `ProviderStrategy` and pass to `create_agent`. LangChain calls `model.bind_tools(tools, strict=True, response_format={...}, ...)`.

**When to use:** Anthropic, OpenAI, and any other provider whose `model.profile["structured_output"]` is `True`.

**Example (from the verified library):**

```python
# Source: .venv/.../langchain/agents/structured_output.py:260–304
# and  .venv/.../langchain/agents/factory.py:1215–1223

from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain_openai import ChatOpenAI

agent = create_agent(
    model=ChatOpenAI(model_name="gpt-4.1-mini", ...),
    tools=[...],
    system_prompt="...",
    response_format=ProviderStrategy(RecipeLoadOutput),
)

result = agent.invoke({"messages": [{"role": "user", "content": "..."}]})
parsed: RecipeLoadOutput = result["structured_response"]   # BaseModel instance
```

When the model emits text (no tool calls), `_handle_model_output` (`factory.py:1027–1053`) parses it as JSON and validates against the schema. On failure it raises `StructuredOutputValidationError`.

### Pattern 2: ToolStrategy for Ollama

**What:** Synthesize a final-emit tool whose `args_schema` IS the response model. The model calls that tool to "finalize"; LangChain catches the tool call, validates the args against the schema, populates `structured_response`, and ends the graph.

**When to use:** Ollama, or any model whose `profile["structured_output"]` is missing/False AND whose name doesn't match `FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT` — though Robotina specifically uses Ollama, where ToolStrategy is the locked decision.

**Example:**

```python
# Source: .venv/.../langchain/agents/structured_output.py:194–257
# and  .venv/.../langchain/agents/factory.py:1057–1109

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
# OllamaBackend's _RetryingChatOllama subclasses ChatOllama:
agent = create_agent(
    model=self._model,                  # _RetryingChatOllama
    tools=tools or [],                  # WebSearchTool, etc. — sibling tools
    system_prompt=system_prompt,
    response_format=ToolStrategy(RecipeResearchGatherOutput),
)
```

The synthesized tool is named after the Pydantic class (`"RecipeResearchGatherOutput"` — derived at `structured_output.py:162–164`). Validation happens at `factory.py:1092` via `_SchemaSpec.parse` → `TypeAdapter.validate_python`. On the validated path, `structured_response` is set to the Pydantic instance and the conversation ends.

Important interaction:
- `tool_choice="any"` is forced when structured output tools are present (`factory.py:1242`), meaning the model **must** call a tool on every step. That's fine because the sibling tools (web search, household-manager-api) are normal tools the model is supposed to use; the structured-output tool is just one more option until the model is ready to finalize.
- The synthesized tool is appended to the tool list (`factory.py:1208–1212`), so it counts toward the agent's tool budget but does NOT collide with `return_direct=True` tools (none of the 5 named agents have one — confirmed in `agents.py:69–133`).

### Pattern 3: structured_response-first artifact extraction

**What:** `_extract_task_output` reads `result.get("structured_response")` and `.model_dump(mode="json")`s it; tool-message branch is preserved for non-response_format agents; free-text parse ladder is deleted.

**When to use:** Always. Single replacement for the existing 60-line parser.

**Example skeleton:**

```python
# Replaces src/robotina/queue/workflow_runner.py:29–87
# Source: locked decision, plus verified result shape from
#   .venv/.../langchain/agents/middleware/types.py:350–355
# and validated behavior at factory.py:1052 (ProviderStrategy) / 1108 (ToolStrategy)

from pydantic import BaseModel

def _extract_task_output(result: dict, *, expects_structured: bool = False) -> dict:
    """Extract artifact from a create_agent invoke result.

    When expects_structured=True (caller knows this agent has response_format
    bound), require result["structured_response"] to be a BaseModel and return
    its model_dump(mode='json'). Raise ValueError if missing — this is the
    regression path that Phase 11 explicitly chooses not to mask.

    When expects_structured=False, fall back to the tool-message branch
    (return_direct artifact) used by handle-incoming-message and
    acknowledge-add-recipe. NO free-text JSON parsing.
    """
    if expects_structured:
        sr = result.get("structured_response")
        if isinstance(sr, BaseModel):
            return sr.model_dump(mode="json")
        if sr is None:
            raise ValueError(
                "structured_response missing on response_format agent result"
            )
        # Defensive: structured_response could in theory be a dict for
        # JSON-schema schemas, but Robotina only uses Pydantic models, so
        # treat anything else as a regression.
        raise ValueError(
            f"structured_response is not a BaseModel: type={type(sr).__name__}"
        )

    # No response_format on this agent — return_direct tool-message path.
    last = result["messages"][-1]
    if getattr(last, "type", None) == "tool":
        return {"tool_message": str(last.content)}

    # Phase 11: there is no longer a free-text fallback for non-tool-message
    # finals. Any agent without response_format that lands here is a bug.
    raise ValueError(
        f"Agent produced no structured_response and no terminal ToolMessage; "
        f"last message type={getattr(last, 'type', None)!r}"
    )
```

**Caller wiring.** `on_step_complete` (`workflow_runner.py:252–253`) currently does:

```python
if isinstance(output, dict) and "messages" in output:
    artifact = _extract_task_output(output)
```

It does not know whether the step's agent has `response_format` bound. The simplest fix is to look up the AgentConfig from the step's `task_type` and pass `expects_structured=config.response_format_model is not None`. Alternative: keep `_extract_task_output` parameterless and have it auto-detect via `"structured_response" in result`; but that conflates "agent did not set it" with "agent should not have set it." The locked decision is explicit fail-loud on missing — so the caller must thread the expectation.

`task_type` is available on `WorkflowRunStep.task_type` — `on_step_complete` has the step in scope already (`workflow_runner.py:242–249`).

### Anti-Patterns to Avoid

- **Passing a bare `BaseModel` class as `response_format=` on the Ollama adapter.** AutoStrategy resolves to ProviderStrategy because `"gpt-oss"` is in the fallback whitelist; the bind silently fails to enforce a schema on Ollama. Always wrap in `ToolStrategy(...)` in `OllamaBackend.create_agent`.
- **Adding `response_format_model` to the overridable fields in `get_agent_config` (`agents.py:175–183`).** The schema is part of the code contract between the agent and the workflow runner. Overriding it from a JSON file would let a deploy-time override break artifact extraction silently. Keep `response_format_model` non-overridable.
- **Keeping any of the free-text JSON parsing in `_extract_task_output`.** Once the five agents emit structured output, the prose-strip / code-fence / JSON-scan ladder cannot be reached on those agents — but it remains a footgun if a new agent without `response_format` is added later and emits free-text. Fail loudly instead.
- **Leaving the "respond with valid JSON only" boilerplate in the bumped prompts.** The schema is token-enforced; instructing the model to also "respond with JSON" can confuse the model into wrapping the structured emit in extra prose or double-emitting.
- **Hand-rolling JSON schema for the response_format value.** `ProviderStrategy(SomeModel)` and `ToolStrategy(SomeModel)` build the schema from `model_json_schema()` (`structured_output.py:179`). No need to pre-serialize.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON-schema enforcement on LLM output | Custom output parser that scans for prose, fences, JSON | `response_format=` on `create_agent` | This is exactly the canelones bug class. LangChain's path is token-level (provider) or tool-arg-validated (Ollama); both eliminate prose-wrap defeats. |
| Strategy selection | A standalone `select_strategy(model)` helper in `robotina.llm` | Per-adapter explicit wrap (locked decision) | The adapter already knows its provider. Centralizing the decision in a helper just hides the provider-specific knowledge in another place. |
| Tool-emit synthesis for Ollama | Building a fake "emit_final" tool manually | `ToolStrategy(Schema)` | LangChain synthesizes the tool, registers it with the graph, validates its args against the schema, and populates `structured_response` — all of which would have to be replicated. |
| Pydantic round-trip on the artifact | Custom `dict_from_model(...)` helper | `instance.model_dump(mode="json")` | Already the existing pattern in `on_step_complete` (`workflow_runner.py:255`) for non-message outputs. |
| Schema → OpenAI `response_format` translation | Manual `{"type": "json_schema", ...}` construction | `ProviderStrategy(...).to_model_kwargs()` | Already in the library (`structured_output.py:285–304`). |

**Key insight:** The entire `_extract_task_output` body shrinks from ~60 lines of defensive parsing to ~12 lines that read a typed field. The complexity is moved into LangChain, which has dedicated tests for it.

## Runtime State Inventory

> Phase 11 is a refactor (it changes how agent output is shaped and parsed). Apply the runtime-state-inventory discipline.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `WorkflowRunStep.artifact` (Postgres JSON column) — historical artifacts persisted by the OLD parser. Schema is the same shape (`model_dump(mode="json")` dict), so existing rows are compatible. **No migration needed.** | None — new artifacts will be byte-equal to old artifacts on the success path; only failing-on-canelones path changes. |
| Live service config | n8n workflows / Datadog / Cloudflare etc. — none of these read agent artifacts. The agent run lives entirely inside RQ + Postgres. | None. |
| OS-registered state | None — no Windows Task Scheduler / launchd entries reference these agents by output shape. | None. |
| Secrets/env vars | None — no new env vars introduced by this phase. Existing `RECIPE_RESEARCH_*_API_TOKEN` / `RECIPE_LOAD_API_TOKEN` continue unchanged. | None. (Memory rule "Always update .env.example" is informational only — no additions here.) |
| Build artifacts | None — no installed-package name changes. | None. |
| **Prompts on disk** (Robotina-specific) | The 5 versioned prompts (`recipe-research-gather/V002.md`, `recipe-research-instructions/V001.md`, `recipe-research-ingredients/V001.md`, `recipe-research-metadata/V001.md`, `recipe-load/V001.md`) reference JSON-shape instructions in their bodies. **They are not state, but they ARE runtime-loaded files** that need new versions written and `AgentConfig.prompt_path` references updated. | (1) Author Vnext.md prompts in same directories. (2) Update `prompt_path` in `agents.py` for each affected agent. (3) Leave old V###.md on disk per project convention (versioned, not overwritten). |
| **In-flight workflows** | If a workflow is mid-execution at deploy time, its in-progress step continues with the OLD code path (job already enqueued with prior worker code); subsequent steps run on new code. This is acceptable because the artifact shape is unchanged. | None — but the deploy notes should mention "drain or accept mixed in-flight workflows during cutover." |

## Common Pitfalls

### Pitfall 1: AutoStrategy silently picks ProviderStrategy on Ollama gpt-oss

**What goes wrong:** `response_format=RecipeResearchGatherOutput` (bare class) → LangChain wraps in `AutoStrategy` → at first invoke, `_supports_provider_strategy(ChatOllama(model='gpt-oss:20b'))` returns `True` (because `"gpt-oss"` is in the fallback list) → LangChain calls `model.bind_tools(tools, strict=True, response_format={"type":"json_schema",...})`. Ollama's chat endpoint ignores or rejects `response_format`, and the run either fails to enforce the schema or 5xx's.

**Why it happens:** `FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT` includes `"gpt-oss"` because OpenAI's hosted gpt-oss-via-API supports structured output; but the same string matches the Ollama-served model name. LangChain has no way to distinguish "OpenAI gpt-oss" from "Ollama gpt-oss" from a substring match.

**How to avoid:** Always explicitly wrap in `ToolStrategy` inside `OllamaBackend.create_agent`. Never pass a bare class to that adapter.

**Warning signs:** Schema validation errors at runtime that mention `additionalProperties`, or Ollama 500 errors with `"error parsing tool call"` — these would surface specifically because Ollama is being told to do something it can't.

[VERIFIED: `factory.py:148–158` (the list), `factory.py:486–528` (matching logic), and empirical test `_supports_provider_strategy(ChatOllama(model='gpt-oss:20b'), tools=[]) == True`.]

### Pitfall 2: OpenAI strict mode rejects `additionalProperties: true` and untyped containers

**What goes wrong:** If the OpenAI override is used for `recipe-research-gather`, the strict-mode JSON schema sent to OpenAI looks like:

```json
"recipes": {"items": {"type": "object", "additionalProperties": true}, "type": "array"}
```

OpenAI strict mode refuses `additionalProperties: true` on nested object types — the API returns a 400 at first invoke.

**Why it happens:** `RecipeResearchGatherOutput.recipes: list[dict]` is intentionally loose (`task_types.py:118–119`). Pydantic v2 emits the loose JSON-schema form unchanged.

**How to avoid:** For the present (Ollama-only) deployment, this is **inert** — ToolStrategy on Ollama does not call `bind_tools(..., strict=True, ...)`. (`factory.py:1244` uses `tool_choice="any"`, no `strict=True`.) Phase 11 should ship Ollama-first and leave OpenAI strict-mode tightening for the deferred follow-up. The plan should add an inline comment on the gather adapter noting "switching this agent to OpenAI requires tightening `recipes` to a stricter schema or passing `ProviderStrategy(RecipeResearchGatherOutput, strict=False)`."

**Warning signs:** OpenAI API 400 with `"Invalid schema for response_format"` referencing `additionalProperties` or `recipes` field.

[VERIFIED: `ProviderStrategy.to_model_kwargs` always sets `strict=True` when `schema_spec.strict` is True (`structured_output.py:297`); when `strict` is None (the default), `strict` is omitted from `json_schema` but the call site at `factory.py:1220` still passes `strict=True` to `bind_tools`. So OpenAI gets strict mode by default whenever ProviderStrategy is used. The locked decision uses ProviderStrategy for OpenAI; the strict-mode rejection is therefore a real risk *only if and when* the OpenAI override is activated for gather.]

### Pitfall 3: Optional Pydantic fields under OpenAI strict mode

**What goes wrong:** OpenAI strict mode requires every property to appear in `required`. Pydantic v2's `model_json_schema()` for `Optional[str] = None` produces `anyOf: [{"type": "string"}, {"type": "null"}]` BUT does not include the field in `required`. OpenAI strict mode rejects this combination (it considers any non-required field a strict-mode violation).

**Why it happens:** Most of the 5 Output models have optional fields:
- `RecipeIngredient`: `unit_name`, `quantity`, `note` (all optional)
- `RecipeStep`: `title` (optional)
- `RecipeData`: 8 optional fields
- `RecipeLoadOutput`: `recipe_description`, `recipe_slug`, `missing_ingredients` (optional/default)

**How to avoid:** Same as Pitfall 2 — under Ollama+ToolStrategy this is inert. For Anthropic+ProviderStrategy, Claude's structured-output is tolerant of optional fields (no equivalent strict-mode reject). For OpenAI strict mode specifically, two options:
1. Pass `ProviderStrategy(SomeModel, strict=False)` — sets `schema_spec.strict=False`, which omits `"strict": true` from the JSON schema OpenAI sees. Loosens enforcement but eliminates the optional-field reject.
2. Pre-process the schema to add all properties to `required` and use `anyOf` for nulls (already partially the case).

**Recommendation:** Default to `ProviderStrategy(SomeModel)` (strict=None, which translates to no `"strict": true` flag — but verify against OpenAI docs at planning time). If a future OpenAI deployment hits this, fix per-model.

**Warning signs:** OpenAI API 400 with `"Invalid schema for response_format"` referencing a specific optional field.

[CITED: OpenAI structured outputs docs link in `structured_output.py:291` comment.]

### Pitfall 4: Ollama 500 "error parsing tool call" on the synthesized emit tool

**What goes wrong:** Phase 10 documented that Ollama returns 500 with `"error parsing tool call"` when gpt-oss:20b emits malformed tool-call JSON; `_RetryingChatOllama` already retries this with backoff. With ToolStrategy adding a structured-emit tool whose args are large (e.g., a full `RecipeData`), the model has more opportunity to emit malformed tool-call JSON.

**Why it happens:** Ollama's tool-call parser is brittle on large or deeply nested tool-args; gpt-oss:20b reasoning + a fat schema can produce edge cases.

**How to avoid:** No new mitigation needed — `_RetryingChatOllama._generate` (and `_agenerate`) already retry 5xx errors up to 3 attempts with backoff (`src/robotina/llm/__init__.py:82–159`). The emit-tool call path goes through the same retry wrapper because it's a normal `model.invoke` step (`factory.py:1273`). If retries are exhausted the job fails, `on_step_failed` runs the dead-letter notification, and the user gets the Spanish apology — same path as today.

**Warning signs:** RQ FailedJobRegistry entries with `OllamaResponseError(status_code=500)` for the 5 named task types. Pre-deployment, run the manual E2E with 3 distinct queries (locked verification criterion) and watch worker logs for retry-warning lines (`"Ollama transient error, retrying"`).

[VERIFIED: `src/robotina/llm/__init__.py:99–128` (retry loop), Phase 10 RESEARCH on ChatOllama 5xx semantics.]

### Pitfall 5: Schema validation failure raises late, not at construction

**What goes wrong:** `create_agent(response_format=ToolStrategy(BadSchema))` does NOT raise at construction time. The synthesized tool is built lazily inside `_get_bound_model` on first invoke. A typo'd schema attribute or unsupported Python type only surfaces at job execution.

**Why it happens:** `_SchemaSpec.__init__` (`structured_output.py:138–191`) validates supported schema kinds (Pydantic, dataclass, TypedDict, JSON schema dict) at strategy-construction time, but the `_create_agent` call itself does not synthesize the tool until first model invocation.

**How to avoid:** The 5 schemas are battle-tested Pydantic v2 models with simple types; a unit test that instantiates each adapter with `response_format=<Model>` and calls `agent.invoke` against a stub LLM would catch any future regression. Since Phase 11's positive test uses a mocked `result` rather than a real agent invoke, no construction-time guard is added — but the plan should note this for the deferred Phase 12 (middleware-based instrumentation) work.

**Warning signs:** First production run after a schema change throws `ValueError: Failed to parse data to {Schema}: ...`.

[VERIFIED: `structured_output.py:138–191`; `factory.py:1131–1258` (bound-model build at invoke).]

### Pitfall 6: `acknowledge-add-recipe` exclusion rationale

**What goes wrong:** If someone later wires `response_format` onto `acknowledge-add-recipe` without removing `return_direct=True` from QueueTool, the agent terminates with a ToolMessage (from QueueTool short-circuit) and never gets a chance to call the synthesized emit tool. `structured_response` stays `None`. The fail-loud `_extract_task_output` would then raise on every ack step.

**Why it happens:** `return_direct=True` ends the graph at the tool node (Phase 07.1 fix verified at `tests/test_workflow_runner.py:269–293`). The structured-emit tool is just another tool; if a return_direct tool fires first, it wins.

**How to avoid:** Document the exclusion in the bumped prompts / code comments. Do NOT add `response_format_model` to `AgentConfig` for `acknowledge-add-recipe`. The flag-based dispatch in `_extract_task_output` (`expects_structured=config.response_format_model is not None`) keeps the tool-message branch for return_direct agents.

**Warning signs:** `ValueError: structured_response missing` on every `acknowledge-add-recipe` step.

[VERIFIED: `tests/test_workflow_runner.py:269–358` already exercises the return_direct path; this phase must not break it.]

## Code Examples

### Example 1: Updated `OllamaBackend.create_agent`

```python
# Source: src/robotina/llm/__init__.py — replacement for lines 215–224
# Verified against .venv/.../langchain/agents/structured_output.py:194 (ToolStrategy)
# and .venv/.../langchain/agents/factory.py:679 (response_format kwarg signature)

def create_agent(
    self,
    system_prompt: str,
    tools: list[BaseTool] | None = None,
    response_format: type[BaseModel] | None = None,
) -> Any:
    kwargs: dict[str, Any] = {
        "model": self._model,
        "tools": tools or [],
        "system_prompt": system_prompt,
    }
    if response_format is not None:
        from langchain.agents.structured_output import ToolStrategy
        # Explicit ToolStrategy: do NOT let AutoStrategy pick ProviderStrategy
        # via the FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT match on "gpt-oss".
        kwargs["response_format"] = ToolStrategy(response_format)
    return _create_agent(**kwargs)
```

### Example 2: Updated `AnthropicBackend.create_agent` / `OpenAIBackend.create_agent`

```python
# Source: src/robotina/llm/__init__.py — same shape as OllamaBackend but ProviderStrategy

def create_agent(
    self,
    system_prompt: str,
    tools: list[BaseTool] | None = None,
    response_format: type[BaseModel] | None = None,
) -> Any:
    kwargs: dict[str, Any] = {
        "model": self._model,
        "tools": tools or [],
        "system_prompt": system_prompt,
    }
    if response_format is not None:
        from langchain.agents.structured_output import ProviderStrategy
        kwargs["response_format"] = ProviderStrategy(response_format)
    return _create_agent(**kwargs)
```

### Example 3: Updated `LLMBackend` Protocol

```python
# Source: src/robotina/llm/__init__.py:162–191 — replacement

from pydantic import BaseModel

@runtime_checkable
class LLMBackend(Protocol):
    @property
    def model(self) -> BaseChatModel: ...

    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
        response_format: type[BaseModel] | None = None,
    ) -> Any:
        """Return a runnable agent graph bound to this model.

        When response_format is provided, the adapter wraps it in the
        provider-appropriate strategy:
          - Ollama → ToolStrategy (synthesized emit tool)
          - Anthropic / OpenAI → ProviderStrategy (native strict-schema)

        The agent's invoke result will populate state['structured_response']
        with a Pydantic instance of `response_format`.
        """
        ...
```

### Example 4: Updated `AgentConfig` and registry entries

```python
# Source: src/robotina/agent/agents.py:23–44 — add field

from pydantic import BaseModel

@dataclass
class AgentConfig:
    task_type: str
    model_config: dict
    prompt_path: str
    skills: list[str] = field(default_factory=list)
    tools: list = field(default_factory=list)
    response_format_model: type[BaseModel] | None = None   # NEW

# Source: agents.py:69–133 — populate for the 5 agents (illustrative)

from robotina.queue.task_types import (
    RecipeResearchGatherOutput,
    RecipeResearchInstructionsOutput,
    RecipeResearchIngredientsOutput,
    RecipeResearchMetadataOutput,
    RecipeLoadOutput,
)

AGENT_REGISTRY["recipe-research-gather"].response_format_model = RecipeResearchGatherOutput
# ... and so on for the other 4.
# (In practice, set inline in the dict literal; this snippet is for clarity.)
```

### Example 5: Threading kwarg through `run_task`

```python
# Source: src/robotina/queue/jobs.py:175 — replacement

# OLD:
# agent = backend.create_agent(system_prompt=prompt_text, tools=tools)
# NEW:
agent = backend.create_agent(
    system_prompt=prompt_text,
    tools=tools,
    response_format=config.response_format_model,  # None for non-bound agents
)
```

### Example 6: Tests — positive + negative for new `_extract_task_output`

```python
# Source: tests/test_workflow_runner.py — additions

import pytest
from pydantic import BaseModel
from robotina.queue.workflow_runner import _extract_task_output

class _Toy(BaseModel):
    x: int
    y: str

def test_extract_returns_model_dump_when_structured_response_present():
    result = {
        "messages": [],  # contents irrelevant on structured path
        "structured_response": _Toy(x=1, y="hi"),
    }
    assert _extract_task_output(result, expects_structured=True) == {"x": 1, "y": "hi"}

def test_extract_raises_when_structured_expected_but_missing():
    result = {"messages": [], "structured_response": None}
    with pytest.raises(ValueError, match="structured_response missing"):
        _extract_task_output(result, expects_structured=True)

def test_extract_raises_when_structured_expected_but_key_absent():
    result = {"messages": []}
    with pytest.raises(ValueError, match="structured_response missing"):
        _extract_task_output(result, expects_structured=True)
```

The existing `test_extract_task_output_handles_return_direct_toolmessage` at `tests/test_workflow_runner.py:269` must be adapted to call `_extract_task_output(result, expects_structured=False)` — the assertion stays the same.

### Override file format

`overrides/openai.json` and `overrides/staging.ollama.json` only override `model_config` and `prompt_path` (per `get_agent_config` at `agents.py:175–183`). Per the locked decision plus the anti-pattern note above, `response_format_model` is **not** added to the overridable set. Therefore **`overrides/*.json` files do not need to change**. The repo-memory rule "Keep overrides/* in sync with AGENT_REGISTRY" is satisfied because we are not adding any field that the override files care about.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Free-text JSON in agent reply + custom parser | `response_format=` on `create_agent` returning `structured_response` | LangChain 1.0 (Sept 2025), matured in 1.2 | Token-level schema enforcement on providers that support it; tool-call-validation on those that don't. Eliminates prose-wrap parse failures by construction. |
| `with_structured_output(...)` on `BaseChatModel` | `response_format` on `create_agent` (graph-level) | LangChain 1.x | The model-level method still exists and still works; for agents, the graph-level integration is preferred because it also populates `structured_response` in the AgentState, plays nicely with tools, and applies strategy auto-detection. |
| `AgentExecutor` + output parsers | `langchain.agents.create_agent` + `response_format` | LangChain 1.x | AgentExecutor is deprecated; output parsers were the canonical way to enforce shape. Now obsolete for new code. |

**Deprecated/outdated:**
- The `_extract_task_output` 60-line parse ladder. It served us during Phases 6–10 when free-text was the only option. Phase 11 retires it.
- The `"respond with valid JSON only"` boilerplate in the affected prompts. Schema is now token-enforced.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | OpenAI strict mode rejects optional fields with `default=None` whose JSON-schema is `anyOf: [type, null]` without being in `required`. | Pitfall 3 | Low — if I'm wrong and OpenAI accepts it, the strict-mode fix becomes a no-op; nothing breaks. If correct and we ignore it, OpenAI override fails at first invoke (visible immediately). [ASSUMED] |
| A2 | Anthropic ProviderStrategy is tolerant of optional fields under Claude's tool-use schema. | Pitfall 3 | Low — same recovery as A1. Easily falsified at planning time by attempting an Anthropic E2E. [ASSUMED] |
| A3 | The repo convention is to write a new `V###.md` for each prompt bump and update `AgentConfig.prompt_path`, not to overwrite. | Runtime State Inventory → "Prompts on disk" | Low — the existing `V001.md` → `V002.md` pattern in `recipe-research-gather` confirms this. [VERIFIED via filesystem listing convention in agents.py paths] |
| A4 | `WF-08` is an unused ID in the workflow-runner family. | Phase Requirements | Low — easy to verify at plan time by grepping REQUIREMENTS.md. [ASSUMED; the convention exists but I didn't enumerate every WF-* in the file] |

## Open Questions

1. **Should `_extract_task_output` take `expects_structured: bool` from the caller, or should it look up `AgentConfig.response_format_model` itself?**
   - What we know: Today's signature is `(result: dict)`. `on_step_complete` has the step in scope and can resolve `task_type` → `AgentConfig` via `get_agent_config`.
   - What's unclear: Passing a bool keeps `_extract_task_output` decoupled from the agent registry (testable in isolation). Doing the lookup inside `_extract_task_output` saves the caller a line. Both work.
   - Recommendation: Pass the bool. Pure-function `_extract_task_output` is easier to unit-test (no registry import in test setup). This is what the code example above does.

2. **What happens when the model declines to call any tool on a ToolStrategy agent (Ollama)?**
   - What we know: `factory.py:1242` forces `tool_choice="any"` when structured output tools are present. The model is required to call a tool.
   - What's unclear: If gpt-oss:20b cannot satisfy the schema AND is forbidden from text-only finish, does the graph terminate with an empty structured_response or hang in a loop? My read of the code is that the loop runs until any AIMessage matches the structured-output tool OR a normal tool — there's no explicit max-iterations cap visible in the snippet I read; if there's a recursion limit, it raises `GraphRecursionError`.
   - Recommendation: Look at `factory.py` recursion-limit handling (or set `langgraph` `recursion_limit` explicitly) during planning. For Phase 11 ship-readiness this is an edge case behind the 3-query manual checkpoint; it's not blocking but should be noted.

3. **Will the `name` argument on `create_agent` (`factory.py:687`) be useful for LangWatch correlation?**
   - What we know: `name` sets `output.name` on each AIMessage. LangWatch tags traces by agent name elsewhere.
   - What's unclear: Whether passing `name=task_type` here helps trace organization.
   - Recommendation: Defer to Phase 12 (middleware-based instrumentation). Not blocking.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `langchain` | ToolStrategy / ProviderStrategy imports | ✓ | 1.2.13 | — |
| `langchain-core` | BaseChatModel base | ✓ | 1.2.22 | — |
| `langgraph` | Underlying graph runtime | ✓ | 1.1.3 | — |
| `langchain-anthropic` | AnthropicBackend | ✓ | 1.4.0 | — |
| `langchain-openai` | OpenAIBackend | ✓ | 1.1.12 | — |
| `langchain-ollama` | OllamaBackend | ✓ | 1.0.1 | — |
| `pydantic` | All output models | ✓ (transitive, v2) | n/a checked | — |
| Ollama daemon at `localhost:11434` | E2E manual checkpoint | n/a (deploy/dev concern) | — | If unreachable, the 3-query checkpoint cannot be run; flag for human. |
| `gpt-oss:20b` pulled in Ollama | Same | n/a | — | Same as above. |

**Missing dependencies with no fallback:** None at the code level.
**Missing dependencies with fallback:** None — Ollama daemon liveness is an operations concern, not a code concern.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` (with `pytest-asyncio` for async tests elsewhere; not needed for this phase's tests, which are sync) |
| Config file | `pyproject.toml` (project-wide config; verified by repo structure) |
| Quick run command | `uv run pytest tests/test_workflow_runner.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RRECIPE-07 | Each recipe-research sub-agent accepts response_format and produces structured_response | unit | `uv run pytest tests/test_workflow_runner.py::test_extract_returns_model_dump_when_structured_response_present -x` | ❌ Wave 0 — new test |
| RLOAD-07 | recipe-load accepts response_format and produces structured_response | unit (shared with RRECIPE-07) | same as above | ❌ Wave 0 |
| WF-08 | `_extract_task_output` reads structured_response when expects_structured=True; raises ValueError when missing | unit (positive + negative) | `uv run pytest tests/test_workflow_runner.py::test_extract_raises_when_structured_expected_but_missing -x` | ❌ Wave 0 |
| WF-08 (continued) | `_extract_task_output` preserves tool_message branch for non-response_format agents | unit | `uv run pytest tests/test_workflow_runner.py::test_extract_task_output_handles_return_direct_toolmessage -x` | ✅ Exists (adapt signature) |
| WF-08 (continued) | `on_step_complete` continues to work for return_direct ack flow after refactor | unit (regression) | `uv run pytest tests/test_workflow_runner.py::test_on_step_complete_advances_after_return_direct_ack -x` | ✅ Exists (no change expected) |
| RRECIPE-07 / RLOAD-07 e2e | 3 distinct recipe queries succeed end-to-end | manual | `uv run agent` + Telegram queries, signed off in VERIFICATION.md | n/a (manual gate) |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_workflow_runner.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green before `/gsd-verify-work`, plus manual 3-query E2E in VERIFICATION.md.

### Wave 0 Gaps

- [ ] Add positive + negative `_extract_task_output` tests (new functions in `tests/test_workflow_runner.py`).
- [ ] Adapt `test_extract_task_output_handles_return_direct_toolmessage` to the new signature `expects_structured=False`.
- [ ] Adapt `test_on_step_complete_writes_artifact`, `test_on_step_complete_marks_step_done`, `test_on_step_complete_enqueues_next_step`, `test_on_step_complete_marks_workflow_done_when_final_step`, `test_on_step_complete_advances_after_return_direct_ack` if the on_step_complete signature changes — the caller now needs to pass `expects_structured` (or look it up). The minimally-invasive option: have `on_step_complete` resolve from `task_type` internally, leaving these tests untouched.

*(Framework install: none — pytest is already in dev deps.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface change. API tokens already managed per `model_config["api_key_env"]`. |
| V3 Session Management | no | No sessions involved. |
| V4 Access Control | no | No access-control change. |
| V5 Input Validation | yes (incidentally) | Pydantic v2 + LangChain structured-output parser. The phase strengthens input validation on agent output by token-level enforcement. |
| V6 Cryptography | no | No crypto. |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| LLM prompt injection that emits crafted JSON to trigger downstream side effects | Tampering | Schema enforcement keeps the artifact shape consistent; downstream consumers (`recipe-load` HouseholdManagerApiTool) validate field semantics. No new mitigation needed for this phase. |
| Tool-call argument injection from LLM-generated content | Tampering | All side-effecting tools (`HouseholdManagerApiTool`, `QueueTool`, `StartWorkflowTool`) already validate inputs at the tool boundary. Out of Phase 11 scope. |
| API token leakage in agent output | Information Disclosure | The 5 Output schemas have no token-shaped fields; structured enforcement actually makes accidental token-leak harder (the model cannot tack on free-text). [VERIFIED by reading task_types.py models.] |

## Project Constraints (from CLAUDE.md)

- **Tech stack** (`langchain>=1.2`, `langchain-core>=1.2`, `langgraph>=1.0`, Pydantic v2) — Phase 11 introduces zero new dependencies; all changes use already-pinned libraries. ✓
- **`create_agent` lives in `langchain.agents`, not `langgraph.prebuilt`** — Phase 11 calls the same import that Phase 10 already established (`from langchain.agents import create_agent as _create_agent` at `src/robotina/llm/__init__.py:32`). ✓
- **All adapter instances created INSIDE `run_task`, never at module level** (locked D-09) — Phase 11 keeps this; `response_format=` is just a kwarg threaded through the existing per-job construction. ✓
- **System prompts in English; user-facing reply text in Spanish** — The 5 affected prompts are sub-agents that emit JSON, not user-facing replies. English prompts only. ✓
- **Notifications always at front of queue (`at_front=True`)** — N/A for this phase; affects send-notification only, which is out of scope. ✓
- **Keep `overrides/*.json` in sync with AGENT_REGISTRY** — Verified that `response_format_model` is **not** overridable (and should not be), so override files do not need to change. ✓
- **No quick-task IDs in code/comments/docstrings** — Plan must brief executors accordingly. ✓ (informational)
- **Always update `.env.example`** — No new env vars in this phase. ✓ (informational)

## Sources

### Primary (HIGH confidence — installed library, verified via Read tool and Python execution)

- `/home/solanoe/code/robotina-gsd/.venv/lib/python3.12/site-packages/langchain/agents/__init__.py:3` — `from langchain.agents.factory import create_agent`
- `/home/solanoe/code/robotina-gsd/.venv/lib/python3.12/site-packages/langchain/agents/factory.py:148–158` — `FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT` includes `"gpt-oss"`
- `/home/solanoe/code/robotina-gsd/.venv/lib/python3.12/site-packages/langchain/agents/factory.py:486–528` — `_supports_provider_strategy` logic
- `/home/solanoe/code/robotina-gsd/.venv/lib/python3.12/site-packages/langchain/agents/factory.py:673–691` — `create_agent` signature including `response_format`
- `/home/solanoe/code/robotina-gsd/.venv/lib/python3.12/site-packages/langchain/agents/factory.py:1027–1129` — `_handle_model_output` populates `structured_response` for both strategies
- `/home/solanoe/code/robotina-gsd/.venv/lib/python3.12/site-packages/langchain/agents/factory.py:1131–1258` — `_get_bound_model`, AutoStrategy resolution, tool list construction
- `/home/solanoe/code/robotina-gsd/.venv/lib/python3.12/site-packages/langchain/agents/structured_output.py:138–191` — `_SchemaSpec` initialization
- `/home/solanoe/code/robotina-gsd/.venv/lib/python3.12/site-packages/langchain/agents/structured_output.py:194–257` — `ToolStrategy`
- `/home/solanoe/code/robotina-gsd/.venv/lib/python3.12/site-packages/langchain/agents/structured_output.py:260–304` — `ProviderStrategy` + `to_model_kwargs`
- `/home/solanoe/code/robotina-gsd/.venv/lib/python3.12/site-packages/langchain/agents/middleware/types.py:350–368` — `AgentState` and `_OutputAgentState` with `structured_response`
- `/home/solanoe/code/robotina-gsd/src/robotina/llm/__init__.py` — current adapter shapes
- `/home/solanoe/code/robotina-gsd/src/robotina/agent/agents.py` — registry + AgentConfig + overrides
- `/home/solanoe/code/robotina-gsd/src/robotina/queue/jobs.py` — `run_task` integration point
- `/home/solanoe/code/robotina-gsd/src/robotina/queue/workflow_runner.py:29–87` — current `_extract_task_output`
- `/home/solanoe/code/robotina-gsd/src/robotina/queue/task_types.py` — 5 Output models
- `/home/solanoe/code/robotina-gsd/tests/test_workflow_runner.py:269–358` — existing tests to adapt
- `/home/solanoe/code/robotina-gsd/.planning/REQUIREMENTS.md:85–211` — existing RRECIPE / RLOAD ID conventions and traceability table

### Secondary (MEDIUM confidence)

- Empirical Python smoke tests run against `.venv`: confirmed `_supports_provider_strategy(ChatOllama(model='gpt-oss:20b')) == True`; confirmed Anthropic and OpenAI model profiles report `structured_output: True`; confirmed JSON schema for `RecipeResearchGatherOutput.recipes` is `{additionalProperties: true}`.
- Phase 10 RESEARCH (`/home/solanoe/code/robotina-gsd/.planning/phases/10-langchain-1-x-agent-api-migration/`) — established `create_agent` import path, `_RetryingChatOllama` rationale.

### Tertiary (LOW confidence — assumed knowledge, flagged in Assumptions Log)

- OpenAI strict-mode rejection of optional-fields-without-required (A1, A2 in Assumptions Log).

## Metadata

**Confidence breakdown:**
- Standard stack & API surface: HIGH — all imports, parameters, and types verified in installed `.venv` files.
- Strategy auto-resolution behavior: HIGH — empirically verified by calling `_supports_provider_strategy` with each backend.
- Pydantic schema → strict-mode interaction (OpenAI): MEDIUM — schema shapes verified; OpenAI strict-mode constraints come from cross-reading the LangChain `ProviderStrategy.to_model_kwargs` source plus general knowledge of OpenAI strict mode. Worst case here is "OpenAI override fails noisily at first invoke" — easy to detect and fix.
- Robotina integration points: HIGH — all touched files read directly.
- Test coverage: HIGH — existing tests inspected; gaps identified.

**Research date:** 2026-05-13
**Valid until:** 2026-06-13 (langchain 1.x API surface is stable; revisit if `langchain>=1.3` ships and changes the `response_format` shape, or if a non-Ollama provider is activated for the gather sub-agent).
