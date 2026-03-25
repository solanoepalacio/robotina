import pytest


def test_skill_set_loads_index_md():
    """AGENT-08: SkillSet reads index.md at construction and exposes index_content."""
    pytest.skip("not implemented")


def test_read_skill_tool_valid_path():
    """AGENT-09: read-skill tool returns content for valid skill-name/subfile.md path."""
    pytest.skip("not implemented")


def test_read_skill_tool_blocks_path_traversal():
    """AGENT-09: read-skill tool raises ValueError for paths containing '..'."""
    pytest.skip("not implemented")


def test_read_skill_tool_blocks_absolute_path():
    """AGENT-09: read-skill tool raises ValueError for absolute paths."""
    pytest.skip("not implemented")


def test_read_skill_tool_unknown_skill_raises():
    """AGENT-09: read-skill tool raises ValueError for unknown skill name."""
    pytest.skip("not implemented")
