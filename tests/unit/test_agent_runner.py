"""Tests for run_task() universal job function.

Tests verify:
- AGENT-06: run_task reads task_type from RQ job meta, not from input model
- AGENT-07: LLM backend is created inside run_task, not at module level
- OBS-06 (Phase 12): RunnableConfig.callbacks retains LangWatch tracer and
  drops the legacy AgentLoggingHandler (which now lives in middleware — see
  tests/unit/test_agent_middleware.py for the four log-line assertions).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_run_task_reads_task_type_from_job_meta():
    """AGENT-06: run_task reads task_type from RQ job meta, not from input model.

    Uses recipe-load (a real LLM agent task type). send-notification can't be used
    here since Phase 07.1 — it takes the deterministic non-LLM branch and never
    calls get_agent_config.
    """
    mock_job = MagicMock()
    mock_job.id = "job-rl-001"
    mock_job.meta = {"task_type": "recipe-load", "queue_name": "agent-tasks"}

    mock_config = MagicMock()
    mock_config.skills = []
    mock_config.tools = []
    mock_config.model_config = {
        "provider": "ollama",
        "url": "http://localhost:11434",
        "model": "llama3.2",
        "api_key_env": "TEST_TOKEN",
    }
    mock_config.prompt_path = "/tmp/test_prompt.md"

    mock_backend = MagicMock()
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {"messages": []}
    mock_backend.create_agent.return_value = mock_agent

    mock_session = MagicMock()
    mock_session_factory = MagicMock(return_value=mock_session)

    mock_task_input = MagicMock()
    mock_task_input.chat_id = "test-chat-1"
    mock_task_input.user_id = "test-user-1"
    mock_task_input.platform = "telegram"
    mock_task_input.household_id = "household-1"
    mock_task_input.to_user_message.return_value = "test message"

    with patch("robotina.queue.jobs.get_current_job", return_value=mock_job), \
         patch("robotina.agent.agents.get_agent_config", return_value=mock_config) as mock_get_config, \
         patch("robotina.llm.make_backend", return_value=mock_backend), \
         patch("pathlib.Path.read_text", return_value="system prompt"), \
         patch("robotina.db.SessionLocal", mock_session_factory), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete"), \
         patch("robotina.queue.workflow_runner.on_step_failed"):
        from robotina.queue.jobs import run_task
        run_task(mock_task_input)

    mock_get_config.assert_called_once_with("recipe-load")


def test_run_task_send_notification_takes_deterministic_path():
    """Phase 07.1: send-notification is delivered via direct send_message() call,
    no LLM agent invocation.
    """
    mock_job = MagicMock()
    mock_job.id = "job-sn-1"
    mock_job.meta = {"task_type": "send-notification", "queue_name": "agent-tasks"}

    mock_session = MagicMock()
    mock_send_result = MagicMock(message_id="42")

    mock_task_input = MagicMock()
    mock_task_input.chat_id = "chat-1"
    mock_task_input.user_id = "user-1"
    mock_task_input.platform = "telegram"
    mock_task_input.text = "hola"

    # send_message is async (awaited under asyncio.run in jobs.py). AsyncMock
    # ensures the returned object is awaitable — avoids relying on quirky
    # asyncio.run() tolerance of a MagicMock return value (IN-04).
    mock_send = AsyncMock(return_value=mock_send_result)

    with patch("robotina.queue.jobs.get_current_job", return_value=mock_job), \
         patch("robotina.gateway.send.send_message", new=mock_send), \
         patch("robotina.db.SessionLocal", return_value=mock_session), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete") as mock_complete, \
         patch("robotina.queue.workflow_runner.on_step_failed"), \
         patch("robotina.agent.agents.get_agent_config") as mock_get_config, \
         patch("robotina.llm.make_backend") as mock_make_backend:
        from robotina.queue.jobs import run_task
        result = run_task(mock_task_input)

    # send_message called exactly once with parse_mode=None (plain text).
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["parse_mode"] is None
    assert call_kwargs["chat_id"] == "chat-1"
    assert call_kwargs["text"] == "hola"

    # No LLM machinery touched.
    mock_get_config.assert_not_called()
    mock_make_backend.assert_not_called()

    # Workflow hook invoked with a plain dict artifact (not an agent message list).
    assert mock_complete.called
    artifact = mock_complete.call_args.args[1]
    assert artifact == {"message_id": "42"}
    assert result == {"message_id": "42"}


def test_run_task_raises_if_no_task_type_in_meta():
    """AGENT-06: run_task raises ValueError when task_type missing from job meta."""
    mock_job = MagicMock()
    mock_job.meta = {}  # empty meta — no task_type

    with patch("robotina.queue.jobs.get_current_job", return_value=mock_job):
        from robotina.queue.jobs import run_task
        with pytest.raises(ValueError, match="task_type"):
            run_task(MagicMock())


def test_backend_instantiated_per_job_not_module_level():
    """AGENT-07: LLM backend is created inside run_task, not at import time.

    Verifies that importing robotina.queue.jobs does NOT trigger any LLM model
    instantiation. The module is imported with LLM constructors patched to raise
    if called — a module-level call would fail the import itself.
    """
    import sys

    # Remove cached module if already imported
    for mod_name in list(sys.modules.keys()):
        if mod_name == "robotina.queue.jobs":
            del sys.modules[mod_name]

    called = []

    def raise_if_called(*args, **kwargs):
        called.append(True)
        raise AssertionError("LLM model instantiated at module level!")

    # Patch all LLM constructors to raise if called at import time
    with patch("langchain_ollama.ChatOllama", side_effect=raise_if_called), \
         patch("langchain_anthropic.ChatAnthropic", side_effect=raise_if_called), \
         patch("langchain_openai.ChatOpenAI", side_effect=raise_if_called):
        # This should succeed without calling any LLM constructor
        import robotina.queue.jobs  # noqa: F401

    assert not called, "LLM model was instantiated at module level during import!"


# --- OBS-06 / Phase 12: regression guards for callback-list invariants ---
# These two tests assert (1) the LangWatch tracer survives in the
# RunnableConfig.callbacks list passed to agent.invoke and (2) the legacy
# AgentLoggingHandler is no longer present. Both invariants are load-bearing:
# (1) protects LangWatch trace fidelity (RESEARCH Pitfall 1); (2) acts as a
# regression guard if a future hand re-adds the legacy callback.

def _run_task_capturing_invoke_config(mock_task_input=None):
    """Helper: drive run_task() once with a fully-mocked stack and return the
    `config` kwarg that was passed to agent.invoke. Used by both OBS-06 tests
    below. Uses recipe-load task type (deterministic non-LLM send-notification
    path skips agent.invoke entirely)."""
    mock_job = MagicMock()
    mock_job.id = "job-obs06-001"
    mock_job.meta = {"task_type": "recipe-load", "queue_name": "agent-tasks"}

    mock_config = MagicMock()
    mock_config.skills = []
    mock_config.tools = []
    mock_config.model_config = {
        "provider": "ollama",
        "url": "http://localhost:11434",
        "model": "llama3.2",
        "api_key_env": "TEST_TOKEN",
    }
    mock_config.prompt_path = "/tmp/test_prompt.md"

    mock_backend = MagicMock()
    mock_agent = MagicMock()
    captured = {}

    def capture_invoke(messages, config=None, **kwargs):
        captured["config"] = config
        return {"messages": []}

    mock_agent.invoke.side_effect = capture_invoke
    mock_backend.create_agent.return_value = mock_agent

    mock_session = MagicMock()
    mock_session_factory = MagicMock(return_value=mock_session)

    if mock_task_input is None:
        mock_task_input = MagicMock()
        mock_task_input.chat_id = "test-chat-1"
        mock_task_input.user_id = "test-user-1"
        mock_task_input.platform = "telegram"
        mock_task_input.household_id = "household-1"
        mock_task_input.to_user_message.return_value = "test message"

    with patch("robotina.queue.jobs.get_current_job", return_value=mock_job), \
         patch("robotina.agent.agents.get_agent_config", return_value=mock_config), \
         patch("robotina.llm.make_backend", return_value=mock_backend), \
         patch("pathlib.Path.read_text", return_value="system prompt"), \
         patch("robotina.db.SessionLocal", mock_session_factory), \
         patch("robotina.queue.workflow_runner.on_step_start"), \
         patch("robotina.queue.workflow_runner.on_step_complete"), \
         patch("robotina.queue.workflow_runner.on_step_failed"):
        from robotina.queue.jobs import run_task
        run_task(mock_task_input)

    return captured.get("config")


def _callback_class_names(config) -> list[str]:
    """Extract class names of callbacks from a RunnableConfig-like object.
    Handles both dict-style ({"callbacks": [...]}) and RunnableConfig (TypedDict
    that subscripts like a dict). Returns [] if no callbacks were configured."""
    if config is None:
        return []
    # RunnableConfig is a TypedDict — same subscription as dict.
    callbacks = config.get("callbacks") if hasattr(config, "get") else None
    if not callbacks:
        return []
    return [type(cb).__name__ for cb in callbacks]


def test_run_task_passes_langwatch_tracer():
    """OBS-06: agent.invoke is called with RunnableConfig.callbacks containing
    a langwatch.langchain.LangChainTracer instance (regression guard for
    Pitfall 1 — the LangWatch trace MUST survive the AgentLoggingHandler removal)."""
    config = _run_task_capturing_invoke_config()
    names = _callback_class_names(config)
    assert "LangChainTracer" in names, (
        f"Expected LangChainTracer in callbacks list. Got: {names}. "
        f"This regression breaks ALL LangWatch traces (RESEARCH Pitfall 1)."
    )


def test_legacy_callbacks_module_deleted():
    """OBS-06: the legacy ``robotina.agent.callbacks`` module is deleted and
    not importable. Split from ``test_run_task_does_not_pass_agent_logging_handler``
    so a failure here points unambiguously at module re-introduction (IN-05).
    """
    import importlib
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("robotina.agent.callbacks")


def test_run_task_does_not_pass_agent_logging_handler():
    """OBS-06: agent.invoke callbacks list does NOT contain any
    AgentLoggingHandler. Split from ``test_legacy_callbacks_module_deleted``
    (IN-05) so a failure here points unambiguously at callback-wiring
    regression (someone re-added the handler to the callbacks list), rather
    than at module re-introduction.
    """
    config = _run_task_capturing_invoke_config()
    names = _callback_class_names(config)
    assert "AgentLoggingHandler" not in names, (
        f"Legacy AgentLoggingHandler reappeared in callbacks list: {names}. "
        f"Phase 12 removal must stay removed."
    )


def test_run_task_injects_all_four_tools_for_handle_incoming_message():
    """Phase 21 D-01/D-02/D-06: run_task() injects HouseholdManagerApiTool,
    RespondTool, TerminateTool, StartWorkflowTool for task_type ==
    'handle-incoming-message' (legacy queue tool retired)."""
    from unittest.mock import MagicMock, patch

    mock_job = MagicMock()
    mock_job.id = "job-hm-001"
    mock_job.meta = {"task_type": "handle-incoming-message", "queue_name": "agent-tasks", "invocation_id": "inv-test"}

    mock_config = MagicMock()
    mock_config.skills = []
    mock_config.tools = []
    mock_config.model_config = {
        "provider": "ollama",
        "url": "http://localhost:11434",
        "model": "gpt-oss:20b",
        "api_key_env": "HANDLE_INCOMING_MESSAGE_API_TOKEN",
    }
    mock_config.prompt_path = "/tmp/test_prompt.md"

    mock_backend = MagicMock()
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {"messages": []}
    mock_backend.create_agent.return_value = mock_agent

    mock_session = MagicMock()
    # Phase 17 / D-04: run_task resolves a Conversation row before constructing
    # StartWorkflowTool. The handle-incoming-message branch threads
    # conversation.id into the tool. Stub the lookup here so the existing
    # assertions survive Wave 2 atomically (no test-update churn in Plan 17-03).
    fake_conversation = MagicMock()
    fake_conversation.id = "conv-from-db"
    query_mock = MagicMock()
    query_mock.filter_by.return_value = query_mock
    query_mock.one.return_value = fake_conversation
    mock_session.query.return_value = query_mock
    # Phase 20 / D-07: run_task now session.get(RobotinaInvocation, id) and
    # branches on inv.trigger. Stub a USER_MESSAGE invocation so the existing
    # tool-injection assertions exercise the existing branch.
    from robotina.queue.models import InvocationTrigger
    _stub_inv = MagicMock()
    _stub_inv.trigger = InvocationTrigger.USER_MESSAGE
    mock_session.get.return_value = _stub_inv

    # Task input with all fields needed for tool construction
    task_input = MagicMock()
    task_input.chat_id = "chat-hm-1"
    task_input.user_id = "user-hm-1"
    task_input.platform = "telegram"
    task_input.household_id = "household-abc"
    task_input.text = "What's on the meal plan?"

    injected_tools = []

    def capture_tools(**kwargs):
        injected_tools.extend(kwargs.get("tools", []))
        return mock_agent

    mock_backend.create_agent.side_effect = capture_tools

    with (
        patch("robotina.queue.jobs.get_current_job", return_value=mock_job),
        patch("robotina.agent.agents.get_agent_config", return_value=mock_config),
        patch("robotina.llm.make_backend", return_value=mock_backend),
        patch("pathlib.Path.read_text", return_value="system prompt"),
        patch("robotina.db.SessionLocal", return_value=mock_session),
        patch("robotina.queue.workflow_runner.on_step_start"),
        patch("robotina.queue.workflow_runner.on_step_complete"),
        patch("robotina.queue.workflow_runner.on_step_failed"),
    ):
        from robotina.queue.jobs import run_task
        run_task(task_input)

    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    from robotina.agent.tools.respond import RespondTool
    from robotina.agent.tools.start_workflow import StartWorkflowTool
    from robotina.agent.tools.terminate import TerminateTool

    hm_tools = [t for t in injected_tools if isinstance(t, HouseholdManagerApiTool)]
    r_tools = [t for t in injected_tools if isinstance(t, RespondTool)]
    t_tools = [t for t in injected_tools if isinstance(t, TerminateTool)]
    sw_tools = [t for t in injected_tools if isinstance(t, StartWorkflowTool)]

    assert len(hm_tools) == 1, f"Expected 1 HouseholdManagerApiTool, got {injected_tools}"
    assert hm_tools[0].household_id == "household-abc"

    assert len(r_tools) == 1, f"Expected 1 RespondTool, got {injected_tools}"
    assert r_tools[0].chat_id == "chat-hm-1"
    assert r_tools[0].user_id == "user-hm-1"
    assert r_tools[0].household_id == "household-abc"

    assert len(t_tools) == 1, f"Expected 1 TerminateTool, got {injected_tools}"

    assert len(sw_tools) == 1, f"Expected 1 StartWorkflowTool, got {injected_tools}"
    assert sw_tools[0].chat_id == "chat-hm-1"
    assert sw_tools[0].user_id == "user-hm-1"
    assert sw_tools[0].platform == "telegram"
    assert sw_tools[0].household_id == "household-abc"
    # Phase 17 / D-04: conversation_id resolved via session.query(Conversation).one().id
    assert sw_tools[0].conversation_id == "conv-from-db"

    # Verify AgentConfig.tools was NOT mutated
    assert mock_config.tools == []


# Phase 21 D-06: the legacy per-workflow ack injection test was deleted
# along with the corresponding agent + its registry entry + the jobs.py
# elif branch that injected the legacy queue tool for it. The
# per-workflow acknowledgment role is gone; Robotina's V005 turn now
# sends the ack directly via RespondTool BEFORE start-workflow.


# ---------------------------------------------------------------------------
# Phase 17 / ARCH-01: run_task Conversation lookup + injection
# ---------------------------------------------------------------------------
# Wave 0 RED-state lock tests. Encode the Phase 17 D-04 contract:
# run_task's handle-incoming-message branch resolves Conversation via
# session.query(Conversation).filter_by(platform=..., chat_id=...).one() and
# threads conversation.id into the StartWorkflowTool constructor. Failure to
# find a Conversation raises sqlalchemy.exc.NoResultFound (fail loud per D-04).
# RED until Wave 2 (Plan 17-03) wires the lookup.


def test_run_task_resolves_and_injects_conversation_id():
    """D-04: run_task handle-incoming-message branch resolves Conversation via .one()
    and threads conversation.id into StartWorkflowTool constructor."""
    from unittest.mock import MagicMock, patch

    mock_job = MagicMock()
    mock_job.id = "job-conv-001"
    mock_job.meta = {"task_type": "handle-incoming-message", "queue_name": "agent-tasks", "invocation_id": "inv-test"}

    mock_config = MagicMock()
    mock_config.skills = []
    mock_config.tools = []
    mock_config.model_config = {
        "provider": "ollama", "url": "http://localhost:11434",
        "model": "gpt-oss:20b", "api_key_env": "HANDLE_INCOMING_MESSAGE_API_TOKEN",
    }
    mock_config.prompt_path = "/tmp/test_prompt.md"

    mock_backend = MagicMock()
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {"messages": []}

    # Session mock returns a Conversation row when queried by (platform, chat_id)
    fake_conversation = MagicMock()
    fake_conversation.id = "conv-from-db"

    mock_session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter_by.return_value = query_mock
    query_mock.one.return_value = fake_conversation
    mock_session.query.return_value = query_mock
    # Phase 20 / D-07: stub USER_MESSAGE invocation for the dispatch branch.
    from robotina.queue.models import InvocationTrigger
    _stub_inv = MagicMock()
    _stub_inv.trigger = InvocationTrigger.USER_MESSAGE
    mock_session.get.return_value = _stub_inv

    task_input = MagicMock()
    task_input.chat_id = "chat-1"
    task_input.user_id = "user-1"
    task_input.platform = "telegram"
    task_input.household_id = "household-abc"
    task_input.text = "agregá lentejas"

    injected_tools = []

    def capture_tools(**kwargs):
        injected_tools.extend(kwargs.get("tools", []))
        return mock_agent

    mock_backend.create_agent.side_effect = capture_tools

    with (
        patch("robotina.queue.jobs.get_current_job", return_value=mock_job),
        patch("robotina.agent.agents.get_agent_config", return_value=mock_config),
        patch("robotina.llm.make_backend", return_value=mock_backend),
        patch("pathlib.Path.read_text", return_value="system prompt"),
        patch("robotina.db.SessionLocal", return_value=mock_session),
        patch("robotina.queue.workflow_runner.on_step_start"),
        patch("robotina.queue.workflow_runner.on_step_complete"),
        patch("robotina.queue.workflow_runner.on_step_failed"),
    ):
        from robotina.queue.jobs import run_task
        run_task(task_input)

    from robotina.agent.tools.start_workflow import StartWorkflowTool
    sw_tools = [t for t in injected_tools if isinstance(t, StartWorkflowTool)]
    assert len(sw_tools) == 1, f"Expected 1 StartWorkflowTool, got {injected_tools}"
    assert sw_tools[0].conversation_id == "conv-from-db", (
        f"StartWorkflowTool.conversation_id must come from session.query(Conversation).one().id; "
        f"got {sw_tools[0].conversation_id!r}"
    )


def test_run_task_raises_when_conversation_missing():
    """D-04: .one() raises NoResultFound = fail loud = correct invariant-violation signal."""
    from unittest.mock import MagicMock, patch
    import pytest
    from sqlalchemy.exc import NoResultFound

    mock_job = MagicMock()
    mock_job.id = "job-conv-miss"
    mock_job.meta = {"task_type": "handle-incoming-message", "queue_name": "agent-tasks", "invocation_id": "inv-test"}

    mock_config = MagicMock()
    mock_config.skills = []
    mock_config.tools = []
    mock_config.model_config = {
        "provider": "ollama", "url": "http://localhost:11434",
        "model": "gpt-oss:20b", "api_key_env": "HANDLE_INCOMING_MESSAGE_API_TOKEN",
    }
    mock_config.prompt_path = "/tmp/test_prompt.md"

    mock_session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter_by.return_value = query_mock
    query_mock.one.side_effect = NoResultFound("no Conversation matches")
    mock_session.query.return_value = query_mock
    # Phase 20 / D-07: stub USER_MESSAGE invocation so the dispatch reaches
    # the Conversation .one() call (which is the assertion target here).
    from robotina.queue.models import InvocationTrigger
    _stub_inv = MagicMock()
    _stub_inv.trigger = InvocationTrigger.USER_MESSAGE
    mock_session.get.return_value = _stub_inv

    task_input = MagicMock()
    task_input.chat_id = "chat-missing"
    task_input.user_id = "u1"
    task_input.platform = "telegram"
    task_input.household_id = "household-abc"
    task_input.text = "agregá lentejas"

    with (
        patch("robotina.queue.jobs.get_current_job", return_value=mock_job),
        patch("robotina.agent.agents.get_agent_config", return_value=mock_config),
        patch("robotina.llm.make_backend", return_value=MagicMock()),
        patch("pathlib.Path.read_text", return_value="system prompt"),
        patch("robotina.db.SessionLocal", return_value=mock_session),
        patch("robotina.queue.workflow_runner.on_step_start"),
        patch("robotina.queue.workflow_runner.on_step_complete"),
        patch("robotina.queue.workflow_runner.on_step_failed"),
    ):
        from robotina.queue.jobs import run_task
        with pytest.raises(NoResultFound):
            run_task(task_input)
