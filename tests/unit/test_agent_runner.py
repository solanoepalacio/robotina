import pytest


def test_run_task_reads_task_type_from_job_meta():
    """AGENT-06: run_task reads task_type from RQ job meta, not from input model."""
    pytest.skip("not implemented")


def test_run_task_raises_if_no_task_type_in_meta():
    """AGENT-06: run_task raises ValueError when task_type missing from job meta."""
    pytest.skip("not implemented")


def test_backend_instantiated_per_job_not_module_level():
    """AGENT-07: LLM backend is created inside run_task, not at import time."""
    pytest.skip("not implemented")


def test_agent_logging_handler_on_llm_start():
    """AGENT-10: AgentLoggingHandler.on_llm_start logs LLM stream start."""
    pytest.skip("not implemented")


def test_agent_logging_handler_on_tool_start():
    """AGENT-10: AgentLoggingHandler.on_tool_start logs tool name and input."""
    pytest.skip("not implemented")


def test_agent_logging_handler_on_tool_end():
    """AGENT-10: AgentLoggingHandler.on_tool_end logs tool output."""
    pytest.skip("not implemented")
