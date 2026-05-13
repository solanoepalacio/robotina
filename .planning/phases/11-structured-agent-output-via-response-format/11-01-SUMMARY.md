---
phase: 11
plan: 01
subsystem: llm-adapter-and-agent-registry
tags:
  - structured-output
  - response_format
  - langchain-1.x
  - llm-adapter
  - agent-config
  - tdd
dependency_graph:
  requires:
    - "langchain.agents.create_agent  # established in Phase 10"
    - "langchain.agents.structured_output.{ToolStrategy,ProviderStrategy}"
    - "pydantic v2 BaseModel"
  provides:
    - "LLMBackend.create_agent(response_format=...)  # protocol-level kwarg"
    - "AgentConfig.response_format_model field  # registry-level schema binding"
    - "RRECIPE-07, RLOAD-07, WF-10  # Phase 11 requirement IDs registered"
  affects:
    - "src/robotina/queue/jobs.py  # threading the kwarg — Plan 11-03"
    - "src/robotina/queue/workflow_runner.py  # structured_response extraction — Plan 11-02"
tech_stack:
  added: []
  patterns:
    - "Per-provider Strategy wrapping inside LLMBackend.create_agent (correctness-required for Ollama gpt-oss)"
    - "Non-overridable dataclass field enforced by omission in get_agent_config"
key_files:
  created:
    - "tests/test_llm_backend.py"
    - "tests/test_agents.py"
    - ".planning/phases/11-structured-agent-output-via-response-format/deferred-items.md"
  modified:
    - "src/robotina/llm/__init__.py"
    - "src/robotina/agent/agents.py"
    - ".planning/REQUIREMENTS.md"
decisions:
  - "Ollama → ToolStrategy explicit wrap (mandatory): gpt-oss matches FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT so AutoStrategy would resolve to ProviderStrategy and silently break."
  - "Anthropic/OpenAI → ProviderStrategy: both report structured_output=True in model profile."
  - "response_format_model is NOT in the overridable field set; schema is a code contract, not config."
  - "WF-10 chosen over WF-08 (taken: workflow failure handling) / WF-09 (taken: reply_context); next free slot in the WF-* family."
metrics:
  duration_minutes: 5
  completed_at: "2026-05-13T18:15:33Z"
---

# Phase 11 Plan 01: LLMBackend response_format kwarg + AgentConfig.response_format_model Summary

Established the contract surface for Phase 11 — extended `LLMBackend.create_agent()` (Protocol + all 3 adapters) with an optional `response_format` kwarg that wraps the Pydantic schema in the provider-correct Strategy, added a non-overridable `response_format_model` field to `AgentConfig`, and registered three new requirement IDs (RRECIPE-07, RLOAD-07, WF-10) in REQUIREMENTS.md so Plans 11-02 and 11-03 can run in parallel against a stable contract.

## What Was Built

**One-liner:** Adapter-level structured-output Strategy dispatch (Tool for Ollama, Provider for Anthropic/OpenAI) plumbed through `LLMBackend.create_agent` and `AgentConfig.response_format_model`, with the Ollama-specific FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT trap explicitly mitigated.

### Files

**Created:**
- `tests/test_llm_backend.py` — 5 unit tests covering the Protocol signature, Ollama omit/wrap behavior, and Anthropic/OpenAI ProviderStrategy wrapping.
- `tests/test_agents.py` — 4 unit tests covering the new dataclass field default, BaseModel subclass acceptance, override silently-dropped semantics, and override regression guard.
- `.planning/phases/11-structured-agent-output-via-response-format/deferred-items.md` — documents pre-existing test-pollution failures in `tests/unit/test_agents_registry.py` not introduced by this plan (out-of-scope per scope boundary).

**Modified:**
- `src/robotina/llm/__init__.py` — Protocol signature + 3 adapter `create_agent` methods now accept `response_format: type[BaseModel] | None = None`; Ollama wraps in `ToolStrategy`, Anthropic/OpenAI wrap in `ProviderStrategy`. Added `from pydantic import BaseModel` import.
- `src/robotina/agent/agents.py` — `AgentConfig` gains `response_format_model: type[BaseModel] | None = None`. `get_agent_config` docstring updated to enumerate non-overridable fields. No behavioral change to `get_agent_config` body — non-overridability is enforced by omission.
- `.planning/REQUIREMENTS.md` — added RRECIPE-07, RLOAD-07, WF-10 (all `In Progress`, to flip Complete in Plan 11-04 after manual end-to-end checkpoint); coverage block recomputed to 72 (was 69).

## Tasks

| Task | Name                                                                            | Commit  | Files                                                        |
| ---- | ------------------------------------------------------------------------------- | ------- | ------------------------------------------------------------ |
| 1.1  | Add RRECIPE-07, RLOAD-07, WF-10 to REQUIREMENTS.md with traceability            | 05bc195 | .planning/REQUIREMENTS.md                                    |
| 1.2 R | RED: failing adapter Strategy-wrap tests                                       | e540e60 | tests/test_llm_backend.py                                    |
| 1.2 G | GREEN: extend LLMBackend with response_format kwarg + Strategy wrap            | 8ae6c44 | src/robotina/llm/__init__.py, tests/test_llm_backend.py, deferred-items.md |
| 1.3 R | RED: failing AgentConfig.response_format_model tests                           | 1d11a9d | tests/test_agents.py                                         |
| 1.3 G | GREEN: add AgentConfig.response_format_model (non-overridable)                 | 5f23573 | src/robotina/agent/agents.py                                 |

Total: 5 commits across 3 tasks (Tasks 1.2 and 1.3 follow the TDD RED → GREEN gate sequence).

## Requirements Covered

- **RRECIPE-07** (Phase 11, In Progress) — recipe-research sub-agents bind `response_format=` on `create_agent`; structured_response is the artifact source. Contract surface (Protocol + adapter wrapping) ready in this plan; per-agent binding happens in Plan 11-03.
- **RLOAD-07** (Phase 11, In Progress) — `recipe-load` binds `response_format=RecipeLoadOutput`. Same contract status as above.
- **WF-10** (Phase 11, In Progress) — `_extract_task_output` reads `structured_response`; fail-loud on missing for structured agents. Foundation laid; behavior change happens in Plan 11-02.

All three flip to `[x]` / `Complete` in Plan 11-04 after the manual end-to-end checkpoint.

## Verification

```bash
$ uv run pytest tests/test_llm_backend.py tests/test_agents.py -x
============================== 9 passed in 0.57s ===============================
```

| Acceptance Criterion | Result |
| --- | --- |
| `uv run pytest tests/test_llm_backend.py tests/test_agents.py -x` exits 0 | PASS (9 passed) |
| `grep -c "RRECIPE-07\|RLOAD-07\|WF-10" .planning/REQUIREMENTS.md` >= 6 | PASS (7 matches: 3 definitions + 3 traceability rows + 1 in the Last-updated footer) |
| 4 `response_format: type[BaseModel] | None = None` signatures in `src/robotina/llm/__init__.py` (Protocol + 3 adapters) | PASS (grep -c → 4) |
| `LLMBackend.create_agent` signature includes `response_format` | PASS (verified via `inspect.signature`) |
| Plans 11-02 and 11-03 can both proceed in parallel against this contract | PASS — contract is stable, fully tested, and committed |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ToolStrategy attribute name correction**
- **Found during:** Task 1.2 GREEN run.
- **Issue:** The plan instructed asserting `response_format.schema_spec.schema is ToyModel`. The installed `langchain 1.2.13` actually exposes `ToolStrategy.schema_specs` (plural list of `_SchemaSpec`), not `schema_spec`. Only `ProviderStrategy` uses the singular `schema_spec`. Plan author was working from a partial reading; the verified surface in `.venv/lib/python3.12/site-packages/langchain/agents/structured_output.py` shows the asymmetry.
- **Fix:** Updated `tests/test_llm_backend.py` to assert against the actual surface — both via the public `.schema` attribute that both strategies expose, and the strategy-specific `.schema_specs[0].schema` (Tool) / `.schema_spec.schema` (Provider) accessors.
- **Files modified:** `tests/test_llm_backend.py`
- **Commit:** 8ae6c44

### Out-of-scope discoveries (logged, NOT fixed)

**Pre-existing test pollution in `tests/unit/test_agents_registry.py`** — A test (in the same module or in a sibling) sets `AGENT_OVERRIDES_FILEPATH` to `overrides/openai.json` and does not restore it in teardown, so subsequent registry tests see the openai override values instead of the registry defaults. Reproduced via `git stash` to confirm the failures pre-exist Plan 11-01 (13 failures without my changes; 9 failures with — the count drop is incidental, no Phase 11 changes touch the affected tests). Logged in `.planning/phases/11-structured-agent-output-via-response-format/deferred-items.md`. Belongs in a separate maintenance quick-task.

**DB-dependent unit tests skipped during verification** — `tests/test_db_models.py`, `tests/test_gateway.py`, `tests/test_workflow_runner.py`, `tests/test_workflows.py`, `tests/test_jobs.py` all require Postgres + Redis running locally. Worktree environment does not have docker-compose running. These tests do not exercise the LLM adapter or AgentConfig surface that this plan changes; skipped is safe. Logged in the same deferred-items file.

## TDD Gate Compliance

Both Tasks 1.2 and 1.3 followed the RED → GREEN gate sequence:

| Task | RED commit | GREEN commit | Gate sequence intact? |
| --- | --- | --- | --- |
| 1.2 | e540e60 (`test(11-01):` — 5 tests, all failing) | 8ae6c44 (`feat(11-01):` — Protocol + adapter wraps) | YES |
| 1.3 | 1d11a9d (`test(11-01):` — 4 tests, all failing) | 5f23573 (`feat(11-01):` — dataclass field) | YES |

No REFACTOR commits were needed — both implementations were minimal and passed the tests as written.

## Notes for Plan 11-02 and Plan 11-03

These plans run in parallel after this one merges:

- **Plan 11-02** (workflow runner): now safely consumes `AgentConfig.response_format_model is not None` to decide `expects_structured` inside `on_step_complete`. The decision boundary is on a Pydantic class identity, not a JSON-parseable string — no schema serialization round-trip needed.
- **Plan 11-03** (jobs + registry binding): can populate `response_format_model` on the 5 named agents in `AGENT_REGISTRY` and pass `response_format=config.response_format_model` through `backend.create_agent(...)` in `run_task`. The kwarg dispatch (Ollama vs Anthropic/OpenAI) happens inside the adapter — `run_task` stays provider-agnostic.

The contract is byte-stable: the kwarg name, default, and type annotation all match across the Protocol and the 3 adapters; future LLM backends added by following the existing pattern in `src/robotina/llm/__init__.py` will automatically pick up the right shape.

## Self-Check: PASSED

Verified files exist:
- `tests/test_llm_backend.py` FOUND
- `tests/test_agents.py` FOUND
- `.planning/phases/11-structured-agent-output-via-response-format/deferred-items.md` FOUND

Verified commits exist (`git log --oneline`):
- 05bc195 FOUND (Task 1.1)
- e540e60 FOUND (Task 1.2 RED)
- 8ae6c44 FOUND (Task 1.2 GREEN)
- 1d11a9d FOUND (Task 1.3 RED)
- 5f23573 FOUND (Task 1.3 GREEN)
