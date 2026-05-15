"""Phase 16 — .env.example documents HOUSEHOLD_ID (REQ-HID-6).

RED until plan 16-06 adds the HOUSEHOLD_ID block to .env.example.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = REPO_ROOT / ".env.example"


def test_env_example_exists():
    assert ENV_EXAMPLE.is_file(), f"missing {ENV_EXAMPLE}"


def test_household_id_documented():
    text = ENV_EXAMPLE.read_text()
    assert re.search(r"^HOUSEHOLD_ID=", text, re.MULTILINE), \
        "HOUSEHOLD_ID= line missing from .env.example"


def test_household_id_marked_required():
    """The line directly above HOUSEHOLD_ID= must call it required (so a fresh-checkout
    operator sees the warning without reading source)."""
    text = ENV_EXAMPLE.read_text()
    # Find the HOUSEHOLD_ID= line index and look up ~5 lines for "required"
    lines = text.splitlines()
    target_idx = next(
        (i for i, ln in enumerate(lines) if ln.startswith("HOUSEHOLD_ID=")),
        None,
    )
    assert target_idx is not None, "HOUSEHOLD_ID= line not found"
    preamble = "\n".join(lines[max(0, target_idx - 5):target_idx])
    assert re.search(r"required", preamble, re.IGNORECASE), \
        f"comment block above HOUSEHOLD_ID= must contain 'required'; got: {preamble!r}"
