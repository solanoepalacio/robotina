"""Deterministic recipe-image acquisition (Phase 24 / D-02 / D-11).

Mirrors the finalize-outcome agent-less pattern at jobs.py:119. Owns the
fallback ladder:
  1. Source-page (when RecipeData.source_url is set):
     safe_fetch(source_url, expected_content_type="text/html") +
     recipe_scrapers.scrape_html(html, wild_mode=True).image()
  2. Tavily image search (otherwise or on source-page miss):
     tavily_image_search(f"{recipe.name} receta")[:1]
  3. Miss: raise RecipeImageAcquisitionError (runner's
     non_fatal_on_failure=True flag converts to StepUnavailableArtifact)

Validation: the candidate URL is run through safe_fetch with
expected_content_type="image/*" and max_bytes=15_000_000. Validation
failures (SafeFetchError) propagate to the runner's non-fatal flag.

Top-result-only. No multi-candidate retry. No PIL magic-byte check.
"""
from __future__ import annotations

import logging

from robotina.queue.task_types import RecipeImageInput, RecipeImageOutput

logger = logging.getLogger(__name__)


class RecipeImageAcquisitionError(Exception):
    """No image URL passed safe_fetch validation.

    Caught by run_task's outer except block (added in 24-01) and routed
    through workflow_runner._finalize_step_unavailable when the
    recipe-image step has non_fatal_on_failure=True.
    """


def acquire_recipe_image(input: RecipeImageInput) -> RecipeImageOutput:
    """Run the fallback ladder; return RecipeData with image_url set or raise.

    Args:
        input: RecipeImageInput carrying the accumulated RecipeData,
            reply_context, and household_id (the latter two are unused
            here but flow through for parity with other steps).

    Returns:
        RecipeImageOutput (alias for RecipeData) with image_url set to a
        URL that has passed safe_fetch validation with image/* Content-Type.

    Raises:
        RecipeImageAcquisitionError: no candidate URL produced by either
            branch passed validation. The runner converts this into a
            StepUnavailableArtifact via WorkflowStepDef.non_fatal_on_failure=True.
        SafeFetchError: NOT caught at the validation step — let it
            propagate. The runner's non-fatal flag absorbs it the same way.
    """
    from robotina.url.safe_fetch import safe_fetch, SafeFetchError

    recipe = input.recipe
    candidate_url: str | None = None

    # ------- Branch 1: source-page (when URL-sourced) -------
    if recipe.source_url:
        try:
            fetched = safe_fetch(recipe.source_url, expected_content_type="text/html")
            html = fetched.content_bytes.decode("utf-8", errors="replace")
            from recipe_scrapers import scrape_html
            try:
                scraper = scrape_html(html, org_url=fetched.final_url, wild_mode=True)
            except Exception:
                scraper = None
            if scraper is not None:
                try:
                    raw = scraper.image()
                    candidate_url = raw.strip() if isinstance(raw, str) and raw else None
                except Exception:
                    # NotImplementedError / SchemaOrgException / etc. — all "miss"
                    candidate_url = None
            if candidate_url:
                logger.info(
                    "recipe-image source-page hit | recipe=%r url=%s",
                    recipe.name, candidate_url,
                )
        except SafeFetchError as exc:
            # Source-page fetch hit an SSRF/abuse defense — documented
            # behavior (D-15 edge case). Fall through to Tavily.
            logger.info(
                "recipe-image source-page fetch blocked, falling back to Tavily | "
                "reason=%s", exc,
            )
            candidate_url = None

    # ------- Branch 2: Tavily image search -------
    if not candidate_url:
        from robotina.agent.tools.tavily_image_search import tavily_image_search
        query = f"{recipe.name} receta"
        images = tavily_image_search(query, max_results=5)
        if images:
            candidate_url = images[0]
            logger.info(
                "recipe-image tavily hit | recipe=%r query=%r url=%s",
                recipe.name, query, candidate_url,
            )

    # ------- Miss -------
    if not candidate_url:
        raise RecipeImageAcquisitionError(
            f"No image candidate for recipe={recipe.name!r}"
        )

    # ------- Validation (top-result-only; SafeFetchError propagates) -------
    safe_fetch(
        candidate_url,
        expected_content_type="image/*",
        max_bytes=15_000_000,
    )

    # ------- Build output: RecipeData with image_url set -------
    output_recipe = recipe.model_copy(update={"image_url": candidate_url})
    # RecipeImageOutput is a sentinel alias for RecipeData (24-02).
    return RecipeImageOutput(**output_recipe.model_dump(mode="json"))
