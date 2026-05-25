# Handoff: RAG-KAG-OCPP — Retrieval Pipeline Stabilization

**Date:** 2026-05-25  
**Status:** Pipeline functional, all three strategies contributing to top-5. Latency high (21s cold). Eval scores unknown (need rerun with current UUIDs).

## Project Summary

OCPP 2.1 knowledge base with hybrid retrieval (vector + keyword + graph) + DeepSeek LLM generation. Backend: PostgreSQL + pgvector + HNSW. Models: BGE-large-en-v1.5 (1024-dim embeddings), BGE-reranker-base (cross-encoder).

## What Was Done

### Bug fixes (critical — do not revert)
1. **`vector.py:vector_search`** — `SET LOCAL hnsw.ef_search` and `SELECT` cannot share one `pool.execute()` call (asyncpg single-statement limit). Split into `conn.execute(SET)` + `conn.fetch(SELECT)` using `pool.acquire()` for shared session state. SET must use f-string (`f"SET LOCAL ... = {int(ef_search)}"`), not `$1`.

2. **Vector embedding must be string** — `_vec(query_embedding)` converts list to pgvector format `[0.1,0.2,...]`. Raw list causes asyncpg error.

3. **`vector.py:keyword_search`** — tsquery stemming misses multi-word terms. Added individual-word ILIKE fallback that OR-matches words against content/section_title.

4. **`graph.py:find_entity_names_by_terms`** — Regex entity extraction only matches camelCase. Added DB-backed ILIKE fallback for multi-word names (e.g. "Certificate Management").

### Improvements
1. **Model upgrade**: BGE-base (768d) → BGE-large (1024d). Column `vector(768)` → `vector(1024)`. Re-embedded 6,535 chunks via `tools/reembed.py`. No re-ingest.

2. **Weighted RRF**: `[1.0, 3.0, 2.0]` (vector, keyword, graph). Keyword dominates for technical specs.

3. **Graph floor**: at least 1 entity-linked chunk in top-5 if graph returned results.

4. **Graph score boost**: spec chunks 0.9, test case chunks (page > 1500) 0.5.

5. **Graph traversal**: `expand_via_traversal=True` by default.

6. **Logging**: `vec=20 kw=20 gr=10 → 5 chunks ({...})` pattern in HybridRetriever.

### Config (`config/default.yaml`)
- `chunking.spec.strategy`: "recursive"
- `chunking.spec.chunk_size`: 1024
- `embedding.model_name`: "BAAI/bge-large-en-v1.5"
- `embedding.dims`: 1024

### New tools
- `reembed.py` — re-embed chunks without re-ingesting
- `repop_eval.py` — populate eval UUIDs from current DB
- `retrieval_diag.py` — per-query diagnostic
- `eval_kw_only.py` — keyword-only eval

## Current Pipeline

```
Query → BGE-large embed → parallel:
  ├─ Vector (HNSW, ef_search=100, top_k=20)
  ├─ Keyword (tsquery + ILIKE, top_k=20)
  └─ Graph (entity → DB fallback → traversal, top_k=10)

→ Weighted RRF [1.0, 3.0, 2.0], k=60
→ Top-30 → reranker → top-5
→ Graph floor: ≥1 graph chunk
→ DeepSeek generation
```

**Verified**: `vec=20 kw=20 gr=10 → 5 chunks ({'vector':1,'graph':1,'keyword':3})`, 21s cold.

## Eval

`data/eval/queries.jsonl` has 20 queries with stale UUIDs. **Must rerun**:
```bash
python tools/repop_eval.py
python tools/fix_relationships.py
rag eval data/eval/queries.jsonl --top-k 10
```

## Known Issues

1. **Latency 21s** — model loading per invocation
2. **Graph chunks often test cases** — score boost helps but content relevance varies
3. **Reranker quality unknown** — may hurt more than help; bypass with `enable_rerank=False`
4. **No eval baseline** — need numbers to compare future improvements

## Next Steps

- [ ] Rerun eval for real baseline
- [ ] Lazy-load reranker (2s saved)
- [ ] Section adjacency (±2 chunks around match)
- [ ] Query expansion (entity aliases in keyword)
- [ ] ColBERT reranker for token-level precision

## Key Files

- `src/rag_ocpp/storage/vector.py` — VectorStore, keyword_search, vector_search (all critical fixes)
- `src/rag_ocpp/retrieval/hybrid.py` — HybridRetriever (RRF, reranker, graph floor, logging)
- `src/rag_ocpp/retrieval/fusion.py` — Weighted RRF
- `src/rag_ocpp/retrieval/graph_search.py` — Entity extraction + traversal + score boost
- `src/rag_ocpp/storage/graph.py` — GraphStore + entity lookup fallback
- `config/default.yaml` — All tunables
- `docker-compose.yml` — PostgreSQL + pgvector
