---
version: 1
created: 2026-05-20
coverage_classes: 10
utterance_count: 30
---

# Phase 22 Multi-Recipe Eval Set

Empirical acceptance evidence for BATCH-01..05. The harness in
`experiments/robotina/multi_recipe_eval.py` runs each utterance below
through the production `handle-incoming-message` agent (V006) against the
configured LLM backend and compares observed tool-call counts + recipe
values against the expected columns. OpenAI staging is the merge gate
per D-04 (≥ 95% count accuracy, ≥ 90% name accuracy on multi-recipe rows).

## Coverage Classes

Each class has at least 3 utterances. All 10 classes from CONTEXT D-03 are
covered (URL-mention deflection replaces the deferred "cross-source" class —
URL handling is Phase 23 scope and V006 must respond "no manejo enlaces"
+ terminate without starting any workflow).

1. Single-recipe (N=1)
2. Multi-recipe N=2
3. Multi-recipe N=3
4. Multi-recipe N=4 or 5
5. Over-cap N>5 — expected 0 workflows + `respond(ask-to-split)` + `terminate` per D-01
6. Compound dish (ambiguous 1-vs-2) — prefer-fewer = 1 workflow per D-11
7. Sauce-on-recipe (1 not 2) per D-12
8. Sanity / must-NOT-split (multi-word recipe names, English noun phrases)
9. Ambiguous non-recipe — clarify via `respond()` per D-10
10. URL-mention deflection — URL handling deferred to Phase 23; V006 must respond "no manejo enlaces" + terminate

## Utterances

The `Expected respond()` column holds a short substring tag (e.g. `ack`,
`ask-to-split`, `clarify-what-recipe`, `no manejo enlaces`). The harness
treats it as a case-insensitive substring assertion against the recorded
`respond(text=...)` payload. `Expected recipe value(s)` is a comma-separated
list of recipe strings the harness expects to see in `start-workflow` `input.value`
arguments; empty when `Expected N` is 0.

| # | Utterance (Spanish) | Class | Expected N start-workflow | Expected recipe value(s) | Expected respond() | Notes |
|---|----------------------|-------|---------------------------|--------------------------|--------------------|-------|
| 1 | agregá lentejas | 1 single-recipe | 1 | lentejas | ack | baseline single |
| 2 | quiero hacer milanesas | 1 single-recipe | 1 | milanesas | ack | intent verb variation |
| 3 | guardame la receta del puré de papas | 1 single-recipe | 1 | puré de papas | ack | multi-word name |
| 4 | agregá canelones y pollo al horno | 2 multi N=2 | 2 | canelones, pollo al horno | ack-all | conjunction `y` between recipes |
| 5 | guardá lentejas y arroz con verduras | 2 multi N=2 | 2 | lentejas, arroz con verduras | ack-all | second recipe is multi-word |
| 6 | querría guardar empanadas de carne y tarta de zapallitos | 2 multi N=2 | 2 | empanadas de carne, tarta de zapallitos | ack-all | two multi-word recipes |
| 7 | agregá canelones, pollo al horno y arroz pilaf | 3 multi N=3 | 3 | canelones, pollo al horno, arroz pilaf | ack-all | comma list + final `y` |
| 8 | guardá milanesas, puré y ensalada mixta | 3 multi N=3 | 3 | milanesas, puré, ensalada mixta | ack-all | mixed length names |
| 9 | agregame fideos con tuco, salmón al horno y postre de chocolate | 3 multi N=3 | 3 | fideos con tuco, salmón al horno, postre de chocolate | ack-all | three compound names |
| 10 | agregá canelones, pollo, arroz y lentejas | 4 multi N=4-5 | 4 | canelones, pollo, arroz, lentejas | ack-all | at-cap N=4 |
| 11 | guardá milanesas, puré, ensalada, postre y pan casero | 4 multi N=4-5 | 5 | milanesas, puré, ensalada, postre, pan casero | ack-all | exactly at cap N=5 |
| 12 | agregame empanadas, tarta, sopa, fideos y flan | 4 multi N=4-5 | 5 | empanadas, tarta, sopa, fideos, flan | ack-all | exactly at cap N=5 |
| 13 | agregá canelones, pollo, arroz, lentejas, milanesas, salmón, ravioles | 5 over-cap | 0 |  | ask-to-split | N=7, must NOT start any workflow per D-01 |
| 14 | guardá estas: pizza, empanadas, tarta, milanesas, sopa, postre, pan, fideos | 5 over-cap | 0 |  | ask-to-split | N=8, must NOT start any workflow |
| 15 | agregá rápido: lentejas, garbanzos, arroz, pollo, papas, zanahorias, calabaza | 5 over-cap | 0 |  | ask-to-split | N=7, ingredients-vs-recipes ambiguity is fine — still over-cap |
| 16 | agregá pollo al horno con papas | 6 compound | 1 | pollo al horno con papas | ack | prefer-fewer per D-11 |
| 17 | guardá milanesas con puré | 6 compound | 1 | milanesas con puré | ack | classic main+side compound |
| 18 | agregame pescado a la plancha con verduras grilladas | 6 compound | 1 | pescado a la plancha con verduras grilladas | ack | longer compound |
| 19 | agregá canelones con salsa blanca y boloñesa | 7 sauce-on-recipe | 1 | canelones con salsa blanca y boloñesa | ack | the `y` inside noun phrase trap — D-12 |
| 20 | guardá ñoquis con salsa rosa y queso rallado | 7 sauce-on-recipe | 1 | ñoquis con salsa rosa y queso rallado | ack | sauce + topping — still 1 |
| 21 | agregame ravioles con manteca y salvia | 7 sauce-on-recipe | 1 | ravioles con manteca y salvia | ack | classic Italian sauce description |
| 22 | salt and pepper chicken | 8 sanity | 1 | salt and pepper chicken | ack | English noun-phrase — small models notoriously split this |
| 23 | papa rellena | 8 sanity | 1 | papa rellena | ack | two-word LatAm recipe |
| 24 | pollo a la portuguesa | 8 sanity | 1 | pollo a la portuguesa | ack | three-word recipe with `a la` |
| 25 | hola | 9 ambiguous | 0 |  | clarify-what-recipe | greeting, no recipe at all |
| 26 | agregá algo rico | 9 ambiguous | 0 |  | clarify | no specific recipe named |
| 27 | qué hago de cena | 9 ambiguous | 0 |  | clarify | asking for suggestion, not adding |
| 28 | agregá esta receta: https://example.com/canelones | 10 url-deflection | 0 |  | no manejo enlaces | URL in message — Phase 23 scope |
| 29 | guardame https://cookpad.com/recetas/123 plis | 10 url-deflection | 0 |  | no manejo enlaces | URL is the whole content |
| 30 | https://recipes.test.example/x — agregala | 10 url-deflection | 0 |  | no manejo enlaces | URL with imperative tail |
