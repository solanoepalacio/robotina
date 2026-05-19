import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Enum, JSON, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from robotina.db import Base


class WorkflowStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class WorkflowStepStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_type: Mapped[str] = mapped_column(String, nullable=False)
    household_id: Mapped[str] = mapped_column(String, nullable=False)
    # Phase 17 / ARCH-01: FK to Conversation that originated this workflow run.
    # NOT NULL upfront (D-01). Operator pre-cleans workflow_runs before migrate
    # (D-08 runbook). FK NOT NULL + run_task's session.query(Conversation).one()
    # in jobs.py carry the write-time invariant; no parallel Python-level guard.
    conversation_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversations.id"), nullable=False
    )
    status: Mapped[WorkflowStatus] = mapped_column(Enum(WorkflowStatus, values_callable=lambda x: [e.value for e in x]), default=WorkflowStatus.PENDING, nullable=False)
    shared_context: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Phase 17 / D-06: nullable JSON slot for Phase 20's AddRecipeOutcome
    # (and per-workflow-type extensions). Unused in Phase 17 — no producer or
    # consumer this phase; the column exists so Phase 20 reads as "fill in
    # the shape" rather than "introduce a new concept."
    outcome: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    steps: Mapped[list["WorkflowRunStep"]] = relationship(back_populates="workflow_run")


class WorkflowRunStep(Base):
    __tablename__ = "workflow_run_steps"
    __table_args__ = (UniqueConstraint("workflow_run_id", "step_key"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_run_id: Mapped[str] = mapped_column(String, ForeignKey("workflow_runs.id"), nullable=False)
    workflow_run: Mapped["WorkflowRun"] = relationship(back_populates="steps")
    step_key: Mapped[str] = mapped_column(String, nullable=False)
    step_order: Mapped[int] = mapped_column(nullable=False, default=0)
    task_type: Mapped[str] = mapped_column(String, nullable=False)
    task_job_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[WorkflowStepStatus] = mapped_column(Enum(WorkflowStepStatus, values_callable=lambda x: [e.value for e in x]), default=WorkflowStepStatus.PENDING, nullable=False)
    artifact: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Phase 13 / Plan 13-01 (DASH-01): dashboard persistence columns. Both nullable
    # so historical rows backfill to NULL and the migration is non-blocking.
    step_input: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
