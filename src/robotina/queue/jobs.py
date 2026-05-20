"""Universal RQ job function for all Robotina task types.

run_task() is the single entry point for every job enqueued to 'agent-tasks'.
It reads the task type from RQ job metadata, looks up the agent configuration,
instantiates the LLM backend, builds skill context, loads the prompt, and
invokes the agent.

IMPORTANT: All per-job objects (LLM backend, skill sets, agent runnable) MUST be
created INSIDE run_task(). Never instantiate them at module level or as class
attributes — this is a locked architectural constraint from STATE.md Phase 4.

Phase 5 will wrap run_task() with workflow state management (mark step RUNNING,
persist artifact, advance to next step). Keep this function clean and focused on
agent execution only.
"""
from __future__ import annotations

import logging
from pathlib import Path

from rq import get_current_job

# AGENT-13 / Phase 12: AgentLoggingHandler removed; per-agent log lines are now
# emitted by robotina.agent.middleware (wired through LLMBackend.create_agent).

logger = logging.getLogger(__name__)


def run_task(task_input) -> object:
    """Universal RQ job function for all task types.

    Execution flow:
    1. Read task_type from RQ job meta (set by gateway handler.py)
    2. Look up AgentConfig from agents.py registry
    3. Instantiate LLM backend (per-job — never module-level)
    4. Build skill context (SkillSet instances + ReadSkillTool)
    5. Load versioned system prompt from AgentConfig.prompt_path
    6. Append skill index content to system prompt
    7. Create and invoke the agent (per-agent logging emitted by middleware; LangWatch trace via callback bus).
    8. Return agent output

    Phase 5: Workflow state management wraps the agent execution via inline calls
    to workflow_runner (on_step_start, on_step_complete, on_step_failed). If the
    job is not part of a workflow (direct task), these are no-ops (D-06).

    Args:
        task_input: Pydantic input model for the task (e.g. IncomingMessageInput).
                    The task type is NOT read from this model — it comes from job meta.

    Returns:
        Agent invocation result (messages list from langchain.agents.create_agent).

    Raises:
        ValueError: If job has no task_type in meta.
        KeyError: If task_type is not registered in agents.py registry.
        KeyError: If required API token env var is not set.
    """
    # Step 1: Read task type from RQ job metadata (not from input model)
    job = get_current_job()
    task_type = job.meta.get("task_type") if job else None
    if not task_type:
        raise ValueError(
            "run_task: job has no task_type in meta. "
            "Ensure all enqueue() calls set meta={'task_type': '<type>'}."
        )
    logger.info("Running Task | Type=%s", task_type)

    # Phase 5: Workflow state management setup (D-08)
    # All per-job objects instantiated here — never at module level (locked Phase 4)
    from robotina.db import SessionLocal
    from robotina.queue import workflow_runner
    from rq import Queue
    from redis import Redis
    import os

    _session = SessionLocal()
    _queue_name = job.meta.get("queue_name", "agent-tasks")
    _queue = Queue(
        _queue_name,
        connection=Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379")),
    )

    # Workflow hook: mark step RUNNING (no-op for direct tasks — D-06)
    workflow_runner.on_step_start(job.id, _session)

    # Phase 07.1: deterministic non-LLM path for send-notification.
    # send-notification is a pure delivery call (escape + send_message); wrapping
    # it in a ReAct agent loop is what allowed the duplicate-message and
    # infinite-loop bugs. Plain text — no MarkdownV2 escaping.
    if task_type == "send-notification":
        from robotina.gateway.send import send_message
        import asyncio
        try:
            result = asyncio.run(send_message(
                chat_id=task_input.chat_id,
                text=task_input.text,
                user_id=task_input.user_id,
                parse_mode=None,
            ))
            artifact = {"message_id": result.message_id}
            logger.info(
                "send-notification delivered | chat_id=%s message_id=%s",
                task_input.chat_id,
                result.message_id,
            )
            workflow_runner.on_step_complete(job.id, artifact, _session, _queue)
            return artifact
        except Exception as exc:  # DASH-03 / Phase 13
            workflow_runner.on_step_failed(job.id, _session, _queue, exc=exc)
            raise
        finally:
            _session.close()

    # WAKE-04 / D-01: deterministic agent-less branch for `finalize-outcome`.
    # Mirrors the send-notification branch shape (no LLM, no skills, no prompt).
    # Composes the AddRecipeOutcome from accumulated artifacts (passed in via
    # FinalizeOutcomeInput by the workflow's build_input lambda) and writes it to
    # WorkflowRun.outcome before the step-complete hook commits.
    if task_type == "finalize-outcome":
        from robotina.queue.task_types import AddRecipeOutcome
        from robotina.queue.models import WorkflowRun, WorkflowRunStep
        try:
            load = task_input.load or {}
            recipe_id = load.get("recipe_id") if isinstance(load, dict) else None
            if recipe_id:
                outcome = AddRecipeOutcome(
                    status="success",
                    recipe_id=recipe_id,
                    recipe_name=load.get("recipe_name"),
                    recipe_slug=load.get("recipe_slug") or None,
                    image_present=False,  # the recipe-image milestone flips this
                )
            else:
                outcome = AddRecipeOutcome(
                    status="failure",
                    failure_reason=(
                        task_input.failure_reason
                        or "finalize-outcome called without a load artifact"
                    ),
                )

            # Locate the WorkflowRun via the step's task_job_id and stamp outcome.
            step = (
                _session.query(WorkflowRunStep)
                .filter(WorkflowRunStep.task_job_id == job.id)
                .first()
            )
            if step is not None:
                run = (
                    _session.query(WorkflowRun)
                    .filter(WorkflowRun.id == step.workflow_run_id)
                    .first()
                )
                if run is not None:
                    run.outcome = outcome.model_dump(mode="json")
                    _session.flush()

            artifact = outcome.model_dump(mode="json")
            workflow_runner.on_step_complete(job.id, artifact, _session, _queue)
            return artifact
        except Exception as exc:
            workflow_runner.on_step_failed(job.id, _session, _queue, exc=exc)
            raise
        finally:
            _session.close()

    try:
        # Step 2: Look up AgentConfig (includes AGENT_OVERRIDES_FILEPATH hot-reload)
        from robotina.agent.agents import get_agent_config
        config = get_agent_config(task_type)

        # Step 3: Instantiate LLM backend (ALWAYS per-job — never at module level)
        from robotina.llm import make_backend
        backend = make_backend(config.model_config)

        # Step 4: Build skill context (lazy import — SkillSet defined in Plan 05)
        from robotina.agent.tools.read_skill import SkillSet, build_read_skill_tool
        skill_sets = [SkillSet(s) for s in config.skills]
        skill_index = "\n\n".join(ss.index_content for ss in skill_sets)
        tools = list(config.tools)
        if skill_sets:
            tools.append(build_read_skill_tool(skill_sets))

        # Phase 6: Inject per-job tools that require task_input context (D-05).
        # send-notification is handled by the deterministic branch above (Phase 07.1)
        # and never reaches this point.
        if task_type == "handle-incoming-message":
            from datetime import datetime as _datetime
            import os as _os
            from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
            from robotina.agent.tools.queue import QueueTool
            from robotina.agent.tools.start_workflow import StartWorkflowTool
            from robotina.gateway.models import Conversation, Platform
            from robotina.queue.models import (
                InvocationStatus,
                InvocationTrigger,
                RobotinaInvocation,
            )

            # Phase 20 / D-07: invocation_id flows through ``job.meta`` for
            # BOTH USER_MESSAGE (gateway-enqueued) and WORKFLOW_COMPLETION
            # (wake-enqueued) jobs. Bracket read — missing key is an invariant
            # violation; fail loud (KeyError) is the contract.
            invocation_id = job.meta["invocation_id"]
            inv = _session.get(RobotinaInvocation, invocation_id)
            if inv is None:
                raise RuntimeError(
                    f"RobotinaInvocation {invocation_id!r} not found in DB"
                )

            # Phase 20 / D-10: PENDING → RUNNING transition. Commit so the
            # dashboard reflects state even if the agent run is long. DONE /
            # FAILED + completed_at writes happen in the outer try/except/else
            # at the bottom of run_task — no inner flag needed.
            inv.status = InvocationStatus.RUNNING
            inv.started_at = _datetime.utcnow()
            _session.commit()

            if inv.trigger == InvocationTrigger.USER_MESSAGE:
                # Phase 17 / ARCH-01 / D-04: USER_MESSAGE path — task_input is
                # IncomingMessageInput. Resolve the Conversation row via the
                # message's (platform, chat_id) pair. The gateway upserts the
                # Conversation BEFORE enqueuing so the row IS guaranteed
                # present; ``.one()`` raises on miss = fail loud.
                conversation = (
                    _session.query(Conversation)
                    .filter_by(
                        platform=Platform(task_input.platform),
                        chat_id=task_input.chat_id,
                    )
                    .one()
                )
                tools.append(HouseholdManagerApiTool(household_id=task_input.household_id))
                tools.append(QueueTool(
                    chat_id=task_input.chat_id,
                    user_id=task_input.user_id,
                    platform=task_input.platform,
                ))
                tools.append(StartWorkflowTool(
                    chat_id=task_input.chat_id,
                    user_id=task_input.user_id,
                    platform=task_input.platform,
                    household_id=task_input.household_id,
                    conversation_id=conversation.id,
                    invocation_id=invocation_id,
                ))
            elif inv.trigger == InvocationTrigger.WORKFLOW_COMPLETION:
                # Phase 20 / WAKE-04 / D-07: wake path. task_input is
                # WakeInvocationInput; conversation / platform identifiers are
                # resolved from the invocation row's conversation_id (PK
                # lookup, not the .filter_by(platform, chat_id).one() form
                # because the wake input doesn't carry those redundantly).
                conversation = _session.get(Conversation, inv.conversation_id)
                if conversation is None:
                    raise RuntimeError(
                        f"Conversation {inv.conversation_id!r} missing for wake "
                        f"invocation {inv.id!r}"
                    )
                # Bracket form — fail loud (Phase 16 dual-guard pattern).
                household_id = _os.environ["HOUSEHOLD_ID"]
                platform_value = conversation.platform.value
                # Conversation does not store a user_id (group chats can have
                # many users; the originating user lives transiently on
                # IncomingMessageInput, not on the Conversation row). The wake
                # path has no originating user — it is a follow-up to a workflow.
                # Tools are wired with chat_id as the user_id placeholder so the
                # constructors validate; V004 instructs the agent NOT to call
                # queue/start-workflow on wake turns, so these placeholders
                # remain decorative until Phase 21 replaces this tool surface.
                wake_user_id = conversation.chat_id
                tools.append(HouseholdManagerApiTool(household_id=household_id))
                tools.append(QueueTool(
                    chat_id=conversation.chat_id,
                    user_id=wake_user_id,
                    platform=platform_value,
                ))
                tools.append(StartWorkflowTool(
                    chat_id=conversation.chat_id,
                    user_id=wake_user_id,
                    platform=platform_value,
                    household_id=household_id,
                    conversation_id=conversation.id,
                    invocation_id=inv.id,
                ))
            else:
                raise RuntimeError(
                    f"unsupported invocation trigger: {inv.trigger!r}"
                )
        elif task_type == "recipe-research-gather":
            from robotina.agent.tools.web_search import WebSearchTool
            tools.append(WebSearchTool())
        elif task_type == "recipe-research-ingredients":
            # Phase 15: ingredients agent gets the two validation tools so it
            # can resolve Spanish food/unit names to household-manager catalog
            # ids before emitting the next RecipeData snapshot. Tools are
            # zero-arg (per D-10 — catalog is shared per household).
            from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
            from robotina.agent.tools.validate_foods import ValidateFoodsTool
            from robotina.agent.tools.validate_units import ValidateUnitsTool
            tools.append(HouseholdManagerApiTool(household_id=task_input.household_id))
            tools.append(ValidateFoodsTool())
            tools.append(ValidateUnitsTool())
        elif task_type == "recipe-load":
            # Phase 15: recipe-load V005 happy path is a thin POST that trusts
            # the food_id / unit_id already on each ingredient. The two
            # validation tools are injected for RECOVERY ONLY — on a non-2xx
            # POST response the agent can re-resolve an offending id and retry
            # (D-17). Zero-arg per D-10 (catalog is shared per household).
            from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
            from robotina.agent.tools.validate_foods import ValidateFoodsTool
            from robotina.agent.tools.validate_units import ValidateUnitsTool
            tools.append(HouseholdManagerApiTool(household_id=task_input.household_id))
            tools.append(ValidateFoodsTool())
            tools.append(ValidateUnitsTool())
        elif task_type == "acknowledge-add-recipe":
            from robotina.agent.tools.queue import QueueTool
            tools.append(QueueTool(
                chat_id=task_input.chat_id,
                user_id=task_input.user_id,
                platform=task_input.platform,
            ))

        # Step 5 + 6: Load versioned prompt and append skill index
        prompt_text = Path(config.prompt_path).read_text()
        if skill_index:
            prompt_text = prompt_text + "\n\n" + skill_index

        # Step 7: Create and invoke agent
        # @langwatch.trace() creates the parent trace; get_langchain_callback() captures
        # LangChain events (LLM calls, tool calls) as child spans under that trace.
        # This is the approach documented at langwatch.ai/docs/integration/python/integrations/langchain
        #
        # Phase 11: thread response_format through. For agents with
        # config.response_format_model = None (handle-incoming-message,
        # acknowledge-add-recipe), the adapter omits the kwarg entirely (see
        # LLMBackend Protocol implementations in src/robotina/llm/__init__.py).
        agent = backend.create_agent(
            system_prompt=prompt_text,
            tools=tools,
            response_format=config.response_format_model,
        )
        user_message = task_input.to_user_message()

        try:
            import langwatch
            import langwatch.langchain
            from langchain_core.runnables import RunnableConfig
            with langwatch.trace():
                result = agent.invoke(
                    {"messages": [{"role": "user", "content": user_message}]},
                    config=RunnableConfig(
                        # AGENT-13 / Phase 12: subtractive — AgentLoggingHandler removed,
                        # LangWatch tracer retained (RESEARCH Pitfall 1: list must be non-empty
                        # for LangWatch traces to be emitted via the callback bus).
                        callbacks=[langwatch.langchain.LangChainTracer()]
                    ),
                )
        except ImportError:
            # AGENT-13 / Phase 12: middleware now emits per-agent log lines without needing
            # a callback. langwatch missing → no tracer needed; drop the config= kwarg entirely.
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_message}]},
            )

        logger.info("Agent run complete | task_type=%s", task_type)

        # Workflow hook: persist artifact + advance to next step or mark WorkflowRun DONE
        workflow_runner.on_step_complete(job.id, result, _session, _queue)
        # Phase 20 / D-10: invocation lifecycle DONE transition for
        # handle-incoming-message jobs (both USER_MESSAGE and WORKFLOW_COMPLETION
        # triggers). Other task types have no invocation row.
        if task_type == "handle-incoming-message":
            _write_invocation_terminal_status(
                _session, job, terminal="done"
            )
        return result

    except Exception as exc:  # DASH-03 / Phase 13
        # Workflow hook: mark step FAILED, cancel pending steps, mark WorkflowRun FAILED
        workflow_runner.on_step_failed(job.id, _session, _queue, exc=exc)
        # Phase 20 / D-10: invocation lifecycle FAILED transition.
        if task_type == "handle-incoming-message":
            _write_invocation_terminal_status(
                _session, job, terminal="failed"
            )
        raise  # re-raise so RQ moves the job to FailedJobRegistry

    finally:
        _session.close()


def _write_invocation_terminal_status(session, job, *, terminal: str) -> None:
    """Phase 20 / D-10: write DONE/FAILED + completed_at on the
    RobotinaInvocation row that owns this handle-incoming-message job.

    Defensive — never raises. The terminal status writes are best-effort:
    a failure here must not mask the real job exception (in the FAILED
    branch) nor convert a happy return into a failure (in the DONE branch).
    """
    from datetime import datetime as _datetime
    from robotina.queue.models import (
        InvocationStatus,
        RobotinaInvocation,
    )

    try:
        invocation_id = job.meta.get("invocation_id") if job else None
        if not invocation_id:
            return
        inv = session.get(RobotinaInvocation, invocation_id)
        if inv is None:
            return
        inv.status = (
            InvocationStatus.DONE
            if terminal == "done"
            else InvocationStatus.FAILED
        )
        inv.completed_at = _datetime.utcnow()
        session.commit()
    except Exception:
        logger.exception(
            "Failed to write invocation %s status",
            terminal,
        )


