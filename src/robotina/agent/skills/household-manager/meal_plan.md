# Manage meal plan

The meal plan list endpoint returns a flat `entries` array, **not** a paginated envelope. Do not look for `items`, `total`, `page`, or `perPage` in the response.

## MealType values

All endpoints that accept or return a `mealType` field use one of these values:

| Value | Description |
|-------|-------------|
| `breakfast` | Breakfast |
| `lunch` | Lunch |
| `dinner` | Dinner |
| `snack` | Snack |
| `dessert` | Dessert |

## List entries

### Endpoint

```
GET /api/meal-plan
```

Authentication required (see `shared.md`). Returns all meal plan entries for the authenticated user's household, optionally filtered by date range.

- `200` — success

### Query parameters

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| from | string (YYYY-MM-DD) | No | Start date (inclusive). Omit for no lower bound. |
| to | string (YYYY-MM-DD) | No | End date (inclusive). Omit for no upper bound. |

Common queries:
- Today's entries: `GET /api/meal-plan?from=2026-03-20&to=2026-03-20`
- This week (Mon-Sun): `GET /api/meal-plan?from=2026-03-16&to=2026-03-22`
- All entries: `GET /api/meal-plan` (no params)

### Response

The response is a `MealPlanResponse` object with an `entries` array:

```json
{
  "entries": [
    {
      "id": "e1e2e3e4-...",
      "date": "2026-03-20",
      "mealType": "lunch",
      "recipeId": "r1r2r3r4-...",
      "recipeName": "Tortilla espanola",
      "recipeSlug": "tortilla-espanola",
      "createdAt": "2026-03-19T10:00:00.000Z",
      "updatedAt": "2026-03-19T10:00:00.000Z"
    }
  ]
}
```

Entry field types:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | string (UUID) | No | Entry ID — use for update and delete |
| date | string (YYYY-MM-DD) | No | Assigned date |
| mealType | string | No | One of the MealType values above |
| recipeId | string (UUID) | No | Recipe ID |
| recipeName | string | No | Recipe name (denormalized) |
| recipeSlug | string | No | Recipe slug (denormalized) |
| createdAt | string (ISO 8601) | No | Creation timestamp |
| updatedAt | string (ISO 8601) | No | Last update timestamp |

## Create an entry

### Endpoint

```
POST /api/meal-plan/entries
```

- `201` — created
- `400` — validation error

### Request body

All three fields are required:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| recipeId | string (UUID) | Yes | Recipe ID to assign (obtain from `recipes_search.md`) |
| date | string | Yes | Date in `YYYY-MM-DD` format |
| mealType | string | Yes | One of: `breakfast`, `lunch`, `dinner`, `snack`, `dessert` |

### Response

`MealPlanEntryResponse` (same shape as entries in the list response above).

### Example

Request:
```
POST /api/meal-plan/entries
```

Request body:
```json
{
  "recipeId": "r1r2r3r4-...",
  "date": "2026-03-21",
  "mealType": "dinner"
}
```

Response:
```json
{
  "id": "e5e6e7e8-...",
  "date": "2026-03-21",
  "mealType": "dinner",
  "recipeId": "r1r2r3r4-...",
  "recipeName": "Tortilla espanola",
  "recipeSlug": "tortilla-espanola",
  "createdAt": "2026-03-20T15:00:00.000Z",
  "updatedAt": "2026-03-20T15:00:00.000Z"
}
```

## Update an entry

### Endpoint

```
PATCH /api/meal-plan/entries/:id
```

Partial update — include only the fields you want to change.

- `200` — updated
- `403` — entry belongs to a different household
- `404` — entry not found

### Request body

All fields are optional:

| Field | Type | Description |
|-------|------|-------------|
| recipeId | string (UUID) | Change the assigned recipe |
| date | string | Change the date (`YYYY-MM-DD`) |
| mealType | string | Change the meal type |

### Response

`MealPlanEntryResponse`.

## Delete an entry

### Endpoint

```
DELETE /api/meal-plan/entries/:id
```

- `200` — deleted
- `403` — entry belongs to a different household
- `404` — entry not found

No request body is needed. Obtain the entry `id` from `GET /api/meal-plan` list response.

## Cross-references

- To obtain a `recipeId` for creating entries: search recipes via `GET /api/recipes` (see `recipes_search.md`).
- Authentication and error codes: see `shared.md`.
