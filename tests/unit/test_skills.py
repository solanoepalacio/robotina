import pytest

from robotina.agent.tools.read_skill import ReadSkillTool, SkillSet, build_read_skill_tool


def test_skill_set_loads_index_md(tmp_path):
    """AGENT-08: SkillSet reads index.md at construction and exposes index_content."""
    import robotina.agent.tools.read_skill as read_skill_module

    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    index_file = skill_dir / "index.md"
    index_file.write_text("# Test Skill\nThis is the index content.")

    original_skills_base = read_skill_module.SKILLS_BASE
    read_skill_module.SKILLS_BASE = tmp_path
    try:
        ss = SkillSet("test-skill")
        assert ss.index_content == "# Test Skill\nThis is the index content."
        assert ss.skill_name == "test-skill"
        assert ss.skill_dir == tmp_path / "test-skill"
    finally:
        read_skill_module.SKILLS_BASE = original_skills_base


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
    """AGENT-09: read-skill tool returns error for paths containing '..'."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()

    tool = ReadSkillTool(skill_dirs={"my-skill": skill_dir})
    result = tool._run("my-skill/../../../etc/passwd")
    assert result.startswith("ERROR:")
    assert "traversal" in result.lower()


def test_read_skill_tool_blocks_absolute_path(tmp_path):
    """AGENT-09: read-skill tool returns error for absolute paths."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()

    tool = ReadSkillTool(skill_dirs={"my-skill": skill_dir})
    result = tool._run("/etc/passwd")
    assert result.startswith("ERROR:")


def test_read_skill_tool_unknown_skill_raises(tmp_path):
    """AGENT-09: read-skill tool returns error for unknown skill name."""
    tool = ReadSkillTool(skill_dirs={})
    result = tool._run("nonexistent/file.md")
    assert result.startswith("ERROR:")
    assert "Unknown skill" in result


def test_read_skill_tool_missing_skill_prefix(tmp_path):
    """read-skill tool returns helpful error when skill-name prefix is omitted."""
    tool = ReadSkillTool(skill_dirs={"household-manager": tmp_path})
    result = tool._run("meal_plan.md")
    assert result.startswith("ERROR:")
    assert "skill-name/subfile.md" in result
    assert "household-manager" in result


def test_read_skill_tool_file_not_found(tmp_path):
    """read-skill tool returns error when sub-file does not exist."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()

    tool = ReadSkillTool(skill_dirs={"my-skill": skill_dir})
    result = tool._run("my-skill/nonexistent.md")
    assert result.startswith("ERROR:")
    assert "not found" in result.lower()


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
    import robotina.agent.tools.read_skill as read_skill_module

    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "index.md").write_text("index")

    original_skills_base = read_skill_module.SKILLS_BASE
    read_skill_module.SKILLS_BASE = tmp_path
    try:
        ss = SkillSet("my-skill")
        tool = build_read_skill_tool([ss])
        assert isinstance(tool, ReadSkillTool)
        assert "my-skill" in tool.skill_dirs
    finally:
        read_skill_module.SKILLS_BASE = original_skills_base
