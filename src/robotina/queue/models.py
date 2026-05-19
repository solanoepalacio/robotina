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


class InvocationTrigger(enum.Enum):
    USER_MESSAGE = "user_message"
    WORKFLOW_COMPLETION = "workflow_completion"
    CRON = "cron"


class InvocationStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


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
    # Phase 18 / ARCH-02 + ARCH-03 / D-02: NULLABLE FK to robotina_invocations.id.
    # New WorkflowRuns created via StartWorkflowTool stamp this column; legacy
    # rows (and any rows created during the deploy window without an upstream
    # invocation context) carry NULL. Phase 20's wake rule only acts on rows
    # where this FK is set — NULL = "historical, ignored by wake."
    triggered_by_invocation_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("robotina_invocations.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    steps: Mapped[list["WorkflowRunStep"]] = relationship(back_populates="workflow_run")


class RobotinaInvocation(Base):
    """Phase 18 / ARCH-02: one row per Robotina LLM turn.

    Phase 18 only WRITES rows with ``trigger=USER_MESSAGE`` and
    ``status=PENDING`` from the gateway handler; the other enum values and
    lifecycle columns are Phase-20-ready slots (D-05, D-06, D-07) — they ship
    now to avoid ALTER TYPE / ALTER TABLE churn next phase.

    The named UniqueConstraint is dormant in Phase 18 (USER_MESSAGE rows use
    StoredMessage.id as trigger_ref_id which is already globally unique) but
    becomes the load-bearing wake-rule idempotency guard in Phase 20 (Pitfall 1).
    """

    __tablename__ = "robotina_invocations"
    __table_args__ = (
        UniqueConstraint(
            "trigger_ref_id", "trigger",
            name="ux_invocation_workflow_completion_once",
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    conversation_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversations.id"), nullable=False
    )
    trigger: Mapped[InvocationTrigger] = mapped_column(
        Enum(InvocationTrigger, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    # USER_MESSAGE        → StoredMessage.id
    # WORKFLOW_COMPLETION → prior RobotinaInvocation.id (Phase 20)
    # CRON                → ScheduledTask.id (future scheduler milestone)
    trigger_ref_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rq_job_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[InvocationStatus] = mapped_column(
        Enum(InvocationStatus, values_callable=lambda x: [e.value for e in x]),
        default=InvocationStatus.PENDING,
        nullable=False,
    )
    wake_dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


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
