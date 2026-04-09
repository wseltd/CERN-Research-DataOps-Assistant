from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "cern_research_dataops_assistant.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("local_repo_under_test", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_init_local_repository_creates_repo_directory_and_visible_records_file(
    tmp_path: Path,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "missing-repo"

    records_path = module.init_local_repository(repo_dir)

    assert repo_dir.is_dir()
    assert records_path == repo_dir / module.RECORDS_JSONL_FILENAME
    assert records_path.exists()
    assert records_path.is_file()
    assert records_path.name == "records.jsonl"
