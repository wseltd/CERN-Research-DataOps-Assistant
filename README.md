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

The assistant is implemented as a metadata-first layer over frozen local JSON assets:

- `knowledge/frozen_records.json`: frozen CERN record metadata (`30522`, `35671`, `14220`)
- `knowledge/official_docs.json`: official docs corpus ingestion source
- `knowledge/dimuon_demo.json`: deterministic three-file dimuon demo specification
- `evaluations/cms_run2_nanoaod_eval_questions.json`: deterministic 20-question evaluation set
- `src/cern_open_data_mvp.py`: deterministic ingestion, intent classification, evidence assembly, command template generation
- `src/cern_research_dataops_assistant.py`: CLI wiring and command dispatch

The seeded output is structured and deterministic (`records.json`, `docs.json`, `command_templates.json`, `dimuon_demo.json`, `seed_process.json`, `manifest.json`) to support reproducible local runs.

## Sources

Official source URLs used in this MVP:

- https://opendata.cern.ch/record/30522
- https://opendata.cern.ch/record/35671
- https://opendata.cern.ch/record/14220
- https://opendata.cern.ch/docs/terms-of-use
- https://opendata.cern.ch/docs/cms-getting-started-nanoaod
- https://opendata.cern.ch/docs/cms-guide-docker
- https://cernopendata-client.readthedocs.io/en/latest/usage.html

## Structured Output Contract

`assistant ask` returns JSON with all required fields:

- `answer`
- `intent`
- `recommended_datasets`
- `provenance`
- `environment`
- `access_recipe`
- `license_and_citation`
- `evidence`
- `caveats`

Command templates are deterministic and metadata-derived for:

- cernopendata-client metadata lookup
- file-location lookup
- XRootD access
- Docker startup
- validated JSON metadata lookup

## Demo Flow

Deterministic dimuon path (three-file subset):

1. Seed frozen records/docs with `assistant seed`.
2. Resolve metadata/provenance for record `30522` and validated JSON record `14220`.
3. Generate XRootD subset commands using deterministic `filter-range 1-3`.
4. Use Docker startup guidance for local analysis environment.
5. Treat this as a bounded demonstration path, not a full-statistics analysis.

## Trade-offs

- Frozen scope improves determinism and governance at the cost of breadth.
- Metadata-first responses prioritize provenance and command reproducibility over broad conversational flexibility.
- Deterministic rule-based intent mapping is explicit and stable, but narrower than open-ended semantic retrieval.

## Limitations

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
