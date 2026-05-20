"""Per Phase 21 D-12 / TOOLS-04: AGENT_REGISTRY ↔ overrides/*.json bidirectional CI guard.

Memory: feedback_overrides_in_sync.md — every agent add/remove/rename must
update every overrides/*.json in the same commit. This test enforces that
going forward.
"""
from pathlib import Path
import json
import pytest

OVERRIDES_DIR = Path(__file__).parent.parent.parent / "overrides"
OVERRIDES_FILES = sorted(OVERRIDES_DIR.glob("*.json"))


@pytest.mark.parametrize("overrides_file", OVERRIDES_FILES, ids=lambda p: p.name)
def test_overrides_match_registry(overrides_file):
    """Each overrides/*.json must have the same top-level keys as AGENT_REGISTRY."""
    from robotina.agent.agents import AGENT_REGISTRY

    with overrides_file.open() as f:
        overrides = json.load(f)

    override_keys = set(overrides.keys())
    registry_keys = set(AGENT_REGISTRY.keys())

    only_in_overrides = override_keys - registry_keys
    only_in_registry = registry_keys - override_keys

    assert override_keys == registry_keys, (
        f"{overrides_file.name} is out of sync with AGENT_REGISTRY.\n"
        f"  In {overrides_file.name} but not in AGENT_REGISTRY: {sorted(only_in_overrides)}\n"
        f"  In AGENT_REGISTRY but not in {overrides_file.name}: {sorted(only_in_registry)}"
    )


def test_overrides_files_discovered():
    """Sanity: we should find at least one overrides file. Catches accidental
    directory rename or empty glob."""
    assert len(OVERRIDES_FILES) >= 1, f"No overrides/*.json files found under {OVERRIDES_DIR}"
