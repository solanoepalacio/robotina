"""Skill loading infrastructure for Robotina agents.

Provides:
- SkillSet: loads a skill directory's index.md at construction
- ReadSkillTool: LangChain BaseTool that loads skill sub-files on demand
- build_read_skill_tool(): factory constructing ReadSkillTool from SkillSet list

Skills live in src/robotina/agent/skills/<skill-name>/index.md (plus sub-files).
The canonical skills directory is src/robotina/agent/skills/ — never the project root.

Security: ReadSkillTool blocks path traversal (any '..' or absolute paths in the
sub-file argument). Uses pathlib.resolve() on both base and target to defeat
symlinks and '..' segments before comparison.
"""
from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool
from pydantic import Field

# Canonical skills directory — anchored relative to this file's location
SKILLS_BASE = Path(__file__).resolve().parent.parent / "skills"


class SkillSet:
    """Represents one loaded skill directory.

    Reads the skill's index.md at construction time. The index content is
    pre-loaded into the agent's system prompt by run_task().

    Args:
        skill_name: Name of the skill directory under SKILLS_BASE.

    Raises:
        FileNotFoundError: If the skill directory or index.md does not exist.
    """

    def __init__(self, skill_name: str) -> None:
        self.skill_name = skill_name
        self.skill_dir = SKILLS_BASE / skill_name
        index_path = self.skill_dir / "index.md"
        self.index_content: str = index_path.read_text()


class ReadSkillTool(BaseTool):
    """LangChain tool for loading skill sub-files on demand.

    Accepts paths in 'skill-name/subfile.md' format only.
    Path traversal outside the configured skill directory is blocked — any
    '..' segments or absolute paths raise a hard ValueError.

    Must be a BaseTool subclass (not @tool) because it needs to hold state
    (the skill_dirs mapping). See RESEARCH.md alternatives section.
    """

    name: str = "read-skill"
    description: str = (
        "Load a skill sub-file. Accept path in 'skill-name/subfile.md' format "
        "(e.g. 'household-manager/api-endpoints.md'). "
        "Returns the full text content of the requested file."
    )
    skill_dirs: dict[str, Path] = Field(default_factory=dict)

    def _run(self, path: str) -> str:
        """Load a skill sub-file by 'skill-name/subfile.md' path.

        Raises:
            ValueError: For invalid format, unknown skill, or path traversal.
            FileNotFoundError: If the sub-file does not exist.
        """
        # Validate path format: must contain exactly one '/' splitting into 2 parts
        parts = path.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(
                f"Invalid skill path format: {path!r}. "
                "Expected 'skill-name/subfile.md' format."
            )
        skill_name, subfile = parts

        # Validate skill name is known
        if skill_name not in self.skill_dirs:
            raise ValueError(
                f"Unknown skill: {skill_name!r}. "
                f"Available skills: {list(self.skill_dirs.keys())}"
            )

        base = self.skill_dirs[skill_name].resolve()
        target = (base / subfile).resolve()

        # Block path traversal (resolve() defeats '..' and symlinks)
        if not str(target).startswith(str(base) + "/") and target != base:
            raise ValueError(
                f"Path traversal outside skill directory is not allowed: {path!r}"
            )

        return target.read_text()

    async def _arun(self, path: str) -> str:
        return self._run(path)


def build_read_skill_tool(skill_sets: list[SkillSet]) -> ReadSkillTool:
    """Construct a ReadSkillTool from a list of loaded SkillSet instances.

    Called by run_task() when the agent has at least one skill configured.
    """
    return ReadSkillTool(
        skill_dirs={ss.skill_name: ss.skill_dir for ss in skill_sets}
    )
