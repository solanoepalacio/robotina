"""SPEC AC #6 — list view returns latest 50 runs newest first.

Two integration tests rely on real Postgres (db_session fixture); two
template-only tests render against the fixture-inserted empty / 1-row state.
"""
from __future__ import annotations

import pytest

from robotina.queue.models import WorkflowRun, WorkflowStatus


@pytest.mark.asyncio
async def test_list_view_renders_empty_state_when_zero_runs(monkeypatch):
    """WR-03: deterministically exercise the empty-state render path.

    The previous version of this test substring-matched "Workflows" — which
    appears in BOTH the populated header and the empty-state page — so it
    couldn't tell the two apart and the docstring was a lie. Here we
    monkeypatch list_recent_runs (called directly inside list_view, not via
    Depends, so dependency_overrides cannot intercept it) to return [],
    then assert two things the empty path uniquely produces:
      1. The empty-state copy ("No workflows yet") from index.html.
      2. Absence of `<tr class="run-row"` — the row marker from _run_rows.html.

    No shared-DB mutation; Pitfall 7 still respected.
    """
    import httpx

    from robotina.dashboard import app as app_mod

    monkeypatch.setattr(app_mod, "list_recent_runs", lambda *a, **kw: [])

    transport = httpx.ASGITransport(app=app_mod.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/")

    assert resp.status_code == 200
    assert "No workflows yet" in resp.text, (
        "empty-state copy from index.html should render when runs=[]"
    )
    assert '<tr class="run-row"' not in resp.text, (
        "no run rows should render when runs=[]"
    )


@pytest.mark.asyncio
async def test_index_template_renders_empty_state_directly():
    """Template-only check: render index.html with runs=[] and assert the
    empty-state copy appears. No DB needed."""
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader, select_autoescape

    tmpl_dir = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "robotina"
        / "dashboard"
        / "templates"
    )
    env = Environment(
        loader=FileSystemLoader(str(tmpl_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    out = env.get_template("index.html").render(runs=[])
    assert "No workflows yet" in out


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_view_renders_rows_newest_first(client, db_session):
    """Insert 3 runs; GET /; assert all three appear with newest first."""
    session, ids = db_session
    runs = []
    for i in range(3):
        r = WorkflowRun(
            workflow_type="add-recipe",
            household_id=f"h-{i}",
            status=WorkflowStatus.DONE,
            shared_context={},
        )
        session.add(r)
        session.flush()
        ids.append(r.id)
        runs.append(r)
    session.commit()

    resp = await client.get("/")
    assert resp.status_code == 200
    # All three ids appear (8-char short form per UI-SPEC §Component Contract 2)
    for r in runs:
        assert r.id[:8] in resp.text, f"missing run {r.id} in list output"
    # Newest first: the third-inserted run's id appears in the response
    # BEFORE the first-inserted run's id (text ordering matches DOM order).
    last_idx = resp.text.find(runs[-1].id[:8])
    first_idx = resp.text.find(runs[0].id[:8])
    assert last_idx >= 0 and first_idx >= 0
    assert last_idx < first_idx, "newest run must appear before older runs"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_row_links_to_detail(client, db_session):
    """Each list row links to /workflows/{id} (anchor in the ID column)."""
    session, ids = db_session
    r = WorkflowRun(
        workflow_type="add-recipe",
        household_id="h-link",
        status=WorkflowStatus.RUNNING,
        shared_context={},
    )
    session.add(r)
    session.flush()
    ids.append(r.id)
    session.commit()

    resp = await client.get("/")
    assert resp.status_code == 200
    assert f'href="/workflows/{r.id}"' in resp.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fragment_runs_returns_partial(client, db_session):
    """GET /fragments/runs returns the polling-target tbody wrapper.

    SPEC AC #6 + D-10: list polling is unconditional (every 10s).
    """
    resp = await client.get("/fragments/runs")
    assert resp.status_code == 200
    assert 'id="runs-body"' in resp.text
    assert 'hx-trigger="every 10s"' in resp.text
