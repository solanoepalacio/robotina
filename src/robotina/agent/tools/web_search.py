"""web-search tool for the recipe-research-gather agent.

WebSearchTool wraps TavilyClient.search() from tavily-python. It is instantiated
per-job inside run_task() — never at module level (locked Phase 4 constraint).

The TAVILY_API_KEY env var must be set. This is the Tavily SDK standard name.
"""
from __future__ import annotations

import logging
import os

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """LangChain tool that searches the web via Tavily API.

    Used by the recipe-research-gather agent to find recipe pages.
    Returns a list of result dicts with title, url, content, raw_content, and score.

    Args (via _run):
        query: Search query string (in Spanish per D-20).

    Returns:
        List of result dicts. Each dict has keys: title, url, content,
        raw_content (may be None per Pitfall 2), score.
    """

    name: str = "web-search"
    description: str = (
        "Search the web for recipes and cooking information. "
        "Returns a list of results with title, url, content (summary), "
        "and raw_content (full HTML page content, may be null for some sites). "
        "Args: query (str) -- search query in Spanish."
    )

    def _run(self, query: str) -> list[dict]:
        """Search via Tavily API. Reads TAVILY_API_KEY from env."""
        from tavily import TavilyClient

        api_key = os.environ["TAVILY_API_KEY"]
        client = TavilyClient(api_key=api_key)

        try:
            response = client.search(
                query=query,
                max_results=3,
                search_depth="advanced",
                include_raw_content=True,
            )
        except Exception as exc:
            logger.error("web-search failed | query=%r error=%s", query, exc)
            return [{"error": str(exc)}]

        results = response.get("results", [])
        logger.info("web-search | query=%r results=%d", query, len(results))

        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "raw_content": r.get("raw_content"),  # may be None (Pitfall 2)
                "score": r.get("score", 0),
            }
            for r in results
        ]

    async def _arun(self, query: str) -> list[dict]:
        return self._run(query)
