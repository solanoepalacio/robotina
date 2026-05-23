"""experiments.recipe_image — Phase 24 manual eval harness for recipe-image acquisition.

Per Phase 24 / D-09 / EXP-03. Iterates a 10-15-row fixture set
(``24-IMG-EVAL-SET.md``), calls ``acquire_recipe_image`` directly (no
workflow round-trip, no DB), captures candidate URL + which branch fired
+ ``safe_fetch`` verdict + LangWatch trace tag. Emits a markdown results
table with ``verdict: pending`` frontmatter for operator review (24-09).

Coverage classes (per D-09): source-page-hit, source-page-miss,
query-only, known-difficult, sanity-miss.

Backend label is informational only — the task is deterministic.
Backend variance comes from Tavily's day-to-day drift, not a model swap.

Usage:
    uv run experiments.recipe_image --backend tavily-live
    uv run experiments.recipe_image --backend tavily-live --limit 5
    uv run experiments.recipe_image --backend mock --eval-set <path> --out <path>

Prerequisites:
    TAVILY_API_KEY env var set (the deterministic function reads it).
    LANGWATCH_API_KEY env var set (observability mandatory per CLAUDE.md).
    HOUSEHOLD_ID env var set (otherwise defaults to "dev-os" for the
    synthetic RecipeImageInput).
"""
from __future__ import annotations

import argparse
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

import langwatch  # noqa: E402 — must follow load_dotenv()
from langwatch.client import Client as LangWatchClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


PHASE = "24"
EXPERIMENT_NAME = "recipe-image-eval"
DEFAULT_EVAL_SET = Path(
    ".planning/phases/24-recipe-images-topic-3/24-IMG-EVAL-SET.md"
)
DEFAULT_OUT_TEMPLATE = (
    ".planning/phases/24-recipe-images-topic-3/24-IMG-EVAL-RESULTS-{backend}.md"
)


# ---------------------------------------------------------------------------
# Eval-set parser
# ---------------------------------------------------------------------------


@dataclass
class EvalRow:
    """One row from the 24-IMG-EVAL-SET fixture."""

    idx: int
    coverage_class: str
    recipe_name: str
    source_url: str | None  # None when the cell is "(none)" / empty
    expected_branch: str  # one of: source_page, tavily, miss_expected
    notes: str = ""


def _normalize_source_url(cell: str) -> str | None:
    """Convert eval-set source-url cell to a URL or None.

    The fixture uses the literal ``(none)`` (or an empty cell) to mark
    rows with no source URL — those rows exercise the Tavily-only
    branch. Any value that doesn't start with ``http://`` / ``https://``
    is treated as "no source URL" UNLESS it's the sanity-miss sentinel
    pointing at a non-routable TLD (``invalid.example.localhost.invalid``),
    which we DO want to pass through to ``acquire_recipe_image`` so its
    ``safe_fetch`` defenses are exercised.
    """
    s = cell.strip()
    if not s or s.lower() == "(none)":
        return None
    if s.startswith("http://") or s.startswith("https://"):
        return s
    # Defensive: anything else is a parser error or a deliberately broken
    # synthetic URL. Pass through so the function exercises its own
    # validation; the harness still records the row.
    return s


def parse_eval_set(path: Path) -> list[EvalRow]:
    """Parse ``24-IMG-EVAL-SET.md`` into a list of ``EvalRow``.

    Walks the markdown line-by-line: locates the ``## Rows`` heading,
    skips until the table header + the ``|---|`` separator, then collects
    every subsequent ``| ... |`` row until a blank line or next heading.
    """
    rows: list[EvalRow] = []
    in_rows_section = False
    saw_header = False
    saw_separator = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("## "):
            if stripped.lower().startswith("## rows"):
                in_rows_section = True
                saw_header = False
                saw_separator = False
                continue
            elif in_rows_section:
                break
        if not in_rows_section:
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
        if len(cells) < 5:
            logger.warning(
                "Skipping malformed row (cells=%d): %s", len(cells), stripped
            )
            continue
        try:
            idx = int(cells[0])
        except ValueError:
            # Skip non-data rows (e.g. distribution-table headers if any
            # leak into the section).
            continue

        coverage_class = cells[1]
        recipe_name = cells[2]
        source_url = _normalize_source_url(cells[3])
        expected_branch = cells[4]
        notes = cells[5] if len(cells) > 5 else ""

        rows.append(
            EvalRow(
                idx=idx,
                coverage_class=coverage_class,
                recipe_name=recipe_name,
                source_url=source_url,
                expected_branch=expected_branch,
                notes=notes,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Branch detection
# ---------------------------------------------------------------------------


def _hosts_match(candidate_url: str | None, source_url: str | None) -> bool:
    """Best-effort host-match for branch-fired detection.

    Returns True only when both URLs parse and share a host suffix
    (handles www-prefixed vs bare; CDN subdomains return False so they
    show up as the Tavily branch — that's the desired classification
    since the recipe-scrapers ``.image()`` would have returned the
    source-page's own ``<img>`` URL, which is normally on the same host
    or a closely-related CDN. False positives are acceptable here — the
    operator reviews the actual URLs visually.)
    """
    if not candidate_url or not source_url:
        return False
    try:
        c_host = urlparse(candidate_url).netloc.lower().lstrip("www.")
        s_host = urlparse(source_url).netloc.lower().lstrip("www.")
    except Exception:
        return False
    if not c_host or not s_host:
        return False
    if c_host == s_host:
        return True
    # Tolerate well-known same-origin CDN suffixes (e.g. paulinacocina.net
    # serving images from a CloudFront subdomain). Conservative: require
    # the registered-domain tail to match.
    c_tail = ".".join(c_host.split(".")[-2:])
    s_tail = ".".join(s_host.split(".")[-2:])
    return c_tail == s_tail


# ---------------------------------------------------------------------------
# Per-row run
# ---------------------------------------------------------------------------


@dataclass
class RowResult:
    """The captured outcome of one row through acquire_recipe_image."""

    idx: int
    coverage_class: str
    recipe_name: str
    source_url: str | None
    expected_branch: str
    candidate_url: str | None = None
    branch_fired: str = "n/a"  # source_page | tavily | miss | validation_failed | exception
    safe_fetch_ok: bool | None = None
    error: str | None = None


def _build_input(row: EvalRow) -> Any:
    """Construct a synthetic RecipeImageInput for the row."""
    # Lazy import — keep module import path cheap (this script's
    # ``--help`` must work even when the runtime deps aren't loaded).
    from robotina.queue.task_types import (
        RecipeImageInput,
        RecipeData,
        ReplyContext,
    )

    recipe = RecipeData(
        name=row.recipe_name,
        source_url=row.source_url,
        ingredients=[],
        steps=[],
    )
    return RecipeImageInput(
        recipe=recipe,
        # ReplyContext requires a known platform Literal; "telegram" is the
        # only currently-supported value. The deterministic function does
        # not consume reply_context, so the platform value is informational.
        reply_context=ReplyContext(
            platform="telegram",
            chat_id="0",
            user_id="0",
        ),
        household_id=os.environ.get("HOUSEHOLD_ID", "dev-os"),
    )


def run_one(row: EvalRow, backend: str) -> RowResult:
    """Invoke acquire_recipe_image directly under a LangWatch trace."""
    # Lazy imports — fail loudly only when actually running a row, not at
    # ``--help`` time.
    from robotina.agent.tasks.recipe_image import (
        acquire_recipe_image,
        RecipeImageAcquisitionError,
    )
    from robotina.url.safe_fetch import SafeFetchError

    task_input = _build_input(row)

    result = RowResult(
        idx=row.idx,
        coverage_class=row.coverage_class,
        recipe_name=row.recipe_name,
        source_url=row.source_url,
        expected_branch=row.expected_branch,
    )

    # LangWatch trace wrap mirrors the recipe-image branch in jobs.py
    # (Pitfall 8 — deterministic branches need their own wrap because
    # they return before the LLM-path tracer).
    trace_ctx: Any = None
    try:
        trace_ctx = langwatch.trace(
            metadata={
                "experiment": EXPERIMENT_NAME,
                "phase": PHASE,
                "recipe_name": row.recipe_name,
                "coverage_class": row.coverage_class,
                "expected_branch": row.expected_branch,
                "source_url": row.source_url or "",
                "backend": backend,
            }
        )
    except Exception as exc:  # langwatch unconfigured / endpoint unreachable
        logger.warning(
            "langwatch.trace setup failed (continuing without tracing) | err=%s",
            exc,
        )
        trace_ctx = None

    def _invoke() -> None:
        try:
            output = acquire_recipe_image(task_input)
            candidate = getattr(output, "image_url", None)
            result.candidate_url = candidate
            result.safe_fetch_ok = True
            if _hosts_match(candidate, row.source_url):
                result.branch_fired = "source_page"
            else:
                result.branch_fired = "tavily"
        except RecipeImageAcquisitionError as exc:
            result.branch_fired = "miss"
            result.safe_fetch_ok = None
            result.error = str(exc)
        except SafeFetchError as exc:
            result.branch_fired = "validation_failed"
            result.safe_fetch_ok = False
            result.error = str(exc)
        except Exception as exc:  # noqa: BLE001 — observability concern; classify all
            result.branch_fired = "exception"
            result.safe_fetch_ok = None
            result.error = f"{type(exc).__name__}: {exc}"

    if trace_ctx is not None:
        try:
            with trace_ctx:
                _invoke()
        except Exception as exc:  # noqa: BLE001 — trace wrap failure must not poison the row
            logger.warning(
                "langwatch.trace context failed (running row outside trace) | err=%s",
                exc,
            )
            _invoke()
    else:
        _invoke()

    return result


# ---------------------------------------------------------------------------
# Results emit
# ---------------------------------------------------------------------------


def write_results(
    out_path: Path,
    backend: str,
    results: list[RowResult],
    operator: str,
) -> None:
    """Emit the per-backend markdown report with ``verdict: pending``.

    The operator (24-09) reviews each candidate URL visually, fills the
    "image looks right?" cells, and flips ``verdict`` to ``pass`` |
    ``fail`` | ``needs-revision``.
    """
    total = len(results)
    source_page_hits = sum(1 for r in results if r.branch_fired == "source_page")
    tavily_hits = sum(1 for r in results if r.branch_fired == "tavily")
    miss_count = sum(
        1 for r in results if r.branch_fired in ("miss", "validation_failed", "exception")
    )

    lines: list[str] = []
    lines.append("---")
    lines.append("verdict: pending")
    lines.append(f"backend: {backend}")
    lines.append("eval_set_version: 1")
    lines.append(f"phase: {PHASE}")
    lines.append(f"date: {date.today().isoformat()}")
    lines.append(f"operator: {operator}")
    lines.append("---")
    lines.append("")
    lines.append(f"# 24-IMG-EVAL-RESULTS — {backend}")
    lines.append("")
    lines.append(
        "Per Phase 24 / D-09 / EXP-03. The harness "
        "(`uv run experiments.recipe_image --backend {backend}`) writes "
        "this file with `verdict: pending`; the operator (24-09) reviews "
        "candidate URLs and stamps the verdict."
    )
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    lines.append(f"- Total rows: {total}")
    lines.append(f"- Source-page hits: {source_page_hits}")
    lines.append(f"- Tavily hits: {tavily_hits}")
    lines.append(f"- Misses / validation failures / exceptions: {miss_count}")
    lines.append("")
    lines.append("## Per-row results")
    lines.append("")
    lines.append(
        "| idx | class | recipe | source_url | expected | candidate_url | "
        "branch_fired | safe_fetch_ok | image looks right? | error |"
    )
    lines.append(
        "|-----|-------|--------|------------|----------|---------------|"
        "--------------|---------------|--------------------|-------|"
    )
    for r in results:
        source_safe = (r.source_url or "").replace("|", "\\|")
        candidate_safe = (r.candidate_url or "").replace("|", "\\|")
        error_safe = (r.error or "").replace("|", "\\|").replace("\n", " ")
        if len(error_safe) > 80:
            error_safe = error_safe[:80] + "…"
        if r.safe_fetch_ok is True:
            sf_cell = "true"
        elif r.safe_fetch_ok is False:
            sf_cell = "false"
        else:
            sf_cell = "n/a"
        lines.append(
            f"| {r.idx} | {r.coverage_class} | {r.recipe_name} | "
            f"{source_safe} | {r.expected_branch} | {candidate_safe} | "
            f"{r.branch_fired} | {sf_cell} | _operator: Y/N_ | {error_safe} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("_operator-fillable._")
    lines.append("")
    lines.append("## Go / No-Go")
    lines.append("")
    lines.append(
        "- [ ] ≥ 60% of Tavily-branch rows have \"image looks right?\" = Y "
        "(Pitfall 8 gate per D-11)"
    )
    lines.append(
        "- [ ] All sanity-miss rows result in `branch_fired ∈ "
        "{miss, validation_failed, exception}` (StepUnavailableArtifact path)"
    )
    lines.append(
        "- [ ] No `SafeFetchError` on legitimate URLs (rows 1-12) — "
        "`safe_fetch_ok` is `true` or `n/a`, never `false`"
    )
    lines.append("")
    lines.append("verdict: pending")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote eval results to %s", out_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 24 recipe-image eval harness (EXP-03). Iterates the "
            "24-IMG-EVAL-SET fixture and calls acquire_recipe_image "
            "directly; emits a verdict: pending markdown table for "
            "operator (24-09) review."
        )
    )
    parser.add_argument(
        "--backend",
        type=str,
        required=True,
        help=(
            "Label-only string (e.g. 'tavily-live', 'tavily-mock'). Informs "
            "the results filename and LangWatch metadata tag. The task is "
            "deterministic — variance comes from Tavily's day-to-day drift."
        ),
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
        help="Run only the first N rows (debug aid).",
    )
    parser.add_argument(
        "--operator",
        type=str,
        default=os.environ.get("USER", "auto-fill"),
        help="Operator label written into the results frontmatter.",
    )
    args = parser.parse_args()

    out_path = args.out or Path(DEFAULT_OUT_TEMPLATE.format(backend=args.backend))

    logger.info("Parsing eval set: %s", args.eval_set)
    rows = parse_eval_set(args.eval_set)
    logger.info("Parsed %d eval rows", len(rows))
    if args.limit:
        rows = rows[: args.limit]
        logger.info("Limiting to first %d rows", len(rows))

    results: list[RowResult] = []
    for row in rows:
        logger.info(
            "--- ROW %d (%s) %s ---",
            row.idx, row.coverage_class, row.recipe_name,
        )
        result = run_one(row, args.backend)
        results.append(result)
        logger.info(
            "row=%d branch=%s candidate=%s error=%s",
            row.idx, result.branch_fired,
            (result.candidate_url or "")[:120],
            (result.error or "")[:120],
        )

    # Flush LangWatch traces before writing results (mirrors gather_from_url).
    if LangWatchClient._tracer_provider is not None:
        try:
            LangWatchClient._tracer_provider.force_flush()
        except Exception as exc:  # noqa: BLE001 — flush failure shouldn't lose results
            logger.warning("LangWatch flush failed: %s", exc)

    write_results(out_path, args.backend, results, args.operator)

    total = len(results)
    sp = sum(1 for r in results if r.branch_fired == "source_page")
    tv = sum(1 for r in results if r.branch_fired == "tavily")
    miss = sum(
        1 for r in results if r.branch_fired in ("miss", "validation_failed", "exception")
    )
    logger.info(
        "=== eval complete: total=%d source_page=%d tavily=%d miss=%d (backend=%s) ===",
        total, sp, tv, miss, args.backend,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
