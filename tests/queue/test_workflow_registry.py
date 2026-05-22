"""Phase 23 D-01 / D-21 — WORKFLOW_REGISTRY rename + URL variant tests.

Asserts:
- ``add-recipe-from-query`` (renamed from legacy ``add-recipe``) and
  ``add-recipe-from-url`` (NEW) are both registered.
- Legacy ``add-recipe`` key is gone (hard rename, no transitional alias).
- The URL variant's first step (``gather-from-url``) reads
  ``shared_context["recipe_url"]`` via its build_input lambda.
- The URL variant's instructions step reads
  ``artifacts["gather-from-url"]`` (the one structural diff vs the
  query-variant tail).
"""
from __future__ import annotations


def _ctx_url():
    return {
        "recipe_url": "https://example.com/recipe-y",
        "reply_context": {
            "platform": "telegram",
            "chat_id": "c-url",
            "user_id": "u-url",
        },
        "household_id": "h-url",
    }


def _recipe_dump(name: str = "ReceptaURL", **overrides):
    from robotina.queue.task_types import RecipeData
    return RecipeData(name=name, **overrides).model_dump(mode="json")


def test_workflow_registry_has_add_recipe_from_query():
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    assert "add-recipe-from-query" in WORKFLOW_REGISTRY
    assert (
        WORKFLOW_REGISTRY["add-recipe-from-query"].workflow_type
        == "add-recipe-from-query"
    )


def test_workflow_registry_has_add_recipe_from_url():
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    assert "add-recipe-from-url" in WORKFLOW_REGISTRY
    assert (
        WORKFLOW_REGISTRY["add-recipe-from-url"].workflow_type
        == "add-recipe-from-url"
    )


def test_workflow_registry_lacks_legacy_add_recipe():
    """D-01: hard rename, no transitional alias for the legacy name."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    assert "add-recipe" not in WORKFLOW_REGISTRY


def test_url_variant_has_seven_steps():
    """Phase 24 D-06: URL variant now has 7 steps after recipe-image
    insertion between metadata and load."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    steps = WORKFLOW_REGISTRY["add-recipe-from-url"].steps
    expected = [
        ("gather-from-url", "gather-from-url"),
        ("instructions", "recipe-research-instructions"),
        ("ingredients", "recipe-research-ingredients"),
        ("metadata", "recipe-research-metadata"),
        ("recipe-image", "recipe-image"),
        ("load", "recipe-load"),
        ("finalize-outcome", "finalize-outcome"),
    ]
    assert len(steps) == len(expected)
    for step, (key, task_type) in zip(steps, expected):
        assert step.step_key == key
        assert step.task_type == task_type


def test_url_variant_first_step_reads_recipe_url_from_shared_context():
    """D-08: gather-from-url's build_input reads ctx['recipe_url']."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import GatherFromUrlInput, ReplyContext

    result = WORKFLOW_REGISTRY["add-recipe-from-url"].steps[0].build_input(
        _ctx_url(), {}
    )
    assert isinstance(result, GatherFromUrlInput)
    assert result.url == "https://example.com/recipe-y"
    assert result.household_id == "h-url"
    assert result.reply_context == ReplyContext(
        platform="telegram", chat_id="c-url", user_id="u-url"
    )


def test_url_variant_instructions_reads_gather_from_url_artifact():
    """The URL variant's instructions step reads artifacts['gather-from-url']
    rather than artifacts['gather'] — the one structural diff vs the
    query-variant tail."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeResearchInstructionsInput

    artifacts = {
        "gather-from-url": _recipe_dump(
            name="ReceptaURL",
            gathered_sources=[{"url": "https://example.com/recipe-y"}],
        )
    }
    result = WORKFLOW_REGISTRY["add-recipe-from-url"].steps[1].build_input(
        _ctx_url(), artifacts
    )
    assert isinstance(result, RecipeResearchInstructionsInput)
    assert result.recipe.name == "ReceptaURL"
    assert result.recipe.gathered_sources == [
        {"url": "https://example.com/recipe-y"}
    ]


def test_url_variant_load_reads_recipe_image_artifact():
    """Phase 24 D-06b: the URL variant's load step reads
    artifacts['recipe-image'] on the happy path (same as the query variant —
    tail steps share key names). Load is at index 5 after recipe-image
    insertion (Phase 24 / D-06)."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeLoadInput

    artifacts = {
        "metadata": _recipe_dump(name="ReceptaURL", servings_qty=4),
        "recipe-image": _recipe_dump(
            name="ReceptaURL",
            servings_qty=4,
            image_url="https://example.com/ricky.jpg",
        ),
    }
    result = WORKFLOW_REGISTRY["add-recipe-from-url"].steps[5].build_input(
        _ctx_url(), artifacts
    )
    assert isinstance(result, RecipeLoadInput)
    assert result.recipe.name == "ReceptaURL"
    assert result.recipe.servings_qty == 4
    assert result.recipe.image_url == "https://example.com/ricky.jpg"


# ---------------------------------------------------------------------------
# Phase 24 / D-19 — recipe-image insertion + load.build_input fallback tests
# ---------------------------------------------------------------------------

import pytest


_VARIANTS = ["add-recipe-from-query", "add-recipe-from-url"]


def _ctx_query():
    return {
        "recipe_query": "canelones de espinaca",
        "reply_context": {
            "platform": "telegram",
            "chat_id": "c-q",
            "user_id": "u-q",
        },
        "household_id": "h-q",
    }


def _ctx_for(variant: str):
    return _ctx_url() if variant == "add-recipe-from-url" else _ctx_query()


@pytest.mark.parametrize("variant", _VARIANTS)
def test_recipe_image_step_present_in_both_variants(variant):
    """D-19: recipe-image is present in both variants, between metadata and load."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    keys = [s.step_key for s in WORKFLOW_REGISTRY[variant].steps]
    assert "recipe-image" in keys, f"recipe-image missing in {variant}"
    metadata_idx = keys.index("metadata")
    image_idx = keys.index("recipe-image")
    load_idx = keys.index("load")
    assert image_idx == metadata_idx + 1
    assert load_idx == image_idx + 1


@pytest.mark.parametrize("variant", _VARIANTS)
def test_recipe_image_step_has_non_fatal_on_failure_true(variant):
    """D-19: recipe-image step opts in to non_fatal_on_failure=True (D-01b)."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    step = next(
        s for s in WORKFLOW_REGISTRY[variant].steps if s.step_key == "recipe-image"
    )
    assert step.non_fatal_on_failure is True


@pytest.mark.parametrize("variant", _VARIANTS)
def test_only_recipe_image_opts_in_to_non_fatal(variant):
    """D-19 (D-01b): no OTHER step in either variant has non_fatal_on_failure=True.
    Only recipe-image opts in; every other step keeps the v1.0 strict default."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    for step in WORKFLOW_REGISTRY[variant].steps:
        if step.step_key == "recipe-image":
            continue
        assert step.non_fatal_on_failure is False, (
            f"{variant}::{step.step_key} unexpectedly opts into non_fatal_on_failure"
        )


@pytest.mark.parametrize("variant", _VARIANTS)
def test_load_build_input_falls_back_to_metadata_on_unavailable_artifact(variant):
    """D-19 (D-06b / Pitfall 6): when recipe-image artifact is the
    StepUnavailableArtifact sentinel shape, load.build_input must fall back
    to artifacts['metadata'] so the recipe payload is preserved."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeLoadInput

    steps = WORKFLOW_REGISTRY[variant].steps
    load_step = next(s for s in steps if s.step_key == "load")

    artifacts = {
        "metadata": _recipe_dump(name="ReceptaFallback"),
        "recipe-image": {
            "status": "unavailable",
            "step_key": "recipe-image",
            "reason": "test forced miss",
        },
    }
    result = load_step.build_input(_ctx_for(variant), artifacts)
    assert isinstance(result, RecipeLoadInput)
    assert result.recipe.name == "ReceptaFallback"
    # Fallback path does NOT pull image_url from the sentinel artifact.
    assert result.recipe.image_url is None


@pytest.mark.parametrize("variant", _VARIANTS)
def test_load_build_input_uses_recipe_image_artifact_on_happy_path(variant):
    """D-19 (D-06b): on the happy path the load step reads
    artifacts['recipe-image'] (a full RecipeData dump with image_url set)."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeLoadInput

    steps = WORKFLOW_REGISTRY[variant].steps
    load_step = next(s for s in steps if s.step_key == "load")

    artifacts = {
        "metadata": _recipe_dump(name="ReceptaNoImage"),
        "recipe-image": _recipe_dump(
            name="ReceptaHappy", image_url="https://x/y.jpg"
        ),
    }
    result = load_step.build_input(_ctx_for(variant), artifacts)
    assert isinstance(result, RecipeLoadInput)
    # Happy path uses the recipe-image artifact, NOT metadata.
    assert result.recipe.name == "ReceptaHappy"
    assert result.recipe.image_url == "https://x/y.jpg"


@pytest.mark.parametrize("variant", _VARIANTS)
def test_each_variant_has_exactly_seven_steps(variant):
    """D-19: both variants have exactly 7 steps after Phase 24 wiring."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    assert len(WORKFLOW_REGISTRY[variant].steps) == 7
