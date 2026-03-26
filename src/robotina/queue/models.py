import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Enum, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from robotina.db import Base


class WorkflowStatus(enum.Enum):
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
    status: Mapped[WorkflowStatus] = mapped_column(Enum(WorkflowStatus, values_callable=lambda x: [e.value for e in x]), default=WorkflowStatus.RUNNING, nullable=False)
    shared_context: Mapped[dict] = mapped_column(JSON, nullable=False)
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
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
