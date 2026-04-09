"""Exit-code mapping contracts for deterministic CLI failure handling."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXIT_CODES_MODULE_PATH = PROJECT_ROOT / "src" / "exit_codes.py"
APP_MODULE_PATH = PROJECT_ROOT / "src" / "cern_research_dataops_assistant.py"


def _load_module(module_path: Path, module_name: str):
    """Load one module directly from source path for isolated contract tests."""
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_map_exception_to_exit_code_returns_known_non_zero_codes() -> None:
    module = _load_module(EXIT_CODES_MODULE_PATH, "exit_codes_known_cases_under_test")

    assert module.map_exception_to_exit_code(ValueError("bad input")) == module.ExitCode.INVALID_INPUT
    assert module.map_exception_to_exit_code(TypeError("bad type")) == module.ExitCode.INVALID_INPUT
    assert module.map_exception_to_exit_code(OSError("io failed")) == module.ExitCode.IO_ERROR
    assert module.map_exception_to_exit_code(KeyboardInterrupt()) == module.ExitCode.INTERRUPTED


def test_map_exception_to_exit_code_uses_single_fallback_for_unknown_exception_types() -> None:
    module = _load_module(EXIT_CODES_MODULE_PATH, "exit_codes_unknown_cases_under_test")

    class UnknownFailure(Exception):
        pass

    class AnotherUnknownFailure(RuntimeError):
        pass

    first_code = module.map_exception_to_exit_code(UnknownFailure("first"))
    second_code = module.map_exception_to_exit_code(AnotherUnknownFailure("second"))

    assert first_code == module.ExitCode.UNEXPECTED_ERROR
    assert second_code == module.ExitCode.UNEXPECTED_ERROR


def test_map_exception_to_exit_code_never_returns_ok_for_exceptions() -> None:
    module = _load_module(EXIT_CODES_MODULE_PATH, "exit_codes_ok_guard_under_test")

    samples = [
        ValueError("bad input"),
        TypeError("bad type"),
        OSError("disk full"),
        KeyboardInterrupt(),
        RuntimeError("unknown"),
    ]
    mapped_codes = [module.map_exception_to_exit_code(exc) for exc in samples]

    assert all(code != module.ExitCode.OK for code in mapped_codes)


def test_app_module_exposes_exit_code_type_and_mapping_function() -> None:
    module = _load_module(APP_MODULE_PATH, "app_exit_code_exports_under_test")

    code = module.map_exception_to_exit_code(ValueError("bad input"))

    assert hasattr(module, "ExitCode")
    assert isinstance(code, int)
    assert code == module.ExitCode.INVALID_INPUT


def test_run_with_exit_handling_maps_unhandled_exception_to_nonzero_exit(monkeypatch) -> None:
    module = _load_module(APP_MODULE_PATH, "app_exit_code_runtime_under_test")

    def _raise_permission_error(_argv=None):
        raise PermissionError("denied")

    monkeypatch.setattr(module, "configure_logging", lambda _level: None)
    monkeypatch.setattr(module, "main", _raise_permission_error)

    code = module.run_with_exit_handling(["summary", "./repo"])

    assert code == int(module.ExitCode.IO_ERROR)
