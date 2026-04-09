from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "cern_research_dataops_assistant.py"


def _load_module():
    """Load the module under test directly from src path."""
    spec = importlib.util.spec_from_file_location("append_atomic_replace_failure_under_test", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_append_record_atomic_replace_failure_preserves_original_content_and_cleans_temp_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    records_path = module.init_local_repository(repo_dir)

    original_lines = [
        {"experiment": "ATLAS", "run_id": "run-1", "timestamp": "2026-01-01T00:00:00Z", "payload": {}},
        {"experiment": "CMS", "run_id": "run-2", "timestamp": "2026-01-02T00:00:00Z", "payload": {"k": "v"}},
    ]
    records_path.write_text(
        "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in original_lines),
        encoding="utf-8",
    )

    def _raise_replace_failure(source: Path, destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(module.os, "replace", _raise_replace_failure)

    with pytest.raises(OSError, match="simulated replace failure"):
        module.append_record_atomic(
            repo_dir,
            {
                "experiment": "LHCb",
                "run_id": "run-3",
                "timestamp": "2026-01-03T00:00:00Z",
                "payload": {"new": True},
            },
        )

    assert records_path.read_text(encoding="utf-8") == "".join(
        json.dumps(line, ensure_ascii=False) + "\n" for line in original_lines
    )
    assert list(repo_dir.glob("records.jsonl.*.tmp")) == []
