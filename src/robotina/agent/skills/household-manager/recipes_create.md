# Create a recipe

## JSON output rules

For every request body documented on this page, use the JSON literal `null` for missing optional fields — never the Python value `None`, never the bare word `none`, never an empty string in place of `null`. Booleans are `true` and `false`, lowercase. Numeric fields are bare numbers, never quoted. Do not omit optional fields when you have decided their value is "missing" — emit them with `null`. (Canonical reference: `shared.md` > JSON output rules.)

## Create recipe

### Endpoint

```
POST /api/recipes
```

- `201` — created
- `400` — validation error

### Request body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Recipe name |
| description | string | No | Plain text description |
| servingsQty | integer | No | Number of servings (must be integer, not decimal) |
| servingsUnit | string | No | Servings label (e.g., "porciones") |
| prepTime | integer | No | Preparation time in minutes |
| cookTime | integer | No | Cooking time in minutes |
| totalTime | integer | No | Total time in minutes |
| performTime | integer | No | Active hands-on time in minutes |
| sourceUrl | string | No | Must be a valid URL if provided |
| ingredients | array | No | Inline ingredients for the default section (see Compound create below) |
| steps | array | No | Inline instruction steps (see Compound create below) |

## How to create:

`POST /api/recipes` accepts optional `ingredients[]` and `steps[]` arrays to create the recipe, all ingredients, and all steps in a single atomic call. If any ingredient references an invalid `foodId` or `unitId`, the entire request is rolled back — no orphaned recipe is created.

### ingredients[] item shape

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| foodId | string (UUID) | Yes | Food ID from `GET /api/foods` |
| unitId | string (UUID) | No | Unit ID from `GET /api/units` |
| quantity | number | No | Amount (can be decimal) |
| note | string | No | Additional note (e.g., "finely chopped") |

All ingredients are added to the auto-created default section in array order.

### steps[] item shape

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| body | string | Yes | Instruction text |
| title | string | No | Optional step heading |

Steps are ordered by array position.

### Error handling

- `201` — recipe + all ingredients + all steps created atomically
- `400` with message `"Invalid ingredient data: food or unit not found"` — a `foodId` or `unitId` does not exist; entire request rolled back, no recipe created

## Example: Compound create

Step 3 — Create recipe with everything:

```
POST /api/recipes
```

Request body:

```json
{
  "name": "Tortilla espanola",
  "servingsQty": 4,
  "servingsUnit": "porciones",
  "prepTime": 15,
  "cookTime": 20,
  "totalTime": 35,
  "ingredients": [
    { "foodId": "f1f2f3f4-...", "quantity": 6, "unitId": "u1u2u3u4-..." },
    { "foodId": "f5f6f7f8-...", "quantity": 0.5, "unitId": "u5u6u7u8-...", "note": "cortadas finas" }
  ],
  "steps": [
    { "body": "Batir los huevos con sal." },
    { "body": "Freir las patatas en aceite hasta dorar." }
  ]
}
```

Response (abbreviated):

```json
{
  "id": "r1r2r3r4-...",
  "name": "Tortilla espanola",
  "slug": "tortilla-espanola",
  "sections": [{
    "id": "s1s2s3s4-...",
    "title": null,
    "order": 0,
    "ingredients": [
      { "id": "i1i2i3i4-...", "foodId": "f1f2f3f4-...", "foodName": "Huevo", "unitId": "u1u2u3u4-...", "unitName": "unidad", "quantity": 6, "note": null, "order": 0 },
      { "id": "i5i6i7i8-...", "foodId": "f5f6f7f8-...", "foodName": "Patata", "unitId": "u5u6u7u8-...", "unitName": "kg", "quantity": 0.5, "note": "cortadas finas", "order": 1 }
    ]
  }],
  "steps": [
    { "id": "st1st2st3-...", "title": null, "body": "Batir los huevos con sal.", "order": 0 },
    { "id": "st4st5st6-...", "title": null, "body": "Freir las patatas en aceite hasta dorar.", "order": 1 }
  ],
  "images": []
}
```
