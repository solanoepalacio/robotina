"""Tests for TerminateTool (D-02, PITFALL 4 mitigation, D-17).

The TerminateTool is a no-argument LangChain BaseTool whose only purpose is
engine-enforced termination of an agent turn via ``return_direct=True``. The
LangChain ``create_agent`` graph terminates immediately after the tool runs;
the model never sees the tool's return value.

These tests pin the contract:
  - Constructs with no args (the tool is context-free).
  - ``return_direct`` is True (load-bearing — PITFALL 4 mitigation).
  - ``name`` is exactly ``"terminate"``.
  - ``_run`` returns a non-empty sentinel string (engine ignores it, but it
    must exist so middleware tracing does not log ``None``).
  - The Pydantic args schema rejects any extra keyword arguments
    (``extra="forbid"``), making the no-arg contract enforceable rather
    than merely documented.
"""

import pytest
from pydantic import ValidationError


def test_terminate_tool_constructs_no_args() -> None:
    """TerminateTool() needs no constructor args — termination is context-free."""
    from robotina.agent.tools.terminate import TerminateTool

    tool = TerminateTool()
    assert tool is not None


def test_terminate_tool_return_direct_true() -> None:
    """return_direct=True is the engine-enforced termination flag (PITFALL 4)."""
    from robotina.agent.tools.terminate import TerminateTool

    tool = TerminateTool()
    assert tool.return_direct is True


def test_terminate_tool_name_is_terminate() -> None:
    """The tool's LangChain ``name`` is exactly ``terminate``."""
    from robotina.agent.tools.terminate import TerminateTool

    tool = TerminateTool()
    assert tool.name == "terminate"


def test_terminate_tool_run_returns_sentinel() -> None:
    """_run returns a non-empty string sentinel — engine ignores it, but it must exist."""
    from robotina.agent.tools.terminate import TerminateTool

    tool = TerminateTool()
    result = tool._run()
    assert isinstance(result, str)
    assert result  # non-empty


def test_terminate_tool_rejects_extra_args() -> None:
    """args_schema is empty with extra='forbid' — passing kwargs raises ValidationError."""
    from robotina.agent.tools.terminate import TerminateArgs

    with pytest.raises(ValidationError):
        TerminateArgs(foo="bar")  # type: ignore[call-arg]
