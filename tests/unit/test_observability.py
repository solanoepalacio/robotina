import pytest


def test_setup_langwatch_nonfatal_when_missing_credentials():
    """OBS-01/OBS-02: setup_langwatch() logs warning and returns when env vars missing."""
    pytest.skip("not implemented")


def test_setup_langwatch_reads_api_key_from_env():
    """OBS-02: setup_langwatch reads LANGWATCH_API_KEY from env."""
    pytest.skip("not implemented")


def test_setup_langwatch_reads_endpoint_from_env():
    """OBS-02: setup_langwatch reads LANGWATCH_ENDPOINT from env."""
    pytest.skip("not implemented")


def test_configure_logging_per_module():
    """AGENT-09: configure_logging() sets log level per module from ROBOTINA_LOG_LEVEL_* env vars."""
    pytest.skip("not implemented")
