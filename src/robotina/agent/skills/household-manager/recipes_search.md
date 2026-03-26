# Search and list recipes

## Endpoint

```
GET /api/recipes
```

Authentication required (see `shared.md`). Returns recipes belonging to the authenticated user's household.

## Query parameters

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| search | string | No | — | Case-insensitive substring match on recipe name |
| foodId | string (UUID) | No | — | Filter to recipes containing an ingredient with this food ID |
| sort | enum | No | createdAt | One of: `name`, `createdAt`, `updatedAt`, `random` |
| order | enum | No | desc | One of: `asc`, `desc`. Ignored when sort is `random`. |
| page | integer | No | 1 | 1-based page number |
| pageSize | integer | No | 20 | Items per page (max: 100) |

## When to use search vs foodId

- Use `search` to find recipes by name (e.g., "tortilla", "pollo").
- Use `foodId` to find recipes that use a specific ingredient. Obtain the food ID from `GET /api/foods` (see `recipes_create.md`) — the endpoint returns all foods as a plain array with no filtering; scan the array by name to find the matching `id`.
- Both can be combined: `?search=tortilla&foodId=<uuid>` returns recipes named "tortilla" that also contain the specified food.

## Response

The response is a paginated envelope (see `shared.md` for envelope shape). Each item in `items` has this shape:

```json
{
  "id": "a1b2c3d4-...",
  "name": "Tortilla espanola",
  "slug": "tortilla-espanola",
  "description": "Receta tradicional",
  "servingsQty": 4,
  "servingsUnit": "porciones",
  "shareToken": null,
  "createdAt": "2026-03-01T10:00:00.000Z",
  "updatedAt": "2026-03-15T14:30:00.000Z",
  "imageCount": 2,
  "coverImageUrl": "/uploads/abc123.jpg"
}
```

Field types:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | string (UUID) | No | Recipe ID — use for `GET /api/recipes/:id` |
| name | string | No | Recipe name |
| slug | string | No | URL-friendly name |
| description | string | Yes | Recipe description |
| servingsQty | number | Yes | Number of servings |
| servingsUnit | string | Yes | Servings unit label |
| shareToken | string | Yes | Non-null if recipe has been shared |
| createdAt | string (ISO 8601) | No | Creation timestamp |
| updatedAt | string (ISO 8601) | No | Last update timestamp |
| imageCount | number | No | Total number of images attached |
| coverImageUrl | string | Yes | URL of the first image, or null if no images |

## Example

Request:
```
GET /api/recipes?search=tortilla&sort=name&order=asc&page=1&pageSize=10
```

Response:
```json
{
  "items": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "name": "Tortilla espanola",
      "slug": "tortilla-espanola",
      "description": "Receta tradicional con patatas",
      "servingsQty": 4,
      "servingsUnit": "porciones",
      "shareToken": null,
      "createdAt": "2026-03-01T10:00:00.000Z",
      "updatedAt": "2026-03-15T14:30:00.000Z",
      "imageCount": 1,
      "coverImageUrl": "/uploads/abc123.jpg"
    }
  ],
  "total": 1,
  "page": 1,
  "perPage": 10
}
```

Note: the response envelope uses `perPage` (not `pageSize`). The query parameter is `pageSize`; the response field is `perPage`.

## Cross-references

- To fetch the full detail of a recipe, use the `id` from a list item with `GET /api/recipes/:id` (see `recipes_get.md`).
- To obtain a `foodId` for filtering, use `GET /api/foods` (see `recipes_create.md`) and scan the returned array by name.
