"""SPEC AC #11 — no authentication required on any dashboard route."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_all_routes_return_200_or_404_without_auth_headers(client):
    """No 401/403 anywhere; auth is out of scope per SPEC."""
    paths = [
        "/",
        "/workflows/nonexistent",
        "/fragments/runs",
        "/fragments/workflows/nonexistent",
    ]
    for p in paths:
        resp = await client.get(p)
        assert resp.status_code not in (401, 403), (
            f"{p} returned {resp.status_code} — auth must not gate dashboard routes"
        )
        # And they all reach FastAPI (not a transport-level error):
        assert resp.status_code in (200, 404), (
            f"{p} returned unexpected status {resp.status_code}"
        )
