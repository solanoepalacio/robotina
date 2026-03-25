"""Tests for pyproject.toml structure (INFRA-02, INFRA-04).

These tests run without Docker or Redis and verify the project is correctly
wired: scripts declared, packages listed, Python version pinned.
"""
import tomllib
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
PYPROJECT = PROJECT_ROOT / "pyproject.toml"


def load_pyproject() -> dict:
    with open(PYPROJECT, "rb") as f:
        return tomllib.load(f)


def test_pyproject_exists():
    assert PYPROJECT.exists(), "pyproject.toml must exist at project root"


def test_requires_python_pinned():
    data = load_pyproject()
    requires = data["project"]["requires-python"]
    assert "3.12" in requires, f"Python 3.12 must be pinned, got: {requires}"
    assert "<3.13" in requires, f"Upper bound <3.13 required to prevent 3.13 selection, got: {requires}"


def test_script_agent_declared():
    data = load_pyproject()
    scripts = data["project"]["scripts"]
    assert "agent" in scripts, "agent script must be declared"
    assert scripts["agent"] == "robotina.queue.runner:main"


def test_script_migrate_declared():
    data = load_pyproject()
    scripts = data["project"]["scripts"]
    assert "migrate" in scripts, "migrate script must be declared"
    assert scripts["migrate"] == "robotina.db:run_migrations"


def test_experiment_scripts_declared():
    data = load_pyproject()
    scripts = data["project"]["scripts"]
    for name in ("experiments.recipe_research", "experiments.recipe_load", "experiments.send_notification"):
        assert name in scripts, f"Script '{name}' must be declared in [project.scripts]"


def test_packages_include_experiments():
    data = load_pyproject()
    packages = data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert "src/robotina" in packages, "src/robotina must be in wheel packages"
    assert "experiments" in packages, "experiments must be in wheel packages (required for uv run experiments.*)"


def test_experiments_package_importable():
    """experiments/ must have __init__.py so uv entry points can resolve the module."""
    init = PROJECT_ROOT / "experiments" / "__init__.py"
    assert init.exists(), "experiments/__init__.py must exist for package to be importable"


def test_experiment_mains_importable():
    """Each experiment module must export a main() callable."""
    import importlib
    for mod_name in ("experiments.recipe_research", "experiments.recipe_load", "experiments.send_notification"):
        mod = importlib.import_module(mod_name)
        assert callable(getattr(mod, "main", None)), f"{mod_name}.main must be a callable"


def test_alembic_config_valid():
    """alembic.ini and migrations/env.py must exist and contain required elements (INFRA-05 offline check).

    Does not require Postgres — validates toolchain configuration only.
    """
    import configparser
    alembic_ini = PROJECT_ROOT / "alembic.ini"
    env_py = PROJECT_ROOT / "migrations" / "env.py"

    assert alembic_ini.exists(), "alembic.ini must exist"
    assert env_py.exists(), "migrations/env.py must exist"

    cfg = configparser.ConfigParser()
    cfg.read(alembic_ini)
    assert cfg.get("alembic", "script_location") == "migrations", (
        "alembic.ini script_location must be 'migrations'"
    )

    env_content = env_py.read_text()
    assert "sys.path.insert" in env_content, "env.py must add src/ to sys.path"
    assert "DATABASE_URL" in env_content, "env.py must support DATABASE_URL override"
    assert "target_metadata" in env_content, "env.py must declare target_metadata"
