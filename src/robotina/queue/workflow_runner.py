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

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from robotina.queue.task_types import NonEmptyHouseholdId

logger = logging.getLogger(__name__)

# WR-02: cap stored failure_reason length. The D-16 format string
# (f"{type(exc).__name__}: {exc}") is SPEC-locked, so we cannot scrub
# content — only bound it. 500 chars accommodates typical exception
# messages (HTTP error bodies tend to be the long tail) while keeping
# the dashboard cell render legible.
_FAILURE_REASON_MAX_CHARS = 500


def _extract_task_output(result: dict, *, expects_structured: bool = False) -> dict:
    """Extract a JSON-serializable artifact from a langchain.agents.create_agent result.

    Phase 11 refactor: prefer ``result['structured_response']`` (a Pydantic
    instance populated by ``create_agent(response_format=...)``) over
    free-text parsing. The legacy free-text JSON parse fallback ladder
    (prose-strip, markdown-code-fence stripping, first-brace scan, retry
    parse) is REMOVED — with ``response_format`` bound on every
    artifact-producing agent (RRECIPE-07, RLOAD-07) it is unreachable on
    the success path, and a footgun for any new agent added without
    ``response_format``.

    Args:
        result: The dict returned by ``agent.invoke({"messages": [...]})``.
                Contains "messages" (list[BaseMessage]) and, when
                response_format was bound, "structured_response" (a Pydantic
                BaseModel instance).
        expects_structured: True when the executing agent has
                ``response_format`` bound (the caller — on_step_complete —
                resolves this from AgentConfig.response_format_model). When
                True, this function REQUIRES result['structured_response']
                to be a BaseModel and returns ``instance.model_dump(mode='json')``.
                When False, only the return_direct tool-message branch is
                available.

    Returns:
        A JSON-serializable dict suitable for ``WorkflowRunStep.artifact``.

    Raises:
        ValueError: When expects_structured=True and structured_response is
            missing / None / not a BaseModel — i.e., regression on a bound
            agent. Also when expects_structured=False and the final message
            is not a ToolMessage (no return_direct short-circuit) — i.e., a
            non-structured agent produced free-text, which Phase 11
            deliberately refuses to silently consume.
    """
    if expects_structured:
        sr = result.get("structured_response")
        if isinstance(sr, BaseModel):
            return sr.model_dump(mode="json")
        if sr is None:
            raise ValueError(
                "structured_response missing on response_format agent result; "
                "this is a regression — the agent did not populate the typed "
                "output channel. Check the agent's create_agent kwargs and "
                "the bound Pydantic schema."
            )
        # Defensive: structured_response could in theory be a dict for
        # JSON-schema schemas, but Robotina only uses Pydantic models, so
        # treat anything else as a regression.
        raise ValueError(
            f"structured_response is not a BaseModel: type={type(sr).__name__}"
        )

    # No response_format on this agent — preserve the return_direct tool-message path
    # (Phase 07.1: QueueTool / StartWorkflowTool short-circuit the graph).
    last = result["messages"][-1]
    if getattr(last, "type", None) == "tool":
        return {"tool_message": str(last.content)}

    # Phase 11: there is no longer a free-text fallback for non-tool-message
    # finals. Any non-structured agent landing here is a bug.
    raise ValueError(
        f"Agent produced no structured_response and no terminal ToolMessage; "
        f"last message type={getattr(last, 'type', None)!r}"
    )


def queue_workflow(
    workflow_type: str,
    shared_context: dict,
    household_id: NonEmptyHouseholdId,
    conversation_id: str,
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
        conversation_id: FK to Conversation that originated this workflow run.
            Resolved by run_task (jobs.py handle-incoming-message branch) via
            session.query(Conversation).filter_by(platform=..., chat_id=...).one()
            and constructor-injected into StartWorkflowTool. No Python-level guard
            here — FK NOT NULL + upstream .one() raise carry the invariant
            (ARCH-01, Phase 17 / D-04 / D-05).
        queue: RQ Queue instance connected to "agent-tasks".
        session: SQLAlchemy session (injected for testability — D-11).

    Returns:
        workflow_run_id: UUID string of the created WorkflowRun.

    Raises:
        KeyError: If workflow_type not in WORKFLOW_REGISTRY.
    """
    # Phase 16 — REQ-HID-4 / RESEARCH Pattern 7: last-line-of-defense before any
    # WorkflowRun row is written. Reaching this branch with an empty household_id
    # means every upstream guard (gateway boot in __init__.py::main, Pydantic
    # NonEmptyHouseholdId on task-input models, and tool-constructor validation
    # on HouseholdManagerApiTool / StartWorkflowTool) was bypassed.
    if not household_id or not household_id.strip():
        raise ValueError(
            "queue_workflow refuses empty household_id; this indicates "
            "HOUSEHOLD_ID was not propagated from the gateway. Check "
            "gateway/__init__.py boot guard, IncomingMessageInput.household_id "
            "validation, and StartWorkflowTool.household_id field."
        )

    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.models import WorkflowRun, WorkflowRunStep, WorkflowStatus, WorkflowStepStatus

    workflow_def = WORKFLOW_REGISTRY[workflow_type]

    # Create the WorkflowRun as PENDING (transitions to RUNNING when first step begins)
    run = WorkflowRun(
        workflow_type=workflow_type,
        household_id=household_id,
        conversation_id=conversation_id,
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

    # DASH-02 / Phase 13: persist step_input before commit so the dashboard
    # can display the exact input the agent was invoked with. Mirrors the
    # artifact serialization pattern in on_step_complete (~line 274-279).
    if hasattr(task_input, "model_dump"):
        first_step.step_input = task_input.model_dump(mode="json")
    else:
        first_step.step_input = task_input

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

    # Extract JSON artifact from agent output. Phase 11: resolve whether this
    # task's agent has response_format bound — that determines whether
    # _extract_task_output should read structured_response (and fail loudly on
    # missing) or fall back to the return_direct tool-message branch.
    if isinstance(output, dict) and "messages" in output:
        from robotina.agent.agents import get_agent_config
        try:
            agent_config = get_agent_config(step.task_type)
            expects_structured = agent_config.response_format_model is not None
        except KeyError:
            # Task type not in registry (e.g. send-notification post-07.1 has
            # been removed; the deterministic Python path in jobs.py builds its
            # own artifact and never reaches this branch). Treat as
            # non-structured to preserve existing tool_message fallback.
            expects_structured = False
        artifact = _extract_task_output(output, expects_structured=expects_structured)
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

        # DASH-02 / Phase 13: persist step_input before commit (same pattern as
        # the first-step site in queue_workflow).
        if hasattr(task_input, "model_dump"):
            next_step.step_input = task_input.model_dump(mode="json")
        else:
            next_step.step_input = task_input

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


def on_step_failed(
    job_id: str,
    session: Session,
    queue=None,
    *,
    exc: BaseException | None = None,
) -> None:
    """Mark step FAILED, cancel all remaining PENDING steps, mark WorkflowRun FAILED.

    The failed RQ job is retained in RQ's FailedJobRegistry by the caller
    (run_task re-raises the exception after calling this function).

    When ``queue`` is provided AND the WorkflowRun's
    ``shared_context.reply_context`` is populated, also enqueue a single
    ``send-notification`` job at the front of the queue with a Spanish apology
    so terminal failures don't go silent. This is best-effort — any error in
    the dead-letter block is logged and swallowed (the workflow is already
    FAILED; we don't cascade).

    When ``exc`` is provided (DASH-03 / Phase 13), persist a one-line
    ``failure_reason`` on the step using the format
    ``f"{type(exc).__name__}: {exc}"`` with embedded newlines collapsed to
    spaces (RESEARCH Pitfall 2). The format is fixed by SPEC constraint D-16
    — no traceback, no chained exceptions. The default ``exc=None`` preserves
    backward compatibility for direct-task callers (the early-return branch
    when ``step is None``) and for legacy tests that don't pass an exception.

    Args:
        job_id: RQ job ID of the failing job.
        session: SQLAlchemy session.
        queue: RQ Queue instance connected to "agent-tasks". Optional; when
               omitted, the dead-letter hook is skipped (preserves
               backward-compatibility for tests that don't pass a queue).
        exc: The live exception that caused the failure. Optional, keyword-only.
             When provided, drives the ``failure_reason`` column write.
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
    # DASH-03 / Phase 13: record one-line failure reason (D-16 format) when an
    # exception was threaded through by the caller. Newlines in exc.__str__()
    # are collapsed to spaces per RESEARCH Pitfall 2; .strip() removes any
    # trailing whitespace left by the substitution.
    #
    # WR-02: the D-16 format is SPEC-locked, so we cannot redact env-var
    # names, URLs, or payload fragments that some exception classes embed
    # in str(exc) (KeyError, httpx.HTTPStatusError, Pydantic ValidationError).
    # Trade-off accepted: cap the stored string at _FAILURE_REASON_MAX_CHARS
    # to bound blast radius, and rely on WR-01's loopback default so the
    # dashboard is not reachable by untrusted networks by default. Operators
    # who opt into DASHBOARD_HOST=0.0.0.0 inherit the residual leak risk.
    if exc is not None:
        reason = f"{type(exc).__name__}: {exc}".replace("\n", " ").strip()
        if len(reason) > _FAILURE_REASON_MAX_CHARS:
            reason = reason[: _FAILURE_REASON_MAX_CHARS - 1] + "…"
        step.failure_reason = reason
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

    # Mark WorkflowRun FAILED. The next dead-letter block defensively
    # treats `run` as possibly None (e.g., the parent row was deleted or
    # archived between the step write and this fetch), so we mirror that
    # nil-check here — otherwise the assignment crashes the worker on
    # the failure path (CR-01).
    run = session.query(WorkflowRun).filter(WorkflowRun.id == step.workflow_run_id).first()
    if run is not None:
        run.status = WorkflowStatus.FAILED
    session.commit()

    logger.error(
        "Step failed | run_id=%s step_key=%s job_id=%s cancelled_steps=%d",
        step.workflow_run_id,
        step.step_key,
        job_id,
        len(pending_steps),
    )

    # Dead-letter: best-effort apology so terminal failures don't go silent.
    # Never raise from this block — the workflow is already FAILED.
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
