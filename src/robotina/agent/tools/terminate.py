"""TerminateTool — engine-enforced termination of an agent turn (D-02).

PITFALL 4 mitigation. Without an explicit ``terminate()`` tool flagged
``return_direct=True``, the LLM can emit trailing free text after its last
real tool call. By making termination an explicit, no-argument tool call,
the agent turn boundary becomes machine-checkable and engine-enforced —
not a prompt-level convention.

The agent is expected to call this AFTER its last ``respond()`` /
``start-workflow()`` tool call. The ``_run`` method returns a sentinel
string, but ``return_direct=True`` causes the LangChain
``create_agent`` graph to ignore the return value and terminate the
turn immediately. No further LLM invocation occurs.
"""
from __future__ import annotations

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict


class TerminateArgs(BaseModel):
    """Empty args schema — ``terminate`` takes no arguments.

    Pydantic ``extra="forbid"`` ensures any kwargs the model attempts to
    pass are rejected at schema-validation time, making the no-arg
    contract enforceable rather than merely documented.
    """

    model_config = ConfigDict(extra="forbid")


class TerminateTool(BaseTool):
    """No-argument tool whose only effect is to terminate the agent turn.

    ``return_direct=True`` is the load-bearing flag: the
    ``langchain.agents.create_agent`` graph terminates immediately after
    this tool runs, with no further LLM invocation. Returning a sentinel
    string from ``_run`` is purely cosmetic — the engine never surfaces
    it to the model.

    No constructor-injected fields. The tool is pure: termination is
    context-free and does not depend on chat_id, household_id, or any
    other per-job state.
    """

    name: str = "terminate"
    description: str = (
        "Signals the end of the assistant turn. Call this AFTER your last "
        "respond() / start-workflow() tool call. Takes no arguments. Do not "
        "write any user-facing text in your final assistant message — "
        "respond() is the only user-visible channel."
    )
    args_schema: type[BaseModel] = TerminateArgs
    return_direct: bool = True

    def _run(self, **kwargs: object) -> str:
        return "turn-terminated"
