"""SPEC AC #9 + D-09 — polling-halt markup contract.

The load-bearing test: detail-view wrapper for a terminal-status workflow
does NOT contain `hx-trigger`. List-view wrapper ALWAYS contains
`hx-trigger="every 10s"` (D-10).
"""
from __future__ import annotations

import pytest

from robotina.queue.models import WorkflowRun, WorkflowStatus


@pytest.mark.integration
@pytest.mark.asyncio
async def test_detail_fragment_terminal_has_no_hx_trigger(client, db_session):
    """For status in (DONE, FAILED) the wrapper has NO hx-trigger attribute."""
    session, ids = db_session
    r = WorkflowRun(
        workflow_type="add-recipe",
        household_id="h-done",
        status=WorkflowStatus.DONE,
        shared_context={},
    )
    session.add(r)
    session.flush()
    ids.append(r.id)
    session.commit()

    resp = await client.get(f"/fragments/workflows/{r.id}")
    assert resp.status_code == 200
    assert 'id="workflow-body"' in resp.text
    # THE load-bearing invariant
    assert "hx-trigger" not in resp.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_detail_fragment_running_has_hx_trigger(client, db_session):
    """For status=RUNNING the wrapper polls every 3s with outerHTML swap."""
    session, ids = db_session
    r = WorkflowRun(
        workflow_type="add-recipe",
        household_id="h-running",
        status=WorkflowStatus.RUNNING,
        shared_context={},
    )
    session.add(r)
    session.flush()
    ids.append(r.id)
    session.commit()

    resp = await client.get(f"/fragments/workflows/{r.id}")
    assert resp.status_code == 200
    assert 'hx-trigger="every 3s"' in resp.text
    assert 'hx-swap="outerHTML"' in resp.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_fragment_always_has_hx_trigger(client, db_session):
    """D-10: list polling is unconditional, regardless of DB state."""
    resp = await client.get("/fragments/runs")
    assert resp.status_code == 200
    assert 'hx-trigger="every 10s"' in resp.text
