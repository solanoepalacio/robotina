"""Dashboard FastAPI application.

Phase 13 / DASH-04..DASH-08. Four routes:

- GET /                          → full-page list view (index.html)
- GET /workflows/{run_id}        → full-page detail view (workflow.html); 404 on miss
- GET /fragments/runs            → polling target for the list view
                                   (_run_rows.html, always polls every 10s — D-10)
- GET /fragments/workflows/{id}  → polling target for the detail view
                                   (_workflow_body.html, omits hx-trigger when
                                   the workflow is in a terminal status — D-09)

D-01: only inward imports from robotina.* — db, queue.models. No other
robotina modules.
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from robotina.dashboard.deps import get_db
from robotina.dashboard.queries import get_workflow_with_steps, list_recent_runs
from robotina.queue.models import WorkflowRun, WorkflowStatus

_HERE = Path(__file__).parent

app = FastAPI(title="Robotina Queue Dashboard")
templates = Jinja2Templates(directory=str(_HERE / "templates"))
app.mount(
    "/static",
    StaticFiles(directory=str(_HERE / "static")),
    name="static",
)

DbDep = Annotated[Session, Depends(get_db)]

# WorkflowStatus terminal set — used by the detail view to decide whether
# the polling wrapper's hx-trigger attribute should be rendered (D-09).
_TERMINAL_WORKFLOW_STATUSES = {WorkflowStatus.DONE, WorkflowStatus.FAILED}


def _is_terminal(run: WorkflowRun) -> bool:
    return run.status in _TERMINAL_WORKFLOW_STATUSES


@app.get("/", response_class=HTMLResponse)
def list_view(request: Request, db: DbDep):
    runs = list_recent_runs(db, limit=50)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"runs": runs},
    )


@app.get("/workflows/{run_id}", response_class=HTMLResponse)
def detail_view(request: Request, run_id: str, db: DbDep):
    run = get_workflow_with_steps(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # RESEARCH Pitfall 5: WorkflowRun.steps relationship has no order_by;
    # sort in Python by step_order so the detail view renders deterministically.
    # WR-06: step_order has no DB uniqueness constraint on
    # (workflow_run_id, step_order). Use s.id as a deterministic tie-breaker
    # so the detail view renders reproducibly even if two rows share the
    # same step_order (manual SQL edits, future migrations).
    steps = sorted(run.steps, key=lambda s: (s.step_order, s.id))
    return templates.TemplateResponse(
        request=request,
        name="workflow.html",
        context={
            "run": run,
            "steps": steps,
            "is_terminal": _is_terminal(run),
        },
    )


@app.get("/fragments/runs", response_class=HTMLResponse)
def fragment_runs(request: Request, db: DbDep):
    """List-view polling fragment. D-10: polling is unconditional."""
    runs = list_recent_runs(db, limit=50)
    return templates.TemplateResponse(
        request=request,
        name="_run_rows.html",
        context={"runs": runs},
    )


@app.get("/fragments/workflows/{run_id}", response_class=HTMLResponse)
def fragment_workflow(request: Request, run_id: str, db: DbDep):
    """Detail-view polling fragment. D-09: terminal status omits hx-trigger."""
    run = get_workflow_with_steps(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # WR-06: step_order has no DB uniqueness constraint on
    # (workflow_run_id, step_order). Use s.id as a deterministic tie-breaker
    # so the detail view renders reproducibly even if two rows share the
    # same step_order (manual SQL edits, future migrations).
    steps = sorted(run.steps, key=lambda s: (s.step_order, s.id))
    return templates.TemplateResponse(
        request=request,
        name="_workflow_body.html",
        context={
            "run": run,
            "steps": steps,
            "is_terminal": _is_terminal(run),
        },
    )
