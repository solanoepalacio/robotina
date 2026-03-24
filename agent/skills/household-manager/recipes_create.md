# Create a recipe

## Create recipe

### Endpoint

```
POST /api/recipes
```

Authentication required (see `shared.md`). Creates a new recipe in the authenticated user's household. A default ingredient section is auto-created and returned in `sections[0]` of the response (see Recommended sequence below).

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

### Response

Full `RecipeDetailResponse` — same shape as `GET /api/recipes/:id` (see `recipes_get.md`). The response includes a `sections` array with one auto-created default section. Use `sections[0].id` as the `:sectionId` when adding ingredients without creating additional sections.

## Compound create (recommended)

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

## Resolve food and unit IDs

Ingredients require a `foodId` (required) and optionally a `unitId`. Resolve these from the reference lists before adding ingredients.

### Resolve food IDs

```
GET /api/foods?name=huevo
```

Authentication required (see `shared.md`). The optional `?name=` parameter filters by case-insensitive substring match. Omit it to retrieve the full list. See `shared.md` > Filtering reference lists for details.

Response:

```json
[{ "id": "f1f2f3f4-...", "name": "Huevo" }]
```

Use the returned `id` as `foodId` in the `ingredients[]` array.

### Resolve unit IDs

```
GET /api/units?name=kilo
```

Authentication required (see `shared.md`). Same filtering behavior as foods. See `shared.md` > Filtering reference lists for details.

Response:

```json
[{ "id": "u1u2u3u4-...", "name": "kilogramo", "abbreviation": "kg" }]
```

Use the returned `id` as `unitId` in the `ingredients[]` array (optional).

## Add a section

### Endpoint

```
POST /api/recipes/:id/sections
```

Authentication required (see `shared.md`). Adds a named ingredient section to the recipe. Only needed if you want sections beyond the auto-created default.

- `201` — created
- `403` — recipe belongs to a different household
- `404` — recipe not found

### Request body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| title | string | No | Section title; omit for an unnamed section |

### Response

```json
{ "id": "s1s2s3s4-...", "title": "Salsa", "order": 1, "ingredients": [] }
```

## Add an ingredient to a section

### Endpoint

```
POST /api/recipes/:id/sections/:sectionId/ingredients
```

Authentication required (see `shared.md`). Adds an ingredient to the specified section.

- `201` — created
- `400` — validation error
- `403` — recipe belongs to a different household
- `404` — recipe or section not found

### Request body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| foodId | string (UUID) | Yes | Food ID from `GET /api/foods` |
| unitId | string (UUID) | No | Unit ID from `GET /api/units` |
| quantity | number | No | Amount (can be decimal, e.g., 0.5) |
| note | string | No | Additional note (e.g., "finely chopped") |

### Response

```json
{
  "id": "i1i2i3i4-...",
  "foodId": "f1f2f3f4-...",
  "foodName": "Huevo",
  "unitId": "u1u2u3u4-...",
  "unitName": "unidad",
  "quantity": 6,
  "note": null,
  "order": 0
}
```

## Add a step

### Endpoint

```
POST /api/recipes/:id/steps
```

Authentication required (see `shared.md`). Adds an instruction step to the recipe. Steps are ordered by creation order.

- `201` — created
- `403` — recipe belongs to a different household
- `404` — recipe not found

### Request body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| body | string | Yes | Instruction text |
| title | string | No | Optional step heading |

### Response

```json
{ "id": "st1st2st3-...", "title": null, "body": "Batir los huevos con sal.", "order": 0 }
```

## Recommended sequence

### Compound path (3 calls)

1. **Resolve food IDs** — `GET /api/foods?name=<name>` for each unique food. Cache results across ingredients.
2. **Resolve unit IDs** — `GET /api/units?name=<name>` for each unique unit (skip if no units needed).
3. **Create the recipe with ingredients and steps** — `POST /api/recipes` with `name`, metadata fields, `ingredients[]`, and `steps[]`.

Total: 1 call per unique food + 1 call per unique unit + 1 POST = typically 3 calls for a simple recipe.

### Sequential path (fallback — 11+ calls)

Use this only if you need to add ingredients to multiple named sections (compound create adds all ingredients to the single default section).

1. **Create the recipe** — `POST /api/recipes` with at least `name`. Response includes `id` and `sections[0].id`.
2. **Resolve food and unit IDs** — `GET /api/foods?name=<name>` and `GET /api/units?name=<name>`.
3. **Add ingredients one by one** — `POST /api/recipes/:id/sections/:sectionId/ingredients` per ingredient.
4. **(Optional) Add named sections** — `POST /api/recipes/:id/sections` with a `title`.
5. **Add steps one by one** — `POST /api/recipes/:id/steps` per step.

## Example: Compound create

Step 1 — Resolve food IDs:

```
GET /api/foods?name=huevo
```

Response: `[{ "id": "f1f2f3f4-...", "name": "Huevo" }]`

```
GET /api/foods?name=patata
```

Response: `[{ "id": "f5f6f7f8-...", "name": "Patata" }]`

Step 2 — Resolve unit IDs:

```
GET /api/units?name=unidad
```

Response: `[{ "id": "u1u2u3u4-...", "name": "unidad", "abbreviation": "ud" }]`

```
GET /api/units?name=kilo
```

Response: `[{ "id": "u5u6u7u8-...", "name": "kilogramo", "abbreviation": "kg" }]`

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

Total calls: 5 (2 food lookups + 2 unit lookups + 1 POST). A recipe with 1 food and no units: 2 calls total.

## Cross-references

- Full response shape for the created recipe: see `recipes_get.md`.
- To upload images after creating the recipe: see `recipes_image.md`.
- To edit or delete any sub-resource after creation: see `recipes_edit.md`.
- Authentication and error codes: see `shared.md`.
- Food and unit filtering with ?name=: see `shared.md` > Filtering reference lists.
