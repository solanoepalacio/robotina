"""Unit tests for tavily_image_search (Phase 24 / D-16).

Covers:
- Happy path: mocked TavilyClient returns an images list -> function returns
  the list verbatim.
- Empty path: empty images list -> function returns [].
- Misconfiguration: TAVILY_API_KEY unset -> raises KeyError (fail-loud).
- Defensive: include_image_descriptions=True dict-shape entries -> .url extracted.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


def test_tavily_image_search_returns_image_urls_on_happy_path(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    fake_response = {
        "images": [
            "https://example.com/a.jpg",
            "https://example.com/b.png",
            "https://example.com/c.webp",
        ]
    }
    with patch("tavily.TavilyClient") as MockClient:
        MockClient.return_value.search.return_value = fake_response
        from robotina.agent.tools.tavily_image_search import tavily_image_search
        urls = tavily_image_search("milanesa napolitana receta")
    assert urls == [
        "https://example.com/a.jpg",
        "https://example.com/b.png",
        "https://example.com/c.webp",
    ]
    # Confirm Tavily was called with include_images=True
    call_kwargs = MockClient.return_value.search.call_args.kwargs
    assert call_kwargs.get("include_images") is True
    assert call_kwargs.get("query") == "milanesa napolitana receta"


def test_tavily_image_search_returns_empty_list_when_tavily_has_no_results(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    with patch("tavily.TavilyClient") as MockClient:
        MockClient.return_value.search.return_value = {"images": []}
        from robotina.agent.tools.tavily_image_search import tavily_image_search
        urls = tavily_image_search("milanesa criolla saltena receta")
    assert urls == []


def test_tavily_image_search_raises_keyerror_when_api_key_unset(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    from robotina.agent.tools.tavily_image_search import tavily_image_search
    with pytest.raises(KeyError, match="TAVILY_API_KEY"):
        tavily_image_search("anything")


def test_tavily_image_search_handles_dict_entries_defensively(monkeypatch):
    """Defensive: if include_image_descriptions=True is flipped later,
    entries are {url, description} dicts. The function extracts .url."""
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    with patch("tavily.TavilyClient") as MockClient:
        MockClient.return_value.search.return_value = {
            "images": [
                {"url": "https://example.com/a.jpg", "description": "foo"},
                {"url": "https://example.com/b.png", "description": "bar"},
            ]
        }
        from robotina.agent.tools.tavily_image_search import tavily_image_search
        urls = tavily_image_search("test")
    assert urls == ["https://example.com/a.jpg", "https://example.com/b.png"]
