"""Startup reconciler for stranded wake invocations.

WAKE-05 / D-11: closes the AOF-can't-replay-RQ-enqueue gap (Pitfall 11). The
wake helper in ``workflow_runner.py`` pre-assigns ``rq_job_id`` on the
``RobotinaInvocation`` row BEFORE committing, then calls
``queue.enqueue(...)`` AFTER commit. A worker crash between commit and
enqueue leaves a stranded row: Postgres has it (AOF replayed), but RQ does
not. The reconciler runs at task-runner boot, finds these rows, and
re-enqueues them with the SAME ``rq_job_id`` — RQ deduplicates on job_id,
so a race-win second enqueue (real enqueue did happen before crash;
reconciler ran first on restart) is safe.

Out of scope (deferred backlog): WorkflowRunStep orphans — a separate
problem with its own artifact-recovery concerns (Pitfall 11 "freebie").
"""
from __future__ import annotations

import logging

from rq.job import Job

logger = logging.getLogger(__name__)


def reconcile_invocations(session, queue) -> int:
    """Re-enqueue wake invocations whose RQ job vanished between commit and enqueue.

    Args:
        session: SQLAlchemy session (lifecycle managed by caller).
        queue: RQ Queue instance whose ``.connection`` is used as the RQ
            ``Job.exists`` probe target.

    Returns:
        Count of rows re-enqueued.
    """
    from robotina.queue.models import (
        InvocationStatus,
        InvocationTrigger,
        RobotinaInvocation,
        WorkflowRun,
        WorkflowStatus,
    )
    from robotina.queue.task_types import (
        AddRecipeOutcome,
        WakeInvocationInput,
        WorkflowOutcomeSummary,
    )

    candidates = (
        session.query(RobotinaInvocation)
        .filter(
            RobotinaInvocation.status == InvocationStatus.PENDING,
            RobotinaInvocation.wake_dispatched_at.isnot(None),
            RobotinaInvocation.rq_job_id.isnot(None),
        )
        .all()
    )
    if not candidates:
        logger.info("Reconciler: no orphan invocations")
        return 0

    reconciled = 0
    for row in candidates:
        try:
            if Job.exists(row.rq_job_id, connection=queue.connection):
                continue  # live job — nothing to do

            # Rebuild WakeInvocationInput from committed state.
            if row.trigger != InvocationTrigger.WORKFLOW_COMPLETION:
                # Only WORKFLOW_COMPLETION rows go through the wake helper.
                # USER_MESSAGE pending rows with rq_job_id+wake_dispatched_at
                # is a state that shouldn't exist; log and skip.
                logger.warning(
                    "Reconciler: skipping non-wake orphan | id=%s trigger=%s",
                    row.id, row.trigger,
                )
                continue

            sibling_runs = (
                session.query(WorkflowRun)
                .filter(WorkflowRun.triggered_by_invocation_id == row.trigger_ref_id)
                .all()
            )
            outcomes = []
            for r in sibling_runs:
                run_outcome = None
                if r.outcome is not None:
                    try:
                        run_outcome = AddRecipeOutcome.model_validate(r.outcome)
                    except Exception:
                        logger.warning(
                            "Reconciler: invalid outcome JSON | run_id=%s", r.id,
                        )
                outcomes.append(
                    WorkflowOutcomeSummary(
                        workflow_run_id=r.id,
                        workflow_type=r.workflow_type,
                        status=("done" if r.status == WorkflowStatus.DONE else "failed"),
                        outcome=run_outcome,
                    )
                )

            wake_input = WakeInvocationInput(
                previous_invocation_id=row.trigger_ref_id,
                conversation_id=row.conversation_id,
                outcomes=outcomes,
            )

            queue.enqueue(
                "robotina.queue.jobs.run_task",
                wake_input,
                job_id=row.rq_job_id,
                meta={
                    "task_type": "handle-incoming-message",
                    "invocation_id": row.id,
                    "queue_name": queue.name,
                },
                result_ttl=-1,
                failure_ttl=-1,
            )
            reconciled += 1
            logger.warning(
                "Reconciler: re-enqueued orphan wake invocation | id=%s rq_job_id=%s",
                row.id, row.rq_job_id,
            )
        except Exception:
            logger.exception(
                "Reconciler: failed to reconcile row | id=%s",
                row.id,
            )

    logger.info("Reconciler: re-enqueued %d orphan(s)", reconciled)
    return reconciled
