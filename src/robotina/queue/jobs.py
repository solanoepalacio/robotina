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

from robotina.agent.callbacks import AgentLoggingHandler

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
    7. Create and invoke the ReAct agent with AgentLoggingHandler
    8. Return agent output

    Phase 5: Workflow state management wraps the agent execution via inline calls
    to workflow_runner (on_step_start, on_step_complete, on_step_failed). If the
    job is not part of a workflow (direct task), these are no-ops (D-06).

    Args:
        task_input: Pydantic input model for the task (e.g. IncomingMessageInput).
                    The task type is NOT read from this model — it comes from job meta.

    Returns:
        Agent invocation result (messages list from create_react_agent).

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

    try:
        # Step 2: Look up AgentConfig (includes AGENT_OVERRIDES_FILEPATH hot-reload)
        from robotina.agent.agents import get_agent_config
        config = get_agent_config(task_type)

        # Step 3: Instantiate LLM backend (ALWAYS per-job — never at module level)
        from robotina.llm import make_backend
        backend = make_backend(config.model_config)

        # Step 4: Build skill context (lazy import — SkillSet defined in Plan 05)
        from robotina.agent import SkillSet, build_read_skill_tool
        skill_sets = [SkillSet(s) for s in config.skills]
        skill_index = "\n\n".join(ss.index_content for ss in skill_sets)
        tools = list(config.tools)
        if skill_sets:
            tools.append(build_read_skill_tool(skill_sets))

        # Phase 6: Inject per-job tools that require task_input context (D-05)
        # SendNotificationTool needs chat_id/user_id/platform from task_input — cannot be in AgentConfig
        if task_type == "send-notification":
            from robotina.agent.tools.send_notification import SendNotificationTool
            tools.append(SendNotificationTool(
                chat_id=task_input.chat_id,
                user_id=task_input.user_id,
                platform=task_input.platform,
            ))
        elif task_type == "handle-incoming-message":
            from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
            from robotina.agent.tools.queue import QueueTool
            from robotina.agent.tools.start_workflow import StartWorkflowTool
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
            ))

        # Step 5 + 6: Load versioned prompt and append skill index
        prompt_text = Path(config.prompt_path).read_text()
        if skill_index:
            prompt_text = prompt_text + "\n\n" + skill_index

        # Step 7: Create and invoke agent
        # @langwatch.trace() creates the parent trace; get_langchain_callback() captures
        # LangChain events (LLM calls, tool calls) as child spans under that trace.
        # This is the approach documented at langwatch.ai/docs/integration/python/integrations/langchain
        agent = backend.create_agent(system_prompt=prompt_text, tools=tools)
        user_message = _extract_user_message(task_input)

        try:
            import langwatch
            import langwatch.langchain
            from langchain_core.runnables import RunnableConfig
            with langwatch.trace():
                result = agent.invoke(
                    {"messages": [{"role": "user", "content": user_message}]},
                    config=RunnableConfig(
                        callbacks=[AgentLoggingHandler(), langwatch.langchain.LangChainTracer()]
                    ),
                )
        except ImportError:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_message}]},
                config={"callbacks": [AgentLoggingHandler()]},
            )

        logger.info("Agent run complete | task_type=%s", task_type)

        # Workflow hook: persist artifact + advance to next step or mark WorkflowRun DONE
        workflow_runner.on_step_complete(job.id, result, _session, _queue)
        return result

    except Exception:
        # Workflow hook: mark step FAILED, cancel pending steps, mark WorkflowRun FAILED
        workflow_runner.on_step_failed(job.id, _session)
        raise  # re-raise so RQ moves the job to FailedJobRegistry

    finally:
        _session.close()


def _extract_user_message(task_input) -> str:
    """Extract the user-facing message text from any task input model.

    For Phase 4 hello-world testing, accepts any input and returns a default.
    Phase 5+ agents will use properly typed inputs with specific fields.
    """
    # IncomingMessageInput has a 'text' field
    if hasattr(task_input, "text"):
        return str(task_input.text)
    # Fallback for hello-world placeholder and unknown types
    return str(task_input)
