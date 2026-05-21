---
verdict: pending
backend: openai
model: gpt-4.1-mini
date: 2026-05-21
operator: solanoe
eval_set_version: 1
---

# Phase 22 Multi-Recipe Eval Results — openai

**Per D-04: OpenAI is the MERGE GATE. ≥ 95% count accuracy required to PASS. ≥ 90% name accuracy on multi-recipe rows required to PASS.**

## Aggregate

- Total utterances: 30
- Count-correct: 27 / 30 (90.0%)
- Name-correct (multi-recipe rows): 21 / 21 (100.0%)
- Per-class breakdown:
  - `1 single-recipe`: count 3/3, name 3/3
  - `10 url-deflection`: count 0/3, name 3/3
  - `2 multi N=2`: count 3/3, name 3/3
  - `3 multi N=3`: count 3/3, name 3/3
  - `4 multi N=4-5`: count 3/3, name 3/3
  - `5 over-cap`: count 3/3, name 3/3
  - `6 compound`: count 3/3, name 3/3
  - `7 sauce-on-recipe`: count 3/3, name 3/3
  - `8 sanity`: count 3/3, name 3/3
  - `9 ambiguous`: count 3/3, name 3/3

## Per-utterance results

OK? gates on count + name per D-04. Trace cell links to LangWatch when `LANGWATCH_UI_BASE_URL` is set; otherwise renders the bare trace_id.

| # | Utterance | Class | Expected N | Observed N | Observed values | OK? | LangWatch trace |
|---|-----------|-------|------------|------------|-----------------|-----|------------------|
| 1 | agregá lentejas | 1 single-recipe | 1 | 1 | lentejas | OK | e3b088cfd5bc4e81059be8a952e27c78 |
| 2 | quiero hacer milanesas | 1 single-recipe | 1 | 1 | milanesas | OK | 01daf2c68ba7eb4cd5d7eed8b01bc9a6 |
| 3 | guardame la receta del puré de papas | 1 single-recipe | 1 | 1 | puré de papas | OK | 1e3454960b3c9f9abe260921f54c6da4 |
| 4 | agregá canelones y pollo al horno | 2 multi N=2 | 2 | 2 | canelones, pollo al horno | OK | df013cad5739419052909e29e0b2cc85 |
| 5 | guardá lentejas y arroz con verduras | 2 multi N=2 | 2 | 2 | arroz con verduras, lentejas | OK | 268089afda4127a182a2b629d44d74df |
| 6 | querría guardar empanadas de carne y tarta de zapallitos | 2 multi N=2 | 2 | 2 | empanadas de carne, tarta de zapallitos | OK | 6f4a1c860355275c25bf89944fd85f00 |
| 7 | agregá canelones, pollo al horno y arroz pilaf | 3 multi N=3 | 3 | 3 | pollo al horno, canelones, arroz pilaf | OK | 86aa272ddec03310f26cdef894ea1bb2 |
| 8 | guardá milanesas, puré y ensalada mixta | 3 multi N=3 | 3 | 3 | milanesas, puré, ensalada mixta | OK | 6d198c679b1db8df0299341e54392ba5 |
| 9 | agregame fideos con tuco, salmón al horno y postre de chocolate | 3 multi N=3 | 3 | 3 | fideos con tuco, salmón al horno, postre de chocolate | OK | 306443b5def773fbd4362f066a0865d8 |
| 10 | agregá canelones, pollo, arroz y lentejas | 4 multi N=4-5 | 4 | 4 | pollo, canelones, arroz, lentejas | OK | 1c238e05f6f66130eedafdf3a0ca8826 |
| 11 | guardá milanesas, puré, ensalada, postre y pan casero | 4 multi N=4-5 | 5 | 5 | milanesas, ensalada, postre, puré, pan casero | OK | 841c9e762ae49901379ec439063f9e57 |
| 12 | agregame empanadas, tarta, sopa, fideos y flan | 4 multi N=4-5 | 5 | 5 | empanadas, tarta, sopa, fideos, flan | OK | be3e01f868f41d793d57f7bfe208a1ed |
| 13 | agregá canelones, pollo, arroz, lentejas, milanesas, salmón, ravioles | 5 over-cap | 0 | 0 |  | OK | 6cb945af1556bb73dcc9f639963559c0 |
| 14 | guardá estas: pizza, empanadas, tarta, milanesas, sopa, postre, pan, fideos | 5 over-cap | 0 | 0 |  | OK | 4be37b2dbc9f6ca19310d4c5f38cb719 |
| 15 | agregá rápido: lentejas, garbanzos, arroz, pollo, papas, zanahorias, calabaza | 5 over-cap | 0 | 0 |  | OK | e1790a6ec7c1a6cf0bf003114c1a3400 |
| 16 | agregá pollo al horno con papas | 6 compound | 1 | 1 | pollo al horno con papas | OK | 7afeeb3a13f1d02aa48ea4d138977c2b |
| 17 | guardá milanesas con puré | 6 compound | 1 | 1 | milanesas con puré | OK | 4d053fd4b0faa6c24a6b8e8d4fd54d31 |
| 18 | agregame pescado a la plancha con verduras grilladas | 6 compound | 1 | 1 | pescado a la plancha con verduras grilladas | OK | 5c11eaa4b8ca786d4fe836aa404a7916 |
| 19 | agregá canelones con salsa blanca y boloñesa | 7 sauce-on-recipe | 1 | 1 | canelones con salsa blanca y boloñesa | OK | 5dd43de9792d82794dfe400c694b57de |
| 20 | guardá ñoquis con salsa rosa y queso rallado | 7 sauce-on-recipe | 1 | 1 | ñoquis con salsa rosa y queso rallado | OK | 3504591ec98a4c59371b1c93e319b8a3 |
| 21 | agregame ravioles con manteca y salvia | 7 sauce-on-recipe | 1 | 1 | ravioles con manteca y salvia | OK | 5343d78ea4d611ea83c6315e1afd7993 |
| 22 | salt and pepper chicken | 8 sanity | 1 | 1 | salt and pepper chicken | OK | 341bbd7ab554a83162d3ad5f4a996b82 |
| 23 | papa rellena | 8 sanity | 1 | 1 | papa rellena | OK | 288620260002ca8eed45913878501606 |
| 24 | pollo a la portuguesa | 8 sanity | 1 | 1 | pollo a la portuguesa | OK | dc46a8182b9fe9e451cae2babc64e6ea |
| 25 | hola | 9 ambiguous | 0 | 0 |  | OK | a20b240b40d41578a4618e18527cb6ca |
| 26 | agregá algo rico | 9 ambiguous | 0 | 0 |  | OK | 3ec0f9b0f455bb8c676bb84f061a78c0 |
| 27 | qué hago de cena | 9 ambiguous | 0 | 0 |  | OK | ff08710a98923f262ae86008c7ba4f83 |
| 28 | agregá esta receta: https://example.com/canelones | 10 url-deflection | 0 | 1 |  | FAIL | fe17b56032025fad1ebe6ff6bda0eb8a |
| 29 | guardame https://cookpad.com/recetas/123 plis | 10 url-deflection | 0 | 1 |  | FAIL | 61abda60937da1ecff9c47732c80c08c |
| 30 | https://recipes.test.example/x — agregala | 10 url-deflection | 0 | 1 |  | FAIL | bbb0300a694b951edb8c2483f465c059 |

## Notes

[Operator narrative — patterns, failures, recommendations.]

## Go / No-Go

Required for PASS: count ≥ 95% AND name ≥ 90% on multi-recipe rows.
If catastrophic (< 50% count): `verdict: pivot` (defensive code cap per Deferred Ideas).

verdict: pass | fail | pivot
