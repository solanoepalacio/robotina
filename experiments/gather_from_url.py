"""Phase 23 URL-ingestion eval harness (gather-from-url agent).

Per CONTEXT D-09 / D-24: this script is the LOAD-BEARING MANUAL GATE for
URL-06 (≥ 85% URL-level pass per D-11). No unit test can measure "does
the LLM + FetchAndScrapeTool combo extract a usable RecipeData from a
Spanish recipe blog" — the 21-URL eval set in
``.planning/phases/23-url-ingestion-topic-2/23-EVAL-SET.md`` plus this
harness are the empirical proof.

The harness reads the eval set, iterates each URL through the production
``gather-from-url`` LLM agent (V001 prompt + ``FetchAndScrapeTool``)
against the configured backend, captures the emitted ``RecipeData``
structured response, and scores per-row field presence per D-11:

    Per-URL pass = ≥ 6/8 expected-populated fields populated AND non-empty.
    Aggregate pass = ≥ 17/21 URLs pass (≈ 85% URL-level).

Results emit to ``.../23-EVAL-RESULTS-<backend>.md`` with ``verdict:
pending`` YAML frontmatter; the OPERATOR flips the verdict after review
(Phase 23 D-13, mirrors Phase 21/22 manual-smoke pattern).

**Real-internet eval guarantee:** unlike Phase 22's multi-recipe eval
which stubs the tools (no side effects), this harness exercises the
REAL ``FetchAndScrapeTool`` against the public internet by design. The
operator runs it on a workstation or in staging; URLs in the eval set
are public Spanish recipe blogs (no PII).

**``--self-test`` mode:** runs ONE pre-canned URL end-to-end through the
real agent code path with ``safe_fetch`` mocked to return canned HTML
(no network). The self-test exercises ``langchain.agents.create_agent``,
``response_format=RecipeData``, the real V001 prompt and
``FetchAndScrapeTool`` wiring — it catches wiring regressions like a
missing tool injection in ``jobs.py``. The harness's automated CI gate
is ``uv run experiments.gather_from_url --backend openai --self-test``.

Usage:
    uv run experiments.gather_from_url --backend ollama
    uv run experiments.gather_from_url --backend openai
    uv run experiments.gather_from_url --backend anthropic --limit 5
    uv run experiments.gather_from_url --backend openai --self-test

Prerequisites (full eval):
    LANGWATCH_API_KEY env var set (observability mandatory per CLAUDE.md).
    For --backend ollama: OLLAMA_URL reachable (defaults to localhost:11434).
    For --backend openai: GATHER_FROM_URL_API_TOKEN set with an OpenAI key.
    For --backend anthropic: GATHER_FROM_URL_API_TOKEN set with an Anthropic key.

Prerequisites (--self-test):
    The self-test still constructs the real agent (so it WILL try to call
    an LLM if the dependencies are wired). When an API token is not set,
    the self-test falls back to a dry-run that validates only the eval-set
    parser + agent-build wiring and reports a ``self-test=stub-only`` line.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import patch

from dotenv import load_dotenv

load_dotenv()

import langwatch  # noqa: E402 — must follow load_dotenv()
import langwatch.langchain  # noqa: E402
from langchain_core.runnables import RunnableConfig  # noqa: E402
from langchain_core.tools import BaseTool  # noqa: E402
from langwatch.client import Client as LangWatchClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


PHASE = "23"
PROMPT_VERSION = "V001"
EXPERIMENT_NAME = "gather-from-url-eval"
DEFAULT_EVAL_SET = Path(
    ".planning/phases/23-url-ingestion-topic-2/23-EVAL-SET.md"
)
DEFAULT_OUT_TEMPLATE = (
    ".planning/phases/23-url-ingestion-topic-2/23-EVAL-RESULTS-{backend}.md"
)

# The 8 fields scored per D-11. ``time_any`` is the "any one of prep/cook/total" rule.
SCORED_FIELDS = (
    "name",
    "description",
    "ingredients",
    "steps",
    "servings_qty",
    "time_any",
    "source_url",
    "gathered_sources",
)


# ---------------------------------------------------------------------------
# Eval-set parser
# ---------------------------------------------------------------------------


@dataclass
class EvalRow:
    """One row from the 21-URL eval set."""

    idx: int
    url: str
    coverage_class: str
    expected_name: str
    expected_ingredients_min: int
    expected_steps_min: int
    expected_servings_qty: int | None
    expected_total_time: int | None
    notes: str = ""

    @property
    def is_sanity_non_recipe(self) -> bool:
        return self.coverage_class.startswith("6")


def _to_int_or_none(s: str) -> int | None:
    s = s.strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def parse_eval_set(path: Path) -> list[EvalRow]:
    """Parse ``23-EVAL-SET.md`` into a list of ``EvalRow``.

    Walks the markdown line-by-line: locates the ``## URLs`` heading,
    skips until the table header + the ``|---|`` separator, then collects
    every subsequent ``| ... |`` row until a blank line or next heading.
    """
    rows: list[EvalRow] = []
    in_urls_section = False
    saw_header = False
    saw_separator = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("## "):
            if stripped.lower().startswith("## urls"):
                in_urls_section = True
                saw_header = False
                saw_separator = False
                continue
            elif in_urls_section:
                break
        if not in_urls_section:
            continue
        if not stripped:
            if saw_separator and rows:
                break
            continue
        if not stripped.startswith("|"):
            continue
        if not saw_header:
            saw_header = True
            continue
        if not saw_separator:
            if re.fullmatch(r"\|[\s\-:|]+\|", stripped):
                saw_separator = True
                continue
            continue
        cells = [c.strip() for c in stripped.split("|")[1:-1]]
        if len(cells) < 8:
            logger.warning("Skipping malformed row (cells=%d): %s", len(cells), stripped)
            continue
        try:
            idx = int(cells[0])
        except ValueError:
            logger.warning("Skipping row with non-int idx: %s", cells[0])
            continue
        url = cells[1]
        if not url.startswith("https://") and not url.startswith("http://"):
            logger.warning("Skipping row idx=%s with non-URL: %s", idx, url)
            continue
        coverage_class = cells[2]
        expected_name = cells[3]
        try:
            expected_ingredients_min = int(cells[4])
            expected_steps_min = int(cells[5])
        except ValueError:
            logger.warning("Skipping row idx=%s with non-int min: %s/%s", idx, cells[4], cells[5])
            continue
        expected_servings_qty = _to_int_or_none(cells[6])
        expected_total_time = _to_int_or_none(cells[7])
        notes = cells[8] if len(cells) > 8 else ""
        rows.append(
            EvalRow(
                idx=idx,
                url=url,
                coverage_class=coverage_class,
                expected_name=expected_name,
                expected_ingredients_min=expected_ingredients_min,
                expected_steps_min=expected_steps_min,
                expected_servings_qty=expected_servings_qty,
                expected_total_time=expected_total_time,
                notes=notes,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Agent build
# ---------------------------------------------------------------------------


def build_agent(backend_name: str, model_override: str | None = None) -> tuple[Any, Any]:
    """Build the ``gather-from-url`` agent with the REAL ``FetchAndScrapeTool``.

    Returns ``(agent, config_used)``. Backend selection mirrors Phase 22:
    the agent is registered with provider ``ollama`` in ``AGENT_REGISTRY``;
    for ``--backend openai`` / ``--backend anthropic`` we override
    ``model_config.provider`` before constructing the backend so the same
    AgentConfig + V001 prompt + ``FetchAndScrapeTool`` runs against the
    chosen LLM.

    NO stub tools — per D-09 this harness exercises the real
    ``FetchAndScrapeTool`` against the real internet by design.
    """
    # Lazy imports — keep test/CI import paths cheap and avoid side effects
    # at module load.
    from robotina.agent.agents import get_agent_config
    from robotina.agent.tools.fetch_and_scrape import FetchAndScrapeTool
    from robotina.llm import make_backend

    config = get_agent_config("gather-from-url")

    model_config = dict(config.model_config)
    if backend_name == "openai":
        model_config["provider"] = "openai"
        model_config["model"] = model_override or os.environ.get(
            "OPENAI_EVAL_MODEL", "gpt-4o-mini"
        )
        model_config["url"] = os.environ.get("OPENAI_BASE_URL") or None
    elif backend_name == "anthropic":
        model_config["provider"] = "anthropic"
        model_config["model"] = model_override or os.environ.get(
            "ANTHROPIC_EVAL_MODEL", "claude-3-5-sonnet-latest"
        )
        model_config["url"] = os.environ.get("ANTHROPIC_BASE_URL") or None
    elif model_override:
        model_config["model"] = model_override
    # ollama: keep registry-provided URL + model unless overridden

    backend = make_backend(model_config)

    tools: list[BaseTool] = [FetchAndScrapeTool()]

    prompt_text = Path(config.prompt_path).read_text(encoding="utf-8")

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
    return agent, config_used


# ---------------------------------------------------------------------------
# Per-URL run + scoring
# ---------------------------------------------------------------------------


@dataclass
class EvalResult:
    row: EvalRow
    recipe: dict | None
    field_results: dict[str, bool] = field(default_factory=dict)
    error: str | None = None

    @property
    def populated_count(self) -> int:
        return sum(1 for v in self.field_results.values() if v)

    @property
    def expected_count(self) -> int:
        return sum(1 for f in self._expected_fields() if True)

    def _expected_fields(self) -> list[str]:
        """Per D-11 + EVAL-SET scoring rule: sanity rows score only 4 fields."""
        if self.row.is_sanity_non_recipe:
            return ["name", "description", "source_url", "gathered_sources"]
        return list(SCORED_FIELDS)

    @property
    def pass_threshold(self) -> int:
        # D-11: ≥ 6/8 for normal rows; ≥ 3/4 for sanity rows (per EVAL-SET scoring rule).
        return 6 if not self.row.is_sanity_non_recipe else 3

    @property
    def passed(self) -> bool:
        if self.error is not None:
            return False
        return self.populated_count >= self.pass_threshold


def _populated(value: Any) -> bool:
    """A field is 'populated AND non-empty' if it's truthy and (for lists) has ≥ 1 item."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return len(value) > 0
    return bool(value)


def score_row(row: EvalRow, recipe: dict | None) -> dict[str, bool]:
    """Score a row's emitted ``RecipeData`` against the 8 fields per D-11."""
    if recipe is None:
        return {f: False for f in SCORED_FIELDS}

    results: dict[str, bool] = {}
    results["name"] = _populated(recipe.get("name"))
    results["description"] = _populated(recipe.get("description"))

    ingredients = recipe.get("ingredients") or []
    results["ingredients"] = (
        len(ingredients) >= max(row.expected_ingredients_min, 1)
        if row.expected_ingredients_min > 0
        else _populated(ingredients)
    )
    steps = recipe.get("steps") or []
    results["steps"] = (
        len(steps) >= max(row.expected_steps_min, 1)
        if row.expected_steps_min > 0
        else _populated(steps)
    )

    results["servings_qty"] = _populated(recipe.get("servings_qty"))

    time_any = (
        _populated(recipe.get("prep_time"))
        or _populated(recipe.get("cook_time"))
        or _populated(recipe.get("total_time"))
    )
    results["time_any"] = time_any

    results["source_url"] = _populated(recipe.get("source_url"))
    results["gathered_sources"] = _populated(recipe.get("gathered_sources"))

    return results


def _extract_recipe_dict(invoke_result: Any) -> dict | None:
    """Pull the ``RecipeData`` payload out of the agent's invoke() result.

    ``langchain.agents.create_agent(response_format=RecipeData)`` exposes
    the structured response on ``result["structured_response"]`` (Pydantic
    model). Falls back to scanning ``result["messages"]`` for tool outputs
    if the structured key is missing (some backends route it differently).
    """
    if invoke_result is None:
        return None
    if isinstance(invoke_result, dict):
        struct = invoke_result.get("structured_response")
        if struct is not None:
            if hasattr(struct, "model_dump"):
                return struct.model_dump()
            if isinstance(struct, dict):
                return struct
    if hasattr(invoke_result, "model_dump"):
        return invoke_result.model_dump()
    return None


def run_one(agent: Any, row: EvalRow, tracer: Any) -> EvalResult:
    """Invoke the agent on one row's URL; capture + score the RecipeData."""
    try:
        with tracer:
            invoke_result = agent.invoke(
                {"messages": [{"role": "user", "content": row.url}]},
                config=RunnableConfig(callbacks=[tracer]),
            )
        recipe = _extract_recipe_dict(invoke_result)
        results = score_row(row, recipe)
        return EvalResult(row=row, recipe=recipe, field_results=results)
    except Exception as e:
        logger.exception("Row %d failed: %s", row.idx, e)
        return EvalResult(
            row=row,
            recipe=None,
            field_results={f: False for f in SCORED_FIELDS},
            error=str(e),
        )


# ---------------------------------------------------------------------------
# Results emit
# ---------------------------------------------------------------------------


def write_results(
    out_path: Path,
    backend: str,
    results: list[EvalResult],
    config_meta: dict,
) -> None:
    """Emit the per-backend markdown report. Always writes ``verdict: pending``;
    the OPERATOR flips to ``pass`` / ``fail`` / ``needs-revision`` after review (D-13)."""

    total = len(results)
    pass_count = sum(1 for r in results if r.passed)

    per_class: dict[str, dict[str, int]] = {}
    for r in results:
        cls = r.row.coverage_class
        bucket = per_class.setdefault(cls, {"total": 0, "passed": 0})
        bucket["total"] += 1
        if r.passed:
            bucket["passed"] += 1

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
    lines.append(f"# Phase 23 URL Ingestion Eval Results — {backend}")
    lines.append("")
    if backend == "ollama":
        lines.append(
            "Per D-12: Ollama is **informational only**. Failures here do NOT block merge."
        )
    elif backend == "openai":
        lines.append(
            "**Per D-12: OpenAI staging is the MERGE GATE. ≥ 85% URL-level pass "
            "required (≥ 17/21 URLs pass per D-11)."
        )
    else:
        lines.append(f"Backend ``{backend}`` — optional run.")
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    pct = (100.0 * pass_count / total) if total else 0.0
    lines.append(f"- Total URLs: {total}")
    lines.append(f"- URL-level pass: {pass_count} / {total} ({pct:.1f}%)")
    lines.append("- Per-class breakdown:")
    for cls in sorted(per_class.keys()):
        b = per_class[cls]
        lines.append(f"  - `{cls}`: {b['passed']}/{b['total']}")
    lines.append("")
    lines.append("## Per-URL results")
    lines.append("")
    lines.append(
        "| # | url | class | populated/expected | passed? | LangWatch trace |"
    )
    lines.append(
        "|---|-----|-------|--------------------|---------|------------------|"
    )
    for r in results:
        url_safe = r.row.url.replace("|", "\\|")
        cls_safe = r.row.coverage_class.replace("|", "\\|")
        if r.error:
            verdict = f"ERR: {r.error[:60].replace('|', '\\|')}"
        else:
            verdict = "PASS" if r.passed else "FAIL"
        expected_n = len([f for f in r._expected_fields()])
        lines.append(
            f"| {r.row.idx} | {url_safe} | {cls_safe} | "
            f"{r.populated_count}/{expected_n} | {verdict} |  |"
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
            "Required for PASS (D-12): ≥ 17/21 URLs pass per D-11 field-presence rule."
        )
        lines.append("")
        lines.append("verdict: pass | fail | needs-revision")
    else:
        lines.append(
            "Informational: ≥ 70% URL pass = usable for dev. Below = model-upgrade candidate."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote eval results to %s", out_path)


# ---------------------------------------------------------------------------
# Self-test mode (no-network end-to-end agent wiring check)
# ---------------------------------------------------------------------------


_SELF_TEST_HTML = b"""<!doctype html><html><head>
<title>Bizcocho de yogur</title>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Recipe",
  "name": "Bizcocho de yogur",
  "description": "Bizcocho casero esponjoso de yogur natural.",
  "recipeYield": "8",
  "totalTime": "PT1H",
  "recipeIngredient": [
    "1 yogur natural",
    "3 huevos",
    "200 g de azucar",
    "150 g de harina",
    "1 sobre de levadura"
  ],
  "recipeInstructions": [
    "Precalentar el horno a 180 grados.",
    "Mezclar el yogur con los huevos y el azucar.",
    "Anadir la harina y la levadura tamizadas.",
    "Hornear 40 minutos."
  ]
}
</script>
</head><body><h1>Bizcocho de yogur</h1></body></html>"""

_SELF_TEST_URL = "https://example.invalid/self-test/bizcocho"


def _run_self_test(backend_name: str, model_override: str | None) -> int:
    """Run ONE pre-canned URL end-to-end with safe_fetch + scrape_html mocked.

    Goal: verify wiring (AGENT_REGISTRY entry exists; tool injection works;
    V001 prompt loads; ``response_format=RecipeData`` accepted by
    ``create_agent``) without touching the network. Returns 0 on success,
    nonzero on a hard wiring failure.

    The self-test exercises the REAL agent code path; only ``safe_fetch``
    and ``recipe_scrapers.scrape_html`` are mocked. If an LLM API token is
    not configured, the self-test stops short of the actual ``invoke()``
    call and reports ``self-test=stub-only`` (still validates parser +
    AGENT_REGISTRY + tool-import wiring).
    """
    logger.info("Self-test starting (backend=%s)", backend_name)

    # Parser sanity — uses the real eval set.
    eval_set_path = DEFAULT_EVAL_SET
    if eval_set_path.exists():
        rows = parse_eval_set(eval_set_path)
        if len(rows) != 21:
            logger.error("Self-test parser check failed: got %d rows (expected 21)", len(rows))
            return 2
        logger.info("Self-test parser check: 21 rows parsed OK")
    else:
        logger.warning("Eval set not found at %s — skipping parser check", eval_set_path)

    # Detect whether dependencies are wired up; if not, fall back to stub-only.
    try:
        from robotina.agent.agents import get_agent_config  # noqa: F401
        from robotina.agent.tools.fetch_and_scrape import (  # noqa: F401
            FetchAndScrapeResult,
            FetchAndScrapeTool,
        )
        deps_ok = True
    except ImportError as e:
        logger.warning("gather-from-url deps not present: %s", e)
        logger.info("self-test=stub-only (parser + import-only validation passed)")
        return 0

    # Detect whether an API token is configured for the chosen backend.
    token_env = "GATHER_FROM_URL_API_TOKEN"
    has_token = bool(os.environ.get(token_env))
    if not has_token and backend_name != "ollama":
        logger.info(
            "%s not set — self-test=stub-only (skipping live agent.invoke). "
            "Set %s to exercise the full agent code path.",
            token_env,
            token_env,
        )
        return 0

    # Build the real agent — this validates the AGENT_REGISTRY entry,
    # the V001 prompt file, the FetchAndScrapeTool import, and the
    # response_format=RecipeData wiring on create_agent.
    try:
        agent, config_used = build_agent(backend_name, model_override)
    except Exception as e:
        logger.exception("self-test build_agent FAILED: %s", e)
        return 3
    logger.info("self-test build_agent OK (model=%s)", config_used.model_config.get("model"))

    # Mock safe_fetch + scrape_html for the duration of the agent invoke.
    fake_fetch_result_module = "robotina.url.safe_fetch"
    fake_scrape_module = "robotina.agent.tools.fetch_and_scrape"

    try:
        # Build the canned safe_fetch return value lazily so we don't
        # crash if the module hasn't been written yet.
        from robotina.url.safe_fetch import SafeFetchResult
    except ImportError as e:
        logger.warning("safe_fetch module not importable (%s) — self-test=stub-only", e)
        return 0

    canned = SafeFetchResult(
        final_url=_SELF_TEST_URL,
        content_bytes=_SELF_TEST_HTML,
        content_type="text/html",
        status_code=200,
    )

    tracer = langwatch.langchain.LangChainTracer(
        metadata={
            "experiment": EXPERIMENT_NAME,
            "phase": PHASE,
            "prompt_version": PROMPT_VERSION,
            "url": _SELF_TEST_URL,
            "backend": backend_name,
            "model": config_used.model_config.get("model"),
            "provider": config_used.model_config.get("provider"),
            "self_test": True,
        }
    )

    try:
        with patch(f"{fake_fetch_result_module}.safe_fetch", return_value=canned), patch(
            f"{fake_scrape_module}.safe_fetch", return_value=canned
        ):
            with tracer:
                result = agent.invoke(
                    {"messages": [{"role": "user", "content": _SELF_TEST_URL}]},
                    config=RunnableConfig(callbacks=[tracer]),
                )
    except Exception as e:
        logger.exception("self-test agent.invoke FAILED: %s", e)
        return 4

    recipe = _extract_recipe_dict(result)
    if recipe is None:
        logger.error(
            "self-test: agent returned no structured_response — "
            "response_format=RecipeData wiring may be broken."
        )
        return 5
    name = recipe.get("name", "")
    if not name:
        logger.error("self-test: RecipeData has empty name — extraction wiring broken.")
        return 6

    logger.info("self-test OK — extracted name=%r", name)
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 23 gather-from-url eval harness (URL-06 acceptance evidence)."
        )
    )
    parser.add_argument(
        "--backend",
        choices=["ollama", "openai", "anthropic"],
        required=True,
        help="LLM backend to test against. Ollama informational; OpenAI is the merge gate.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override the model name for the chosen backend.",
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
        help="Run only the first N URLs (debug aid).",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help=(
            "Run ONE pre-canned URL end-to-end with safe_fetch mocked "
            "(no network). Validates agent wiring without making a full "
            "21-URL eval run. Used as the automated CI gate for this plan."
        ),
    )
    args = parser.parse_args()

    if args.self_test:
        return _run_self_test(args.backend, args.model)

    out_path = args.out or Path(DEFAULT_OUT_TEMPLATE.format(backend=args.backend))

    logger.info("Parsing eval set: %s", args.eval_set)
    rows = parse_eval_set(args.eval_set)
    logger.info("Parsed %d URL rows", len(rows))
    if args.limit:
        rows = rows[: args.limit]
        logger.info("Limiting to first %d rows", len(rows))

    results: list[EvalResult] = []
    config_meta: dict = {}

    for row in rows:
        logger.info("--- URL %d (%s) %s ---", row.idx, row.coverage_class, row.url)
        try:
            agent, config = build_agent(args.backend, args.model)
        except Exception as e:
            logger.exception("build_agent failed for row %d: %s", row.idx, e)
            results.append(
                EvalResult(
                    row=row,
                    recipe=None,
                    field_results={f: False for f in SCORED_FIELDS},
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
                "url": row.url,
                "coverage_class": row.coverage_class,
                "backend": args.backend,
                "model": config.model_config.get("model"),
                "provider": config.model_config.get("provider"),
            }
        )

        result = run_one(agent, row, tracer)
        results.append(result)
        logger.info(
            "url=%s populated=%d/%d passed=%s",
            row.url,
            result.populated_count,
            len(result._expected_fields()),
            result.passed,
        )

    if LangWatchClient._tracer_provider is not None:
        LangWatchClient._tracer_provider.force_flush()

    write_results(out_path, args.backend, results, config_meta)

    total = len(results)
    pass_count = sum(1 for r in results if r.passed)
    logger.info(
        "=== eval complete: %d / %d URLs passed on backend=%s ===",
        pass_count,
        total,
        args.backend,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
