---
version: 1
total_urls: 21
created: 2026-05-20
coverage_classes: 6
class_distribution: {1: 4, 2: 4, 3: 5, 4: 3, 5: 2, 6: 3}
---

# Phase 23 URL Ingestion Eval Set

Canonical 21-URL Spanish-recipe-blog eval set for the `gather-from-url`
agent (URL-06). The harness in `experiments/gather_from_url.py` runs each
URL through the production agent (V001) against the configured LLM
backend and scores the emitted `RecipeData` against the 8 expected
fields per D-11.

**Scoring rule (D-11):** Per-URL pass = ≥6/8 expected-populated fields
populated AND non-empty. Aggregate pass = ≥17/21 URLs pass (≈ 85%
URL-level success — operationalizes URL-06's "≥ 85% field-level
success at v1.1 ship").

**Backends (D-12):**
- **OpenAI staging — merge gate:** ≥ 85% URL-level pass.
- **Ollama dev — informational only.**
- **Anthropic — optional.**

The 8 expected fields scored per row (D-11): `name`, `description`,
`ingredients` (≥ `expected_ingredients_min` items), `steps` (≥
`expected_steps_min` items), `servings_qty`, one of {`prep_time`,
`cook_time`, `total_time`}, `source_url`, `gathered_sources` (legacy,
optional — counts as populated if any value present).

## Coverage classes

The 6 coverage classes from CONTEXT D-10, each represented by ≥ 1 row
in the `## URLs` table below:

1. **Well-supported by `recipe-scrapers`** — major Spanish-language
   sites with first-class site adapters. Expectation: scraper returns
   a Pydantic-valid `RecipeData` with ≥ 2 ingredients; the agent's
   pass-through branch fires; near-full field population expected.
2. **`wild_mode=True` schema.org/Recipe territory** — long-tail
   Spanish blogs that ship valid schema.org JSON-LD but no per-site
   adapter. `wild_mode=True` extraction; same pass-through branch.
3. **LLM-fallback territory** — Spanish blogs without (or with
   inconsistent) schema.org markup; `recipe-scrapers` fails or
   returns insufficient data; the agent extracts from cleaned
   `trafilatura` HTML text. Looser field coverage tolerated.
4. **Locale-specific units** — Argentine/Uruguayan/Mexican blogs
   with regional measure phrasing ("una taza", "1/2 cucharadita",
   "rinde 8 porciones"). Tests that the LLM normalizes units into
   `RecipeIngredient` without dropping fields.
5. **Known-difficult site** — JS-gated / paywalled / heavy-gallery
   sites where the sync fetcher cannot retrieve clean content.
   Expected: partial extraction; the row failing per D-11 is the
   data point, not a missing URL.
6. **Sanity non-recipe** — site homepages / category indexes / about
   pages that are clearly NOT recipes. Per V001 prompt fallback rule:
   the agent emits a minimal `RecipeData` with `name` set to a brief
   page description; most other fields empty.

## URLs

| # | url | coverage_class | expected_name | expected_ingredients_min | expected_steps_min | expected_servings_qty | expected_total_time | notes |
|---|-----|----------------|---------------|--------------------------|--------------------|-----------------------|---------------------|-------|
| 1 | https://www.paulinacocina.net/receta-de-tarta-de-manzana/47322 | 1 well-supported | tarta de manzana | 5 | 4 | 6 | 60 | Paulina Cocina — recipe-scrapers ships an adapter; baseline pass-through |
| 2 | https://www.directoalpaladar.com/postres/receta-de-flan-de-huevo-tradicional | 1 well-supported | flan de huevo | 3 | 3 | 6 | 60 | Directo al Paladar — major ES food blog; full schema.org markup |
| 3 | https://www.cocinatis.com/recetas/postres/tarta-de-santiago/ | 1 well-supported | tarta de santiago | 4 | 3 | 8 | 45 | Cocinatis — Atresmedia food vertical; well-marked JSON-LD |
| 4 | https://www.recetasgratis.net/receta-de-empanadas-argentinas-caseras-50125.html | 1 well-supported | empanadas argentinas | 6 | 5 | 12 | 90 | Recetas Gratis — large multilingual recipe site with strong schema.org |
| 5 | https://webosfritos.es/2009/04/bizcocho-de-yogur/ | 2 wild_mode json-ld | bizcocho de yogur | 5 | 3 | 8 | 60 | Webos Fritos — Spanish blog with schema.org/Recipe JSON-LD, no per-site adapter |
| 6 | https://www.recetasdesenorsenor.com/2014/02/croquetas-de-jamon-receta-tradicional.html | 2 wild_mode json-ld | croquetas de jamón | 6 | 5 | 4 | 45 | Recetas del Señor Señor — Spanish family blog with JSON-LD |
| 7 | https://elcomidista.elpais.com/elcomidista/2017/11/14/receta/1510669687_148812.html | 2 wild_mode json-ld | tortilla de patatas | 4 | 4 | 4 | 40 | El Comidista (El País) — major newspaper food section; JSON-LD present |
| 8 | https://www.midiariodecocina.com/gnocchis-caseros-de-papa/ | 2 wild_mode json-ld | ñoquis de papa | 4 | 4 | 4 | 60 | Mi Diario de Cocina — Chilean Spanish blog with schema.org |
| 9 | https://www.cocinerosargentinos.com/recetas/12345-pastel-de-papa-clasico | 3 llm fallback | pastel de papa | 5 | 4 | 6 | 75 | Cocineros Argentinos — large AR community blog; schema.org coverage spotty |
| 10 | https://www.recetinas.com/2015/05/lentejas-estofadas.html | 3 llm fallback | lentejas estofadas | 6 | 5 | 6 | 60 | Recetinas — Spanish home-cooking blog; inconsistent structured data |
| 11 | https://lacocinadefrabisa.lavozdegalicia.es/empanada-gallega-de-atun/ | 3 llm fallback | empanada gallega de atún | 7 | 5 | 6 | 90 | La Cocina de Frabisa (La Voz de Galicia) — regional newspaper blog |
| 12 | https://comerconpoco.com/receta-arroz-tres-delicias/ | 3 llm fallback | arroz tres delicias | 6 | 5 | 4 | 30 | Comer con Poco — budget cooking blog; recipe in prose paragraphs |
| 13 | https://www.cucinare.tv/recetas/canelones-de-ricota-y-espinaca | 3 llm fallback | canelones de ricota y espinaca | 7 | 6 | 6 | 90 | Cucinare (Mauricio Asta) — AR cooking show blog; weak structured data |
| 14 | https://www.paulinacocina.net/receta-de-alfajores-de-maicena/30982 | 4 locale units | alfajores de maicena | 5 | 4 | 24 | 45 | AR Spanish — "una taza de almidón", "rinde 24 unidades" — locale yield phrasing |
| 15 | https://www.cocinerosargentinos.com/recetas/12346-locro-criollo-tradicional | 4 locale units | locro criollo | 8 | 5 | 8 | 240 | AR Spanish — long simmer recipe, "rinde 8 porciones", weight units in kg |
| 16 | https://www.recetasargentinas.net/dulce-de-leche-casero/ | 4 locale units | dulce de leche | 3 | 4 | 6 | 120 | AR Spanish — "1 lata de leche condensada", regional dessert |
| 17 | https://www.canalcocina.es/receta/paella-valenciana-tradicional | 5 known difficult | paella valenciana | 8 | 6 | 6 | 60 | Canal Cocina — JS-rendered SPA; sync fetcher gets shell only; expected partial extraction |
| 18 | https://www.bonviveur.es/recetas/pulpo-a-la-gallega-receta-tradicional | 5 known difficult | pulpo a la gallega | 5 | 4 | 4 | 45 | Bon Viveur — heavy gallery + carousel layout; recipe text scattered; expected partial fields |
| 19 | https://www.paulinacocina.net/ | 6 sanity non-recipe | Paulina Cocina | 0 | 0 |  |  | Site homepage — V001 minimal-RecipeData fallback; expect name only |
| 20 | https://www.directoalpaladar.com/categoria/postres | 6 sanity non-recipe | postres | 0 | 0 |  |  | Category index — many recipe links, no single recipe; expect name only |
| 21 | https://www.recetasgratis.net/quienes-somos | 6 sanity non-recipe | Recetas Gratis | 0 | 0 |  |  | About page — clearly non-recipe; expect minimal RecipeData per V001 |

## Scoring rule

Per CONTEXT D-11 verbatim:

> Per-URL pass = ≥ 6/8 expected-populated fields populated AND non-empty.
> Aggregate pass = ≥ 17/21 URLs pass.

The 8 fields scored per row: `name`, `description`, `ingredients`
(populated when `len(ingredients) >= expected_ingredients_min`),
`steps` (populated when `len(steps) >= expected_steps_min`),
`servings_qty`, any one of {`prep_time`, `cook_time`, `total_time`},
`source_url`, `gathered_sources`.

For Class 6 (sanity non-recipe) rows the `expected_ingredients_min` /
`expected_steps_min` are 0 and the time / servings columns are empty —
those four fields are NOT counted as "expected-populated", so the
per-URL pass threshold for sanity rows becomes ≥ 3/4 of the remaining
fields (`name`, `description`, `source_url`, `gathered_sources`).

## Class distribution

| Class | Count | Rows |
|-------|-------|------|
| 1 well-supported (recipe-scrapers adapter) | 4 | 1, 2, 3, 4 |
| 2 wild_mode JSON-LD | 4 | 5, 6, 7, 8 |
| 3 LLM-fallback | 5 | 9, 10, 11, 12, 13 |
| 4 locale-specific units | 3 | 14, 15, 16 |
| 5 known-difficult | 2 | 17, 18 |
| 6 sanity non-recipe | 3 | 19, 20, 21 |
| **Total** | **21** | |
