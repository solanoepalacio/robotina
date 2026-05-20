"""Phase 22 multi-recipe eval harness.

Per CONTEXT D-15: this script is the LOAD-BEARING MANUAL GATE for BATCH-01..05.
No unit test can measure "does the LLM extract 3 recipes from a Spanish
multi-recipe utterance" — the eval set + this harness are the empirical proof.

The harness loads the production ``handle-incoming-message`` agent config
(which points at V006 after Phase 22 Plan 02), swaps in **stub** Respond /
StartWorkflow / Terminate tools that RECORD calls without enqueuing real
workflows or sending Telegram messages, then dispatches each utterance from
``22-EVAL-SET.md`` through the agent and counts how many ``start-workflow``
tool calls the LLM emits per turn. The observed count + the recipe values
inside each call are compared against the eval set's expected columns and
written to ``22-EVAL-RESULTS-<backend>.md`` for operator review.

**No side effects guarantee (T-22-07 / T-22-08):** the stub tools NEVER call
``workflow_runner.queue_workflow``, NEVER open a ``SessionLocal()``, and NEVER
enqueue to RQ. Running this script does NOT touch the production database or
the Telegram bot. It only calls the configured LLM provider.

Usage:
    uv run experiments.multi_recipe_eval --backend ollama
    uv run experiments.multi_recipe_eval --backend openai
    uv run experiments.multi_recipe_eval --backend anthropic --limit 5

Per D-04: Ollama results are informational only. OpenAI is the merge gate
(≥ 95% count accuracy, ≥ 90% name accuracy on multi-recipe rows).

Prerequisites:
    LANGWATCH_API_KEY env var set (observability is mandatory per CLAUDE.md).
    For --backend ollama: OLLAMA_URL reachable (defaults to localhost:11434).
    For --backend openai: HANDLE_INCOMING_MESSAGE_API_TOKEN set with an OpenAI key.
    For --backend anthropic: HANDLE_INCOMING_MESSAGE_API_TOKEN set with an Anthropic key.
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
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


PHASE = "22"
PROMPT_VERSION = "V006"
EXPERIMENT_NAME = "multi-recipe-eval"
DEFAULT_EVAL_SET = Path(
    ".planning/phases/22-multi-recipe-per-message-topic-1/22-EVAL-SET.md"
)
DEFAULT_OUT_TEMPLATE = (
    ".planning/phases/22-multi-recipe-per-message-topic-1/22-EVAL-RESULTS-{backend}.md"
)


# ---------------------------------------------------------------------------
# Eval-set parser
# ---------------------------------------------------------------------------


@dataclass
class EvalRow:
    """One row from the eval-set markdown table."""

    idx: int
    utterance: str
    class_name: str
    expected_n: int
    expected_values: list[str]
    expected_respond_tag: str
    notes: str = ""


def parse_eval_set(path: Path) -> list[EvalRow]:
    """Parse ``22-EVAL-SET.md`` into a list of ``EvalRow``.

    Accepted format for the ``Expected recipe value(s)`` column:
      - empty cell when ``Expected N == 0``
      - comma-separated plain strings, e.g. ``canelones, pollo al horno``
      - bracketed/quoted variant also accepted: ``["canelones", "pollo al horno"]``

    Walks the markdown line-by-line: locates the ``## Utterances`` heading,
    skips until the table header row + the ``|---`` separator, then collects
    every subsequent ``| ... |`` row until a blank line or next heading.
    """
    rows: list[EvalRow] = []
    in_utterances_section = False
    saw_header = False
    saw_separator = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("## "):
            if stripped.lower().startswith("## utterances"):
                in_utterances_section = True
                saw_header = False
                saw_separator = False
                continue
            elif in_utterances_section:
                # Left the section
                break
        if not in_utterances_section:
            continue
        if not stripped:
            if saw_separator and rows:
                # blank line ends the table
                break
            continue
        if not stripped.startswith("|"):
            continue
        # First | row is the header; second is the |---|---| separator
        if not saw_header:
            saw_header = True
            continue
        if not saw_separator:
            # Either a separator row or (unlikely) a data row with --- inside;
            # accept the row as separator if it is dashes.
            if re.fullmatch(r"\|[\s\-:|]+\|", stripped):
                saw_separator = True
                continue
            # If not a separator, treat as header artifact and continue
            continue
        # Data row
        cells = [c.strip() for c in stripped.split("|")[1:-1]]
        if len(cells) < 7:
            logger.warning("Skipping malformed row (cells=%d): %s", len(cells), stripped)
            continue
        try:
            idx = int(cells[0])
        except ValueError:
            logger.warning("Skipping row with non-int idx: %s", cells[0])
            continue
        utterance = cells[1]
        class_name = cells[2]
        try:
            expected_n = int(cells[3])
        except ValueError:
            logger.warning("Skipping row idx=%s with non-int expected_n: %s", idx, cells[3])
            continue
        expected_values = _parse_value_list(cells[4])
        expected_respond_tag = cells[5]
        notes = cells[6] if len(cells) > 6 else ""
        rows.append(
            EvalRow(
                idx=idx,
                utterance=utterance,
                class_name=class_name,
                expected_n=expected_n,
                expected_values=expected_values,
                expected_respond_tag=expected_respond_tag,
                notes=notes,
            )
        )
    return rows


def _parse_value_list(cell: str) -> list[str]:
    """Parse the ``Expected recipe value(s)`` cell into a list of strings.

    Empty / whitespace-only cell → ``[]``. JSON-style ``["a", "b"]`` and
    plain ``a, b`` are both accepted.
    """
    s = cell.strip()
    if not s:
        return []
    # Strip surrounding brackets if present
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    # Split on commas; strip whitespace + surrounding quotes
    parts = []
    for raw in s.split(","):
        v = raw.strip().strip('"').strip("'").strip()
        if v:
            parts.append(v)
    return parts


# ---------------------------------------------------------------------------
# Stub tools — record calls, do NOT enqueue / send / open DB sessions
# ---------------------------------------------------------------------------


class _StubStartWorkflowArgs(BaseModel):
    """Minimal mirror of the production schema — keep tolerant for the eval.

    We re-declare instead of importing ``StartWorkflowArgs`` so the eval
    harness has zero coupling to ``robotina.queue.task_types`` (which would
    pull in SQLAlchemy session imports). The wire shape the LLM emits is
    identical to the production tool because the description string below
    mirrors the production tool's description.
    """

    model_config = ConfigDict(extra="forbid")
    workflow_type: Literal["add-recipe-from-query", "add-recipe-from-url"] = Field(
        description="Workflow identifier. Currently only 'add-recipe-from-query' is supported."
    )
    input: dict = Field(
        description=(
            "Typed input for the workflow. For 'add-recipe-from-query', shape is "
            "{value: <recipe query string>}."
        ),
    )


class _StubRespondArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(description="Mensaje en español para enviar al usuario.")


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

    Returns a fake ``workflow_run_id`` string with the same ``Workflow started.``
    prefix as the production tool so the LLM's downstream reasoning sees an
    identical success shape. Does NOT enqueue, does NOT open a DB session.
    """

    name: str = "start-workflow"
    description: str = (
        "Inicia un flujo de tipo workflow_type con el input dado. "
        "Podes llamarme varias veces en un mismo turno para iniciar N flujos. "
        "No termino el turno — usa terminate() cuando hayas terminado.\n"
        "Args:\n"
        "  workflow_type (str): Workflow name. Only 'add-recipe-from-query' is supported.\n"
        "  input (object): Typed input for the workflow. For 'add-recipe-from-query', "
        "shape is {value: <recipe query string>}.\n"
        "reply_context and household_id are injected automatically by the "
        "runtime — do not pass them.\n"
        "Arguments are passed as JSON. Use JSON literals: null (not None or "
        "none), true/false (not True/False). Strings must use double quotes. "
        "Example: {\"workflow_type\": \"add-recipe-from-query\", \"input\": "
        "{\"value\": \"lentil soup\"}}."
    )
    return_direct: bool = False
    args_schema: type[BaseModel] = _StubStartWorkflowArgs
    calls: list[dict] = Field(default_factory=list, exclude=True)

    def _run(self, workflow_type: str, input: dict) -> str:
        # Normalize: input may arrive as pydantic model or dict
        if isinstance(input, BaseModel):
            input_dict = input.model_dump()
        else:
            input_dict = dict(input)
        self.calls.append({"workflow_type": workflow_type, "input": input_dict})
        return f"Workflow started. workflow_run_id=stub-{len(self.calls)}"

    async def _arun(self, workflow_type: str, input: dict) -> str:
        return self._run(workflow_type, input)


class StubTerminateTool(BaseTool):
    """Eval stub for ``terminate`` — return_direct=True (matches production).

    Appends a sentinel ``{"terminated": True}`` to ``self.calls``. The
    ``return_direct=True`` flag is load-bearing: the agent graph short-circuits
    after this tool runs, matching the production turn-termination semantics.
    """

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
# Tool-call counting + name matching
# ---------------------------------------------------------------------------


def count_start_workflow_calls(stubs: dict) -> tuple[int, list[str]]:
    """Return (count, recipe_values) from the StubStartWorkflowTool's recorded calls.

    Counting from the stub's call list (rather than walking ``result["messages"]``)
    is more reliable because the stub captures exactly what the agent dispatched
    — no risk of double-counting retried tool calls or missing calls that the
    agent emitted but the engine deduplicated before invoking.
    """
    start_calls = stubs["start_workflow"].calls
    count = len(start_calls)
    recipe_values: list[str] = []
    for call in start_calls:
        inp = call.get("input") or {}
        val = inp.get("value") if isinstance(inp, dict) else None
        if val:
            recipe_values.append(val)
    return count, recipe_values


def _normalize(s: str) -> str:
    """Lowercase + accent-strip for tolerant name matching."""
    if not s:
        return ""
    nfd = unicodedata.normalize("NFD", s)
    no_accents = "".join(c for c in nfd if not unicodedata.combining(c))
    return no_accents.lower().strip()


def _name_match_one(expected: str, observed_values: list[str], threshold: float = 0.75) -> bool:
    e = _normalize(expected)
    for obs in observed_values:
        o = _normalize(obs)
        if not o:
            continue
        if e in o or o in e:
            return True
        if SequenceMatcher(None, e, o).ratio() >= threshold:
            return True
    return False


def names_match(expected_values: list[str], observed_values: list[str]) -> bool:
    """All expected names found in the observed values (tolerant)."""
    if not expected_values:
        return True
    return all(_name_match_one(e, observed_values) for e in expected_values)


def respond_tag_matches(expected_tag: str, respond_calls: list[dict]) -> bool:
    """True if any respond() text contains the expected tag substring (case-insensitive,
    accent-insensitive). Empty expected_tag → always True (no assertion)."""
    if not expected_tag:
        return True
    tag_norm = _normalize(expected_tag)
    if not tag_norm:
        return True
    for call in respond_calls:
        text = _normalize(call.get("text", ""))
        if tag_norm in text:
            return True
    return False


# ---------------------------------------------------------------------------
# Agent build
# ---------------------------------------------------------------------------


def build_agent(backend_name: str) -> tuple[Any, Any, dict[str, BaseTool]]:
    """Build the handle-incoming-message agent with stub tools.

    Returns (agent, config, stubs_dict). The stubs_dict keys are
    ``respond``, ``start_workflow``, ``terminate``.

    Backend selection: ``handle-incoming-message`` is registered with provider
    ``ollama`` in ``AGENT_REGISTRY``. For ``--backend openai`` or ``--backend
    anthropic`` we override ``model_config.provider`` before constructing the
    backend so the same agent config + V006 prompt runs against the chosen LLM.
    Model name and URL fall back to provider-sensible defaults; operator can
    pin via env if needed.
    """
    from robotina.agent.agents import get_agent_config
    from robotina.agent.tools.read_skill import SkillSet, build_read_skill_tool
    from robotina.llm import make_backend

    config = get_agent_config("handle-incoming-message")

    model_config = dict(config.model_config)
    if backend_name == "openai":
        model_config["provider"] = "openai"
        # Sensible defaults — operator overrides via env if needed
        model_config.setdefault("model", os.environ.get("OPENAI_EVAL_MODEL", "gpt-4o-mini"))
        model_config["url"] = os.environ.get("OPENAI_BASE_URL") or None
    elif backend_name == "anthropic":
        model_config["provider"] = "anthropic"
        model_config.setdefault(
            "model", os.environ.get("ANTHROPIC_EVAL_MODEL", "claude-3-5-sonnet-latest")
        )
        model_config["url"] = os.environ.get("ANTHROPIC_BASE_URL") or None
    # ollama: keep the registry-provided URL + model

    backend = make_backend(model_config)

    # Build stubs FIRST so we can return them to the caller
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

    skill_sets = [SkillSet(s) for s in config.skills]
    skill_index = "\n\n".join(ss.index_content for ss in skill_sets)
    if skill_sets:
        tools.append(build_read_skill_tool(skill_sets))

    prompt_text = Path(config.prompt_path).read_text(encoding="utf-8")
    if skill_index:
        prompt_text = prompt_text + "\n\n" + skill_index

    agent = backend.create_agent(system_prompt=prompt_text, tools=tools)
    # Return a config object with the overridden model_config so caller can
    # surface the actual model used in the LangWatch metadata + report.
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
# Per-utterance result + report emit
# ---------------------------------------------------------------------------


@dataclass
class EvalResult:
    row: EvalRow
    observed_n: int
    observed_values: list[str]
    respond_texts: list[str]
    terminated: bool
    error: str | None = None

    @property
    def count_ok(self) -> bool:
        return self.error is None and self.observed_n == self.row.expected_n

    @property
    def name_ok(self) -> bool:
        if self.error is not None:
            return False
        if not self.row.expected_values:
            return True
        return names_match(self.row.expected_values, self.observed_values)

    @property
    def respond_ok(self) -> bool:
        if self.error is not None:
            return False
        calls = [{"text": t} for t in self.respond_texts]
        return respond_tag_matches(self.row.expected_respond_tag, calls)


def write_results(
    out_path: Path,
    backend: str,
    results: list[EvalResult],
    config_meta: dict,
) -> None:
    """Emit the per-backend markdown report. Always writes ``verdict: pending``;
    the OPERATOR flips to ``pass``/``fail``/``pivot`` after reviewing."""

    total = len(results)
    count_correct = sum(1 for r in results if r.count_ok)
    multi_rows = [r for r in results if r.row.expected_values]
    name_correct = sum(1 for r in multi_rows if r.name_ok)
    multi_total = len(multi_rows)

    # Per-class breakdown
    per_class: dict[str, dict[str, int]] = {}
    for r in results:
        cls = r.row.class_name
        bucket = per_class.setdefault(cls, {"total": 0, "count_ok": 0, "name_ok": 0})
        bucket["total"] += 1
        if r.count_ok:
            bucket["count_ok"] += 1
        if r.name_ok:
            bucket["name_ok"] += 1

    operator = os.environ.get("USER", "auto-fill")
    model = config_meta.get("model", "<unknown>")

    lines: list[str] = []
    lines.append("---")
    lines.append("verdict: pending")
    lines.append(f"backend: {backend}")
    lines.append(f"model: {model}")
    lines.append(f"date: {date.today().isoformat()}")
    lines.append(f"operator: {operator}")
    lines.append("eval_set_version: 1")
    lines.append("---")
    lines.append("")
    lines.append(f"# Phase 22 Multi-Recipe Eval Results — {backend}")
    lines.append("")
    if backend == "ollama":
        lines.append("Per D-04: Ollama is **informational only**. Failures here do NOT block merge.")
    elif backend == "openai":
        lines.append(
            "**Per D-04: OpenAI is the MERGE GATE. ≥ 95% count accuracy required to PASS. "
            "≥ 90% name accuracy on multi-recipe rows required to PASS.**"
        )
    else:
        lines.append(f"Backend ``{backend}`` — informational run.")
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    pct_count = (100.0 * count_correct / total) if total else 0.0
    pct_name = (100.0 * name_correct / multi_total) if multi_total else 0.0
    lines.append(f"- Total utterances: {total}")
    lines.append(f"- Count-correct: {count_correct} / {total} ({pct_count:.1f}%)")
    lines.append(f"- Name-correct (multi-recipe rows): {name_correct} / {multi_total} ({pct_name:.1f}%)")
    lines.append("- Per-class breakdown:")
    for cls in sorted(per_class.keys()):
        b = per_class[cls]
        lines.append(
            f"  - `{cls}`: count {b['count_ok']}/{b['total']}, name {b['name_ok']}/{b['total']}"
        )
    lines.append("")
    lines.append("## Per-utterance results")
    lines.append("")
    lines.append(
        "| # | Utterance | Class | Expected N | Observed N | Observed values | OK? | LangWatch trace |"
    )
    lines.append(
        "|---|-----------|-------|------------|------------|-----------------|-----|------------------|"
    )
    for r in results:
        observed = ", ".join(r.observed_values) if r.observed_values else ""
        if r.error:
            ok = "ERR"
            observed = f"<error: {r.error}>"
        else:
            ok = "OK" if (r.count_ok and r.name_ok and r.respond_ok) else "FAIL"
        # Pipe-safe utterance
        utt = r.row.utterance.replace("|", "\\|")
        observed_safe = observed.replace("|", "\\|")
        lines.append(
            f"| {r.row.idx} | {utt} | {r.row.class_name} | {r.row.expected_n} | "
            f"{r.observed_n} | {observed_safe} | {ok} |  |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("[Operator narrative — patterns, failures, recommendations.]")
    lines.append("")
    lines.append("## Go / No-Go")
    lines.append("")
    if backend == "openai":
        lines.append(
            "Required for PASS: count ≥ 95% AND name ≥ 90% on multi-recipe rows.\n"
            "If catastrophic (< 50% count): `verdict: pivot` (defensive code cap per Deferred Ideas)."
        )
        lines.append("")
        lines.append("verdict: pass | fail | pivot")
    else:
        lines.append(
            "Informational: ≥ 70% count accuracy = usable for dev. Below = model-upgrade candidate."
        )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote eval results to %s", out_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 22 multi-recipe eval harness (BATCH-01..05 acceptance evidence)."
    )
    parser.add_argument(
        "--backend",
        choices=["ollama", "openai", "anthropic"],
        default="ollama",
        help="LLM backend to test against. Ollama is informational; OpenAI is the merge gate.",
    )
    parser.add_argument(
        "--eval-set",
        type=Path,
        default=DEFAULT_EVAL_SET,
        help="Path to the eval-set markdown table.",
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
        help="Run only the first N utterances (debug aid).",
    )
    args = parser.parse_args()

    out_path = args.out or Path(DEFAULT_OUT_TEMPLATE.format(backend=args.backend))

    logger.info("Parsing eval set: %s", args.eval_set)
    rows = parse_eval_set(args.eval_set)
    logger.info("Parsed %d utterance rows", len(rows))
    if args.limit:
        rows = rows[: args.limit]
        logger.info("Limiting to first %d rows", len(rows))

    results: list[EvalResult] = []
    config_meta: dict = {}

    for row in rows:
        logger.info("--- Utterance %d (%s) ---", row.idx, row.class_name)
        try:
            agent, config, stubs = build_agent(args.backend)
        except Exception as e:
            logger.exception("build_agent failed for utterance %d: %s", row.idx, e)
            results.append(
                EvalResult(
                    row=row,
                    observed_n=-1,
                    observed_values=[],
                    respond_texts=[],
                    terminated=False,
                    error=f"build_agent: {e}",
                )
            )
            continue

        if not config_meta:
            config_meta = {
                "model": config.model_config.get("model"),
                "provider": config.model_config.get("provider"),
            }

        tracer = langwatch.langchain.LangChainTracer(
            metadata={
                "experiment": EXPERIMENT_NAME,
                "phase": PHASE,
                "prompt_version": PROMPT_VERSION,
                "utterance_id": row.idx,
                "class": row.class_name,
                "expected_n": row.expected_n,
                "backend": args.backend,
                "model": config.model_config.get("model"),
                "provider": config.model_config.get("provider"),
            }
        )

        try:
            with tracer:
                agent.invoke(
                    {"messages": [{"role": "user", "content": row.utterance}]},
                    config=RunnableConfig(callbacks=[tracer]),
                )
            observed_n, observed_values = count_start_workflow_calls(stubs)
            respond_texts = [c.get("text", "") for c in stubs["respond"].calls]
            terminated = bool(stubs["terminate"].calls)
            results.append(
                EvalResult(
                    row=row,
                    observed_n=observed_n,
                    observed_values=observed_values,
                    respond_texts=respond_texts,
                    terminated=terminated,
                )
            )
            logger.info(
                "utterance=%d expected_n=%d observed_n=%d values=%s",
                row.idx,
                row.expected_n,
                observed_n,
                observed_values,
            )
        except Exception as e:
            logger.exception("Utterance %d failed: %s", row.idx, e)
            results.append(
                EvalResult(
                    row=row,
                    observed_n=-1,
                    observed_values=[],
                    respond_texts=[],
                    terminated=False,
                    error=str(e),
                )
            )
            # Continue to next utterance (per recipe_research.py error pattern)
            continue

    # Flush LangWatch traces
    if LangWatchClient._tracer_provider is not None:
        LangWatchClient._tracer_provider.force_flush()

    write_results(out_path, args.backend, results, config_meta)

    total = len(results)
    count_correct = sum(1 for r in results if r.count_ok)
    logger.info(
        "=== eval complete: %d / %d count-correct on backend=%s ===",
        count_correct,
        total,
        args.backend,
    )


if __name__ == "__main__":
    main()
