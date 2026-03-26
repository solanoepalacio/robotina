# Manage recipe images

## Upload an image

### Endpoint

```
POST /api/recipes/:id/images
```

Authentication required (see `shared.md`). Uploads a single image file to the recipe.

- `201` — uploaded
- `400` — invalid MIME type or file exceeds size limit
- `403` — recipe belongs to a different household
- `404` — recipe not found

### Request format

The request must use `multipart/form-data` encoding with a single field:

| Field | Type | Description |
|-------|------|-------------|
| file | binary | The image file |

Accepted MIME types:

| MIME type |
|-----------|
| `image/jpeg` |
| `image/png` |
| `image/webp` |
| `image/gif` |

Maximum file size: **10 MB**.

### Response

```json
{
  "id": "im1im2im3-...",
  "url": "/uploads/a1b2c3d4.jpg",
  "order": 0,
  "createdAt": "2026-03-20T12:00:00.000Z"
}
```

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | string (UUID) | No | Image ID — use for delete |
| url | string | No | Image URL path relative to base URL (e.g., `/uploads/a1b2c3d4.jpg`) |
| order | number | No | Display order (0-based) |
| createdAt | string (ISO 8601) | No | Upload timestamp |

### Example

Request (pseudo-HTTP):
```
POST /api/recipes/r1r2r3r4-.../images HTTP/1.1
Authorization: Bearer <token>
Content-Type: multipart/form-data; boundary=----boundary

------boundary
Content-Disposition: form-data; name="file"; filename="tortilla.jpg"
Content-Type: image/jpeg

<binary data>
------boundary--
```

Response:
```json
{
  "id": "im1im2im3-...",
  "url": "/uploads/a1b2c3d4.jpg",
  "order": 0,
  "createdAt": "2026-03-20T12:00:00.000Z"
}
```

## Delete an image

### Endpoint

```
DELETE /api/recipes/:id/images/:imageId
```

- `200` — deleted
- `403` — recipe belongs to a different household
- `404` — recipe or image not found

No request body is needed. Obtain the `imageId` from `GET /api/recipes/:id` (see `recipes_get.md`) — it is the `id` field in the `images[]` array.

## Cross-references

- To obtain the recipe `id` and existing image IDs: see `recipes_get.md`.
- To create the recipe before uploading images: see `recipes_create.md`.
- Authentication and error codes: see `shared.md`.
