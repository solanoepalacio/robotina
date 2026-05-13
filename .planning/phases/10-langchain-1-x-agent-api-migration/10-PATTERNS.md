# Phase 10: LangChain 1.x Agent API Migration - Pattern Map

**Mapped:** 2026-05-12
**Files analyzed:** 14 (5 source, 5 test, 2 experiment, 1 NEW decision, 1 doc-update CLAUDE.md, plus REQUIREMENTS.md / STATE.md / PROJECT.md edits)
**Analogs found:** 14 / 14 — for migration files the file IS its own analog (before/after code excerpts); for the new decision record the analog is `.planning/decisions/switch-to-simple-worker.md`

## Notes on Approach

This is a **pure migration** phase, not new code. For each touched file, the "analog" is the file itself — the pattern is the existing code that must be swapped for the new API. So this PATTERNS.md is **heavy on before/after excerpts** rather than copy-from-X excerpts. Two exceptions:

1. `.planning/decisions/agent-12-migrate-to-create-agent.md` — NEW file; analog is `.planning/decisions/switch-to-simple-worker.md` (same directory, same audience, same format expectations).
2. `.planning/REQUIREMENTS.md` AGENT-12 entry — NEW row; analog is the existing AGENT-11 row (line 62).

## File Classification

| Touched File | Role | Data Flow | Closest Analog | Match Quality |
|--------------|------|-----------|----------------|---------------|
| `src/robotina/llm/__init__.py` | adapter / LLM module | request-response (factory) | self (3 call sites) | self |
| `src/robotina/queue/jobs.py` | dispatcher / job entrypoint | request-response | self (docstring only) | self — doc sweep |
| `src/robotina/queue/workflow_runner.py` | runner / artifact extractor | transform | self (docstring only) | self — doc sweep |
| `src/robotina/agent/tools/queue.py` | tool | event-driven (terminal tool) | self (comment only) | self — doc sweep |
| `src/robotina/agent/tools/start_workflow.py` | tool | event-driven (terminal tool) | self (comment only) | self — doc sweep |
| `tests/unit/test_llm_backend.py` | unit test (mock-based) | request-response | self | self |
| `tests/unit/test_queue_tool.py` | unit test (real-agent parity) | event-driven | self | self |
| `tests/unit/test_start_workflow_tool.py` | unit test (real-agent parity) | event-driven | self | self |
| `tests/unit/test_household_manager_api_tool.py` | unit test (real-agent parity) | request-response (strict-args error path) | self | self |
| `tests/test_workflow_runner.py` | integration test | transform | self (comments only) | self — doc sweep |
| `experiments/recipe_research.py` | experiment script | request-response | self (comments only) | self — doc sweep |
| `experiments/recipe_load.py` | experiment script | request-response | self (comments only) | self — doc sweep |
| `CLAUDE.md` | doc / project conventions | n/a | self | self — table edits |
| `.planning/REQUIREMENTS.md` | doc / requirements registry | n/a | AGENT-11 row (line 62) | role-match — add AGENT-12 in same shape |
| `.planning/STATE.md` | doc / decisions log | n/a | self (line 128) | self — in-place rewrite |
| `.planning/PROJECT.md` | doc / Key Decisions table | n/a | other rows in same table | role-match — add a row |
| `.planning/decisions/agent-12-migrate-to-create-agent.md` | NEW decision record | n/a | `.planning/decisions/switch-to-simple-worker.md` | role-match |

## Pattern Assignments

### `src/robotina/llm/__init__.py` (adapter, request-response) — **CORE MIGRATION FILE**

**Analog:** self — the 3 adapter call sites are the load-bearing change.

**Import line — BEFORE (line 32):**
```python
from langgraph.prebuilt import create_react_agent  # locked per AGENT-11/D-03
```

**Import line — AFTER:**
```python
from langchain.agents import create_agent as _create_agent  # AGENT-12
```

Rationale for the `_create_agent` alias: the `LLMBackend.create_agent` *method* shares the name. Without aliasing, the inner factory call self-recurses. The protocol method name stays `create_agent` — that's the public contract used by `run_task`, experiments, and tests.

**LLMBackend Protocol docstring — BEFORE (lines 175-186):**
```python
    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
    ) -> Any:
        """Return a runnable LangGraph ReAct agent bound to this model.

        Uses create_react_agent from langgraph.prebuilt (locked per AGENT-11/D-03).
        Note: langgraph 1.1.3 emits LangGraphDeprecatedSinceV10 — this is expected
        and the API remains fully functional through at least LangGraph v1.x.
        """
        ...
```

**LLMBackend Protocol docstring — AFTER:**
```python
    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
    ) -> Any:
        """Return a runnable agent graph bound to this model.

        Uses ``langchain.agents.create_agent`` (the LangChain 1.x agent factory;
        AGENT-12 supersedes AGENT-11/D-03). The factory returns a
        ``CompiledStateGraph`` whose ``.invoke({"messages": [...]})`` contract is
        unchanged from the previous ``create_react_agent`` path — including
        ``return_direct=True`` short-circuit semantics, strict-args validation
        producing ``ToolMessage(status='error')``, and callback delivery via
        ``RunnableConfig(callbacks=[...])``. Verified empirically against
        ``langchain 1.2.13``.
        """
        ...
```

**`_RetryingChatOllama` docstring — BEFORE (lines 93-97):**
```python
    Why a subclass and not Runnable.with_retry(): with_retry filters by
    exception type only, so it would also retry 4xx — undesirable. And the
    result of with_retry is a RunnableRetry wrapper, which langgraph's
    create_react_agent does not accept (it requires BaseChatModel |
    RunnableBinding).
```

**`_RetryingChatOllama` docstring — AFTER:**
```python
    Why a subclass and not Runnable.with_retry(): with_retry filters by
    exception type only, so it would also retry 4xx — undesirable. And the
    result of with_retry is a RunnableRetry wrapper, which
    ``langchain.agents.create_agent`` does not accept (it requires
    BaseChatModel | RunnableBinding).
```

**OllamaBackend.create_agent — BEFORE (lines 210-219):**
```python
    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
    ) -> Any:
        return create_react_agent(
            model=self._model,
            tools=tools or [],
            prompt=system_prompt,
        )
```

**OllamaBackend.create_agent — AFTER:**
```python
    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
    ) -> Any:
        return _create_agent(
            model=self._model,
            tools=tools or [],
            system_prompt=system_prompt,
        )
```

**AnthropicBackend.create_agent — BEFORE (lines 243-252):**
```python
    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
    ) -> Any:
        return create_react_agent(
            model=self._model,
            tools=tools or [],
            prompt=system_prompt,
        )
```

**AnthropicBackend.create_agent — AFTER:**
```python
    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
    ) -> Any:
        return _create_agent(
            model=self._model,
            tools=tools or [],
            system_prompt=system_prompt,
        )
```

**OpenAIBackend.create_agent — BEFORE (lines 276-285):**
```python
    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
    ) -> Any:
        return create_react_agent(
            model=self._model,
            tools=tools or [],
            prompt=system_prompt,
        )
```

**OpenAIBackend.create_agent — AFTER:**
```python
    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
    ) -> Any:
        return _create_agent(
            model=self._model,
            tools=tools or [],
            system_prompt=system_prompt,
        )
```

**Total LOC impact:** 1 import line + 3 call-site bodies (3 lines each = ~9 lines) + ~8 lines of docstring rewording = ~18 lines.

---

### `src/robotina/queue/jobs.py` (dispatcher, request-response) — **DOC SWEEP ONLY**

**Analog:** self. Functional code is unchanged — `backend.create_agent(system_prompt=..., tools=...)` (line 175) already calls the protocol method, which is what changes its internals.

**Docstring — BEFORE (line 50):**
```python
        Agent invocation result (messages list from create_react_agent).
```

**Docstring — AFTER:**
```python
        Agent invocation result (messages list from langchain.agents.create_agent).
```

No call-site changes needed.

---

### `src/robotina/queue/workflow_runner.py` (runner, transform) — **DOC SWEEP ONLY**

**Analog:** self. `_extract_task_output` logic stays identical; smoke tests confirmed `result["messages"][-1]` contract holds.

**Docstring — BEFORE (lines 36-37, in `_extract_task_output`):**
```python
    short-circuits the prebuilt ``create_react_agent`` graph, the last message
```

**Docstring — AFTER:**
```python
    short-circuits the ``langchain.agents.create_agent`` graph, the last message
```

---

### `src/robotina/agent/tools/queue.py` (tool, event-driven) — **DOC SWEEP ONLY**

**Analog:** self. `return_direct=True` semantics are preserved by the new factory.

**Comment — BEFORE (lines 19-24):**
```python
``create_react_agent`` graph terminates immediately after the tool runs, with no
further LLM invocation. (``Command(goto=END)`` from a tool does NOT
short-circuit the prebuilt graph in langgraph 1.1.x — empirically verified —
hence this approach.)
```

**Comment — AFTER:**
```python
``langchain.agents.create_agent`` graph terminates immediately after the tool
runs, with no further LLM invocation. (``Command(goto=END)`` from a tool does
NOT short-circuit the prebuilt graph — verified for both
``langgraph.prebuilt.create_react_agent`` (legacy) and the LangChain 1.x
``create_agent`` factory — hence this ``return_direct=True`` approach.)
```

---

### `src/robotina/agent/tools/start_workflow.py` (tool, event-driven) — **DOC SWEEP ONLY**

**Analog:** self. Same shape as `queue.py` above.

**Comment — BEFORE (lines 12-17):**
```python
``create_react_agent`` graph terminates immediately after the tool runs (both
```

**Comment — AFTER:**
```python
``langchain.agents.create_agent`` graph terminates immediately after the tool
runs (both
```

---

### `tests/unit/test_llm_backend.py` (unit test, request-response) — **PATCH-TARGET RENAME + ASSERTION INVERSION**

**Analog:** self.

**Patch target — BEFORE (lines 24, 44, 67, repeated 3x):**
```python
    with patch("robotina.llm.create_react_agent", return_value=mock_agent) as mock_cra:
```

**Patch target — AFTER:**
```python
    with patch("robotina.llm._create_agent", return_value=mock_agent) as mock_cra:
```

(Must match whatever alias the adapter uses in `src/robotina/llm/__init__.py`. If the planner picks `_create_agent`, this is the patch target. If they pick `la.create_agent` style, the patch target is `robotina.llm.la.create_agent`. Recommend `_create_agent` for grep-simplicity.)

**Source-grep test — BEFORE (lines 107-118):**
```python
def test_create_react_agent_used_not_agent_executor():
    """AGENT-11: create_react_agent from langgraph.prebuilt is used, not AgentExecutor."""
    import robotina.llm as llm_module
    import inspect

    source_path = inspect.getfile(llm_module)
    with open(source_path) as f:
        source = f.read()

    assert "AgentExecutor" not in source, "AgentExecutor must not be used in robotina.llm"
    assert "create_react_agent" in source, "create_react_agent must be imported from langgraph.prebuilt"
    assert "from langgraph.prebuilt import create_react_agent" in source
```

**Source-grep test — AFTER:**
```python
def test_create_agent_used_not_agent_executor():
    """AGENT-12: create_agent from langchain.agents is used, not AgentExecutor or the deprecated create_react_agent."""
    import robotina.llm as llm_module
    import inspect

    source_path = inspect.getfile(llm_module)
    with open(source_path) as f:
        source = f.read()

    assert "AgentExecutor" not in source, "AgentExecutor must not be used in robotina.llm"
    assert "from langchain.agents import create_agent" in source, (
        "robotina.llm must import create_agent from langchain.agents"
    )
    assert "create_react_agent" not in source, (
        "robotina.llm must not reference the deprecated create_react_agent"
    )
    assert "from langgraph.prebuilt" not in source, (
        "robotina.llm must not import from the deprecated langgraph.prebuilt module"
    )
```

**Per-adapter test docstrings — BEFORE (lines 17, 35, 58):**
```python
    """AGENT-02: OllamaBackend creates a create_react_agent runnable."""
```

**Per-adapter test docstrings — AFTER:**
```python
    """AGENT-02 / AGENT-12: OllamaBackend creates a langchain.agents.create_agent runnable."""
```

---

### `tests/unit/test_queue_tool.py` (unit test, event-driven) — **IMPORT + FACTORY-CALL + NAME RENAME**

**Analog:** self.

**Module docstring — BEFORE (lines 8-10):**
```python
Phase 07.1: QueueTool is terminal via ``return_direct=True``. The LangGraph
``create_react_agent`` graph terminates immediately after the tool runs, with
no further LLM invocation. (``Command(goto=END)`` from a tool does NOT
```

**Module docstring — AFTER:**
```python
Phase 07.1 + AGENT-12: QueueTool is terminal via ``return_direct=True``. The
``langchain.agents.create_agent`` graph terminates immediately after the tool
runs, with no further LLM invocation. (``Command(goto=END)`` from a tool does NOT
```

**Test name + body — BEFORE (lines 77-127):**
```python
def test_queue_tool_short_circuits_create_react_agent():
    """Phase 07.1 regression: drive the QueueTool through a real
    ``create_react_agent`` with a stub model that ALWAYS tries to emit a tool
    call. If the engine truly terminates after the tool runs, the model is
    invoked exactly once. If not, the model is invoked twice (or more).

    This is the test that should fail loudly if anything in our termination
    setup regresses (e.g. ``return_direct`` removed, prebuilt swapped for one
    that doesn't honor it)."""
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage, HumanMessage
    from langgraph.prebuilt import create_react_agent

    ...
    agent = create_react_agent(model=model, tools=[tool])
    agent.invoke({"messages": [HumanMessage(content="please reply")]})

    assert call_count["n"] == 1, (
        f"Expected exactly 1 LLM call (engine terminates after terminal tool); "
        f"got {call_count['n']}. return_direct may have regressed."
    )
```

**Test name + body — AFTER:**
```python
def test_queue_tool_short_circuits_create_agent():
    """Phase 07.1 / AGENT-12 regression: drive the QueueTool through a real
    ``langchain.agents.create_agent`` with a stub model that ALWAYS tries to
    emit a tool call. If the engine truly terminates after the tool runs, the
    model is invoked exactly once. If not, the model is invoked twice (or
    more).

    This is the test that should fail loudly if anything in our termination
    setup regresses (e.g. ``return_direct`` removed, factory swapped for one
    that doesn't honor it)."""
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain.agents import create_agent

    ...
    agent = create_agent(model=model, tools=[tool])
    agent.invoke({"messages": [HumanMessage(content="please reply")]})

    assert call_count["n"] == 1, (
        f"Expected exactly 1 LLM call (engine terminates after terminal tool); "
        f"got {call_count['n']}. return_direct may have regressed."
    )
```

**`bind_tools` override (lines 106-107) stays untouched** — the `create_agent` factory still calls `model.bind_tools(...)` the same way; returning `self` keeps the canned-response behavior. **Do not change this.**

---

### `tests/unit/test_start_workflow_tool.py` (unit test, event-driven) — **IMPORT + FACTORY-CALL + NAME RENAME**

**Analog:** self.

**Module docstring — BEFORE (lines 6-9):**
```python
Phase 07.1: StartWorkflowTool is terminal via ``return_direct=True``. The
LangGraph ``create_react_agent`` graph terminates immediately after the tool
runs (both happy and error paths).
```

**Module docstring — AFTER:**
```python
Phase 07.1 + AGENT-12: StartWorkflowTool is terminal via ``return_direct=True``.
The ``langchain.agents.create_agent`` graph terminates immediately after the
tool runs (both happy and error paths).
```

**Test name + body — BEFORE (lines 116-168):**
```python
def test_start_workflow_tool_short_circuits_create_react_agent():
    """Phase 07.1 regression: drive the StartWorkflowTool through a real
    ``create_react_agent`` with a stub model that always tries to emit a tool
    call. The engine must terminate after the tool runs, regardless of what
    the model wants to do next."""
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage, HumanMessage
    from langgraph.prebuilt import create_react_agent

    ...
    agent = create_react_agent(model=model, tools=[tool])
    agent.invoke({"messages": [HumanMessage(content="add a recipe")]})
```

**Test name + body — AFTER:**
```python
def test_start_workflow_tool_short_circuits_create_agent():
    """Phase 07.1 / AGENT-12 regression: drive the StartWorkflowTool through a
    real ``langchain.agents.create_agent`` with a stub model that always tries
    to emit a tool call. The engine must terminate after the tool runs,
    regardless of what the model wants to do next."""
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain.agents import create_agent

    ...
    agent = create_agent(model=model, tools=[tool])
    agent.invoke({"messages": [HumanMessage(content="add a recipe")]})
```

---

### `tests/unit/test_household_manager_api_tool.py` (unit test, request-response strict-args) — **IMPORT + FACTORY-CALL ONLY (no rename)**

**Analog:** self. This test is named for the *behavior* (`test_extra_field_in_agent_loop_yields_tool_error_message`), not the factory — no rename needed.

**Test body — BEFORE (lines 229-279):**
```python
def test_extra_field_in_agent_loop_yields_tool_error_message(monkeypatch):
    """End-to-end proof: a tool call with an extra field, driven through a
    real ``create_react_agent``, produces a ``ToolMessage(status="error")``
    rather than letting a ``TypeError`` escape ``agent.invoke()``.

    ...
    """
    ...
    from langgraph.prebuilt import create_react_agent
    ...

    class CountingModel(FakeMessagesListChatModel):
        # FakeMessagesListChatModel doesn't know how to bind tools. The
        # prebuilt react agent calls ``model.bind_tools(...)`` before use;
        # returning ``self`` keeps the canned-response behavior intact.
        def bind_tools(self, tools, **kwargs):
            return self

    ...
    agent = create_react_agent(model=model, tools=[tool])
    ...
    result = agent.invoke({"messages": [HumanMessage(content="get foods")]})

    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1, ...
    tm = tool_messages[0]
    assert tm.status == "error", ...
```

**Test body — AFTER:**
```python
def test_extra_field_in_agent_loop_yields_tool_error_message(monkeypatch):
    """End-to-end proof: a tool call with an extra field, driven through a
    real ``langchain.agents.create_agent``, produces a
    ``ToolMessage(status="error")`` rather than letting a ``TypeError`` escape
    ``agent.invoke()``.

    ...
    """
    ...
    from langchain.agents import create_agent
    ...

    class CountingModel(FakeMessagesListChatModel):
        # FakeMessagesListChatModel doesn't know how to bind tools. The
        # ``create_agent`` factory calls ``model.bind_tools(...)`` before use;
        # returning ``self`` keeps the canned-response behavior intact.
        def bind_tools(self, tools, **kwargs):
            return self

    ...
    agent = create_agent(model=model, tools=[tool])
    ...
    result = agent.invoke({"messages": [HumanMessage(content="get foods")]})

    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1, ...
    tm = tool_messages[0]
    assert tm.status == "error", ...
```

---

### `tests/test_workflow_runner.py` (integration test, transform) — **COMMENT SWEEP ONLY**

**Analog:** self. Test logic stays unchanged; the `ToolMessage` last-message contract is preserved.

**Comments — BEFORE (lines 271, 336):**
```python
    create_react_agent graph, the agent's final state has a ToolMessage as the last
```
```python
    # Mirror what create_react_agent leaves in state when QueueTool (return_direct=True) runs:
```

**Comments — AFTER:**
```python
    create_agent graph, the agent's final state has a ToolMessage as the last
```
```python
    # Mirror what langchain.agents.create_agent leaves in state when QueueTool (return_direct=True) runs:
```

---

### `experiments/recipe_research.py` (experiment script, request-response) — **COMMENT SWEEP ONLY**

**Analog:** self. Line 99's `backend.create_agent(system_prompt=..., tools=...)` already uses the protocol method — no functional change.

**Comment — BEFORE (line 106):**
```python
    Per Pitfall 4: create_react_agent returns {"messages": [...]}.
```

**Comment — AFTER:**
```python
    Per Pitfall 4: langchain.agents.create_agent returns {"messages": [...]}.
```

---

### `experiments/recipe_load.py` (experiment script, request-response) — **COMMENT SWEEP ONLY**

**Analog:** self.

**Comment — BEFORE (line 151):**
```python
    Per Pitfall 4: create_react_agent returns {"messages": [...]}.
```

**Comment — AFTER:**
```python
    Per Pitfall 4: langchain.agents.create_agent returns {"messages": [...]}.
```

---

### `CLAUDE.md` (doc, table edits) — **4 TABLE-ROW EDITS**

**Analog:** self. Exact diff text already in RESEARCH.md "CLAUDE.md Update Diff Sketch" — verbatim per the planner.

Four table edits required (see RESEARCH.md sections 1-4 of "CLAUDE.md Update Diff Sketch"):

1. **Core Technologies table** — update `langchain` and `langgraph` rows (versions + description shift).
2. **Alternatives Considered table** — replace `LangGraph create_react_agent | LangChain AgentExecutor` row with `LangChain langchain.agents.create_agent | LangGraph create_react_agent` (polarity flips).
3. **What NOT to Use table** — add new row for `langgraph.prebuilt.create_react_agent`.
4. **Confidence Notes** — update `LangChain package split` row to mention `langchain.agents`.

Full text in RESEARCH.md lines 462-509 of `10-RESEARCH.md`.

---

### `.planning/REQUIREMENTS.md` (doc, registry) — **ADD AGENT-12 + SUPERSEDE AGENT-11**

**Analog:** AGENT-11 row at line 62.

**AGENT-11 existing row (line 62) — BEFORE:**
```markdown
- [x] **AGENT-11**: `create_react_agent` from `langgraph.prebuilt` is used for all agents
```

**AGENT-11 existing row — AFTER (add supersession note in italics):**
```markdown
- [x] **AGENT-11**: `create_react_agent` from `langgraph.prebuilt` is used for all agents *(superseded by AGENT-12 in Phase 10)*
```

**New AGENT-12 entry — to add directly under AGENT-11 (line 63):**
```markdown
- [ ] **AGENT-12**: All agents use `create_agent` from `langchain.agents` (supersedes AGENT-11). The deprecated `langgraph.prebuilt.create_react_agent` is no longer imported anywhere in `src/` or `tests/`. The three `LLMBackend` adapters (Ollama, Anthropic, OpenAI) call `langchain.agents.create_agent(model=…, tools=…, system_prompt=…)` with strict behavior parity — `return_direct=True` short-circuit, message state shape, callback delivery, and strict-args→ToolMessage(status='error') flow are all preserved.
```

**Traceability table — to add new row after AGENT-11 (line 172):**
```markdown
| AGENT-12 | Phase 10 | Complete |
```
(Mark `Complete` only at phase exit; during the plans it stays at `In Progress` or unchecked.)

---

### `.planning/STATE.md` (doc, decisions log) — **REWRITE LINE 128**

**Analog:** self.

**STATE.md line 128 — BEFORE:**
```
- [Phase 04-llm-module-and-agent-infrastructure]: Use create_react_agent from langgraph.prebuilt despite LangGraphDeprecatedSinceV10 warning — locked per AGENT-11/D-03, API remains functional in v1.1.3
```

**STATE.md line 128 — AFTER:**
```
- [Phase 04-llm-module-and-agent-infrastructure]: AGENT-11/D-03 superseded in Phase 10 by AGENT-12 — all agents now use `langchain.agents.create_agent` (LangGraph V1.0 deprecation; removal in V2.0). Behavior parity (return_direct, state shape, callbacks) verified during Phase 10.
```

---

### `.planning/PROJECT.md` (doc, Key Decisions table) — **ADD ROW**

**Analog:** existing rows in the "Key Decisions" table (lines 56-64 per RESEARCH.md).

**New row to add:**
```markdown
| `create_agent` from `langchain.agents` is used for all agents | LangGraph deprecated `create_react_agent` (V1.0; removal in V2.0). The new factory is required to unlock `response_format` (Phase 11) and middleware (Phase 12). Behavior parity verified empirically during Phase 10. | — Active |
```

Match the column count and pipe alignment of existing rows. (Confirm column headers at edit time — RESEARCH cited 3 columns but verify in the actual file.)

---

### `.planning/decisions/agent-12-migrate-to-create-agent.md` (NEW decision record) — **MIRROR `switch-to-simple-worker.md` FORMAT**

**Analog:** `.planning/decisions/switch-to-simple-worker.md` (full content read 2026-05-12).

**Analog format — sections to mirror exactly:**
```markdown
# Decision: <one-line title>

## Context
<2-4 paragraphs: what the existing setup is, what problem(s) it has, evidence>

## What <legacy thing> actually buys us
<bulleted list of the legacy approach's genuine benefits>

## Why those benefits don't apply here
<bulleted list rebutting each, grounded in this project's specifics>

## Proposed change
<numbered list of concrete, narrow code changes>

## Files to change
<bulleted list, one path per bullet with a short note on what changes in each>

## Risk
<single paragraph: rated Low/Medium/High + the one regression scenario worth naming>
```

**Content for the new file (drafted; planner can refine wording in the plan action):**
```markdown
# Decision: Migrate from `langgraph.prebuilt.create_react_agent` to `langchain.agents.create_agent`

## Context

The `LLMBackend.create_agent()` method in `src/robotina/llm/__init__.py` currently
wraps `create_react_agent` from `langgraph.prebuilt`. This API is deprecated in
LangGraph V1.0 — calling it emits `LangGraphDeprecatedSinceV10`, and the
deprecation decorator (`langgraph/prebuilt/chat_agent_executor.py:274-308`)
points to `langchain.agents.create_agent` as the replacement.

The repo's `uv.lock` already pins `langchain 1.2.13` and `langchain-core 1.2.22`,
so the new factory is already available in the venv. AGENT-11/D-03 (Phase 4
decision) explicitly deferred the migration to a "future phase" — Phase 10 is
that phase.

Two near-term phases also depend on this:
- Phase 11 needs `response_format=...` on the factory (only on `create_agent`).
- Phase 12 needs `middleware=[...]` on the factory (only on `create_agent`).

## What `create_react_agent` actually buys us

- It works today. Strict behavior we rely on (`return_direct=True`,
  `{"messages": [...]}` state shape, strict-args→ToolMessage(status='error'),
  callback delivery via `RunnableConfig`) is intact in `langgraph 1.1.3`.
- It is already wired into 5 source files and 4 test files with parity tests.

## Why those benefits don't apply here

- `langchain.agents.create_agent` provides byte-for-byte parity for every
  behavior the project relies on. Verified empirically against `langchain 1.2.13`
  on 2026-05-12 (return_direct short-circuit, system_prompt SystemMessage
  prepending, strict-args ToolMessage, callbacks via RunnableConfig — all
  identical).
- Staying on `create_react_agent` blocks Phases 11 and 12 from accessing
  `response_format=` and `middleware=`, which are the planned mitigations for
  the canelones-de-choclo parse failure class.
- Eventual removal in LangGraph V2.0 forces the migration anyway.

## Proposed change

1. Replace the import in `src/robotina/llm/__init__.py` from
   `from langgraph.prebuilt import create_react_agent` to
   `from langchain.agents import create_agent as _create_agent`. The alias
   prevents self-recursion with the protocol method of the same name.
2. Switch the three adapter call sites (`OllamaBackend`, `AnthropicBackend`,
   `OpenAIBackend`) from `create_react_agent(model=..., tools=..., prompt=...)`
   to `_create_agent(model=..., tools=..., system_prompt=...)`.
3. Update the four test files that construct real agent graphs
   (`test_llm_backend.py`, `test_queue_tool.py`, `test_start_workflow_tool.py`,
   `test_household_manager_api_tool.py`) to import and call `create_agent`.
4. Rename three tests for grep-discoverability: `..._short_circuits_create_react_agent`
   → `..._short_circuits_create_agent` (×2);
   `test_create_react_agent_used_not_agent_executor` →
   `test_create_agent_used_not_agent_executor` and invert its source-grep
   assertions to lock the migration direction.
5. Sweep stale comments/docstrings in 5 source files and 2 experiment files
   that mention `create_react_agent` or `langgraph.prebuilt`.
6. Update CLAUDE.md, PROJECT.md (Key Decisions), REQUIREMENTS.md (add
   AGENT-12, mark AGENT-11 superseded), and STATE.md (rewrite line 128).

## Files to change

- `src/robotina/llm/__init__.py` — import + 3 adapter call sites + Protocol
  docstring
- `tests/unit/test_llm_backend.py` — patch target rename, source-grep test
  inversion, per-adapter test docstrings
- `tests/unit/test_queue_tool.py` — import + factory call + test rename +
  module docstring
- `tests/unit/test_start_workflow_tool.py` — import + factory call + test
  rename + module docstring
- `tests/unit/test_household_manager_api_tool.py` — import + factory call (no
  test rename — name is behavior-based)
- `src/robotina/queue/jobs.py`,
  `src/robotina/queue/workflow_runner.py`,
  `src/robotina/agent/tools/queue.py`,
  `src/robotina/agent/tools/start_workflow.py`,
  `tests/test_workflow_runner.py`,
  `experiments/recipe_research.py`,
  `experiments/recipe_load.py` — comment/docstring sweep
- `CLAUDE.md` — 4 table-row edits (Core Technologies, Alternatives Considered,
  What NOT to Use, Confidence Notes)
- `.planning/REQUIREMENTS.md` — add AGENT-12, mark AGENT-11 superseded, add
  AGENT-12 to traceability
- `.planning/STATE.md` — rewrite line 128 decision log entry
- `.planning/PROJECT.md` — add row to Key Decisions table

## Risk

Low. The migration is a 1:1 API rename with empirically verified behavior parity.
Total functional diff is ~18 LOC plus ~20 LOC of doc/comment hygiene. Rollback
is a single `git revert` per affected commit; no data, no env vars, no lockfile
bumps. The only interaction-level risk is LangWatch trace delivery under the
new factory — covered by criterion 4's end-to-end add-recipe run.
```

## Shared Patterns

### Pattern A: Self-recursion guard (alias on import)

**Source:** RESEARCH.md Pitfall 1.
**Apply to:** Every place that imports `langchain.agents.create_agent` from inside a class whose method is also called `create_agent`.

**Rule:** Either `from langchain.agents import create_agent as _create_agent` (preferred — keeps the public protocol method named `create_agent`), or rename the wrapper method. Don't import the bare name into a module that also defines a method of that name.

**Applies to:** `src/robotina/llm/__init__.py` only. Tests and experiments use the bare name `create_agent` because they don't have a same-named method.

### Pattern B: `bind_tools` override stays untouched

**Source:** existing test code, validated in RESEARCH.md Pitfall 4.
**Apply to:** All three parity tests (`test_queue_tool.py`, `test_start_workflow_tool.py`, `test_household_manager_api_tool.py`).

**Rule:** Keep the `def bind_tools(self, tools, **kwargs): return self` override exactly as is. The new `create_agent` factory still calls `model.bind_tools(...)` the same way.

### Pattern C: Comment-sweep batching

**Source:** RESEARCH.md Pitfall 2 and Files Touched section.
**Apply to:** All 7 doc-only files: `jobs.py`, `workflow_runner.py`, `queue.py`, `start_workflow.py`, `test_workflow_runner.py`, `recipe_research.py`, `recipe_load.py`.

**Rule:** Group all comment/docstring sweeps into a single sub-task / commit. They don't affect behavior; landing them together makes review trivial (one diff, all "create_react_agent" → "create_agent" string changes). Avoid sprinkling them across the functional commits.

### Pattern D: Decision-record format

**Source:** `.planning/decisions/switch-to-simple-worker.md` (40 lines, dated, 6 sections).
**Apply to:** `.planning/decisions/agent-12-migrate-to-create-agent.md`.

**Rule:** Match the section layout (Context / What X buys us / Why those benefits don't apply here / Proposed change (numbered) / Files to change (bulleted) / Risk (single para)). Keep length under ~80 lines. Cite concrete file paths in "Files to change", not abstract roles.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | All 14 touched files have an in-codebase analog (themselves, or the decision-record analog). No file in this phase requires falling back to RESEARCH.md patterns. |

## Metadata

**Analog search scope:** `src/robotina/`, `tests/`, `experiments/`, `.planning/decisions/`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `CLAUDE.md` — all files referenced in RESEARCH.md "Files Touched" section.

**Files scanned:** 14 (5 source, 5 test, 2 experiment, 1 decision-record analog, 1 CLAUDE.md, plus targeted grep across the 3 planning docs).

**Pattern extraction date:** 2026-05-12

## PATTERN MAPPING COMPLETE

**Phase:** 10 - langchain-1-x-agent-api-migration
**Files classified:** 14
**Analogs found:** 14 / 14

### Coverage
- Files with self-analog (in-place migration): 13
- Files with role-match analog (new decision-record): 1
- Files with no analog: 0

### Key Patterns Identified
- **Self-recursion guard:** `from langchain.agents import create_agent as _create_agent` to avoid clobbering the `LLMBackend.create_agent` method name (load-bearing for `src/robotina/llm/__init__.py`).
- **Strict-parity test pattern preserved:** `FakeMessagesListChatModel` + `def bind_tools(self, tools, **kwargs): return self` override continues to work under the new factory — do NOT change.
- **Three-axis sweep per file:** functional code (3 adapter call sites) + test imports/calls (4 files) + doc strings & comments (7 files) + planning docs (4 files) + 1 new decision record. The functional surface is tiny; the hygiene surface is wider.

### File Created
`/home/solanoe/code/robotina-gsd/.planning/phases/10-langchain-1-x-agent-api-migration/10-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference per-file before/after excerpts and the analog decision-record format directly in PLAN.md actions.
