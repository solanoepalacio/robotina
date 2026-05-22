"""Tavily image search — plain function used by acquire_recipe_image (Phase 24 / D-12).

No LangChain tool wrapping in v1.1 — only the deterministic recipe-image task
calls this; no LLM agent uses it. Mirrors WebSearchTool's TAVILY_API_KEY env
var bracket-read and TavilyClient lazy-import pattern.

Query construction is the caller's responsibility. Phase 24 callers use
f"{recipe.name} receta" (Spanish-language hint per Claude's discretion).
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def tavily_image_search(query: str, *, max_results: int = 5) -> list[str]:
    """Return a list of image URLs from Tavily image search.

    Args:
        query: Search query string.
        max_results: Tavily ``max_results`` param (default 5). Only the top
            result is used in v1.1 (top-result-only per D-11); the extra slack
            is retained so the caller has data for the eval / future v1.2
            multi-candidate retry without re-querying.

    Returns:
        list[str] of image URLs. Empty list when Tavily indexed no images
        for the query.

    Raises:
        KeyError: If ``TAVILY_API_KEY`` env var is not set (fail-loud
            mirrors ``WebSearchTool``). Caller — ``acquire_recipe_image`` —
            lets this propagate; the runner's ``non_fatal_on_failure`` flag
            absorbs it into a ``StepUnavailableArtifact``.
        Exception: Any TavilyClient transport error propagates upward
            (timeout, 5xx, auth) for the same reason — let the runner's
            non-fatal flag handle it. Do NOT swallow exceptions here.
    """
    from tavily import TavilyClient

    api_key = os.environ["TAVILY_API_KEY"]
    client = TavilyClient(api_key=api_key)
    response = client.search(
        query=query,
        max_results=max_results,
        search_depth="basic",
        include_images=True,
        # include_image_descriptions=False — default; response["images"] is list[str]
    )
    images_raw = response.get("images", []) or []
    logger.info(
        "tavily-image-search | query=%r results=%d", query, len(images_raw)
    )

    # Defensive: with include_image_descriptions=False (default), entries are
    # plain URL strings. If a future caller flips the flag, entries become
    # {url, description} dicts — extract .url then.
    out: list[str] = []
    for entry in images_raw:
        if isinstance(entry, str):
            out.append(entry)
        elif isinstance(entry, dict) and isinstance(entry.get("url"), str):
            out.append(entry["url"])
    return out
