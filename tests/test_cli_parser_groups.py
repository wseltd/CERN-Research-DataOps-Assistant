"""Parser group coverage for CLI command-group construction contracts."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "cern_research_dataops_assistant.py"


def _load_bootstrap_module():
    """Load the bootstrap module directly from src path."""
    spec = importlib.util.spec_from_file_location("cli_parser_groups_under_test", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_parser_parses_config_show_and_dataset_list_groups(tmp_path) -> None:
    """build_parser should parse both supported command groups and subcommands."""
    module = _load_bootstrap_module()
    default_config_path = tmp_path / "shared-default.toml"
    parser = module.build_parser(default_config_path)

    config_args = parser.parse_args(["config", "show"])
    dataset_args = parser.parse_args(["dataset", "list"])

    assert config_args.command_group == "config"
    assert config_args.config_command == "show"
    assert config_args.command_id == "config_show"
    assert config_args.config == str(default_config_path)

    assert dataset_args.command_group == "dataset"
    assert dataset_args.dataset_command == "list"
    assert dataset_args.command_id == "dataset_list"
    assert dataset_args.config == str(default_config_path)


def test_build_parser_help_and_defaults_reflect_single_config_path_source(
    tmp_path,
    capsys,
) -> None:
    """Visible defaults in help should consistently use the provided config path."""
    module = _load_bootstrap_module()
    default_config_path = tmp_path / "single-source.toml"
    parser = module.build_parser(default_config_path)

    assert parser.get_default("config") == str(default_config_path)
    assert parser.parse_args(["config", "show"]).config == str(default_config_path)
    assert parser.parse_args(["dataset", "list"]).config == str(default_config_path)

    with pytest.raises(SystemExit) as top_help_exit:
        parser.parse_args(["--help"])
    assert top_help_exit.value.code == 0
    top_help = "".join(capsys.readouterr().out.split())
    assert str(default_config_path) in top_help

    with pytest.raises(SystemExit) as config_help_exit:
        parser.parse_args(["config", "--help"])
    assert config_help_exit.value.code == 0
    config_help = "".join(capsys.readouterr().out.split())
    assert str(default_config_path) in config_help
