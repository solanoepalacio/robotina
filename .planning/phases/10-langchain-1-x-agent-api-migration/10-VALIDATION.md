---
phase: 10
slug: langchain-1-x-agent-api-migration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Lifted from `10-RESEARCH.md` → `## Validation Architecture`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio 1.x (verified via `pyproject.toml [dependency-groups].dev`) |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `asyncio_mode = "auto"`, marker `integration` |
| **Quick run command** | `uv run pytest tests/unit/test_llm_backend.py tests/unit/test_queue_tool.py tests/unit/test_start_workflow_tool.py tests/unit/test_household_manager_api_tool.py -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | Quick: ~1s · Full: ~3–5s |

---

## Sampling Rate

- **After every task commit:** Run the quick run command (the four migration-target test files).
- **After every plan wave:** Run the full suite command.
- **Before `/gsd-verify-work`:** Full suite must be green AND end-to-end add-recipe manual run (success criterion 4) must complete without regression.
- **Max feedback latency:** ≤ 5 seconds (quick run target ≤ 1s).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD-01 | TBD | 1 | AGENT-12 | — | N/A | unit (source-grep) | `uv run pytest tests/unit/test_llm_backend.py::test_create_agent_used_not_agent_executor -x` | ✅ rename needed | ⬜ pending |
| TBD-02 | TBD | 1 | AGENT-12 | — | N/A | unit | `uv run pytest tests/unit/test_llm_backend.py::test_ollama_adapter_creates_agent -x` | ✅ patch-target rename | ⬜ pending |
| TBD-03 | TBD | 1 | AGENT-12 | — | N/A | unit | `uv run pytest tests/unit/test_llm_backend.py::test_anthropic_adapter_creates_agent -x` | ✅ patch-target rename | ⬜ pending |
| TBD-04 | TBD | 1 | AGENT-12 | — | N/A | unit | `uv run pytest tests/unit/test_llm_backend.py::test_openai_adapter_creates_agent -x` | ✅ patch-target rename | ⬜ pending |
| TBD-05 | TBD | 1 | AGENT-12 (parity) | — | N/A | unit | `uv run pytest tests/unit/test_queue_tool.py::test_queue_tool_short_circuits_create_agent -x` | ✅ rename + import swap | ⬜ pending |
| TBD-06 | TBD | 1 | AGENT-12 (parity) | — | N/A | unit | `uv run pytest tests/unit/test_start_workflow_tool.py::test_start_workflow_tool_short_circuits_create_agent -x` | ✅ rename + import swap | ⬜ pending |
| TBD-07 | TBD | 1 | AGENT-12 (parity) | — | N/A | unit | `uv run pytest tests/unit/test_household_manager_api_tool.py::test_extra_field_in_agent_loop_yields_tool_error_message -x` | ✅ import swap only | ⬜ pending |
| TBD-08 | TBD | 2 | AGENT-12 (consumer-side parity) | — | N/A | unit | `uv run pytest tests/test_workflow_runner.py -q` | ✅ existing — unchanged | ⬜ pending |
| TBD-09 | TBD | 2 | AGENT-12 (end-to-end) | — | N/A | manual | Telegram → "add a recipe for X" → confirm research→load→notify completes | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

> Task IDs are placeholders (TBD-NN) until the planner assigns them. The planner's tasks MUST reference these `pytest` commands verbatim in `<acceptance_criteria>` blocks so this map can be filled in.

---

## Wave 0 Requirements

- [x] `tests/unit/test_llm_backend.py` — already exists, requires patch-target renames (`create_react_agent` → `create_agent`) and one test rename
- [x] `tests/unit/test_queue_tool.py` — already exists, requires test rename + import swap
- [x] `tests/unit/test_start_workflow_tool.py` — already exists, requires test rename + import swap
- [x] `tests/unit/test_household_manager_api_tool.py` — already exists, requires import swap only
- [x] `tests/test_workflow_runner.py` — already exists, should pass unchanged

*Wave 0 verdict: no new test infrastructure required. The single "rename" sub-task captured in the research is cosmetic and can be folded into the swap commits.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end add-recipe (research → load → notify) on real recipe query | AGENT-12 (success criterion 4) | Requires real Telegram + real LLM + real household-manager API; no deterministic automated path | 1. `docker compose up postgres redis` 2. `uv run agent` 3. Send "agrega receta de tortilla de papa" via Telegram 4. Confirm: research agent runs, load agent runs, notify confirmation arrives back in Telegram |
| LangWatch trace lands in correct experiment collection | Spec constraint (CLAUDE.md "LangWatch instrumentation must be active during both production and experiment runs") | Trace ingestion is an external SaaS observation, not in-process | After the end-to-end run, confirm in LangWatch UI that the new trace appears under the configured project / experiment tag |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (none — all targets exist)
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner fills in real task IDs)

**Approval:** pending
