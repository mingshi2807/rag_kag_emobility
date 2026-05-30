# Changelog

All notable changes to this project will be documented in this file.

## [v0.4.0] - 2026-05-30

### Added

- Added a lightweight source-aware ontology catalog for OCPP 2.1 Ed2 evidence
  relationships across Part 2 specification sections, Device Model
  components/variables, and JSON schema payload paths.
- Added ontology-aware graph promotion for fusion retrieval.
- Added ontology metrics to retrieval quality reports, including graph
  candidate chunks, graph candidate semantic links, final graph chunks, and
  traversal depth.
- Added ontology provenance in API/MCP evidence packs for downstream coding
  agents and clients.
- Added ontology-aware generation prompt guidance for implementation traces:
  `spec behavior -> Device Model component/variable -> JSON schema payload`.
- Added golden-answer scoring for ontology trace quality and missing-link
  disclosure.

### Changed

- Updated generated-answer evaluation weighting so source-layer traceability is
  part of the pass/fail contract.
- Updated saved DeepSeek and Codex-only golden-answer reports under the stricter
  ontology trace rubric.
- Updated query-quality documentation to explain ontology trace scoring and
  missing-link disclosure.
- Updated handoff documentation to reflect ontology-aware retrieval,
  generation, reporting, and answer scoring.

### Verified

- Ontology-aware retrieval quality report: `12/12` passed, score `0.976`.
- DeepSeek saved-answer evaluation: `3/3` passed, score `0.990`.
- Codex-only saved-answer evaluation: `3/3` passed, score `0.992`.
- Golden-answer tests: `13/13` passed.
- Scoped ruff checks passed on changed ontology, retrieval, generation, and
  answer-evaluation files.
- Scoped mypy checks passed on changed generation and answer-evaluation files.
- Python compile checks passed for `src/rag_ocpp`.
- `git diff --check` passed.

### Known Limitations

- API/CLI/MCP generated-answer Markdown parity is still not complete.
- The ontology is currently a practical source-aware traceability layer, not a
  complete formal protocol ontology.
- Source ACLs, tenant isolation, retention/deletion policy, and secret-handling
  policy remain future work.
- Broader OCPP 2.1 Ed2 evaluation beyond R/Q/K remains future work.
- CI wiring for ontology-aware retrieval and golden-answer gates remains
  pending.

## [v0.3.0] - 2026-05-28

### Added

- Added source-aware FastAPI query/search response controls for `top_k`,
  `doc_type`, `evidence_layer`, `source_type`, content inclusion, answer
  inclusion, and query echoing.
- Added source metadata in API chunk responses: evidence layer, source type,
  source path, and content hash.
- Added correlation IDs and privacy-preserving query references to API query and
  search responses.
- Added admin bearer-token guard for mutating FastAPI endpoints through
  `API_ADMIN_TOKEN`.
- Added dedicated source-aware corpus API endpoints:
  - `GET /corpus/status`
  - `POST /corpus/preview`
  - `POST /corpus/store`
  - `POST /corpus/index`
- Added shared corpus status contract across API, CLI, and MCP with
  `src/rag_ocpp/corpus/status.py`.
- Added `rag corpus-status`.
- Added API/CLI/MCP corpus status contract tests.
- Added curl and Postman smoke-test documentation in
  `docs/api_http_client_tests.md`.

### Changed

- Bumped package version and FastAPI OpenAPI metadata to `0.3.0`.
- Regenerated `api.json` as OpenAPI `3.0.3` with API version `0.3.0`.
- Marked `POST /ingest` as a legacy admin direct-ingestion endpoint.
- Updated README and handoff documentation to reference the HTTP client smoke
  test process and source-aware corpus API flow.
- Updated MCP `inspect_ocpp_corpus` to use the shared corpus status helper.
- Updated API `GET /corpus/status` to use the shared corpus status helper.

### Fixed

- Fixed API query/search `top_k` handling so request limits are passed into
  retrieval.
- Fixed API generation failures to return redacted structured errors instead of
  leaking internal exception details.
- Fixed corpus status drift risk by removing separate API and MCP status SQL
  implementations.

### Verified

- API, corpus-status contract, audit, and privacy test group: `22/22` passed.
- Corpus route tests: `2/2` passed.
- Corpus status plus corpus route contract group: `6/6` passed.
- Scoped ruff checks passed on changed API, CLI, corpus, MCP, and test files.
- Python compile checks passed for `src/rag_ocpp`.
- `git diff --check` passed.
- Live uvicorn curl smoke tests passed for health, OpenAPI, corpus status,
  documents, entity lookup, search, generation, streaming generation, admin
  guard failures, and safe admin no-op/not-found checks.

### Known Limitations

- Corpus preview/store/index remain synchronous API operations and need
  background job records before production use.
- Full API/CLI/MCP generated-answer Markdown parity is not complete.
- Source ACLs, tenant isolation, retention/deletion policy, and secret-handling
  policy remain future work.
- CI wiring for API smoke tests, eval-quality, eval-answers, and migrations is
  still pending.
- Broad ruff checks still report older unrelated style debt in legacy CLI
  modules outside this release scope.

## [v0.2.0] - 2026-05-28

### Added

- Added configurable redacted logging for private source text, prompts, generated answers, secrets, and long payloads.
- Added privacy-preserving audit event storage for query, retrieval, generation, corpus ingestion/indexing, and MCP access.
- Added explicit PostgreSQL migration runner with `schema_migrations` ledger.
- Added migration CLI commands: `rag migrate-status`, `rag migrate --dry-run`, `rag migrate`, and `rag migrate --baseline`.
- Added initial schema migration `001_initial_schema.sql`.
- Added legacy repair migration `002_ensure_audit_events.sql` for databases missing `audit_events`.
- Added `docs/db_migrations.md` with fresh database setup and legacy baseline adoption flows.
- Added Docker-backed migration tests for fresh apply and legacy baseline-plus-repair behavior.

### Changed

- Updated package data so storage SQL and migration files are included with the Python package.
- Updated handoff and audit documentation to reflect redaction, audit events, repaired retrieval tests, and explicit migrations.
- Updated enterprise-readiness framing: migrations are now implemented, while source ACLs, retention/deletion policy, CI wiring, and broader contract tests remain open.

### Fixed

- Fixed legacy migration adoption for databases that already have the core schema but no migration ledger.
- Fixed the missing `audit_events` table path by adding an idempotent repair migration.
- Repaired retrieval/storage integration tests to use inserted document UUIDs and deterministic 1024-dimensional embeddings.

### Verified

- Migration tests: `2/2` passed.
- Migration, audit, and privacy test group: `10/10` passed.
- Ruff checks passed on the touched migration, CLI, and test files.
- Python compile checks passed for `src/rag_ocpp`.
- CLI help confirms `rag migrate` and `rag migrate-status` are available.
- `git diff --check` passed.

### Known Limitations

- Source-level ACLs, tenant isolation, retention/deletion policy, and secret-handling policy are still future work.
- API, CLI, and MCP generated-answer behavior still needs full golden-answer Markdown and citation contract alignment.
- Eval coverage remains strongest for Section R DER, Section Q V2X, and Section K smart charging; broader OCPP 2.1 Ed2 coverage is still pending.
- CI wiring for migration tests, retrieval quality, and golden-answer gates remains future work.
- Migration rollback, backup, restore, and re-embedding runbooks still need to be formalized.
- Local `mypy` validation is blocked by the Python interpreter missing `_sqlite3`, which makes mypy fail before project type checking starts.

## [v0.1.2] - 2026-05-27

### Added

- Added source-aware `rag eval-quality` suite for 12 OCPP 2.1 Ed2 R/Q/K cases across specification, Device Model, JSON schema, and fusion retrieval modes.
- Added `rag eval-answers` golden Markdown answer evaluation for generated implementation guidance.
- Added strict golden-answer sections: Purpose, Normative behavior, Implementation guidance, Conformance-test focus, and Evidence gaps.
- Added cached/offline answer scoring with `--from-answers-dir`.
- Added DeepSeek generated-answer baseline reports in `reports/golden_answers/`.
- Added Codex-assisted MCP-evidence benchmark answers in `reports/golden_answers_codex-only/`.
- Added DeepSeek vs Codex-only golden-answer benchmark report.

### Changed

- Hardened generation prompting for golden-answer evaluation with implementation-guidance and conformance-test expectations.
- Updated MCP and query-quality documentation with the Codex-assisted manual benchmark workflow.
- Updated handoff state to reflect retrieval and generated-answer evaluation gates.

### Verified

- Retrieval quality baseline: `12/12` passed, score `0.976`.
- DeepSeek golden answers: `3/3` passed, score `1.000`.
- Codex-assisted MCP golden answers: `3/3` passed, score `1.000`.
- DeepSeek vs Codex-only benchmark completed: DeepSeek `50` citations, Codex-only `28` citations.

### Known Limitations

- Golden-answer scoring is necessary but not sufficient to prove full OCPP protocol correctness.
- Citation precision and unsupported-claim detection still need stricter scorer layers.
- OpenAI/Codex generation remains a Codex-assisted manual MCP workflow, not a repo CLI provider.
- CI wiring for retrieval and golden-answer gates remains future work.

## [v0.1.0-wip] - 2026-05-27

### Added

- Added source-aware OCPP 2.1 Ed2 corpus ingestion foundation.
- Added support for three evidence layers:
  - OCPP 2.1 Ed2 Part 2 specification PDF
  - Device Model CSV/XLSX files
  - JSON schema files
- Added corpus storage for sources, records, chunks, embeddings, entities, entity links, and relationships.
- Added corpus indexing CLI flow with embedding generation.
- Added evidence-layer-aware RAG query support.
- Added OCPP-specific retrieval improvements for Device Model, schemas, message definitions, and implementation-oriented queries.
- Added Markdown-constrained generation prompts for clearer implementation answers.
- Added DeepSeek model configuration defaults for `deepseek-v4-pro`.
- Added safe model logging for generation and extraction requests.
- Added project-local Codex skills for:
  - RAG/KAG continuous improvement
  - OCPP expert review
  - Query evaluation
  - Implementation guide generation
  - Smoke testing
- Added MCP tooling for external coding agents to access the OCPP knowledge backend.
- Added MCP documentation and handoff updates.

### Changed

- Improved hybrid retrieval scoring with evidence-layer and source-type awareness.
- Improved query CLI output with source metadata.
- Improved source metadata propagation through retrieval and generation.
- Updated documentation to reflect current OCPP 2.1 Ed2 backend status.

### Fixed

- Fixed embedding model cache path handling to use configured model paths instead of hardcoded local assumptions.
- Fixed stale DeepSeek model references in documentation and configuration.
- Fixed PostgreSQL Docker host port conflict by using an alternate bind port.

### Verified

- Corpus indexing completed successfully with embedded chunks.
- MCP server exposes the expected OCPP knowledge tools.
- Targeted corpus tests pass.
- Python source compilation passes.

### Known Limitations

- Query evaluation suite is not yet implemented.
- Retrieval ranking still needs systematic scoring and regression protection.
- Expert validation workflow is not yet fully automated.
- Enterprise governance features such as access control, audit trails, and policy enforcement remain future work.
