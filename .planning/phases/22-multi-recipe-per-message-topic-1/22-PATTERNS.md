# Phase 22: Multi-recipe per message (Topic 1) - Pattern Map

**Mapped:** 2026-05-20
**Files analyzed:** 17 (5 modified, 12 new)
**Analogs found:** 17 / 17

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/robotina/agent/prompts/robotina/V006.md` | prompt | transform | `src/robotina/agent/prompts/robotina/V005.md` | exact (verbatim fork) |
| `src/robotina/agent/agents.py` (MOD) | config | n/a | `src/robotina/agent/agents.py:84` (current V005 line) | exact (in-place) |
| `src/robotina/queue/task_types.py` (MOD `WorkflowOutcomeSummary`) | model | transform | `src/robotina/queue/task_types.py:322-339` `AddRecipeOutcome` | exact (sibling Pydantic) |
| `src/robotina/queue/task_types.py` (MOD `to_user_message`) | model method | transform | `src/robotina/queue/task_types.py:379-395` (current impl) | exact (in-place rewrite) |
| `src/robotina/queue/workflow_runner.py` (MOD `_check_and_dispatch_wake`) | service | event-driven | `src/robotina/queue/workflow_runner.py:195-253` (current impl) | exact (in-place) |
| `experiments/robotina/__init__.py` | package marker | n/a | `experiments/__init__.py` (if present) | role-match |
| `experiments/robotina/multi_recipe_eval.py` | experiment harness | batch / request-response | `experiments/recipe_research.py` | exact (LangWatch experiment script) |
| `pyproject.toml` `[project.scripts]` (MOD) | config | n/a | `pyproject.toml:46-47` | exact (in-place) |
| `tests/queue/test_wake_helper_ordering.py` | test | event-driven | `tests/queue/test_wake_dispatch.py` | exact |
| `tests/queue/test_wake_invocation_input.py` | test | transform | `tests/queue/test_task_types_wake_models.py` (extend or split) | exact |
| `tests/queue/test_task_types_wake_models.py` (extend) | test | transform | same file | exact (in-place) |
| `tests/agents/test_agent_registry.py` (MOD) | test | config-assert | same file | exact (in-place) |
| `.planning/phases/22-.../22-EVAL-SET.md` | spec doc | n/a | `.planning/phases/21-.../21-SMOKE.md` (utterance table) | role-match |
| `.planning/phases/22-.../22-EVAL-RESULTS-ollama.md` | results doc | n/a | `.planning/phases/21-.../21-SMOKE.md` | role-match |
| `.planning/phases/22-.../22-EVAL-RESULTS-openai.md` | results doc | n/a | `.planning/phases/21-.../21-SMOKE.md` | role-match |
| `.planning/phases/22-.../22-SMOKE.md` | verdict doc | n/a | `.planning/phases/21-.../21-SMOKE.md` | exact (template) |
| `.planning/REQUIREMENTS.md` (tick BATCH-01..05) | spec doc | n/a | prior phase tick conventions | exact |

## Pattern Assignments

### `src/robotina/agent/prompts/robotina/V006.md` (prompt, transform)

**Analog:** `src/robotina/agent/prompts/robotina/V005.md` (fork verbatim, then insert new sections)

**Header comment pattern** (V005.md lines 1-12):
```markdown
<!--
Robotina prompt V006

Design refs:
- D-09 V006 = V005 + multi-recipe extraction + ambiguity-via-respond + over-cap ask-to-split
- D-10/D-11/D-12 ambiguity worked examples (compound dish, sauce-on-recipe)
- D-01 over-cap (>5) → respond(ask-to-split) + terminate, no start-workflow
- PITFALL 12 (multi-recipe LLM parsing unreliability) — operationalized by eval set
V005 is RETAINED untouched in this directory for rollback.
-->

# Robotina — V006
```

**Insert point — replace V005 lines 72-74** ("Multi-recipe note (minimal — Phase 22 will expand)"):
```markdown
## Multi-recipe extraction

If the user lists multiple recipes in one Spanish message, emit ONE
`start-workflow(workflow_type="add-recipe", input={"value": "<recipe>"})` per
recipe. Order them as the user said them. Up to FIVE recipes per turn.

### Worked example — N=3 happy path
[per CONTEXT D-09; RESEARCH §"V005 → V006 fork"]

### Recipe-boundary rules (anti-patterns)
- Sauce-on-recipe ("canelones con salsa blanca y boloñesa") → 1 workflow (D-12)
- Compound dish ("pollo al horno con papas") → 1 workflow, prefer FEWER (D-11)
- English noun-phrases ("salt and pepper chicken") → 1 workflow
- Ambiguity → respond(clarify) + terminate, NO start-workflow (D-10)

## Over-cap (more than 5 recipes)
If the user names MORE than 5 recipes, do NOT start any workflows. Call
respond(text="Son muchas recetas a la vez. ¿Probamos de a cinco?...") then
terminate(). (D-01, BATCH-05)
```

**Wake-context worked examples — replace V005 lines 95-115** with D-09's expanded set:
single-success / multi-success / partial-failure (BATCH-04) / all-failure, all in Spanish, preserving preamble order.

**Preserve from V005 unchanged:** Role, Inputs, Tools, Strict Output Rule, Process, language rule, forbidden behaviors.

---

### `src/robotina/agent/agents.py` (config, in-place modify)

**Analog:** same file, current line 84.

**Current** (line 84):
```python
prompt_path="src/robotina/agent/prompts/robotina/V005.md",
```

**Target** (1-line edit; mirror Phase 21 D-10):
```python
prompt_path="src/robotina/agent/prompts/robotina/V006.md",
```

No other change in this file.

---

### `src/robotina/queue/task_types.py` — `WorkflowOutcomeSummary` field add (model, transform)

**Analog:** `AddRecipeOutcome` at `task_types.py:322-339` (sibling Pydantic model with optional fields and `extra="forbid"`).

**Pattern — optional field with default `None`** (from `AddRecipeOutcome:336-339`):
```python
class AddRecipeOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["success", "failure"]
    recipe_id: str | None = None        # success only
    recipe_name: str | None = None      # success only
    recipe_slug: str | None = None      # success only
    failure_reason: str | None = None   # failure only
```

**Apply to `WorkflowOutcomeSummary` at lines 355-361** — add after `outcome`:
```python
class WorkflowOutcomeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_run_id: str
    workflow_type: str
    status: Literal["done", "failed"]
    outcome: AddRecipeOutcome | None = None
    recipe_query: str | None = None     # D-08: surfaced from WorkflowRun.shared_context["recipe_query"]
```

---

### `src/robotina/queue/task_types.py` — `to_user_message()` rewrite (model method, transform)

**Analog:** in-place rewrite of `task_types.py:379-395` (current impl).

**Current behavior to remove:**
- Trailing `lines.append("(Wake-trigger; el usuario ya fue notificado.)")` (line 394) — Phase 21 removed `notify`; this parenthetical mis-trains the LLM.
- Failure-line fallback to "(receta sin nombre)" without using `recipe_query`.

**Target pattern** (per RESEARCH §"`to_user_message()` rewrite (D-07)"):
```python
def to_user_message(self) -> str:
    lines = ["Los siguientes flujos terminaron:"]
    for o in self.outcomes:
        if o.status == "done" and o.outcome is not None and o.outcome.status == "success":
            name = o.outcome.recipe_name or o.recipe_query or "(receta sin nombre)"
            slug = o.outcome.recipe_slug  # BATCH-03 name+slug
            if slug:
                lines.append(f"- ✓ {o.workflow_type}: {name} (slug: {slug}, run {o.workflow_run_id})")
            else:
                lines.append(f"- ✓ {o.workflow_type}: {name} (run {o.workflow_run_id})")
        elif o.status == "done":
            lines.append(f"- ✓ {o.workflow_type} terminó (run {o.workflow_run_id})")
        else:
            query = o.recipe_query or "(receta sin nombre)"  # BATCH-04 readable failures
            reason = (o.outcome.failure_reason if o.outcome else None) or "(sin detalle)"
            lines.append(f"- ✗ {o.workflow_type}: {query} falló: {reason} (run {o.workflow_run_id})")
    lines.append("(Wake-trigger; el usuario espera el resumen final.)")
    return "\n".join(lines)
```

**Verify before locking:** `AddRecipeOutcome.recipe_slug` field name (assumption A1) — confirmed in `task_types.py:338` (`recipe_slug: str | None = None`).

---

### `src/robotina/queue/workflow_runner.py` — `_check_and_dispatch_wake` (service, event-driven)

**Analog:** in-place modify of `workflow_runner.py:195-253` (current impl).

**Imports already present** (lines 181-193): `WorkflowRun`, `WorkflowStatus`, `WorkflowOutcomeSummary`, etc. No new imports needed.

**Change 1 (D-06) — sibling-runs query at lines 195-199:**
```python
sibling_runs = (
    session.query(WorkflowRun)
    .filter(WorkflowRun.triggered_by_invocation_id == invocation_id)
    .order_by(WorkflowRun.created_at.asc())  # D-06: best-available proxy for user-utterance order
    .all()
)
```

**Change 2 (D-08) — outcome summary build at lines 246-253:**
```python
outcomes.append(
    WorkflowOutcomeSummary(
        workflow_run_id=r.id,
        workflow_type=r.workflow_type,
        status="done" if r.status == WorkflowStatus.DONE else "failed",
        outcome=run_outcome,
        recipe_query=(r.shared_context or {}).get("recipe_query"),  # D-08
    )
)
```

**Pitfall 6 fallback:** `(r.shared_context or {}).get("recipe_query")` returns `None` if `shared_context` is null OR if `recipe_query` key missing. `WorkflowOutcomeSummary.recipe_query` is Optional; downstream `to_user_message()` falls back to "(receta sin nombre)".

---

### `experiments/robotina/multi_recipe_eval.py` (experiment harness, batch)

**Analog:** `experiments/recipe_research.py` (full file — exhaustive boilerplate match).

**Imports/setup pattern** (recipe_research.py:20-35):
```python
from __future__ import annotations
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
import langwatch
import langwatch.langchain
from langchain_core.runnables import RunnableConfig
from langwatch.client import Client as LangWatchClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
```

**Agent build pattern** (recipe_research.py:75-100):
```python
def build_agent(task_type: str = "handle-incoming-message", backend_name: str = "ollama"):
    from robotina.agent.agents import get_agent_config
    from robotina.agent.tools.read_skill import SkillSet, build_read_skill_tool
    from robotina.llm import make_backend

    config = get_agent_config(task_type)
    backend = make_backend(config.model_config)

    skill_sets = [SkillSet(s) for s in config.skills]
    skill_index = "\n\n".join(ss.index_content for ss in skill_sets)
    tools = list(config.tools)
    if skill_sets:
        tools.append(build_read_skill_tool(skill_sets))

    # Phase 22: inject STUB Respond / StartWorkflow / Terminate tools that
    # record calls but do NOT enqueue real workflows. Counting tool calls
    # = our acceptance metric (Pitfall 12 → eval).

    prompt_text = Path(config.prompt_path).read_text()
    if skill_index:
        prompt_text = prompt_text + "\n\n" + skill_index

    agent = backend.create_agent(system_prompt=prompt_text, tools=tools)
    return agent, config
```

**LangWatch tracer pattern (per-utterance metadata)** (recipe_research.py:236-255):
```python
tracer = langwatch.langchain.LangChainTracer(
    metadata={
        "experiment": "multi-recipe-eval",
        "phase": "22",
        "prompt_version": "V006",
        "utterance_id": idx,
        "model": config.model_config.get("model"),
        "provider": config.model_config.get("provider"),
        "backend": backend_name,
    }
)
with tracer:
    result = agent.invoke(
        {"messages": [{"role": "user", "content": utterance]}]},
        config=RunnableConfig(callbacks=[tracer]),
    )
    # count tool calls in result["messages"] (see below)
```

**Tool-call counting pattern** (analog: `extract_json_output` in recipe_research.py:103-148 walks `result["messages"]`):
```python
def count_start_workflow_calls(result: dict) -> tuple[int, list[str]]:
    """Walk AIMessage.tool_calls for name == 'start-workflow'; return count + recipe values."""
    count = 0
    recipe_values: list[str] = []
    for msg in result.get("messages", []):
        tcs = getattr(msg, "tool_calls", None) or []
        for tc in tcs:
            if tc.get("name") == "start-workflow":
                count += 1
                args = tc.get("args") or {}
                val = (args.get("input") or {}).get("value")
                if val:
                    recipe_values.append(val)
    return count, recipe_values
```

**Trace flush pattern** (recipe_research.py:306-307 — required for spans to ship):
```python
if LangWatchClient._tracer_provider is not None:
    LangWatchClient._tracer_provider.force_flush()
```

**Error handling pattern** (recipe_research.py:276-287):
```python
try:
    result = agent.invoke(...)
    # ... record success
except Exception as e:
    logger.exception("Utterance %s failed: %s", idx, e)
    with tracer.trace.span(type="evaluation", name=f"utterance-{idx}") as eval_span:
        eval_span.update(passed=False, details=str(e))
    # record error row; continue to next utterance (do NOT break — single-utterance failure ≠ batch failure)
```

**CLI / main pattern** (recipe_research.py:212-318): `main()` prints header, loops cases, prints SUMMARY, flushes traces, `raise SystemExit(1)` if errors. Phase 22 adds `argparse` for `--backend {ollama,openai,anthropic}`.

**Markdown report emit pattern (new for Phase 22):** write `22-EVAL-RESULTS-<backend>.md` with the same table shape as `21-SMOKE.md` (see Shared Patterns below).

---

### `experiments/robotina/__init__.py` (package marker)

Empty file. Mirrors `experiments/__init__.py` (verify exists at plan time; if not, add it too).

---

### `pyproject.toml` `[project.scripts]` (config)

**Analog:** lines 46-47 (existing experiment scripts).

**Pattern:**
```toml
"experiments.recipe_research" = "experiments.recipe_research:main"
"experiments.recipe_load" = "experiments.recipe_load:main"
"experiments.multi_recipe_eval" = "experiments.robotina.multi_recipe_eval:main"   # Phase 22
```

Operator invokes: `uv run experiments.multi_recipe_eval --backend openai`.

---

### `tests/queue/test_wake_helper_ordering.py` (test, event-driven) — NEW

**Analog:** `tests/queue/test_wake_dispatch.py` (full file — exhaustive match).

**Imports + fixture pattern** (test_wake_dispatch.py:1-52):
```python
import pytest
from sqlalchemy import text
from robotina.gateway.models import Conversation
from robotina.queue.workflow_runner import _check_and_dispatch_wake
from robotina.queue.models import (
    InvocationStatus, InvocationTrigger, RobotinaInvocation,
    WorkflowRun, WorkflowStatus,
)

@pytest.fixture(autouse=True)
def _cleanup_workflow_tables(db_session):
    db_session.execute(text("DELETE FROM workflow_run_steps"))
    db_session.execute(text("DELETE FROM workflow_runs"))
    db_session.commit()
    yield
    db_session.execute(text("DELETE FROM workflow_run_steps"))
    db_session.execute(text("DELETE FROM workflow_runs"))
    db_session.commit()
```

**FakeQueue + helper pattern** (test_wake_dispatch.py:59-108): `FakeQueue` records `enqueue()` args; `_make_conversation`, `_make_parent_invocation`, `_make_run` factories. **Reuse verbatim** in the new test file (or import from `test_wake_dispatch` via a shared `conftest` — planner picks).

**ORDER BY assertion pattern (new):**
```python
def test_wake_helper_orders_outcomes_by_created_at_asc(db_session):
    """D-06: sibling runs surface in created_at ASC order in WakeInvocationInput.outcomes."""
    from datetime import datetime, timezone, timedelta
    session = db_session
    conv = _make_conversation(session)
    parent = _make_parent_invocation(session, conv.id)

    # Insert 3 runs with explicit created_at >= 1ms apart (Pitfall 1 — avoid clock-tie flakes)
    base = datetime.now(timezone.utc)
    runs = []
    for i, name in enumerate(["canelones", "pollo", "arroz"]):
        r = _make_run(
            session, conv_id=conv.id, parent_inv_id=parent.id,
            status=WorkflowStatus.DONE,
            outcome={"status": "success", "recipe_name": name.capitalize(), "recipe_slug": name},
        )
        # Force created_at; SQLAlchemy server_default may have set it
        r.created_at = base + timedelta(milliseconds=i * 10)
        r.shared_context = {"recipe_query": name}
        runs.append(r)
    session.flush()

    fake_queue = FakeQueue()
    _check_and_dispatch_wake(parent.id, session, fake_queue)
    session.commit()

    args, _ = fake_queue.enqueued[0]
    wake_input = args[1]
    observed = [o.outcome.recipe_name for o in wake_input.outcomes]
    assert observed == ["Canelones", "Pollo", "Arroz"]

    # recipe_query populated (D-08)
    observed_queries = [o.recipe_query for o in wake_input.outcomes]
    assert observed_queries == ["canelones", "pollo", "arroz"]
```

---

### `tests/queue/test_wake_invocation_input.py` or extend `test_task_types_wake_models.py` (test, transform)

**Analog:** `tests/queue/test_task_types_wake_models.py` (existing file — extend in place per RESEARCH §Wave 0 Gaps).

**Pattern from existing tests** (test_task_types_wake_models.py:72-101):
```python
def _make_wake_with(status, outcome, recipe_query=None):
    return WakeInvocationInput(
        previous_invocation_id="inv-1",
        conversation_id="conv-1",
        outcomes=[
            WorkflowOutcomeSummary(
                workflow_run_id="run-1",
                workflow_type="add-recipe",
                status=status,
                outcome=outcome,
                recipe_query=recipe_query,
            )
        ],
    )
```

**New test assertions to add (D-07 / D-08):**
```python
def test_to_user_message_success_includes_slug():
    w = _make_wake_with("done",
        AddRecipeOutcome(status="success", recipe_name="Lentejas", recipe_slug="lentejas"),
        recipe_query="lentejas")
    msg = w.to_user_message()
    assert "slug: lentejas" in msg
    assert "Lentejas" in msg

def test_to_user_message_failure_uses_recipe_query():
    w = _make_wake_with("failed",
        AddRecipeOutcome(status="failure", failure_reason="no encontré la receta"),
        recipe_query="canelones")
    msg = w.to_user_message()
    assert "canelones falló" in msg
    assert "no encontré la receta" in msg
    assert "(receta sin nombre)" not in msg

def test_to_user_message_drops_legacy_parenthetical():
    w = _make_wake_with("done",
        AddRecipeOutcome(status="success", recipe_name="X", recipe_slug="x"))
    msg = w.to_user_message()
    assert "usuario ya fue notificado" not in msg
    assert "espera el resumen final" in msg  # D-07 replacement

def test_workflow_outcome_summary_accepts_recipe_query_none_and_str():
    WorkflowOutcomeSummary(workflow_run_id="r", workflow_type="add-recipe",
                           status="failed", recipe_query=None)
    WorkflowOutcomeSummary(workflow_run_id="r", workflow_type="add-recipe",
                           status="failed", recipe_query="canelones")
```

**Update existing test:** `test_wake_invocation_input_to_user_message_success` (line 72) currently asserts `"Wake-trigger" in msg` — replace with `"espera el resumen final" in msg` since the legacy parenthetical is removed.

---

### `tests/agents/test_agent_registry.py` (test, config-assert) — MODIFY

**Analog:** in-place edit of existing assertion at lines 19-24.

**Current** (lines 19-24):
```python
def test_handle_incoming_message_uses_v005():
    """Per D-10: handle-incoming-message bumped from V004.md to V005.md."""
    cfg = AGENT_REGISTRY["handle-incoming-message"]
    assert cfg.prompt_path.endswith("V005.md"), (
        f"handle-incoming-message prompt_path is {cfg.prompt_path!r}, expected to end with V005.md"
    )
```

**Target** (rename + bump):
```python
def test_handle_incoming_message_uses_v006():
    """Per Phase 22: handle-incoming-message bumped from V005.md to V006.md."""
    cfg = AGENT_REGISTRY["handle-incoming-message"]
    assert cfg.prompt_path.endswith("V006.md"), (
        f"handle-incoming-message prompt_path is {cfg.prompt_path!r}, expected to end with V006.md"
    )
```

---

### `22-EVAL-SET.md`, `22-EVAL-RESULTS-<backend>.md`, `22-SMOKE.md` (spec/results docs)

**Analog:** `.planning/phases/21-tool-surface-flip-remove-acknowledge-notify/21-SMOKE.md`.

**Frontmatter pattern** (21-SMOKE.md:1-5):
```markdown
---
verdict: pending
date: <YYYY-MM-DD — operator fills>
operator: <name — operator fills>
---
```

**Utterance-set table pattern** (21-SMOKE.md:17-27):
```markdown
| # | Utterance (Spanish) | Coverage | Expected N | Observed N | Recipe names observed | OK? | LangWatch trace |
|---|---------------------|----------|------------|------------|----------------------|-----|------------------|
| 1 | agregá lentejas | single-recipe | 1 | | | | |
```

**22-EVAL-SET.md** uses this table with ≥ 30 rows across the 10 coverage classes (D-03). Tool-call hygiene checklist + operator runbook + verdict section follow the 21-SMOKE.md structure.

**22-EVAL-RESULTS-<backend>.md** = filled-in table per backend; aggregate counts; go/no-go line.

**22-SMOKE.md** = final operator verdict referencing the two EVAL-RESULTS files.

---

## Shared Patterns

### Pydantic `extra="forbid"` for all wake-path models
**Source:** `src/robotina/queue/task_types.py:333, 356, 373`
**Apply to:** `WorkflowOutcomeSummary` (any field addition keeps this guard active — verified by `test_workflow_outcome_summary_rejects_extra` at `test_task_types_wake_models.py:47-54`).

### LangWatch tracer with per-call metadata
**Source:** `experiments/recipe_research.py:236-255` and `experiments/recipe_load.py:232-242`
**Apply to:** `experiments/robotina/multi_recipe_eval.py` — every utterance gets a tracer with `experiment`, `phase`, `prompt_version`, `utterance_id`, `model`, `provider`, `backend` keys. Mandatory per CLAUDE.md observability constraint.

### `dotenv` + lazy intra-function imports
**Source:** `experiments/recipe_research.py:26-27` (`load_dotenv()` at module top before `langwatch` import) and inside `build_agent()` (deferred `from robotina.X import Y` to keep import cycles shallow).
**Apply to:** eval harness.

### `db_session` fixture + workflow_runs cleanup
**Source:** `tests/queue/test_wake_dispatch.py:36-51` (autouse fixture deleting workflow_run_steps then workflow_runs).
**Apply to:** `test_wake_helper_ordering.py` (real-Postgres integration — required because `_check_and_dispatch_wake` uses raw SQL UPDATE-RETURNING that won't run on mock sessions, per test_wake_dispatch.py:1-10 docstring).

### `FakeQueue` test double
**Source:** `tests/queue/test_wake_dispatch.py:59-66`
```python
class FakeQueue:
    name = "agent-tasks"
    def __init__(self):
        self.enqueued: list[tuple[tuple, dict]] = []
    def enqueue(self, *args, **kwargs):
        self.enqueued.append((args, kwargs))
```
**Apply to:** any new wake-helper test. Inspect `args[1]` (the `WakeInvocationInput`) to verify outcome ordering and `recipe_query` plumbing.

### Operator-driven smoke template (frontmatter + table + runbook + verdict)
**Source:** `.planning/phases/21-.../21-SMOKE.md`
**Apply to:** all three new doc files (`22-EVAL-SET.md`, `22-EVAL-RESULTS-<backend>.md`, `22-SMOKE.md`).

### Prompt fork convention (keep prior version unchanged for rollback)
**Source:** `src/robotina/agent/prompts/robotina/V001..V005.md` (all retained; only the agent-registry pointer changes).
**Apply to:** V006.md — V005.md stays untouched per D-16.

### Spanish user-text, English prompt body
**Source:** V005.md:117-138 (Rules + Language rule sections).
**Apply to:** V006.md — body in English; `respond()` example payloads in Argentine/LatAm Spanish.

---

## No Analog Found

None. Every Phase 22 file has a close analog in the codebase (this phase is intentionally a small thin tail on top of mature Phase 18/20/21 contracts).

---

## Metadata

**Analog search scope:**
- `src/robotina/agent/prompts/robotina/` (V001-V005 prompts)
- `src/robotina/queue/` (task_types.py, workflow_runner.py, models.py)
- `src/robotina/agent/` (agents.py)
- `experiments/` (recipe_research.py, recipe_load.py)
- `tests/queue/` (test_wake_dispatch.py, test_task_types_wake_models.py)
- `tests/agents/` (test_agent_registry.py)
- `.planning/phases/21-.../` (21-SMOKE.md as doc template)
- `pyproject.toml` ([project.scripts])

**Files scanned:** ~12 source + ~6 test + 2 docs + 1 toml.

**Pattern extraction date:** 2026-05-20
