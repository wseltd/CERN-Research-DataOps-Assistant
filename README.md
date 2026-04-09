# cern-research-dataops-assistant

`cern-research-dataops-assistant` is a metadata-first, provenance-aware local CLI for a frozen CERN Open Data MVP focused on CMS Run 2 NanoAOD.

Frozen product scope:

- collision dataset record `30522`
- MC dataset record `35671`
- validated JSON record `14220`
- official docs corpus:
  - CERN Open Data Terms of Use
  - CMS NanoAOD getting-started guide
  - CMS Docker guide
  - cernopendata-client docs

## Quickstart

From a clean checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
cern-dataops --help
```

## CLI Usage

Top-level CLI:

```bash
cern-dataops --help
```

Seed frozen records/docs into deterministic local state:

```bash
cern-dataops assistant seed --seed-dir data/cms_run2_nanoaod_mvp
```

Ask evidence-backed questions with structured output:

```bash
cern-dataops assistant ask --seed-dir data/cms_run2_nanoaod_mvp "How do I access record 30522 via xrootd?"
```

Run the deterministic 20-question evaluation suite:

```bash
cern-dataops assistant eval --seed-dir data/cms_run2_nanoaod_mvp --questions-file evaluations/cms_run2_nanoaod_eval_questions.json
```

Return the deterministic dimuon demo path:

```bash
cern-dataops assistant demo --seed-dir data/cms_run2_nanoaod_mvp
```

## Architecture

The CERN assistant path is centered in `src/cern_open_data_mvp.py` and remains deterministic.

- Source assets (`knowledge/`):
  - `frozen_records.json`
  - `frozen_record_details.json`
  - `official_docs.json`
  - `official_docs_passages.json`
  - `dimuon_demo.json`
- Evaluation suite:
  - `evaluations/cms_run2_nanoaod_eval_questions.json`
- CLI wiring:
  - `src/cern_research_dataops_assistant.py`

The older generic local JSONL ingest/query machinery still exists for backwards compatibility but is secondary to the CERN assistant flow.

## Ingestion Flow

`assistant seed` reads frozen source assets and writes normalized deterministic artifacts:

- `records.json`: normalized record metadata with field-level provenance maps
- `docs.json`: normalized docs corpus with passage groups
- `docs_passage_index.json`: deterministic passage-level retrieval index
- `command_templates.json`: deterministic command families (legacy-compatible format)
- `command_catalog.json`: command templates plus explicit source attribution
- `dimuon_demo.json`: frozen deterministic dimuon path
- `demo_linkage.json`: explicit linkage to records `30522`, `35671`, `14220`
- `seed_process.json`: seed scope, source hashes, deterministic process metadata
- `manifest.json`: deterministic hashes for source assets and generated artifacts

## Retrieval and Answer Assembly

`assistant ask` uses deterministic intent routing and metadata-first assembly:

1. classify intent with explicit keyword rules
2. select recommended frozen records by intent
3. retrieve relevant docs passages from `docs_passage_index.json` using deterministic keyword scoring
4. assemble structured output with auditable evidence entries:
   - `source_type` (`record_field` or `doc_passage`)
   - `source_id`
   - `url`
   - `locator`
   - `claim`
   - optional `quote`
5. attach deterministic command templates and command-level source attribution

The assistant does not generate freehand shell commands from open-ended LLM output.

## Structured Output Contract

`assistant ask` preserves the required top-level contract:

- `answer`
- `intent`
- `recommended_datasets`
- `provenance`
- `environment`
- `access_recipe`
- `license_and_citation`
- `evidence`
- `caveats`

## Demo Flow

Deterministic dimuon path (three-file subset):

1. seed frozen assets with `assistant seed`
2. anchor collision path to record `30522`
3. anchor MC reference to record `35671`
4. enforce validated JSON linkage to record `14220`
5. keep bounded subset strategy (`filter-range 1-3`)

This demo path is intentionally bounded and deterministic.

## Sources

Official source URLs used in this frozen MVP:

- https://opendata.cern.ch/record/30522
- https://opendata.cern.ch/record/35671
- https://opendata.cern.ch/record/14220
- https://opendata.cern.ch/docs/terms-of-use
- https://opendata.cern.ch/docs/cms-getting-started-nanoaod
- https://opendata.cern.ch/docs/cms-guide-docker
- https://cernopendata-client.readthedocs.io/en/latest/usage.html

## Trade-offs

- Frozen scope improves determinism and auditability at the cost of dataset breadth.
- Deterministic keyword retrieval is inspectable and stable, but narrower than semantic retrieval systems.
- The assistant prioritizes metadata-grounded command generation over conversational flexibility.

## Limitations

- No live CERN API calls are performed during assistant responses; this repository works from frozen local assets.
- No hosted deployment path is provided.
- No remote services integration is implemented by this repository itself.
- No cloud/services runtime is included.
- The assistant is intentionally limited to frozen records `30522`, `35671`, and `14220`.
- Outputs are guidance on top of official tooling; users still execute cernopendata-client and analysis code themselves.

## Non-goals

- Building cloud platforms, SaaS backends, hosted deployment, or managed services.
- Replacing cernopendata-client, REANA, or official CERN/CMS analysis tooling.
- Broadening beyond CMS Run 2 NanoAOD for this MVP.
- Defaulting to full dataset download workflows.
