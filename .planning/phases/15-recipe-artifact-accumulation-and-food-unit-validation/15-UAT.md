---
status: complete
phase: 15-recipe-artifact-accumulation-and-food-unit-validation
source:
  - 15-01-SUMMARY.md
  - 15-02-SUMMARY.md
  - 15-03-SUMMARY.md
  - 15-04-SUMMARY.md
  - 15-05-SUMMARY.md
started: 2026-05-15T17:26:29Z
updated: 2026-05-15T17:32:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Add Recipe — End-to-End via Telegram
expected: |
  Send "agregá receta de pollo al horno" (or any recipe) via Telegram. Receive
  Spanish ack within seconds, completion notification within ~3 min. Recipe
  appears in household-manager app with name, description, ingredients (with
  resolved foods + units), ordered steps, and populated metadata fields.
result: pass

### 2. Catalog Resolution on Created Recipe
expected: |
  Open the recipe created in test 1 in the household-manager app and inspect
  ingredients. Foods that exist in the household catalog show as catalog
  entries (not raw strings), and where the source mentioned a unit (g, ml,
  unidad, cucharada, etc.) the unit is attached to the ingredient. Quantities
  carried through.
result: pass

### 3. Missing Ingredients Surfaced (Not Silently Dropped)
expected: |
  Add a recipe that's likely to contain at least one food not in your
  household catalog (e.g. an unusual spice or a regional ingredient). After
  the workflow completes, that ingredient is listed under
  `missing_ingredients` on the recipe (visible in the API response or app),
  while the recipe itself was still created with all the resolved
  ingredients. No silent drop, no hard failure.
result: pass

### 4. Recipe Discovery After Creation
expected: |
  After test 1 completes, send a follow-up question like "qué ingredientes
  necesito para hacer pollo al horno" via Telegram. The agent finds the
  just-created recipe in the catalog and replies with the ingredient list
  (in Spanish) — proving that the artifact created by the pipeline is
  correctly persisted and queryable.
result: pass

### 5. Recipe-Load Single-POST Behavior (Regression for Empty-Body Loop)
expected: |
  In the run logs (or in LangWatch), the `recipe-load` step for the recipe
  created in test 1 shows ONE POST to `/api/recipes` returning 201 Created —
  not 30+ identical retries with `body={}`. This is the regression check for
  the bug fixed today (typed body schema + construct-then-call prompt). If
  this regresses, the empty-body loop is back.
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
