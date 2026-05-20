"""fetch-and-scrape tool — deterministic URL → RecipeData extraction (URL-02 / D-03).

The gather-from-url agent calls this tool exactly once per URL. It:

  1. Calls ``safe_fetch`` (Phase 23-01) which raises ``SafeFetchError`` on any
     SSRF / abuse defense violation. Failures RE-RAISE here (D-03) — the agent
     has no recovery path; LangChain converts the exception to
     ``ToolMessage(status="error")`` and the gather-from-url step is marked
     FAILED with the SafeFetchError text in ``failure_reason``; the wake reply
     surfaces URL + reason to the user.
  2. Attempts ``recipe_scrapers.scrape_html(html, org_url=..., wild_mode=True)``.
  3. Walks the canonical field map with PER-FIELD ``try/except`` (Pitfall 7):
     a single broken method (e.g. ``total_time()``) never aborts the entire
     extraction — the other fields still populate. Exceptions from a single
     scraper method are isolated to that field.
  4. Coerces ``servings_qty`` from strings like ``"4 personas"`` via regex.
  5. Falls back ``source_url`` to ``fetched.final_url`` when the scraper's
     ``canonical_url()`` is missing or raises.
  6. Validates the partial dict against ``RecipeData`` (only ``name`` required).
  7. Applies the QUALITY GATE (D-19): valid recipe AND ≥ 2 ingredients AND
     ≥ 1 step. On pass → ``scraped_recipe`` populated, ``html_text`` is None.
     On fail → ``trafilatura.extract`` produces plain text, capped to
     200_000 chars (D-04 + threat T-23-CTX-BLOAT), placed in ``html_text``;
     ``scraped_recipe`` is None.

Returns the result as a JSON string via ``FetchAndScrapeResult.model_dump_json()``
(LangChain BaseTool contract: tool output is str).

All heavy imports (``recipe_scrapers``, ``trafilatura``, ``safe_fetch``,
``RecipeData``) happen INSIDE ``_run`` — matches the per-job lazy-import
convention used in ``web_search.py`` so module import stays light.
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class FetchAndScrapeArgs(BaseModel):
    """Strict args schema. ``extra="forbid"`` rejects unknown LLM fields at
    args-validation time so they surface as ToolMessage(error) rather than
    silently dropping through to ``_run``."""

    model_config = ConfigDict(extra="forbid")
    url: str = Field(description="The recipe URL to fetch and parse.")


class FetchAndScrapeResult(BaseModel):
    """Tool output payload — emitted as a JSON string by ``_run``.

    Exactly one of ``scraped_recipe`` / ``html_text`` is populated:

    - When the deterministic scraper passed the quality gate:
      ``scraped_recipe`` is the ``RecipeData.model_dump(mode="json")`` dict,
      ``html_text`` is None.
    - Otherwise: ``scraped_recipe`` is None, ``html_text`` is the trafilatura
      plain-text rendering of the page (capped at 200_000 chars).

    ``source_url`` is always the URL that actually responded
    (``fetched.final_url`` after redirect resolution).
    """

    model_config = ConfigDict(extra="forbid")
    source_url: str
    scraped_recipe: dict | None = None
    html_text: str | None = None


class FetchAndScrapeTool(BaseTool):
    """Deterministic recipe-URL extractor used by the gather-from-url agent.

    See module docstring for the full flow. The tool is the SOLE entry point
    into ``safe_fetch`` from the LLM surface — and safe_fetch's exceptions
    re-raise so the engine marks the step FAILED (D-03).
    """

    name: str = "fetch-and-scrape"
    description: str = (
        "Fetch a recipe URL with SSRF defenses and attempt deterministic recipe "
        "extraction. Returns either {scraped_recipe: <RecipeData dump>, source_url, "
        "html_text: null} when extraction succeeds (>=2 ingredients AND >=1 step), "
        "OR {scraped_recipe: null, source_url, html_text: <cleaned plain text>} "
        "when extraction fails. Args: {url: <https URL>}."
    )
    args_schema: type[BaseModel] = FetchAndScrapeArgs

    def _run(self, url: str) -> str:
        # Lazy imports — keep module import light; matches web_search.py.
        import httpx

        from recipe_scrapers import scrape_html
        from recipe_scrapers._exceptions import RecipeScrapersExceptions
        from trafilatura import extract as trafilatura_extract

        from robotina.queue.task_types import RecipeData
        from robotina.url.safe_fetch import safe_fetch

        # safe_fetch failures re-raise (D-03) — DO NOT wrap in try/except.
        fetched = safe_fetch(url, expected_content_type="text/html")

        # Strip query string from the logged URL — credentials / session
        # tokens often live there (Security note from 23-01).
        try:
            safe_url = str(httpx.URL(url).copy_with(query=None))
        except Exception:
            safe_url = url
        logger.info(
            "fetch-and-scrape | url=%s final_url=%s bytes=%d",
            safe_url,
            fetched.final_url,
            len(fetched.content_bytes),
        )

        html = fetched.content_bytes.decode("utf-8", errors="replace")

        # Attempt the deterministic scraper. wild_mode=True lets recipe_scrapers
        # try its generic / wild parser even when no host-specific scraper
        # matches. RecipeScrapersExceptions is the package's base exception
        # class — catch it AND generic Exception so a single broken scraper
        # never crashes the tool.
        scraper: Any | None
        try:
            scraper = scrape_html(html, org_url=fetched.final_url, wild_mode=True)
        except RecipeScrapersExceptions:
            scraper = None
        except Exception:
            scraper = None

        partial: dict[str, Any] = {}
        if scraper is not None:
            # Per-field try/except (Pitfall 7). Each scraper method is wrapped
            # independently so a single per-method exception isolated to that
            # field; other fields proceed.
            for field_name, scraper_method in [
                ("name", "title"),
                ("description", "description"),
                ("total_time", "total_time"),
                ("prep_time", "prep_time"),
                ("cook_time", "cook_time"),
                ("servings_qty", "yields"),
                ("source_url", "canonical_url"),
            ]:
                try:
                    val = getattr(scraper, scraper_method)()
                    if val:
                        partial[field_name] = val
                except Exception:
                    pass
            try:
                ingredients_raw = scraper.ingredients()
                partial["ingredients"] = [
                    {"food_name": s} for s in ingredients_raw if s
                ]
            except Exception:
                partial["ingredients"] = []
            try:
                instructions_raw = scraper.instructions_list()
                partial["steps"] = [{"body": s} for s in instructions_raw if s]
            except Exception:
                partial["steps"] = []

        # Coerce servings_qty "4 personas" → 4. If no digits → None.
        if isinstance(partial.get("servings_qty"), str):
            import re

            m = re.search(r"\d+", partial["servings_qty"])
            partial["servings_qty"] = int(m.group()) if m else None

        # source_url fallback: scraper.canonical_url() missing → fetched.final_url.
        partial.setdefault("source_url", fetched.final_url)

        # Validate against RecipeData — only `name` is required. Failures
        # (missing name, type errors) drop us to the trafilatura fallback.
        valid_recipe: RecipeData | None = None
        if partial.get("name"):
            try:
                valid_recipe = RecipeData.model_validate(partial)
            except Exception:
                valid_recipe = None

        # Quality gate (D-19): ≥ 2 ingredients AND ≥ 1 step.
        scraped_recipe_ok = (
            valid_recipe is not None
            and len(valid_recipe.ingredients or []) >= 2
            and len(valid_recipe.steps or []) >= 1
        )

        if scraped_recipe_ok:
            result = FetchAndScrapeResult(
                source_url=fetched.final_url,
                scraped_recipe=valid_recipe.model_dump(mode="json"),
                html_text=None,
            )
            logger.info(
                "fetch-and-scrape extracted recipe | name=%r ingredients=%d steps=%d",
                valid_recipe.name,
                len(valid_recipe.ingredients),
                len(valid_recipe.steps),
            )
        else:
            cleaned = (
                trafilatura_extract(
                    html,
                    include_comments=False,
                    include_tables=True,
                    output_format="txt",
                )
                or ""
            )
            # Threat T-23-CTX-BLOAT — cap text size before placing into LLM context.
            cleaned = cleaned[:200_000]
            result = FetchAndScrapeResult(
                source_url=fetched.final_url,
                scraped_recipe=None,
                html_text=cleaned,
            )
            logger.info(
                "fetch-and-scrape fallback to html_text | chars=%d", len(cleaned)
            )

        return result.model_dump_json()

    async def _arun(self, url: str) -> str:
        return self._run(url)
