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
- Count-correct: 26 / 30 (86.7%)
- Name-correct (multi-recipe rows): 20 / 21 (95.2%)
- Per-class breakdown:
  - `1 single-recipe`: count 3/3, name 3/3
  - `10 url-deflection`: count 0/3, name 3/3
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
| 1 | agregá lentejas | 1 single-recipe | 1 | 1 | lentejas | OK | 9a1e31c1aae405dd53b51c749a54e1eb |
| 2 | quiero hacer milanesas | 1 single-recipe | 1 | 1 | milanesas | OK | f32e92618ed254842acaedf5ec05e3ca |
| 3 | guardame la receta del puré de papas | 1 single-recipe | 1 | 1 | puré de papas | OK | 8c6643b30b8f85a8f6ecf2c4c447406c |
| 4 | agregá canelones y pollo al horno | 2 multi N=2 | 2 | 2 | canelones, pollo al horno | OK | aa3f770d40301f3dd81f3ebfc0df2931 |
| 5 | guardá lentejas y arroz con verduras | 2 multi N=2 | 2 | 2 | lentejas, arroz con verduras | OK | d8efb4437673cf981fed5af1ff6fdc24 |
| 6 | querría guardar empanadas de carne y tarta de zapallitos | 2 multi N=2 | 2 | 2 | empanadas de carne, tarta de zapallitos | OK | 0140dfd13d78c489f67ea32af2168392 |
| 7 | agregá canelones, pollo al horno y arroz pilaf | 3 multi N=3 | 3 | 3 | canelones, pollo al horno, arroz pilaf | OK | 991235cbc8e170d9c395f3aaa2ab4c1c |
| 8 | guardá milanesas, puré y ensalada mixta | 3 multi N=3 | 3 | 3 | puré, milanesas, ensalada mixta | OK | dab01449c39b261f8ba3de61d8434e61 |
| 9 | agregame fideos con tuco, salmón al horno y postre de chocolate | 3 multi N=3 | 3 | 3 | fideos con tuco, salmón al horno, postre de chocolate | OK | 145ef04607f432316c01e346b1500c45 |
| 10 | agregá canelones, pollo, arroz y lentejas | 4 multi N=4-5 | 4 | 4 | canelones, pollo, arroz, lentejas | OK | 2a1a60d37d8e96b7ea69500922ca0884 |
| 11 | guardá milanesas, puré, ensalada, postre y pan casero | 4 multi N=4-5 | 5 | 0 |  | FAIL | 017ce5f88cfc92b3b9117c78e275c05a |
| 12 | agregame empanadas, tarta, sopa, fideos y flan | 4 multi N=4-5 | 5 | 5 | tarta, empanadas, sopa, fideos, flan | OK | adc31cefaf9b75dc4e717faa4f361b20 |
| 13 | agregá canelones, pollo, arroz, lentejas, milanesas, salmón, ravioles | 5 over-cap | 0 | 0 |  | OK | 6f5456619486e1b68af77f880cfb165d |
| 14 | guardá estas: pizza, empanadas, tarta, milanesas, sopa, postre, pan, fideos | 5 over-cap | 0 | 0 |  | OK | 402d0f30bee2217e4dae319eb579e008 |
| 15 | agregá rápido: lentejas, garbanzos, arroz, pollo, papas, zanahorias, calabaza | 5 over-cap | 0 | 0 |  | OK | cdacd066be6aa72794f8a0383161d6f6 |
| 16 | agregá pollo al horno con papas | 6 compound | 1 | 1 | pollo al horno con papas | OK | e5fdc5ea79543a01c972dfffc586c724 |
| 17 | guardá milanesas con puré | 6 compound | 1 | 1 | milanesas con puré | OK | 6d0fb7021abdae679df62227d216d803 |
| 18 | agregame pescado a la plancha con verduras grilladas | 6 compound | 1 | 1 | pescado a la plancha con verduras grilladas | OK | 2e333874627f86eaca4ffdd555016f68 |
| 19 | agregá canelones con salsa blanca y boloñesa | 7 sauce-on-recipe | 1 | 1 | canelones con salsa blanca y boloñesa | OK | b9613721021f7f9563ca0e390d446042 |
| 20 | guardá ñoquis con salsa rosa y queso rallado | 7 sauce-on-recipe | 1 | 1 | ñoquis con salsa rosa y queso rallado | OK | a2611d28371ae38e1f9dda08bb430684 |
| 21 | agregame ravioles con manteca y salvia | 7 sauce-on-recipe | 1 | 1 | ravioles con manteca y salvia | OK | 1ec5598cc5e9f3b1587b1c8f2ef4c1b9 |
| 22 | salt and pepper chicken | 8 sanity | 1 | 1 | salt and pepper chicken | OK | c0e287fadc75e3d28ea1a563a5547e49 |
| 23 | papa rellena | 8 sanity | 1 | 1 | papa rellena | OK | 8d1a2fd7e0db80983b41f3e60489f6b2 |
| 24 | pollo a la portuguesa | 8 sanity | 1 | 1 | pollo a la portuguesa | OK | e07d02c989fbfc77772e1935668cb76f |
| 25 | hola | 9 ambiguous | 0 | 0 |  | OK | c5ce29a336a891a2814c2d56df33451b |
| 26 | agregá algo rico | 9 ambiguous | 0 | 0 |  | OK | 70146512e7f1a19f300c1c0883ab223f |
| 27 | qué hago de cena | 9 ambiguous | 0 | 0 |  | OK | 19581aa433260b3f95b528bc2457ec3d |
| 28 | agregá esta receta: https://example.com/canelones | 10 url-deflection | 0 | 1 |  | FAIL | 478a9be65fa65bd9fac1088fbe1b2da8 |
| 29 | guardame https://cookpad.com/recetas/123 plis | 10 url-deflection | 0 | 1 |  | FAIL | 0e9a43499da5a4680e697574b55aa981 |
| 30 | https://recipes.test.example/x — agregala | 10 url-deflection | 0 | 1 |  | FAIL | 4f6fa7b10eeeaa7c2955dce7bf635395 |

## Notes

[Operator narrative — patterns, failures, recommendations.]

## Go / No-Go

Required for PASS: count ≥ 95% AND name ≥ 90% on multi-recipe rows.
If catastrophic (< 50% count): `verdict: pivot` (defensive code cap per Deferred Ideas).

verdict: pass | fail | pivot
