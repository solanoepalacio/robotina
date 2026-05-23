---
phase: 24-recipe-images-topic-3
plan: 07
subsystem: experiments
tags: [experiment-harness, recipe-image-eval, langwatch-trace, manual-gate, fixture-set, pyproject-script, claude-md]

# Dependency graph
requires:
  - phase: 24-recipe-images-topic-3
    plan: 04
    provides: "acquire_recipe_image deterministic function (fallback ladder + safe_fetch image/* validation)"
  - phase: 24-recipe-images-topic-3
    plan: 05
    provides: "recipe-image deterministic branch wired into run_task (used by production; the experiment script bypasses it via direct function call per D-09)"
provides:
  - "24-IMG-EVAL-SET.md canonical fixture (13 rows, 5 coverage classes per D-09: 5 source-page-hit, 3 source-page-miss, 3 query-only, 1 known-difficult, 1 sanity-miss)"
  - "experiments/recipe_image.py manual-eval harness — direct acquire_recipe_image call, LangWatch tracer per row, branch_fired classification (source_page | tavily | miss | validation_failed | exception)"
  - "experiments/recipe_image.py emits 24-IMG-EVAL-RESULTS-<backend>.md with verdict: pending frontmatter for operator (24-09) review"
  - "pyproject.toml [project.scripts] entry experiments.recipe_image"
  - "CLAUDE.md installation reference for experiments.recipe_image"
affects: [24-08, 24-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Agent-less manual-eval harness (no build_agent step) — direct deterministic-function call under a LangWatch trace, mirroring the recipe-image jobs.py branch's own trace wrap (Pitfall 8)"
    - "Branch-fired heuristic for evaluation: host-suffix match on candidate_url vs source_url. Tail-domain match tolerates CDN subdomains without parameterizing the operator's mental model"
    - "Eval-set parser pattern reused from experiments/gather_from_url.py: walk markdown line-by-line, locate ## <section> heading + table separator, collect | ... | rows until blank line or next heading"

key-files:
  created:
    - ".planning/phases/24-recipe-images-topic-3/24-IMG-EVAL-SET.md"
    - "experiments/recipe_image.py"
  modified:
    - "pyproject.toml"
    - "CLAUDE.md"

key-decisions:
  - "Used a 13-row fixture (target was 10-15). 5 source-page-hit reuses URLs 1-5 from 23-EVAL-SET (already verified to have JSON-LD images during Phase 23). 3 source-page-miss draws from Phase 23 class-3 LLM-fallback URLs (schema.org coverage spotty). 3 query-only uses common AR/ES recipe names that are likely to be well-indexed by Tavily for baseline-quality measurement. 1 known-difficult is 'milanesa criolla salteña' (NW-Argentine regional variant) per D-09's documents-the-v1.1-gap intent. 1 sanity-miss uses synthetic name + non-routable invalid.example.localhost.invalid source URL — exercises both safe_fetch SSRF defense AND Tavily empty-result path."
  - "branch_fired classification expanded beyond plan's source_page|tavily into 5 buckets: source_page, tavily, miss, validation_failed, exception. The plan's verbatim per-row body lumped 'RecipeImageAcquisitionError' and 'SafeFetchError' under separate but informal branch labels; making them explicit distinct buckets lets the operator's Go/No-Go gate (no SafeFetchError on legitimate URLs) tick mechanically against the safe_fetch_ok column rather than requiring error-string parsing."
  - "Surgical/additive edits to pyproject.toml and CLAUDE.md only — one new line each, placed alongside existing experiments.* entries — to minimize merge friction with sibling plan 24-08 which also modifies these two files (it adds experiments.robotina_wake)."
  - "Used existing langwatch.trace(metadata={...}) API rather than langwatch.langchain.LangChainTracer (which gather_from_url uses for LLM-agent tracing). Per D-09 / Pitfall 8 / the recipe-image branch in jobs.py, deterministic agent-less tasks use the simpler trace context manager — no LLM means no LLM-span. Trace wrap is best-effort: setup failures and context-enter failures degrade gracefully (the row still runs, the harness logs a warning) so the eval can complete even when LangWatch credentials aren't loaded."
  - "Reused experiments/gather_from_url.py's parser shape verbatim (line-walk, ## section heading detection, header+separator+row state machine) but adapted to 6-column 24-IMG-EVAL-SET schema (idx, coverage_class, recipe_name, source_url, expected_branch, notes). Source-URL normalization: '(none)' / empty cells → None; anything else passes through (including the sanity-miss row's deliberately-broken invalid.example.localhost.invalid URL, which safe_fetch will reject)."
  - "ReplyContext platform value is the Literal['telegram'] only allowed in the model; harness sets platform='telegram', chat_id='0', user_id='0'. The deterministic acquire_recipe_image function does not read reply_context — it flows through for parity with other steps (per D-03)."

patterns-established:
  - "Manual-eval harness for agent-less deterministic tasks: parser + per-row run_one + verdict: pending markdown emitter. Reusable template for any future deterministic-task eval (Phase 25+)."
  - "Branch-fired classification for fallback-ladder experiments: host-match heuristic for the source_page vs tavily distinction; distinct error-class buckets (miss, validation_failed, exception) for non-happy-path observability."

requirements-completed:
  - EXP-03
  - EXP-06
  - EXP-01

# Metrics
duration: ~15min
completed: 2026-05-22
---

# Phase 24 Plan 07: experiments.recipe_image eval harness + fixture set Summary

**Shipped the deterministic-recipe-image manual-eval harness: 13-row canonical fixture set across 5 D-09 coverage classes, a runnable `uv run experiments.recipe_image --backend <label>` script that exercises `acquire_recipe_image` directly under a LangWatch trace, and the `pyproject.toml` + `CLAUDE.md` script declarations (EXP-06). The harness emits a `verdict: pending` markdown table for operator (24-09) review.**

## Performance

- **Duration:** ~15 minutes
- **Tasks:** 3 / 3
- **Files created:** 2 (`24-IMG-EVAL-SET.md`, `experiments/recipe_image.py`)
- **Files modified:** 2 (`pyproject.toml`, `CLAUDE.md` — surgical/additive)
- **Commits:** 3 task commits

## Accomplishments

### Task 1 — 24-IMG-EVAL-SET.md fixture (commit `0bfaf02`)

- Created `.planning/phases/24-recipe-images-topic-3/24-IMG-EVAL-SET.md` with frontmatter (`eval_set_version: 1`, `phase: 24`, `total_rows: 13`, `coverage_classes` list, `last_updated: 2026-05-22`).
- 13 data rows distributed across 5 D-09 coverage classes:
  - 5 `source-page-hit` (rows 1-5): reuse Phase 23 URLs 1-5 (Paulina Cocina, Directo al Paladar, Cocinatis, Recetas Gratis, Webos Fritos — all known to have `.image()` data).
  - 3 `source-page-miss` (rows 6-8): Cocineros Argentinos, Comer con Poco, Cucinare — Phase 23 class-3 sites where `.image()` likely raises / returns None; Tavily fallback expected.
  - 3 `query-only` (rows 9-11): "milanesa napolitana", "tarta de manzana", "asado argentino" — `source_url=None` (literal `(none)` cell) → Tavily-only branch.
  - 1 `known-difficult` (row 12): "milanesa criolla salteña" — NW-Argentine regional variant; documents v1.1 gap per D-09.
  - 1 `sanity-miss` (row 13): `__force_miss__ receta inexistente xyz123` + non-routable `invalid.example.localhost.invalid` URL — exercises both safe_fetch defense + Tavily empty-result → `RecipeImageAcquisitionError` → `StepUnavailableArtifact` path.
- Added `## Class Distribution` table + `## Notes` section explaining the sanity-miss mechanism, the branch-fired host-match heuristic, and the operator gate (60% Tavily-relevance / no SafeFetchError on legitimate URLs).
- Verified by the plan's inline parser snippet: 13 data rows, all 5 classes present.

### Task 2 — experiments/recipe_image.py harness (commit `f7dc28c`)

- Created `experiments/recipe_image.py` (539 lines; target was 150-250, longer because the eval-set parser + RowResult dataclass + 5-bucket branch classifier + verdict-frontmatter writer each pull their own block).
- Module header documents the D-09 / EXP-03 purpose, coverage classes, backend semantics, prerequisites.
- Constants: `PHASE = "24"`, `EXPERIMENT_NAME = "recipe-image-eval"`, `DEFAULT_EVAL_SET`, `DEFAULT_OUT_TEMPLATE`.
- `EvalRow` dataclass + `parse_eval_set(path)` parser walks markdown line-by-line, locates `## Rows` heading, then header+separator+row state machine. Source-URL cell normalization: `(none)` / empty → `None`; non-URL strings pass through verbatim (so the sanity-miss row's deliberately-broken URL feeds the function's safe_fetch defenses).
- `run_one(row, backend)`:
  - Builds synthetic `RecipeImageInput` via `_build_input` (lazy-imports `RecipeImageInput`, `RecipeData`, `ReplyContext`; uses `os.environ.get("HOUSEHOLD_ID", "dev-os")`; `ReplyContext(platform="telegram", chat_id="0", user_id="0")`).
  - Wraps the call in `langwatch.trace(metadata={...phase:24, recipe_name, coverage_class, expected_branch, source_url, backend...})`. Trace setup and context-enter failures degrade to warning-and-continue so eval rows still run when LangWatch credentials aren't loaded.
  - Calls `acquire_recipe_image(task_input)`; classifies into 5 buckets:
    - happy + host-match → `source_page`
    - happy + host-mismatch → `tavily`
    - `RecipeImageAcquisitionError` → `miss`
    - `SafeFetchError` → `validation_failed`
    - any other `Exception` → `exception` (logs the type-name + message)
  - Returns `RowResult(idx, coverage_class, recipe_name, source_url, expected_branch, candidate_url, branch_fired, safe_fetch_ok, error)`.
- `_hosts_match(candidate, source)` heuristic: parsed-host equality first; falls back to registered-domain tail (last two labels) match. CDN subdomains on the same registered domain count as `source_page`.
- `write_results(out_path, backend, results, operator)` emits the per-backend markdown:
  - YAML frontmatter: `verdict: pending`, `backend`, `eval_set_version: 1`, `phase: 24`, `date`, `operator`.
  - `## Aggregate` (totals per branch).
  - `## Per-row results` table with columns: `idx | class | recipe | source_url | expected | candidate_url | branch_fired | safe_fetch_ok | image looks right? | error`. The "image looks right?" cell ships as `_operator: Y/N_` placeholder for visual review.
  - `## Notes` (operator-fillable).
  - `## Go / No-Go` checklist mirroring the Pitfall 8 / D-11 gate.
- `main()` CLI: `--backend` (required, label-only string), `--eval-set` (defaults), `--out` (defaults), `--limit`, `--operator`. Flushes LangWatch tracer provider before writing results.

### Task 3 — pyproject.toml + CLAUDE.md entries (commit `9fc4cca`)

- `pyproject.toml [project.scripts]`: added one line `"experiments.recipe_image" = "experiments.recipe_image:main"` immediately after the existing `experiments.gather_from_url` line. Sibling plan 24-08 will add `experiments.robotina_wake` in the same block.
- `CLAUDE.md`: added one commented-out installation reference next to the existing `# "experiments.recipe_research" = ...` comment in the Installation section. This is where the existing pattern lives (no formal "Experiments" table exists yet; not adding one to minimize cross-plan merge friction). Plan 24-08 will add its `experiments.robotina_wake` line in the same block.
- Verified EXP-01 (existing scripts unchanged):
  - `uv run python -c "import experiments.recipe_research, experiments.recipe_load, experiments.gather_from_url, experiments.recipe_image"` → all imports ok.
  - `uv run experiments.recipe_research --help` → exits 0.
  - `uv run experiments.gather_from_url --help` → exits 0.
  - `uv run experiments.recipe_image --help` → exits 0.

## Test Results

- Full repo suite: **423 passed, 38 failed, 74 errors** (baseline from 24-06: 423 passed, 38 failed, 74 errors). **My changes: 0 new failures, 0 new errors.**
- All 38 failures + 74 errors are pre-existing infrastructure issues (Postgres unreachable for db/gateway/migration tests, langwatch credentials, dashboard auth) — none introduced by 24-07.
- The plan's automated `<verify>` block for Task 2 (module imports + `PHASE == "24"`) passes.
- Parser-end-to-end test: `parse_eval_set(DEFAULT_EVAL_SET)` returns 13 rows, all 5 coverage classes, 4 rows with `source_url=None` (the 3 query-only + 1 known-difficult).

## Acceptance grep counts

| Check | Expected | Actual |
|-------|----------|--------|
| `wc -l experiments/recipe_image.py` | ≥150 | 539 |
| `grep -c 'def main' experiments/recipe_image.py` | 1 | 1 |
| `grep -c 'PHASE = "24"' experiments/recipe_image.py` | 1 | 1 |
| `grep -c 'from robotina.agent.tasks.recipe_image import' experiments/recipe_image.py` | 1 | 1 |
| `grep -c 'langwatch.trace(' experiments/recipe_image.py` | ≥1 | 1 |
| `grep -c 'verdict: pending' experiments/recipe_image.py` | ≥1 | 6 |
| `grep -c 'phase.*24' experiments/recipe_image.py` | ≥1 | 2 |
| `grep -c 'experiments.recipe_image" = "experiments.recipe_image:main' pyproject.toml` | 1 | 1 |
| `grep -c "experiments.recipe_image" CLAUDE.md` | ≥1 | 1 |
| `uv run python -c "import experiments.recipe_research, experiments.recipe_load, experiments.gather_from_url, experiments.recipe_image"` | exit 0 | exit 0 |
| `uv run experiments.recipe_research --help` | exit 0 | exit 0 |
| `uv run experiments.gather_from_url --help` | exit 0 | exit 0 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Robustness] Expanded `branch_fired` classification from 2 buckets to 5**

- **Found during:** Task 2 — drafting the per-row body.
- **Issue:** The plan's verbatim per-row body lumped error paths into informal labels (`branch_fired="miss"` for `RecipeImageAcquisitionError`, `branch_fired="validation_failed"` for `SafeFetchError`, `branch_fired="exception"` for fallthrough). Each was scattered across the example code's `except` blocks without a unifying enum. Operator gates would need error-string parsing to distinguish, e.g., "no SafeFetchError on legitimate URLs" — flaky.
- **Fix:** Made the 5-bucket scheme (`source_page | tavily | miss | validation_failed | exception`) explicit and load-bearing for the Go/No-Go gate in the results template. The "no SafeFetchError on legitimate URLs" check now ticks mechanically against the `safe_fetch_ok` column (`false` vs `true | n/a`) rather than requiring error-string greps.
- **Files modified:** `experiments/recipe_image.py`
- **Commit:** `f7dc28c`

**2. [Rule 2 — Robustness] Wrapped LangWatch trace setup and context-enter in try/except with graceful degradation**

- **Found during:** Task 2 — running the harness's `--help` smoke (which lazy-imports langwatch via the load-bearing module-top `import langwatch`).
- **Issue:** Plan's verbatim code wrapped only the inner `acquire_recipe_image` call in the LangWatch `with` block. If `langwatch.trace()` raises at construction time (e.g. credentials not set) OR if the context-manager `__enter__` raises (e.g. endpoint unreachable), the entire eval would fail to produce results — a deal-breaker for the operator who needs the markdown emit even when LangWatch is sad.
- **Fix:** Both `langwatch.trace(metadata=...)` construction and the `with trace_ctx:` block are wrapped in `try/except` that logs a warning and falls through to invoking the function outside the trace. The eval still emits results; LangWatch traces are best-effort (the comment-block in run_one documents this).
- **Files modified:** `experiments/recipe_image.py`
- **Commit:** `f7dc28c`

### Cosmetic refresh (not a Rule 1 fix — behavior unchanged)

**3. CLAUDE.md additive comment instead of formal table row**

- **Found during:** Task 3.
- **Issue:** Plan recommended adding a row to a CLAUDE.md "Experiments" table. CLAUDE.md does NOT currently have one — only a single commented-out `# "experiments.recipe_research" = ...` reference inside the Installation section. Inventing a new table cross-cuts plan 24-08's CLAUDE.md edit (also targets this file) and risks merge friction.
- **Fix:** Added a sibling commented-out reference for `experiments.recipe_image` right beside the existing `experiments.recipe_research` comment. Matches the only formatting pattern currently in CLAUDE.md. Plan 24-08 can append its `experiments.robotina_wake` line in the same block trivially.
- **Files modified:** `CLAUDE.md`
- **Commit:** `9fc4cca`

### Deferred Items

None.

## Threat Flags

No new threat surface introduced. The harness:
- Calls `acquire_recipe_image` (24-04, already threat-modeled — uses `safe_fetch` for SSRF defenses on both source-page and image validation fetches).
- Does not open new network endpoints, auth paths, or DB writes.
- LangWatch trace metadata includes `source_url` (not secret; identical to what jobs.py emits) and a `backend` label string (operator-supplied; no secret value).

## Commits

| Task | Commit    | Description |
|------|-----------|-------------|
| 1    | `0bfaf02` | docs(24-07): add 24-IMG-EVAL-SET canonical fixture set (13 rows, 5 coverage classes) |
| 2    | `f7dc28c` | feat(24-07): add experiments.recipe_image eval harness (EXP-03) |
| 3    | `9fc4cca` | chore(24-07): wire experiments.recipe_image in pyproject.toml + CLAUDE.md (EXP-06) |

## Self-Check: PASSED

- File `.planning/phases/24-recipe-images-topic-3/24-IMG-EVAL-SET.md`: FOUND
- File `experiments/recipe_image.py`: FOUND
- File `pyproject.toml` modified: FOUND
- File `CLAUDE.md` modified: FOUND
- File `.planning/phases/24-recipe-images-topic-3/24-07-SUMMARY.md`: FOUND
- Commit `0bfaf02`: FOUND
- Commit `f7dc28c`: FOUND
- Commit `9fc4cca`: FOUND
