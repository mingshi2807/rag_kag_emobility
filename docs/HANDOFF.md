# Handoff: RAG-KAG-OCPP Repository Control

**Date:** 2026-05-25
**Control status:** Repo reviewed from local checkout. Root `AGENTS.md` now defines agent operating rules. Enterprise audit is captured in `docs/AUDIT_REPORT.md`.
**Current conclusion:** The project has a coherent RAG/KAG prototype, but it is not yet enterprise-grade for private knowledge operation. The blocking work is evaluation, schema/config drift, SQL hardening, private-data controls, and operational reproducibility.

## Mission

Build a private e-mobility knowledge base with LLM, RAG, and KAG integration for OCPP first, then broader protocol coverage. The required product bar is answer traceability, private-data protection, reproducible ingestion, measurable retrieval quality, and stable API/CLI/MCP access.

## Current Architecture

```
PDF/JSON -> parser -> cleaner -> metadata -> chunking
        -> embeddings -> PostgreSQL + pgvector
        -> entity extraction/linking -> graph tables

Query -> vector + keyword + graph retrieval
      -> weighted RRF -> reranker -> top chunks
      -> DeepSeek generation / API / CLI / MCP
```

## Current Evidence Snapshot

- `pyproject.toml` defines a Python 3.12 package named `rag-kag-ocpp` with CLI entries `rag` and `rag-mcp`.
- `config/default.yaml` currently sets BGE-large embeddings at 1024 dimensions and recursive spec chunking at 1024 tokens.
- `src/rag_ocpp/storage/schema.sql` still declares `chunks.embedding VECTOR(768)`, creating a schema/config mismatch.
- `docs/ingest.md`, `docs/dev_journey.md`, and `docs/plan_note.md` still describe older BGE-base, 768-dimensional, SDPM/512-token assumptions.
- `docs/mcp.md` documents six MCP read tools, OCPP-only scope, and stdio-only transport.
- `tests/test_retrieval/test_vector_search.py` appears to use random document UUIDs instead of the ID returned by `insert_document`, so retrieval integration tests are likely not proving the intended path.

## Strict Control Rules

1. Do not make retrieval or generation changes without a measurable eval baseline.
2. Do not change embedding dimensions without schema migration, re-embedding, and documentation updates in the same branch.
3. Do not add SQL built from raw user/query terms. Parameterize all query inputs.
4. Do not log private source chunks, retrieved context, prompts, answers, or secrets without a redaction policy.
5. Keep `AGENTS.md`, this handoff, and `docs/AUDIT_REPORT.md` current after material changes.

## Ordered Next Actions

1. Fix schema/config/docs drift around embedding dimension and chunking strategy.
2. Fix SQL injection surfaces in keyword and graph fallback lookup.
3. Repair retrieval integration tests and run a clean `pytest` baseline.
4. Create and run a versioned retrieval evaluation set with Recall@k, MRR, NDCG, source coverage, and answer citation checks.
5. Add private-knowledge controls: secret handling, log redaction, source access model, data retention, and audit events.
6. Make migrations explicit instead of relying on manual DB mutation.
7. Align API, CLI, and MCP limits, filters, and citation behavior.
8. Add operational runbooks for ingestion, re-embedding, eval, rollback, backup, and restore.

## Verification Commands

```bash
ruff check .
mypy src
pytest
docker compose up -d
rag eval data/eval/queries.jsonl --top-k 10
```

If Docker, model downloads, or DeepSeek credentials are unavailable, record the gap in this file and keep local static checks as the minimum validation.

## Critical Files

- `AGENTS.md` - agent and contributor operating rules.
- `docs/AUDIT_REPORT.md` - strict enterprise-readiness audit and improvement order.
- `config/default.yaml` - current runtime tunables.
- `src/rag_ocpp/storage/schema.sql` - database contract.
- `src/rag_ocpp/storage/vector.py` - vector and keyword retrieval.
- `src/rag_ocpp/storage/graph.py` - entity, relationship, and graph fallback lookup.
- `src/rag_ocpp/retrieval/hybrid.py` - retrieval orchestration and strategy fusion.
- `src/rag_ocpp/mcp/server.py` - agent-facing knowledge tools.
