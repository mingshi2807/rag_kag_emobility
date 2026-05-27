# Changelog

All notable changes to this project will be documented in this file.

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
