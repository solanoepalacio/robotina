# Ingredients: Extract and verify ingredients

## Goal
Extract ingredients from the draft instructions and verify each one exists in the household-manager system.

## Process

### 1. Extract ingredients
Read the draft instructions and identify every ingredient mentioned, with:
- Food name in Spanish (e.g., `"cebolla"`, `"aceite de oliva"`)
- Quantity as a number (e.g., `2`, `0.5`)
- Unit name in Spanish (e.g., `"unidad"`, `"cucharada"`, `"g"`, `"ml"`, `"taza"`)
- Optional note in Spanish (e.g., `"picada finamente"`)

### 2. Verify against household-manager
For each ingredient, call the `household-manager-api` tool to verify the food exists:
- Method: `GET`
- Path: `/api/foods?name={food_name}`
- Look up the Spanish name directly (e.g., `GET /api/foods?name=cebolla`).

### 3. Handle missing ingredients
If an ingredient does not exist in household-manager:
- Re-check the other recipes from the gather step for a substitute.
- If you find a substitute that **does** exist, use it.
- If no substitute is available, drop the ingredient entirely.

### 4. Do not create new foods
Do not attempt to create new foods in household-manager. Only use foods that already exist.

## Output format
Your final response must be a JSON object with the verified ingredients:
```json
{
  "ingredients": [
    {"food_name": "cebolla", "unit_name": "unidad", "quantity": 1.0, "note": "picada"},
    {"food_name": "aceite de oliva", "unit_name": "cucharada", "quantity": 2.0, "note": null}
  ]
}
```
Only include ingredients you have verified against household-manager.

**JSON output rules.** Use the JSON literal `null` for missing optional fields — never the Python value `None`, never the bare word `none`, never an empty string in place of `null`. Booleans are `true` and `false`, lowercase. Numeric fields are bare numbers, never quoted. Do not omit optional fields when you have decided their value is "missing" — emit them with `null`.
