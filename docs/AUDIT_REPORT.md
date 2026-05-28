# Enterprise Audit Report: RAG/KAG E-Mobility Knowledge Base

**Date:** 2026-05-28
**Scope:** Local repository audit of source, config, tests, and every file under `docs/`.
**Purpose:** Assess readiness for an enterprise private knowledge base using LLM, RAG, and KAG integration.

## Verdict

The repository is a credible prototype, not an enterprise-grade private knowledge platform yet.

The strongest parts are the direct Python implementation, hybrid retrieval design, PostgreSQL plus pgvector consolidation, graph schema foundation, API/CLI/MCP access surfaces, admin-controlled API mutation endpoints, source-aware corpus API operations, explicit DB migrations, OpenAPI reference output, and documented intent. The weakest remaining parts are enterprise controls: source-level access control, retention/deletion policy, CI wiring, broader MCP contract tests, and operational runbooks.

## Strict Criteria

| Criterion | Status | Evidence | Enterprise Risk |
| --- | --- | --- | --- |
| Source-grounded retrieval | Partial | Vector, keyword, graph, RRF, rerank pipeline and R/Q/K eval baselines exist. | Coverage is still narrow outside the initial R/Q/K topics. |
| KAG graph fidelity | Partial | Entity and relationship tables exist. | Relationship quality, provenance, and traversal precision are not measured. |
| Private-data protection | Partial | Redacted logging, privacy-preserving audit events, and API admin mutation guards exist. | Source ACLs, retention/deletion policy, and tenant isolation are not complete. |
| Reproducibility | Partial | Docker, CLI, migration commands, and install docs exist. | Docker bootstrap still uses `schema.sql`; broader rollback, backup, restore, and CI migration gates are not complete. |
| Evaluation governance | Partial | Retrieval and generated-answer eval reports exist for R/Q/K topics. | Eval gates are not wired to CI and coverage beyond R/Q/K remains limited. |
| Operational reliability | Partial | API, CLI, MCP, migrations, and API contract tests are present. | No runbook for backup, restore, re-index, rollback, model cache, or cold-start management. |
| Security posture | Partial | Basic env-based secrets, SQL parameterization hardening, redacted logs, and audit events exist. | Source ACLs, retention controls, and API/MCP contract tests are still incomplete. |
| Documentation accuracy | Weak | `/docs` has useful design notes. | Several docs contradict current config and schema. |

## Evidence

- `pyproject.toml` declares Python 3.12, production dependencies, dev dependencies, and scripts `rag` plus `rag-mcp`.
- `config/default.yaml` sets `BAAI/bge-large-en-v1.5`, `dims: 1024`, and spec chunking as `recursive` with `chunk_size: 1024`.
- `src/rag_ocpp/storage/schema.sql` declares `embedding VECTOR(1024)`.
- `src/rag_ocpp/storage/migrations.py` and `src/rag_ocpp/storage/migrations/` provide explicit SQL migrations tracked in `schema_migrations`, including legacy repair for missing `audit_events`.
- `docs/db_migrations.md` documents fresh DB migration setup and legacy `schema.sql` baseline adoption.
- `docs/ingest.md` describes SDPM chunking, 512-token chunks, 64 overlap, BGE-base, GPU batch 256, and 768-dimensional memory estimates.
- `docs/dev_journey.md` describes BGE-base 768-dimensional architecture and SDPM 512/64 chunking.
- `docs/HANDOFF.md` reports implemented retrieval quality evals, generated-answer evals, redacted logging, audit events, and migrations.
- `api.json` exports the FastAPI reference as OpenAPI `3.0.3`.
- `tests/test_api/` covers API query/search contract behavior, admin mutation guards, source-aware corpus API behavior, and exported OpenAPI schema drift.
- Mutating API endpoints require configured `API_ADMIN_TOKEN` bearer auth; otherwise they are disabled.
- `POST /corpus/preview`, `POST /corpus/store`, and `POST /corpus/index` provide the preferred source-aware OCPP corpus API path. `GET /corpus/status` exposes read-only corpus/index counts.
- `docs/mcp.md` documents nine MCP read tools and the Codex-assisted manual benchmark workflow.
- `src/rag_ocpp/storage/vector.py` and `src/rag_ocpp/storage/graph.py` parameterize keyword/entity fallback SQL paths.
- `tests/test_retrieval/test_vector_search.py` uses inserted document UUIDs and deterministic 1024-dimensional embeddings.

## Ranked Findings

### 1. Schema, Config, and Docs Still Need Full Lifecycle Governance

**Severity:** High
**Confidence:** Medium

The runtime config and schema now agree on 1024-dimensional BGE-large embeddings, and explicit migrations exist. `/docs` still contains older BGE-base and SDPM/512-token assumptions, and Docker Compose still bootstraps local databases from `schema.sql` for compatibility.

**Required improvement:** Keep migrations as the authoritative schema path, refresh stale historical docs, add rollback/backup/restore runbooks, and record the re-embedding procedure.

### 2. Retrieval Quality Governance Is Still Narrow

**Severity:** Critical
**Confidence:** High

R/Q/K retrieval quality and generated-answer baselines exist, but they focus on Section R DER, Section Q V2X, and Section K smart charging. Without broader protocol coverage and CI enforcement, retrieval tuning is not fully enterprise-controlled.

**Required improvement:** Extend eval cases beyond R/Q/K, store metrics artifacts, and fail CI on regressions after the CI/model/API assumptions are ready.

### 3. Input Contract Hardening Is Incomplete

**Severity:** High
**Confidence:** Medium

Keyword/entity fallback SQL paths have been parameterized, but enterprise private-knowledge systems must still treat CLI, API, and MCP inputs as untrusted across all access surfaces.

**Required improvement:** Add shared API/CLI/MCP validation, broaden hostile-input tests, validate relation types against an allowlist, and clamp numeric bounds.

### 4. Private Knowledge Controls Are Missing

**Severity:** High
**Confidence:** High

The system handles proprietary protocol documents and generated answers. Redacted logging, audit events, and private-knowledge control documentation now exist, but there is no complete source-level authorization, deletion, retention, or tenant-isolation model.

**Required improvement:** Add source ACL metadata before multi-user use, define retention/deletion behavior, and keep avoiding raw prompt/context/source logging by default.

### 5. Tests Do Not Establish Enterprise Confidence

**Severity:** High
**Confidence:** Medium

Tests exist for chunking, ingestion cleaning, metadata, extraction, vector search, audit events, migrations, and FastAPI query/search contracts. Docker-backed tests may skip entirely. MCP contract tests and broader generation safety tests are still incomplete.

**Required improvement:** Add MCP contract tests, broaden eval tests, and record skipped integration tests as an explicit CI signal.

### 6. Operations Are Under-Specified

**Severity:** High
**Confidence:** High

Docs explain how to run pieces, but there is no enterprise runbook for ingestion jobs, re-embedding, model cache warming, backup/restore, rollback, credential rotation, index rebuilds, or incident response.

**Required improvement:** Add operational runbooks and make long-running jobs resumable, idempotent, and observable.

### 7. API, CLI, and MCP Need Contract Alignment

**Severity:** Medium
**Confidence:** Medium

MCP docs say `top_k` defaults to 5 and maxes at 20, while server startup initializes the retriever with `final_top_k=20` and the search handler does not pass `top_k` into retrieval. Similar limits and filters should be verified across API, CLI, and MCP.

**Required improvement:** Define one retrieval contract and enforce it in all access surfaces with shared validation.

## Ordered Improvement Roadmap

1. **Stabilize the data contract lifecycle.** Keep schema changes migration-first, document rollback/re-embedding, and update stale docs.
2. **Close remaining input-contract gaps.** Share API/CLI/MCP validation, validate traversal inputs, and add hostile-input tests.
3. **Broaden the test baseline.** Add API/MCP contract tests, run unit tests, and make Docker skips visible in CI.
4. **Expand the eval gate.** Extend curated e-mobility query sets with expected chunks, entities, protocols, and citation requirements. Track Recall@5/10, MRR, NDCG, graph contribution, latency, and hallucination checks.
5. **Add privacy controls.** Define data classes, source ACLs, secret handling, redacted logging, prompt/context retention, deletion, and audit events.
6. **Make ingestion production-grade.** Add idempotent job records, chunk provenance, checksum manifests, failed-page capture, reprocessing controls, and source versioning.
7. **Improve KAG quality.** Add relationship provenance, confidence calibration, entity alias governance, cross-protocol mapping review, and traversal explainability.
8. **Improve answer trust.** Require citations, separate retrieved evidence from generated synthesis, include abstention behavior, and add answer faithfulness evaluation.
9. **Optimize serving.** Keep models warm in API/MCP process, measure cold/warm latency separately, tune reranking, and add cache boundaries that respect private-data controls.
10. **Prepare enterprise operation.** Add backup/restore, index rebuild, model upgrade, credential rotation, incident response, and release checklists.

## Documentation Review

- `docs/HANDOFF.md`: Now updated as the control document. Keep it current after every operationally meaningful change.
- `docs/dev_journey.md`: Useful historical map, but stale for current embedding and chunking. Refresh or mark historical.
- `docs/ingest.md`: Useful scale thinking, but stale for current config and model dimensions. Recalculate after the schema/config decision.
- `docs/mcp.md`: Useful MCP surface documentation. Needs contract checks against implementation, especially `top_k`, filters, and OCPP-only assumptions.
- `docs/plan_note.md`: Useful as an original build plan. Mark historical if it is no longer the active implementation state.

## Stop Condition for Enterprise Readiness

This project should not be treated as enterprise-ready until all of the following are true:

- Fresh database setup succeeds from migrations and migration tests run in CI.
- Config, schema, docs, and model dimensions agree.
- Retrieval has a recorded baseline and regression gate.
- Input validation and hostile-input tests are complete for query/MCP/API inputs.
- Private-data logging, retention, ACL, and audit policies are implemented.
- API, CLI, and MCP contracts are tested.
- Operational runbooks exist and have been smoke-tested.
