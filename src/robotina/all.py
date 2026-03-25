"""Entry point for `uv run all`.

Launches both the RQ task runner (uv run agent) and the Telegram gateway
(uv run gateway) as concurrent child processes.

Handles KeyboardInterrupt (Ctrl+C) by terminating both processes cleanly.

Note: If either subprocess exits unexpectedly, the other continues running.
For Phase 1 dev mode, manual restart is acceptable.
"""
import subprocess
import sys


def main() -> None:
    """Start agent worker + gateway bot as concurrent subprocesses."""
    procs = [
        subprocess.Popen(["uv", "run", "agent"]),
        subprocess.Popen(["uv", "run", "gateway"]),
    ]
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait()
        sys.exit(0)
