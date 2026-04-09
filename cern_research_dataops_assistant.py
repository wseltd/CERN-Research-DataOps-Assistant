"""Console-script bridge for the local-first CERN DataOps CLI.

The production implementation lives in ``src/cern_research_dataops_assistant.py``.
This module is kept as the console entrypoint target and delegates execution to
the implementation module to preserve the public script contract.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


IMPLEMENTATION_MODULE_PATH = (
    Path(__file__).resolve().parent / "src" / "cern_research_dataops_assistant.py"
)


def _load_implementation_module() -> ModuleType:
    """Load and return the concrete CLI implementation module from ``src``."""
    module_spec = importlib.util.spec_from_file_location(
        "cern_research_dataops_assistant_impl",
        IMPLEMENTATION_MODULE_PATH,
    )
    if module_spec is None or module_spec.loader is None:
        raise ImportError(
            f"Unable to load CLI implementation from '{IMPLEMENTATION_MODULE_PATH}'."
        )
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def main() -> int:
    """Run the delegated CLI entrypoint and return a process exit code."""
    implementation = _load_implementation_module()
    return int(implementation.run_with_exit_handling())
