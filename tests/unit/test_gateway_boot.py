"""Phase 16 — Gateway entrypoint refuses to start without HOUSEHOLD_ID (REQ-HID-5).

These tests are RED until plan 16-05 adds the fail-fast guard at the top of
src/robotina/gateway/__init__.py::main().

Subprocess isolation is used because main() terminates the Python process via
sys.exit(1); running it in-process would kill the pytest runner.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest


def _run_gateway_main(env: dict) -> subprocess.CompletedProcess:
    """Run `python -c 'from robotina.gateway import main; main()'` with isolated env."""
    return subprocess.run(
        [sys.executable, "-c", "from robotina.gateway import main; main()"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )


def _base_env() -> dict:
    """Inherit PATH and PYTHONPATH so the subprocess can import the project, but
    strip HOUSEHOLD_ID so the guard fires."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "TELEGRAM_BOT_TOKEN": "fake-token-for-boot-test",
    }
    for var in ("PYTHONPATH", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PWD"):
        if var in os.environ:
            env[var] = os.environ[var]
    return env


def test_main_exits_on_missing_household_id():
    env = _base_env()  # HOUSEHOLD_ID absent
    result = _run_gateway_main(env)
    assert result.returncode != 0, f"expected non-zero exit, got {result.returncode}\nstderr={result.stderr}"
    assert "HOUSEHOLD_ID" in result.stderr, f"stderr must name the env var; got: {result.stderr!r}"


def test_main_exits_on_empty_household_id():
    env = _base_env()
    env["HOUSEHOLD_ID"] = ""
    result = _run_gateway_main(env)
    assert result.returncode != 0
    assert "HOUSEHOLD_ID" in result.stderr


def test_main_exits_on_whitespace_household_id():
    env = _base_env()
    env["HOUSEHOLD_ID"] = "   "
    result = _run_gateway_main(env)
    assert result.returncode != 0
    assert "HOUSEHOLD_ID" in result.stderr


def test_main_boots_with_valid_household_id(monkeypatch):
    """When HOUSEHOLD_ID is non-empty, the guard passes and main() proceeds to
    ApplicationBuilder construction. We monkeypatch ApplicationBuilder so we don't
    actually start polling; the test asserts no SystemExit is raised before that point.

    This test runs in-process (not subprocess) so monkeypatch can intercept the
    Telegram setup.
    """
    monkeypatch.setenv("HOUSEHOLD_ID", "hh-smoke")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake")

    import robotina.gateway as gateway_pkg

    fake_app = type("FakeApp", (), {"add_handler": lambda self, *a, **k: None, "run_polling": lambda self: None})()
    fake_builder = type(
        "FakeBuilder",
        (),
        {"token": lambda self, t: self, "build": lambda self: fake_app},
    )()
    monkeypatch.setattr(gateway_pkg, "ApplicationBuilder", lambda: fake_builder)

    # Must not raise SystemExit
    gateway_pkg.main()
