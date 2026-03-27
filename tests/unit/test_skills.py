import pytest

from robotina.agent import ReadSkillTool, SkillSet, build_read_skill_tool


def test_skill_set_loads_index_md(tmp_path):
    """AGENT-08: SkillSet reads index.md at construction and exposes index_content."""
    import robotina.agent as agent_module

    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    index_file = skill_dir / "index.md"
    index_file.write_text("# Test Skill\nThis is the index content.")

    original_skills_base = agent_module.SKILLS_BASE
    agent_module.SKILLS_BASE = tmp_path
    try:
        ss = SkillSet("test-skill")
        assert ss.index_content == "# Test Skill\nThis is the index content."
        assert ss.skill_name == "test-skill"
        assert ss.skill_dir == tmp_path / "test-skill"
    finally:
        agent_module.SKILLS_BASE = original_skills_base


def test_read_skill_tool_valid_path(tmp_path):
    """AGENT-09: read-skill tool returns content for valid skill-name/subfile.md path."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    subfile = skill_dir / "subfile.md"
    subfile.write_text("# Sub-file content\nSome details here.")

    tool = ReadSkillTool(skill_dirs={"my-skill": skill_dir})
    result = tool._run("my-skill/subfile.md")
    assert result == "# Sub-file content\nSome details here."


def test_read_skill_tool_blocks_path_traversal(tmp_path):
    """AGENT-09: read-skill tool raises ValueError for paths containing '..'."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()

    tool = ReadSkillTool(skill_dirs={"my-skill": skill_dir})
    with pytest.raises(ValueError, match="traversal"):
        tool._run("my-skill/../../../etc/passwd")


def test_read_skill_tool_blocks_absolute_path(tmp_path):
    """AGENT-09: read-skill tool raises ValueError for absolute paths."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()

    tool = ReadSkillTool(skill_dirs={"my-skill": skill_dir})
    with pytest.raises(ValueError):
        tool._run("/etc/passwd")


def test_read_skill_tool_unknown_skill_raises(tmp_path):
    """AGENT-09: read-skill tool raises ValueError for unknown skill name."""
    tool = ReadSkillTool(skill_dirs={})
    with pytest.raises(ValueError, match="Unknown skill"):
        tool._run("nonexistent/file.md")


def test_household_manager_shared_md_has_no_authentication_section():
    """ROBOT-05: shared.md no longer contains ## Authentication section."""
    from pathlib import Path
    shared_path = Path("src/robotina/agent/skills/household-manager/shared.md")
    assert shared_path.exists()
    content = shared_path.read_text()
    assert "## Authentication" not in content, (
        "shared.md must not contain Authentication section — auth is handled by HouseholdManagerApiTool"
    )


def test_household_manager_shared_md_has_no_401_or_403_rows():
    """ROBOT-05: shared.md error table has no 401 or 403 rows."""
    from pathlib import Path
    shared_path = Path("src/robotina/agent/skills/household-manager/shared.md")
    content = shared_path.read_text()
    lines = content.splitlines()
    # Check no table row starts with | 401 or | 403
    for line in lines:
        stripped = line.strip()
        assert not stripped.startswith("| 401"), (
            f"Found 401 row in error table (must be removed): {line!r}"
        )
        assert not stripped.startswith("| 403"), (
            f"Found 403 row in error table (must be removed): {line!r}"
        )


def test_build_read_skill_tool(tmp_path):
    """build_read_skill_tool() constructs ReadSkillTool from SkillSet list."""
    import robotina.agent as agent_module

    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "index.md").write_text("index")

    original_skills_base = agent_module.SKILLS_BASE
    agent_module.SKILLS_BASE = tmp_path
    try:
        ss = SkillSet("my-skill")
        tool = build_read_skill_tool([ss])
        assert isinstance(tool, ReadSkillTool)
        assert "my-skill" in tool.skill_dirs
    finally:
        agent_module.SKILLS_BASE = original_skills_base
