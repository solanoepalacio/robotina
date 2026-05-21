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

- Total utterances: 27
- Count-correct: 26 / 27 (96.3%)
- Name-correct (multi-recipe rows): 20 / 21 (95.2%)
- Per-class breakdown:
  - `1 single-recipe`: count 3/3, name 3/3
  - `2 multi N=2`: count 3/3, name 3/3
  - `3 multi N=3`: count 3/3, name 3/3
  - `4 multi N=4-5`: count 2/3, name 2/3
  - `5 over-cap`: count 3/3, name 3/3
  - `6 compound`: count 3/3, name 3/3
  - `7 sauce-on-recipe`: count 3/3, name 3/3
  - `8 sanity`: count 3/3, name 3/3
  - `9 ambiguous`: count 3/3, name 3/3

## Per-utterance results

OK? gates on count + name per D-04. Trace cell links to LangWatch when `LANGWATCH_UI_BASE_URL` is set; otherwise renders the bare trace_id.

| # | Utterance | Class | Expected N | Observed N | Observed values | OK? | LangWatch trace |
|---|-----------|-------|------------|------------|-----------------|-----|------------------|
| 1 | agregá lentejas | 1 single-recipe | 1 | 1 | lentejas | OK | 754e8353b92de877e1ac80371c9ab69a |
| 2 | quiero hacer milanesas | 1 single-recipe | 1 | 1 | milanesas | OK | a8709b3f0c146b355d04768d33222cc0 |
| 3 | guardame la receta del puré de papas | 1 single-recipe | 1 | 1 | puré de papas | OK | e30dd9a290cd66420b9f6865ccf106c0 |
| 4 | agregá canelones y pollo al horno | 2 multi N=2 | 2 | 2 | canelones, pollo al horno | OK | 6d1130e6d01db1c228960667fb2f374c |
| 5 | guardá lentejas y arroz con verduras | 2 multi N=2 | 2 | 2 | lentejas, arroz con verduras | OK | a84a2069db9c7be8567672d5d8d695c4 |
| 6 | querría guardar empanadas de carne y tarta de zapallitos | 2 multi N=2 | 2 | 2 | tarta de zapallitos, empanadas de carne | OK | d3b4c626d43cbb2d4cc080faf548feed |
| 7 | agregá canelones, pollo al horno y arroz pilaf | 3 multi N=3 | 3 | 3 | canelones, pollo al horno, arroz pilaf | OK | 35c1829558b5e3ac4ee5586be3fc6dec |
| 8 | guardá milanesas, puré y ensalada mixta | 3 multi N=3 | 3 | 3 | milanesas, puré, ensalada mixta | OK | d1566d1f49eedd40a6ad8cd59dc1290c |
| 9 | agregame fideos con tuco, salmón al horno y postre de chocolate | 3 multi N=3 | 3 | 3 | fideos con tuco, salmón al horno, postre de chocolate | OK | fa29a397eead9f0359b8cb8c61422544 |
| 10 | agregá canelones, pollo, arroz y lentejas | 4 multi N=4-5 | 4 | 4 | canelones, pollo, arroz, lentejas | OK | 19b91b20c5c4a3f7de63508f2f8e944c |
| 11 | guardá milanesas, puré, ensalada, postre y pan casero | 4 multi N=4-5 | 5 | 0 |  | FAIL | 8946dad23c7b8f45b79297d3bb941df4 |
| 12 | agregame empanadas, tarta, sopa, fideos y flan | 4 multi N=4-5 | 5 | 5 | empanadas, tarta, sopa, fideos, flan | OK | 5e931b1cf6f83f26e27da662547dfcc6 |
| 13 | agregá canelones, pollo, arroz, lentejas, milanesas, salmón, ravioles | 5 over-cap | 0 | 0 |  | OK | dcba8ea9f6498a50b0ec0f9bf432a69b |
| 14 | guardá estas: pizza, empanadas, tarta, milanesas, sopa, postre, pan, fideos | 5 over-cap | 0 | 0 |  | OK | a14789fee9d29b2033d660843e1a3b88 |
| 15 | agregá rápido: lentejas, garbanzos, arroz, pollo, papas, zanahorias, calabaza | 5 over-cap | 0 | 0 |  | OK | 4454ea338190085c27c083f7445072cc |
| 16 | agregá pollo al horno con papas | 6 compound | 1 | 1 | pollo al horno con papas | OK | 83d175493e301d5e631d5f6dabf79943 |
| 17 | guardá milanesas con puré | 6 compound | 1 | 1 | milanesas con puré | OK | 576f7ce8ee4fd13534341fbd46f6be46 |
| 18 | agregame pescado a la plancha con verduras grilladas | 6 compound | 1 | 1 | pescado a la plancha con verduras grilladas | OK | f6b90c3735aea70c9071002d1c7fee83 |
| 19 | agregá canelones con salsa blanca y boloñesa | 7 sauce-on-recipe | 1 | 1 | canelones con salsa blanca y boloñesa | OK | 05e259f1d3e02a683af7b0f3919c7a19 |
| 20 | guardá ñoquis con salsa rosa y queso rallado | 7 sauce-on-recipe | 1 | 1 | ñoquis con salsa rosa y queso rallado | OK | 9c7d6b5838a901af192e0c258457c596 |
| 21 | agregame ravioles con manteca y salvia | 7 sauce-on-recipe | 1 | 1 | ravioles con manteca y salvia | OK | 7ffb503dff9dfe66f836e297007c543c |
| 22 | salt and pepper chicken | 8 sanity | 1 | 1 | salt and pepper chicken | OK | 6e8c10a159f71a3b202a21cc07da1e91 |
| 23 | papa rellena | 8 sanity | 1 | 1 | papa rellena | OK | 7f7671b7436db6395b2d8e28ad3b455d |
| 24 | pollo a la portuguesa | 8 sanity | 1 | 1 | pollo a la portuguesa | OK | b2428d03e7f84ac798d1094feba674bd |
| 25 | hola | 9 ambiguous | 0 | 0 |  | OK | 1a758c638e9959e75c143c5ce6f7c009 |
| 26 | agregá algo rico | 9 ambiguous | 0 | 0 |  | OK | a88553ed1c1450103ddc6cfc21765c7b |
| 27 | qué hago de cena | 9 ambiguous | 0 | 0 |  | OK | 83f77025a0b8da2ab09f2d8fe6ba63fc |

## Notes

[Operator narrative — patterns, failures, recommendations.]

## Go / No-Go

Required for PASS: count ≥ 95% AND name ≥ 90% on multi-recipe rows.
If catastrophic (< 50% count): `verdict: pivot` (defensive code cap per Deferred Ideas).

verdict: pass | fail | pivot
