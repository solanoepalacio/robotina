"""Tests for WebSearchTool (RRECIPE-03)."""
import os
from unittest.mock import MagicMock, patch

import pytest

from robotina.agent.tools.web_search import WebSearchTool


def test_web_search_tool_is_base_tool():
    """RRECIPE-03: WebSearchTool inherits from BaseTool."""
    from langchain_core.tools import BaseTool
    assert issubclass(WebSearchTool, BaseTool)


def test_web_search_tool_name_is_web_search():
    """RRECIPE-03: Tool name is 'web-search'."""
    tool = WebSearchTool()
    assert tool.name == "web-search"


def test_web_search_tool_calls_tavily_client(monkeypatch):
    """RRECIPE-03: _run calls TavilyClient.search() with correct params."""
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    mock_client = MagicMock()
    mock_client.search.return_value = {
        "results": [
            {
                "title": "Pasta Bolognesa",
                "url": "http://example.com/recipe",
                "content": "A classic pasta recipe",
                "raw_content": "<html>...</html>",
                "score": 0.95,
            }
        ]
    }

    with patch("tavily.TavilyClient", return_value=mock_client) as MockClient:
        tool = WebSearchTool()
        result = tool._run("receta pasta bolognesa")

    MockClient.assert_called_once_with(api_key="test-key")
    mock_client.search.assert_called_once_with(
        query="receta pasta bolognesa",
        max_results=3,
        search_depth="advanced",
        include_raw_content=True,
    )
    assert len(result) == 1
    assert result[0]["title"] == "Pasta Bolognesa"
    assert result[0]["url"] == "http://example.com/recipe"
    assert result[0]["score"] == 0.95


def test_web_search_tool_handles_none_raw_content(monkeypatch):
    """Pitfall 2: raw_content may be None for some results."""
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    mock_client = MagicMock()
    mock_client.search.return_value = {
        "results": [
            {
                "title": "Recipe",
                "url": "http://example.com",
                "content": "summary",
                "raw_content": None,
                "score": 0.5,
            }
        ]
    }

    with patch("tavily.TavilyClient", return_value=mock_client):
        tool = WebSearchTool()
        result = tool._run("receta")

    assert result[0]["raw_content"] is None
    assert result[0]["content"] == "summary"


def test_web_search_tool_handles_api_error(monkeypatch):
    """RRECIPE-03: API errors are caught and returned as error dict."""
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    mock_client = MagicMock()
    mock_client.search.side_effect = Exception("API rate limit exceeded")

    with patch("tavily.TavilyClient", return_value=mock_client):
        tool = WebSearchTool()
        result = tool._run("receta")

    assert len(result) == 1
    assert "error" in result[0]
    assert "rate limit" in result[0]["error"]


def test_web_search_tool_missing_api_key_raises():
    """Pitfall 5: Missing TAVILY_API_KEY raises KeyError."""
    tool = WebSearchTool()
    env = os.environ.copy()
    env.pop("TAVILY_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(KeyError, match="TAVILY_API_KEY"):
            tool._run("test")
