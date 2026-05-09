# Shared conventions

## Base URL

All endpoint paths in this bundle are relative to a configurable base URL.

Default base URL: `http://localhost:3001`

All paths start with `/api` (e.g., `GET /api/recipes`).

## Error codes

| Status | Meaning | Action |
|--------|---------|--------|
| 400 | Validation error — request body or query params are invalid | Check the `message` field (array of strings) for details |
| 404 | Not found — the resource does not exist | Verify the ID or path is correct |
| 422 | Validation error (alternative) — same as 400 | Check the `message` field |
| 500 | Server error | Do not retry immediately; report the issue |

## Error response shape

```json
{
  "statusCode": 404,
  "message": "Recipe abc123 not found",
  "error": "Not Found"
}
```

For validation errors (400), `message` is an array of strings:

```json
{
  "statusCode": 400,
  "message": ["name must be a string", "servingsQty must be a number"],
  "error": "Bad Request"
}
```

## Pagination

List endpoints return a paginated envelope:

```json
{
  "items": [],
  "total": 100,
  "page": 1,
  "perPage": 20
}
```

| Field | Type | Description |
|-------|------|-------------|
| items | array | The page of results |
| total | integer | Total number of matching items across all pages |
| page | integer | Current 1-based page number |
| perPage | integer | Number of items per page |

**Important:** The response field is `perPage` (not `pageSize`). The query parameter for requesting page size is `pageSize`. These are different names — do not confuse them.

## JSON output rules

When you construct request bodies for any household-manager endpoint, follow these rules. Use the JSON literal `null` for missing optional fields — never the Python value `None`, never the bare word `none`, never an empty string in place of `null`. Booleans are `true` and `false`, lowercase. Numeric fields are bare numbers, never quoted. Do not omit optional fields when you have decided their value is "missing" — emit them with `null`.

This is the canonical rule for the whole bundle; the per-file pages may restate it for emphasis.

## Filtering reference lists

The food and unit reference endpoints accept an optional `?name=` query parameter for targeted lookups.

| Endpoint | Filter param | Behavior |
|----------|-------------|----------|
| `GET /api/foods?name=tomate` | `name` (optional) | Returns only foods whose name contains "tomate" (case-insensitive substring match) |
| `GET /api/units?name=taza` | `name` (optional) | Returns only units whose name contains "taza" (case-insensitive substring match) |

When the `name` parameter is **omitted or empty**, the full list is returned unchanged (backward-compatible).

Example — resolve the food ID for "Huevo":

```
GET /api/foods?name=huevo
```

Response:

```json
[{ "id": "f1f2f3f4-...", "name": "Huevo" }]
```

Use the returned `id` as `foodId` when creating ingredients. This replaces the need to fetch the entire foods list and scan it client-side.

## Data language

All user-facing data returned by the household-manager API — recipe names, food names, unit names, descriptions, meal plan entries — is stored in Spanish. Use these values as-is in your responses without translating them.
