# Changelog

All notable changes to this project will be documented in this file.

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
