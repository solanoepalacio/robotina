"""Per Phase 21 D-20: AGENT_REGISTRY content guards.

Enforces post-Phase-21 invariants:
- D-06: acknowledge-add-recipe agent removed.
- D-10: handle-incoming-message bumped from V004.md to V005.md.
- D-05: QueueTool module deleted.
"""
import importlib
import pytest

from robotina.agent.agents import AGENT_REGISTRY


def test_no_acknowledge_add_recipe():
    """Per D-06: acknowledge-add-recipe agent removed in Phase 21."""
    assert "acknowledge-add-recipe" not in AGENT_REGISTRY


def test_handle_incoming_message_uses_v006():
    """Per Phase 22: handle-incoming-message bumped from V005.md to V006.md."""
    cfg = AGENT_REGISTRY["handle-incoming-message"]
    assert cfg.prompt_path.endswith("V006.md"), (
        f"handle-incoming-message prompt_path is {cfg.prompt_path!r}, expected to end with V006.md"
    )


def test_queuetool_module_deleted():
    """Per D-05: QueueTool module deleted in Phase 21."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("robotina.agent.tools.queue")
