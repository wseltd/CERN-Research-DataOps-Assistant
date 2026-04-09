"""Focused tests for CLI entrypoint return and boundary behavior."""

from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "cern_research_dataops_assistant.py"


def _load_module():
    """Load the CLI module from source for direct function testing."""
    spec = importlib.util.spec_from_file_location("cli_main_under_test", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_main_success_path_returns_zero(monkeypatch) -> None:
    """main should return the command handler's success exit code."""
    module = _load_module()

    class StubParser:
        def parse_args(self, _argv):
            return Namespace(config="ignored.toml", command_id=module.COMMAND_ID_CONFIG_SHOW)

    call_state: dict[str, object] = {}

    def fake_load_app_config(config_path):
        call_state["config_path"] = config_path
        return object()

    def fake_run_config_show(config):
        call_state["config"] = config
        return 0

    monkeypatch.setattr(module, "build_parser", lambda: StubParser())
    monkeypatch.setattr(module, "load_app_config", fake_load_app_config)
    monkeypatch.setattr(module, "_run_config_show", fake_run_config_show)

    assert module.main(["config", "show"]) == 0
    assert call_state["config_path"] == "ignored.toml"
    assert "config" in call_state


def test_main_argparse_boundary_failure_returns_nonzero_without_config_load(monkeypatch) -> None:
    """main should return a non-zero code when parsing exits at the CLI boundary."""
    module = _load_module()

    class ExitingParser:
        def parse_args(self, _argv):
            raise SystemExit(2)

    monkeypatch.setattr(module, "build_parser", lambda: ExitingParser())

    def fail_if_called(_config_path):
        raise AssertionError("load_app_config should not run when argparse exits.")

    monkeypatch.setattr(module, "load_app_config", fail_if_called)

    assert module.main(["dataset"]) == 2
