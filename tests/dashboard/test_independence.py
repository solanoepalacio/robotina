"""SPEC AC #10 + D-01 enforcement — load-bearing independence gate.

These tests run on every commit in this plan. If any fails, the
dashboard has leaked an import into a non-dashboard module (or a
non-dashboard module has reached into the dashboard package). Both
violate the user-locked D-01 constraint.

WR-04: the original grep-based check matches text only and is bypassed
by extra whitespace, lazy importlib.import_module / __import__ calls,
or re-exports through a third module. The AST-based test below
complements (does not replace) it: defense in depth.
"""
import ast
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


def test_no_reverse_imports_from_dashboard_ast():
    """WR-04: AST-based reverse-imports check (defense in depth vs. the grep).

    Parses every .py file under src/robotina/ (excluding src/robotina/dashboard/)
    and walks the AST for Import / ImportFrom nodes. Asserts that no module
    name or alias targets robotina.dashboard or any submodule thereof.

    Catches the grep's blind spots:
      - `from robotina .dashboard` (extra space) — AST normalizes whitespace.
      - `import robotina.dashboard.app as foo` — alias forms.
      - Multi-target `import a, robotina.dashboard, b` — each name walked.

    Does NOT catch dynamic imports (importlib.import_module / __import__) —
    those require runtime instrumentation, out of scope for a static gate.
    """
    repo_root = Path(__file__).resolve().parents[2]
    src_root = repo_root / "src" / "robotina"
    dashboard_root = src_root / "dashboard"

    forbidden_prefix = "robotina.dashboard"
    offenders: list[tuple[str, int, str]] = []

    for py_file in src_root.rglob("*.py"):
        # Skip the dashboard package itself — D-01 forbids reverse imports
        # FROM non-dashboard code, not dashboard's internal imports.
        try:
            py_file.relative_to(dashboard_root)
            continue
        except ValueError:
            pass

        try:
            tree = ast.parse(py_file.read_text(), filename=str(py_file))
        except SyntaxError as e:  # pragma: no cover — should not happen in src tree
            offenders.append((str(py_file.relative_to(repo_root)), 0, f"unparseable: {e}"))
            continue

        rel = str(py_file.relative_to(repo_root))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name == forbidden_prefix or name.startswith(forbidden_prefix + "."):
                        offenders.append((rel, node.lineno, f"import {name}"))
            elif isinstance(node, ast.ImportFrom):
                # Relative imports (level > 0) cannot escape src/robotina,
                # but `from robotina.dashboard import x` is level=0 module=...
                module = node.module or ""
                if module == forbidden_prefix or module.startswith(forbidden_prefix + "."):
                    offenders.append((rel, node.lineno, f"from {module} import ..."))

    assert not offenders, (
        "AST detected forbidden imports of robotina.dashboard from non-dashboard code:\n"
        + "\n".join(f"  {f}:{ln}  {snippet}" for f, ln, snippet in offenders)
    )
