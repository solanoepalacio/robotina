# Metadata: Estimate times and servings

## Goal
Produce the final, complete recipe with all metadata estimated.

## Process

### 1. Review metadata sources
Read the metadata of every recipe from the gather step (times, servings) plus the draft instructions.

### 2. Estimate times
- **prep_time**: preparation time in minutes. Estimate based on the count and complexity of the ingredients.
- **cook_time**: cooking time in minutes. Estimate based on the instructions (temperature, cooking technique).
- **total_time**: `prep_time + cook_time`.

### 3. Estimate servings
- **servings_qty**: number of servings as an integer. If the source recipes do not specify a value, default to `4` as a reasonable fallback.
- **servings_unit**: always `"porciones"`.

### 4. Assemble the final RecipeData
Combine everything from the previous steps into the final structure.

## Output format
Your final response must be a JSON object with the full `RecipeData` structure:
```json
{
  "recipe": {
    "name": "Nombre de la receta",
    "description": "Descripcion breve",
    "servings_qty": 4,
    "servings_unit": "porciones",
    "prep_time": 15,
    "cook_time": 30,
    "total_time": 45,
    "source_url": "http://...",
    "ingredients": [
      {"food_name": "...", "unit_name": "...", "quantity": 1.0, "note": null}
    ],
    "steps": [
      {"body": "Paso 1...", "title": null}
    ]
  }
}
```

**JSON output rules.** Use the JSON literal `null` for missing optional fields — never the Python value `None`, never the bare word `none`, never an empty string in place of `null`. Booleans are `true` and `false`, lowercase. Numeric fields are bare numbers, never quoted. Do not omit optional fields when you have decided their value is "missing" — emit them with `null`.

**Time fields must always be numeric.** Always estimate `prep_time`, `cook_time`, and `total_time` even when the source recipes do not provide values — use the complexity of the instructions as a guide (e.g., pasta with 10 ingredients -> ~30 min of cooking time). All time fields must hold numeric values; they are never `null` (this is a narrower constraint than the general null rule above — time fields are specifically required).
