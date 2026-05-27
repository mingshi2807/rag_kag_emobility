# Handoff: RAG-KAG-OCPP Repository Control

**Date:** 2026-05-27
**Control status:** OCPP 2.1 Ed2 source-aware corpus, full embedded index, project-local skills, and upgraded MCP evidence tools are implemented. Root `AGENTS.md` defines agent operating rules. Enterprise audit is captured in `docs/AUDIT_REPORT.md`.
**Current conclusion:** The project now has a first-class corpus record layer for Part 2 spec, Device Model tables, and JSON schemas, plus agent-facing MCP tools for evidence packs, implementation briefs, corpus status, and filtered search. It is still not enterprise-ready until retrieval eval gates, private-data controls, migrations, and broader integration tests are complete.

## Mission

Build a private e-mobility knowledge base with LLM, RAG, and KAG integration for OCPP first, then broader protocol coverage. The required product bar is answer traceability, private-data protection, reproducible ingestion, measurable retrieval quality, and stable API/CLI/MCP access.

## Current Architecture

```
PDF/JSON -> parser -> cleaner -> metadata -> chunking
        -> embeddings -> PostgreSQL + pgvector
        -> entity extraction/linking -> graph tables

Query -> vector + keyword + graph retrieval
      -> weighted RRF -> reranker -> top chunks
      -> DeepSeek generation / API / CLI / MCP evidence tools
```

## Current Evidence Snapshot

- `pyproject.toml` defines a Python 3.12 package named `rag-kag-ocpp` with CLI entries `rag` and `rag-mcp`.
- `config/default.yaml` currently sets BGE-large embeddings at 1024 dimensions and recursive spec chunking at 1024 tokens.
- `src/rag_ocpp/storage/schema.sql` now declares `chunks.embedding VECTOR(1024)` and adds `source_documents` plus `corpus_records`.
- `src/rag_ocpp/corpus/` normalizes source-aware evidence records from the OCPP 2.1 Ed2 Part 2 PDF, Device Model CSV/XLSX files, and JSON schemas.
- `src/rag_ocpp/cli/corpus.py` adds `rag corpus`, defaulting to dry-run preview; use `--store` to write source/corpus records.
- `rag index-corpus` indexes stored corpus records into `chunks`, embeddings, graph entities, chunk/entity links, and source-definition relationships.
- `src/rag_ocpp/storage/vector.py` and `src/rag_ocpp/storage/graph.py` now parameterize the previous keyword/entity ILIKE fallback SQL paths.
- `docs/ingest.md`, `docs/dev_journey.md`, and `docs/plan_note.md` still describe older BGE-base, 768-dimensional, SDPM/512-token assumptions.
- `docs/mcp.md` documents nine MCP read tools, including filtered search, evidence packs, implementation briefs, corpus status, chunk/entity lookup, and section search.
- `.codex/skills/` contains repo-local OCPP RAG/KAG workflow skills for improvement, expert review, query eval, implementation guides, and smoke testing.
- `tests/test_retrieval/test_vector_search.py` appears to use random document UUIDs instead of the ID returned by `insert_document`, so retrieval integration tests are likely not proving the intended path.

## Strict Control Rules

1. Do not make retrieval or generation changes without a measurable eval baseline.
2. Do not change embedding dimensions without schema migration, re-embedding, and documentation updates in the same branch.
3. Do not add SQL built from raw user/query terms. Parameterize all query inputs.
4. Do not log private source chunks, retrieved context, prompts, answers, or secrets without a redaction policy.
5. Keep `AGENTS.md`, this handoff, and `docs/AUDIT_REPORT.md` current after material changes.

## Ordered Next Actions

1. Smoke-test indexing with `rag index-corpus --no-embed --limit 50`, then inspect `chunks`, `chunk_entities`, and `relationships`.
2. Run full indexing with `rag index-corpus --batch-size 32` or another batch size that fits local memory.
3. Repair retrieval integration tests and run a clean `pytest` baseline.
4. Create and run a versioned OCPP Ed2 Part 2 eval set with Recall@k, MRR, NDCG, source coverage, and answer citation checks.
5. Add private-knowledge controls: secret handling, log redaction, source access model, data retention, and audit events.
6. Make migrations explicit instead of relying on manual DB mutation.
7. Align API and CLI with the upgraded MCP evidence filters and citation metadata.
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
- `src/rag_ocpp/corpus/ocpp21.py` - OCPP 2.1 Ed2 source-aware corpus parsers.
- `src/rag_ocpp/corpus/indexer.py` - indexes corpus records into chunks, embeddings, and graph links.
- `src/rag_ocpp/storage/corpus.py` - DB adapter for source documents and corpus records.
- `src/rag_ocpp/cli/corpus.py` - corpus preview/store CLI command.
- `src/rag_ocpp/storage/vector.py` - vector and keyword retrieval.
- `src/rag_ocpp/storage/graph.py` - entity, relationship, and graph fallback lookup.
- `src/rag_ocpp/retrieval/hybrid.py` - retrieval orchestration and strategy fusion.
- `src/rag_ocpp/mcp/server.py` - agent-facing knowledge tools.
