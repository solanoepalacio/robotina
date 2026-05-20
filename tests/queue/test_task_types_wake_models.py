"""Unit tests for the WAKE-04 Pydantic models.

Covers construction, round-trip (model_dump / model_validate), extra-field
rejection, and the Spanish to_user_message() rendering for WakeInvocationInput.
"""
import pytest
from pydantic import ValidationError

from robotina.queue.task_types import (
    AddRecipeOutcome,
    FinalizeOutcomeInput,
    WakeInvocationInput,
    WorkflowOutcomeSummary,
)


def test_workflow_outcome_summary_round_trip():
    s = WorkflowOutcomeSummary(
        workflow_run_id="r1",
        workflow_type="add-recipe",
        status="done",
        outcome=AddRecipeOutcome(
            status="success",
            recipe_id="r1",
            recipe_name="Lentejas",
            recipe_slug="lentejas",
        ),
    )
    dumped = s.model_dump(mode="json")
    restored = WorkflowOutcomeSummary.model_validate(dumped)
    assert restored.outcome is not None
    assert restored.outcome.recipe_name == "Lentejas"


def test_workflow_outcome_summary_failed_with_no_outcome():
    s = WorkflowOutcomeSummary(
        workflow_run_id="r2",
        workflow_type="add-recipe",
        status="failed",
        outcome=None,
    )
    restored = WorkflowOutcomeSummary.model_validate(s.model_dump(mode="json"))
    assert restored.outcome is None
    assert restored.status == "failed"


def test_workflow_outcome_summary_rejects_extra():
    with pytest.raises(ValidationError):
        WorkflowOutcomeSummary(
            workflow_run_id="r3",
            workflow_type="add-recipe",
            status="done",
            foo=1,
        )


def _make_wake_with(status, outcome):
    return WakeInvocationInput(
        previous_invocation_id="inv-1",
        conversation_id="conv-1",
        outcomes=[
            WorkflowOutcomeSummary(
                workflow_run_id="run-1",
                workflow_type="add-recipe",
                status=status,
                outcome=outcome,
            )
        ],
    )


def test_wake_invocation_input_to_user_message_success():
    w = _make_wake_with(
        "done",
        AddRecipeOutcome(status="success", recipe_name="Lentejas"),
    )
    msg = w.to_user_message()
    assert "✓" in msg
    assert "Lentejas" in msg
    assert "Wake-trigger" in msg


def test_wake_invocation_input_to_user_message_failure():
    w = _make_wake_with(
        "failed",
        AddRecipeOutcome(status="failure", failure_reason="no gather artifact"),
    )
    msg = w.to_user_message()
    assert "✗" in msg
    assert "no gather artifact" in msg


def test_wake_invocation_input_to_user_message_empty_list():
    w = WakeInvocationInput(
        previous_invocation_id="inv-x",
        conversation_id="conv-x",
        outcomes=[],
    )
    msg = w.to_user_message()
    assert "Los siguientes flujos terminaron" in msg
    assert "Wake-trigger" in msg


def test_finalize_outcome_input_optional_fields():
    empty = FinalizeOutcomeInput()
    assert empty.metadata is None
    assert empty.load is None
    assert empty.failure_reason is None
    with_meta = FinalizeOutcomeInput(metadata={"a": 1})
    assert with_meta.metadata == {"a": 1}


def test_finalize_outcome_input_rejects_extra():
    with pytest.raises(ValidationError):
        FinalizeOutcomeInput(metadata={"a": 1}, bogus="x")
