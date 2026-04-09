from __future__ import annotations

import argparse
import importlib.util
import json
import os as stdlib_os
import sys
from argparse import Namespace
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "cern_research_dataops_assistant.py"


def _load_module():
    """Load the module under test directly from src path."""
    spec = importlib.util.spec_from_file_location("record_parser_under_test", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_record_valid_record_returns_canonical_fields() -> None:
    module = _load_module()

    result = module.parse_record(
        {
            "experiment": "ATLAS",
            "run_id": "run-1",
            "timestamp": "2026-01-01T00:00:00Z",
            "payload": {"tag": "muon"},
            "extra": "drop-me",
        }
    )

    assert result == {
        "experiment": "ATLAS",
        "run_id": "run-1",
        "timestamp": "2026-01-01T00:00:00Z",
        "payload": {"tag": "muon"},
    }


def test_parse_record_missing_experiment_raises_value_error() -> None:
    module = _load_module()

    with pytest.raises(ValueError) as exc_info:
        module.parse_record(
            {
                "run_id": "run-1",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {"tag": "muon"},
            }
        )

    assert str(exc_info.value) == "Missing required field 'experiment'."


def test_parse_record_invalid_timestamp_raises_value_error() -> None:
    module = _load_module()

    with pytest.raises(ValueError) as exc_info:
        module.parse_record(
            {
                "experiment": "ATLAS",
                "run_id": "run-1",
                "timestamp": "not-a-timestamp",
                "payload": {"tag": "muon"},
            }
        )

    assert str(exc_info.value) == "Invalid value for 'timestamp': expected UTC ISO-8601 string."
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_parse_record_non_dict_payload_raises_value_error() -> None:
    module = _load_module()

    with pytest.raises(ValueError) as exc_info:
        module.parse_record(
            {
                "experiment": "ATLAS",
                "run_id": "run-1",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": ["not", "a", "dict"],
            }
        )

    assert str(exc_info.value) == "Invalid value for 'payload': expected dict."


def test_init_local_repository_creates_records_jsonl_file(tmp_path: Path) -> None:
    module = _load_module()

    records_path = module.init_local_repository(tmp_path / "repo")

    assert records_path.name == module.RECORDS_JSONL_FILENAME
    assert records_path.exists()
    assert records_path.is_file()


def test_init_local_repository_is_idempotent(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"

    first_path = module.init_local_repository(repo_dir)
    first_path.write_text("", encoding="utf-8")
    second_path = module.init_local_repository(repo_dir)

    assert second_path == first_path
    assert second_path.exists()
    assert second_path.read_text(encoding="utf-8") == ""


def test_append_record_atomic_appends_without_overwrite(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)

    module.append_record_atomic(repo_dir, {"run_id": "run-1"})
    module.append_record_atomic(repo_dir, {"run_id": "run-2"})

    records_path = repo_dir / module.RECORDS_JSONL_FILENAME
    lines = records_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    assert [json.loads(line)["run_id"] for line in lines] == ["run-1", "run-2"]


def test_append_record_atomic_replace_failure_preserves_original_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    module.append_record_atomic(repo_dir, {"run_id": "run-1"})

    def _raise_replace_failure(source: Path, destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(module.os, "replace", _raise_replace_failure)

    with pytest.raises(OSError, match="simulated replace failure"):
        module.append_record_atomic(repo_dir, {"run_id": "run-2"})

    records_path = repo_dir / module.RECORDS_JSONL_FILENAME
    lines = records_path.read_text(encoding="utf-8").splitlines()
    temp_files = list(repo_dir.glob("records.jsonl.*.tmp"))

    assert len(lines) == 1
    assert json.loads(lines[0]) == {"run_id": "run-1"}
    assert temp_files == []


def test_read_records_malformed_line_logs_warning_and_continues(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    records_path = module.init_local_repository(repo_dir)
    records_path.write_text(
        '{"run_id":"run-1"}\nnot-json\n{"run_id":"run-2"}\n',
        encoding="utf-8",
    )

    with caplog.at_level("WARNING"):
        records = module.read_records(repo_dir)

    assert records == [{"run_id": "run-1"}, {"run_id": "run-2"}]
    assert "Skipping malformed JSONL line 2" in caplog.text


def test_ingest_single_valid_record_inserts_once(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)

    summary = module.ingest(
        str(repo_dir),
        [
            {
                "experiment": "ATLAS",
                "run_id": "run-1",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {"tag": "muon"},
            }
        ],
    )

    stored_rows = list(module.read_records(repo_dir))
    assert summary == {
        "accepted": 1,
        "invalid": 0,
        "skipped_existing": 0,
        "skipped_batch": 0,
        "inserted": 1,
        "skipped_duplicates": 0,
    }
    assert stored_rows == [
        {
            "experiment": "ATLAS",
            "run_id": "run-1",
            "timestamp": "2026-01-01T00:00:00Z",
            "payload": {"tag": "muon"},
        }
    ]


def test_ingest_returns_inserted_and_skipped_duplicate_counts(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-0",
            "timestamp": "2026-01-01T00:00:00Z",
            "payload": {"existing": True},
        },
    )

    summary = module.ingest(
        str(repo_dir),
        [
            {
                "experiment": "ATLAS",
                "run_id": "run-0",
                "timestamp": "2026-01-01T00:00:01Z",
                "payload": {"existing": "duplicate"},
            },
            {
                "experiment": "ATLAS",
                "run_id": "run-1",
                "timestamp": "2026-01-01T00:00:02Z",
                "payload": {"new": 1},
            },
            {
                "experiment": "ATLAS",
                "run_id": "run-1",
                "timestamp": "2026-01-01T00:00:03Z",
                "payload": {"new": 2},
            },
        ],
    )

    stored_rows = list(module.read_records(repo_dir))
    assert summary["inserted"] == 1
    assert summary["skipped_duplicates"] == 2
    assert summary["accepted"] == 1
    assert summary["skipped_existing"] == 1
    assert summary["skipped_batch"] == 1
    assert [row["run_id"] for row in stored_rows] == ["run-0", "run-1"]


def test_ingest_duplicate_run_id_in_batch_keeps_first_record(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)

    summary = module.ingest(
        str(repo_dir),
        [
            {
                "experiment": "ATLAS",
                "run_id": "run-5",
                "timestamp": "2026-01-05T00:00:00Z",
                "payload": {"first": True},
            },
            {
                "experiment": "ATLAS",
                "run_id": "run-5",
                "timestamp": "2026-01-05T00:00:01Z",
                "payload": {"first": False},
            },
        ],
    )

    stored_rows = list(module.read_records(repo_dir))
    assert summary["accepted"] == 1
    assert summary["skipped_batch"] == 1
    assert len(stored_rows) == 1
    assert stored_rows[0]["payload"] == {"first": True}
    assert stored_rows[0]["timestamp"] == "2026-01-05T00:00:00Z"


def test_ingest_duplicate_run_id_in_repository_is_skipped(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-existing",
            "timestamp": "2026-01-06T00:00:00Z",
            "payload": {"source": "repo"},
        },
    )

    summary = module.ingest(
        str(repo_dir),
        [
            {
                "experiment": "ATLAS",
                "run_id": "run-existing",
                "timestamp": "2026-01-06T00:00:01Z",
                "payload": {"source": "batch"},
            }
        ],
    )

    stored_rows = list(module.read_records(repo_dir))
    assert summary["accepted"] == 0
    assert summary["skipped_existing"] == 1
    assert summary["inserted"] == 0
    assert len(stored_rows) == 1
    assert stored_rows[0]["payload"] == {"source": "repo"}


def test_ingest_second_run_with_same_batch_is_idempotent(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    batch = [
        {
            "experiment": "ATLAS",
            "run_id": "run-10",
            "timestamp": "2026-01-10T00:00:00Z",
            "payload": {"value": 10},
        },
        {
            "experiment": "ATLAS",
            "run_id": "run-11",
            "timestamp": "2026-01-11T00:00:00Z",
            "payload": {"value": 11},
        },
    ]

    first_summary = module.ingest(str(repo_dir), batch)
    second_summary = module.ingest(str(repo_dir), batch)
    stored_rows = list(module.read_records(repo_dir))

    assert first_summary["inserted"] == 2
    assert first_summary["skipped_duplicates"] == 0
    assert second_summary["inserted"] == 0
    assert second_summary["skipped_existing"] == 2
    assert second_summary["skipped_duplicates"] == 2
    assert len(stored_rows) == 2
    assert [row["run_id"] for row in stored_rows] == ["run-10", "run-11"]


def test_ingest_invalid_record_logs_warning_and_continues(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)

    with caplog.at_level("WARNING"):
        summary = module.ingest(
            str(repo_dir),
            [
                {
                    "experiment": "ATLAS",
                    "run_id": "run-invalid",
                    "timestamp": "2026-01-12T00:00:00Z",
                    "payload": ["invalid-payload"],
                },
                {
                    "experiment": "ATLAS",
                    "run_id": "run-12",
                    "timestamp": "2026-01-12T00:00:01Z",
                    "payload": {"ok": True},
                },
            ],
        )

    stored_rows = list(module.read_records(repo_dir))
    assert summary["invalid"] == 1
    assert summary["accepted"] == 1
    assert len(stored_rows) == 1
    assert "Skipping invalid record at index 1: Invalid value for 'payload': expected dict." in caplog.text


def test_ingest_mixed_valid_invalid_and_duplicate_records_persists_only_unique_valid(
    tmp_path: Path,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-existing",
            "timestamp": "2026-01-13T00:00:00Z",
            "payload": {"repo": True},
        },
    )

    summary = module.ingest(
        str(repo_dir),
        [
            {
                "experiment": "ATLAS",
                "run_id": "run-13",
                "timestamp": "2026-01-13T00:00:01Z",
                "payload": {"batch": "first"},
            },
            {
                "experiment": "ATLAS",
                "run_id": "run-existing",
                "timestamp": "2026-01-13T00:00:02Z",
                "payload": {"batch": "existing"},
            },
            {
                "experiment": "ATLAS",
                "run_id": "run-invalid",
                "timestamp": "2026-01-13T00:00:03Z",
                "payload": ["invalid-payload"],
            },
            {
                "experiment": "ATLAS",
                "run_id": "run-13",
                "timestamp": "2026-01-13T00:00:04Z",
                "payload": {"batch": "duplicate"},
            },
            "not-a-record",
            {
                "experiment": "ATLAS",
                "run_id": "run-14",
                "timestamp": "2026-01-13T00:00:05Z",
                "payload": {"batch": "second"},
            },
        ],
    )

    stored_rows = list(module.read_records(repo_dir))
    assert summary == {
        "accepted": 2,
        "invalid": 2,
        "skipped_existing": 1,
        "skipped_batch": 1,
        "inserted": 2,
        "skipped_duplicates": 2,
    }
    assert [row["run_id"] for row in stored_rows] == ["run-existing", "run-13", "run-14"]
    assert stored_rows[1]["payload"] == {"batch": "first"}


def test_ingest_append_failure_raises_and_preserves_existing_repository_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    records_path = module.init_local_repository(repo_dir)
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-existing",
            "timestamp": "2026-01-14T00:00:00Z",
            "payload": {"repo": True},
        },
    )
    original_contents = records_path.read_text(encoding="utf-8")

    def _raise_replace_failure(source: Path, destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(module.os, "replace", _raise_replace_failure)

    with pytest.raises(OSError, match="simulated replace failure"):
        module.ingest(
            str(repo_dir),
            [
                {
                    "experiment": "ATLAS",
                    "run_id": "run-new",
                    "timestamp": "2026-01-14T00:00:01Z",
                    "payload": {"repo": False},
                }
            ],
        )

    assert records_path.read_text(encoding="utf-8") == original_contents
    assert list(repo_dir.glob("records.jsonl.*.tmp")) == []


def test_query_without_filters_returns_all_sorted_by_timestamp_then_run_id(
    tmp_path: Path,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-2",
            "timestamp": "2026-01-01T00:00:01Z",
            "payload": {"tag": "muon"},
        },
    )
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "CMS",
            "run_id": "run-3",
            "timestamp": "2026-01-01T00:00:00Z",
            "payload": {"tag": "muon"},
        },
    )
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-1",
            "timestamp": "2026-01-01T00:00:01Z",
            "payload": {"tag": "muon"},
        },
    )

    result = module.query(repo_dir)

    assert [record["run_id"] for record in result] == ["run-3", "run-1", "run-2"]


def test_query_filter_by_experiment_returns_matching_records(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "CMS",
            "run_id": "run-1",
            "timestamp": "2026-01-02T00:00:01Z",
            "payload": {"tag": "muon"},
        },
    )
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-2",
            "timestamp": "2026-01-02T00:00:00Z",
            "payload": {"tag": "electron"},
        },
    )

    result = module.query(repo_dir, experiment="ATLAS")

    assert len(result) == 1
    assert result[0]["experiment"] == "ATLAS"
    assert result[0]["run_id"] == "run-2"


def test_query_filter_by_date_matches_timestamp_utc_date(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-1",
            "timestamp": "2026-01-03T23:59:59Z",
            "payload": {"tag": "muon"},
        },
    )
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-2",
            "timestamp": "2026-01-04T00:00:00Z",
            "payload": {"tag": "muon"},
        },
    )

    result = module.query(repo_dir, date="2026-01-03")

    assert [record["run_id"] for record in result] == ["run-1"]


def test_query_filter_by_tag_matches_payload_tag(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-1",
            "timestamp": "2026-01-05T00:00:00Z",
            "payload": {"tag": "electron"},
        },
    )
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-2",
            "timestamp": "2026-01-05T00:00:01Z",
            "payload": {"tag": "muon"},
        },
    )

    result = module.query(repo_dir, tag="muon")

    assert [record["run_id"] for record in result] == ["run-2"]


def test_query_combined_filters_apply_logical_and(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-match",
            "timestamp": "2026-01-06T00:00:00Z",
            "payload": {"tag": "muon"},
        },
    )
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-wrong-tag",
            "timestamp": "2026-01-06T00:00:01Z",
            "payload": {"tag": "electron"},
        },
    )
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "CMS",
            "run_id": "run-wrong-experiment",
            "timestamp": "2026-01-06T00:00:00Z",
            "payload": {"tag": "muon"},
        },
    )
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-wrong-date",
            "timestamp": "2026-01-07T00:00:00Z",
            "payload": {"tag": "muon"},
        },
    )

    result = module.query(
        repo_dir,
        experiment="ATLAS",
        date="2026-01-06",
        tag="muon",
    )

    assert [record["run_id"] for record in result] == ["run-match"]


def test_query_tiebreaker_run_id_makes_equal_timestamp_order_deterministic(
    tmp_path: Path,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-2",
            "timestamp": "2026-01-08T00:00:00Z",
            "payload": {"tag": "muon"},
        },
    )
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-1",
            "timestamp": "2026-01-08T00:00:00Z",
            "payload": {"tag": "muon"},
        },
    )

    result = module.query(repo_dir)

    assert [record["run_id"] for record in result] == ["run-1", "run-2"]


def test_query_no_match_returns_empty_list(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "CMS",
            "run_id": "run-1",
            "timestamp": "2026-01-09T00:00:00Z",
            "payload": {"tag": "muon"},
        },
    )

    result = module.query(repo_dir, experiment="ATLAS")

    assert result == []


def test_query_tag_filter_ignores_records_without_payload_tag(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-missing-tag",
            "timestamp": "2026-01-10T00:00:00Z",
            "payload": {},
        },
    )
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-with-tag",
            "timestamp": "2026-01-10T00:00:01Z",
            "payload": {"tag": "muon"},
        },
    )

    result = module.query(repo_dir, tag="muon")

    assert [record["run_id"] for record in result] == ["run-with-tag"]


def test_query_command_emits_sorted_jsonl_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-2",
            "timestamp": "2026-01-01T00:00:01Z",
            "payload": {"tag": "muon"},
        },
    )
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-1",
            "timestamp": "2026-01-01T00:00:01Z",
            "payload": {"tag": "muon"},
        },
    )
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "CMS",
            "run_id": "run-3",
            "timestamp": "2026-01-01T00:00:00Z",
            "payload": {"tag": "muon"},
        },
    )

    exit_code = module.query_command(
        Namespace(
            repo_dir=str(repo_dir),
            experiment="ATLAS",
            date="2026-01-01",
            tag="muon",
        )
    )

    captured_output = capsys.readouterr().out.splitlines()
    parsed_output = [json.loads(line) for line in captured_output]

    assert exit_code == 0
    assert [record["run_id"] for record in parsed_output] == ["run-1", "run-2"]


def test_atomic_write_tempfile_creation_failure_triggers_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    records_path = module.init_local_repository(repo_dir)
    records_path.write_text('{"run_id":"run-1"}\n', encoding="utf-8")
    original_contents = records_path.read_text(encoding="utf-8")

    def _raise_tempfile_creation_failure(*_args, **_kwargs):
        raise OSError("simulated tempfile creation failure")

    monkeypatch.setattr(module.tempfile, "mkstemp", _raise_tempfile_creation_failure)

    with pytest.raises(OSError, match="simulated tempfile creation failure"):
        module.append_record_atomic(repo_dir, {"run_id": "run-2"})

    assert records_path.read_text(encoding="utf-8") == original_contents
    assert list(repo_dir.glob("records.jsonl.*.tmp")) == []


def test_atomic_write_flush_failure_triggers_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    records_path = module.init_local_repository(repo_dir)
    records_path.write_text('{"run_id":"run-1"}\n', encoding="utf-8")
    original_contents = records_path.read_text(encoding="utf-8")

    original_fdopen = stdlib_os.fdopen

    class _FlushFailingFile:
        def __init__(self, fd: int, mode: str) -> None:
            self._file = original_fdopen(fd, mode)

        def __enter__(self) -> "_FlushFailingFile":
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> bool:
            self._file.close()
            return False

        def write(self, data: bytes) -> int:
            return self._file.write(data)

        def flush(self) -> None:
            raise OSError("simulated flush failure")

        def fileno(self) -> int:
            return self._file.fileno()

    def _failing_fdopen(fd: int, mode: str):
        return _FlushFailingFile(fd, mode)

    monkeypatch.setattr(module.os, "fdopen", _failing_fdopen)

    with pytest.raises(OSError, match="simulated flush failure"):
        module.append_record_atomic(repo_dir, {"run_id": "run-2"})

    assert records_path.read_text(encoding="utf-8") == original_contents
    assert list(repo_dir.glob("records.jsonl.*.tmp")) == []


def test_atomic_write_fsync_failure_triggers_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    records_path = module.init_local_repository(repo_dir)
    records_path.write_text('{"run_id":"run-1"}\n', encoding="utf-8")
    original_contents = records_path.read_text(encoding="utf-8")

    def _raise_fsync_failure(_fd: int) -> None:
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(module.os, "fsync", _raise_fsync_failure)

    with pytest.raises(OSError, match="simulated fsync failure"):
        module.append_record_atomic(repo_dir, {"run_id": "run-2"})

    assert records_path.read_text(encoding="utf-8") == original_contents
    assert list(repo_dir.glob("records.jsonl.*.tmp")) == []


def test_atomic_write_replace_failure_preserves_original_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    records_path = module.init_local_repository(repo_dir)
    records_path.write_text('{"run_id":"run-1"}\n', encoding="utf-8")
    original_contents = records_path.read_text(encoding="utf-8")

    def _raise_replace_failure(_source: Path, _destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(module.os, "replace", _raise_replace_failure)

    with pytest.raises(OSError, match="simulated replace failure"):
        module.append_record_atomic(repo_dir, {"run_id": "run-2"})

    assert records_path.read_text(encoding="utf-8") == original_contents
    assert list(repo_dir.glob("records.jsonl.*.tmp")) == []


def test_atomic_write_rollback_cleanup_failure_logs_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    records_path = module.init_local_repository(repo_dir)
    records_path.write_text('{"run_id":"run-1"}\n', encoding="utf-8")
    original_contents = records_path.read_text(encoding="utf-8")

    def _raise_replace_failure(_source: Path, _destination: Path) -> None:
        raise OSError("simulated replace failure")

    original_unlink = Path.unlink

    def _raise_cleanup_failure(path: Path, *args, **kwargs):
        if path.name.startswith("records.jsonl.") and path.suffix == ".tmp":
            raise OSError("simulated cleanup failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(module.os, "replace", _raise_replace_failure)
    monkeypatch.setattr(module.pathlib.Path, "unlink", _raise_cleanup_failure)

    with caplog.at_level("WARNING"):
        with pytest.raises(OSError, match="simulated replace failure"):
            module.append_record_atomic(repo_dir, {"run_id": "run-2"})

    assert records_path.read_text(encoding="utf-8") == original_contents
    assert len(list(repo_dir.glob("records.jsonl.*.tmp"))) == 1
    assert "Failed to remove temporary repository file" in caplog.text


def test_dedupe_replay_same_record_second_ingest_is_noop(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    replay_batch = [
        {
            "experiment": "ATLAS",
            "run_id": "run-replay",
            "timestamp": "2026-02-01T00:00:00Z",
            "payload": {"tag": "muon"},
        }
    ]

    first_summary = module.ingest(str(repo_dir), replay_batch)
    second_summary = module.ingest(str(repo_dir), replay_batch)
    stored_rows = list(module.read_records(repo_dir))

    assert first_summary["inserted"] == 1
    assert second_summary["inserted"] == 0
    assert second_summary["skipped_existing"] == 1
    assert len(stored_rows) == 1


def test_dedupe_semantic_duplicate_with_reordered_keys_is_noop(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    first_record = {
        "experiment": "ATLAS",
        "run_id": "run-semantic",
        "timestamp": "2026-02-02T00:00:00Z",
        "payload": {"alpha": 1, "beta": 2},
    }
    semantically_duplicate_reordered = {
        "payload": {"beta": 2, "alpha": 1},
        "timestamp": "2026-02-02T00:00:00Z",
        "run_id": "run-semantic",
        "experiment": "ATLAS",
    }

    first_summary = module.ingest(str(repo_dir), [first_record])
    second_summary = module.ingest(str(repo_dir), [semantically_duplicate_reordered])
    stored_rows = list(module.read_records(repo_dir))

    assert first_summary["inserted"] == 1
    assert second_summary["inserted"] == 0
    assert second_summary["skipped_existing"] == 1
    assert len(stored_rows) == 1
    assert stored_rows[0]["payload"] == {"alpha": 1, "beta": 2}


def test_dedupe_missing_identifier_falls_back_to_stable_fingerprint(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    records_missing_run_id = [
        {
            "experiment": "ATLAS",
            "timestamp": "2026-02-03T00:00:00Z",
            "payload": {"tag": "muon"},
        },
        {
            "experiment": "ATLAS",
            "timestamp": "2026-02-03T00:00:00Z",
            "payload": {"tag": "muon"},
        },
    ]

    first_summary = module.ingest(str(repo_dir), records_missing_run_id)
    second_summary = module.ingest(str(repo_dir), records_missing_run_id)
    stored_rows = list(module.read_records(repo_dir))

    assert first_summary["accepted"] == 1
    assert first_summary["invalid"] == 0
    assert first_summary["skipped_batch"] == 1
    assert first_summary["inserted"] == 1
    assert first_summary["skipped_duplicates"] == 1
    assert second_summary["accepted"] == 0
    assert second_summary["invalid"] == 0
    assert second_summary["skipped_existing"] == 2
    assert second_summary["inserted"] == 0
    assert len(stored_rows) == 1
    assert isinstance(stored_rows[0]["run_id"], str)
    assert stored_rows[0]["run_id"].startswith(module.RUN_ID_FINGERPRINT_PREFIX)


def test_dedupe_mixed_batch_writes_only_new_records(tmp_path: Path) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)
    module.append_record_atomic(
        repo_dir,
        {
            "experiment": "ATLAS",
            "run_id": "run-existing",
            "timestamp": "2026-02-04T00:00:00Z",
            "payload": {"source": "existing"},
        },
    )

    summary = module.ingest(
        str(repo_dir),
        [
            {
                "experiment": "ATLAS",
                "run_id": "run-existing",
                "timestamp": "2026-02-04T00:00:01Z",
                "payload": {"source": "duplicate-existing"},
            },
            {
                "experiment": "ATLAS",
                "run_id": "run-new-a",
                "timestamp": "2026-02-04T00:00:02Z",
                "payload": {"source": "new-a-first"},
            },
            {
                "experiment": "ATLAS",
                "run_id": "run-new-a",
                "timestamp": "2026-02-04T00:00:03Z",
                "payload": {"source": "new-a-duplicate"},
            },
            {
                "experiment": "ATLAS",
                "run_id": "run-new-b",
                "timestamp": "2026-02-04T00:00:04Z",
                "payload": {"source": "new-b"},
            },
        ],
    )

    stored_rows = list(module.read_records(repo_dir))
    assert summary["inserted"] == 2
    assert summary["skipped_existing"] == 1
    assert summary["skipped_batch"] == 1
    assert [record["run_id"] for record in stored_rows] == [
        "run-existing",
        "run-new-a",
        "run-new-b",
    ]


def test_query_filters_when_range_and_exact_conflict_then_returns_validation_error(
    tmp_path: Path,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)

    with pytest.raises(ValueError, match="expected YYYY-MM-DD"):
        module.query(repo_dir, date="2026-01-01..2026-01-31")

    assert list(module.read_records(repo_dir)) == []


def test_query_filters_when_unknown_filter_key_then_returns_invalid_input_error(
    tmp_path: Path,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)

    with pytest.raises(TypeError):
        module.query(repo_dir, unknown_filter="muon")

    assert list(module.read_records(repo_dir)) == []


def test_query_filters_when_filter_value_type_is_invalid_then_returns_invalid_input_error(
    tmp_path: Path,
) -> None:
    module = _load_module()
    repo_dir = tmp_path / "repo"
    module.init_local_repository(repo_dir)

    with pytest.raises(TypeError, match="Invalid value for 'date'"):
        module.query(repo_dir, date=123)

    assert list(module.read_records(repo_dir)) == []


def test_cli_when_status_command_invoked_then_routes_and_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    parser = argparse.ArgumentParser(prog="cern-dataops")
    subparsers = parser.add_subparsers(dest="command_group", required=True)
    status_parser = subparsers.add_parser("status")
    status_parser.set_defaults(
        command_id=module.COMMAND_ID_CONFIG_SHOW,
        config=str(tmp_path / "config.toml"),
    )

    observed = {"called": False}

    def _fake_run_config_show(_config) -> int:
        observed["called"] = True
        return 0

    monkeypatch.setattr(module, "build_parser", lambda: parser)
    monkeypatch.setattr(module, "load_app_config", lambda _config_path: object())
    monkeypatch.setattr(module, "_run_config_show", _fake_run_config_show)

    exit_code = module.main(["status"])

    assert exit_code == 0
    assert observed["called"] is True


def test_cli_when_query_command_invoked_then_routes_and_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    parser = argparse.ArgumentParser(prog="cern-dataops")
    subparsers = parser.add_subparsers(dest="command_group", required=True)
    query_parser = subparsers.add_parser("query")
    query_parser.set_defaults(
        command_id=module.COMMAND_ID_DATASET_LIST,
        config=str(tmp_path / "config.toml"),
    )

    observed = {"called": False}

    def _fake_run_dataset_list(_config) -> int:
        observed["called"] = True
        return 0

    monkeypatch.setattr(module, "build_parser", lambda: parser)
    monkeypatch.setattr(module, "load_app_config", lambda _config_path: object())
    monkeypatch.setattr(module, "_run_dataset_list", _fake_run_dataset_list)

    exit_code = module.main(["query"])

    assert exit_code == 0
    assert observed["called"] is True


def test_cli_when_unknown_command_invoked_then_exits_two() -> None:
    module = _load_module()

    assert module.main(["unknown"]) == 2


def test_readme_smoke_when_documented_invocation_runs_then_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()

    exit_code = module.main(["--help"])
    help_output = capsys.readouterr().out

    assert exit_code == 0
    assert "cern-dataops" in help_output


def test_cli_end_to_end_assistant_seed_ask_demo_round_trip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    seed_dir = tmp_path / "seed"

    seed_exit = module.main(["assistant", "seed", "--seed-dir", str(seed_dir)])
    seed_output = json.loads(capsys.readouterr().out.strip())

    ask_exit = module.main(
        [
            "assistant",
            "ask",
            "--seed-dir",
            str(seed_dir),
            "What is the deterministic dimuon demo path?",
        ]
    )
    ask_output = json.loads(capsys.readouterr().out.strip())

    demo_exit = module.main(["assistant", "demo", "--seed-dir", str(seed_dir)])
    demo_output = json.loads(capsys.readouterr().out.strip())

    assert seed_exit == 0
    assert seed_output["seed_version"] == "cms-run2-nanoaod-mvp-v1"
    assert ask_exit == 0
    assert "answer" in ask_output
    assert ask_output["intent"] == "dimuon_demo"
    assert demo_exit == 0
    assert demo_output["demo"]["dataset_recid"] == 30522
    assert demo_output["demo"]["subset_strategy"]["range"] == "1-3"
