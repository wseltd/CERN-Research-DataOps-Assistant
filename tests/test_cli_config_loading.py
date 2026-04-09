"""Boundary tests for CLI config-loading behavior in the src implementation module."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "cern_research_dataops_assistant.py"


def _load_bootstrap_module():
    """Load the bootstrap module directly from src path."""
    spec = importlib.util.spec_from_file_location("cli_config_loading_under_test", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_app_config_default_path_resolution_uses_cwd_config_toml(tmp_path, monkeypatch) -> None:
    """When config_path is omitted, load from cwd/config.toml and resolve relative paths."""
    module = _load_bootstrap_module()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.toml").write_text(
        'project_root = "workspace"\n'
        'data_dir = "datasets"\n'
        'log_level = "debug"\n',
        encoding="utf-8",
    )

    result = module.load_app_config()

    assert result.config_path == (tmp_path / "config.toml")
    assert result.project_root == (tmp_path / "workspace")
    assert result.data_dir == (tmp_path / "workspace" / "datasets")
    assert result.log_level == "DEBUG"


def test_load_app_config_rejects_invalid_config_inputs_deterministically(tmp_path) -> None:
    """Invalid path/type/content inputs should fail with deterministic error details."""
    module = _load_bootstrap_module()

    invalid_toml_path = tmp_path / "invalid.toml"
    invalid_toml_path.write_text('log_level = "trace"\n', encoding="utf-8")

    observed_errors: list[tuple[str, str]] = []

    for bad_input in (tmp_path, 123, invalid_toml_path):
        try:
            module.load_app_config(bad_input)
        except (TypeError, ValueError) as exc:
            observed_errors.append((type(exc).__name__, str(exc)))

    expected_errors = [
        (
            "ValueError",
            f"Invalid config_path '{tmp_path}': expected a file path.",
        ),
        (
            "TypeError",
            "Invalid value for 'config_path': expected str or pathlib.Path, got int.",
        ),
        (
            "ValueError",
            "Invalid value for 'log_level': 'trace'. Expected one of ['CRITICAL', 'DEBUG', 'ERROR', 'INFO', 'WARNING'].",
        ),
    ]

    assert observed_errors == expected_errors
