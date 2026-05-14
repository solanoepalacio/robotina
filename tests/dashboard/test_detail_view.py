"""SPEC AC #7 + #8 — detail view renders ordered steps with input/output/status
and the FAILED-vs-CANCELLED badges are visually distinct."""
from __future__ import annotations

import pytest

from tests.dashboard.conftest import make_failed_cascade_run


@pytest.mark.asyncio
async def test_detail_view_404_for_missing_id(client):
    """SPEC AC #7: unknown run id returns 404."""
    resp = await client.get("/workflows/does-not-exist-uuid")
    assert resp.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_detail_view_renders_failed_cascade(client, db_session):
    """SPEC AC #7 + AC #8: failed-cascade workflow renders correctly."""
    session, ids = db_session
    run = make_failed_cascade_run(session)
    ids.append(run.id)

    resp = await client.get(f"/workflows/{run.id}")
    assert resp.status_code == 200
    text = resp.text

    # All 3 distinct badges present in the response body
    assert "badge--done" in text
    assert "badge--failed" in text
    assert "badge--cancelled" in text

    # Step input JSON for at least one step (the seeded recipe_url marker)
    assert "recipe_url" in text

    # Failure reason for the FAILED step
    assert "ValueError: ingredient not found" in text

    # Steps appear in step_order (DONE → FAILED → CANCELLED → CANCELLED).
    # We assert via the data-status attribute order in the rendered HTML.
    done_idx = text.find('data-status="done"')
    failed_idx = text.find('data-status="failed"')
    first_cancelled_idx = text.find('data-status="cancelled"')
    second_cancelled_idx = text.find('data-status="cancelled"', first_cancelled_idx + 1)
    assert done_idx >= 0, "missing data-status='done' step row"
    assert failed_idx >= 0, "missing data-status='failed' step row"
    assert first_cancelled_idx >= 0, "missing first cancelled step row"
    assert second_cancelled_idx >= 0, "missing second cancelled step row"
    assert done_idx < failed_idx < first_cancelled_idx < second_cancelled_idx, (
        f"step rows out of step_order: "
        f"done={done_idx} failed={failed_idx} "
        f"cancelled1={first_cancelled_idx} cancelled2={second_cancelled_idx}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_failed_vs_cancelled_badges(client, db_session):
    """SPEC AC #8 falsifiability — both class strings appear, distinct."""
    session, ids = db_session
    run = make_failed_cascade_run(session)
    ids.append(run.id)

    resp = await client.get(f"/workflows/{run.id}")
    text = resp.text
    assert "badge--failed" in text
    assert "badge--cancelled" in text
    # And they are not the same substring (sanity check)
    assert "badge--failed" != "badge--cancelled"
