# Dev Journey — RAG/KAG OCPP 2.1 Pipeline

> Last updated: 2026-05-22
> Git: `main` branch, 9 commits, 36 source files, ~6,900 lines

---

## Completed Phases (9/11)

| Phase | Commit | Files | Status |
|-------|--------|-------|--------|
| 1 — Scaffold + Schema | `9b2359e` | 9 | ✅ |
| 2 — Storage Layer | `9b2359e` | 2 | ✅ |
| 3 — Ingestion | `794b2c8` | 4 | ✅ |
| 4 — Embedding | `fb881c6` | 2 | ✅ |
| 5 — Knowledge Graph | `554b974` | 3 | ✅ |
| 6 — Retrieval | `d6a624f` | 5 | ✅ |
| 7 — Generation | `c87b6a9` | 2 | ✅ |
| 8 — API | `4f3c29d` | 6 | ✅ |
| 9 — CLI | `b1eb3f0` | 3 | ✅ |
| **Total** | **9 commits** | **36 files** | **75%** |

---

## Source Tree

```
rag-kag-ocpp/
├── pyproject.toml              # 19 deps, entry: rag
├── docker-compose.yml          # pgvector/pg16, 2GB SHM
├── .env.example                # PG + DeepSeek keys
├── .gitignore                  # data/, models/, .env
├── config/
│   └── default.yaml            # All tunables
├── docs/
│   ├── plan_note.md            # 38-step plan, 17-protocol roster
│   ├── ingest.md               # Chunk thresholds, page estimates
│   └── dev_journey.md          # This file
└── src/rag_ocpp/
    ├── config.py               # 8 typed dataclasses, OmegaConf + env
    ├── storage/
    │   ├── schema.sql          # 9 tables, 16 indexes
    │   ├── vector.py           # pgvector ops: cosine, tsvector, COPY
    │   └── graph.py            # Entity CRUD, recursive CTE
    ├── ingestion/
    │   ├── parser.py           # PDF (PyMuPDF + pdfplumber) + JSON
    │   ├── cleaner.py          # NFKC, header strip, 24 OCPP terms
    │   └── metadata.py         # 3 filename patterns
    ├── chunking/
    │   └── engine.py           # chonkie SDPM/Sentence/Recursive
    ├── embedding/
    │   ├── model.py            # BGE-base-en-v1.5, query asymmetry
    │   └── batch.py            # Async backfill loop
    ├── knowledge/
    │   ├── entities.py         # 9 types, 245 terms, 9 patterns
    │   ├── extractor.py        # 2-pass: regex + LLM (cached)
    │   └── linker.py           # exact → alias → fuzzy → create
    ├── retrieval/
    │   ├── searchers.py        # Vector + Keyword + ScoredChunk
    │   ├── graph_search.py     # Query entity → chunks
    │   ├── fusion.py           # RRF (k=60)
    │   ├── reranker.py         # BGE-reranker-base (270M)
    │   └── hybrid.py           # Orchestrator
    ├── generation/
    │   ├── prompt.py           # Jinja2 templates
    │   └── client.py           # DeepSeek API (non-stream + SSE)
    ├── api/
    │   ├── app.py              # FastAPI lifespan
    │   ├── dependencies.py     # 9 DI functions
    │   ├── schemas.py          # 8 Pydantic models
    │   └── routes/
    │       ├── ingest.py       # POST /ingest
    │       ├── query.py        # POST /query, /query/stream, GET /search
    │       └── admin.py        # GET /health, /documents, /entities
    └── cli/
        ├── main.py             # typer entry
        ├── ingest.py           # rag ingest <file|dir>
        └── query.py            # rag query "..."
```

---

## Pipeline Architecture

```
PDF/JSON → parse → clean → metadata → chunk (chonkie SDPM 512/64)
  ├── embed (BGE-base 768-dim) → pgvector HNSW + tsvector
  └── extract entities (regex + LLM) → entities + relationships + chunk_entities

Query → embed → [vector ‖ keyword ‖ graph] → RRF(k=60) → rerank(cross-encoder) → DeepSeek
```

---

## Key Decisions

1. **Single PostgreSQL** for vectors + graph — zero ETL
2. **SDPM chunking** (not fixed-size) — respects spec section boundaries
3. **Two-pass extraction** — regex (free) + LLM DeepSeek (cached)
4. **BGE asymmetry** — docs without prefix, queries with `Represent this sentence...`
5. **RRF fusion** — score-agnostic, robust
6. **No LangChain/LlamaIndex** — direct control
7. **Schema extensible** to 16+ protocols — just INSERT rows + add regex patterns

---

## Reproduce

```bash
# 1. Docker
docker compose up -d

# 2. Python
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. Env
cp .env.example .env
# edit: DEEPSEEK_API_KEY=sk-...

# 4. Ingest
rag ingest data/pdf/ocpp/OCPP2.1Ed2.pdf --doc-type spec --version 2.1

# 5. Query
rag query "What fields are required in Authorize.req?"
rag query "How does smart charging work?" --stream

# 6. API
uvicorn rag_ocpp.api.app:create_app --factory
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is BootNotification?", "top_k": 5}'
```

---

## Remaining

| Phase | Steps | Files | Purpose |
|-------|-------|-------|---------|
| 10 — Tests | 34-36 | 6+ | Unit, integration (testcontainers), e2e |
| 11 — Eval | 37-38 | 2 | MRR, Recall@k, NDCG + benchmark CLI |
