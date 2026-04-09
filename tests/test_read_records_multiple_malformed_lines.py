from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "cern_research_dataops_assistant.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "read_records_multiple_malformed_under_test",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_read_records_multiple_malformed_lines_logs_warning_per_line_and_continues(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    records_path = module.init_local_repository(repo_dir)
    records_path.write_text(
        '\n'.join(
            [
                '{"run_id":"run-1"}',
                'invalid-json-token',
                '{"run_id":"run-2"}',
                '{"run_id":"truncated"',
                '{"run_id":"run-3"}',
                '',
            ]
        ),
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING):
        records = list(module.read_records(repo_dir))

    malformed_line_warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelname == "WARNING"
        and record.getMessage().startswith("Skipping malformed JSONL line")
    ]

    assert records == [
        {"run_id": "run-1"},
        {"run_id": "run-2"},
        {"run_id": "run-3"},
    ]
    assert len(malformed_line_warnings) == 2
    assert "Skipping malformed JSONL line 2" in malformed_line_warnings[0]
    assert "Skipping malformed JSONL line 4" in malformed_line_warnings[1]
