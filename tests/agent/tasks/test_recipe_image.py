"""Unit tests for acquire_recipe_image (Phase 24 / D-15).

Six named cases covering the full fallback ladder:

1. test_source_page_branch_happy_path
   — source-page .image() returns a URL; validation passes; that URL is set.
2. test_source_page_miss_falls_through_to_tavily
   — source-page .image() returns None; Tavily branch fires; Tavily URL is set.
3. test_tavily_only_when_no_source_url
   — source_url=None; only Tavily branch runs; called with f"{name} receta".
4. test_tavily_empty_raises_recipe_image_acquisition_error
   — source_url=None; Tavily returns []; RecipeImageAcquisitionError raised.
5. test_validation_safe_fetch_error_propagates
   — Tavily returns a URL but validation safe_fetch raises SafeFetchError;
     the function does NOT catch it (Pitfall 6 / D-11). The runner's
     non_fatal_on_failure flag (24-01) absorbs it generically.
6. test_source_url_safe_fetch_error_falls_through_to_tavily
   — source_url is set but the FIRST safe_fetch (source page) raises
     SafeFetchError; function falls through to Tavily.

Patch strategy: ``acquire_recipe_image`` imports its dependencies lazily
INSIDE the function body, so the standard ``patch("module.func")`` against
the consumer module's attribute does not work. Instead, every patch
targets the source module so the lazy import picks up the mock:
- ``robotina.url.safe_fetch.safe_fetch``
- ``robotina.agent.tools.tavily_image_search.tavily_image_search``
- ``recipe_scrapers.scrape_html``

This matches the test_tavily_image_search.py mocking idiom (Phase 24 / D-16).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from robotina.queue.task_types import (
    RecipeData,
    RecipeImageInput,
    ReplyContext,
)
from robotina.url.safe_fetch import SafeFetchError, SafeFetchResult


def make_input(source_url: str | None = None, name: str = "canelones de choclo") -> RecipeImageInput:
    """Build a valid RecipeImageInput for tests.

    The reply_context and household_id are required by the model but unused
    by acquire_recipe_image; we pass minimal stub values.
    """
    return RecipeImageInput(
        recipe=RecipeData(name=name, source_url=source_url),
        reply_context=ReplyContext(platform="telegram", chat_id="1", user_id="1"),
        household_id="dev-os",
    )


def _fake_safe_fetch_result(content_bytes: bytes = b"<html></html>", final_url: str = "https://example.com/recipe") -> SafeFetchResult:
    return SafeFetchResult(
        final_url=final_url,
        content_bytes=content_bytes,
        content_type="text/html",
        status_code=200,
    )


def test_source_page_branch_happy_path(monkeypatch):
    """When source_url is set and scraper.image() returns a URL, it wins."""
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    fake_scraper = MagicMock()
    fake_scraper.image.return_value = "https://cdn.example/img.jpg"

    # First call = source-page text/html fetch; second call = image/* validation.
    with patch(
        "robotina.url.safe_fetch.safe_fetch",
        side_effect=[_fake_safe_fetch_result(), _fake_safe_fetch_result()],
    ), patch("recipe_scrapers.scrape_html", return_value=fake_scraper):
        from robotina.agent.tasks.recipe_image import acquire_recipe_image
        out = acquire_recipe_image(make_input(source_url="https://example.com/recipe"))

    assert out.image_url == "https://cdn.example/img.jpg"


def test_source_page_miss_falls_through_to_tavily(monkeypatch):
    """scraper.image() returns None → Tavily branch fires."""
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    fake_scraper = MagicMock()
    fake_scraper.image.return_value = None

    # Two safe_fetch calls happen: source-page fetch + image/* validation.
    with patch(
        "robotina.url.safe_fetch.safe_fetch",
        side_effect=[_fake_safe_fetch_result(), _fake_safe_fetch_result()],
    ), patch("recipe_scrapers.scrape_html", return_value=fake_scraper), patch(
        "robotina.agent.tools.tavily_image_search.tavily_image_search",
        return_value=["https://tavily.example/x.jpg"],
    ):
        from robotina.agent.tasks.recipe_image import acquire_recipe_image
        out = acquire_recipe_image(make_input(source_url="https://example.com/recipe"))

    assert out.image_url == "https://tavily.example/x.jpg"


def test_tavily_only_when_no_source_url(monkeypatch):
    """source_url=None → source-page branch is skipped; only Tavily runs."""
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    tavily_mock = MagicMock(return_value=["https://tavily.example/y.jpg"])
    with patch(
        "robotina.agent.tools.tavily_image_search.tavily_image_search",
        new=tavily_mock,
    ), patch(
        "robotina.url.safe_fetch.safe_fetch",
        return_value=_fake_safe_fetch_result(),  # only the validation call
    ):
        from robotina.agent.tasks.recipe_image import acquire_recipe_image
        out = acquire_recipe_image(make_input(source_url=None, name="milanesa"))

    assert out.image_url == "https://tavily.example/y.jpg"
    # Tavily was called with the Spanish-language query convention.
    tavily_mock.assert_called_once()
    call_args = tavily_mock.call_args
    assert call_args.args[0] == "milanesa receta"


def test_tavily_empty_raises_recipe_image_acquisition_error(monkeypatch):
    """source_url=None and Tavily returns [] → RecipeImageAcquisitionError."""
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    with patch(
        "robotina.agent.tools.tavily_image_search.tavily_image_search",
        return_value=[],
    ):
        from robotina.agent.tasks.recipe_image import (
            RecipeImageAcquisitionError,
            acquire_recipe_image,
        )
        with pytest.raises(RecipeImageAcquisitionError, match="No image candidate"):
            acquire_recipe_image(make_input(source_url=None))


def test_validation_safe_fetch_error_propagates(monkeypatch):
    """Validation safe_fetch raises SafeFetchError → propagates (not caught).

    Critical contract: the function does NOT convert validation
    SafeFetchError into RecipeImageAcquisitionError; the runner's
    non_fatal_on_failure flag absorbs it generically (D-11).
    """
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    with patch(
        "robotina.agent.tools.tavily_image_search.tavily_image_search",
        return_value=["https://tavily.example/bad.jpg"],
    ), patch(
        "robotina.url.safe_fetch.safe_fetch",
        side_effect=SafeFetchError("Content-Type 'text/html' not in ('image/',)"),
    ):
        from robotina.agent.tasks.recipe_image import acquire_recipe_image
        with pytest.raises(SafeFetchError, match="Content-Type"):
            acquire_recipe_image(make_input(source_url=None))


def test_source_url_safe_fetch_error_falls_through_to_tavily(monkeypatch):
    """First safe_fetch (source page) raises SafeFetchError → fall through to Tavily.

    Documented D-15 edge case: a recipe whose source_url is RFC1918 / blocked
    must not break the workflow — Tavily fallback runs instead.
    """
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    # First call (source-page fetch) raises; second call (image/* validation) passes.
    with patch(
        "robotina.url.safe_fetch.safe_fetch",
        side_effect=[
            SafeFetchError("IP 10.0.0.1 is private (RFC1918)"),
            _fake_safe_fetch_result(),
        ],
    ), patch(
        "robotina.agent.tools.tavily_image_search.tavily_image_search",
        return_value=["https://tavily.example/fallback.jpg"],
    ):
        from robotina.agent.tasks.recipe_image import acquire_recipe_image
        out = acquire_recipe_image(make_input(source_url="https://internal.private/recipe"))

    assert out.image_url == "https://tavily.example/fallback.jpg"
