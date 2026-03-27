"""Tests for QueueTool.

Covers ROBOT-03: Robotina agent has queue tool (enqueue a single follow-up
send-notification task directly). Tests mock RQ Queue — never touch real Redis.
"""
import pytest
from unittest.mock import MagicMock, patch


def test_queue_tool_construction():
    """ROBOT-03: QueueTool can be constructed with chat_id, user_id, platform."""
    pytest.skip("ROBOT-03: not yet implemented")


def test_queue_tool_enqueues_send_notification_with_correct_meta():
    """ROBOT-03: _run(text) enqueues 'robotina.queue.jobs.run_task' with meta={'task_type': 'send-notification'},
    result_ttl=-1, failure_ttl=-1."""
    pytest.skip("ROBOT-03: not yet implemented")


def test_queue_tool_enqueues_at_back_of_queue():
    """ROBOT-03: _run() does NOT pass at_front=True — follow-up tasks go to back of queue."""
    pytest.skip("ROBOT-03: not yet implemented")


def test_queue_tool_returns_job_id_string():
    """ROBOT-03: _run(text) returns the job.id string (used for IncomingMessageOutput.queued_task_ids)."""
    pytest.skip("ROBOT-03: not yet implemented")
