# Shared conventions

## Base URL

All endpoint paths in this bundle are relative to a configurable base URL.

Default base URL: `http://localhost:3001`

All paths start with `/api` (e.g., `GET /api/recipes`).

## Authentication

Every request must include the header:

```
Authorization: Bearer <token>
```

The token is a raw API key issued by an administrator. Do not hash or encode it.

Example:

```
GET /api/recipes HTTP/1.1
Authorization: Bearer abc123def456...
```

## Error codes

| Status | Meaning | Action |
|--------|---------|--------|
| 400 | Validation error — request body or query params are invalid | Check the `message` field (array of strings) for details |
| 401 | Not authenticated — token is missing or invalid | Verify the `Authorization` header is present and the token is correct |
| 403 | Forbidden — authenticated but not authorized for this resource | The resource belongs to a different household |
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
