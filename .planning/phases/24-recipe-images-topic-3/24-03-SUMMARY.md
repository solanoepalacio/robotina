---
phase: 24-recipe-images-topic-3
plan: 03
subsystem: agent-tools
tags: [tavily, image-search, agent-tools, langchain-tools, pytest, mocking]

# Dependency graph
requires:
  - phase: 04-recipe-research
    provides: WebSearchTool TAVILY_API_KEY bracket-read + lazy-import pattern (analog)
  - phase: 23-url-ingestion-topic-2
    provides: TAVILY_API_KEY already declared in .env.example
provides:
  - tavily_image_search(query, *, max_results=5) -> list[str] plain function
  - Mocked-TavilyClient unit-test pattern for D-12-class tools (no BaseTool wrapping)
affects: [24-04-acquire-recipe-image, 24-04-recipe-image-eval]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Plain-function Tavily wrapper (no BaseTool) for deterministic non-LLM call sites (D-12)"
    - "Defensive parsing for Tavily images list[str] vs list[dict] dual response shapes"

key-files:
  created:
    - src/robotina/agent/tools/tavily_image_search.py
    - tests/agent/tools/test_tavily_image_search.py
    - tests/agent/__init__.py
    - tests/agent/tools/__init__.py
  modified: []

key-decisions:
  - "Plain function, not BaseTool subclass (D-12) — no LLM agent uses it in v1.1; deterministic acquire_recipe_image (24-04) will call it directly"
  - "search_depth='basic' (image lookup is shallow; matches Tavily image-search defaults) — different from WebSearchTool's 'advanced'"
  - "Defensive dual-shape parsing so future include_image_descriptions=True flip does not break callers"
  - "Test path tests/agent/tools/ (singular) per plan literal, even though existing repo convention is tests/agents/tools/ (plural) — plan acceptance criteria reference singular path verbatim"

patterns-established:
  - "Tavily plain-function wrapper: lazy `from tavily import TavilyClient` inside body, `os.environ['TAVILY_API_KEY']` bracket-read for fail-loud, INFO log of query + result count (no key leakage — T-24-04)"
  - "Mock-TavilyClient unit pattern: `patch('tavily.TavilyClient')`, set `.return_value.search.return_value`, assert `call_args.kwargs` for contract"

requirements-completed: [IMG-02]

# Metrics
duration: 8min
completed: 2026-05-22
---

# Phase 24 Plan 03: Tavily Image Search Tool Summary

**`tavily_image_search` plain function — Tavily image-search primitive with TAVILY_API_KEY fail-loud, lazy SDK import, and four unit tests covering happy / empty / misconfig / defensive-dict paths.**

## Performance

- **Duration:** ~8 min
- **Completed:** 2026-05-22
- **Tasks:** 2 / 2
- **Files created:** 4 (1 source + 1 test + 2 `__init__.py`)
- **Files modified:** 0

## Accomplishments
- New `tavily_image_search(query, *, max_results=5) -> list[str]` plain function ready for `acquire_recipe_image` (plan 24-04) to consume directly.
- D-16 contract covered by four passing unit tests (happy, empty, missing-key, defensive-dict-shape).
- Mirrors `WebSearchTool`'s established idioms: bracket-read fail-loud, lazy `TavilyClient` import, INFO log with no key leakage.
- Defensive parsing handles both Tavily response shapes (`list[str]` default, `list[dict]` when `include_image_descriptions=True`) so a future caller flip cannot silently break consumers.

## Task Commits

1. **Task 1: Create tavily_image_search function** — `3dd91b5` (feat)
2. **Task 2: D-16 unit tests** — `8495ff8` (test)

## Files Created/Modified

- `src/robotina/agent/tools/tavily_image_search.py` (new) — 66 lines; plain function wrapping `TavilyClient.search(include_images=True)`; lazy import inside body; bracket-read of `TAVILY_API_KEY`; INFO log with query + count only; defensive list[str]/list[dict] parsing.
- `tests/agent/tools/test_tavily_image_search.py` (new) — 4 mocked unit tests, all passing.
- `tests/agent/__init__.py`, `tests/agent/tools/__init__.py` (new) — empty package markers required by plan path layout.

## Decisions Made
- **Test directory path** — plan's `<files>` frontmatter and all acceptance criteria reference `tests/agent/tools/` (singular). The existing repo uses `tests/agents/tools/` (plural). Followed plan literally (created the singular-path namespace). If future phases want to unify, consolidating both into the existing plural convention is a one-`git mv` away.
- **`search_depth="basic"`** — image search does not benefit from `advanced` depth (which adds raw_content); kept basic to minimize API spend. (`WebSearchTool` uses `advanced` because it needs raw HTML content for the gather agent.)

## Deviations from Plan

None — plan executed exactly as written for both tasks. One micro-edit was needed before Task 1 commit: the source docstring originally contained the phrase "No BaseTool wrapping" which made the plan's `grep -c "BaseTool" ... returns 0` verification fail; rephrased to "No LangChain tool wrapping" to satisfy the literal acceptance criterion without changing meaning. Recorded here for traceability; not a behavioral deviation.

## Issues Encountered

None.

## Verification

- `uv run python -c "from robotina.agent.tools.tavily_image_search import tavily_image_search; ..."` → signature ok
- `uv run pytest tests/agent/tools/test_tavily_image_search.py -x -q` → 4 passed in 0.12s
- `uv run pytest tests/agent/tools/ -q` → 4 passed in 0.06s
- `grep -c "BaseTool" src/robotina/agent/tools/tavily_image_search.py` → 0
- `grep -c "def tavily_image_search" src/robotina/agent/tools/tavily_image_search.py` → 1
- `grep -c 'os.environ\["TAVILY_API_KEY"\]' src/robotina/agent/tools/tavily_image_search.py` → 1
- `grep -c "include_images=True" src/robotina/agent/tools/tavily_image_search.py` → 1
- `grep -c "    from tavily import TavilyClient" src/robotina/agent/tools/tavily_image_search.py` → 1 (lazy import inside function body)

## Threat Model Adherence

- T-24-03 (SSRF): out of scope here; this plan only returns `list[str]`. Downstream `safe_fetch` in 24-04 validates URLs.
- T-24-04 (API key disclosure): logger emits only `query=%r results=%d` — never the key. Verified by inspection.
- T-24-05 (DoS): function does NOT swallow exceptions; transport errors propagate to caller, runner's non_fatal_on_failure (24-01) absorbs them. Verified — the function body has no try/except.

## User Setup Required

None — `TAVILY_API_KEY` is already declared in `.env.example` from Phase 23 and reused unchanged.

## Next Phase Readiness

- `acquire_recipe_image` (plan 24-04) can now import and call `tavily_image_search` directly as its Tavily fallback branch.
- Test fixture pattern (mock-TavilyClient) is reusable by 24-04 unit tests when they assert the fallback ladder calls Tavily on source-page miss.

## Self-Check: PASSED

- File `src/robotina/agent/tools/tavily_image_search.py` — FOUND
- File `tests/agent/tools/test_tavily_image_search.py` — FOUND
- File `tests/agent/__init__.py` — FOUND
- File `tests/agent/tools/__init__.py` — FOUND
- Commit `3dd91b5` (feat) — FOUND in git log
- Commit `8495ff8` (test) — FOUND in git log

---
*Phase: 24-recipe-images-topic-3*
*Plan: 03*
*Completed: 2026-05-22*
