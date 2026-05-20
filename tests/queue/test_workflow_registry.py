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


def test_url_variant_has_six_steps():
    """Phase 23: URL variant inline-duplicates the 5-step tail; total = 6."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    steps = WORKFLOW_REGISTRY["add-recipe-from-url"].steps
    expected = [
        ("gather-from-url", "gather-from-url"),
        ("instructions", "recipe-research-instructions"),
        ("ingredients", "recipe-research-ingredients"),
        ("metadata", "recipe-research-metadata"),
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


def test_url_variant_load_reads_metadata_artifact():
    """Sanity: the URL variant's load step reads artifacts['metadata']
    (same as the query variant — tail steps share key names)."""
    from robotina.agent.workflows import WORKFLOW_REGISTRY
    from robotina.queue.task_types import RecipeLoadInput

    artifacts = {
        "metadata": _recipe_dump(name="ReceptaURL", servings_qty=4),
    }
    result = WORKFLOW_REGISTRY["add-recipe-from-url"].steps[4].build_input(
        _ctx_url(), artifacts
    )
    assert isinstance(result, RecipeLoadInput)
    assert result.recipe.name == "ReceptaURL"
    assert result.recipe.servings_qty == 4
