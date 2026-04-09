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
    assert sorted(manifest_payload["generated_files"].keys()) == [
        "command_catalog",
        "command_templates",
        "demo_linkage",
        "dimuon_demo",
        "docs",
        "docs_passage_index",
        "records",
        "seed_process",
    ]
    assert sorted(manifest_payload["source_assets"].keys()) == [
        "demo",
        "doc_passages",
        "docs",
        "record_details",
        "records",
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


def test_evidence_entries_are_auditable_and_source_typed(tmp_path: Path) -> None:
    module = _load_module()
    seed_dir = tmp_path / "seed"
    module.seed_frozen_inputs(seed_dir)

    response = module.build_structured_response(
        "Show provenance and command evidence for this CMS NanoAOD assistant.",
        seed_dir,
    )

    evidence = response["evidence"]
    assert evidence
    for item in evidence:
        assert item["source_type"] in {"record_field", "doc_passage"}
        assert isinstance(item["source_id"], str)
        assert isinstance(item["url"], str)
        assert isinstance(item["locator"], str)
        assert isinstance(item["claim"], str)
    assert any(item["source_type"] == "record_field" for item in evidence)
    assert any(item["source_type"] == "doc_passage" for item in evidence)


def test_doi_and_citation_response_contains_frozen_doi_values(tmp_path: Path) -> None:
    module = _load_module()
    seed_dir = tmp_path / "seed"
    module.seed_frozen_inputs(seed_dir)

    response = module.build_structured_response(
        "Give me DOI and citation details for collision and MC records.",
        seed_dir,
    )

    citations = response["license_and_citation"]["citations"]
    dois = {entry["recid"]: entry["doi"] for entry in citations if isinstance(entry, dict)}

    assert dois[30522] == "10.7483/OPENDATA.CMS.ZQS3.LGLP"
    assert dois[35671] == "10.7483/OPENDATA.CMS.CRNB.POY1"


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
    assert "14220" in json.dumps(response["provenance"], ensure_ascii=False)


def test_xrootd_response_is_bounded_and_not_full_download_default(tmp_path: Path) -> None:
    module = _load_module()
    seed_dir = tmp_path / "seed"
    module.seed_frozen_inputs(seed_dir)

    response = module.build_structured_response(
        "Give me XRootD access commands without downloading everything.",
        seed_dir,
    )

    assert response["intent"] == "xrootd_access"
    assert any("--protocol xrootd" in command for command in response["access_recipe"]["xrootd_access"])
    assert any("--filter-range 1-3" in command for command in response["access_recipe"]["xrootd_access"])
    assert any("full dataset" in caveat.lower() for caveat in response["caveats"])


def test_docs_retrieval_adds_official_doc_passage_evidence(tmp_path: Path) -> None:
    module = _load_module()
    seed_dir = tmp_path / "seed"
    module.seed_frozen_inputs(seed_dir)

    response = module.build_structured_response(
        "What official docs support Docker and cernopendata-client usage?",
        seed_dir,
    )

    doc_evidence = [item for item in response["evidence"] if item["source_type"] == "doc_passage"]
    assert doc_evidence
    assert any("opendata.cern.ch/docs" in item["url"] or "readthedocs.io" in item["url"] for item in doc_evidence)


def test_command_catalog_doc_origins_store_real_passage_quotes(tmp_path: Path) -> None:
    module = _load_module()
    seed_dir = tmp_path / "seed"
    module.seed_frozen_inputs(seed_dir)

    command_catalog = json.loads((seed_dir / "command_catalog.json").read_text(encoding="utf-8"))
    doc_origins = [
        origin
        for command in command_catalog
        for origin in command.get("origins", [])
        if isinstance(origin, dict) and origin.get("source_type") == "doc_passage"
    ]

    assert doc_origins
    for origin in doc_origins:
        quote = origin.get("quote")
        locator = origin.get("locator")
        assert isinstance(quote, str)
        assert quote.strip()
        assert " " in quote
        assert quote != locator
        assert ":" in str(locator)
        assert quote != str(origin.get("source_id", "")).split("doc:")[-1] + ":" + str(locator).split(":")[-1]
        assert isinstance(origin.get("section"), str)
        assert origin["section"].strip()


def test_command_attribution_in_ask_contains_real_doc_quotes(tmp_path: Path) -> None:
    module = _load_module()
    seed_dir = tmp_path / "seed"
    module.seed_frozen_inputs(seed_dir)

    response = module.build_structured_response(
        "Give me XRootD access commands without downloading everything.",
        seed_dir,
    )

    command_attribution = response["access_recipe"]["command_attribution"]
    doc_origins = [
        origin
        for command in command_attribution
        for origin in command.get("origins", [])
        if isinstance(origin, dict) and origin.get("source_type") == "doc_passage"
    ]

    assert doc_origins
    for origin in doc_origins:
        quote = origin.get("quote")
        locator = origin.get("locator")
        assert isinstance(quote, str)
        assert quote.strip()
        assert " " in quote
        assert quote != locator
        assert isinstance(origin.get("url"), str)
        assert "http" in origin["url"]


def test_readme_states_frozen_local_curated_assets_and_no_live_fetch() -> None:
    readme_text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    lowered = readme_text.lower()

    assert "frozen local curated source assets" in lowered
    assert "no live cern api calls are performed during assistant responses" in lowered
    assert "no live documentation fetching is performed during assistant responses" in lowered
    assert "live ingestion" not in lowered


def test_evaluation_suite_is_exactly_20_questions_and_runs(tmp_path: Path) -> None:
    module = _load_module()
    seed_dir = tmp_path / "seed"
    module.seed_frozen_inputs(seed_dir)

    questions = module.load_evaluation_questions()
    result = module.run_evaluation(seed_dir)

    assert len(questions) == 20
    assert result["total_questions"] == 20
    assert result["passed"] + result["failed"] == 20
    assert result["failed"] == 0


def test_dimuon_demo_is_deterministic_three_file_path(tmp_path: Path) -> None:
    module = _load_module()
    seed_dir = tmp_path / "seed"
    module.seed_frozen_inputs(seed_dir)

    demo = module.get_dimuon_demo(seed_dir)

    assert demo["demo"]["dataset_recid"] == 30522
    assert demo["demo"]["validated_json_recid"] == 14220
    assert demo["demo"]["subset_strategy"]["range"] == "1-3"
    assert any("--filter-range 1-3" in cmd for cmd in demo["commands"]["xrootd_access"])
