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


def load_knowledge_bundle(knowledge_dir: str | pathlib.Path | None = None) -> dict[str, Any]:
    """Load frozen records, docs corpus, and dimuon demo definitions."""
    base_dir = _repo_root() / DEFAULT_KNOWLEDGE_DIR if knowledge_dir is None else pathlib.Path(knowledge_dir)
    records_path = base_dir / "frozen_records.json"
    docs_path = base_dir / "official_docs.json"
    demo_path = base_dir / "dimuon_demo.json"

    records = _load_json(records_path)
    docs = _load_json(docs_path)
    demo = _load_json(demo_path)

    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("knowledge/frozen_records.json must contain a JSON list of objects.")
    if not isinstance(docs, list) or not all(isinstance(item, dict) for item in docs):
        raise ValueError("knowledge/official_docs.json must contain a JSON list of objects.")
    if not isinstance(demo, dict):
        raise ValueError("knowledge/dimuon_demo.json must contain a JSON object.")

    record_ids = tuple(sorted(item.get("recid") for item in records))
    if record_ids != FROZEN_RECORD_IDS:
        raise ValueError(
            "Frozen record set mismatch. Expected recids "
            f"{FROZEN_RECORD_IDS}, got {record_ids}."
        )

    return {
        "knowledge_dir": str(base_dir.resolve()),
        "records": records,
        "docs": docs,
        "demo": demo,
    }


def _records_by_recid(records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Index records by integer recid."""
    indexed: dict[int, dict[str, Any]] = {}
    for record in records:
        recid = record.get("recid")
        if not isinstance(recid, int):
            raise ValueError("Each frozen record must define an integer 'recid'.")
        indexed[recid] = record
    return indexed


def build_command_templates(records: list[dict[str, Any]]) -> dict[str, list[str] | str]:
    """Generate deterministic command templates from frozen metadata."""
    indexed = _records_by_recid(records)
    collision = indexed[30522]
    mc = indexed[35671]
    validated = indexed[14220]

    collision_doi = collision.get("doi")
    mc_doi = mc.get("doi")

    if not isinstance(collision_doi, str) or not isinstance(mc_doi, str):
        raise ValueError("Collision and MC records must include DOI strings.")

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
        "docker_startup": "docker run --rm -it -P -p 5901:5901 -p 6080:6080 -p 8888:8888 gitlab-registry.cern.ch/cms-cloud/python-vnc:latest",
        "validated_json_lookup": [
            "cernopendata-client get-metadata --recid 14220",
            "cernopendata-client get-file-locations --recid 14220",
        ],
    }


def seed_frozen_inputs(seed_dir: str | pathlib.Path) -> dict[str, Any]:
    """Ingest frozen records/docs into deterministic structured seed files."""
    seed_root = pathlib.Path(seed_dir).expanduser().resolve()
    seed_root.mkdir(parents=True, exist_ok=True)

    bundle = load_knowledge_bundle()
    templates = build_command_templates(bundle["records"])

    files_to_write = {
        "records": seed_root / "records.json",
        "docs": seed_root / "docs.json",
        "command_templates": seed_root / "command_templates.json",
        "dimuon_demo": seed_root / "dimuon_demo.json",
        "seed_process": seed_root / "seed_process.json",
    }

    files_to_write["records"].write_text(_json_dumps(bundle["records"]), encoding="utf-8")
    files_to_write["docs"].write_text(_json_dumps(bundle["docs"]), encoding="utf-8")
    files_to_write["command_templates"].write_text(_json_dumps(templates), encoding="utf-8")
    files_to_write["dimuon_demo"].write_text(_json_dumps(bundle["demo"]), encoding="utf-8")
    files_to_write["seed_process"].write_text(
        _json_dumps(
            {
                "seed_version": SEED_VERSION,
                "scope": "CMS Run 2 NanoAOD only",
                "frozen_record_ids": list(FROZEN_RECORD_IDS),
                "docs_sources": [doc.get("url") for doc in bundle["docs"]],
                "deterministic": True,
            }
        ),
        encoding="utf-8",
    )

    manifest_payload = {
        "seed_version": SEED_VERSION,
        "files": {
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
        seed_root / "command_templates.json",
        seed_root / "dimuon_demo.json",
        seed_root / "seed_process.json",
    ]
    if not all(path.exists() for path in required):
        seed_frozen_inputs(seed_root)

    return {
        "records": _load_json(seed_root / "records.json"),
        "docs": _load_json(seed_root / "docs.json"),
        "command_templates": _load_json(seed_root / "command_templates.json"),
        "dimuon_demo": _load_json(seed_root / "dimuon_demo.json"),
        "seed_process": _load_json(seed_root / "seed_process.json"),
        "seed_dir": str(seed_root),
    }


def _normalize(text: str) -> str:
    """Normalize input question text for deterministic intent matching."""
    return " ".join(text.strip().lower().split())


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
    if any(token in normalized for token in ("xrootd", "root://", "file locations", "file-location")):
        return "xrootd_access"
    if any(token in normalized for token in ("docker", "container", "environment", "cmssw")):
        return "docker_environment"
    if any(token in normalized for token in ("cernopendata-client", "command", "metadata lookup", "download-files")):
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
        "title": record.get("title"),
        "doi": record.get("doi"),
        "modality": record.get("modality"),
        "record_url": record.get("record_url"),
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


def _build_answer_text(intent: str) -> str:
    """Build deterministic answer prose for each supported intent."""
    answers = {
        "dataset_discovery": (
            "Use record 30522 as the frozen collision NanoAOD entry point and "
            "record 35671 as the frozen MC reference. Keep validated JSON record "
            "14220 in scope for collision-quality filtering."
        ),
        "provenance": (
            "The assistant is pinned to frozen CMS Run 2 NanoAOD records 30522 "
            "(collision) and 35671 (MC), with validated JSON context from record "
            "14220 for collision-quality constraints."
        ),
        "doi_citation": (
            "Use DOI 10.7483/OPENDATA.CMS.ZQS3.LGLP for collision record 30522 and "
            "DOI 10.7483/OPENDATA.CMS.CRNB.POY1 for MC record 35671; include record "
            "URLs in citation metadata for reproducibility."
        ),
        "license": (
            "CERN Open Data terms and frozen record metadata indicate CC0-style "
            "licensing context for these records; include citation and terms references "
            "in outputs and retain portal caveats."
        ),
        "docker_environment": (
            "Use CMS Docker images for local analysis environments and do not require "
            "CMSSW for NanoAOD-level workflows in this MVP scope."
        ),
        "xrootd_access": (
            "Use cernopendata-client file-location commands with --protocol xrootd and "
            "bound access to deterministic subsets instead of full dataset download."
        ),
        "client_command": (
            "Generate cernopendata-client commands only from frozen record metadata "
            "(recids and DOIs), including deterministic subset controls via filter-range."
        ),
        "validated_json": (
            "Collision workflows anchored to record 30522 must include validated JSON "
            "context from record 14220 to enforce good run/lumisection handling."
        ),
        "dimuon_demo": (
            "The dimuon demo uses record 30522 with deterministic three-file selection "
            "(filter-range 1-3), optional MC comparison from 35671, and validated JSON "
            "context from 14220."
        ),
        "docs_discovery": (
            "The official docs corpus includes CERN Terms of Use, CMS NanoAOD getting "
            "started, CMS Docker guidance, and cernopendata-client documentation."
        ),
        "general_assistant": (
            "This assistant is a metadata-first layer over frozen CMS Run 2 NanoAOD "
            "records and official docs, returning deterministic evidence-backed outputs."
        ),
    }
    return answers[intent]


def build_structured_response(question: str, seed_dir: str | pathlib.Path) -> dict[str, Any]:
    """Return one evidence-backed structured answer for a user question."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question must be a non-empty string.")

    seed = _load_seed(seed_dir)
    records = seed["records"]
    docs = seed["docs"]
    templates = seed["command_templates"]
    demo = seed["dimuon_demo"]

    indexed = _records_by_recid(records)
    intent = classify_intent(question)
    recids = _recommended_recids(intent)

    reasons = {
        30522: "Frozen collision NanoAOD anchor record for CMS Run 2 MVP.",
        35671: "Frozen MC NanoAODSIM reference record for comparative workflows.",
        14220: "Validated JSON run/lumisection quality context for collision analyses.",
    }
    recommended = [_record_projection(indexed[recid], reasons[recid]) for recid in recids]

    citations: list[dict[str, Any]] = []
    for recid in (30522, 35671, 14220):
        record = indexed[recid]
        citations.append(
            {
                "recid": recid,
                "title": record.get("title"),
                "doi": record.get("doi"),
                "record_url": record.get("record_url"),
            }
        )

    evidence_entries: list[dict[str, str]] = []
    for recid in recids:
        record = indexed[recid]
        record_evidence = record.get("evidence")
        if isinstance(record_evidence, list):
            for claim in record_evidence[:2]:
                if isinstance(claim, str):
                    evidence_entries.append(
                        {
                            "source_id": f"record_{recid}",
                            "url": str(record.get("record_url")),
                            "claim": claim,
                        }
                    )
    for doc in docs:
        doc_id = doc.get("doc_id")
        doc_url = doc.get("url")
        doc_evidence = doc.get("evidence")
        if isinstance(doc_id, str) and isinstance(doc_url, str) and isinstance(doc_evidence, list):
            first_claim = next((item for item in doc_evidence if isinstance(item, str)), None)
            if first_claim is not None:
                evidence_entries.append(
                    {
                        "source_id": doc_id,
                        "url": doc_url,
                        "claim": first_claim,
                    }
                )

    response = {
        "answer": _build_answer_text(intent),
        "intent": intent,
        "recommended_datasets": recommended,
        "provenance": {
            "scope": "CMS Run 2 NanoAOD frozen MVP",
            "collision_record": {
                "recid": 30522,
                "doi": indexed[30522].get("doi"),
                "dataset_path": indexed[30522].get("dataset_path"),
            },
            "mc_record": {
                "recid": 35671,
                "doi": indexed[35671].get("doi"),
                "dataset_path": indexed[35671].get("dataset_path"),
            },
            "validated_json_record": {
                "recid": 14220,
                "dataset_path": indexed[14220].get("dataset_path"),
            },
            "validated_json_requirement": "Use record 14220 as quality metadata for collision workflows.",
        },
        "environment": {
            "supports_cmssw_free_nanoaod_analysis": True,
            "recommended_images": indexed[30522].get("recommended_images", []),
            "docker_startup": templates.get("docker_startup"),
        },
        "access_recipe": {
            "metadata_lookup": templates.get("metadata_lookup", []),
            "file_location_lookup": templates.get("file_location_lookup", []),
            "xrootd_access": templates.get("xrootd_access", []),
            "validated_json_lookup": templates.get("validated_json_lookup", []),
            "dimuon_subset": {
                "dataset_recid": demo.get("dataset_recid"),
                "subset_strategy": demo.get("subset_strategy"),
            },
        },
        "license_and_citation": {
            "license_summary": "Use CERN Open Data terms and CC0 context from frozen records/docs.",
            "terms_of_use_url": "https://opendata.cern.ch/docs/terms-of-use",
            "citations": citations,
        },
        "evidence": evidence_entries,
        "caveats": [
            "Scope is frozen to CMS Run 2 NanoAOD records 30522, 35671, and validated JSON record 14220.",
            "Do not default to full dataset downloads; use bounded deterministic subsets for demos.",
            "This assistant layers metadata/provenance guidance on top of official CERN tooling and does not replace cernopendata-client.",
            "No CMSSW dependency is required for NanoAOD analysis guidance in this MVP.",
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

    return {
        "demo": demo,
        "commands": {
            "metadata_lookup": templates.get("metadata_lookup", []),
            "xrootd_access": templates.get("xrootd_access", []),
            "docker_startup": templates.get("docker_startup"),
            "validated_json_lookup": templates.get("validated_json_lookup", []),
        },
        "notes": [
            "This path is deterministic and bounded to a three-file subset.",
            "Use it for reproducible MVP demonstrations, not full-statistics physics measurements.",
        ],
    }
