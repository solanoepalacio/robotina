"""AGENT_REGISTRY content guards.

Enforces invariants:
- Phase 21 D-06: acknowledge-add-recipe agent removed.
- Phase 22: handle-incoming-message bumped from V005.md to V006.md.
- Phase 21 D-05: QueueTool module deleted.
"""
import importlib
import pytest

from robotina.agent.agents import AGENT_REGISTRY


def test_no_acknowledge_add_recipe():
    """Per D-06: acknowledge-add-recipe agent removed in Phase 21."""
    assert "acknowledge-add-recipe" not in AGENT_REGISTRY


def test_handle_incoming_message_uses_v007():
    """Per Phase 23 D-05/D-06/D-07: handle-incoming-message bumped from V006.md to V007.md (URL handling)."""
    cfg = AGENT_REGISTRY["handle-incoming-message"]
    assert cfg.prompt_path.endswith("V007.md"), (
        f"handle-incoming-message prompt_path is {cfg.prompt_path!r}, expected to end with V007.md"
    )


def test_queuetool_module_deleted():
    """Per D-05: QueueTool module deleted in Phase 21."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("robotina.agent.tools.queue")
