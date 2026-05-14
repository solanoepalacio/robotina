"""SELECT statements for the dashboard.

All queries return ORM rows; templates do the rendering. No business
logic here — queries only. The detail-view query uses selectinload to
prevent DetachedInstanceError when Jinja accesses run.steps after the
session has closed (RESEARCH Pitfall 4).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from robotina.queue.models import WorkflowRun


def list_recent_runs(db: Session, limit: int = 50) -> list[WorkflowRun]:
    """Latest N runs newest first (SPEC AC #6 — 50-row cap)."""
    return list(
        db.scalars(
            select(WorkflowRun)
            .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id.desc())
            .limit(limit)
        )
    )


def get_workflow_with_steps(db: Session, run_id: str) -> Optional[WorkflowRun]:
    """Detail-view fetch with eager-loaded steps (Pitfall 4)."""
    return db.scalars(
        select(WorkflowRun)
        .where(WorkflowRun.id == run_id)
        .options(selectinload(WorkflowRun.steps))
    ).first()
