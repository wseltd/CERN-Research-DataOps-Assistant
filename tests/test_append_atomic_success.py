from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "cern_research_dataops_assistant.py"


def _load_module():
    """Load the module under test directly from src path."""
    spec = importlib.util.spec_from_file_location("append_atomic_under_test", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_append_record_atomic_existing_jsonl_preserves_lines_and_jsonl_delimiters(
    tmp_path: Path,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    records_path = module.init_local_repository(repo_dir)

    existing_jsonl = (
        json.dumps({"run_id": "run-1"}, ensure_ascii=False)
        + "\n"
        + json.dumps({"run_id": "run-2"}, ensure_ascii=False)
        + "\n"
    )
    records_path.write_text(existing_jsonl, encoding="utf-8")

    new_record = {"run_id": "run-3"}
    module.append_record_atomic(repo_dir, new_record)

    expected_jsonl = existing_jsonl + json.dumps(new_record, ensure_ascii=False) + "\n"
    resulting_jsonl = records_path.read_text(encoding="utf-8")

    assert resulting_jsonl == expected_jsonl
    assert resulting_jsonl.endswith("\n")
    assert [json.loads(line) for line in resulting_jsonl.splitlines()] == [
        {"run_id": "run-1"},
        {"run_id": "run-2"},
        {"run_id": "run-3"},
    ]
