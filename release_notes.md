# v0.4.0 - Source-Aware Ontology and Traceable Generation

## Release Title

Source-Aware Ontology for OCPP 2.1 Ed2 RAG/KAG Traceability

## Release Description

`v0.4.0` adds the first source-aware ontology layer for the OCPP 2.1 Ed2
knowledge backend. The release makes relationships between Part 2 specification
sections, Device Model components/variables, and JSON schema payloads explicit
enough to support ontology-guided retrieval, evidence-pack provenance, and
stricter generated-answer evaluation.

The goal of this release is not to replace normative OCPP evidence with an
ontology. The ontology acts as a traceability layer: it helps developers,
coding agents, and reviewers see how retrieved evidence connects across source
layers, and it forces generated implementation guidance to disclose missing
links instead of inventing unsupported fields or requirements.

## Highlights

- Added a lightweight source-aware ontology catalog for OCPP 2.1 Ed2 evidence
  layers:
  - Part 2 specification sections and feature areas
  - Device Model components and variables
  - JSON schema message and payload paths
- Added ontology-aware graph promotion for fusion retrieval.
- Added ontology metrics to retrieval evaluation reports:
  - graph candidate chunks
  - graph candidate semantic links
  - final graph chunks
  - traversal depth
- Added ontology provenance in API/MCP evidence packs so downstream clients can
  inspect semantic links and mapping rules.
- Improved generation prompts with ontology-aware implementation trace guidance:
  `spec behavior -> Device Model component/variable -> JSON schema payload`.
- Added stricter golden-answer scoring for ontology trace quality and
  missing-link disclosure.
- Refreshed DeepSeek and Codex-only golden-answer reports under the stricter
  ontology trace rubric.
- Updated handoff and query-quality documentation for ontology-guided retrieval
  and answer evaluation.

## Operator Guidance

Run retrieval quality with ontology metrics:

```bash
HF_HOME=./models .venv/bin/rag eval-quality \
  --topic all \
  --mode all \
  --top-k 12 \
  --output reports/ocpp21-ed2-rqk-quality-ontology-aware-retrieval.md
```

Rescore saved generated answers without a new LLM call:

```bash
HF_HOME=./models .venv/bin/rag eval-answers \
  --from-answers-dir \
  --answers-dir reports/golden_answers \
  --output reports/ocpp21-ed2-rqk-golden-answers.md

HF_HOME=./models .venv/bin/rag eval-answers \
  --from-answers-dir \
  --answers-dir reports/golden_answers_codex-only \
  --output reports/ocpp21-ed2-rqk-golden-answers-codex-only.md
```

## Validation

Validated locally with:

- Retrieval quality baseline with ontology-aware retrieval:
  - `12/12` passed
  - score `0.976`
  - `30` graph candidate chunks
  - `134` graph candidate semantic links
  - `3` final graph chunks
- DeepSeek saved-answer evaluation under the ontology trace rubric:
  - `3/3` passed
  - score `0.990`
- Codex-only saved-answer evaluation under the ontology trace rubric:
  - `3/3` passed
  - score `0.992`
- `.venv/bin/pytest tests/test_eval/test_answers.py -q`
  - `13 passed`
- Scoped `ruff check` on changed ontology, retrieval, generation, and answer
  evaluation files.
- Scoped `mypy` on changed generation and answer evaluation files.
- `.venv/bin/python -m compileall -q src/rag_ocpp`
- `git diff --check`

## Known Gaps

- API/CLI/MCP generated-answer outputs still need full parity with the
  golden-answer Markdown, citation, ontology trace, and missing-link disclosure
  contract.
- The ontology is a traceability and retrieval aid, not a complete formal OCPP
  ontology.
- Source-level ACLs, tenant isolation, retention/deletion policy, and
  secret-handling policy remain future enterprise controls.
- Eval coverage remains strongest for Section R DER, Section Q V2X, and Section
  K smart charging; broader OCPP 2.1 Ed2 coverage is still pending.
- CI wiring for ontology-aware retrieval and golden-answer gates remains
  pending.

## Recommended Tag

```text
v0.4.0
```

## Recommended Release Commit Message

```text
release: publish v0.4.0 source-aware ontology traceability
```

# v0.3.0 - FastAPI Enterprise Access Surface

## Release Title

FastAPI Enterprise Access Surface for OCPP 2.1 Ed2 RAG/KAG

## Release Description

`v0.3.0` promotes the FastAPI layer from a basic access surface into a tested,
source-aware API for OCPP 2.1 Ed2 private knowledge operations. This release
aligns query/search responses with source metadata, adds admin-controlled corpus
operations, exports an OpenAPI 3.0.3 reference at version `0.3.0`, and documents
curl/Postman smoke tests against a running uvicorn server.

The release keeps the enterprise privacy, audit, and migration controls from
`v0.2.0`, then adds the HTTP contracts needed for API clients, coding agents,
and operators to inspect corpus health, retrieve evidence, generate answers,
and run safe admin checks.

## Highlights

- Bumped package and FastAPI metadata to `0.3.0`.
- Regenerated `api.json` as OpenAPI `3.0.3` with API version `0.3.0`.
- Added source-aware FastAPI query/search controls:
  - `top_k`
  - `doc_type`
  - `evidence_layer`
  - `source_type`
  - `max_chars`
  - `include_content`
  - `include_answer`
  - `include_query`
- Added source metadata in API chunk responses:
  - `evidence_layer`
  - `source_type`
  - `source_path`
  - `content_hash`
- Added privacy-preserving query references and correlation IDs in API responses.
- Added redacted generation failure responses for `/query` and `/query/stream`.
- Added `API_ADMIN_TOKEN` bearer-auth guard for mutating API endpoints.
- Marked `POST /ingest` as a legacy admin direct-ingestion endpoint.
- Added dedicated source-aware corpus API endpoints:
  - `GET /corpus/status`
  - `POST /corpus/preview`
  - `POST /corpus/store`
  - `POST /corpus/index`
- Added shared corpus status contract across API, CLI, and MCP:
  - `GET /corpus/status`
  - `rag corpus-status`
  - MCP `inspect_ocpp_corpus`
- Added HTTP client smoke-test documentation for curl and Postman.

## Operator Guidance

Start the API with `.env` explicitly sourced:

```bash
set -a
source .env
set +a

HF_HOME=./models API_ADMIN_TOKEN=local-test-token \
  .venv/bin/uvicorn "rag_ocpp.api.app:create_app" \
  --factory \
  --host 127.0.0.1 \
  --port 8000
```

Import the OpenAPI reference into Postman:

```text
http://127.0.0.1:8000/openapi.json
```

Run the HTTP smoke-test procedure:

```text
docs/api_http_client_tests.md
```

## Validation

Validated locally with:

- `.venv/bin/pytest tests/test_api tests/test_corpus/test_status_contract.py tests/test_storage/test_audit.py tests/test_privacy.py -q`
  - `22 passed`
- `.venv/bin/pytest tests/test_api/test_corpus_routes.py -q`
  - `2 passed`
- `.venv/bin/pytest tests/test_corpus/test_status_contract.py tests/test_api/test_corpus_routes.py -q`
  - `6 passed`
- Scoped `ruff check` on changed API, CLI, corpus, MCP, and test files.
- `.venv/bin/python -m compileall -q src/rag_ocpp`
- `git diff --check`
- Live uvicorn smoke tests with curl:
  - `GET /health`
  - `GET /openapi.json`
  - `GET /corpus/status`
  - `GET /documents`
  - `GET /entities/DeviceDataCtrlr`
  - `GET /search`
  - `POST /query`
  - `POST /query/stream`
  - admin guard checks for `/corpus/*`, `/ingest`, and `/documents/{id}`

## Known Gaps

- Corpus preview/store/index still run synchronously in the API; production
  operation should move these to explicit background jobs with job records.
- Full API/CLI/MCP generated-answer Markdown parity is still pending.
- Source-level ACLs, tenant isolation, retention/deletion policy, and
  secret-handling policy remain future enterprise controls.
- Eval coverage remains strongest for Section R DER, Section Q V2X, and Section
  K smart charging; broader OCPP 2.1 Ed2 coverage is still pending.
- CI wiring for API smoke tests, retrieval quality, golden answers, and
  migrations remains pending.
- Local broad ruff checks still expose older unrelated style debt in legacy CLI
  modules outside the v0.3.0 API work.

## Recommended Tag

```text
v0.3.0
```

## Recommended Release Commit Message

```text
release: publish v0.3.0 FastAPI access surface
```

# v0.2.0 - Enterprise Control Plane: Privacy, Audit, and DB Migrations

## Release Title

Enterprise Control Plane for OCPP 2.1 Ed2 Knowledge Backend

## Release Description

`v0.2.0` moves the OCPP 2.1 Ed2 RAG/KAG backend beyond evaluation baselines into enterprise-control foundations. This release adds configurable private-knowledge protections, privacy-preserving audit events, repaired storage/retrieval integration tests, and explicit PostgreSQL migrations with a migration ledger.

The release keeps the existing R/Q/K retrieval and golden-answer benchmarks from `v0.1.2`, then strengthens the operational substrate needed for private enterprise knowledge: safer logging, auditable access events, reproducible schema setup, and documented legacy database adoption.

## Highlights

- Added configurable redacted logging for private source text, prompts, answers, secrets, and long payloads.
- Added privacy-preserving audit events for:
  - query
  - retrieval
  - generation
  - corpus ingestion/indexing
  - MCP access
- Added `audit_events` storage and audit helpers that store hashes, lengths, IDs, counts, status, latency, and redacted metadata instead of raw private text.
- Repaired retrieval/storage integration tests with deterministic document IDs and 1024-dimensional embeddings.
- Added explicit SQL migration runner with `schema_migrations` ledger.
- Added migration CLI commands:
  - `rag migrate-status`
  - `rag migrate --dry-run`
  - `rag migrate`
  - `rag migrate --baseline`
- Added migration `001_initial_schema.sql` for fresh databases.
- Added migration `002_ensure_audit_events.sql` for legacy databases missing `audit_events`.
- Added `docs/db_migrations.md` with fresh DB setup and legacy baseline adoption flows.
- Updated `docs/HANDOFF.md` and `docs/AUDIT_REPORT.md` to reflect current enterprise-control status.

## Operator Guidance

For a fresh empty database:

```bash
docker compose up -d
.venv/bin/rag migrate --dry-run
.venv/bin/rag migrate
.venv/bin/rag migrate-status
```

For an existing local database created before migrations existed:

```bash
.venv/bin/rag migrate --baseline
.venv/bin/rag migrate --dry-run
.venv/bin/rag migrate
.venv/bin/rag migrate-status
```

Expected final migration state:

```text
001 initial_schema: applied at <timestamp>
002 ensure_audit_events: applied at <timestamp>
```

## Validation

Validated locally with:

- `.venv/bin/pytest tests/test_storage/test_migrations.py -q`
  - `2 passed`
- `.venv/bin/pytest tests/test_storage/test_migrations.py tests/test_storage/test_audit.py tests/test_privacy.py -q`
  - `10 passed`
- `.venv/bin/ruff check src/rag_ocpp/storage/migrations.py src/rag_ocpp/cli/db.py src/rag_ocpp/cli/main.py tests/test_storage/test_migrations.py`
- `.venv/bin/python -m compileall -q src/rag_ocpp`
- `.venv/bin/rag migrate --help`
- `git diff --check`

## Known Gaps

- Source-level ACLs, tenant isolation, retention/deletion policy, and secret-handling policy are still not complete.
- API, CLI, and MCP generated-answer behavior still need full alignment with the golden-answer Markdown and citation contract.
- Eval coverage is still concentrated on Section R DER, Section Q V2X, and Section K smart charging.
- CI wiring for migration tests, retrieval quality, and golden-answer gates remains pending.
- Migration rollback, backup, restore, and re-embedding operational runbooks still need to be formalized.
- `mypy` could not be used in the local Python environment because the interpreter build is missing `_sqlite3`, which causes mypy 2.1.0 to fail before checking project code.

## Recommended Tag

```text
v0.2.0
```

## Recommended Release Commit Message

```text
release: publish v0.2.0 enterprise controls
```

# v0.1.2 - OCPP 2.1 Ed2 Evaluation and Golden Answer Benchmarks

## Release Title

OCPP 2.1 Ed2 Evaluation and Golden Answer Benchmarks

## Release Description

`v0.1.2` promotes the OCPP 2.1 Ed2 knowledge backend from an indexed RAG/KAG foundation to a measurable evaluation baseline. It adds repeatable retrieval quality gates for Section R DER control, Section Q V2X energy services, and Section K smart charging, then adds golden Markdown answer evaluation to verify generated implementation guidance quality beyond retrieval coverage.

This release also introduces provider-neutral answer benchmarking. DeepSeek-generated answers remain the source-rich baseline, while Codex-assisted answers are generated from MCP evidence tools and scored offline without DeepSeek or OpenAI API calls from the repo CLI.

## Highlights

- Added `rag eval-quality` source-aware retrieval evaluation for 12 R/Q/K cases:
  - `spec`
  - `dm`
  - `schema`
  - `fusion`
- Added `rag eval-answers` golden Markdown answer evaluation for fusion implementation guidance.
- Added strict generated-answer sections:
  - Purpose
  - Normative behavior
  - Implementation guidance
  - Conformance-test focus
  - Evidence gaps
- Added strict golden-answer prompting for generated Markdown answers.
- Added cached/offline answer scoring with `--from-answers-dir`.
- Added DeepSeek golden answer baseline reports.
- Added Codex-assisted MCP-evidence benchmark answers and offline scoring reports.
- Added DeepSeek vs Codex-only benchmark comparison.
- Documented the MCP-assisted manual benchmark workflow for Codex and other coding agents.

## Reports

- `reports/ocpp21-ed2-rqk-quality-baseline.md`
  - Retrieval suite: `12/12` passed
  - Score: `0.976`
- `reports/ocpp21-ed2-rqk-golden-answers.md`
  - DeepSeek generated-answer suite: `3/3` passed
  - Score: `1.000`
- `reports/ocpp21-ed2-rqk-golden-answers-codex-only.md`
  - Codex-assisted MCP-evidence answer suite: `3/3` passed
  - Score: `1.000`
- `reports/ocpp21-ed2-rqk-golden-answers-benchmark.md`
  - DeepSeek vs Codex-only comparison
  - DeepSeek citations: `50`
  - Codex-only citations: `28`

## Validation

Validated locally with:

- `HF_HOME=./models .venv/bin/rag eval-quality --top-k 12 --fail-under 0.80`
- `HF_HOME=./models .venv/bin/rag eval-answers --from-answers-dir --answers-dir reports/golden_answers --output reports/ocpp21-ed2-rqk-golden-answers.md`
- `HF_HOME=./models .venv/bin/rag eval-answers --from-answers-dir --answers-dir reports/golden_answers_codex-only --output reports/ocpp21-ed2-rqk-golden-answers-codex-only.md`
- Targeted eval tests for golden-answer scoring and query quality.
- Python compile checks for `src/rag_ocpp`.

## Known Gaps

- Automated scoring still checks structure, required terms, citation shape, and grounding signals; it does not yet prove full protocol correctness.
- Expert validation status is not yet modeled as a first-class approval field.
- Citation precision scoring needs to become stricter: exact requirement IDs, schema paths, and unsupported-claim detection.
- OpenAI/Codex generation is currently a Codex-assisted manual MCP workflow, not a repo CLI provider.
- CI wiring for retrieval and golden-answer gates is still pending.

## Recommended Tag

```text
v0.1.2
```

## Recommended Release Commit Message

```text
release: publish v0.1.2 evaluation baseline
```
