"""Phase 16 — Pydantic field-level rejection of empty household_id (REQ-HID-2).

These tests are RED until plan 16-02 applies Field(min_length=1) (or the
NonEmptyHouseholdId Annotated alias) to all 7 task-input models in
src/robotina/queue/task_types.py.
"""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from robotina.queue.task_types import (
    IncomingMessageInput,
    Message,
    RecipeData,
    RecipeLoadInput,
    RecipeResearchGatherInput,
    RecipeResearchIngredientsInput,
    RecipeResearchInput,
    RecipeResearchInstructionsInput,
    RecipeResearchMetadataInput,
    ReplyContext,
)


def _reply_ctx() -> ReplyContext:
    return ReplyContext(platform="telegram", chat_id="c1", user_id="u1")


def _recipe() -> RecipeData:
    return RecipeData(name="test recipe")


def _build(model_cls, household_id: str):
    """Construct each model with the minimum required fields plus the given household_id."""
    if model_cls is IncomingMessageInput:
        return model_cls(
            message_id="m1",
            platform="telegram",
            received_at=datetime.now(timezone.utc),
            chat_id="c1",
            user_id="u1",
            household_id=household_id,
            text="hello",
            history=[],
        )
    if model_cls is RecipeResearchInput:
        return model_cls(query="carbonara", household_id=household_id)
    if model_cls is RecipeResearchGatherInput:
        return model_cls(query="carbonara", reply_context=_reply_ctx(), household_id=household_id)
    if model_cls in (
        RecipeResearchInstructionsInput,
        RecipeResearchIngredientsInput,
        RecipeResearchMetadataInput,
        RecipeLoadInput,
    ):
        return model_cls(recipe=_recipe(), reply_context=_reply_ctx(), household_id=household_id)
    raise AssertionError(f"unhandled model_cls={model_cls!r}")


ALL_MODELS = [
    IncomingMessageInput,
    RecipeResearchInput,
    RecipeResearchGatherInput,
    RecipeResearchInstructionsInput,
    RecipeResearchIngredientsInput,
    RecipeResearchMetadataInput,
    RecipeLoadInput,
]


@pytest.mark.parametrize("model_cls", ALL_MODELS, ids=lambda c: c.__name__)
def test_household_id_rejects_empty(model_cls):
    """Each task-input model must reject household_id='' at construction (REQ-HID-2)."""
    with pytest.raises(ValidationError) as exc_info:
        _build(model_cls, household_id="")
    assert "household_id" in str(exc_info.value)


@pytest.mark.parametrize("model_cls", ALL_MODELS, ids=lambda c: c.__name__)
def test_household_id_rejects_whitespace(model_cls):
    """Whitespace-only household_id must also be rejected (Open Question 4 resolution)."""
    with pytest.raises(ValidationError) as exc_info:
        _build(model_cls, household_id="   ")
    assert "household_id" in str(exc_info.value)


@pytest.mark.parametrize("model_cls", ALL_MODELS, ids=lambda c: c.__name__)
def test_household_id_accepts_valid(model_cls):
    """Non-empty household_id must still construct successfully (regression guard)."""
    inst = _build(model_cls, household_id="hh-1")
    assert inst.household_id == "hh-1"
