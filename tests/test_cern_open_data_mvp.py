from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "cern_open_data_mvp.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("cern_open_data_mvp_under_test", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_knowledge_bundle_is_frozen_to_required_records_and_docs() -> None:
    module = _load_module()

    bundle = module.load_knowledge_bundle()
    recids = sorted(record["recid"] for record in bundle["records"])
    doc_urls = sorted(doc["url"] for doc in bundle["docs"])

    assert recids == [14220, 30522, 35671]
    assert len(doc_urls) == 4
    assert "https://opendata.cern.ch/docs/terms-of-use" in doc_urls
    assert "https://opendata.cern.ch/docs/cms-getting-started-nanoaod" in doc_urls


def test_seed_frozen_inputs_writes_deterministic_structured_files(tmp_path: Path) -> None:
    module = _load_module()
    seed_dir = tmp_path / "seed"

    first = module.seed_frozen_inputs(seed_dir)
    second = module.seed_frozen_inputs(seed_dir)

    manifest_path = seed_dir / "manifest.json"
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert first["seed_version"] == module.SEED_VERSION
    assert second["seed_version"] == module.SEED_VERSION
    assert sorted(first["frozen_record_ids"]) == [14220, 30522, 35671]
    assert manifest_payload["seed_version"] == module.SEED_VERSION
    assert sorted(manifest_payload["files"].keys()) == [
        "command_templates",
        "dimuon_demo",
        "docs",
        "records",
        "seed_process",
    ]


def test_build_structured_response_returns_required_schema_and_templates(tmp_path: Path) -> None:
    module = _load_module()
    seed_dir = tmp_path / "seed"
    module.seed_frozen_inputs(seed_dir)

    response = module.build_structured_response(
        "Generate deterministic cernopendata-client commands for xrootd access.",
        seed_dir,
    )

    assert all(field in response for field in module.REQUIRED_RESPONSE_FIELDS)
    assert response["intent"] in {
        "client_command",
        "xrootd_access",
    }
    assert response["access_recipe"]["metadata_lookup"]
    assert response["access_recipe"]["file_location_lookup"]
    assert response["access_recipe"]["xrootd_access"]
    assert "docker run --rm -it" in response["environment"]["docker_startup"]


def test_validated_json_question_references_record_14220(tmp_path: Path) -> None:
    module = _load_module()
    seed_dir = tmp_path / "seed"
    module.seed_frozen_inputs(seed_dir)

    response = module.build_structured_response(
        "Do I need validated JSON for this collision analysis?",
        seed_dir,
    )

    recids = [record["recid"] for record in response["recommended_datasets"]]

    assert response["intent"] == "validated_json"
    assert 14220 in recids
    assert response["provenance"]["validated_json_record"]["recid"] == 14220


def test_evaluation_suite_is_exactly_20_questions_and_runs(tmp_path: Path) -> None:
    module = _load_module()
    seed_dir = tmp_path / "seed"
    module.seed_frozen_inputs(seed_dir)

    questions = module.load_evaluation_questions()
    result = module.run_evaluation(seed_dir)

    assert len(questions) == 20
    assert result["total_questions"] == 20
    assert result["passed"] + result["failed"] == 20


def test_dimuon_demo_is_deterministic_three_file_path(tmp_path: Path) -> None:
    module = _load_module()
    seed_dir = tmp_path / "seed"
    module.seed_frozen_inputs(seed_dir)

    demo = module.get_dimuon_demo(seed_dir)

    assert demo["demo"]["dataset_recid"] == 30522
    assert demo["demo"]["validated_json_recid"] == 14220
    assert demo["demo"]["subset_strategy"]["range"] == "1-3"
    assert any("--filter-range 1-3" in cmd for cmd in demo["commands"]["xrootd_access"])
