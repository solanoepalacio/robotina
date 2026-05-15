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
    """The comment block above HOUSEHOLD_ID= must call it required (so a fresh-checkout
    operator sees the warning without reading source).

    Window widened from 5 to 12 lines in Phase 16 WR-04: the empty-default
    rationale needs more prose, which pushes "REQUIRED" further from the
    assignment line. The intent — the contiguous comment block immediately
    above the var must say "required" — remains the same.
    """
    text = ENV_EXAMPLE.read_text()
    lines = text.splitlines()
    target_idx = next(
        (i for i, ln in enumerate(lines) if ln.startswith("HOUSEHOLD_ID=")),
        None,
    )
    assert target_idx is not None, "HOUSEHOLD_ID= line not found"
    # Walk upward from HOUSEHOLD_ID= through the contiguous comment block
    # (lines starting with '#'), stopping at the first non-comment line.
    # This naturally bounds the search to the block that documents this var
    # rather than fixed-line window that bleeds into unrelated config above.
    start = target_idx
    while start > 0 and lines[start - 1].lstrip().startswith("#"):
        start -= 1
    preamble = "\n".join(lines[start:target_idx])
    assert re.search(r"required", preamble, re.IGNORECASE), \
        f"comment block above HOUSEHOLD_ID= must contain 'required'; got: {preamble!r}"
