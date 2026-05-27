# v0.1.0-wip - OCPP 2.1 Ed2 Source-Aware RAG/KAG Foundation

## Release Description

This WIP release establishes the first enterprise-oriented OCPP 2.1 Edition 2 knowledge backend foundation. It focuses on source-aware ingestion, retrieval, generation, and MCP exposure for the OCPP Part 2 specification, Device Model data, and JSON schemas.

The release is intended as a working baseline for private knowledge backend validation before moving into query quality evaluation, regression scoring, and expert validation workflows.

## Highlights

- Added source-aware corpus ingestion for OCPP 2.1 Ed2 evidence layers:
  - Part 2 specification PDF
  - Device Model CSV/XLSX data
  - JSON schemas
- Added corpus storage model for documents, records, chunks, embeddings, entities, and relationships.
- Added full embedding-based indexing flow for the OCPP corpus.
- Improved hybrid retrieval with evidence-layer filtering and better OCPP-specific routing.
- Improved Markdown answer generation for implementation-oriented RAG queries.
- Added DeepSeek configuration hardening with explicit `deepseek-v4-pro` defaults.
- Added project-local Codex skills for repeatable RAG/KAG improvement, review, query evaluation, implementation guide, and smoke testing.
- Exposed the OCPP knowledge backend through MCP for Codex and other coding agents.

## MCP Tooling

The MCP server now exposes source-aware tools for coding agents, including:

- `search_ocpp_knowledge`
- `get_ocpp_evidence_pack`
- `build_ocpp_implementation_brief`
- `inspect_ocpp_corpus`
- `get_ocpp_chunk`
- `list_ocpp_entities`
- `get_ocpp_entity`
- `list_ocpp_documents`
- `search_ocpp_by_section`

## Validation

Validated locally with:

- Python compile check
- Corpus indexing smoke validation
- Targeted corpus tests
- MCP server tool import check
- DB-backed MCP handler smoke checks

## Known Gaps

- Query quality evaluation suite is not yet implemented.
- Retrieval quality still needs measurable regression tests.
- Expert review and validation workflow is documented as direction but not fully automated.
- Conformance-test-oriented answer templates need further hardening.
- Enterprise access control, audit logs, and multi-tenant governance are future milestones.

## Recommended Tag

```text
v0.1.0-wip
```

## Recommended Release Commit Message

```text
release: publish v0.1.0-wip OCPP knowledge backend baseline
```
