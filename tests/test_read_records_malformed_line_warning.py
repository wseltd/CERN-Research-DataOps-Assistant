from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "cern_research_dataops_assistant.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("read_records_under_test", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_read_records_malformed_line_logs_warning_and_continues(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    records_path = module.init_local_repository(repo_dir)
    records_path.write_text(
        '{"run_id":"run-1"}\n{malformed-json}\n{"run_id":"run-2"}\n',
        encoding="utf-8",
    )

    with caplog.at_level("WARNING"):
        records = list(module.read_records(repo_dir))

    assert records == [{"run_id": "run-1"}, {"run_id": "run-2"}]
    assert "Skipping malformed JSONL line 2" in caplog.text
