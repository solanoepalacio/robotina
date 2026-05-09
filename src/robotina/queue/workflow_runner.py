"""Workflow execution engine for Robotina.

All lifecycle state transitions for WorkflowRun and WorkflowRunStep live here.
Called by run_task() (jobs.py) for advancement hooks and by StartWorkflowTool
for workflow initiation.

Functions accept a SQLAlchemy session argument so they are testable
without a live database (D-11).

IMPORTANT: All RQ enqueue calls must use:
  - queue name: "agent-tasks" (locked)
  - result_ttl=-1, failure_ttl=-1 (locked — no lost tasks)
  - job_id pre-assigned before commit (D-07 — transactional advancement)
  - meta={'task_type': step.task_type}
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _extract_task_output(result: dict) -> dict:
    """Extract the agent's final JSON output from a LangGraph result.

    Reads the last message content and parses it as JSON.
    Strips markdown code fences (```...```) if present.

    Phase 07.1: When a terminal tool (``return_direct=True``, e.g. ``QueueTool``)
    short-circuits the prebuilt ``create_react_agent`` graph, the last message
    is a ``ToolMessage`` rather than a JSON-emitting ``AIMessage`` — the
    tool-call AIMessage that immediately precedes it has no text content for
    Anthropic models (the tool_use block carries no JSON). In that case there
    is no agent-emitted JSON to parse; surface the tool's return string as the
    artifact directly. Steps that use return_direct tools (e.g. the
    per-workflow ack agents) do not have downstream consumers of their
    artifact, so the ``{"tool_message": ...}`` shape is safe.
    """
    messages = result["messages"]
    last = messages[-1]
    if getattr(last, "type", None) == "tool":
        return {"tool_message": str(last.content)}
    # Find the last AI message (LangGraph always ends with one, but be explicit)
    ai_messages = [m for m in messages if getattr(m, "type", None) == "ai"]
    raw = ai_messages[-1].content if ai_messages else last.content
    # AIMessage.content can be a list of content blocks (Anthropic tool-use format)
    if isinstance(raw, list):
        raw = " ".join(b.get("text", "") for b in raw if isinstance(b, dict) and b.get("type") == "text")
    content = raw.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        json_lines = []
        for line in lines[1:]:
            if line.strip() == "```":
                break
            json_lines.append(line)
        content = "\n".join(json_lines)
    parsed = None
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # Scan for first JSON object or array in case of leading prose
        for start_char in ('{', '['):
            idx = content.find(start_char)
            if idx != -1:
                try:
                    parsed = json.loads(content[idx:])
                    break
                except json.JSONDecodeError:
                    pass
    if parsed is None:
        # TEMP DIAGNOSTIC (remove once recipe-research-gather parse failure is understood):
        # Dump the full content (and length) so we can tell whether the failure is
        # trailing prose vs. mid-JSON truncation.
        logger.error(
            "extract_task_output | parse failed | length=%d | full_content=%r",
            len(content),
            content,
        )
        raise ValueError(f"Could not parse JSON from agent output: {content[:200]!r}")
    return parsed


def queue_workflow(
    workflow_type: str,
    shared_context: dict,
    household_id: str,
    queue,
    session: Session,
) -> str:
    """Create a WorkflowRun as PENDING and all WorkflowRunStep records, enqueue the first step.

    The WorkflowRun is created with status=PENDING. It transitions to RUNNING
    when the worker begins executing the first step (on_step_start).

    Args:
        workflow_type: Key in WORKFLOW_REGISTRY (e.g. "add-recipe").
        shared_context: Frozen context dict set once at creation — stored in
                        WorkflowRun.shared_context. Contains reply_context,
                        household_id, recipe_query, etc.
        household_id: Stored on WorkflowRun for filtering/monitoring.
        queue: RQ Queue instance connected to "agent-tasks".
        session: SQLAlchemy session (injected for testability — D-11).

    Returns:
        workflow_run_id: UUID string of the created WorkflowRun.

    Raises:
        KeyError: If workflow_type not in WORKFLOW_REGISTRY.
    """
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.models import WorkflowRun, WorkflowRunStep, WorkflowStatus, WorkflowStepStatus

    workflow_def = WORKFLOW_REGISTRY[workflow_type]

    # Create the WorkflowRun as PENDING (transitions to RUNNING when first step begins)
    run = WorkflowRun(
        workflow_type=workflow_type,
        household_id=household_id,
        shared_context=shared_context,
        status=WorkflowStatus.PENDING,
    )
    session.add(run)
    session.flush()  # get run.id before creating steps

    # Create all steps as PENDING
    steps = []
    for order, step_def in enumerate(workflow_def.steps):
        step = WorkflowRunStep(
            workflow_run_id=run.id,
            step_key=step_def.step_key,
            step_order=order,
            task_type=step_def.task_type,
            status=WorkflowStepStatus.PENDING,
        )
        session.add(step)
        steps.append((step, step_def))
    session.flush()

    # Build and enqueue the first step — pre-assign job_id BEFORE commit (D-07)
    first_step, first_step_def = steps[0]
    first_job_id = str(uuid.uuid4())
    task_input = first_step_def.build_input(dict(shared_context), {})

    queue.enqueue(
        "robotina.queue.jobs.run_task",
        task_input,
        job_id=first_job_id,
        meta={"task_type": first_step.task_type, "queue_name": queue.name},
        result_ttl=-1,
        failure_ttl=-1,
    )

    first_step.task_job_id = first_job_id
    session.commit()

    logger.info(
        "Workflow queued | workflow_type=%s run_id=%s first_job_id=%s",
        workflow_type,
        run.id,
        first_job_id,
    )
    return run.id


def on_step_start(job_id: str, session: Session) -> None:
    """Mark the WorkflowRunStep matching job_id as RUNNING.

    If no step is found (direct task, not part of a workflow), returns None
    without modifying any state — this is the normal path for all current
    production direct tasks (D-06).

    Args:
        job_id: RQ job ID of the currently executing job.
        session: SQLAlchemy session.
    """
    from robotina.queue.models import WorkflowRun, WorkflowRunStep, WorkflowStatus, WorkflowStepStatus

    step = (
        session.query(WorkflowRunStep)
        .filter(WorkflowRunStep.task_job_id == job_id)
        .first()
    )
    if step is None:
        logger.debug("on_step_start: no workflow step found for job_id=%s (direct task)", job_id)
        return None

    step.status = WorkflowStepStatus.RUNNING
    step.started_at = datetime.now(timezone.utc)
    # Transition WorkflowRun from PENDING → RUNNING when first step begins
    run = session.query(WorkflowRun).filter(WorkflowRun.id == step.workflow_run_id).first()
    if run is not None and run.status == WorkflowStatus.PENDING:
        run.status = WorkflowStatus.RUNNING
    session.commit()
    logger.info(
        "Step started | run_id=%s step_key=%s job_id=%s",
        step.workflow_run_id,
        step.step_key,
        job_id,
    )
    return step


def on_step_complete(
    job_id: str,
    output: Any,
    session: Session,
    queue,
) -> None:
    """Persist artifact, advance to next step, or mark WorkflowRun DONE.

    Steps:
    1. Find WorkflowRunStep by task_job_id.
    2. Write output to artifact as JSON-serializable dict.
    3. Mark step DONE, record completed_at.
    4. Build accumulated_artifacts from all DONE steps in this run.
    5. Find next PENDING step; call build_input; enqueue with pre-assigned job_id.
    6. If no next step: mark WorkflowRun DONE.
    7. Commit.

    Args:
        job_id: RQ job ID of the completing job.
        output: Agent output — Pydantic BaseModel or dict. Serialized via
                model_dump(mode='json') if Pydantic, stored as-is if dict.
        session: SQLAlchemy session.
        queue: RQ Queue instance connected to "agent-tasks".
    """
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.models import (
        WorkflowRun,
        WorkflowRunStep,
        WorkflowStatus,
        WorkflowStepStatus,
    )

    step = (
        session.query(WorkflowRunStep)
        .filter(WorkflowRunStep.task_job_id == job_id)
        .first()
    )
    if step is None:
        logger.debug("on_step_complete: no workflow step found for job_id=%s (direct task)", job_id)
        return

    # Extract JSON artifact from agent output
    if isinstance(output, dict) and "messages" in output:
        artifact = _extract_task_output(output)
    elif hasattr(output, "model_dump"):
        artifact = output.model_dump(mode="json")
    elif isinstance(output, dict):
        artifact = output
    else:
        artifact = {"result": str(output)}

    step.artifact = artifact
    step.status = WorkflowStepStatus.DONE
    step.completed_at = datetime.now(timezone.utc)
    session.flush()

    # Build accumulated_artifacts from all DONE steps for this run
    done_steps = (
        session.query(WorkflowRunStep)
        .filter(
            WorkflowRunStep.workflow_run_id == step.workflow_run_id,
            WorkflowRunStep.status == WorkflowStepStatus.DONE,
        )
        .all()
    )
    accumulated_artifacts: dict[str, dict] = {
        s.step_key: s.artifact for s in done_steps
    }

    # Find the WorkflowRun for this step
    run = session.query(WorkflowRun).filter(WorkflowRun.id == step.workflow_run_id).first()

    # Find the next PENDING step
    next_step = (
        session.query(WorkflowRunStep)
        .filter(
            WorkflowRunStep.workflow_run_id == step.workflow_run_id,
            WorkflowRunStep.status == WorkflowStepStatus.PENDING,
        )
        .order_by(WorkflowRunStep.step_order)  # deterministic step ordering
        .first()
    )

    if next_step is not None:
        # Enqueue next step — pre-assign job_id before commit (D-07)
        workflow_def = WORKFLOW_REGISTRY[run.workflow_type]
        next_step_def = next(
            s for s in workflow_def.steps if s.step_key == next_step.step_key
        )
        next_job_id = str(uuid.uuid4())
        task_input = next_step_def.build_input(dict(run.shared_context), accumulated_artifacts)

        queue.enqueue(
            "robotina.queue.jobs.run_task",
            task_input,
            job_id=next_job_id,
            meta={"task_type": next_step.task_type, "queue_name": queue.name},
            result_ttl=-1,
            failure_ttl=-1,
        )

        next_step.task_job_id = next_job_id
        session.commit()
        logger.info(
            "Step complete, advanced | run_id=%s completed_step=%s next_step=%s next_job_id=%s",
            step.workflow_run_id,
            step.step_key,
            next_step.step_key,
            next_job_id,
        )
    else:
        # Final step — mark WorkflowRun DONE
        run.status = WorkflowStatus.DONE
        session.commit()
        logger.info(
            "Workflow complete | run_id=%s final_step=%s",
            step.workflow_run_id,
            step.step_key,
        )


def on_step_failed(job_id: str, session: Session, queue=None) -> None:
    """Mark step FAILED, cancel all remaining PENDING steps, mark WorkflowRun FAILED.

    The failed RQ job is retained in RQ's FailedJobRegistry by the caller
    (run_task re-raises the exception after calling this function).

    Quick task 260509-ln9: when ``queue`` is provided AND the WorkflowRun's
    ``shared_context.reply_context`` is populated, also enqueue a single
    ``send-notification`` job at the front of the queue with a Spanish apology
    so terminal failures don't go silent. This is best-effort — any error in
    the dead-letter block is logged and swallowed (the workflow is already
    FAILED; we don't cascade).

    Args:
        job_id: RQ job ID of the failing job.
        session: SQLAlchemy session.
        queue: RQ Queue instance connected to "agent-tasks". Optional; when
               omitted, the dead-letter hook is skipped (preserves
               backward-compatibility for tests that don't pass a queue).
    """
    from robotina.queue.models import (
        WorkflowRun,
        WorkflowRunStep,
        WorkflowStatus,
        WorkflowStepStatus,
    )

    step = (
        session.query(WorkflowRunStep)
        .filter(WorkflowRunStep.task_job_id == job_id)
        .first()
    )
    if step is None:
        logger.debug("on_step_failed: no workflow step found for job_id=%s (direct task)", job_id)
        return

    step.status = WorkflowStepStatus.FAILED
    session.flush()

    # Cancel all remaining PENDING steps
    pending_steps = (
        session.query(WorkflowRunStep)
        .filter(
            WorkflowRunStep.workflow_run_id == step.workflow_run_id,
            WorkflowRunStep.status == WorkflowStepStatus.PENDING,
        )
        .all()
    )
    for pending in pending_steps:
        pending.status = WorkflowStepStatus.CANCELLED

    # Mark WorkflowRun FAILED
    run = session.query(WorkflowRun).filter(WorkflowRun.id == step.workflow_run_id).first()
    run.status = WorkflowStatus.FAILED
    session.commit()

    logger.error(
        "Step failed | run_id=%s step_key=%s job_id=%s cancelled_steps=%d",
        step.workflow_run_id,
        step.step_key,
        job_id,
        len(pending_steps),
    )

    # Dead-letter: notify user that their request failed (quick task 260509-ln9).
    # Best-effort: never raise from this block — the workflow is already FAILED.
    if queue is None:
        return
    try:
        reply_context = (run.shared_context or {}).get("reply_context") if run is not None else None
        required = ("platform", "chat_id", "user_id")
        if not isinstance(reply_context, dict) or not all(k in reply_context and reply_context[k] for k in required):
            logger.warning(
                "Workflow failed without reply_context; skipping dead-letter | run_id=%s workflow_type=%s",
                step.workflow_run_id,
                run.workflow_type if run is not None else "<unknown>",
            )
            return

        from robotina.queue.task_types import SendNotificationInput

        apology_text = (
            f"Algo falló procesando tu pedido ({run.workflow_type}). Disculpá las molestias."
        )
        task_input = SendNotificationInput(
            platform=reply_context["platform"],
            chat_id=reply_context["chat_id"],
            user_id=reply_context["user_id"],
            text=apology_text,
        )
        queue.enqueue(
            "robotina.queue.jobs.run_task",
            task_input,
            result_ttl=-1,
            failure_ttl=-1,
            meta={"task_type": "send-notification"},
            at_front=True,
        )
        logger.info(
            "Dead-letter notification enqueued | run_id=%s workflow_type=%s",
            step.workflow_run_id,
            run.workflow_type,
        )
    except Exception:
        logger.exception(
            "Dead-letter enqueue failed; swallowing | run_id=%s",
            step.workflow_run_id,
        )
