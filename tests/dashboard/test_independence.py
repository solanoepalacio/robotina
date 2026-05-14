"""SPEC AC #10 + D-01 enforcement — load-bearing independence gate.

These tests run on every commit in this plan. If either fails, the
dashboard has leaked an import into a non-dashboard module (or a
non-dashboard module has reached into the dashboard package). Both
violate the user-locked D-01 constraint.
"""
import subprocess
from pathlib import Path


def test_no_reverse_imports_from_dashboard():
    """SPEC AC #10: zero reverse imports from robotina.dashboard."""
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            "grep",
            "-rE",
            r"from robotina\.dashboard|import robotina\.dashboard",
            str(repo_root / "src" / "robotina"),
            "--exclude-dir=dashboard",
        ],
        capture_output=True,
        text=True,
    )
    # grep exits 1 when no match → success.
    assert result.returncode == 1, (
        f"Found reverse imports from robotina.dashboard:\n{result.stdout}"
    )


def test_dashboard_imports_only_allowed_robotina_modules():
    """D-01 inward-only rule: dashboard imports only db, queue.models, queue.task_types."""
    repo_root = Path(__file__).resolve().parents[2]
    dashboard_dir = repo_root / "src" / "robotina" / "dashboard"
    forbidden_prefixes = [
        "from robotina.agent",
        "import robotina.agent",
        "from robotina.gateway",
        "import robotina.gateway",
        "from robotina.llm",
        "import robotina.llm",
        "from robotina.scheduler",
        "import robotina.scheduler",
        "from robotina.queue.workflow_runner",
        "import robotina.queue.workflow_runner",
        "from robotina.queue.runner",
        "import robotina.queue.runner",
        "from robotina.queue.jobs",
        "import robotina.queue.jobs",
        "from robotina.all",
        "import robotina.all",
    ]
    offenders = []
    for py_file in dashboard_dir.rglob("*.py"):
        text = py_file.read_text()
        for pat in forbidden_prefixes:
            if pat in text:
                offenders.append((py_file.relative_to(repo_root), pat))
    assert not offenders, f"Forbidden imports found: {offenders}"
