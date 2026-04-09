"""Contract tests for CLI bootstrap behavior in the src implementation module."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "cern_research_dataops_assistant.py"


def _load_bootstrap_module():
    """Load the bootstrap module directly from src path."""
    spec = importlib.util.spec_from_file_location("cli_bootstrap_under_test", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_app_config_without_overrides_uses_visible_defaults(tmp_path, monkeypatch) -> None:
    """Defaults should derive from cwd/config.toml when no config file is present."""
    module = _load_bootstrap_module()
    monkeypatch.chdir(tmp_path)

    config = module.load_app_config()

    assert config.config_path == (tmp_path / "config.toml")
    assert config.project_root == tmp_path
    assert config.data_dir == (tmp_path / "data")
    assert config.log_level == "INFO"


def test_load_app_config_with_data_dir_override_uses_override(tmp_path) -> None:
    """Config file data_dir should override the default data path."""
    module = _load_bootstrap_module()
    config_path = tmp_path / "assistant.toml"
    config_path.write_text('data_dir = "datasets"\n', encoding="utf-8")

    config = module.load_app_config(config_path)

    assert config.config_path == config_path
    assert config.project_root == tmp_path
    assert config.data_dir == (tmp_path / "datasets")


def test_build_parser_parses_config_show_command(tmp_path) -> None:
    """Parser should accept the config/show command path."""
    module = _load_bootstrap_module()
    default_config_path = tmp_path / "cfg.toml"

    parser = module.build_parser(default_config_path)
    args = parser.parse_args(["config", "show"])

    assert args.command_group == "config"
    assert args.config_command == "show"
    assert args.command_id == "config_show"
    assert args.config == str(default_config_path)


def test_build_parser_parses_dataset_list_command(tmp_path) -> None:
    """Parser should accept the dataset/list command path."""
    module = _load_bootstrap_module()
    default_config_path = tmp_path / "cfg.toml"

    parser = module.build_parser(default_config_path)
    args = parser.parse_args(["dataset", "list"])

    assert args.command_group == "dataset"
    assert args.dataset_command == "list"
    assert args.command_id == "dataset_list"
    assert args.config == str(default_config_path)


def test_main_help_flag_returns_zero() -> None:
    """main should return zero for help output."""
    module = _load_bootstrap_module()

    assert module.main(["--help"]) == 0


def test_main_unknown_command_returns_nonzero() -> None:
    """main should return non-zero when command parsing fails."""
    module = _load_bootstrap_module()

    assert module.main(["unknown"]) != 0
