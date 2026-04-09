"""Contract tests for packaging metadata in pyproject.toml."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import tomllib


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_pyproject() -> dict:
    """Load and parse project metadata from pyproject.toml."""
    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))


def test_pyproject_uses_setuptools_build_meta_and_console_entrypoint() -> None:
    """Ensure build backend and console script entrypoint contract are stable."""
    pyproject_data = _load_pyproject()

    assert pyproject_data["build-system"]["build-backend"] == "setuptools.build_meta"

    entrypoint = pyproject_data["project"]["scripts"]["cern-dataops"]
    assert entrypoint == "cern_research_dataops_assistant:main"

    module_name, function_name = entrypoint.split(":")
    module_spec = importlib.util.find_spec(module_name)
    assert module_spec is not None

    module = __import__(module_name, fromlist=[function_name])
    assert hasattr(module, function_name)


def test_pyproject_runtime_and_test_dependencies_are_pinned() -> None:
    """Verify runtime and test dependencies are explicit pinned versions."""
    pyproject_data = _load_pyproject()

    runtime_dependencies = pyproject_data["project"].get("dependencies", [])
    test_dependencies = pyproject_data["project"].get("optional-dependencies", {}).get("test", [])

    assert runtime_dependencies
    assert test_dependencies
    assert all("==" in dependency for dependency in runtime_dependencies + test_dependencies)
