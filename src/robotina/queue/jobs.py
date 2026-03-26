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

from langchain_core.callbacks import BaseCallbackHandler
from rq import get_current_job

logger = logging.getLogger(__name__)


class AgentLoggingHandler(BaseCallbackHandler):
    """LangChain callback handler for structured agent action logging.

    Logs three lifecycle events:
    - Chat model start (model name) — on_chat_model_start, not on_llm_start (chat models only)
    - Tool call (tool name + first 200 chars of input)
    - Tool result (first 200 chars of output)

    This is the single location for agent action logging. Individual agents do NOT
    need to emit their own tool-call log lines.
    """

    def on_chat_model_start(self, serialized: dict, messages: list, **kwargs) -> None:
        logger.info("LLM stream start | model=%s", serialized.get("name"))

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
        logger.info(
            "Tool call | tool=%s input=%s",
            serialized.get("name"),
            str(input_str)[:200],
        )

    def on_tool_end(self, output: str, **kwargs) -> None:
        logger.info("Tool result | output=%s", str(output)[:200])


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

    Phase 5 will add workflow state management around this core flow.

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
    return result


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
