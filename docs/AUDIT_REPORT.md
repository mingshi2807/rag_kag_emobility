# Enterprise Audit Report: RAG/KAG E-Mobility Knowledge Base

**Date:** 2026-05-25
**Scope:** Local repository audit of source, config, tests, and every file under `docs/`.
**Purpose:** Assess readiness for an enterprise private knowledge base using LLM, RAG, and KAG integration.

## Verdict

The repository is a credible prototype, not an enterprise-grade private knowledge platform yet.

The strongest parts are the direct Python implementation, hybrid retrieval design, PostgreSQL plus pgvector consolidation, graph schema foundation, API/CLI/MCP access surfaces, and documented intent. The weakest parts are enterprise controls: measurable quality gates, schema migrations, private-data safeguards, SQL hardening, reproducibility, and current-state documentation accuracy.

## Strict Criteria

| Criterion | Status | Evidence | Enterprise Risk |
| --- | --- | --- | --- |
| Source-grounded retrieval | Partial | Vector, keyword, graph, RRF, rerank pipeline exists. | No verified baseline means answer quality cannot be governed. |
| KAG graph fidelity | Partial | Entity and relationship tables exist. | Relationship quality, provenance, and traversal precision are not measured. |
| Private-data protection | Weak | Config reads secrets from env and `.env`. | No documented redaction, access control, retention, tenant isolation, or prompt/context logging policy. |
| Reproducibility | Weak | Docker, CLI, and install docs exist. | No migration system, missing README target, stale docs, and model/schema drift. |
| Evaluation governance | Weak | Eval tooling is referenced. | Handoff says eval UUIDs are stale and baseline is unknown. |
| Operational reliability | Weak | API, CLI, MCP are present. | No runbook for backup, restore, re-index, rollback, model cache, or cold-start management. |
| Security posture | Weak | Basic env-based secrets are used. | Dynamic SQL uses raw query terms in keyword and graph fallbacks. |
| Documentation accuracy | Weak | `/docs` has useful design notes. | Several docs contradict current config and schema. |

## Evidence

- `pyproject.toml` declares Python 3.12, production dependencies, dev dependencies, and scripts `rag` plus `rag-mcp`.
- `config/default.yaml` sets `BAAI/bge-large-en-v1.5`, `dims: 1024`, and spec chunking as `recursive` with `chunk_size: 1024`.
- `src/rag_ocpp/storage/schema.sql` still declares `embedding VECTOR(768)`.
- `docs/ingest.md` describes SDPM chunking, 512-token chunks, 64 overlap, BGE-base, GPU batch 256, and 768-dimensional memory estimates.
- `docs/dev_journey.md` describes BGE-base 768-dimensional architecture and SDPM 512/64 chunking.
- `docs/HANDOFF.md` reported functional hybrid retrieval but unknown eval scores and stale eval UUIDs.
- `docs/mcp.md` documents six MCP tools, stdio-only transport, OCPP-only scope, and no ingest tools.
- `src/rag_ocpp/storage/vector.py` builds ILIKE fallback SQL with raw query words.
- `src/rag_ocpp/storage/graph.py` builds entity-name fallback SQL with raw query words and traversal relation filters through string interpolation.
- `tests/test_retrieval/test_vector_search.py` creates random document UUIDs after inserting documents instead of using the returned document ID.

## Ranked Findings

### 1. Schema, Config, and Docs Are Inconsistent

**Severity:** Critical
**Confidence:** High

The runtime config expects 1024-dimensional BGE-large embeddings, while the schema file still creates `VECTOR(768)`. `/docs` still contains older BGE-base and SDPM/512-token assumptions. This can break fresh database setup, confuse future re-ingestion, and make audit evidence unreliable.

**Required improvement:** Introduce explicit DB migrations, align schema to the chosen embedding model, update all docs, and record the re-embedding procedure.

### 2. Retrieval Quality Is Not Governed

**Severity:** Critical
**Confidence:** High

The handoff says eval scores are unknown and UUIDs need regeneration. Without Recall@k, MRR, NDCG, source coverage, citation accuracy, and answer faithfulness checks, retrieval tuning is not enterprise-controlled.

**Required improvement:** Version `data/eval/queries.jsonl`, regenerate valid ground truth, store metrics artifacts, and fail CI on regressions after a baseline is accepted.

### 3. SQL Construction Is Unsafe for Enterprise Inputs

**Severity:** Critical
**Confidence:** High

Keyword ILIKE fallback and graph entity fallback interpolate query terms into SQL. Graph traversal interpolates relation filters and max depth. Even if inputs are usually internal, enterprise private-knowledge systems must treat queries and MCP tool inputs as untrusted.

**Required improvement:** Parameterize fallback SQL, validate relation types against an allowlist, clamp numeric bounds, and add regression tests for hostile query strings.

### 4. Private Knowledge Controls Are Missing

**Severity:** High
**Confidence:** High

The system handles proprietary protocol documents and generated answers, but there is no documented access model, data classification, redaction, log policy, prompt retention policy, audit-event schema, or source-level authorization.

**Required improvement:** Add a privacy/security design doc, implement redacted structured logging, avoid storing raw prompts/context by default, and add source ACL metadata before multi-user use.

### 5. Tests Do Not Establish Enterprise Confidence

**Severity:** High
**Confidence:** Medium

Tests exist for chunking, ingestion cleaning, metadata, extraction, and vector search, but the retrieval integration test appears to use wrong document IDs. Docker-backed tests may skip entirely. There are no API/MCP contract tests, generation safety tests, migration tests, or retrieval quality tests.

**Required improvement:** Repair integration fixtures, add API/MCP contract tests, add eval tests, and record skipped integration tests as an explicit CI signal.

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

1. **Stabilize the data contract.** Fix embedding dimension drift, add migrations, document the active model/chunking contract, and update stale docs.
2. **Close SQL safety gaps.** Parameterize keyword and graph fallback queries, validate traversal inputs, and add hostile-input tests.
3. **Repair the test baseline.** Fix document IDs in retrieval tests, run unit tests, and make Docker skips visible in CI.
4. **Create the eval gate.** Build a curated e-mobility query set with expected chunks, entities, protocols, and citation requirements. Track Recall@5/10, MRR, NDCG, graph contribution, latency, and hallucination checks.
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

- Fresh database setup succeeds from migrations.
- Config, schema, docs, and model dimensions agree.
- Retrieval has a recorded baseline and regression gate.
- SQL hardening is complete for query/MCP/API inputs.
- Private-data logging, retention, ACL, and audit policies are implemented.
- API, CLI, and MCP contracts are tested.
- Operational runbooks exist and have been smoke-tested.
