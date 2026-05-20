---
phase: 23-url-ingestion-topic-2
plan: 03
subsystem: agent
tags: [tool, recipe-scrapers, trafilatura, langchain, base-tool, fetch-and-scrape, url-ingestion]

requires:
  - phase: 23-url-ingestion-topic-2
    provides: safe_fetch (SSRF/abuse defenses) — src/robotina/url/safe_fetch.py
provides:
  - FetchAndScrapeTool — deterministic URL → RecipeData extractor for the gather-from-url agent
  - FetchAndScrapeArgs / FetchAndScrapeResult — strict pydantic schemas
  - Per-field try/except scraper-extraction pattern (Pitfall 7) applied across the seven RecipeData fields the scraper populates
  - trafilatura fallback (text/html → cleaned plain text, capped at 200_000 chars)
affects:
  - 23-04 (gather-from-url agent — wires FetchAndScrapeTool)
  - 23-05 (add-recipe-from-url workflow + topology change in WORKFLOW_REGISTRY)
  - 23-06 (integration / smoke tests with real fixtures)
  - 24 (recipe-image step — re-uses safe_fetch with `expected_content_type="image/*"`)

tech-stack:
  added:
    - recipe-scrapers (wild_mode=True + per-method exception handling)
    - trafilatura (extract → plain text fallback)
  patterns:
    - Lazy imports inside `_run` (matches web_search.py): all heavy modules imported per-call, not at module level
    - Per-field try/except over scraper methods (Pitfall 7): one broken method never aborts extraction
    - Quality gate before emitting structured artifact (≥2 ingredients AND ≥1 step, D-19)
    - Tool exceptions re-raise (D-03): SafeFetchError → ToolMessage(error) → step FAILED → wake surfaces URL + reason
    - Query-string stripped from logged URLs (PII / token safety, inherited from safe_fetch INFO log)
    - 200_000-char cap on free-form text before LLM context (T-23-CTX-BLOAT)

key-files:
  created:
    - src/robotina/agent/tools/fetch_and_scrape.py
    - tests/agents/tools/__init__.py
    - tests/agents/tools/test_fetch_and_scrape_tool.py
  modified: []

key-decisions:
  - "Patch lazy-imported dependencies at their source module (e.g. `recipe_scrapers.scrape_html`, `trafilatura.extract`, `robotina.url.safe_fetch.safe_fetch`) rather than at the tool's import namespace — lazy `from x import y` resolves attribute at call time, so source-module patch works without sys.modules tricks."
  - "Test the `trafilatura returns None` branch explicitly (collapses to empty string, never None) — small defensive guarantee that's easy to regress."
  - "Inline `import re` at servings_qty coercion point rather than at module top — keeps module-level imports minimal and matches the lazy-import convention used elsewhere in this file."

patterns-established:
  - "Tool module structure: docstring → `from __future__ import annotations` → `logger = logging.getLogger(__name__)` → strict `*Args` schema (`ConfigDict(extra='forbid')`) → strict `*Result` schema (same) → BaseTool subclass with `name`/`description`/`args_schema` → `_run(...)` with all heavy imports inline → `_arun` thin async wrapper. (Mirrors web_search.py + start_workflow.py.)"
  - "Test module structure: helper builders (`_make_fetched`, `_make_scraper`) at top with side_effect / return_value bound from kwargs → one `def test_*` per behavioral path → all I/O patched at lazy-import source paths."

requirements-completed: [URL-02]

duration: 22min
completed: 2026-05-20
---

# Phase 23 Plan 03: FetchAndScrapeTool Summary

**Deterministic URL → RecipeData extractor (LangChain BaseTool) wrapping safe_fetch + recipe-scrapers(wild_mode=True) + trafilatura fallback, with per-field try/except, quality gate (≥2 ingredients AND ≥1 step), 200_000-char text cap, and D-03 fail-fast SafeFetchError propagation.**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-05-20T22:30:00Z
- **Completed:** 2026-05-20T22:52:00Z
- **Tasks:** 2 / 2
- **Files created:** 3 (1 module + 1 test package init + 1 test module)
- **Files modified:** 0

## Accomplishments

- Implemented `FetchAndScrapeTool` (URL-02 / D-03) in `src/robotina/agent/tools/fetch_and_scrape.py` (229 lines).
- Strict pydantic schemas (`FetchAndScrapeArgs`, `FetchAndScrapeResult`) with `ConfigDict(extra="forbid")` — unknown LLM-emitted fields rejected at args-validation time.
- Per-field try/except over the seven canonical scraper methods (name/description/total_time/prep_time/cook_time/yields/canonical_url + ingredients + instructions_list) — Pitfall 7 mitigation; one broken method never aborts extraction.
- Quality gate (D-19): scraper output emitted only when RecipeData validates AND ingredients ≥ 2 AND steps ≥ 1; otherwise trafilatura extract path runs.
- trafilatura fallback capped at 200_000 chars (T-23-CTX-BLOAT mitigation).
- SafeFetchError re-raises out of `_run` (D-03) — no rescue inside the tool; LangChain surfaces it as ToolMessage(error).
- 15-test unit suite in `tests/agents/tools/test_fetch_and_scrape_tool.py` (330 lines) covering every happy/sad/coercion/cap path — all green, no real network I/O.

## Task Commits

1. **Task 1: Implement FetchAndScrapeTool** — `cb15990` (feat)
2. **Task 2: Write unit tests for FetchAndScrapeTool** — `cd7ae19` (test)

_Plan metadata (this SUMMARY) will be committed as a final docs commit after this file is written._

## Files Created/Modified

- `src/robotina/agent/tools/fetch_and_scrape.py` (created, 229 lines) — `FetchAndScrapeArgs`, `FetchAndScrapeResult`, `FetchAndScrapeTool`. All heavy deps lazy-imported inside `_run`.
- `tests/agents/tools/__init__.py` (created, empty) — package marker.
- `tests/agents/tools/test_fetch_and_scrape_tool.py` (created, 330 lines) — 15 tests, all mocked.

## Decisions Made

- **Lazy-import patch targets:** Mocks are patched at the source modules (`robotina.url.safe_fetch.safe_fetch`, `recipe_scrapers.scrape_html`, `trafilatura.extract`) rather than at the tool's namespace. Because the tool uses `from X import Y` inside `_run`, the attribute is resolved at call time on the source module — source-module patching is the correct and minimal target.
- **Explicit `trafilatura → None` coverage:** The plan didn't enumerate this path explicitly, but it's a natural defensive guarantee (the canonical code uses `... or ""`) and a one-line test prevents future regression.
- **`import re` inline** at the servings_qty coercion point — keeps module imports light and matches the lazy-import convention used everywhere else in the module.

## Deviations from Plan

**None — plan executed exactly as written.**

Minor observation, not a deviation: the plan lists `tests/agents/__init__.py` among files to create, but that file already exists in the repository (created in 21-06 commit `0094803`). The execution skipped creating it (touching it would have been a no-op overwrite). Both `tests/agents/tools/__init__.py` and the test module itself were created as planned.

## Issues Encountered

None.

## Threat Model Coverage

All `mitigate` dispositions from the plan's `<threat_model>` are implemented:

| Threat ID | Disposition | Implementation |
|-----------|-------------|----------------|
| T-23-PARSER-CRASH | mitigate | Per-field try/except over each scraper method (Pitfall 7) — verified by `test_recipe_scrapers_exception_per_field_isolated` and `test_scrape_html_raises_falls_back_to_trafilatura`. |
| T-23-CONTENT-INJECTION | accept | (no code action required) |
| T-23-CTX-BLOAT | mitigate | `cleaned = cleaned[:200_000]` before placement into result — verified by `test_html_text_capped_to_200k`. |
| T-23-SAFE-FETCH-BYPASS | mitigate | `safe_fetch(...)` called WITHOUT enclosing try/except; SafeFetchError re-raises — verified by `test_safe_fetch_error_propagates`. |
| T-23-LARGE-BODY-DECODE | accept | (safe_fetch already caps body at 5 MB) |

## User Setup Required

None — no external service configuration required for this plan. Recipe-scrapers and trafilatura are pure-Python libraries; trafilatura was already declared in `pyproject.toml` by 23-01.

## Verification

- `uv run python -c "from robotina.agent.tools.fetch_and_scrape import FetchAndScrapeTool, FetchAndScrapeArgs, FetchAndScrapeResult; t=FetchAndScrapeTool(); print(t.name, t.args_schema.__name__)"` → `fetch-and-scrape FetchAndScrapeArgs`
- `uv run pytest tests/agents/tools/test_fetch_and_scrape_tool.py -q` → `15 passed in 0.50s`
- All grep acceptance criteria pass (`name: str = "fetch-and-scrape"`, `extra="forbid"` ×3, `from recipe_scrapers import scrape_html`, `from trafilatura import extract`, `from robotina.url.safe_fetch import safe_fetch`, `wild_mode=True` ×3, `model_dump_json` ×2).

## Self-Check

- File `src/robotina/agent/tools/fetch_and_scrape.py` → FOUND
- File `tests/agents/tools/__init__.py` → FOUND
- File `tests/agents/tools/test_fetch_and_scrape_tool.py` → FOUND
- Commit `cb15990` (feat: FetchAndScrapeTool) → FOUND
- Commit `cd7ae19` (test: unit tests) → FOUND

## Self-Check: PASSED

## Next Phase Readiness

- 23-04 (gather-from-url agent) can now `from robotina.agent.tools.fetch_and_scrape import FetchAndScrapeTool` and pass it to `LLMBackend.create_agent(..., tools=[FetchAndScrapeTool()], response_format=RecipeData)`.
- The tool's contract (re-raises SafeFetchError, never returns an error string from `_run`) is what wires the wake-reply surface in 23-05.

---
*Phase: 23-url-ingestion-topic-2*
*Completed: 2026-05-20*
