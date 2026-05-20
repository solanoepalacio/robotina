---
phase: 23-url-ingestion-topic-2
plan: 04
subsystem: agent
tags: [agent, prompt, registry, overrides, url-ingestion]
dependency_graph:
  requires:
    - 23-02  # AddRecipeUrlInput / GatherFromUrlInput + workflow registry
    - 23-03  # FetchAndScrapeTool
  provides:
    - "gather-from-url" agent
    - V001 prompt for gather-from-url
  affects:
    - src/robotina/agent/agents.py
    - src/robotina/queue/jobs.py
    - overrides/*.json
tech_stack:
  added: []
  patterns:
    - "AGENT_REGISTRY + overrides/*.json atomic sync (Phase 21 D-12, feedback_overrides_in_sync)"
    - "Per-job tool injection in run_task() elif chain (mirrors recipe-research-gather → WebSearchTool)"
    - "Stubbed BaseChatModel via langchain_core FakeMessagesListChatModel for agent integration tests"
    - "ToolStrategy(<Pydantic>) on create_agent — schema bound as synthetic tool named after class"
key_files:
  created:
    - src/robotina/agent/prompts/gather-from-url/V001.md
    - tests/agents/test_gather_from_url_agent.py
  modified:
    - src/robotina/agent/agents.py
    - src/robotina/queue/jobs.py
    - overrides/anthropic.json
    - overrides/openai.json
    - overrides/staging.ollama.json
    - .env.example
decisions:
  - "V001 prompt body in English, ≤30-line process section, instructs single fetch-and-scrape call with pass-through-or-extract branch logic"
  - "AGENT_REGISTRY entry mirrors recipe-research-gather shape (ollama default, gpt-oss:20b, reasoning=True), response_format_model=RecipeData"
  - "FetchAndScrapeTool injection lives in run_task() elif chain, lazy import per Phase 4 convention"
  - "Stub-LLM tests load the real V001 prompt from disk (URL-04 mandates real prompt drives the test)"
  - "ToolStrategy(RecipeData) used in tests — matches OllamaBackend.create_agent production path"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-20"
  tasks_completed: 2
  files_changed: 7
---

# Phase 23 Plan 04: gather-from-url agent registration Summary

Registered the `gather-from-url` LLM agent end-to-end — V001 prompt + AGENT_REGISTRY entry + all three `overrides/*.json` files (atomic per `feedback_overrides_in_sync`, Phase 21 D-12 CI guard) + `FetchAndScrapeTool` per-job tool injection in `run_task()` + automated stub-LLM integration tests covering BOTH the scraped_recipe pass-through and URL-04 LLM-fallback (html_text) branches end-to-end through `langchain.agents.create_agent` with `ToolStrategy(RecipeData)`.

## Tasks Completed

### Task 1 — V001 prompt + AGENT_REGISTRY + overrides sync (`f778b0b`)

- `src/robotina/agent/prompts/gather-from-url/V001.md` — English prompt body, ≤30-line process section instructing one `fetch-and-scrape` call, pass-through verbatim when `scraped_recipe` is non-null, LLM-extract from `html_text` otherwise. Explicit "never fabricate" rule + "do not call any tool more than once" cap + minimal-RecipeData fallback for non-recipe pages.
- `src/robotina/agent/agents.py` — new `AGENT_REGISTRY["gather-from-url"]` AgentConfig mirroring `recipe-research-gather` shape (ollama default, gpt-oss:20b, reasoning=True, `response_format_model=RecipeData`, `tools=[]` with FetchAndScrapeTool injected per-job).
- `overrides/anthropic.json` / `overrides/openai.json` / `overrides/staging.ollama.json` — same-commit `gather-from-url` blocks per existing backend conventions (claude-haiku-4-5-20251001 / gpt-4.1-mini / ollama@192.168.68.109). Phase 21 D-12 CI guard (`tests/agents/test_registry_override_sync.py`) passes.
- `.env.example` — adds `GATHER_FROM_URL_API_TOKEN=` near other `*_API_TOKEN=` entries per `feedback_env_example`.

### Task 2 — Tool injection + integration tests (`9ffab25`)

- `src/robotina/queue/jobs.py` — new `elif task_type == "gather-from-url"` branch in `run_task()` injecting `FetchAndScrapeTool()` (no constructor args, mirrors `WebSearchTool` injection). Lazy import per Phase 4 convention.
- `tests/agents/test_gather_from_url_agent.py` — two automated end-to-end tests driving the real `langchain.agents.create_agent` factory with a `FakeMessagesListChatModel` subclass (`bind_tools(self)` no-op, scripted `AIMessage` responses):
  - `test_gather_from_url_passes_through_scraped_recipe` — script: fetch-and-scrape tool_call → `RecipeData` tool_call mirroring the scraped payload. Asserts: tool called exactly once; `structured_response` is a `RecipeData` instance with preserved name / 2 ingredients / 2 steps / source_url.
  - `test_gather_from_url_extracts_from_html_text` — URL-04 LLM-fallback path. Tool returns `scraped_recipe=None` + populated `html_text`; script emits a `RecipeData` tool_call with fields derived from the page text. Asserts: tool called exactly once; structured_response is a `RecipeData` with `name`, ≥2 ingredients, ≥1 step, and `source_url` populated. **No `@pytest.mark.skip`, no grep-only fallback** — URL-04 has a real automated test.
- Both tests use the production V001 prompt loaded from `AGENT_REGISTRY["gather-from-url"].prompt_path` and `ToolStrategy(RecipeData)` — same `response_format` wiring as `OllamaBackend.create_agent` in `src/robotina/llm/__init__.py`.

## Verification

- `uv run pytest tests/agents/ -q` → **24 passed** (the 22 prior agent guard tests + 2 new gather-from-url tests).
- `uv run pytest tests/agents/test_gather_from_url_agent.py -q` → **2 passed**.
- `uv run python -c "from robotina.agent.agents import AGENT_REGISTRY; cfg=AGENT_REGISTRY['gather-from-url']; print(cfg.task_type, cfg.prompt_path, cfg.response_format_model.__name__)"` → `gather-from-url src/robotina/agent/prompts/gather-from-url/V001.md RecipeData`.
- Overrides sync CI guard (`tests/agents/test_registry_override_sync.py`, parametrized over each `overrides/*.json`) — **green for all three backends**.

## Acceptance Criteria

All criteria from PLAN.md `<acceptance_criteria>` blocks satisfied:

| Criterion | Status |
| --- | --- |
| `AGENT_REGISTRY` contains `"gather-from-url"` with `response_format_model=RecipeData` | ✓ |
| `AgentConfig.prompt_path` resolves to `gather-from-url/V001.md` | ✓ |
| All three `overrides/*.json` contain `"gather-from-url"` block (atomic commit `f778b0b`) | ✓ |
| `run_task` injects `FetchAndScrapeTool` for `gather-from-url` | ✓ |
| `tests/agents/test_gather_from_url_agent.py` has ≥2 `def test_` (count = 2) | ✓ |
| `test_gather_from_url_extracts_from_html_text` present (URL-04 fallback covered) | ✓ |
| Stubbed `BaseChatModel` drives both tests (no grep-only fallback) | ✓ |
| No `@pytest.mark.skip` / `pytest.skip(` markers in the test file (count = 0) | ✓ |
| `uv run pytest tests/agents/test_gather_from_url_agent.py -q` exits 0 | ✓ |
| `uv run pytest tests/ -q -k 'overrides_sync or agent_registry'` exits 0 | ✓ |

## Deviations from Plan

None — plan executed exactly as written. The TDD RED/GREEN cycle was elided per the acceptance criteria being grep + import + invariant checks (the existing parametrized `test_overrides_match_registry` IS the structural RED that fires when registry gains a new entry without matching override blocks; all three overrides were updated in the same commit `f778b0b` so the guard stayed green). The integration test suite was written GREEN (with verified passing assertions) because URL-04's mandate is "the test exists and is real", not "the implementation reached test-first".

## Authentication Gates

None — no external services contacted; `FetchAndScrapeTool._run` is patched in both tests.

## Known Stubs

None. All new agent surface is wired to real code paths:

- V001 prompt is loaded from disk in tests (not stubbed).
- `FetchAndScrapeTool` is the real Wave 2 tool; only its `_run` method is patched in tests so safe_fetch isn't reached.
- `RecipeData` validation is real (the structured_response goes through `ToolStrategy.parse → RecipeData.model_validate`).

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced by this plan. The threat surface scoped in `<threat_model>` (LLM hallucinate, tool loop, overrides drift, prompt-inject-HTML) is unchanged; mitigations applied:

- T-23-LLM-HALLUCINATE-FIELDS: V001 prompt explicit "Never fabricate" + `response_format=RecipeData`.
- T-23-TOOL-LOOP: V001 prompt "Call fetch-and-scrape EXACTLY ONCE … Do not call any tool more than once."
- T-23-OVERRIDES-DRIFT: all three overrides + AGENT_REGISTRY in same commit `f778b0b`; CI guard green.
- T-23-PROMPT-INJECT-HTML: accepted per plan; FetchAndScrapeTool's 200k-char cap (Wave 2) carries forward; response_format constrains output shape.

## Pre-existing failure (out of scope)

`tests/unit/test_agents_registry.py::test_handle_incoming_message_registered_in_agent_registry` fails because it expects `prompt_path` to end with `V005.md` while the registry has been on `V006.md` since Phase 22. Verified pre-existing via `git stash` — unrelated to this plan's diff. Logged for the verifier; not fixed here per the scope-boundary rule.

## Self-Check: PASSED

**Files created (existence verified):**
- `src/robotina/agent/prompts/gather-from-url/V001.md` — FOUND
- `tests/agents/test_gather_from_url_agent.py` — FOUND
- `.planning/phases/23-url-ingestion-topic-2/23-04-SUMMARY.md` — FOUND (this file)

**Commits (presence verified via `git log`):**
- `f778b0b` `feat(23-04): register gather-from-url agent + sync overrides + V001 prompt` — FOUND
- `9ffab25` `feat(23-04): wire FetchAndScrapeTool injection + gather-from-url agent tests` — FOUND
