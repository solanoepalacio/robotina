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

import logging
from pathlib import Path

from langchain_core.tools import BaseTool
from pydantic import Field

logger = logging.getLogger(__name__)

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
        "Load a skill sub-file. The path MUST include the skill name as a prefix: "
        "'skill-name/subfile.md' (e.g. 'household-manager/meal_plan.md'). "
        "WRONG: 'meal_plan.md'. CORRECT: 'household-manager/meal_plan.md'. "
        "Returns the full text content of the requested file."
    )
    skill_dirs: dict[str, Path] = Field(default_factory=dict)

    def _run(self, path: str) -> str:
        """Load a skill sub-file by 'skill-name/subfile.md' path.

        Errors are returned as strings so the LLM can fix its input and retry
        instead of crashing the task.
        """
        # Validate path format: must contain exactly one '/' splitting into 2 parts
        parts = path.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            available = list(self.skill_dirs.keys())
            logger.warning("read-skill invalid path format: %r", path)
            return (
                f"ERROR: Invalid path format: {path!r}. "
                f"You must include the skill name prefix: 'skill-name/subfile.md'. "
                f"Available skills: {available}"
            )
        skill_name, subfile = parts

        # Validate skill name is known
        if skill_name not in self.skill_dirs:
            available = list(self.skill_dirs.keys())
            logger.warning("read-skill unknown skill: %r", skill_name)
            return (
                f"ERROR: Unknown skill: {skill_name!r}. "
                f"Available skills: {available}"
            )

        base = self.skill_dirs[skill_name].resolve()
        target = (base / subfile).resolve()

        # Block path traversal (resolve() defeats '..' and symlinks)
        if not str(target).startswith(str(base) + "/") and target != base:
            logger.warning("read-skill path traversal attempt: %r", path)
            return f"ERROR: Path traversal outside skill directory is not allowed: {path!r}"

        try:
            return target.read_text()
        except FileNotFoundError:
            logger.warning("read-skill file not found: %r", path)
            return f"ERROR: File not found: {path!r}"

    async def _arun(self, path: str) -> str:
        return self._run(path)


def build_read_skill_tool(skill_sets: list[SkillSet]) -> ReadSkillTool:
    """Construct a ReadSkillTool from a list of loaded SkillSet instances.

    Called by run_task() when the agent has at least one skill configured.
    """
    return ReadSkillTool(
        skill_dirs={ss.skill_name: ss.skill_dir for ss in skill_sets}
    )
