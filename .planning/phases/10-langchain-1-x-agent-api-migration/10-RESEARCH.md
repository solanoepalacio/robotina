# Phase 10: LangChain 1.x Agent API Migration - Research

**Researched:** 2026-05-12
**Domain:** LangChain 1.x agent API surface; mechanical API swap with strict parity
**Confidence:** HIGH — all critical claims verified by reading the installed library source AND by running smoke scripts against `langchain 1.2.13` in this repo's `.venv`

## Summary

The migration is mechanically simple: change one import (`from langgraph.prebuilt import create_react_agent` → `from langchain.agents import create_agent`), rename one keyword argument (`prompt=` → `system_prompt=`), and update the four test files that construct real agent graphs. Everything else — `return_direct=True` short-circuit semantics, message state shape (`{"messages": [...]}`), callback delivery via `RunnableConfig(callbacks=[...])`, strict-args-schema → `ToolMessage(status='error')` conversion — is **byte-for-byte identical** between the two factories.

The riskiest area named in the phase brief — `return_direct=True` parity — was verified two ways: (1) direct read of `langchain/agents/factory.py` lines 1477-1498 and 1772-1805 confirms the exit-edge logic ("if all executed tools have `return_direct=True`, route to END"); (2) a smoke test against the installed library (`uv run python -c ...`) showed exactly 1 LLM call, last message is `ToolMessage`, total messages = 3. That is identical to the existing `test_queue_tool_short_circuits_create_react_agent` assertion.

There are **no new required parameters**. `create_agent` accepts the same `model`, `tools`, and `system_prompt` (renamed) we already pass. The function returns a `CompiledStateGraph` with the same `.invoke()` contract as the old `create_react_agent` output. No breaking change in stream chunk shapes is relevant here because the codebase only calls `.invoke()`.

**Primary recommendation:** Pure mechanical swap. Three adapter `create_agent` call sites in `src/robotina/llm/__init__.py`, plus four test files that build real agents. Update CLAUDE.md and PROJECT.md/REQUIREMENTS.md decision records. No `response_format`, no middleware, no state-schema changes — those belong to Phases 11 and 12. Add **AGENT-12** as the new requirement that supersedes AGENT-11.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Agent graph construction | LLM adapter (`src/robotina/llm/__init__.py`) | — | Locked by AGENT-01: each `LLMBackend.create_agent()` returns the graph |
| Tool short-circuit semantics (`return_direct=True`) | Agent factory (`langchain.agents.create_agent`) | Tool implementation (`return_direct: bool = True` attr) | Engine-level; tool only declares intent, factory enforces |
| Agent state shape (`{"messages": [...]}`) | Agent factory | Workflow runner (`_extract_task_output`) | Shape is part of the factory contract; runner consumes it |
| Callback / instrumentation delivery | Job dispatcher (`run_task` via `RunnableConfig`) | LangWatch SDK | Callbacks are passed at `.invoke()` time, not bound to the factory |
| Test scaffolding for agent behavior | 4 test files (queue, start_workflow, hh_api, llm_backend) | — | Tests directly import the factory to drive the agent loop |
| Documentation (stack table, decision records) | CLAUDE.md, PROJECT.md, REQUIREMENTS.md | STATE.md (locked decisions section) | Tier-3 docs reflect the change |

## Standard Stack

### Core (versions verified against `uv.lock`)

| Library | Version (locked) | Purpose | Why Standard |
|---------|-----------------|---------|--------------|
| `langchain` | `1.2.13` | Hosts `langchain.agents.create_agent` — the **new** agent factory | Official successor to `langgraph.prebuilt.create_react_agent`; explicit deprecation warning points here |
| `langchain-core` | `1.2.22` | `BaseChatModel`, `BaseTool`, `BaseCallbackHandler`, `RunnableConfig` | Unchanged from Phase 4 |
| `langgraph` | `1.1.3` | Underlying graph engine used **by** `create_agent`; not the agent API surface anymore | Demoted: still pinned (transitive of `langchain`), but `langgraph.prebuilt.create_react_agent` is the deprecated path we leave behind |
| `langchain-anthropic` | `1.4.0` | `ChatAnthropic` adapter | Unchanged |
| `langchain-openai` | `1.1.12` | `ChatOpenAI` adapter | Unchanged |
| `langchain-ollama` | `1.0.1` | `ChatOllama` adapter | Unchanged |
| `langwatch` | `0.17.0` | LLM trace collection | Unchanged; callback wiring identical |

[VERIFIED: `cat /home/solanoe/code/robotina-gsd/uv.lock`]

### Installation
No new dependencies. No version bumps. `langchain.agents` is already importable in the current `.venv`:

```bash
$ uv run python -c "from langchain.agents import create_agent; print(create_agent)"
<function create_agent at 0x...>
```

[VERIFIED: ran in repo `.venv` 2026-05-12]

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `langchain.agents.create_agent` | Keep `langgraph.prebuilt.create_react_agent` | Stays on a deprecated path; emits `LangGraphDeprecatedSinceV10` warnings; blocks Phases 11/12 from using `response_format=` and middleware. Per phase goal — **not acceptable**. |
| `langchain.agents.create_agent` | Build agent graph manually with `StateGraph` + `ToolNode` | Defeats the purpose; loses the factory's correctness guarantees (return_direct, error tool-message handling). **Not considered.** |

## Architecture Patterns

### System Architecture Diagram

```
                                  Caller
                                    │
                                    ▼
                    LLMBackend.create_agent(system_prompt, tools)
                    (src/robotina/llm/__init__.py — 3 adapters)
                                    │
                                    ▼
                    langchain.agents.create_agent(
                        model=self._model,
                        tools=tools,
                        system_prompt=system_prompt,
                    )                                          ← THE ONLY CHANGE
                                    │
                                    ▼
                          CompiledStateGraph
                          (built on langgraph)
                                    │
                                    ▼
                    agent.invoke({"messages": [...]}, config=...)
                                    │
              ┌─────────────────────┼────────────────────┐
              ▼                     ▼                    ▼
        model node           tools node           END / after_agent
              │                     │                    ▲
              │  AIMessage          │ ToolMessage        │
              │  (with tool_calls?) │                    │
              └────► tools ─────────┘                    │
                       │  (if return_direct ALL):        │
                       └─────────────────────────────────┘
                          (engine-enforced exit)

Downstream:  workflow_runner._extract_task_output(result)
             reads result["messages"][-1] — same contract
```

### Recommended Project Structure (no change)

```
src/robotina/
├── llm/__init__.py          # 3 adapters — ONE import line + 3 call-site updates
├── agent/tools/
│   ├── queue.py             # return_direct=True — unchanged
│   └── start_workflow.py    # return_direct=True — unchanged
├── queue/
│   ├── jobs.py              # backend.create_agent(system_prompt=…, tools=…) — UNCHANGED
│   └── workflow_runner.py   # _extract_task_output — UNCHANGED (logic identical)
tests/
├── unit/test_llm_backend.py            # patch target rename
├── unit/test_queue_tool.py             # parity test — import + call rename
├── unit/test_start_workflow_tool.py    # parity test — import + call rename
└── unit/test_household_manager_api_tool.py  # parity test — import + call rename
```

### Pattern 1: Adapter Migration (uniform across all 3 backends)

**Before:**
```python
# Source: src/robotina/llm/__init__.py:32
from langgraph.prebuilt import create_react_agent  # locked per AGENT-11/D-03

# Source: src/robotina/llm/__init__.py:210-219 (OllamaBackend.create_agent — sample)
def create_agent(
    self,
    system_prompt: str,
    tools: list[BaseTool] | None = None,
) -> Any:
    return create_react_agent(
        model=self._model,
        tools=tools or [],
        prompt=system_prompt,        # ← old keyword
    )
```

**After:**
```python
# src/robotina/llm/__init__.py (line ~32 — replace import)
from langchain.agents import create_agent as _create_agent  # AGENT-12

# OllamaBackend.create_agent (and identically for AnthropicBackend, OpenAIBackend)
def create_agent(
    self,
    system_prompt: str,
    tools: list[BaseTool] | None = None,
) -> Any:
    return _create_agent(
        model=self._model,
        tools=tools or [],
        system_prompt=system_prompt,  # ← new keyword
    )
```

Notes:
- The local alias `_create_agent` (or rename our method) is needed because the protocol method is also called `create_agent` — without aliasing, the inner call would self-recurse.
- Alternative: `import langchain.agents as la` and call `la.create_agent(...)`. Either is fine; pick the one the planner prefers for grep-ability. (Recommendation: `_create_agent` alias because it leaves call sites short.)

### Pattern 2: Test File Migration (uniform across all 4 files)

**Before:**
```python
# Source: tests/unit/test_queue_tool.py:88, 121 (representative)
from langgraph.prebuilt import create_react_agent
...
agent = create_react_agent(model=model, tools=[tool])
```

**After:**
```python
from langchain.agents import create_agent
...
agent = create_agent(model=model, tools=[tool])
```

For `test_llm_backend.py`, the patch target also changes:
**Before:** `patch("robotina.llm.create_react_agent", return_value=mock_agent)`
**After:** `patch("robotina.llm._create_agent", return_value=mock_agent)` (or whatever alias the adapter uses)

Plus `test_create_react_agent_used_not_agent_executor` (lines 107-118) needs the source-grep assertions inverted:
```python
# Replace these assertions:
assert "from langgraph.prebuilt import create_react_agent" in source
# With:
assert "from langchain.agents import create_agent" in source
assert "create_react_agent" not in source  # negative assertion locks the migration
```
And rename the test to `test_create_agent_used_not_agent_executor` (or `_not_create_react_agent`).

### Anti-Patterns to Avoid

- **Don't introduce `response_format=`, `middleware=`, or `state_schema=`** — those are explicitly Phases 11 and 12. Strict parity for this phase.
- **Don't change the wrapper signature** of `LLMBackend.create_agent(self, system_prompt, tools)` — that is the public protocol contract used by 7+ call sites (run_task, experiments, tests). Only the internal call to `_create_agent(...)` changes.
- **Don't remove the `RunnableConfig(callbacks=[...])` wiring** — `AgentLoggingHandler` and `langwatch.langchain.LangChainTracer` fire identically under `create_agent`. [VERIFIED: smoke test 2026-05-12]
- **Don't drop the `langgraph` dependency** from `pyproject.toml` — `create_agent` is built on top of it (`langchain.agents.factory` imports `CompiledStateGraph`, `ToolNode`, `StateGraph` from `langgraph`). Removing it would break the install.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tool short-circuit / terminal-tool behavior | Custom routing edges or `Command(goto=END)` from tool `_run` | `tool.return_direct = True` | Factory already implements this correctly; `Command(goto=END)` is documented as **not honored** by `langgraph.prebuilt` (the existing comment in `queue.py:22-24` notes this). The new `create_agent` factory honors `return_direct` identically [VERIFIED: factory.py:1786-1794]. |
| Strict tool-arg validation → recoverable tool error | Custom `try/except` in `_run` | `args_schema` with `ConfigDict(extra='forbid')` | The factory's `ToolNode` already converts `ValidationError` → `ToolMessage(status='error')` [VERIFIED: smoke test 2026-05-12]. |
| System prompt prepending | Construct `[SystemMessage(...), HumanMessage(...)]` manually before `.invoke` | `create_agent(system_prompt=...)` | Factory prepends a `SystemMessage` to every model call automatically [VERIFIED: smoke test 2026-05-12 confirmed first model invocation got `[SystemMessage, HumanMessage]`]. |
| LangWatch / OTel span correlation | Bypass callbacks and emit spans manually | `agent.invoke(..., config=RunnableConfig(callbacks=[langwatch.langchain.LangChainTracer(), AgentLoggingHandler()]))` | Phase 4 OBS-01/02 wiring is unchanged. |

**Key insight:** This phase is a 1:1 API rename. Every behavior the project relies on — return_direct, message shape, strict-args→ToolMessage, system_prompt prepending, callback delivery — is preserved by the new factory. The phase brief asked us to verify this; we did, and it holds.

## Runtime State Inventory

Pure code change. No stored data, no live service config, no OS-registered state, no env vars, no build artifacts are affected by the migration.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `create_agent` does not persist anything by default (no `checkpointer=` set). | None |
| Live service config | None — agents are constructed per-job, no long-lived service holds the factory output. | None |
| OS-registered state | None | None |
| Secrets / env vars | None — env vars (`*_API_TOKEN`, `LANGWATCH_*`) read in adapters and `run_task` are unchanged. | None |
| Build artifacts | None — `langchain` and `langgraph` are both already installed (verified in `.venv`); no `uv sync` needed. | None |

**Nothing found in any category** — verified by `grep -rn "create_react_agent\|langgraph.prebuilt" /home/solanoe/code/robotina-gsd/src /home/solanoe/code/robotina-gsd/tests` returning only the 5 source files and 4 test files we already know about.

## Common Pitfalls

### Pitfall 1: Self-recursion if the wrapper method shares a name with the factory
**What goes wrong:** If the import is `from langchain.agents import create_agent` and the wrapper method is also called `create_agent`, Python resolves `create_agent(...)` inside the method to `self.create_agent` (the wrapper itself), causing infinite recursion.
**Why it happens:** Module-level `create_agent` shadows nothing if no `as` alias is used, but inside the class body `create_agent` refers to the method (when called on `self`). The current code is safe today because `create_react_agent` has a different name.
**How to avoid:** Either alias on import (`from langchain.agents import create_agent as _create_agent`) or rename the wrapper method. **Recommended:** `from langchain.agents import create_agent as _create_agent` — keeps the public protocol method name (`LLMBackend.create_agent`) unchanged.
**Warning signs:** First test run hits `RecursionError` from one of the 3 adapter call sites.

### Pitfall 2: Stale docstring / comment claims about "langgraph.prebuilt" or "create_react_agent"
**What goes wrong:** Future maintainers read comments like `"Uses create_react_agent from langgraph.prebuilt (locked per AGENT-11/D-03)"` (currently in `LLMBackend.create_agent` docstring lines 180-186) and revert to the old API.
**Why it happens:** Phase 4 locked the language explicitly; that language is now wrong.
**How to avoid:** Sweep for the strings during the migration. Affected locations (verified by `grep`):
- `src/robotina/llm/__init__.py`: line 32 (import comment), 95-96 (RetryingChatOllama docstring), 182-185 (Protocol docstring)
- `src/robotina/queue/jobs.py`: line 50 (run_task docstring)
- `src/robotina/queue/workflow_runner.py`: lines 36-37 (`_extract_task_output` docstring)
- `src/robotina/agent/tools/queue.py`: lines 19-24 (terminal tool note)
- `src/robotina/agent/tools/start_workflow.py`: lines 12-17 (terminal tool note)
- `tests/test_workflow_runner.py`: lines 271, 336 (comments only)
- `experiments/recipe_research.py`: line 106 comment
- `experiments/recipe_load.py`: line 151 comment

These are doc/comment-only sweeps. Functional behavior is unaffected if a comment is missed, but the planner should include them as part of "the same commit" for review-grep accuracy. Doc-only references can be batched into a single sub-task.

### Pitfall 3: Test patch target divergence
**What goes wrong:** `tests/unit/test_llm_backend.py` uses `patch("robotina.llm.create_react_agent", ...)` four times. After the import rename, the patch target name in the module must match the new name (e.g., `robotina.llm._create_agent` if aliased) or the patch silently does nothing.
**Why it happens:** `unittest.mock.patch` looks up an attribute by name at patch time; if the name doesn't exist on the module, **it raises `AttributeError`**, which is loud — but if the wrong name is patched (e.g., still patching `create_react_agent` after rename), pytest will surface the AttributeError. So this is loud, not silent. The risk is choosing a patch target name that doesn't match what the adapter actually binds.
**How to avoid:** Whichever name the adapter uses (`_create_agent`, `la.create_agent`, etc.), the test patches must match. Run `grep -rn "robotina.llm.create_react_agent\|robotina.llm._create_agent" tests/` after the test file edits to confirm zero stale references.
**Warning signs:** `AttributeError: <module 'robotina.llm'> does not have the attribute 'create_react_agent'` in `test_llm_backend.py::test_*_adapter_creates_agent`.

### Pitfall 4: `bind_tools` no-op in fake models
**What goes wrong:** The 3 parity tests in `test_queue_tool.py`, `test_start_workflow_tool.py`, and the in-loop test in `test_household_manager_api_tool.py` use `FakeMessagesListChatModel` and override `bind_tools` to `return self`. **This pattern continues to work under `create_agent`** [VERIFIED: smoke test 2026-05-12]. There is no migration risk here — flagged only because the comments in those tests explicitly mention "the prebuilt react agent calls `model.bind_tools(...)`" and that statement is still true under `create_agent` (the factory binds tools the same way). Update the wording, but don't change the pattern.
**Why it happens:** `FakeMessagesListChatModel` doesn't implement `bind_tools`; the factory needs it called; returning `self` keeps the canned-response behavior.
**How to avoid:** Keep the `bind_tools(self, tools, **kwargs): return self` overrides exactly as they are.

### Pitfall 5: Test-name search artifacts
**What goes wrong:** Two test names in the affected files embed the old factory name: `test_queue_tool_short_circuits_create_react_agent` and `test_start_workflow_tool_short_circuits_create_react_agent`. If you only change imports and not test names, future grep for `create_agent` parity tests will miss them.
**Why it happens:** Test names were chosen when the factory was `create_react_agent`.
**How to avoid:** Rename to `..._short_circuits_create_agent`. Same for `test_create_react_agent_used_not_agent_executor` → `test_create_agent_used_not_agent_executor` in `test_llm_backend.py`. Trivial rename, but matters for grep-discoverability post-migration.

### Pitfall 6: Two factories live in the venv — easy to accidentally mix
**What goes wrong:** Both `langchain.agents.create_agent` and `langgraph.prebuilt.create_react_agent` are importable post-migration (langgraph 1.1.3 still ships `create_react_agent` with a deprecation warning). A stray import of the old one in a new test file would not break anything immediately but would emit the warning and undermine criterion 1 ("no longer imports `create_react_agent`").
**Why it happens:** The deprecation warning is non-fatal; tests pass anyway.
**How to avoid:** Add a grep-based assertion or pre-commit hook step: `grep -rn "from langgraph.prebuilt import create_react_agent" src/ tests/` must return zero hits after the phase. The existing test `test_create_react_agent_used_not_agent_executor` (lines 107-118 of `test_llm_backend.py`) already does the inverse of this — flipping its polarity gives us the lock.

### Pitfall 7: `result["messages"][-1]` consumer code (workflow_runner) MUST be re-verified end-to-end
**What goes wrong:** Theory says `create_agent` and `create_react_agent` produce the same final-message shape. **Smoke tests confirm this** [VERIFIED: 2026-05-12]. But the production code path runs through `_extract_task_output` (`workflow_runner.py:29-87`) under live agent output, which has more variation than the smoke test covers (Anthropic content blocks, structured artifact JSON, etc.). The workflow_runner test suite at `tests/test_workflow_runner.py` already covers the `ToolMessage` branch and the JSON-extraction branches; if `uv run pytest tests/test_workflow_runner.py -q` is green after the migration with no changes to `workflow_runner.py`, the parity holds.
**Why it happens:** This is a "you'd only see it in production" risk; it's not specific to the migration, just amplified by it.
**How to avoid:** Add `uv run pytest tests/test_workflow_runner.py -q` as part of the per-task / per-wave validation in VALIDATION.md (already covered by "full suite" but worth being explicit). Plus criterion 4's end-to-end add-recipe run.

## Code Examples

### Verified Pattern 1: empty tools list still works

```python
# Source: smoke-verified against langchain 1.2.13 (.venv) 2026-05-12
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage

class M(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs): return self

model = M(responses=[AIMessage(content='hello world reply', tool_calls=[])])
agent = create_agent(model=model, tools=[])
result = agent.invoke({'messages': [HumanMessage(content='hi')]})
# Last: AIMessage('hello world reply')  ← identical to old create_react_agent path
```

### Verified Pattern 2: return_direct=True terminates after exactly 1 LLM call

```python
# Source: smoke-verified 2026-05-12 — full output captured in research notes
from langchain.agents import create_agent
from langchain_core.tools import BaseTool

class MyTool(BaseTool):
    name: str = 'mytool'
    description: str = 'test'
    return_direct: bool = True
    def _run(self, x: str) -> str:
        return f'tool ran with x={x}'

# Drive through real create_agent — 1st response = tool call, 2nd = should NEVER be reached
agent = create_agent(model=counting_model, tools=[MyTool()])
result = agent.invoke({'messages': [HumanMessage(content='go')]})
# LLM calls: 1
# Last message type: ToolMessage
# Last message content: 'tool ran with x=hi'
# Number of messages: 3   (HumanMessage, AIMessage(tool_calls=[…]), ToolMessage)
```

### Verified Pattern 3: strict args_schema → ToolMessage(status='error')

```python
# Source: smoke-verified 2026-05-12 — ToolMessage(status='error') content begins with
# "Error invoking tool 'st' with kwargs {…} with error:\n extra: Extra inputs are not permitted"
class StrictArgs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    x: str = Field(...)

class StrictTool(BaseTool):
    name: str = 'st'
    description: str = 't'
    args_schema: type[BaseModel] = StrictArgs
    def _run(self, x: str) -> str: ...

agent = create_agent(model=fake_model, tools=[StrictTool()])
# Result: 1 ToolMessage, status='error', content contains 'extra' and 'Extra inputs are not permitted'
# — existing assertions in test_extra_field_in_agent_loop_yields_tool_error_message still pass
```

### Verified Pattern 4: callbacks via RunnableConfig fire correctly

```python
# Source: smoke-verified 2026-05-12
from langchain_core.runnables import RunnableConfig
agent = create_agent(model=fake_model, tools=[], system_prompt='sp')
result = agent.invoke(
    {'messages': [HumanMessage(content='hi')]},
    config=RunnableConfig(callbacks=[CB()]),
)
# Events: [('chat_start', None)]
# → AgentLoggingHandler.on_chat_model_start and langwatch.langchain.LangChainTracer
#   both fire identically. No instrumentation change needed in run_task or experiments.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `from langgraph.prebuilt import create_react_agent` | `from langchain.agents import create_agent` | LangChain 1.0 / LangGraph 1.0 (the agent factory moved out of `langgraph.prebuilt` into the new `langchain.agents` package) | This phase migrates Robotina to the current API; unlocks `response_format=` (Phase 11) and `middleware=` (Phase 12) |
| `prompt=` keyword on the factory | `system_prompt=` keyword on the factory | Same release | One-keyword rename per adapter call site |
| Pydantic-state agent (`AgentStatePydantic`, `AgentStateWithStructuredResponse`) — deprecated | `AgentState` TypedDict in `langchain.agents` | Same release | Not used by Robotina today; relevant only if Phase 999.1 (state schemas) is ever promoted |
| `ValidationNode` for tool-arg validation — deprecated | Tools auto-validate inside `create_agent` | Same release | Robotina never used `ValidationNode`; current `extra='forbid'` args_schema pattern is the documented modern path |

**Deprecated/outdated:**
- `langgraph.prebuilt.create_react_agent`: emits `LangGraphDeprecatedSinceV10` warning when called; "Deprecated in LangGraph V1.0 to be removed in V2.0" per the warning message [VERIFIED: deprecation decorator at `langgraph/prebuilt/chat_agent_executor.py:274-277`]. Will be **removed** in LangGraph V2.0 — migration is mandatory before that release.

[CITED: docs.langchain.com/oss/python/migrate/langgraph-v1 — "prompt has been renamed to system_prompt"; "AgentStatePydantic deprecated in favor of AgentState in `langchain.agents`"; "ValidationNode has been deprecated because tools automatically validate input with create_agent"]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | LangWatch `langwatch.langchain.LangChainTracer()` is compatible with `create_agent` (callbacks fire as usual) | Code Examples / Pitfall 7 | LOW — empirically verified `RunnableConfig(callbacks=[...])` delivers `on_chat_model_start` events; LangChainTracer uses the same callback API surface, so it should work. Full LangWatch trace appearance in the correct experiment collection is part of criterion 4's end-to-end check. If the trace fails to land, the regression is contained to instrumentation, not agent behavior. |
| A2 | Stale comments in `experiments/recipe_research.py:106` and `experiments/recipe_load.py:151` are pure documentation and don't affect runtime | Pitfall 2 | NEGLIGIBLE — they are inside docstrings, not executable code. |

All other factual claims in this research are tagged `[VERIFIED]` or `[CITED]` and were either confirmed by reading the installed library source under `/home/solanoe/code/robotina-gsd/.venv/lib/python3.12/site-packages/langchain/` or by running smoke scripts in the actual `.venv`.

## Open Questions

1. **AGENT-12 placement in REQUIREMENTS.md.**
   - What we know: AGENT-11 is the current requirement ("`create_react_agent` from `langgraph.prebuilt` is used for all agents"). Success criterion 1 implies a new AGENT-12 superseding AGENT-11.
   - What's unclear: Should AGENT-11 be marked deprecated/superseded with strikethrough, replaced in place, or kept as-is with AGENT-12 added below?
   - Recommendation (see "AGENT-12 candidate" below): **add AGENT-12** as a new active requirement; **mark AGENT-11 as superseded** in the traceability section (don't delete — it's still part of the historical record). The traceability line for AGENT-11 stays "Complete @ Phase 4"; AGENT-12 gets "Complete @ Phase 10" added. This matches how the project already handles other multi-phase requirements (e.g., QUEUE-01 lists Phase 2 only despite ongoing relevance).

2. **PROJECT.md "Key Decisions" decision-record format.**
   - What we know: PROJECT.md `## Key Decisions` table (lines 56-64) currently has 5 rows; none of them is "use `create_react_agent`". The "D-03" identifier in STATE.md refers to a **phase-internal locked decision** in Phase 4 plans, not a global D-XX row in PROJECT.md.
   - What's unclear: Does success criterion 1 want PROJECT.md updated (no row to update), or only the in-phase decision documents?
   - Recommendation: **Add a row to PROJECT.md Key Decisions table**: `| `create_agent` from `langchain.agents` is used for all agents | LangGraph deprecated `create_react_agent`; the new factory is required to unlock `response_format` (Phase 11) and middleware (Phase 12) | — Active |`. Also write a Phase 10 entry in `.planning/decisions/` (mirror the existing `switch-to-simple-worker.md` format) to capture rationale + supersession.

3. **Should `langgraph` be demoted in `pyproject.toml`?**
   - What we know: `langgraph>=0.2` is currently a direct dependency. `langchain 1.2.13` requires `langgraph>=1.0`, so the existing pin is functionally satisfied but the version floor is now wrong.
   - What's unclear: Bump the floor (e.g., `langgraph>=1.0`) or drop the direct entry and let `langchain` pull it transitively?
   - Recommendation: **Keep `langgraph>=1.0` as a direct dependency** because Robotina imports tools/types from it indirectly (via `langchain.agents`) and a direct pin documents the floor. Bump the floor from `>=0.2` to `>=1.0` to match the installed version. Independent of the migration — could be a separate small task in the plan.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `langchain.agents.create_agent` | All three LLMBackend adapters | ✓ | 1.2.13 | — |
| `langgraph.prebuilt.create_react_agent` (legacy, for test parity comparison) | Smoke baseline only | ✓ (deprecated, still importable) | 1.1.3 | — |
| `langchain-core.tools.BaseTool`, `BaseChatModel`, `RunnableConfig` | Adapters + run_task | ✓ | 1.2.22 | — |
| `langchain-core.language_models.fake_chat_models.FakeMessagesListChatModel` | Test scaffolding (existing pattern) | ✓ | 1.2.22 | — |
| `langwatch.langchain.LangChainTracer` | Production instrumentation | ✓ | 0.17.0 | (current code already has a `try/except ImportError` fallback in `run_task` — see `jobs.py:178-193`) |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

[VERIFIED: `find .venv -path "*/langchain/agents/__init__.py"` returns the file; `uv run python -c "from langchain.agents import create_agent"` succeeds]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest 9.x` (`pytest-asyncio 1.x`) — verified via `pyproject.toml [dependency-groups].dev` |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]` block; `testpaths = ["tests"]`, `asyncio_mode = "auto"`, marker `integration`) |
| Quick run command | `uv run pytest tests/unit/test_llm_backend.py tests/unit/test_queue_tool.py tests/unit/test_start_workflow_tool.py tests/unit/test_household_manager_api_tool.py -q` |
| Full suite command | `uv run pytest -q` |
| Phase-gate (end-to-end) | Manual: send "add a recipe for X" to the Telegram bot and confirm the full `research → load → notify` runs without parse failure (success criterion 4) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AGENT-12 | All three adapters call `langchain.agents.create_agent` (not `create_react_agent`) | unit (source-grep assertion) | `uv run pytest tests/unit/test_llm_backend.py::test_create_agent_used_not_agent_executor -x` | ✅ exists (currently named `test_create_react_agent_used_not_agent_executor` — rename + invert assertions) |
| AGENT-12 | `OllamaBackend.create_agent` returns a runnable graph (patched factory) | unit | `uv run pytest tests/unit/test_llm_backend.py::test_ollama_adapter_creates_agent -x` | ✅ exists (patch target needs rename to match new symbol name in module) |
| AGENT-12 | `AnthropicBackend.create_agent` returns a runnable graph | unit | `uv run pytest tests/unit/test_llm_backend.py::test_anthropic_adapter_creates_agent -x` | ✅ exists (same patch-target rename) |
| AGENT-12 | `OpenAIBackend.create_agent` returns a runnable graph | unit | `uv run pytest tests/unit/test_llm_backend.py::test_openai_adapter_creates_agent -x` | ✅ exists (same patch-target rename) |
| AGENT-12 (parity) | `return_direct=True` terminates `create_agent` graph in exactly 1 LLM call with `ToolMessage` as last state message — **QueueTool** | unit | `uv run pytest tests/unit/test_queue_tool.py::test_queue_tool_short_circuits_create_agent -x` | ✅ exists (rename + import swap) |
| AGENT-12 (parity) | Same, for **StartWorkflowTool** | unit | `uv run pytest tests/unit/test_start_workflow_tool.py::test_start_workflow_tool_short_circuits_create_agent -x` | ✅ exists (rename + import swap) |
| AGENT-12 (parity) | Strict-args ToolMessage(status='error') flow under `create_agent` — **HouseholdManagerApiTool** | unit | `uv run pytest tests/unit/test_household_manager_api_tool.py::test_extra_field_in_agent_loop_yields_tool_error_message -x` | ✅ exists (import swap only — no rename needed) |
| AGENT-12 (consumer-side parity) | `_extract_task_output` still handles `ToolMessage` last-message and JSON-bearing AIMessage paths after migration | unit | `uv run pytest tests/test_workflow_runner.py -q` | ✅ exists — should pass unchanged |
| AGENT-12 (end-to-end) | Full `add-recipe` workflow runs without regression on at least one real recipe | manual (Telegram → bot) | — (human checkpoint per criterion 4) | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_llm_backend.py tests/unit/test_queue_tool.py tests/unit/test_start_workflow_tool.py tests/unit/test_household_manager_api_tool.py -q` (target ≤ 1s)
- **Per wave merge:** `uv run pytest -q` (full unit + workflow_runner suite)
- **Phase gate:** Full suite green AND end-to-end add-recipe manual run (criterion 4)

### Wave 0 Gaps
- None for unit test infrastructure — all 4 target test files already exist with parity tests in place.
- One **test rename** wave 0 item: the `..._short_circuits_create_react_agent` → `..._short_circuits_create_agent` rename in two files and the `test_create_react_agent_used_not_agent_executor` → `test_create_agent_used_not_agent_executor` rename in one file. Cosmetic; group into a single rename sub-task.

## Security Domain

No security impact. The migration does not touch:
- Authentication tokens (`*_API_TOKEN` env vars unchanged)
- Input validation (`args_schema` continues to enforce `extra='forbid'` — same behavior under both factories)
- Authorization / tier boundaries (`HouseholdManagerApiTool` still raises `RuntimeError` on 401/403)
- Cryptographic primitives (none used)

`security_enforcement` is not configured in `.planning/config.json`; absence is treated as enabled per the agent contract. The above audit confirms no ASVS-relevant change. No threats added or removed by this phase.

## Project Constraints (from CLAUDE.md)

The migration is constrained by these CLAUDE.md directives:

- **Tech stack locked:** Python, LangChain, Postgres, Redis + RQ, uv — no deviations. (This phase stays within the locked stack — `langchain` is already pinned.) [VERIFIED: CLAUDE.md "Constraints" section]
- **LangGraph `create_react_agent` is now in the "What NOT to Use" zone** — CLAUDE.md currently says "Never — `AgentExecutor` is deprecated… The spec's `LLMBackend.create_agent()` must use LangGraph's `create_react_agent`." After this phase, that table row must invert: `create_react_agent` becomes the "avoid" entry, `create_agent` from `langchain.agents` becomes the recommended path. [VERIFIED: CLAUDE.md `## Alternatives Considered` table]
- **`LLMBackend` Protocol contract unchanged:** "Add a new adapter class implementing `LLMBackend` Protocol — Only need to implement `.model` property and `.create_agent()` method." This protocol-method name stays `create_agent` — the migration changes only what the method *internally calls*, not its public signature. [VERIFIED: `## Stack Patterns by Variant` section]
- **No callback-based observability rewrite in this phase:** CLAUDE.md says "LangChain callbacks for observability → fragile … Use LangWatch + OTel native instrumentation." That migration is **Phase 12** (`@before_model`/`@after_model`/`@wrap_model_call` middleware). Phase 10 must **not** touch `AgentLoggingHandler` or the LangWatch callback wiring — strict parity. [VERIFIED: CLAUDE.md `## What NOT to Use` table]
- **GSD workflow enforcement:** "Before using Edit, Write, or other file-changing tools, start work through a GSD command." This research file is being written under `/gsd-plan-phase 10`'s research step, which is compliant.
- **Always update `.env.example`** (from MEMORY.md `feedback_env_example`): Not applicable — no env vars added or renamed.
- **Avoid premature abstraction** (from MEMORY.md `feedback_avoid_premature_abstraction`): The 3 adapter classes already exist — we're not generalizing. Just swap the inner call. ✓

## CLAUDE.md Update Diff Sketch

For success criterion 5. Three table updates needed in `/home/solanoe/code/robotina-gsd/CLAUDE.md`:

### 1. Core Technologies table — `langchain` and `langgraph` rows

**Before:**
```markdown
| LangChain | `langchain>=0.3`, `langchain-core>=0.3` | Agent orchestration | 0.3 stabilized the `create_react_agent` API from `langgraph` and removed most of the deprecated `AgentExecutor` path. … |
| langgraph | `>=0.2` | `create_react_agent` implementation | As of LangChain 0.2+, `create_react_agent` lives in `langgraph` (not `langchain`). The spec's `create_agent()` method returns a LangGraph runnable. Required for the ReAct agent pattern. |
```

**After:**
```markdown
| LangChain | `langchain>=1.2`, `langchain-core>=1.2` | Agent orchestration via `langchain.agents.create_agent` | LangChain 1.x is the current major. `create_agent` (the agent factory) lives in `langchain.agents`, not `langgraph.prebuilt`. `LLMBackend.create_agent()` wraps this factory. |
| langgraph | `>=1.0` | Underlying graph engine for `create_agent` | `create_agent` is built on `langgraph` (`CompiledStateGraph`, `ToolNode`, `StateGraph`). Pinned as a direct dep to document the floor; not the agent API surface anymore. |
```

### 2. "Alternatives Considered" table — `LangGraph create_react_agent` row

**Before:**
```markdown
| LangGraph `create_react_agent` | LangChain `AgentExecutor` | Never — `AgentExecutor` is deprecated as of LangChain 0.2 and scheduled for removal. The spec's `LLMBackend.create_agent()` must use LangGraph's `create_react_agent`. |
```

**After:**
```markdown
| LangChain `langchain.agents.create_agent` | LangGraph `create_react_agent` | Never — `create_react_agent` is deprecated in LangGraph V1.0 (emits `LangGraphDeprecatedSinceV10`, removal in V2.0). `LLMBackend.create_agent()` must use `langchain.agents.create_agent`. `AgentExecutor` is still forbidden (long-standing). |
```

### 3. "What NOT to Use" table — add `create_react_agent` row

**After (new row added beneath `AgentExecutor`):**
```markdown
| `langgraph.prebuilt.create_react_agent` | Deprecated in LangGraph V1.0, removal in V2.0. Emits `LangGraphDeprecatedSinceV10` at call time. | `langchain.agents.create_agent` |
```

### 4. Confidence Notes — update `LangChain package split` row

**Before:**
```markdown
| LangChain package split (core / langgraph) | HIGH | Well-documented migration that happened LangChain 0.2 → 0.3. `create_react_agent` is in `langgraph.prebuilt`. |
```

**After:**
```markdown
| LangChain package split (core / langgraph / agents) | HIGH | `langchain.agents.create_agent` is the current factory as of LangChain 1.x (verified empirically against installed `langchain 1.2.13`, 2026-05-12). `create_react_agent` is deprecated in `langgraph.prebuilt`. |
```

## AGENT-12 Requirement Candidate (for REQUIREMENTS.md)

Proposed entry to add under `### Agent Infrastructure`, **after** AGENT-11:

```markdown
- [ ] **AGENT-12**: All agents use `create_agent` from `langchain.agents` (supersedes AGENT-11). The deprecated `langgraph.prebuilt.create_react_agent` is no longer imported anywhere in `src/` or `tests/`. The three `LLMBackend` adapters (Ollama, Anthropic, OpenAI) call `langchain.agents.create_agent(model=…, tools=…, system_prompt=…)` with strict behavior parity — `return_direct=True` short-circuit, message state shape, callback delivery, and strict-args→ToolMessage(status='error') flow are all preserved.
```

Plus the traceability table addition:
```markdown
| AGENT-12 | Phase 10 | Complete |  ← becomes Complete after Phase 10 ships
```

And the supersession note (under AGENT-11, optional):
```markdown
- [x] **AGENT-11**: `create_react_agent` from `langgraph.prebuilt` is used for all agents *(superseded by AGENT-12 in Phase 10)*
```

## AGENT-11 / D-03 Decision Record Update

The Phase 4 RESEARCH.md and STATE.md "Decisions" section both reference `AGENT-11/D-03` locking `create_react_agent`. There is no single `decisions/D-03.md` file — the identifier lives in `STATE.md` as a one-line entry. Three places need updates:

### 1. STATE.md "Decisions" section — update the existing line in place

**Before (line 128 of STATE.md):**
```
- [Phase 04-llm-module-and-agent-infrastructure]: Use create_react_agent from langgraph.prebuilt despite LangGraphDeprecatedSinceV10 warning — locked per AGENT-11/D-03, API remains functional in v1.1.3
```

**After:**
```
- [Phase 04-llm-module-and-agent-infrastructure]: AGENT-11/D-03 superseded in Phase 10 by AGENT-12 — all agents now use `langchain.agents.create_agent` (LangGraph V1.0 deprecation; removal in V2.0). Behavior parity (return_direct, state shape, callbacks) verified during Phase 10.
```

### 2. Create a phase-decision file: `.planning/decisions/agent-12-migrate-to-create-agent.md`

Mirror the format of the existing `.planning/decisions/switch-to-simple-worker.md`. Include: context (langgraph deprecation, lockfile already pins 1.x), decision (migrate now, strict parity), consequences (Phases 11/12 unblocked), and verification notes.

### 3. Phase 4 RESEARCH.md note — leave intact as historical record

Phase 4's RESEARCH.md already says "**planner must decide whether to use deprecated API or upgrade**" with a "decision belongs to a future phase" framing — that future phase is **this one**. No edit needed there.

## Rollback Strategy

Two-level rollback if something breaks post-migration:

### Level 1 — Single-commit revert (preferred)

Plan the migration as a small number of focused commits (suggested):
1. Rename test names + invert assertions in `test_llm_backend.py` (lock the migration direction; this commit alone won't pass yet)
2. Switch the 3 adapter call sites in `src/robotina/llm/__init__.py` (now the locked tests pass)
3. Update the 3 parity test files (imports + factory calls)
4. Sweep doc/comment references (5 source files + 2 test files + 2 experiment files)
5. Update CLAUDE.md, REQUIREMENTS.md, STATE.md, PROJECT.md, decisions/

If a regression appears, `git revert` the offending commit. Because the migration is mechanical and isolated to ~10 files, individual reverts are clean.

### Level 2 — Branch revert

If the regression is interaction-level (e.g., LangWatch traces don't land — Assumption A1), and the branch hasn't been merged: `git reset --hard` to the pre-Phase-10 commit. No `uv lock` change needed (we didn't bump versions; `langchain.agents.create_agent` is already importable in the existing lockfile).

### Level 3 — Lockfile pin-back (NOT NEEDED for this phase)

The phase doesn't change `pyproject.toml` versions. The only optional bump is `langgraph>=0.2` → `langgraph>=1.0` (open question 3), which is documentation-only and reversible.

**No data migration to roll back.** No env vars to restore. No service config to revert. Pure code change → revert is `git revert` + a fresh `uv run pytest`.

## Files Touched

For pattern-mapper input (step 7.8). Source files (modify in place):

```
src/robotina/llm/__init__.py
src/robotina/queue/jobs.py
src/robotina/queue/workflow_runner.py
src/robotina/agent/tools/queue.py
src/robotina/agent/tools/start_workflow.py
```

Test files (modify in place):

```
tests/unit/test_llm_backend.py
tests/unit/test_queue_tool.py
tests/unit/test_start_workflow_tool.py
tests/unit/test_household_manager_api_tool.py
tests/test_workflow_runner.py
```

Experiment files (comment-sweep only — no behavior change):

```
experiments/recipe_research.py
experiments/recipe_load.py
```

Planning/docs files (update in place):

```
CLAUDE.md
.planning/REQUIREMENTS.md
.planning/STATE.md
.planning/PROJECT.md
```

New file to create:

```
.planning/decisions/agent-12-migrate-to-create-agent.md
```

**Behavioral diff scope (loc affected):**
- `src/robotina/llm/__init__.py`: 1 import line + 3 method bodies × 1 line each + ~6 lines of stale docstring/comment text = ~10 lines
- 4 test files: ~4 import lines + ~4 factory-call lines + 3 test renames + 4 patch-target updates + 4 assertion changes = ~20 lines
- Experiments + workflow_runner comments: ~6 lines of pure prose
- CLAUDE.md: 4 table-row edits
- Planning docs: 4 small edits + 1 new decision file

**Total functional diff:** under ~30 lines of behavioral change. Plus ~20 lines of doc/comment hygiene. This is genuinely a 1-commit-per-concern migration.

## Sources

### Primary (HIGH confidence)
- `/home/solanoe/code/robotina-gsd/.venv/lib/python3.12/site-packages/langchain/agents/__init__.py` (lines 1-9) — confirms `create_agent` exposed from `langchain.agents`
- `/home/solanoe/code/robotina-gsd/.venv/lib/python3.12/site-packages/langchain/agents/factory.py` (lines 673-690, 1477-1498, 1772-1805) — confirms function signature and `return_direct` exit-edge logic
- `/home/solanoe/code/robotina-gsd/.venv/lib/python3.12/site-packages/langchain/agents/middleware/types.py` (lines 350-368) — confirms `AgentState` shape (`messages`, optional `structured_response`) is identical to old shape for our (no-response_format) case
- `/home/solanoe/code/robotina-gsd/.venv/lib/python3.12/site-packages/langgraph/prebuilt/chat_agent_executor.py` (lines 274-308) — confirms `create_react_agent` is `@deprecated` pointing to `langchain.agents.create_agent`
- Smoke tests run against `.venv` 2026-05-12 — confirmed `return_direct` short-circuit, `system_prompt` SystemMessage prepending, strict-args `ToolMessage(status='error')`, callback delivery via `RunnableConfig`

### Secondary (MEDIUM confidence)
- https://docs.langchain.com/oss/python/migrate/langgraph-v1 — confirms `prompt` → `system_prompt` rename, `AgentStatePydantic` deprecation, `ValidationNode` deprecation
- `uv.lock` — confirms installed versions: `langchain 1.2.13`, `langchain-core 1.2.22`, `langgraph 1.1.3`, `langchain-anthropic 1.4.0`, `langchain-openai 1.1.12`, `langchain-ollama 1.0.1`, `langwatch 0.17.0`

### Tertiary (LOW confidence — none used as load-bearing)
- WebFetch of https://docs.langchain.com/oss/python/langchain/agents did NOT confirm `return_direct` status — that finding came from direct source-read instead, which is HIGH confidence.

## Metadata

**Confidence breakdown:**
- Standard stack & versions: HIGH — verified against `uv.lock` and installed `.venv`
- Architecture / API surface (signature, state shape, return_direct semantics): HIGH — verified by direct source read of installed library AND by smoke tests in `.venv`
- Pitfalls: HIGH — derived from the actual call-site analysis of all 5 source files and 4 test files; not generic
- Test migration mechanics: HIGH — every patch target, test name, and assertion change is grounded in the existing test code
- LangWatch trace integration unchanged: MEDIUM — empirically verified that callbacks fire under `create_agent`; not separately verified that LangWatch traces appear in the experiment collection (Assumption A1; covered by criterion 4)
- CLAUDE.md / decision-record edits: HIGH — exact text diffs proposed from the current file contents

**Research date:** 2026-05-12
**Valid until:** Stable until `langchain 1.x` next minor release (likely 30 days; LangChain 1.x is the current major and the API is documented as stable in this surface)
