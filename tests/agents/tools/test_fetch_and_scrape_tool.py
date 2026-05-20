"""Unit tests for FetchAndScrapeTool (URL-02 / D-03).

All network-touching dependencies are mocked at the import paths used by the
tool's lazy imports inside `_run`:

  - `robotina.url.safe_fetch.safe_fetch`
  - `recipe_scrapers.scrape_html`
  - `trafilatura.extract`

Each test covers exactly one behavioral path the plan calls out:

  - SafeFetchError propagates (no rescue inside the tool).
  - Happy path with quality-gate-passing recipe.
  - Per-method recipe-scrapers exception isolation (Pitfall 7).
  - Quality gate fail (too-few ingredients / no steps / no title) → trafilatura.
  - servings_qty string-to-int coercion (`"4 personas"` → 4, `"muchas"` → None).
  - source_url fallback to fetched.final_url when canonical_url raises.
  - Tool returns a JSON string parseable by FetchAndScrapeResult.
  - html_text capped at 200_000 chars.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from robotina.agent.tools.fetch_and_scrape import (
    FetchAndScrapeArgs,
    FetchAndScrapeResult,
    FetchAndScrapeTool,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_fetched(
    *,
    final_url: str = "https://example.com/recipe",
    html: str = "<html><body>hello</body></html>",
    content_type: str = "text/html",
    status_code: int = 200,
):
    """Build a minimal stand-in for SafeFetchResult.

    The tool only reads .final_url and .content_bytes, so a MagicMock with
    those attributes is sufficient and avoids importing the real class
    (which would also pull pydantic validation noise into the test).
    """
    fetched = MagicMock()
    fetched.final_url = final_url
    fetched.content_bytes = html.encode("utf-8")
    fetched.content_type = content_type
    fetched.status_code = status_code
    return fetched


def _make_scraper(
    *,
    title="Pasta Bolognesa",
    description="A classic",
    total_time=30,
    prep_time=10,
    cook_time=20,
    yields="4 personas",
    canonical_url="https://example.com/recipe",
    ingredients=("200g pasta", "100g carne", "tomate"),
    instructions_list=("Cook pasta", "Add sauce"),
):
    """Build a MagicMock scraper with controllable method return values.

    Pass ``Exception(...)`` instances or callables that raise to simulate
    per-field failures; pass ``None`` to simulate "no data for that field".
    """
    scraper = MagicMock()

    def _bind(method_name, value):
        if isinstance(value, Exception):
            getattr(scraper, method_name).side_effect = value
        else:
            getattr(scraper, method_name).return_value = value

    _bind("title", title)
    _bind("description", description)
    _bind("total_time", total_time)
    _bind("prep_time", prep_time)
    _bind("cook_time", cook_time)
    _bind("yields", yields)
    _bind("canonical_url", canonical_url)
    _bind("ingredients", list(ingredients) if ingredients is not None else [])
    _bind(
        "instructions_list",
        list(instructions_list) if instructions_list is not None else [],
    )
    return scraper


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_tool_is_base_tool_with_correct_name():
    """Sanity: tool name + args_schema reachable."""
    tool = FetchAndScrapeTool()
    assert tool.name == "fetch-and-scrape"
    assert tool.args_schema is FetchAndScrapeArgs


def test_safe_fetch_error_propagates():
    """D-03: SafeFetchError must re-raise out of _run (no rescue inside the tool)."""
    from robotina.url.safe_fetch import SafeFetchError

    with patch(
        "robotina.url.safe_fetch.safe_fetch",
        side_effect=SafeFetchError("Scheme not allowed: ftp://example.com"),
    ):
        tool = FetchAndScrapeTool()
        with pytest.raises(SafeFetchError, match="Scheme not allowed"):
            tool._run("ftp://example.com/recipe")


def test_full_recipe_extracts_via_scraper():
    """Happy path: scraper returns valid data passing quality gate."""
    scraper = _make_scraper()
    fetched = _make_fetched(final_url="https://example.com/r")

    with patch("robotina.url.safe_fetch.safe_fetch", return_value=fetched), \
         patch("recipe_scrapers.scrape_html", return_value=scraper):
        tool = FetchAndScrapeTool()
        out = tool._run("https://example.com/r")

    payload = json.loads(out)
    assert payload["source_url"] == "https://example.com/r"
    assert payload["scraped_recipe"] is not None
    assert payload["html_text"] is None
    recipe = payload["scraped_recipe"]
    assert recipe["name"] == "Pasta Bolognesa"
    assert len(recipe["ingredients"]) == 3
    assert recipe["ingredients"][0]["food_name"] == "200g pasta"
    assert len(recipe["steps"]) == 2
    assert recipe["steps"][0]["body"] == "Cook pasta"
    assert recipe["servings_qty"] == 4
    assert recipe["total_time"] == 30


def test_recipe_scrapers_exception_per_field_isolated():
    """Pitfall 7: a single broken scraper method must not abort extraction."""
    # total_time() raises but the rest succeed — quality gate still passes.
    scraper = _make_scraper(total_time=RuntimeError("boom"))
    fetched = _make_fetched()

    with patch("robotina.url.safe_fetch.safe_fetch", return_value=fetched), \
         patch("recipe_scrapers.scrape_html", return_value=scraper):
        tool = FetchAndScrapeTool()
        out = tool._run("https://example.com/r")

    payload = json.loads(out)
    assert payload["scraped_recipe"] is not None
    assert payload["scraped_recipe"]["name"] == "Pasta Bolognesa"
    # total_time field was isolated and dropped (None default on RecipeData).
    assert payload["scraped_recipe"]["total_time"] is None
    # Other fields still populated.
    assert len(payload["scraped_recipe"]["ingredients"]) == 3
    assert len(payload["scraped_recipe"]["steps"]) == 2


def test_too_few_ingredients_falls_back_to_html_text():
    """Quality gate: 1 ingredient < 2 → trafilatura fallback."""
    scraper = _make_scraper(ingredients=("only one",))
    fetched = _make_fetched()

    with patch("robotina.url.safe_fetch.safe_fetch", return_value=fetched), \
         patch("recipe_scrapers.scrape_html", return_value=scraper), \
         patch("trafilatura.extract", return_value="clean body text here"):
        tool = FetchAndScrapeTool()
        out = tool._run("https://example.com/r")

    payload = json.loads(out)
    assert payload["scraped_recipe"] is None
    assert payload["html_text"] == "clean body text here"


def test_no_steps_falls_back_to_html_text():
    """Quality gate: 0 steps → trafilatura fallback."""
    scraper = _make_scraper(instructions_list=())
    fetched = _make_fetched()

    with patch("robotina.url.safe_fetch.safe_fetch", return_value=fetched), \
         patch("recipe_scrapers.scrape_html", return_value=scraper), \
         patch("trafilatura.extract", return_value="fallback text"):
        tool = FetchAndScrapeTool()
        out = tool._run("https://example.com/r")

    payload = json.loads(out)
    assert payload["scraped_recipe"] is None
    assert payload["html_text"] == "fallback text"


def test_no_title_falls_back():
    """No name → RecipeData validation fails → trafilatura fallback."""
    scraper = _make_scraper(title=None)
    fetched = _make_fetched()

    with patch("robotina.url.safe_fetch.safe_fetch", return_value=fetched), \
         patch("recipe_scrapers.scrape_html", return_value=scraper), \
         patch("trafilatura.extract", return_value="no-title fallback"):
        tool = FetchAndScrapeTool()
        out = tool._run("https://example.com/r")

    payload = json.loads(out)
    assert payload["scraped_recipe"] is None
    assert payload["html_text"] == "no-title fallback"


def test_yields_string_coerced_to_int():
    """`yields()` returns 'X personas' → servings_qty extracted as int X."""
    scraper = _make_scraper(yields="4 personas")
    fetched = _make_fetched()

    with patch("robotina.url.safe_fetch.safe_fetch", return_value=fetched), \
         patch("recipe_scrapers.scrape_html", return_value=scraper):
        tool = FetchAndScrapeTool()
        out = tool._run("https://example.com/r")

    payload = json.loads(out)
    assert payload["scraped_recipe"]["servings_qty"] == 4


def test_yields_no_digits_coerced_to_none():
    """`yields()` returns 'muchas' (no digits) → servings_qty is None."""
    scraper = _make_scraper(yields="muchas")
    fetched = _make_fetched()

    with patch("robotina.url.safe_fetch.safe_fetch", return_value=fetched), \
         patch("recipe_scrapers.scrape_html", return_value=scraper):
        tool = FetchAndScrapeTool()
        out = tool._run("https://example.com/r")

    payload = json.loads(out)
    assert payload["scraped_recipe"]["servings_qty"] is None


def test_canonical_url_fallback_to_final_url():
    """`canonical_url()` raises → source_url falls back to fetched.final_url."""
    scraper = _make_scraper(canonical_url=RuntimeError("no canonical"))
    fetched = _make_fetched(final_url="https://final.example.com/recipe")

    with patch("robotina.url.safe_fetch.safe_fetch", return_value=fetched), \
         patch("recipe_scrapers.scrape_html", return_value=scraper):
        tool = FetchAndScrapeTool()
        out = tool._run("https://example.com/r")

    payload = json.loads(out)
    assert payload["scraped_recipe"]["source_url"] == "https://final.example.com/recipe"
    assert payload["source_url"] == "https://final.example.com/recipe"


def test_returns_model_dump_json_string():
    """Tool output is a string parseable into FetchAndScrapeResult."""
    scraper = _make_scraper()
    fetched = _make_fetched()

    with patch("robotina.url.safe_fetch.safe_fetch", return_value=fetched), \
         patch("recipe_scrapers.scrape_html", return_value=scraper):
        tool = FetchAndScrapeTool()
        out = tool._run("https://example.com/r")

    assert isinstance(out, str)
    parsed = FetchAndScrapeResult.model_validate_json(out)
    assert parsed.source_url == "https://example.com/recipe"
    assert parsed.scraped_recipe is not None


def test_html_text_capped_to_200k():
    """trafilatura returning 300_000 chars → html_text truncated to 200_000."""
    scraper = _make_scraper(ingredients=("solo uno",))  # force quality-gate fail
    fetched = _make_fetched()
    big_text = "x" * 300_000

    with patch("robotina.url.safe_fetch.safe_fetch", return_value=fetched), \
         patch("recipe_scrapers.scrape_html", return_value=scraper), \
         patch("trafilatura.extract", return_value=big_text):
        tool = FetchAndScrapeTool()
        out = tool._run("https://example.com/r")

    payload = json.loads(out)
    assert payload["scraped_recipe"] is None
    assert len(payload["html_text"]) == 200_000


def test_scrape_html_raises_falls_back_to_trafilatura():
    """scrape_html() itself raises → tool catches → trafilatura fallback used."""
    fetched = _make_fetched()

    with patch("robotina.url.safe_fetch.safe_fetch", return_value=fetched), \
         patch("recipe_scrapers.scrape_html", side_effect=RuntimeError("parser exploded")), \
         patch("trafilatura.extract", return_value="rescued by trafilatura"):
        tool = FetchAndScrapeTool()
        out = tool._run("https://example.com/r")

    payload = json.loads(out)
    assert payload["scraped_recipe"] is None
    assert payload["html_text"] == "rescued by trafilatura"
    assert payload["source_url"] == fetched.final_url


def test_trafilatura_returning_none_yields_empty_html_text():
    """trafilatura.extract returning None must collapse to empty string, never None."""
    scraper = _make_scraper(instructions_list=())  # force fallback
    fetched = _make_fetched()

    with patch("robotina.url.safe_fetch.safe_fetch", return_value=fetched), \
         patch("recipe_scrapers.scrape_html", return_value=scraper), \
         patch("trafilatura.extract", return_value=None):
        tool = FetchAndScrapeTool()
        out = tool._run("https://example.com/r")

    payload = json.loads(out)
    assert payload["scraped_recipe"] is None
    assert payload["html_text"] == ""


def test_args_schema_rejects_extra_fields():
    """FetchAndScrapeArgs has extra='forbid' — unknown LLM args fail validation."""
    with pytest.raises(Exception):  # pydantic.ValidationError
        FetchAndScrapeArgs.model_validate({"url": "https://x", "rogue": 1})
