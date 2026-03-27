"""Tests for LangWatch initialization and per-module logging configuration.

Tests verify:
- OBS-01: __setup_langwatch_in_workhorse() is non-fatal when credentials are missing
- OBS-02: __setup_langwatch_in_workhorse() reads LANGWATCH_API_KEY and LANGWATCH_ENDPOINT from env
- AGENT-09: configure_logging() sets log levels per module from env vars
"""
import logging
from unittest.mock import MagicMock, patch

import pytest


def test__setup_langwatch_nonfatal_when_missing_credentials(monkeypatch, caplog):
    """OBS-01/OBS-02: _setup_langwatch() logs warning and returns when env vars missing."""
    monkeypatch.delenv("LANGWATCH_API_KEY", raising=False)
    monkeypatch.delenv("LANGWATCH_ENDPOINT", raising=False)

    from robotina.queue.runner import _setup_langwatch

    with caplog.at_level(logging.WARNING, logger="robotina.queue.runner"):
        # Should NOT raise
        _setup_langwatch()

    messages = [r.message for r in caplog.records]
    assert any("LangWatch credentials not set" in m for m in messages), \
        f"Expected warning about missing credentials. Got: {messages}"


def test__setup_langwatch_reads_api_key_from_env(monkeypatch):
    """OBS-02: _setup_langwatch reads LANGWATCH_API_KEY from env."""
    monkeypatch.setenv("LANGWATCH_API_KEY", "test-key")
    monkeypatch.setenv("LANGWATCH_ENDPOINT", "http://test")

    mock_setup = MagicMock()
    with patch("langwatch.setup", mock_setup):
        from robotina.queue.runner import _setup_langwatch
        _setup_langwatch()

    mock_setup.assert_called_once()
    call_kwargs = mock_setup.call_args.kwargs
    assert call_kwargs.get("api_key") == "test-key", \
        f"Expected api_key='test-key', got: {call_kwargs}"


def test__setup_langwatch_reads_endpoint_from_env(monkeypatch):
    """OBS-02: _setup_langwatch reads LANGWATCH_ENDPOINT from env."""
    monkeypatch.setenv("LANGWATCH_API_KEY", "test-key")
    monkeypatch.setenv("LANGWATCH_ENDPOINT", "http://test")

    mock_setup = MagicMock()
    with patch("langwatch.setup", mock_setup):
        from robotina.queue.runner import _setup_langwatch
        _setup_langwatch()

    mock_setup.assert_called_once()
    call_kwargs = mock_setup.call_args.kwargs
    assert call_kwargs.get("endpoint_url") == "http://test", \
        f"Expected endpoint_url='http://test', got: {call_kwargs}"


def test_configure_logging_per_module(monkeypatch):
    """AGENT-09: configure_logging() sets log level per module from ROBOTINA_LOG_LEVEL_* env vars."""
    monkeypatch.setenv("ROBOTINA_LOG_LEVEL_AGENT", "DEBUG")

    # Reset the logger level before test
    agent_logger = logging.getLogger("robotina.agent")
    original_level = agent_logger.level
    agent_logger.setLevel(logging.NOTSET)

    from robotina.agent.agents import configure_logging
    configure_logging()

    assert logging.getLogger("robotina.agent").level == logging.DEBUG, \
        f"Expected DEBUG level, got: {logging.getLevelName(logging.getLogger('robotina.agent').level)}"

    # Cleanup
    agent_logger.setLevel(original_level)
