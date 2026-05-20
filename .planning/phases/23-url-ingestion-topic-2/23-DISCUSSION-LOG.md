# Phase 23 Discussion Log

**Date:** 2026-05-20
**Mode:** `--auto` (Auto Mode active — Claude made the calls without stopping)

## Gray areas presented

User selected ALL FOUR:

1. Workflow variant shape (URL-03)
2. gather-from-url + LLM fallback shape (URL-02/04)
3. Robotina V007 URL detection (URL-05)
4. Eval set + harness (URL-06 + EXP-02)

## Decisions made (auto-mode rationale)

### 1. Workflow variant shape
- **D-01 (A) per-source workflow types**: rename `add-recipe` → `add-recipe-from-query`, add `add-recipe-from-url` peer. Discriminated `input` union `AddRecipeQueryInput | AddRecipeUrlInput` (no `kind` field needed — shapes mutually exclusive). `@model_validator(mode='after')` on `StartWorkflowArgs` enforces workflow_type ↔ input pairing.
- **D-02 `AddRecipeUrlInput {url: str}` only** — no hint field; mirror AddRecipeQueryInput shape.

### 2. gather-from-url shape
- **D-03 (α) LLM agent + deterministic `FetchAndScrapeTool`** with `response_format=RecipeData`. Tool runs `safe_fetch` + recipe-scrapers + per-field try/except + Pydantic partial-validation; returns scraped-or-null + trafilatura-cleaned html_text. Agent's prompt branches on the tool's response. `safe_fetch` failures re-raise → step FAILED → wake reply surfaces URL.
- **D-04 trafilatura>=1.6** for HTML→text preprocessing (purpose-built; ~10-50× token savings vs raw HTML; recommended in Pitfall 7).

### 3. Robotina V007 URL detection
- **D-05 LLM-judgment, not regex.** Strip surrounding punctuation; preserve paths/queries. Ambiguous bare hostnames (no scheme) → respond+clarify, do not start workflow.
- **D-06 one start-workflow per URL** — Phase 22 multi-recipe carry-over; soft cap of 5 applies across combined query + URL count.
- **D-07 mixed text + URLs → one workflow per item per variant**. No "mixed batch" abstraction.
- **D-08 wake helper reads BOTH `recipe_query` and `recipe_url`** from shared_context to populate `WorkflowOutcomeSummary.recipe_query` (kept as display-label field name; rename deferred per `feedback_avoid_premature_abstraction`).

### 4. Eval set + harness
- **D-09 one concrete script** `experiments/gather_from_url.py` (no framework). `pyproject.toml` adds `experiments.gather_from_url`.
- **D-10 21 URLs** (20 Spanish recipe blog + 1 known-difficult) across 6 coverage classes: well-supported scraper / `wild_mode` JSON-LD / LLM-fallback / locale-units / known-difficult / sanity-non-recipe.
- **D-11 URL-level scoring**: per-URL pass = ≥6/8 expected-populated fields present. Aggregate pass = ≥17/21 URLs pass (≈85%).
- **D-12 thresholds**: OpenAI staging = merge gate; Ollama dev informational; Anthropic optional.
- **D-13 file structure**: `23-EVAL-SET.md` (canonical) + `23-EVAL-RESULTS-<backend>.md` (per-backend operator runs) + `23-SMOKE.md` (final verdict).

### `safe_fetch` design (FIRST commit per ROADMAP)
- **D-14 location** `src/robotina/url/safe_fetch.py` (new top-level `url/` package, sibling to `queue/`, `agent/`).
- **D-15 sync, not async** — RQ workers are sync; `httpx.Client` sync mode.
- **D-16 signature** `safe_fetch(url, *, expected_content_type, max_bytes, timeout_s, allow_http) -> SafeFetchResult`; raises `SafeFetchError`. Six defenses: scheme allowlist, post-DNS private-IP block, manual redirect re-validation (max 3 hops), configurable timeout, content-length cap + streaming abort, content-type sniff. + gzip-bomb defense (20:1 ratio cap).
- **D-17 `URL_INGESTION_ALLOW_HTTP` env var** for dev/testing; default False (HTTPS-only). Added to `.env.example` per `feedback_env_example`.

### Test strategy (Claude's discretion)
- D-18 `safe_fetch` unit tests — one per defense (load-bearing safety net; host-dev makes localhost a real attack surface).
- D-19 `FetchAndScrapeTool` integration tests (well-supported / wild_mode / insufficient / total-fail / safe_fetch-raises).
- D-20 `gather-from-url` agent integration test (mocked LLM, all three tool-return paths).
- D-21 WORKFLOW_REGISTRY tests (both variants 6 steps each, no `"add-recipe"` key).
- D-22 `StartWorkflowTool` schema tests (union + model_validator pairing).
- D-23 AGENT_REGISTRY + overrides atomic commit.
- D-24 Operator runs eval; phase verifies as `human_needed` until `23-SMOKE.md` verdict pass.
- D-25 V006 retained for rollback.

### Claude's discretion items
- Tool naming `FetchAndScrapeTool` in `src/robotina/agent/tools/fetch_and_scrape.py`.
- Plain pydantic union (no explicit discriminator field) for input.
- Single atomic rename commit (no transitional alias).
- Dashboard label `"gather-from-url": "Búsqueda por URL"`.
- Plan execution order: 23-01 (safe_fetch FIRST), 23-02 (schema + variant), 23-03 (tool), 23-04 (agent + overrides), 23-05 (V007), 23-06 (harness + eval-set), 23-07 (operator-run + ticks).
- New env var `URL_INGESTION_ALLOW_HTTP`; new dep `trafilatura>=1.6`; no Alembic revision; no DDL.

## Deferred ideas captured

- recipe-image step (Phase 24)
- vision-LLM page validation (Phase 24 follow-up)
- CDN/HTML caching, recipe rehosting (v2)
- `hint` field on `AddRecipeUrlInput`
- `recipe_source` field rename (premature)
- LLM-judge / vision-model correctness scoring (v1.2)
- JS-rendered recipe pages
- Spanish translation of foreign recipe URLs
- Inline dedup ("este nombre ya está guardado")
- recipe-scrapers site-list expansion
- HTTPS-only without escape hatch (dev needs HTTP)

## Scope creep redirected

None during discussion — all four gray areas stayed within the URL-01..06 + EXP-02 boundary. Recipe-image surfaced naturally as a Phase 24 dependency (shared-tail helper extraction) and was deferred without resistance.
