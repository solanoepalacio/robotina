# Edit a recipe

Always fetch the current recipe via `GET /api/recipes/:id` (see `recipes_get.md`) before editing. This gives you the correct sub-resource IDs (section, ingredient, step) needed for update and delete operations.

If `isLocked` is `true` in the response, the recipe cannot be edited. To unlock, send `PATCH /api/recipes/:id` with `{ "isLocked": false }` first.

## Update recipe metadata

### Endpoint

```
PATCH /api/recipes/:id
```

Authentication required (see `shared.md`). Partial update — include only the fields you want to change.

- `200` — updated
- `400` — validation error
- `403` — recipe belongs to a different household
- `404` — recipe not found

### Request body

All fields are optional:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| name | string | No | Recipe name |
| description | string | Yes | Set `null` to clear |
| servingsQty | integer | Yes | Set `null` to clear |
| servingsUnit | string | Yes | Set `null` to clear |
| prepTime | integer | Yes | Set `null` to clear |
| cookTime | integer | Yes | Set `null` to clear |
| totalTime | integer | Yes | Set `null` to clear |
| performTime | integer | Yes | Set `null` to clear |
| sourceUrl | string | Yes | Set `null` to clear; must be a valid URL if non-null |
| isLocked | boolean | No | Set `true` to lock, `false` to unlock |

### Response

Full `RecipeDetailResponse` (see `recipes_get.md`).

### Example

Request:

```
PATCH /api/recipes/a1b2c3d4-...
```

Request body:

```json
{ "description": "Receta actualizada", "cookTime": 25 }
```

## Update a section

### Endpoint

```
PATCH /api/recipes/:id/sections/:sectionId
```

Authentication required (see `shared.md`). Partial update.

- `200` — updated
- `403` — recipe belongs to a different household
- `404` — recipe or section not found

### Request body

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| title | string | Yes | Set `null` to remove the title |

### Response

`SectionResponse`: `{ "id": "...", "title": "Nuevo titulo", "order": 0, "ingredients": [...] }`

## Update an ingredient

### Endpoint

```
PATCH /api/recipes/:id/sections/:sectionId/ingredients/:ingredientId
```

Authentication required (see `shared.md`). Partial update — all fields optional.

- `200` — updated
- `400` — validation error
- `403` — recipe belongs to a different household
- `404` — recipe, section, or ingredient not found

### Request body

All fields are optional:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| foodId | string (UUID) | No | Change the food |
| unitId | string (UUID) | Yes | Set `null` to remove unit |
| quantity | number | Yes | Set `null` to remove quantity (allows decimals) |
| note | string | Yes | Set `null` to remove note |

### Response

`IngredientResponse` (same shape as in `recipes_get.md` nested ingredients).

## Add multiple ingredients (batch)

### Endpoint

```
POST /api/recipes/:id/sections/:sectionId/ingredients/batch
```

Authentication required (see `shared.md`). Adds multiple ingredients to a section in a single atomic call. If any `foodId` or `unitId` is invalid, the entire batch is rolled back — no partial inserts.

New ingredients are appended after existing ingredients in the section (order values continue from the current maximum).

- `201` — all ingredients created, returns updated section
- `400` — validation error
- `403` — recipe belongs to a different household
- `404` — recipe, section not found, or invalid food/unit ID

### Request body

```json
{
  "ingredients": [
    { "foodId": "f1f2f3f4-...", "unitId": "u1u2u3u4-...", "quantity": 6 },
    { "foodId": "f5f6f7f8-...", "unitId": "u5u6u7u8-...", "quantity": 0.5, "note": "cortadas finas" }
  ]
}
```

Each ingredient item:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| foodId | string (UUID) | Yes | Food ID from `GET /api/foods` |
| unitId | string (UUID) | No | Unit ID from `GET /api/units` |
| quantity | number | No | Amount (can be decimal) |
| note | string | No | Additional note |

### Response

Returns the full `SectionResponse` for the section, including all existing and newly added ingredients with hydrated `foodName` and `unitName`:

```json
{
  "id": "s1s2s3s4-...",
  "title": null,
  "order": 0,
  "ingredients": [
    { "id": "i1i2i3i4-...", "foodId": "f1f2f3f4-...", "foodName": "Huevo", "unitId": "u1u2u3u4-...", "unitName": "unidad", "quantity": 6, "note": null, "order": 0 },
    { "id": "i5i6i7i8-...", "foodId": "f5f6f7f8-...", "foodName": "Patata", "unitId": "u5u6u7u8-...", "unitName": "kg", "quantity": 0.5, "note": "cortadas finas", "order": 1 }
  ]
}
```

### When to use

Use batch add instead of single-ingredient POST when adding 2+ ingredients during an edit flow. For recipe creation, prefer the compound create path in `recipes_create.md` which inlines ingredients in the initial POST.

## Update a step

### Endpoint

```
PATCH /api/recipes/:id/steps/:stepId
```

Authentication required (see `shared.md`). Partial update.

- `200` — updated
- `403` — recipe belongs to a different household
- `404` — recipe or step not found

### Request body

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| body | string | No | Instruction text |
| title | string | Yes | Set `null` to remove title |

### Response

`StepResponse`: `{ "id": "...", "title": null, "body": "Updated instruction.", "order": 0 }`

## Delete operations

All delete endpoints return `200` on success. No request body is needed.

| Endpoint | What it deletes |
|----------|-----------------|
| `DELETE /api/recipes/:id` | The entire recipe and all sub-resources (sections, ingredients, steps, images) |
| `DELETE /api/recipes/:id/sections/:sectionId` | The section and all its ingredients |
| `DELETE /api/recipes/:id/sections/:sectionId/ingredients/:ingredientId` | A single ingredient |
| `DELETE /api/recipes/:id/steps/:stepId` | A single step |

Status codes for all delete operations: `200` (success), `403` (recipe belongs to a different household), `404` (not found).

## Cross-references

- To obtain the recipe `id` and all sub-resource IDs: see `recipes_get.md`.
- To find a recipe by name: see `recipes_search.md`.
- To manage images (upload/delete): see `recipes_image.md`.
- To create new sub-resources (sections, ingredients, steps): see `recipes_create.md`.
- To add multiple ingredients at once: use batch add above, or compound create in `recipes_create.md`.
- Authentication and error codes: see `shared.md`.
