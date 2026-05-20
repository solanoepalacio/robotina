---
verdict: pending
backend: openai
model: <auto-filled by harness>
date: <YYYY-MM-DD — auto-filled by harness>
operator: <auto-filled by harness>
eval_set_version: 1
---

# Phase 23 URL Ingestion Eval Results — openai

**SKELETON — operator runs the harness to populate this file:**

```bash
uv run experiments.gather_from_url --backend openai --eval-set .planning/phases/23-url-ingestion-topic-2/23-EVAL-SET.md
```

The harness overwrites this file with real per-URL results and the aggregate. Until then, this skeleton documents the expected shape and lists the 21 URLs the operator should expect to see scored.

**Per D-12: OpenAI staging is the MERGE GATE.** ≥ 85% URL-level pass required (≥ 17/21 URLs pass per D-11).

## Aggregate

- Total URLs: 21
- URL-level pass: `<X> / 21` (`<X.X>%`)
- Per-class breakdown (filled by harness):
  - `1 well-supported`: `<X>/4`
  - `2 wild_mode json-ld`: `<X>/4`
  - `3 llm fallback`: `<X>/5`
  - `4 locale units`: `<X>/3`
  - `5 known difficult`: `<X>/2`
  - `6 sanity non-recipe`: `<X>/3`

## Per-URL results

| # | url | class | populated/expected | passed? | LangWatch trace |
|---|-----|-------|--------------------|---------|------------------|
| 1 | https://www.paulinacocina.net/receta-de-tarta-de-manzana/47322 | 1 well-supported |  /8 |  |  |
| 2 | https://www.directoalpaladar.com/postres/receta-de-flan-de-huevo-tradicional | 1 well-supported |  /8 |  |  |
| 3 | https://www.cocinatis.com/recetas/postres/tarta-de-santiago/ | 1 well-supported |  /8 |  |  |
| 4 | https://www.recetasgratis.net/receta-de-empanadas-argentinas-caseras-50125.html | 1 well-supported |  /8 |  |  |
| 5 | https://webosfritos.es/2009/04/bizcocho-de-yogur/ | 2 wild_mode json-ld |  /8 |  |  |
| 6 | https://www.recetasdesenorsenor.com/2014/02/croquetas-de-jamon-receta-tradicional.html | 2 wild_mode json-ld |  /8 |  |  |
| 7 | https://elcomidista.elpais.com/elcomidista/2017/11/14/receta/1510669687_148812.html | 2 wild_mode json-ld |  /8 |  |  |
| 8 | https://www.midiariodecocina.com/gnocchis-caseros-de-papa/ | 2 wild_mode json-ld |  /8 |  |  |
| 9 | https://www.cocinerosargentinos.com/recetas/12345-pastel-de-papa-clasico | 3 llm fallback |  /8 |  |  |
| 10 | https://www.recetinas.com/2015/05/lentejas-estofadas.html | 3 llm fallback |  /8 |  |  |
| 11 | https://lacocinadefrabisa.lavozdegalicia.es/empanada-gallega-de-atun/ | 3 llm fallback |  /8 |  |  |
| 12 | https://comerconpoco.com/receta-arroz-tres-delicias/ | 3 llm fallback |  /8 |  |  |
| 13 | https://www.cucinare.tv/recetas/canelones-de-ricota-y-espinaca | 3 llm fallback |  /8 |  |  |
| 14 | https://www.paulinacocina.net/receta-de-alfajores-de-maicena/30982 | 4 locale units |  /8 |  |  |
| 15 | https://www.cocinerosargentinos.com/recetas/12346-locro-criollo-tradicional | 4 locale units |  /8 |  |  |
| 16 | https://www.recetasargentinas.net/dulce-de-leche-casero/ | 4 locale units |  /8 |  |  |
| 17 | https://www.canalcocina.es/receta/paella-valenciana-tradicional | 5 known difficult |  /8 |  |  |
| 18 | https://www.bonviveur.es/recetas/pulpo-a-la-gallega-receta-tradicional | 5 known difficult |  /8 |  |  |
| 19 | https://www.paulinacocina.net/ | 6 sanity non-recipe |  /4 |  |  |
| 20 | https://www.directoalpaladar.com/categoria/postres | 6 sanity non-recipe |  /4 |  |  |
| 21 | https://www.recetasgratis.net/quienes-somos | 6 sanity non-recipe |  /4 |  |  |

## Notes

[Operator narrative — patterns, failures, recommendations.]

## Go / No-Go

Required for PASS (D-12): ≥ 17/21 URLs pass per D-11 field-presence rule.

verdict: pass | fail | needs-revision
