"""Metadata-first CERN Open Data MVP assistant for CMS Run 2 NanoAOD.

This module intentionally freezes the product scope to:
- collision dataset record 30522
- MC dataset record 35671
- validated JSON record 14220
- official docs corpus listed in knowledge/official_docs.json
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

FROZEN_RECORD_IDS = (14220, 30522, 35671)
REQUIRED_RESPONSE_FIELDS = (
    "answer",
    "intent",
    "recommended_datasets",
    "provenance",
    "environment",
    "access_recipe",
    "license_and_citation",
    "evidence",
    "caveats",
)

DEFAULT_SEED_DIR = pathlib.Path("data") / "cms_run2_nanoaod_mvp"
DEFAULT_KNOWLEDGE_DIR = pathlib.Path("knowledge")
DEFAULT_EVAL_QUESTIONS = pathlib.Path("evaluations") / "cms_run2_nanoaod_eval_questions.json"
SEED_VERSION = "cms-run2-nanoaod-mvp-v1"

RECORD_DETAILS_FILENAME = "frozen_record_details.json"
DOC_PASSAGES_FILENAME = "official_docs_passages.json"

DOI_BY_RECID = {
    30522: "10.7483/OPENDATA.CMS.ZQS3.LGLP",
    35671: "10.7483/OPENDATA.CMS.CRNB.POY1",
}

INTENT_DOC_HINTS = {
    "dataset_discovery": ["cms_nanoaod_getting_started", "cernopendata_client_docs"],
    "provenance": ["cms_nanoaod_getting_started", "cernopendata_client_docs"],
    "doi_citation": ["terms_of_use"],
    "license": ["terms_of_use"],
    "docker_environment": ["cms_docker_guide", "cms_nanoaod_getting_started"],
    "xrootd_access": ["cernopendata_client_docs", "cms_nanoaod_getting_started"],
    "client_command": ["cernopendata_client_docs"],
    "validated_json": ["cms_nanoaod_getting_started"],
    "dimuon_demo": ["cms_nanoaod_getting_started", "cernopendata_client_docs"],
    "docs_discovery": [
        "terms_of_use",
        "cms_nanoaod_getting_started",
        "cms_docker_guide",
        "cernopendata_client_docs",
    ],
    "general_assistant": [
        "terms_of_use",
        "cms_nanoaod_getting_started",
        "cms_docker_guide",
        "cernopendata_client_docs",
    ],
}

INTENT_KEYWORDS = {
    "dataset_discovery": {"dataset", "discover", "recommend", "collision", "mc"},
    "provenance": {"provenance", "lineage", "origin", "global", "tag", "cmssw"},
    "doi_citation": {"doi", "cite", "citation"},
    "license": {"license", "terms", "cc0", "endorse"},
    "docker_environment": {"docker", "container", "environment", "cmssw"},
    "xrootd_access": {"xrootd", "root://", "xrdcp", "file", "locations", "download"},
    "client_command": {"command", "get-metadata", "get-file-locations", "download-files", "cernopendata-client"},
    "validated_json": {"validated", "json", "lumisection", "good", "run", "14220"},
    "dimuon_demo": {"dimuon", "invariant", "mass", "three-file", "subset", "demo"},
}


def _repo_root() -> pathlib.Path:
    """Return repository root from the src module location."""
    return pathlib.Path(__file__).resolve().parents[1]


def _load_json(path: pathlib.Path) -> Any:
    """Load one JSON file with deterministic error messaging."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Required file not found: '{path}'.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in '{path}': {exc}.") from exc


def _json_dumps(payload: Any) -> str:
    """Serialize JSON deterministically."""
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _sha256_path(path: pathlib.Path) -> str:
    """Hash one file deterministically for seed manifests."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize(text: str) -> str:
    """Normalize input text for deterministic matching."""
    return " ".join(text.strip().lower().split())


def _normalized_words(text: str) -> set[str]:
    """Split normalized text into deterministic word tokens."""
    cleaned = _normalize(text)
    for token in [",", ".", ":", ";", "(", ")", "[", "]", "\"", "'", "?", "!"]:
        cleaned = cleaned.replace(token, " ")
    return {part for part in cleaned.split() if part}


def _records_by_recid(records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Index records by integer recid."""
    indexed: dict[int, dict[str, Any]] = {}
    for record in records:
        recid = record.get("recid")
        if not isinstance(recid, int):
            raise ValueError("Each frozen record must define an integer 'recid'.")
        indexed[recid] = record
    return indexed


def load_knowledge_bundle(knowledge_dir: str | pathlib.Path | None = None) -> dict[str, Any]:
    """Load frozen records, docs corpus, and dimuon demo definitions."""
    base_dir = _repo_root() / DEFAULT_KNOWLEDGE_DIR if knowledge_dir is None else pathlib.Path(knowledge_dir)
    records_path = base_dir / "frozen_records.json"
    docs_path = base_dir / "official_docs.json"
    demo_path = base_dir / "dimuon_demo.json"
    details_path = base_dir / RECORD_DETAILS_FILENAME
    doc_passages_path = base_dir / DOC_PASSAGES_FILENAME

    records = _load_json(records_path)
    docs = _load_json(docs_path)
    demo = _load_json(demo_path)
    record_details = _load_json(details_path)
    doc_passages = _load_json(doc_passages_path)

    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("knowledge/frozen_records.json must contain a JSON list of objects.")
    if not isinstance(docs, list) or not all(isinstance(item, dict) for item in docs):
        raise ValueError("knowledge/official_docs.json must contain a JSON list of objects.")
    if not isinstance(demo, dict):
        raise ValueError("knowledge/dimuon_demo.json must contain a JSON object.")
    if not isinstance(record_details, dict):
        raise ValueError(f"knowledge/{RECORD_DETAILS_FILENAME} must contain a JSON object.")
    if not isinstance(doc_passages, list) or not all(isinstance(item, dict) for item in doc_passages):
        raise ValueError(f"knowledge/{DOC_PASSAGES_FILENAME} must contain a JSON list of objects.")

    record_ids = tuple(sorted(item.get("recid") for item in records))
    if record_ids != FROZEN_RECORD_IDS:
        raise ValueError(
            "Frozen record set mismatch. Expected recids "
            f"{FROZEN_RECORD_IDS}, got {record_ids}."
        )

    detail_keys = tuple(sorted(int(key) for key in record_details.keys()))
    if detail_keys != FROZEN_RECORD_IDS:
        raise ValueError(
            f"knowledge/{RECORD_DETAILS_FILENAME} must contain keys {FROZEN_RECORD_IDS}, got {detail_keys}."
        )

    doc_ids = {doc.get("doc_id") for doc in docs}
    if not all(isinstance(value, str) for value in doc_ids):
        raise ValueError("Each official docs entry must include string doc_id.")

    for passage_group in doc_passages:
        doc_id = passage_group.get("doc_id")
        if doc_id not in doc_ids:
            raise ValueError(f"Unknown doc_id '{doc_id}' in {DOC_PASSAGES_FILENAME}.")
        passages = passage_group.get("passages")
        if not isinstance(passages, list) or not passages:
            raise ValueError(f"Doc '{doc_id}' must include non-empty passages list.")

    return {
        "knowledge_dir": str(base_dir.resolve()),
        "records": records,
        "docs": docs,
        "demo": demo,
        "record_details": record_details,
        "doc_passages": doc_passages,
        "source_paths": {
            "records": str(records_path),
            "docs": str(docs_path),
            "demo": str(demo_path),
            "record_details": str(details_path),
            "doc_passages": str(doc_passages_path),
        },
    }


def _deep_get(payload: dict[str, Any], locator: str) -> Any:
    """Resolve a dotted locator from nested dictionaries."""
    current: Any = payload
    for part in locator.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _normalize_records(records: list[dict[str, Any]], record_details: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize frozen records with field-level provenance mapping."""
    normalized: list[dict[str, Any]] = []

    for base in sorted(records, key=lambda item: int(item.get("recid", 0))):
        recid = int(base["recid"])
        detail = record_details[str(recid)]
        detail_record = detail.get("record", {}) if isinstance(detail.get("record"), dict) else {}

        identity = {
            "recid": recid,
            "record_url": detail_record.get("url", base.get("record_url")),
            "dataset_path": base.get("dataset_path"),
            "title": detail_record.get("title", base.get("title")),
            "doi": detail_record.get("doi", base.get("doi")),
            "modality": base.get("modality"),
            "experiment": base.get("experiment"),
            "center_of_mass": base.get("center_of_mass"),
            "year_recorded": detail_record.get("data_recorded", base.get("year_recorded")),
            "year_published": detail_record.get("data_published", base.get("year_published")),
        }

        if base.get("run_range"):
            identity["run_range"] = base.get("run_range")
        elif detail_record.get("run_range"):
            identity["run_range"] = detail_record.get("run_range")

        dataset_characteristics = detail.get("dataset_characteristics")
        if not isinstance(dataset_characteristics, dict):
            dataset_characteristics = {
                "events": base.get("events"),
                "files": base.get("files"),
                "total_size": base.get("size"),
                "file_format": None,
            }

        validated_json = {
            "required_record": base.get("requires_validated_json_recid"),
            "validated_json_file_url": None,
            "requirement_statement": None,
            "luminosity_fields_for_filtering": [],
        }
        if isinstance(detail.get("validated_runs_requirement"), dict):
            validated_json["required_record"] = detail["validated_runs_requirement"].get(
                "required_record",
                validated_json["required_record"],
            )
            validated_json["validated_json_file_url"] = detail["validated_runs_requirement"].get(
                "validated_json_file_url"
            )
            validated_json["requirement_statement"] = detail["validated_runs_requirement"].get(
                "requirement_statement"
            )
        if recid == 14220:
            validated_json["validated_json_file_url"] = detail.get("validated_json_file_url")
            validated_json["requirement_statement"] = detail.get("validation_statement")
            lumifields = detail.get("luminosity_fields_for_filtering")
            if isinstance(lumifields, list):
                validated_json["luminosity_fields_for_filtering"] = list(lumifields)

        machine_access_endpoints = {
            "json_export": detail_record.get("json_export"),
            "api_record": detail_record.get("api_record"),
        }

        container_recommendation = detail.get("container_recommendation")
        if not isinstance(container_recommendation, dict):
            container_recommendation = {
                "recommended_images": list(base.get("recommended_images", [])),
                "reproducible_python_image": None,
            }

        license_and_citation = detail.get("license_and_citation")
        if not isinstance(license_and_citation, dict):
            license_and_citation = {
                "license": base.get("license"),
                "cite_as": None,
                "disclaimer_note": None,
            }

        processing_provenance = detail.get("processing_provenance")
        if not isinstance(processing_provenance, dict):
            processing_provenance = {"steps": []}

        normalized.append(
            {
                "recid": recid,
                "identity": identity,
                "dataset_characteristics": dataset_characteristics,
                "processing_provenance": processing_provenance,
                "validated_json": validated_json,
                "container_recommendation": container_recommendation,
                "license_and_citation": license_and_citation,
                "machine_access_endpoints": machine_access_endpoints,
                "source_map": {
                    "identity.doi": {
                        "source_id": f"record:{recid}",
                        "url": identity.get("record_url"),
                        "locator": "doi",
                    },
                    "identity.title": {
                        "source_id": f"record:{recid}",
                        "url": identity.get("record_url"),
                        "locator": "title",
                    },
                    "identity.dataset_path": {
                        "source_id": f"record:{recid}",
                        "url": identity.get("record_url"),
                        "locator": "dataset_path",
                    },
                    "dataset_characteristics.events": {
                        "source_id": f"record:{recid}",
                        "url": identity.get("record_url"),
                        "locator": "dataset_characteristics.events",
                    },
                    "dataset_characteristics.files": {
                        "source_id": f"record:{recid}",
                        "url": identity.get("record_url"),
                        "locator": "dataset_characteristics.files",
                    },
                    "dataset_characteristics.total_size": {
                        "source_id": f"record:{recid}",
                        "url": identity.get("record_url"),
                        "locator": "dataset_characteristics.total_size",
                    },
                    "validated_json.required_record": {
                        "source_id": f"record:{recid}",
                        "url": identity.get("record_url"),
                        "locator": "validated_json.required_record",
                    },
                    "validated_json.validated_json_file_url": {
                        "source_id": f"record:{recid}",
                        "url": identity.get("record_url"),
                        "locator": "validated_json.validated_json_file_url",
                    },
                    "container_recommendation.recommended_images": {
                        "source_id": f"record:{recid}",
                        "url": identity.get("record_url"),
                        "locator": "container_recommendation.recommended_images",
                    },
                    "container_recommendation.reproducible_python_image": {
                        "source_id": f"record:{recid}",
                        "url": identity.get("record_url"),
                        "locator": "container_recommendation.reproducible_python_image",
                    },
                    "license_and_citation.license": {
                        "source_id": f"record:{recid}",
                        "url": identity.get("record_url"),
                        "locator": "license_and_citation.license",
                    },
                    "license_and_citation.cite_as": {
                        "source_id": f"record:{recid}",
                        "url": identity.get("record_url"),
                        "locator": "license_and_citation.cite_as",
                    },
                    "machine_access_endpoints.json_export": {
                        "source_id": f"record:{recid}",
                        "url": identity.get("record_url"),
                        "locator": "machine_access_endpoints.json_export",
                    },
                    "machine_access_endpoints.api_record": {
                        "source_id": f"record:{recid}",
                        "url": identity.get("record_url"),
                        "locator": "machine_access_endpoints.api_record",
                    },
                },
            }
        )

    return normalized


def _normalize_docs(
    docs: list[dict[str, Any]],
    doc_passages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize official docs into passage-level store and flat index."""
    passages_by_doc: dict[str, list[dict[str, Any]]] = {}
    for group in doc_passages:
        doc_id = group.get("doc_id")
        if not isinstance(doc_id, str):
            continue
        group_passages = group.get("passages")
        if not isinstance(group_passages, list):
            continue
        normalized_group: list[dict[str, Any]] = []
        for index, passage in enumerate(group_passages):
            if not isinstance(passage, dict):
                continue
            passage_id = passage.get("passage_id")
            if not isinstance(passage_id, str):
                passage_id = f"{doc_id}:p{index + 1}"
            text = passage.get("text")
            section = passage.get("section")
            keywords = passage.get("keywords")
            if not isinstance(text, str) or not isinstance(section, str):
                continue
            if not isinstance(keywords, list):
                keywords = []
            normalized_group.append(
                {
                    "passage_id": passage_id,
                    "section": section,
                    "text": text,
                    "keywords": [str(keyword).lower() for keyword in keywords],
                }
            )
        passages_by_doc[doc_id] = normalized_group

    normalized_docs: list[dict[str, Any]] = []
    flat_index: list[dict[str, Any]] = []
    for doc in sorted(docs, key=lambda value: str(value.get("doc_id", ""))):
        doc_id = doc.get("doc_id")
        if not isinstance(doc_id, str):
            continue
        title = doc.get("title")
        url = doc.get("url")
        evidence = doc.get("evidence")
        if not isinstance(title, str) or not isinstance(url, str):
            continue
        if not isinstance(evidence, list):
            evidence = []

        doc_passages_for_id = passages_by_doc.get(doc_id, [])
        normalized_docs.append(
            {
                "doc_id": doc_id,
                "title": title,
                "url": url,
                "summary_evidence": [str(item) for item in evidence if isinstance(item, str)],
                "passages": doc_passages_for_id,
            }
        )

        for passage in doc_passages_for_id:
            combined = " ".join(
                [
                    doc_id,
                    title,
                    passage.get("section", ""),
                    passage.get("text", ""),
                    " ".join(passage.get("keywords", [])),
                ]
            )
            flat_index.append(
                {
                    "doc_id": doc_id,
                    "title": title,
                    "url": url,
                    "passage_id": passage.get("passage_id"),
                    "section": passage.get("section"),
                    "text": passage.get("text"),
                    "keywords": passage.get("keywords", []),
                    "search_text": _normalize(combined),
                }
            )

    return normalized_docs, flat_index


def _get_record(records_by_recid: dict[int, dict[str, Any]], recid: int) -> dict[str, Any]:
    """Fetch one normalized record or raise deterministic error."""
    if recid not in records_by_recid:
        raise ValueError(f"Missing required normalized record {recid}.")
    return records_by_recid[recid]


def _format_template_with_map(template: str, mapping: dict[str, Any]) -> str:
    """Render deterministic command template values."""
    rendered = template
    for key, value in mapping.items():
        rendered = rendered.replace(f"{{{key}}}", str(value))
    return rendered


def _build_command_catalog(
    normalized_records: list[dict[str, Any]],
    normalized_docs: list[dict[str, Any]],
    demo: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build command templates with explicit metadata and docs attribution."""
    records_by_recid = _records_by_recid(normalized_records)
    collision = _get_record(records_by_recid, 30522)
    mc = _get_record(records_by_recid, 35671)
    _get_record(records_by_recid, 14220)
    doc_url_by_id = {
        doc.get("doc_id"): doc.get("url")
        for doc in normalized_docs
        if isinstance(doc, dict) and isinstance(doc.get("doc_id"), str) and isinstance(doc.get("url"), str)
    }

    collision_doi = _deep_get(collision, "identity.doi")
    mc_doi = _deep_get(mc, "identity.doi")
    docker_image = _deep_get(collision, "container_recommendation.reproducible_python_image")
    if not isinstance(docker_image, str) or not docker_image:
        docker_image = "gitlab-registry.cern.ch/cms-cloud/python-vnc:latest"

    subset_range = _deep_get(demo, "subset_strategy.range")
    if not isinstance(subset_range, str):
        subset_range = "1-3"

    command_specs = [
        {
            "id": "metadata_lookup_collision_recid",
            "family": "metadata_lookup",
            "template": "cernopendata-client get-metadata --recid {collision_recid}",
            "why": "Lookup frozen metadata for collision dataset record 30522.",
            "origin_refs": [
                {"type": "record_field", "recid": 30522, "locator": "identity.recid"},
                {"type": "doc_passage", "doc_id": "cernopendata_client_docs", "passage_id": "cernopendata_client_docs:p1"},
            ],
        },
        {
            "id": "metadata_lookup_mc_recid",
            "family": "metadata_lookup",
            "template": "cernopendata-client get-metadata --recid {mc_recid}",
            "why": "Lookup frozen metadata for MC dataset record 35671.",
            "origin_refs": [
                {"type": "record_field", "recid": 35671, "locator": "identity.recid"},
                {"type": "doc_passage", "doc_id": "cernopendata_client_docs", "passage_id": "cernopendata_client_docs:p1"},
            ],
        },
        {
            "id": "metadata_lookup_validated_json_recid",
            "family": "metadata_lookup",
            "template": "cernopendata-client get-metadata --recid {validated_json_recid}",
            "why": "Lookup validated JSON metadata for collision quality requirements.",
            "origin_refs": [
                {"type": "record_field", "recid": 14220, "locator": "identity.recid"},
                {"type": "doc_passage", "doc_id": "cms_nanoaod_getting_started", "passage_id": "cms_nanoaod_getting_started:p2"},
            ],
        },
        {
            "id": "metadata_lookup_collision_doi",
            "family": "metadata_lookup",
            "template": "cernopendata-client get-metadata --doi {collision_doi}",
            "why": "Resolve collision metadata by DOI for citation workflows.",
            "origin_refs": [
                {"type": "record_field", "recid": 30522, "locator": "identity.doi"},
                {"type": "doc_passage", "doc_id": "cernopendata_client_docs", "passage_id": "cernopendata_client_docs:p1"},
            ],
        },
        {
            "id": "metadata_lookup_mc_doi",
            "family": "metadata_lookup",
            "template": "cernopendata-client get-metadata --doi {mc_doi}",
            "why": "Resolve MC metadata by DOI for citation workflows.",
            "origin_refs": [
                {"type": "record_field", "recid": 35671, "locator": "identity.doi"},
                {"type": "doc_passage", "doc_id": "cernopendata_client_docs", "passage_id": "cernopendata_client_docs:p1"},
            ],
        },
        {
            "id": "file_location_lookup_collision",
            "family": "file_location_lookup",
            "template": "cernopendata-client get-file-locations --recid {collision_recid} --protocol xrootd",
            "why": "List XRootD file endpoints for collision dataset 30522.",
            "origin_refs": [
                {"type": "record_field", "recid": 30522, "locator": "identity.recid"},
                {"type": "doc_passage", "doc_id": "cernopendata_client_docs", "passage_id": "cernopendata_client_docs:p2"},
            ],
        },
        {
            "id": "file_location_lookup_mc",
            "family": "file_location_lookup",
            "template": "cernopendata-client get-file-locations --recid {mc_recid} --protocol xrootd",
            "why": "List XRootD file endpoints for MC dataset 35671.",
            "origin_refs": [
                {"type": "record_field", "recid": 35671, "locator": "identity.recid"},
                {"type": "doc_passage", "doc_id": "cernopendata_client_docs", "passage_id": "cernopendata_client_docs:p2"},
            ],
        },
        {
            "id": "xrootd_subset_download",
            "family": "xrootd_access",
            "template": "cernopendata-client download-files --recid {collision_recid} --protocol xrootd --dry-run --filter-range {subset_range}",
            "why": "Keep access bounded to deterministic three-file subset for MVP demo.",
            "origin_refs": [
                {"type": "record_field", "recid": 30522, "locator": "identity.recid"},
                {"type": "doc_passage", "doc_id": "cernopendata_client_docs", "passage_id": "cernopendata_client_docs:p3"},
                {"type": "doc_passage", "doc_id": "cms_nanoaod_getting_started", "passage_id": "cms_nanoaod_getting_started:p3"},
            ],
        },
        {
            "id": "xrootd_subset_listing",
            "family": "xrootd_access",
            "template": "cernopendata-client get-file-locations --recid {collision_recid} --protocol xrootd | sed -n '1,3p'",
            "why": "Expose deterministic first-three file list without full download default.",
            "origin_refs": [
                {"type": "record_field", "recid": 30522, "locator": "identity.recid"},
                {"type": "doc_passage", "doc_id": "cernopendata_client_docs", "passage_id": "cernopendata_client_docs:p2"},
                {"type": "doc_passage", "doc_id": "cms_nanoaod_getting_started", "passage_id": "cms_nanoaod_getting_started:p3"},
            ],
        },
        {
            "id": "docker_startup",
            "family": "docker_startup",
            "template": "docker run --rm -it -P -p 5901:5901 -p 6080:6080 -p 8888:8888 {docker_image}",
            "why": "Start reproducible CMS NanoAOD analysis environment from pinned image.",
            "origin_refs": [
                {"type": "record_field", "recid": 30522, "locator": "container_recommendation.reproducible_python_image"},
                {"type": "doc_passage", "doc_id": "cms_docker_guide", "passage_id": "cms_docker_guide:p1"},
                {"type": "doc_passage", "doc_id": "cms_docker_guide", "passage_id": "cms_docker_guide:p3"},
            ],
        },
        {
            "id": "validated_json_metadata_lookup",
            "family": "validated_json_lookup",
            "template": "cernopendata-client get-metadata --recid {validated_json_recid}",
            "why": "Retrieve validated JSON record metadata required for collision quality masking.",
            "origin_refs": [
                {"type": "record_field", "recid": 14220, "locator": "identity.recid"},
                {"type": "doc_passage", "doc_id": "cms_nanoaod_getting_started", "passage_id": "cms_nanoaod_getting_started:p2"},
            ],
        },
        {
            "id": "validated_json_file_lookup",
            "family": "validated_json_lookup",
            "template": "cernopendata-client get-file-locations --recid {validated_json_recid}",
            "why": "Retrieve validated JSON file location for masking run/lumisection ranges.",
            "origin_refs": [
                {"type": "record_field", "recid": 14220, "locator": "validated_json.validated_json_file_url"},
                {"type": "doc_passage", "doc_id": "cms_nanoaod_getting_started", "passage_id": "cms_nanoaod_getting_started:p2"},
            ],
        },
    ]

    mapping = {
        "collision_recid": 30522,
        "mc_recid": 35671,
        "validated_json_recid": 14220,
        "collision_doi": collision_doi,
        "mc_doi": mc_doi,
        "subset_range": subset_range,
        "docker_image": docker_image,
    }

    catalog: list[dict[str, Any]] = []
    for spec in command_specs:
        rendered = _format_template_with_map(spec["template"], mapping)
        origins: list[dict[str, Any]] = []
        for origin in spec["origin_refs"]:
            if origin["type"] == "record_field":
                recid = int(origin["recid"])
                locator = str(origin["locator"])
                record = _get_record(records_by_recid, recid)
                record_url = _deep_get(record, "identity.record_url")
                quote_value = _deep_get(record, locator)
                origins.append(
                    {
                        "source_type": "record_field",
                        "source_id": f"record:{recid}",
                        "url": record_url,
                        "locator": locator,
                        "quote": json.dumps(quote_value, ensure_ascii=False)
                        if isinstance(quote_value, (dict, list))
                        else str(quote_value),
                    }
                )
            elif origin["type"] == "doc_passage":
                doc_id = str(origin["doc_id"])
                passage_id = str(origin["passage_id"])
                origins.append(
                    {
                        "source_type": "doc_passage",
                        "source_id": f"doc:{doc_id}",
                        "url": doc_url_by_id.get(doc_id),
                        "locator": passage_id,
                        "quote": passage_id,
                    }
                )

        catalog.append(
            {
                "id": spec["id"],
                "family": spec["family"],
                "template": spec["template"],
                "command": rendered,
                "why": spec["why"],
                "origins": origins,
            }
        )

    return catalog


def build_command_templates(records: list[dict[str, Any]]) -> dict[str, list[str] | str]:
    """Generate deterministic command templates from frozen metadata."""
    indexed = _records_by_recid(records)
    collision_doi = _deep_get(indexed[30522], "identity.doi") or indexed[30522].get("doi")
    mc_doi = _deep_get(indexed[35671], "identity.doi") or indexed[35671].get("doi")
    docker_image = _deep_get(indexed[30522], "container_recommendation.reproducible_python_image")
    if not isinstance(docker_image, str) or not docker_image:
        docker_image = "gitlab-registry.cern.ch/cms-cloud/python-vnc:latest"

    return {
        "metadata_lookup": [
            "cernopendata-client get-metadata --recid 30522",
            "cernopendata-client get-metadata --recid 35671",
            "cernopendata-client get-metadata --recid 14220",
            f"cernopendata-client get-metadata --doi {collision_doi}",
            f"cernopendata-client get-metadata --doi {mc_doi}",
        ],
        "file_location_lookup": [
            "cernopendata-client get-file-locations --recid 30522 --protocol xrootd",
            "cernopendata-client get-file-locations --recid 35671 --protocol xrootd",
        ],
        "xrootd_access": [
            "cernopendata-client download-files --recid 30522 --protocol xrootd --dry-run --filter-range 1-3",
            "cernopendata-client get-file-locations --recid 30522 --protocol xrootd | sed -n '1,3p'",
        ],
        "docker_startup": (
            "docker run --rm -it -P -p 5901:5901 -p 6080:6080 -p 8888:8888 "
            f"{docker_image}"
        ),
        "validated_json_lookup": [
            "cernopendata-client get-metadata --recid 14220",
            "cernopendata-client get-file-locations --recid 14220",
        ],
    }


def _build_demo_linkage(demo: dict[str, Any], records_by_recid: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Build explicit demo linkage to frozen records and validated JSON."""
    collision = _get_record(records_by_recid, 30522)
    mc = _get_record(records_by_recid, 35671)
    validated = _get_record(records_by_recid, 14220)

    return {
        "demo_id": demo.get("demo_id"),
        "dataset_recid": demo.get("dataset_recid"),
        "mc_recid": demo.get("mc_recid"),
        "validated_json_recid": demo.get("validated_json_recid"),
        "subset_strategy": demo.get("subset_strategy"),
        "linked_records": [
            {
                "recid": 30522,
                "title": _deep_get(collision, "identity.title"),
                "record_url": _deep_get(collision, "identity.record_url"),
            },
            {
                "recid": 35671,
                "title": _deep_get(mc, "identity.title"),
                "record_url": _deep_get(mc, "identity.record_url"),
            },
            {
                "recid": 14220,
                "title": _deep_get(validated, "identity.title"),
                "record_url": _deep_get(validated, "identity.record_url"),
                "validated_json_file_url": _deep_get(validated, "validated_json.validated_json_file_url"),
            },
        ],
    }


def _build_source_asset_hashes(source_paths: dict[str, str]) -> dict[str, dict[str, str]]:
    """Build deterministic hashes for frozen source assets used in seed."""
    output: dict[str, dict[str, str]] = {}
    for logical_name, raw_path in sorted(source_paths.items()):
        path = pathlib.Path(raw_path)
        output[logical_name] = {
            "path": str(path),
            "sha256": _sha256_path(path),
        }
    return output


def seed_frozen_inputs(seed_dir: str | pathlib.Path) -> dict[str, Any]:
    """Ingest frozen records/docs into deterministic structured seed files."""
    seed_root = pathlib.Path(seed_dir).expanduser().resolve()
    seed_root.mkdir(parents=True, exist_ok=True)

    bundle = load_knowledge_bundle()

    normalized_records = _normalize_records(bundle["records"], bundle["record_details"])
    normalized_docs, docs_passage_index = _normalize_docs(bundle["docs"], bundle["doc_passages"])
    records_by_recid = _records_by_recid(normalized_records)

    command_catalog = _build_command_catalog(normalized_records, normalized_docs, bundle["demo"])
    templates = build_command_templates(normalized_records)
    demo_linkage = _build_demo_linkage(bundle["demo"], records_by_recid)

    files_to_write = {
        "records": seed_root / "records.json",
        "docs": seed_root / "docs.json",
        "docs_passage_index": seed_root / "docs_passage_index.json",
        "command_templates": seed_root / "command_templates.json",
        "command_catalog": seed_root / "command_catalog.json",
        "dimuon_demo": seed_root / "dimuon_demo.json",
        "demo_linkage": seed_root / "demo_linkage.json",
        "seed_process": seed_root / "seed_process.json",
    }

    files_to_write["records"].write_text(_json_dumps(normalized_records), encoding="utf-8")
    files_to_write["docs"].write_text(_json_dumps(normalized_docs), encoding="utf-8")
    files_to_write["docs_passage_index"].write_text(_json_dumps(docs_passage_index), encoding="utf-8")
    files_to_write["command_templates"].write_text(_json_dumps(templates), encoding="utf-8")
    files_to_write["command_catalog"].write_text(_json_dumps(command_catalog), encoding="utf-8")
    files_to_write["dimuon_demo"].write_text(_json_dumps(bundle["demo"]), encoding="utf-8")
    files_to_write["demo_linkage"].write_text(_json_dumps(demo_linkage), encoding="utf-8")

    source_asset_hashes = _build_source_asset_hashes(bundle["source_paths"])
    files_to_write["seed_process"].write_text(
        _json_dumps(
            {
                "seed_version": SEED_VERSION,
                "scope": "CMS Run 2 NanoAOD only",
                "frozen_record_ids": list(FROZEN_RECORD_IDS),
                "docs_sources": [doc.get("url") for doc in normalized_docs],
                "deterministic": True,
                "source_assets": source_asset_hashes,
                "generated_artifacts": sorted(files_to_write.keys()),
                "validated_json_required_for_collision_record": {
                    "collision_recid": 30522,
                    "validated_json_recid": 14220,
                    "reason": "Collision NanoAOD workflows require validated run/lumisection filtering.",
                },
            }
        ),
        encoding="utf-8",
    )

    manifest_payload = {
        "seed_version": SEED_VERSION,
        "deterministic": True,
        "source_assets": source_asset_hashes,
        "generated_files": {
            logical_name: {
                "path": str(path),
                "sha256": _sha256_path(path),
            }
            for logical_name, path in sorted(files_to_write.items())
        },
    }
    manifest_path = seed_root / "manifest.json"
    manifest_path.write_text(_json_dumps(manifest_payload), encoding="utf-8")

    return {
        "seed_dir": str(seed_root),
        "manifest_path": str(manifest_path),
        "seed_version": SEED_VERSION,
        "frozen_record_ids": list(FROZEN_RECORD_IDS),
        "written_files": [str(path) for _, path in sorted(files_to_write.items())],
    }


def _load_seed(seed_dir: str | pathlib.Path) -> dict[str, Any]:
    """Load seed files, creating them deterministically if missing."""
    seed_root = pathlib.Path(seed_dir).expanduser().resolve()
    required = [
        seed_root / "records.json",
        seed_root / "docs.json",
        seed_root / "docs_passage_index.json",
        seed_root / "command_templates.json",
        seed_root / "command_catalog.json",
        seed_root / "dimuon_demo.json",
        seed_root / "demo_linkage.json",
        seed_root / "seed_process.json",
        seed_root / "manifest.json",
    ]
    if not all(path.exists() for path in required):
        seed_frozen_inputs(seed_root)

    return {
        "records": _load_json(seed_root / "records.json"),
        "docs": _load_json(seed_root / "docs.json"),
        "docs_passage_index": _load_json(seed_root / "docs_passage_index.json"),
        "command_templates": _load_json(seed_root / "command_templates.json"),
        "command_catalog": _load_json(seed_root / "command_catalog.json"),
        "dimuon_demo": _load_json(seed_root / "dimuon_demo.json"),
        "demo_linkage": _load_json(seed_root / "demo_linkage.json"),
        "seed_process": _load_json(seed_root / "seed_process.json"),
        "manifest": _load_json(seed_root / "manifest.json"),
        "seed_dir": str(seed_root),
    }


def classify_intent(question: str) -> str:
    """Classify user intent using deterministic keyword rules."""
    normalized = _normalize(question)

    if "structured answer" in normalized:
        return "general_assistant"
    if any(token in normalized for token in ("validated json", "good luminosity", "lumisection", "cert_", "14220")):
        return "validated_json"
    if (
        ("dimuon" in normalized and "demo" in normalized)
        or any(
            token in normalized
            for token in ("dimuon demo", "invariant mass", "invariant-mass", "three-file", "3-file", "demo flow")
        )
    ):
        return "dimuon_demo"
    if any(token in normalized for token in ("xrootd", "root://", "file locations", "file-location", "xrdcp")):
        return "xrootd_access"
    if any(token in normalized for token in ("docker", "container", "environment", "cmssw")):
        return "docker_environment"
    if any(
        token in normalized
        for token in ("cernopendata-client", "command", "metadata lookup", "download-files", "file-location lookup")
    ):
        return "client_command"
    if any(token in normalized for token in ("doi", "citation", "cite")):
        return "doi_citation"
    if any(token in normalized for token in ("license", "terms of use", "terms")):
        return "license"
    if any(token in normalized for token in ("provenance", "lineage", "origin")):
        return "provenance"
    if any(token in normalized for token in ("official docs", "documentation source", "sources")):
        return "docs_discovery"
    if any(token in normalized for token in ("dataset", "discover", "recommend", "collision", "mc")):
        return "dataset_discovery"
    return "general_assistant"


def _record_projection(record: dict[str, Any], reason: str) -> dict[str, Any]:
    """Project one record into the response recommendation schema."""
    return {
        "recid": record.get("recid"),
        "title": _deep_get(record, "identity.title"),
        "doi": _deep_get(record, "identity.doi"),
        "modality": _deep_get(record, "identity.modality"),
        "record_url": _deep_get(record, "identity.record_url"),
        "reason": reason,
    }


def _recommended_recids(intent: str) -> list[int]:
    """Return deterministic recommended record IDs per intent."""
    if intent in {"dataset_discovery", "provenance", "docs_discovery", "general_assistant"}:
        return [30522, 35671]
    if intent in {"validated_json", "dimuon_demo"}:
        return [30522, 14220, 35671]
    if intent in {"doi_citation", "license", "docker_environment", "xrootd_access", "client_command"}:
        return [30522, 35671, 14220]
    return [30522, 35671]


def _retrieve_doc_passages(
    intent: str,
    question: str,
    docs_passage_index: list[dict[str, Any]],
    *,
    max_results: int = 4,
) -> list[dict[str, Any]]:
    """Retrieve deterministic supporting passages from frozen docs corpus."""
    question_words = _normalized_words(question)
    intent_words = INTENT_KEYWORDS.get(intent, set())
    hint_doc_ids = set(INTENT_DOC_HINTS.get(intent, []))

    scored: list[tuple[int, dict[str, Any]]] = []
    for entry in docs_passage_index:
        doc_id = entry.get("doc_id")
        keywords = entry.get("keywords")
        text = entry.get("search_text")
        if not isinstance(doc_id, str) or not isinstance(text, str) or not isinstance(keywords, list):
            continue

        keyword_set = {str(keyword).lower() for keyword in keywords}
        search_words = _normalized_words(text)

        score = 0
        if doc_id in hint_doc_ids:
            score += 5
        score += len(question_words.intersection(keyword_set)) * 3
        score += len(intent_words.intersection(keyword_set)) * 2
        score += len(question_words.intersection(search_words))
        score += len(intent_words.intersection(search_words))

        if score > 0:
            scored.append((score, entry))

    scored.sort(
        key=lambda pair: (
            -pair[0],
            str(pair[1].get("doc_id", "")),
            str(pair[1].get("passage_id", "")),
        )
    )

    selected = [entry for _, entry in scored[:max_results]]
    if selected:
        return selected

    # Fallback to the first deterministic passage from hinted docs.
    fallback = [
        entry
        for entry in docs_passage_index
        if isinstance(entry.get("doc_id"), str) and entry.get("doc_id") in hint_doc_ids
    ]
    fallback.sort(key=lambda item: (str(item.get("doc_id", "")), str(item.get("passage_id", ""))))
    return fallback[:max_results]


def _stringify_quote(value: Any) -> str:
    """Return deterministic quote text for evidence values."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _append_record_evidence(
    evidence: list[dict[str, Any]],
    records_by_recid: dict[int, dict[str, Any]],
    recid: int,
    locator: str,
    claim: str,
) -> None:
    """Append one record-field evidence entry if value exists."""
    record = _get_record(records_by_recid, recid)
    value = _deep_get(record, locator)
    if value is None:
        return

    evidence.append(
        {
            "source_type": "record_field",
            "source_id": f"record:{recid}",
            "url": _deep_get(record, "identity.record_url"),
            "locator": locator,
            "claim": claim,
            "quote": _stringify_quote(value),
        }
    )


def _append_doc_evidence(evidence: list[dict[str, Any]], passages: list[dict[str, Any]]) -> None:
    """Append doc-passage evidence entries from retrieved passages."""
    for passage in passages:
        evidence.append(
            {
                "source_type": "doc_passage",
                "source_id": f"doc:{passage.get('doc_id')}",
                "url": passage.get("url"),
                "locator": passage.get("passage_id"),
                "claim": f"{passage.get('title')}::{passage.get('section')}",
                "quote": passage.get("text"),
            }
        )


def _build_answer_text(intent: str, records_by_recid: dict[int, dict[str, Any]]) -> str:
    """Build deterministic answer prose for each supported intent."""
    collision_title = _deep_get(records_by_recid[30522], "identity.title")
    mc_title = _deep_get(records_by_recid[35671], "identity.title")
    answers = {
        "dataset_discovery": (
            f"Use record 30522 ({collision_title}) as the frozen collision NanoAOD entry point and "
            f"record 35671 ({mc_title}) as the frozen MC reference. Keep validated JSON record "
            "14220 in scope for collision-quality filtering."
        ),
        "provenance": (
            "The assistant is pinned to frozen CMS Run 2 NanoAOD records 30522 (collision) and "
            "35671 (MC), with validated JSON context from record 14220 for collision-quality constraints."
        ),
        "doi_citation": (
            "Use DOI 10.7483/OPENDATA.CMS.ZQS3.LGLP for collision record 30522 and "
            "DOI 10.7483/OPENDATA.CMS.CRNB.POY1 for MC record 35671; include record URLs and Cite as "
            "strings in citation metadata for reproducibility."
        ),
        "license": (
            "Use CC0 dataset and metadata context from records 30522 and 35671, and check per-item "
            "licensing caveats in CERN Open Data Terms of Use for non-dataset content."
        ),
        "docker_environment": (
            "Use CMS Docker guidance with python-vnc image for reproducible NanoAOD analysis; "
            "this MVP keeps NanoAOD workflows CMSSW-free."
        ),
        "xrootd_access": (
            "Use cernopendata-client get-file-locations with --protocol xrootd and keep access bounded "
            "to deterministic first-three-file subset commands instead of full download defaults."
        ),
        "client_command": (
            "Generate cernopendata-client commands only from frozen recids, DOIs, and deterministic subset range metadata."
        ),
        "validated_json": (
            "Collision workflows anchored to record 30522 must include validated JSON context from record 14220 "
            "and apply run/lumisection filtering metadata."
        ),
        "dimuon_demo": (
            "The dimuon demo uses record 30522 with deterministic three-file selection (filter-range 1-3), "
            "optional MC comparison from 35671, and validated JSON context from 14220."
        ),
        "docs_discovery": (
            "The frozen official docs corpus covers CERN Terms of Use, CMS NanoAOD getting started, "
            "CMS Docker guidance, and cernopendata-client usage docs."
        ),
        "general_assistant": (
            "This assistant is a metadata-first layer over frozen CMS Run 2 NanoAOD records and official docs, "
            "returning deterministic evidence-backed outputs."
        ),
    }
    return answers[intent]


def _intent_record_locators(intent: str) -> list[tuple[int, str, str]]:
    """Return record field locators and claims used as evidence per intent."""
    common = [
        (30522, "identity.title", "Record 30522 defines the frozen collision dataset title."),
        (35671, "identity.title", "Record 35671 defines the frozen MC dataset title."),
    ]
    by_intent = {
        "dataset_discovery": common
        + [
            (30522, "dataset_characteristics.events", "Record 30522 reports collision event count."),
            (30522, "dataset_characteristics.files", "Record 30522 reports collision file count."),
            (35671, "dataset_characteristics.events", "Record 35671 reports MC event count."),
        ],
        "provenance": common
        + [
            (30522, "processing_provenance.steps", "Record 30522 contains processing provenance steps."),
            (35671, "processing_provenance.steps", "Record 35671 contains processing provenance steps."),
            (30522, "machine_access_endpoints.json_export", "Record 30522 exposes deterministic JSON export endpoint."),
        ],
        "doi_citation": [
            (30522, "identity.doi", "Record 30522 DOI is used for citation."),
            (30522, "license_and_citation.cite_as", "Record 30522 includes Cite as text."),
            (35671, "identity.doi", "Record 35671 DOI is used for citation."),
            (35671, "license_and_citation.cite_as", "Record 35671 includes Cite as text."),
        ],
        "license": [
            (30522, "license_and_citation.license", "Record 30522 provides dataset license metadata."),
            (35671, "license_and_citation.license", "Record 35671 provides dataset license metadata."),
            (30522, "license_and_citation.disclaimer_note", "Record 30522 includes endorsement disclaimer note."),
        ],
        "docker_environment": [
            (30522, "container_recommendation.recommended_images", "Record 30522 lists recommended container images."),
            (30522, "container_recommendation.reproducible_python_image", "Record 30522 supports pinned reproducible Python image."),
        ],
        "xrootd_access": [
            (30522, "identity.recid", "Record 30522 recid anchors deterministic file-location lookup."),
            (30522, "dataset_characteristics.files", "Record 30522 file count supports bounded subset rationale."),
            (30522, "dataset_characteristics.total_size", "Record 30522 total size supports bounded subset caveat."),
        ],
        "client_command": [
            (30522, "identity.recid", "Collision recid supports deterministic cernopendata-client commands."),
            (35671, "identity.recid", "MC recid supports deterministic cernopendata-client commands."),
            (14220, "identity.recid", "Validated JSON recid supports deterministic cernopendata-client commands."),
            (30522, "identity.doi", "Collision DOI supports deterministic metadata lookup command."),
            (35671, "identity.doi", "MC DOI supports deterministic metadata lookup command."),
        ],
        "validated_json": [
            (30522, "validated_json.required_record", "Record 30522 links validated JSON recid requirement."),
            (30522, "validated_json.validated_json_file_url", "Record 30522 points to validated JSON file URL."),
            (14220, "validated_json.validated_json_file_url", "Record 14220 provides validated JSON file URL."),
            (14220, "validated_json.requirement_statement", "Record 14220 states run/lumisection quality purpose."),
        ],
        "dimuon_demo": [
            (30522, "identity.recid", "Demo collision source is frozen to record 30522."),
            (35671, "identity.recid", "Demo MC comparison source is frozen to record 35671."),
            (14220, "identity.recid", "Demo quality mask source is frozen to record 14220."),
            (30522, "validated_json.required_record", "Record 30522 links validated JSON dependency for collision analysis."),
        ],
        "docs_discovery": common,
        "general_assistant": common,
    }
    return by_intent.get(intent, common)


def _command_attribution_for_intent(intent: str, command_catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return command provenance snippets relevant to one intent."""
    families = {
        "dataset_discovery": {"metadata_lookup"},
        "provenance": {"metadata_lookup", "file_location_lookup"},
        "doi_citation": {"metadata_lookup"},
        "license": {"metadata_lookup"},
        "docker_environment": {"docker_startup"},
        "xrootd_access": {"file_location_lookup", "xrootd_access"},
        "client_command": {"metadata_lookup", "file_location_lookup", "xrootd_access", "validated_json_lookup"},
        "validated_json": {"validated_json_lookup", "metadata_lookup"},
        "dimuon_demo": {"xrootd_access", "validated_json_lookup", "metadata_lookup"},
        "docs_discovery": {"metadata_lookup"},
        "general_assistant": {"metadata_lookup", "file_location_lookup", "xrootd_access", "docker_startup"},
    }.get(intent, {"metadata_lookup"})

    selected = [entry for entry in command_catalog if entry.get("family") in families]
    selected.sort(key=lambda item: (str(item.get("family", "")), str(item.get("id", ""))))

    output: list[dict[str, Any]] = []
    for entry in selected[:8]:
        output.append(
            {
                "id": entry.get("id"),
                "family": entry.get("family"),
                "command": entry.get("command"),
                "why": entry.get("why"),
                "origins": entry.get("origins", []),
            }
        )
    return output


def _docs_used_summary(passages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize docs passages used for response provenance."""
    grouped: dict[str, dict[str, Any]] = {}
    for passage in passages:
        doc_id = passage.get("doc_id")
        if not isinstance(doc_id, str):
            continue
        current = grouped.setdefault(
            doc_id,
            {
                "doc_id": doc_id,
                "title": passage.get("title"),
                "url": passage.get("url"),
                "passages": [],
            },
        )
        current["passages"].append(passage.get("passage_id"))

    result = list(grouped.values())
    result.sort(key=lambda item: str(item.get("doc_id", "")))
    return result


def build_structured_response(question: str, seed_dir: str | pathlib.Path) -> dict[str, Any]:
    """Return one evidence-backed structured answer for a user question."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question must be a non-empty string.")

    seed = _load_seed(seed_dir)
    records = seed["records"]
    docs_passage_index = seed["docs_passage_index"]
    templates = seed["command_templates"]
    command_catalog = seed["command_catalog"]
    demo = seed["dimuon_demo"]
    demo_linkage = seed["demo_linkage"]
    seed_process = seed["seed_process"]
    manifest = seed["manifest"]

    indexed = _records_by_recid(records)
    intent = classify_intent(question)
    recids = _recommended_recids(intent)

    reasons = {
        30522: "Frozen collision NanoAOD anchor record for CMS Run 2 MVP.",
        35671: "Frozen MC NanoAODSIM reference record for comparative workflows.",
        14220: "Validated JSON run/lumisection quality context for collision analyses.",
    }
    recommended = [_record_projection(indexed[recid], reasons[recid]) for recid in recids]

    passages = _retrieve_doc_passages(intent, question, docs_passage_index)

    evidence_entries: list[dict[str, Any]] = []
    for recid, locator, claim in _intent_record_locators(intent):
        _append_record_evidence(evidence_entries, indexed, recid, locator, claim)
    _append_doc_evidence(evidence_entries, passages)

    citations: list[dict[str, Any]] = []
    for recid in (30522, 35671, 14220):
        record = indexed[recid]
        citations.append(
            {
                "recid": recid,
                "title": _deep_get(record, "identity.title"),
                "doi": _deep_get(record, "identity.doi"),
                "record_url": _deep_get(record, "identity.record_url"),
                "cite_as": _deep_get(record, "license_and_citation.cite_as"),
            }
        )

    collision_images = _deep_get(indexed[30522], "container_recommendation.recommended_images")
    if not isinstance(collision_images, list):
        collision_images = []

    subset_strategy = demo.get("subset_strategy") if isinstance(demo.get("subset_strategy"), dict) else {}

    response = {
        "answer": _build_answer_text(intent, indexed),
        "intent": intent,
        "recommended_datasets": recommended,
        "provenance": {
            "scope": "CMS Run 2 NanoAOD frozen MVP",
            "scope_version": seed_process.get("seed_version"),
            "frozen_record_ids": list(FROZEN_RECORD_IDS),
            "collision_record": {
                "recid": 30522,
                "doi": _deep_get(indexed[30522], "identity.doi"),
                "dataset_path": _deep_get(indexed[30522], "identity.dataset_path"),
                "record_url": _deep_get(indexed[30522], "identity.record_url"),
            },
            "mc_record": {
                "recid": 35671,
                "doi": _deep_get(indexed[35671], "identity.doi"),
                "dataset_path": _deep_get(indexed[35671], "identity.dataset_path"),
                "record_url": _deep_get(indexed[35671], "identity.record_url"),
            },
            "validated_json_record": {
                "recid": 14220,
                "dataset_path": _deep_get(indexed[14220], "identity.dataset_path"),
                "record_url": _deep_get(indexed[14220], "identity.record_url"),
                "validated_json_file_url": _deep_get(indexed[14220], "validated_json.validated_json_file_url"),
            },
            "validated_json_requirement": (
                "Record 14220 is required for collision workflows because record 30522 links a validated run/lumisection mask "
                "that must be applied before analysis."
            ),
            "seed_artifacts_used": sorted(manifest.get("generated_files", {}).keys()),
            "seed_artifact_hashes": manifest.get("generated_files", {}),
            "command_templates_from": "command_catalog.json built from normalized record fields and doc passages",
            "docs_informed": _docs_used_summary(passages),
            "demo_linkage": {
                "dataset_recid": demo_linkage.get("dataset_recid"),
                "mc_recid": demo_linkage.get("mc_recid"),
                "validated_json_recid": demo_linkage.get("validated_json_recid"),
            },
        },
        "environment": {
            "supports_cmssw_free_nanoaod_analysis": True,
            "recommended_images": collision_images,
            "reproducible_python_image": _deep_get(
                indexed[30522],
                "container_recommendation.reproducible_python_image",
            ),
            "docker_startup": templates.get("docker_startup"),
            "runtime": "docker",
        },
        "access_recipe": {
            "metadata_lookup": templates.get("metadata_lookup", []),
            "file_location_lookup": templates.get("file_location_lookup", []),
            "xrootd_access": templates.get("xrootd_access", []),
            "validated_json_lookup": templates.get("validated_json_lookup", []),
            "dimuon_subset": {
                "dataset_recid": demo.get("dataset_recid"),
                "subset_strategy": subset_strategy,
            },
            "command_attribution": _command_attribution_for_intent(intent, command_catalog),
        },
        "license_and_citation": {
            "license_summary": (
                "Dataset and metadata context is CC0 in frozen records; verify per-item licenses for other content "
                "using Terms of Use evidence."
            ),
            "terms_of_use_url": "https://opendata.cern.ch/docs/terms-of-use",
            "citations": citations,
        },
        "evidence": evidence_entries,
        "caveats": [
            "Scope is frozen to CMS Run 2 NanoAOD records 30522, 35671, and validated JSON record 14220.",
            "Do not default to full dataset downloads; use bounded deterministic subsets for demos.",
            "Use deterministic command templates from metadata and docs; do not generate freehand shell commands.",
            "This assistant layers metadata/provenance guidance on top of official CERN tooling and does not replace cernopendata-client.",
            "No CMSSW dependency is required for NanoAOD analysis guidance in this MVP.",
            "Dimuon demo is a shape-oriented bounded subset path, not a full-statistics precision analysis.",
        ],
    }

    missing = [field for field in REQUIRED_RESPONSE_FIELDS if field not in response]
    if missing:
        raise RuntimeError(f"Structured response is missing required fields: {missing}.")

    return response


def load_evaluation_questions(questions_path: str | pathlib.Path | None = None) -> list[dict[str, Any]]:
    """Load deterministic 20-question evaluation suite."""
    path = _repo_root() / DEFAULT_EVAL_QUESTIONS if questions_path is None else pathlib.Path(questions_path)
    loaded = _load_json(path)
    if not isinstance(loaded, list) or not all(isinstance(item, dict) for item in loaded):
        raise ValueError("Evaluation question file must be a list of objects.")
    if len(loaded) != 20:
        raise ValueError(f"Evaluation suite must contain exactly 20 questions, found {len(loaded)}.")
    return loaded


def _validate_evidence_entries(response: dict[str, Any]) -> list[str]:
    """Validate evidence structure for deterministic auditability."""
    failures: list[str] = []
    evidence = response.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        failures.append("Evidence must be a non-empty list.")
        return failures

    has_doc_passage = False
    has_record_field = False
    for index, item in enumerate(evidence, start=1):
        if not isinstance(item, dict):
            failures.append(f"Evidence entry {index} must be an object.")
            continue
        for key in ("source_type", "source_id", "url", "locator", "claim"):
            if key not in item or not isinstance(item[key], str) or not item[key].strip():
                failures.append(f"Evidence entry {index} missing required string '{key}'.")

        source_type = item.get("source_type")
        if source_type == "doc_passage":
            has_doc_passage = True
        if source_type == "record_field":
            has_record_field = True

    if not has_doc_passage:
        failures.append("Evidence must include at least one doc_passage source.")
    if not has_record_field:
        failures.append("Evidence must include at least one record_field source.")
    return failures


def run_evaluation(seed_dir: str | pathlib.Path, questions_path: str | pathlib.Path | None = None) -> dict[str, Any]:
    """Run deterministic evaluation over the frozen 20-question suite."""
    questions = load_evaluation_questions(questions_path)
    results: list[dict[str, Any]] = []

    for item in questions:
        question_id = item.get("id")
        question_text = item.get("question")
        expected_intent = item.get("expected_intent")
        required_record_ids = item.get("required_record_ids")

        failures: list[str] = []
        if not isinstance(question_id, str):
            failures.append("Missing string id.")
        if not isinstance(question_text, str):
            failures.append("Missing string question.")
        if not isinstance(expected_intent, str):
            failures.append("Missing string expected_intent.")
        if not isinstance(required_record_ids, list) or not all(
            isinstance(value, int) for value in required_record_ids
        ):
            failures.append("required_record_ids must be a list of integers.")

        response = build_structured_response(str(question_text), seed_dir)
        missing_fields = [field for field in REQUIRED_RESPONSE_FIELDS if field not in response]
        if missing_fields:
            failures.append(f"Missing required response fields: {missing_fields}.")

        if response.get("intent") != expected_intent:
            failures.append(
                f"Intent mismatch. Expected '{expected_intent}', got '{response.get('intent')}'."
            )

        recommended_ids = {
            record.get("recid")
            for record in response.get("recommended_datasets", [])
            if isinstance(record, dict)
        }
        for expected_recid in required_record_ids or []:
            if expected_recid not in recommended_ids:
                failures.append(f"Missing required recid {expected_recid} in recommendations.")

        failures.extend(_validate_evidence_entries(response))

        if expected_intent == "doi_citation":
            citations = response.get("license_and_citation", {}).get("citations", [])
            seen_dois = {
                citation.get("doi")
                for citation in citations
                if isinstance(citation, dict) and isinstance(citation.get("doi"), str)
            }
            for recid in (30522, 35671):
                if DOI_BY_RECID[recid] not in seen_dois:
                    failures.append(f"DOI {DOI_BY_RECID[recid]} missing from citation output.")

        if expected_intent == "validated_json":
            provenance_text = json.dumps(response.get("provenance", {}), ensure_ascii=False).lower()
            if "14220" not in provenance_text:
                failures.append("Validated JSON provenance must include record 14220 linkage.")
            if "validated" not in provenance_text:
                failures.append("Validated JSON provenance text must mention validation requirement.")

        if expected_intent in {"xrootd_access", "dimuon_demo", "general_assistant"}:
            caveats = response.get("caveats", [])
            caveat_text = " ".join(item for item in caveats if isinstance(item, str)).lower()
            if "full dataset" not in caveat_text:
                failures.append("Caveats must warn against default full dataset download.")

        if expected_intent == "dimuon_demo":
            subset = response.get("access_recipe", {}).get("dimuon_subset", {}).get("subset_strategy", {})
            if subset.get("range") != "1-3":
                failures.append("Dimuon demo must retain deterministic three-file subset range 1-3.")

        if expected_intent == "docker_environment":
            environment = response.get("environment", {})
            if environment.get("supports_cmssw_free_nanoaod_analysis") is not True:
                failures.append("Docker/environment response must state CMSSW-free NanoAOD support.")

        if expected_intent in {"xrootd_access", "client_command"}:
            commands = response.get("access_recipe", {}).get("xrootd_access", [])
            if not any("--filter-range 1-3" in str(command) for command in commands):
                failures.append("XRootD access recipe must include deterministic --filter-range 1-3 command.")

        results.append(
            {
                "id": question_id,
                "passed": not failures,
                "failures": failures,
            }
        )

    passed = sum(1 for result in results if result["passed"])
    total = len(results)
    return {
        "seed_version": SEED_VERSION,
        "total_questions": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "results": results,
    }


def get_dimuon_demo(seed_dir: str | pathlib.Path) -> dict[str, Any]:
    """Return deterministic dimuon demo path and command templates."""
    seed = _load_seed(seed_dir)
    templates = seed["command_templates"]
    demo = seed["dimuon_demo"]
    demo_linkage = seed["demo_linkage"]

    return {
        "demo": demo,
        "commands": {
            "metadata_lookup": templates.get("metadata_lookup", []),
            "xrootd_access": templates.get("xrootd_access", []),
            "docker_startup": templates.get("docker_startup"),
            "validated_json_lookup": templates.get("validated_json_lookup", []),
        },
        "provenance": {
            "linked_records": demo_linkage.get("linked_records", []),
            "subset_strategy": demo.get("subset_strategy"),
        },
        "notes": [
            "This path is deterministic and bounded to a three-file subset.",
            "Use it for reproducible MVP demonstrations, not full-statistics physics measurements.",
        ],
    }
