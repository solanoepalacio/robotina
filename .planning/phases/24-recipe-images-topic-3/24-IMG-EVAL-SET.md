---
eval_set_version: 1
phase: 24
total_rows: 13
coverage_classes: source-page-hit, source-page-miss, query-only, known-difficult, sanity-miss
last_updated: 2026-05-22
---

# Phase 24 Recipe-Image Eval Set

Canonical 13-row fixture set for the deterministic `acquire_recipe_image`
function (Phase 24 / D-09 / EXP-03). The harness in
`experiments/recipe_image.py` parses this file, iterates each row, calls
`acquire_recipe_image` directly (no workflow round-trip, no DB), and
records the candidate URL + which branch fired + safe_fetch verdict +
LangWatch trace tag.

The operator (24-09) eyeballs the resulting markdown table and stamps
`verdict: pass | fail | needs-revision` after manual visual inspection of
each candidate image URL.

**Backends:** the harness's `--backend` argument is a label-only string
(e.g. `tavily-live`, `tavily-mock`) that informs the results filename and
the LangWatch metadata tag. The task itself is deterministic — backend
variance comes from Tavily's day-to-day result drift, not from a model
swap.

## Coverage classes

Per D-09 (CONTEXT lines 540-561):

| Class | Min rows | Description |
|-------|----------|-------------|
| source-page-hit | 5 | Known recipe-scrapers-supported URLs with `.image()` present; source-page branch fires |
| source-page-miss | 3 | URLs where `.image()` returns None / raises (no JSON-LD image); Tavily fallback fires |
| query-only | 3 | No `source_url`; common Spanish recipe names; Tavily branch only |
| known-difficult | 1 | Regional/obscure name where Tavily is expected to miss or return irrelevant |
| sanity-miss | 1 | Forced-miss row (recipe name with `__force_miss__` marker — script behavior: the literal source_url is a non-real domain that fails safe_fetch AND the recipe name is too synthetic for Tavily to resolve, exercising the "unavailable" path) |

## Rows

| idx | coverage_class | recipe_name | source_url | expected_branch | notes |
|-----|----------------|-------------|------------|-----------------|-------|
| 1 | source-page-hit | Tarta de manzana | https://www.paulinacocina.net/receta-de-tarta-de-manzana/47322 | source_page | Paulina Cocina — recipe-scrapers adapter; reuse from 23-EVAL row 1 |
| 2 | source-page-hit | Flan de huevo | https://www.directoalpaladar.com/postres/receta-de-flan-de-huevo-tradicional | source_page | Directo al Paladar — full schema.org markup; reuse from 23-EVAL row 2 |
| 3 | source-page-hit | Tarta de Santiago | https://www.cocinatis.com/recetas/postres/tarta-de-santiago/ | source_page | Cocinatis — well-marked JSON-LD; reuse from 23-EVAL row 3 |
| 4 | source-page-hit | Empanadas argentinas | https://www.recetasgratis.net/receta-de-empanadas-argentinas-caseras-50125.html | source_page | Recetas Gratis — strong schema.org; reuse from 23-EVAL row 4 |
| 5 | source-page-hit | Bizcocho de yogur | https://webosfritos.es/2009/04/bizcocho-de-yogur/ | source_page | Webos Fritos — JSON-LD via wild_mode; reuse from 23-EVAL row 5 |
| 6 | source-page-miss | Pastel de papa | https://www.cocinerosargentinos.com/recetas/12345-pastel-de-papa-clasico | tavily | Cocineros Argentinos — schema.org coverage spotty; source-page `.image()` likely raises; Tavily fallback fires |
| 7 | source-page-miss | Arroz tres delicias | https://comerconpoco.com/receta-arroz-tres-delicias/ | tavily | Comer con Poco — recipe in prose; no JSON-LD image; Tavily fallback |
| 8 | source-page-miss | Canelones de ricota y espinaca | https://www.cucinare.tv/recetas/canelones-de-ricota-y-espinaca | tavily | Cucinare — weak structured data; Tavily fallback expected |
| 9 | query-only | milanesa napolitana | (none) | tavily | Common AR Spanish recipe name; gauges Tavily image relevance |
| 10 | query-only | tarta de manzana | (none) | tavily | Common ES Spanish recipe name; baseline Tavily quality probe |
| 11 | query-only | asado argentino | (none) | tavily | Regional AR query; tests Spanish-language hint biasing |
| 12 | known-difficult | milanesa criolla salteña | (none) | tavily | Regional/obscure NW-Argentine variant; Tavily likely returns generic milanesa or irrelevant; documents v1.1 gap |
| 13 | sanity-miss | __force_miss__ receta inexistente xyz123 | https://invalid.example.localhost.invalid/nonexistent.html | miss_expected | Forced miss — synthetic non-real source URL fails safe_fetch; nonsense query yields no Tavily images → RecipeImageAcquisitionError → StepUnavailableArtifact path exercised |

## Class distribution

| Class | Count | Rows |
|-------|-------|------|
| source-page-hit | 5 | 1, 2, 3, 4, 5 |
| source-page-miss | 3 | 6, 7, 8 |
| query-only | 3 | 9, 10, 11 |
| known-difficult | 1 | 12 |
| sanity-miss | 1 | 13 |
| **Total** | **13** | |

## Notes

- **Branch-fired detection (the harness's heuristic):** if the candidate
  URL's host matches the row's `source_url` host → `source_page`;
  otherwise → `tavily`. If `acquire_recipe_image` raises
  `RecipeImageAcquisitionError` or `SafeFetchError` → `miss` /
  `validation_failed`.
- **Sanity-miss mechanism:** the synthetic recipe name
  `__force_miss__ receta inexistente xyz123` is unlikely to return any
  Tavily images (the leading sentinel token and trailing nonsense suffix
  defeat indexed-content match). The `source_url` (`https://invalid.example.localhost.invalid/...`)
  is on a non-routable TLD; `safe_fetch` will raise on the source-page
  branch and the function will fall through to Tavily, which then misses,
  raising `RecipeImageAcquisitionError`. This exercises the runner's
  `non_fatal_on_failure=True` → `StepUnavailableArtifact` conversion path
  end-to-end.
- **`expected_branch` values:** one of `source_page`, `tavily`, or
  `miss_expected`. The harness records the ACTUAL branch fired alongside
  the expected branch so the operator can quickly spot drift (e.g. a
  source-page-hit row that fell through to Tavily because the site
  removed JSON-LD).
- **Reuse from Phase 23:** rows 1-5 reuse URLs from `23-EVAL-SET.md`
  rows 1-5 — those were verified to have `.image()` data during Phase 23
  exploration (well-supported sites with JSON-LD images).
- **`source_url` literal `(none)`:** the harness interprets `(none)` (or
  any non-URL cell) as `source_url=None`. Query-only and known-difficult
  rows use `(none)` to force the Tavily-only branch.
- **Eval operator gate (24-09):** stamps `verdict: pass` only if
  (a) ≥ 60% of `tavily`-branch rows have `image looks right? = Y` per
  Pitfall 8 / D-11, (b) all `sanity-miss` rows result in a miss /
  unavailable, (c) no `SafeFetchError` on legitimate URLs. Falling below
  60% triggers the v1.2 vision-LLM escalation per D-11.
