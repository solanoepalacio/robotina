"""experiments.robotina_wake — Phase 24 synthetic wake-context Robotina eval.

Per Phase 24 / D-10 / EXP-04 — and load-bearing for D-08b (V007 acceptability
across image_present True/False). Constructs synthetic ``WakeInvocationInput``
objects in memory (no DB writes, no Redis), invokes the wake-context Robotina
agent (``handle-incoming-message`` task type, V007 prompt) directly via the
``LLMBackend.create_agent`` path, and prints / emits the agent's ``respond()``
text + LangWatch trace link for each fixture row.

Fixture rows (D-08b):
  1. ``single-success-with-image``    — single recipe saved with image
                                        (image_present=True).
  2. ``single-success-without-image`` — single recipe saved WITHOUT image
                                        (image_present=False). LOAD-BEARING
                                        for D-08: V007 should NOT surface
                                        "sin foto" / awkwardly omit the
                                        image — operator confirms in
                                        ``24-WAKE-RESULTS-<backend>.md``.
  3. ``single-failure``               — recipe failed; failure_reason should
                                        be surfaced in the wake reply.
  4. ``mixed-batch-three-recipes``    — multi-outcome batch with mixed
                                        ``image_present`` (success+image,
                                        success-no-image, failure).

The Robotina agent is invoked exactly like the production wake-context dispatch
path in ``robotina.queue.jobs.run_task`` (``InvocationTrigger.WORKFLOW_COMPLETION``
branch), except DB / Redis / Telegram side effects are stubbed:

  - ``respond`` is a ``StubRespondTool`` that records ``{"text": ...}`` calls
    (the captured Spanish replies are what we surface for D-08b verdict).
  - ``terminate`` is a ``StubTerminateTool`` (``return_direct=True`` matches
    production turn semantics).
  - ``start-workflow`` is a ``StubStartWorkflowTool`` (wake turns rarely call it
    — V007 teaches the agent to use respond+terminate on wake turns — but the
    surface is wired so the agent doesn't choke if it does try).
  - ``household-manager-api`` is NOT injected (the wake turn shouldn't need
    backend reads; if a row's reply asks for one, that's itself an observation
    for D-08b).

No side effects guarantee: this script never opens a SQLAlchemy session, never
enqueues to RQ, never sends a Telegram message. It only calls the configured
LLM provider (Ollama / OpenAI / Anthropic, selected via ``--backend``) and the
LangWatch tracer.

Usage:
    uv run experiments.robotina_wake --backend ollama
    uv run experiments.robotina_wake --backend openai
    uv run experiments.robotina_wake --backend anthropic --limit 2
    uv run experiments.robotina_wake --backend ollama --operator solano

Prerequisites:
    LANGWATCH_API_KEY env var set (observability is mandatory per CLAUDE.md).
    For --backend ollama:    OLLAMA_URL reachable (defaults to localhost:11434).
    For --backend openai:    HANDLE_INCOMING_MESSAGE_API_TOKEN set with an OpenAI key.
    For --backend anthropic: HANDLE_INCOMING_MESSAGE_API_TOKEN set with an Anthropic key.
"""
from __future__ import annotations

import argparse
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv

load_dotenv()

import langwatch  # noqa: E402 — must follow load_dotenv()
import langwatch.langchain  # noqa: E402
from langchain_core.runnables import RunnableConfig  # noqa: E402
from langchain_core.tools import BaseTool  # noqa: E402
from langwatch.client import Client as LangWatchClient  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


PHASE = "24"
PROMPT_VERSION = "V007"  # current Robotina (handle-incoming-message) prompt
EXPERIMENT_NAME = "robotina-wake-eval"
DEFAULT_OUT_TEMPLATE = (
    ".planning/phases/24-recipe-images-topic-3/24-WAKE-RESULTS-{backend}.md"
)


# ---------------------------------------------------------------------------
# D-08b fixture rows — the four mandatory synthetic scenarios.
# ---------------------------------------------------------------------------


def build_fixture_rows() -> list[dict]:
    """Build the canonical D-08b fixture-row specs.

    Each spec is a dict (NOT a Pydantic model) so module-level tests can
    introspect it without loading robotina.queue.task_types (which pulls in
    SQLAlchemy and prevents a cheap ``--help`` smoke). The
    ``synthetic_wake_input`` constructor below converts each spec into a real
    ``WakeInvocationInput``.
    """
    return [
        {
            "label": "single-success-with-image",
            "outcomes": [
                {
                    "status": "done",
                    "workflow_type": "add-recipe-from-query",
                    "outcome": {
                        "status": "success",
                        "recipe_id": "101",
                        "recipe_name": "Canelones de choclo",
                        "recipe_slug": "canelones-de-choclo",
                        "image_present": True,
                    },
                    "recipe_query": "canelones de choclo",
                },
            ],
        },
        {
            # LOAD-BEARING for D-08: V007 must NOT awkwardly surface
            # "sin foto" / omit the recipe just because image_present=False.
            # Operator (24-09) reviews the reply and ticks the V007 verdict.
            "label": "single-success-without-image",
            "outcomes": [
                {
                    "status": "done",
                    "workflow_type": "add-recipe-from-query",
                    "outcome": {
                        "status": "success",
                        "recipe_id": "102",
                        "recipe_name": "Milanesa criolla salteña",
                        "recipe_slug": "milanesa-criolla-saltena",
                        "image_present": False,
                    },
                    "recipe_query": "milanesa criolla salteña",
                },
            ],
        },
        {
            "label": "single-failure",
            "outcomes": [
                {
                    "status": "failed",
                    "workflow_type": "add-recipe-from-query",
                    "outcome": {
                        "status": "failure",
                        "failure_reason": "metadata: validation timed out",
                    },
                    "recipe_query": "ñoquis de papa",
                },
            ],
        },
        {
            "label": "mixed-batch-three-recipes",
            "outcomes": [
                {
                    "status": "done",
                    "workflow_type": "add-recipe-from-query",
                    "outcome": {
                        "status": "success",
                        "recipe_id": "201",
                        "recipe_name": "Canelones",
                        "recipe_slug": "canelones",
                        "image_present": True,
                    },
                    "recipe_query": "canelones",
                },
                {
                    "status": "done",
                    "workflow_type": "add-recipe-from-query",
                    "outcome": {
                        "status": "success",
                        "recipe_id": "202",
                        "recipe_name": "Pollo al horno",
                        "recipe_slug": "pollo-al-horno",
                        "image_present": False,
                    },
                    "recipe_query": "pollo al horno",
                },
                {
                    "status": "failed",
                    "workflow_type": "add-recipe-from-query",
                    "outcome": {
                        "status": "failure",
                        "failure_reason": "tarta: no recipe found",
                    },
                    "recipe_query": "tarta",
                },
            ],
        },
    ]


def synthetic_wake_input(spec: dict) -> Any:
    """Convert a fixture-row spec dict into a real ``WakeInvocationInput``.

    Lazy-imports ``WakeInvocationInput`` / ``WorkflowOutcomeSummary`` /
    ``AddRecipeOutcome`` so this module's ``--help`` smoke stays cheap and so
    ``build_fixture_rows()`` can be exercised in isolation by the verify-time
    Python snippet (which does not require the production Pydantic models).
    """
    from robotina.queue.task_types import (
        AddRecipeOutcome,
        WakeInvocationInput,
        WorkflowOutcomeSummary,
    )

    outcomes = []
    for o in spec["outcomes"]:
        outcome_payload = o.get("outcome")
        outcomes.append(
            WorkflowOutcomeSummary(
                workflow_run_id=o.get("workflow_run_id", str(uuid.uuid4())),
                workflow_type=o.get("workflow_type", "add-recipe-from-query"),
                status=o["status"],
                outcome=AddRecipeOutcome(**outcome_payload) if outcome_payload else None,
                recipe_query=o.get("recipe_query"),
            )
        )
    return WakeInvocationInput(
        previous_invocation_id=str(uuid.uuid4()),
        conversation_id=str(uuid.uuid4()),
        outcomes=outcomes,
    )


# ---------------------------------------------------------------------------
# Stub tools — capture-only mirrors of RespondTool / TerminateTool /
# StartWorkflowTool. Identical surface to production (same ``name`` +
# argument shapes + ``return_direct`` flags) so the LLM sees no difference.
# ---------------------------------------------------------------------------


class _StubRespondArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(description="Mensaje en español para enviar al usuario.")


class _StubStartWorkflowArgs(BaseModel):
    """Minimal mirror of production StartWorkflowArgs — wake turns rarely call
    this tool (V007 teaches respond+terminate on wake), but the surface is
    wired so the agent doesn't error out if it does try."""

    model_config = ConfigDict(extra="forbid")
    workflow_type: Literal["add-recipe-from-query", "add-recipe-from-url"] = Field(
        description="Workflow identifier."
    )
    input: dict = Field(
        description="Typed input for the workflow (e.g. {value: <query string>})."
    )


class _StubTerminateArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StubRespondTool(BaseTool):
    """Eval stub for ``respond`` — records ``{"text": text}`` in ``self.calls``.

    Same ``name`` and ``return_direct=False`` as the production RespondTool so
    the LLM sees an identical surface. No queue / Redis / Telegram side effects.
    """

    name: str = "respond"
    description: str = (
        "Envía un mensaje al usuario en español. No termina el turno: "
        "podés llamar a otras herramientas después (start-workflow, terminate). "
        "Args: text (str) — el mensaje en español para el usuario."
    )
    return_direct: bool = False
    args_schema: type[BaseModel] = _StubRespondArgs
    calls: list[dict] = Field(default_factory=list, exclude=True)

    def _run(self, text: str) -> str:
        self.calls.append({"text": text})
        return "OK"

    async def _arun(self, text: str) -> str:
        return self._run(text)


class StubStartWorkflowTool(BaseTool):
    """Eval stub for ``start-workflow`` — records call args in ``self.calls``.

    Returns a fake ``workflow_run_id`` so the agent's downstream reasoning
    sees the same success-shape as production. Does NOT enqueue, does NOT
    open a DB session.
    """

    name: str = "start-workflow"
    description: str = (
        "Inicia un flujo de tipo workflow_type con el input dado. "
        "Podes llamarme varias veces en un mismo turno para iniciar N flujos. "
        "No termino el turno — usa terminate() cuando hayas terminado.\n"
        "Args:\n"
        "  workflow_type (str): Workflow name.\n"
        "  input (object): Typed input for the workflow."
    )
    return_direct: bool = False
    args_schema: type[BaseModel] = _StubStartWorkflowArgs
    calls: list[dict] = Field(default_factory=list, exclude=True)

    def _run(self, workflow_type: str, input: dict) -> str:
        if isinstance(input, BaseModel):
            input_dict = input.model_dump()
        else:
            input_dict = dict(input)
        self.calls.append({"workflow_type": workflow_type, "input": input_dict})
        return f"Workflow started. workflow_run_id=stub-{len(self.calls)}"

    async def _arun(self, workflow_type: str, input: dict) -> str:
        return self._run(workflow_type, input)


class StubTerminateTool(BaseTool):
    """Eval stub for ``terminate`` — return_direct=True (matches production)."""

    name: str = "terminate"
    description: str = (
        "Signals the end of the assistant turn. Call this AFTER your last "
        "respond() / start-workflow() tool call. Takes no arguments. Do not "
        "write any user-facing text in your final assistant message — "
        "respond() is the only user-visible channel."
    )
    args_schema: type[BaseModel] = _StubTerminateArgs
    return_direct: bool = True
    calls: list[dict] = Field(default_factory=list, exclude=True)

    def _run(self, **kwargs: object) -> str:
        self.calls.append({"terminated": True})
        return ""


# ---------------------------------------------------------------------------
# Agent build — mirrors jobs.py InvocationTrigger.WORKFLOW_COMPLETION branch.
# ---------------------------------------------------------------------------


def build_agent(backend_name: str) -> tuple[Any, Any, dict[str, BaseTool]]:
    """Build the ``handle-incoming-message`` wake-context agent with stub tools.

    Mirrors the production wake dispatch in ``robotina.queue.jobs.run_task``
    (``InvocationTrigger.WORKFLOW_COMPLETION`` branch): same prompt + same
    skills + same response_format_model (None for this task) — only the
    Respond / Terminate / StartWorkflow tools are swapped for stubs.
    """
    from robotina.agent.agents import get_agent_config
    from robotina.agent.tools.read_skill import SkillSet, build_read_skill_tool
    from robotina.llm import make_backend

    config = get_agent_config("handle-incoming-message")

    model_config = dict(config.model_config)
    if backend_name == "openai":
        model_config["provider"] = "openai"
        model_config.setdefault(
            "model", os.environ.get("OPENAI_EVAL_MODEL", "gpt-4o-mini")
        )
        model_config["url"] = os.environ.get("OPENAI_BASE_URL") or None
    elif backend_name == "anthropic":
        model_config["provider"] = "anthropic"
        model_config.setdefault(
            "model", os.environ.get("ANTHROPIC_EVAL_MODEL", "claude-3-5-sonnet-latest")
        )
        model_config["url"] = os.environ.get("ANTHROPIC_BASE_URL") or None
    # ollama: keep the registry-provided URL + model

    backend = make_backend(model_config)

    stubs = {
        "respond": StubRespondTool(),
        "start_workflow": StubStartWorkflowTool(),
        "terminate": StubTerminateTool(),
    }
    tools: list[BaseTool] = [
        stubs["respond"],
        stubs["start_workflow"],
        stubs["terminate"],
    ]

    # Match production: handle-incoming-message has skills=["household-manager"].
    # The read-skill index is appended to the prompt; we wire the read-skill
    # tool so the agent CAN read skill files if it asks. (HouseholdManagerApiTool
    # is intentionally NOT injected — wake-turn replies don't need backend
    # reads in v1.1; if the agent tries to call one, that's itself an
    # observation worth surfacing for D-08b.)
    skill_sets = [SkillSet(s) for s in config.skills]
    skill_index = "\n\n".join(ss.index_content for ss in skill_sets)
    if skill_sets:
        tools.append(build_read_skill_tool(skill_sets))

    prompt_text = Path(config.prompt_path).read_text(encoding="utf-8")
    if skill_index:
        prompt_text = prompt_text + "\n\n" + skill_index

    agent = backend.create_agent(
        system_prompt=prompt_text,
        tools=tools,
        response_format=config.response_format_model,
    )
    config_used = type(config)(
        task_type=config.task_type,
        model_config=model_config,
        prompt_path=config.prompt_path,
        skills=config.skills,
        tools=config.tools,
        response_format_model=config.response_format_model,
    )
    return agent, config_used, stubs


# ---------------------------------------------------------------------------
# Per-row run + result capture.
# ---------------------------------------------------------------------------


@dataclass
class RowResult:
    label: str
    outcomes_summary: str
    user_message: str
    respond_texts: list[str] = field(default_factory=list)
    start_workflow_calls: list[dict] = field(default_factory=list)
    terminated: bool = False
    trace_id: str | None = None
    error: str | None = None


def _summarize_outcomes(spec: dict) -> str:
    """One-line, table-friendly summary of a row's outcome shapes (for the report)."""
    parts: list[str] = []
    for o in spec["outcomes"]:
        kind = o["status"]
        if o.get("outcome"):
            payload = o["outcome"]
            img = payload.get("image_present")
            if payload.get("status") == "success":
                parts.append(
                    f"success(image={img}, name={payload.get('recipe_name', '?')!r})"
                )
            else:
                parts.append(f"failure({payload.get('failure_reason', '?')!r})")
        else:
            parts.append(kind)
    return "; ".join(parts)


def run_one(
    agent: Any, spec: dict, stubs: dict, backend: str, config_meta: dict
) -> RowResult:
    """Invoke the wake-context agent on one synthetic fixture row."""
    label = spec["label"]
    try:
        wake_input = synthetic_wake_input(spec)
    except Exception as exc:
        logger.exception("Row %s: failed to build WakeInvocationInput: %s", label, exc)
        return RowResult(
            label=label,
            outcomes_summary=_summarize_outcomes(spec),
            user_message="(failed to build wake input)",
            error=f"build wake input: {exc}",
        )

    user_message = wake_input.to_user_message()

    # Reset stub call buffers so this row's captures are isolated.
    for stub in stubs.values():
        stub.calls.clear()

    tracer = langwatch.langchain.LangChainTracer(
        metadata={
            "experiment": EXPERIMENT_NAME,
            "phase": PHASE,
            "prompt_version": PROMPT_VERSION,
            "label": label,
            "n_outcomes": len(spec["outcomes"]),
            "image_present_values": [
                o.get("outcome", {}).get("image_present")
                for o in spec["outcomes"]
            ],
            "backend": backend,
            "model": config_meta.get("model"),
            "provider": config_meta.get("provider"),
        }
    )

    result = RowResult(
        label=label,
        outcomes_summary=_summarize_outcomes(spec),
        user_message=user_message,
    )
    try:
        with tracer:
            agent.invoke(
                {"messages": [{"role": "user", "content": user_message}]},
                config=RunnableConfig(callbacks=[tracer]),
            )
            lw_trace = getattr(tracer, "trace", None)
            if lw_trace is not None:
                result.trace_id = getattr(lw_trace, "trace_id", None)
    except Exception as exc:
        logger.exception("Row %s: agent.invoke failed: %s", label, exc)
        result.error = f"agent.invoke: {exc}"
        return result

    result.respond_texts = [c.get("text", "") for c in stubs["respond"].calls]
    result.start_workflow_calls = list(stubs["start_workflow"].calls)
    result.terminated = bool(stubs["terminate"].calls)
    return result


# ---------------------------------------------------------------------------
# Markdown emit.
# ---------------------------------------------------------------------------


def _truncate(s: str, n: int = 200) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _table_safe(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def write_results(
    out_path: Path,
    backend: str,
    results: list[RowResult],
    config_meta: dict,
    operator: str,
) -> None:
    """Emit the per-backend ``verdict: pending`` markdown report for 24-09."""
    lines: list[str] = []
    lines.append("---")
    lines.append("verdict: pending")
    lines.append(f"backend: {backend}")
    lines.append(f"model: {config_meta.get('model', '<unknown>')}")
    lines.append(f"prompt_version: {PROMPT_VERSION}")
    lines.append(f"phase: {PHASE}")
    lines.append(f"date: {date.today().isoformat()}")
    lines.append(f"operator: {operator}")
    lines.append("---")
    lines.append("")
    lines.append(f"# 24-WAKE-RESULTS — {backend}")
    lines.append("")
    lines.append(
        "Per Phase 24 / D-08b / D-10 / EXP-04. Synthetic wake-context "
        "Robotina eval — the harness "
        "(`uv run experiments.robotina_wake --backend " + backend + "`) "
        "constructs in-memory `WakeInvocationInput` objects and invokes the "
        "wake-context agent (V007 prompt) with stub Respond / Terminate / "
        "StartWorkflow tools. No DB writes, no Redis, no Telegram side "
        "effects."
    )
    lines.append("")
    lines.append(
        "**Load-bearing row:** `single-success-without-image` is the D-08 "
        "V007 acceptability gate — V007 should NOT awkwardly surface "
        "\"sin foto\" / omit the recipe just because `image_present=False`. "
        "Operator confirms or rejects below."
    )
    lines.append("")
    lines.append("## Per-row results")
    lines.append("")
    lines.append(
        "| label | outcomes_summary | wake_reply (respond text) | "
        "reply acceptable? | langwatch_trace_id |"
    )
    lines.append(
        "|-------|------------------|---------------------------|"
        "-------------------|--------------------|"
    )
    for r in results:
        replies = " || ".join(r.respond_texts) if r.respond_texts else "(no respond text)"
        if r.error:
            replies = f"ERROR: {r.error}"
        # Mark the load-bearing row distinctly so the operator can't miss it.
        if r.label == "single-success-without-image":
            acceptable_cell = "_operator: Y/N (LOAD-BEARING for D-08)_"
        else:
            acceptable_cell = "_operator: Y/N_"
        lines.append(
            f"| {r.label} | {_table_safe(_truncate(r.outcomes_summary, 100))} | "
            f"{_table_safe(_truncate(replies, 240))} | {acceptable_cell} | "
            f"{r.trace_id or ''} |"
        )
    lines.append("")
    lines.append("## Per-row details")
    lines.append("")
    for r in results:
        lines.append(f"### {r.label}")
        lines.append("")
        lines.append("**Synthetic user message:**")
        lines.append("")
        lines.append("```")
        lines.append(r.user_message)
        lines.append("```")
        lines.append("")
        if r.error:
            lines.append(f"**Error:** `{r.error}`")
        else:
            lines.append(
                f"**respond() texts ({len(r.respond_texts)}):**"
            )
            for i, t in enumerate(r.respond_texts, 1):
                lines.append(f"{i}. {t}")
            if not r.respond_texts:
                lines.append("(none — agent did not call respond())")
            lines.append("")
            if r.start_workflow_calls:
                lines.append(
                    f"**start-workflow() calls ({len(r.start_workflow_calls)}, "
                    "unexpected on wake turns):**"
                )
                for c in r.start_workflow_calls:
                    lines.append(f"- {c}")
            lines.append(f"**terminate() called:** {r.terminated}")
            if r.trace_id:
                lines.append(f"**LangWatch trace_id:** `{r.trace_id}`")
        lines.append("")
    lines.append("## D-08 V007 Verdict")
    lines.append("")
    lines.append(
        "- [ ] V007 wake reply on `single-success-without-image` is acceptable "
        "(does NOT awkwardly omit the recipe / surface \"sin foto\" / behave "
        "differently from the image-present variant)."
    )
    lines.append(
        "- [ ] V007 wake reply on `single-success-with-image` is acceptable."
    )
    lines.append(
        "- [ ] V007 wake reply on `single-failure` surfaces the failure_reason."
    )
    lines.append(
        "- [ ] V007 wake reply on `mixed-batch-three-recipes` consolidates all "
        "three outcomes coherently."
    )
    lines.append(
        "- [ ] If the load-bearing row is unacceptable, file a V008 fork as a "
        "v1.2 follow-up."
    )
    lines.append("")
    lines.append("verdict: pending")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote wake-eval results to %s", out_path)


# ---------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 24 synthetic wake-context Robotina eval (D-08b / EXP-04). "
            "Builds 4 synthetic WakeInvocationInput fixtures in memory and "
            "invokes the wake-context agent (V007 prompt); emits a "
            "verdict: pending markdown table for operator (24-09) review."
        )
    )
    parser.add_argument(
        "--backend",
        choices=["ollama", "openai", "anthropic"],
        required=True,
        help=(
            "LLM backend. Tags the LangWatch metadata + results filename. "
            "The four fixture rows are deterministic synthetic inputs."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path for the per-backend results report.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N fixture rows (debug aid; default 4).",
    )
    parser.add_argument(
        "--operator",
        type=str,
        default=os.environ.get("USER", "auto-fill"),
        help="Operator label written into the results frontmatter.",
    )
    args = parser.parse_args()

    out_path = args.out or Path(DEFAULT_OUT_TEMPLATE.format(backend=args.backend))

    specs = build_fixture_rows()
    if args.limit:
        specs = specs[: args.limit]
        logger.info("Limiting to first %d fixture rows", len(specs))
    logger.info("Building agent (backend=%s)", args.backend)
    agent, config, stubs = build_agent(args.backend)
    config_meta = {
        "model": config.model_config.get("model"),
        "provider": config.model_config.get("provider"),
    }
    logger.info(
        "Agent ready | provider=%s model=%s prompt=%s",
        config_meta["provider"],
        config_meta["model"],
        config.prompt_path,
    )

    results: list[RowResult] = []
    for spec in specs:
        logger.info("--- ROW %s ---", spec["label"])
        result = run_one(agent, spec, stubs, args.backend, config_meta)
        results.append(result)
        logger.info(
            "label=%s respond_n=%d terminated=%s error=%s",
            result.label,
            len(result.respond_texts),
            result.terminated,
            (result.error or "")[:120],
        )
        for i, t in enumerate(result.respond_texts, 1):
            logger.info("  respond[%d]: %s", i, _truncate(t, 200))
        if result.trace_id:
            logger.info("  langwatch trace_id: %s", result.trace_id)

    # Flush LangWatch traces before writing results (mirrors gather_from_url).
    if LangWatchClient._tracer_provider is not None:
        try:
            LangWatchClient._tracer_provider.force_flush()
        except Exception as exc:  # noqa: BLE001 — flush failure must not lose results
            logger.warning("LangWatch flush failed: %s", exc)

    write_results(out_path, args.backend, results, config_meta, args.operator)

    total = len(results)
    ok = sum(1 for r in results if r.error is None)
    logger.info(
        "=== wake-eval complete: %d / %d rows produced output on backend=%s ===",
        ok,
        total,
        args.backend,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
