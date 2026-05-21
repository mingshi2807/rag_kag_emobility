# RAG/KAG Pipeline for OCPP 2.1 — Build Plan

> **Status**: Phase 1 complete (steps 1–5). Step 6 deferred (no Docker in env).
> **Last updated**: 2026-05-21

---

## Architecture Overview

```
PDFs / JSONs
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  INGESTION (Phase 3)                                     │
│  PyMuPDF + pdfplumber → TextCleaner → MetadataExtractor  │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  CHUNKING (Phase 3)                                      │
│  chonkie SDPMChunker (specs) / SentenceChunker (tests)   │
│  512 tokens, 64 overlap for OCPP specs                   │
└──────────────────────────┬──────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            │            ▼
┌─────────────────┐        │    ┌──────────────────────┐
│  EMBEDDING       │        │    │  KNOWLEDGE GRAPH     │
│  (Phase 4)       │        │    │  (Phase 5)           │
│  bge-base-en     │        │    │  Regex NER +         │
│  768-dim, batch  │        │    │  LLM deep extraction │
│  32, GPU         │        │    │  Entity linker       │
└────────┬─────────┘        │    └──────────┬───────────┘
         │                  │               │
         ▼                  │               ▼
┌─────────────────────────────────────────────────────────┐
│  POSTGRESQL + pgvector (Phase 2)                         │
│  ┌───────────────────┐   ┌────────────────────────────┐ │
│  │ chunks             │   │ entities                   │ │
│  │  - HNSW (cosine)   │   │ relationships              │ │
│  │  - GIN (tsvector)  │   │ chunk_entities             │ │
│  └───────────────────┘   └────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  RETRIEVAL (Phase 6)                                     │
│  ┌─────────┐  ┌──────────┐  ┌──────────────┐           │
│  │ Vector  │  │ Keyword  │  │ Graph        │           │
│  │ cosine  │  │ ts_rank  │  │ CTE traverse │           │
│  │ top-20  │  │ top-10   │  │ top-10       │           │
│  └────┬────┘  └────┬─────┘  └──────┬───────┘           │
│       └────────────┼───────────────┘                    │
│                    ▼                                     │
│           RRF Fusion (k=60)                              │
│                    │                                     │
│                    ▼                                     │
│      Cross-encoder Rerank (bge-reranker-base)            │
│                    │                                     │
│                    ▼                                     │
│               Top-5 Chunks                               │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  GENERATION (Phase 7)                                    │
│  Jinja2 prompt template + DeepSeek Chat API              │
└─────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Choice | Version | Rationale |
|-------|--------|---------|-----------|
| Language | Python | ≥3.12 | HuggingFace ecosystem native |
| Chunking | chonkie | ≥1.0.0 | Rust core, 10-50× faster than LangChain, SDPM for semantic boundaries |
| Database | PostgreSQL + pgvector | pg16 + pgvector 0.7+ | Single DB for vectors + graph, zero ETL |
| Vector index | HNSW | m=16, ef_construction=200 | Fast ANN, cosine distance |
| Fulltext | tsvector (GIN) | — | PostgreSQL native, zero additional infra |
| Embedding | BAAI/bge-base-en-v1.5 | 768 dims | Top-3 MTEB for size class, query/passage asymmetry |
| Reranking | BAAI/bge-reranker-base | 270M params | Cross-encoder, +5-10% MRR over embedding-only |
| Generation | DeepSeek Chat API | deepseek-chat | 64K context, API key available |
| PDF parsing | PyMuPDF + pdfplumber | ≥1.25 / ≥0.11 | Text extraction + table extraction |
| API | FastAPI + asyncpg + uvicorn | ≥0.115 | Async PostgreSQL, OpenAPI auto-docs, SSE streaming |
| CLI | typer + rich | ≥0.15 / ≥13 | Subcommands, progress bars |
| Config | OmegaConf | ≥2.3 | YAML + env-var interpolation |
| Templates | Jinja2 | ≥3.1 | Prompt construction |
| HTTP | httpx | ≥0.28 | Async DeepSeek API calls |

---

## Phase 1 — Project Scaffold & Database (steps 1–6)

### Step 1 — Project directory
**Status**: ✅ Completed

Create `rag-kag-ocpp/` with:

- `pyproject.toml` — 19 production dependencies, `[project.scripts]` entry `rag`
- `.env.example` — PG connection, DeepSeek API key, HF_HOME, LOG_LEVEL
- `.gitignore` — Python artifacts, `data/`, `models/`, environment, IDE

Full dependency list:
```
chonkie, asyncpg, pgvector, fastapi, uvicorn, pydantic, pydantic-settings,
pymupdf, pdfplumber, sentence-transformers, torch, transformers,
typer, rich, jinja2, httpx, sse-starlette, omegaconf, tqdm, numpy
```

Dev dependencies: `pytest, pytest-asyncio, testcontainers[postgres], ruff, mypy`

### Step 2 — docker-compose.yml
**Status**: ✅ Completed

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: rag-ocpp-pg
    shm_size: 2gb
    environment:
      POSTGRES_DB: rag_ocpp
      POSTGRES_USER: rag
      POSTGRES_PASSWORD: ${PG_PASSWORD}
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./src/rag_ocpp/storage/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql:ro
    command: >
      -c shared_buffers=2GB
      -c work_mem=64MB
      -c maintenance_work_mem=512MB
      -c effective_cache_size=6GB
      -c max_parallel_workers_per_gather=4
      -c max_parallel_workers=8
      -c max_connections=50
      -c random_page_cost=1.1
      -c effective_io_concurrency=200
    healthcheck:
      test: pg_isready
      interval: 5s
      retries: 5
```

### Step 3 — config/default.yaml
**Status**: ✅ Completed

All tunable parameters across 6 sections:

| Section | Key settings |
|---------|-------------|
| `postgres` | host, port, database, pool min/max connections, DSN property |
| `deepseek` | api_key (env), base_url, model=deepseek-chat, temperature=0.1, max_tokens=4096 |
| `embedding` | model=BAAI/bge-base-en-v1.5, device=cuda, dims=768, batch=32, BGE query prefix |
| `reranker` | model=BAAI/bge-reranker-base, device=cuda, max_length=512, batch=16 |
| `chunking` | spec: sdpm/512/64, test_suite: sentence/256/32, fallback: recursive/1024/128 |
| `retrieval` | vector_top_k=20, keyword_top_k=10, graph_top_k=10, fusion_k=60, final_top_k=5, weights |

### Step 4 — config.py
**Status**: ✅ Completed

8 typed dataclasses:
```
AppConfig
├── PostgresConfig (host, port, database, user, password, pool sizes, dsn property)
├── DeepSeekConfig (api_key, base_url, model, temperature, max_tokens)
├── EmbeddingConfig (model_name, device, dims, batch_size, normalize, query_prefix)
├── RerankerConfig (model_name, device, max_length, batch_size)
├── ChunkingConfig → ChunkingStrategy (strategy, chunk_size, overlap, threshold)
├── RetrievalConfig → RetrievalWeights (vector, keyword, graph)
└── LoggingConfig (level)
```

Loader resolution order:
1. `config/default.yaml` (shipped defaults)
2. User-specified override path
3. Environment variables (`PG_HOST`, `DEEPSEEK_API_KEY`, etc.)

### Step 5 — storage/schema.sql
**Status**: ✅ Completed

12 tables, 16 indexes, seeded with OCPP 2.1 entity types:

| # | Table | Purpose | Key indexes |
|---|-------|---------|-------------|
| 1 | `protocols` | Protocol registry | PK only |
| 2 | `documents` | Source file metadata | protocol_id, doc_type |
| 3 | `chunks` | Vector + fulltext store | HNSW (cosine), GIN (tsvector), content_hash |
| 4 | `entity_types` | Per-protocol type enum | PK (id, protocol_id) |
| 5 | `entities` | Knowledge graph nodes | name, aliases (GIN), protocol_id |
| 6 | `relationships` | Graph edges (7 types) | source_id, target_id, rel_type |
| 7 | `chunk_entities` | Chunk ↔ entity bridge | entity_id |
| 8 | `cross_protocol_mappings` | Future multi-protocol links | — |
| 9 | `query_log` | Evaluation / observability | — |

Entity types seeded for OCPP 2.1:
```
command, datatype, component, variable, enum, message_flow,
functional_block, error_code, test_case
```

Relationship types supported:
```
uses, extends, requires, responds_to, belongs_to, tested_by, references
```

### Step 6 — Start PostgreSQL, verify schema
**Status**: ⏸️ Pending (Docker not available in current environment)

```bash
cd rag-kag-ocpp
cp .env.example .env          # edit PG_PASSWORD and DEEPSEEK_API_KEY
docker compose up -d
docker compose logs postgres   # verify "database system is ready"
docker compose exec postgres psql -U rag -d rag_ocpp -c "\dx"
# Expected: vector, pg_trgm, uuid-ossp extensions
docker compose exec postgres psql -U rag -d rag_ocpp -c "\dt"
# Expected: 9 tables listed
```

---

## Phase 2 — Storage Layer (steps 7–8)

### Step 7 — storage/vector.py
**Status**: ⬜ Pending

Purpose: PostgreSQL pgvector operations via asyncpg.

```python
class VectorStore:
    def __init__(self, pool: asyncpg.Pool)

    async def insert_chunks(self, chunks: list[ChunkWithEmbedding])
        # Uses COPY protocol for bulk insert

    async def vector_search(self, query_embedding, top_k=20, doc_type=None)
        # SELECT ... ORDER BY embedding <=> $1 LIMIT $3
        # Returns list[SearchResult] with similarity scores

    async def keyword_search(self, query: str, top_k=20)
        # SELECT ... WHERE tsv @@ plainto_tsquery('english', $1)
        # ORDER BY ts_rank DESC
        # Returns list[SearchResult] with rank scores

    async def get_pending_chunks(self, batch_size=256)
        # SELECT chunks WHERE embedding IS NULL

    async def update_embeddings(self, chunk_ids, embeddings)
        # UPDATE chunks SET embedding = $2 WHERE id = $1
```

### Step 8 — storage/graph.py
**Status**: ⬜ Pending

Purpose: Knowledge graph CRUD and traversal queries.

```python
class GraphStore:
    def __init__(self, pool: asyncpg.Pool)

    async def upsert_entity(self, protocol_id, type_id, name, description, aliases, properties)
        # INSERT ... ON CONFLICT (protocol_id, type_id, name) DO UPDATE

    async def upsert_relationship(self, source_id, target_id, rel_type, properties)
        # INSERT ... ON CONFLICT (source_id, target_id, rel_type) DO NOTHING

    async def link_chunk_entity(self, chunk_id, entity_id, confidence, span)
        # INSERT INTO chunk_entities

    async def find_entity(self, protocol_id, type_id, name)
        # Exact match

    async def find_entity_fuzzy(self, protocol_id, name, threshold=0.3)
        # pg_trgm similarity search

    async def traverse(self, entity_id, rel_types, max_depth=3)
        # Recursive CTE:
        # WITH RECURSIVE chain AS (
        #   SELECT ... FROM entities WHERE id = $1
        #   UNION ALL
        #   SELECT ... FROM chain JOIN relationships JOIN entities
        #   WHERE depth < $3
        # )

    async def get_chunks_for_entity(self, entity_id, top_k=10)
        # SELECT chunks.* FROM chunk_entities JOIN chunks
        # WHERE entity_id = $1 ORDER BY confidence DESC
```

---

## Phase 3 — Ingestion Pipeline (steps 9–12)

### Step 9 — ingestion/parser.py
**Status**: ⬜ Pending

Purpose: Parse PDF and JSON input files.

```python
@dataclass
class ParsedPage:
    text: str
    tables: list[dict]  # pdfplumber extracted tables
    page_num: int

@dataclass
class ParsedDocument:
    pages: list[ParsedPage]
    toc: list[dict]      # Table of Contents entries
    metadata: dict       # title, author, page_count
    source_path: str
    doc_type: str

class DocumentParser:
    def parse(self, path: Path) -> ParsedDocument
        if .pdf → self._parse_pdf (PyMuPDF text + pdfplumber tables)
        if .json → self._parse_json (stdlib json)

    def _parse_pdf(self, path) -> ParsedDocument
        # PyMuPDF: extract_page_text() per page
        # pdfplumber: extract_tables() per page
        # Extract ToC via doc.get_toc()

    def _parse_json(self, path) -> ParsedDocument
        # json.load → flatten nested structure to text
        # Preserve JSON paths as "section" metadata
```

### Step 10 — ingestion/cleaner.py
**Status**: ⬜ Pending

Purpose: Normalize extracted text.

```python
class TextCleaner:
    def clean(self, text: str) -> str:
        # 1. Strip PDF headers/footers via regex
        #    ("OCPP 2.1 — Part X" repeated per page)
        # 2. Unicode normalization (NFKC)
        # 3. Collapse multiple whitespace → single space
        # 4. Fix common OCR artifacts:
        #    "l"→"1", "O"→"0" in numeric contexts
        # 5. Normalize OCPP terminology variants:
        #    "Charge Point" → "ChargePoint"
        #    "EVSE" ↔ "EV Supply Equipment"
        # 6. Remove empty lines
        # 7. Trim leading/trailing whitespace
```

### Step 11 — ingestion/metadata.py
**Status**: ⬜ Pending

Purpose: Extract structured metadata from filenames and content.

```python
class OCPPMetadataExtractor:
    def extract(self, path: Path, doc: ParsedDocument) -> DocumentMetadata:
        # From filename patterns:
        #   "OCPP-2.1-Part2-Core.pdf"
        #     → version="2.1", part="Part 2: Core", doc_type="spec"
        #   "OCPP-2.1-TestCases-ProfileA.json"
        #     → version="2.1", profile="A", doc_type="test_suite"
        #
        # From content heuristics:
        #   - First 500 chars for title detection
        #   - Section numbering patterns (e.g. "2.3.1") for structure
        #   - Known OCPP part names for classification
```

### Step 12 — chunking/engine.py
**Status**: ⬜ Pending

Purpose: Wrap chonkie with per-document-type strategy dispatch.

```python
from chonkie import SDPMChunker, SentenceChunker, RecursiveChunker

@dataclass
class Chunk:
    index: int
    content: str
    content_hash: str    # SHA-256
    strategy: str
    section_title: str
    page_start: int
    page_end: int
    token_count: int

class ChunkingEngine:
    def __init__(self, config: ChunkingConfig):
        self.sdpm = SDPMChunker(
            chunk_size=config.spec.chunk_size,       # 512
            chunk_overlap=config.spec.chunk_overlap,  # 64
            min_sentences_per_chunk=3,
            threshold=0.5,
        )
        self.sentence = SentenceChunker(
            chunk_size=config.test_suite.chunk_size,  # 256
            chunk_overlap=config.test_suite.chunk_overlap,  # 32
        )
        self.recursive = RecursiveChunker(
            chunk_size=config.fallback.chunk_size,    # 1024
            chunk_overlap=config.fallback.chunk_overlap,  # 128
        )

    def chunk(self, doc: ParsedDocument, doc_type: str) -> list[Chunk]:
        strategy = {
            "spec":        self.sdpm,
            "test_suite":  self.sentence,
            "json_config": self.sentence,
        }.get(doc_type, self.recursive)

        raw_chunks = strategy.chunk(doc.flat_text)
        return self._enrich(raw_chunks, doc)
        # Enrich with section_title, page_range, strategy label
```

**Why SDPM for OCPP specs**: OCPP specifications are hierarchically structured (Part → Section → Subsection → Paragraph). SDPM's threshold-based semantic merging preserves these boundaries — chunks won't span across section breaks when semantic similarity drops at topic boundaries.

---

## Phase 4 — Embedding (steps 13–14)

### Step 13 — embedding/model.py
**Status**: ⬜ Pending

Purpose: HuggingFace embedding model loader and inference.

```python
class EmbeddingModel:
    """
    Primary: BAAI/bge-base-en-v1.5
      - Dimensions: 768
      - Parameters: 109M
      - Max tokens: 512
      - MTEB retrieval: ~53% (top-3 for size class)

    Critical BGE detail: asymmetric encoding.
      Documents embedded WITHOUT prefix.
      Queries embedded WITH prefix:
        "Represent this sentence for searching relevant passages: "
    """

    def __init__(self, model_name, device="cuda"):
        self.model = SentenceTransformer(model_name, device=device)
        self.query_prefix = "..."

    def embed_documents(self, texts: list[str], batch_size=32) -> np.ndarray:
        return self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,     # cosine = dot product after norm
            show_progress_bar=True,
        )

    def embed_query(self, query: str) -> np.ndarray:
        return self.model.encode(
            [self.query_prefix + query],
            normalize_embeddings=True,
        )[0]
```

### Step 14 — embedding/batch.py
**Status**: ⬜ Pending

Purpose: Asynchronous backfill loop.

```python
class BatchEmbedder:
    """Stream chunks from PostgreSQL → embed in batches → write back."""

    def __init__(self, pool: asyncpg.Pool, model: EmbeddingModel):
        ...

    async def embed_all_pending(self, batch_size=256):
        """
        Loop:
          SELECT id, content FROM chunks
          WHERE embedding IS NULL
          ORDER BY created_at
          LIMIT $batch_size

          If empty → return

          embeddings = model.embed_documents(contents)

          UPDATE chunks SET embedding = $2 WHERE id = $1
          (batch UPDATE with executemany)

        Progress bar via tqdm.
        Checkpoint: if process crashes, re-running picks up
        remaining NULL-embedding rows.
        """
```

---

## Phase 5 — Knowledge Graph (steps 15–17)

### Step 15 — knowledge/entities.py
**Status**: ⬜ Pending

Purpose: OCPP entity type definitions and regex patterns.

```python
class OCPPEntityType(Enum):
    COMMAND          = ("command",          1)
    DATATYPE         = ("datatype",         2)
    COMPONENT        = ("component",        3)
    VARIABLE         = ("variable",         4)
    ENUM             = ("enum",             5)
    MESSAGE_FLOW     = ("message_flow",     6)
    FUNCTIONAL_BLOCK = ("functional_block", 7)
    ERROR_CODE       = ("error_code",       8)
    TEST_CASE        = ("test_case",        9)

# Per-type regex for Pass 1 extraction:
PATTERNS = {
    "command": r"\b(Authorize|BootNotification|Heartbeat|StartTransaction|"
               r"StopTransaction|MeterValues|StatusNotification|"
               r"DataTransfer|DiagnosticsStatusNotification|"
               r"FirmwareStatusNotification|GetConfiguration|...)"
               r"(?:\.(req|conf))?\b",

    "datatype": r"\b(IdToken|ChargingProfile|ChargingSchedule|"
                r"TransactionData|MeterValue|SampledValue|"
                r"ComponentVariable|...)\b",

    "component": r"\b(ChargePoint|Connector|EVSE|"
                 r"ChargingStation|...)\b",

    "variable": r"\b([a-z]+[A-Z][a-z]*)+",  # camelCase patterns

    "test_case": r"\bTC_[A-Z]{2}_\d{2,3}\b",
}
```

### Step 16 — knowledge/extractor.py
**Status**: ⬜ Pending

Purpose: Two-pass entity and relationship extraction.

```python
class EntityExtractor:
    """
    Pass 1: Regex (fast, high precision, no API cost)
      - Match entity patterns in chunk text
      - Extract span offsets
      - Score confidence based on pattern specificity

    Pass 2: LLM DeepSeek (batched, cached)
      - Prompt: "Extract OCPP entities and their relationships.
                 Entity types: command, datatype, component, variable.
                 Relationships: uses, requires, responds_to, extends, belongs_to.
                 Return JSON."
      - Batch multiple chunks per LLM call to amortize latency
      - Cache results by content_hash to avoid re-extraction
    """

    def extract_entities(self, chunk: Chunk) -> list[EntityMention]:
        # Pass 1: regex
        regex_matches = self._regex_pass(chunk.content)

        # Pass 2: LLM (only for chunks with potential relationships)
        if self._needs_llm_pass(chunk):
            llm_matches = self._llm_pass(chunk.content)
            return self._merge(regex_matches, llm_matches)

        return regex_matches

    def extract_relationships(self, entities, chunk) -> list[RelationMention]:
        # LLM prompt: "Given the OCPP entities found, identify their relationships"
        ...
```

### Step 17 — knowledge/linker.py
**Status**: ⬜ Pending

Purpose: Entity resolution across chunks.

```python
class EntityLinker:
    """Merge duplicate entity mentions from different chunks."""

    async def resolve(
        self,
        pool: asyncpg.Pool,
        mentions: list[EntityMention],
    ) -> list[UUID]:
        """
        1. Exact match: same protocol + type + name → existing entity UUID
        2. Alias match: name found in existing entity's aliases[] → existing UUID
        3. Fuzzy match: pg_trgm similarity > threshold → candidate for review
        4. New entity: INSERT → new UUID
        """
```

---

## Phase 6 — Retrieval Pipeline (steps 18–22)

### Step 18 — retrieval/vector_search.py + keyword_search.py
**Status**: ⬜ Pending

Purpose: Thin wrappers with filtering support.

```python
class VectorSearcher:
    def __init__(self, vector_store: VectorStore):
        ...

    async def search(
        self, query_embedding, top_k=20, protocol_id=None, doc_type=None
    ) -> list[ScoredChunk]:
        # Calls vector_store.vector_search() with optional filters


class KeywordSearcher:
    def __init__(self, vector_store: VectorStore):
        ...

    async def search(self, query: str, top_k=10) -> list[ScoredChunk]:
        # Calls vector_store.keyword_search() with ts_rank
```

### Step 19 — retrieval/graph_search.py
**Status**: ⬜ Pending

Purpose: Entity-aware graph traversal retrieval.

```python
class GraphSearcher:
    """
    1. Extract entity mentions from query text (regex)
    2. For each matched entity, find in entities table
    3. Traverse relationships (1-2 hops) to find related entities
    4. Retrieve chunks linked to these entities via chunk_entities bridge
    """

    async def search(self, query: str, top_k=10) -> list[ScoredChunk]:
        entities = self._extract_query_entities(query)
        # ... graph traversal ...
        # ... chunk_entities JOIN ...
```

**Example traversal query** (PostgreSQL recursive CTE):
```sql
WITH RECURSIVE entity_chain AS (
    SELECT e.id, e.name, e.type_id, 0 AS depth
    FROM entities e
    WHERE e.name = 'IdToken' AND e.type_id = 2  -- datatype

    UNION ALL

    SELECT e.id, e.name, e.type_id, ec.depth + 1
    FROM entity_chain ec
    JOIN relationships r ON r.target_id = ec.id
    JOIN entities e ON e.id = r.source_id
    WHERE r.rel_type = 'uses' AND ec.depth < 3
)
SELECT DISTINCT c.content, c.section_title
FROM entity_chain ec
JOIN chunk_entities ce ON ce.entity_id = ec.id
JOIN chunks c ON c.id = ce.chunk_id
WHERE ec.type_id = 1  -- commands only
ORDER BY ce.confidence DESC
LIMIT 10;
```

### Step 20 — retrieval/fusion.py
**Status**: ⬜ Pending

Purpose: Reciprocal Rank Fusion.

```python
def reciprocal_rank_fusion(
    result_sets: list[list[ScoredChunk]],
    k: int = 60,
) -> list[tuple[ScoredChunk, float]]:
    """
    RRF score = Σ (1 / (k + rank_in_list))

    For each result list:
      score[chunk_id] += 1 / (60 + rank)

    Sort by descending aggregated score.
    Deduplicate by chunk_id (keep highest score).

    RRF is preferred over weighted sum because:
      - No need to normalize scores across strategies
      - Robust to outlier scores from one strategy
      - Proven in academic IR benchmarks
    """
```

### Step 21 — retrieval/reranker.py
**Status**: ⬜ Pending

Purpose: Cross-encoder reranking.

```python
class CrossEncoderReranker:
    """
    BAAI/bge-reranker-base
      - Type: Cross-encoder (attends across query AND passage)
      - Parameters: 270M
      - Input: (query, passage) pairs
      - Output: relevance score per pair

    More accurate than embedding cosine because the model sees
    query and passage simultaneously, not separately.
    Cost: ~10-20ms per pair (GPU), O(n) where n = candidates.
    """

    def __init__(self, model_name="BAAI/bge-reranker-base"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.eval()

    @torch.no_grad()
    def rerank(
        self, query: str, candidates: list[ScoredChunk], top_k=5
    ) -> list[ScoredChunk]:
        pairs = [[query, c.content] for c in candidates]
        inputs = self.tokenizer(
            pairs, padding=True, truncation=True,
            max_length=512, return_tensors="pt",
        )
        scores = self.model(**inputs).logits.squeeze(-1)
        top_indices = scores.argsort(descending=True)[:top_k]
        return [candidates[i] for i in top_indices]
```

### Step 22 — retrieval/hybrid.py
**Status**: ⬜ Pending

Purpose: Orchestrator that ties all three strategies together.

```python
class HybridRetriever:
    """
    Full retrieval flow:

    1. Query embedding (model.embed_query)
    2. Parallel: vector_search, keyword_search, graph_search
    3. RRF fusion (k=60) → merged top-30
    4. Cross-encoder rerank → top-5
    5. Return with scores, source citations
    """

    def __init__(
        self,
        vector_store: VectorStore,
        graph_store: GraphStore,
        embedding_model: EmbeddingModel,
        reranker: CrossEncoderReranker,
    ):
        ...

    async def retrieve(
        self, query: str, top_k=5, filters: SearchFilters | None = None
    ) -> list[RetrievedChunk]:
        # Step 1: embed query
        q_embed = self.embedding_model.embed_query(query)

        # Step 2: parallel async searches
        vec, kw, graph = await asyncio.gather(
            self.vector_searcher.search(q_embed, top_k=20),
            self.keyword_searcher.search(query, top_k=10),
            self.graph_searcher.search(query, top_k=10),
        )

        # Step 3: RRF fusion
        fused = reciprocal_rank_fusion([vec, kw, graph], k=60)

        # Step 4: rerank top-30 → top-k
        reranked = self.reranker.rerank(query, fused[:30], top_k=top_k)

        return reranked
```

---

## Phase 7 — Generation (steps 23–24)

### Step 23 — generation/prompt.py
**Status**: ⬜ Pending

Purpose: Jinja2 templates for OCPP Q&A.

```python
SYSTEM_PROMPT = """You are an OCPP 2.1 protocol expert. Answer questions using ONLY
the provided context from the OCPP specification and test suites.
If the context doesn't contain the answer, say so clearly.
Cite the specific section or source document for each claim."""

QUERY_TEMPLATE = jinja2.Template("""
## Context from OCPP 2.1 Knowledge Base

{% for chunk in chunks %}
**[{{ chunk.section_title }}]** ({{ chunk.document_title }}, p.{{ chunk.page_start }})
{{ chunk.content }}
{% endfor %}

## Question
{{ query }}

## Instructions
Answer concisely. Include relevant command names, data types, and message flow details.
Cite source sections in format: [Section Title](Document, page N).
""")
```

### Step 24 — generation/client.py
**Status**: ⬜ Pending

Purpose: DeepSeek Chat API wrapper.

```python
class DeepSeekClient:
    BASE_URL = "https://api.deepseek.com/v1"

    def __init__(self, api_key: str, model="deepseek-chat"):
        ...

    async def generate(
        self,
        query: str,
        context: list[RetrievedChunk],
        stream: bool = False,
    ) -> str | AsyncIterator[str]:
        prompt = QUERY_TEMPLATE.render(chunks=context, query=query)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": stream,
                    "temperature": 0.1,     # low for factual
                    "max_tokens": 4096,
                },
            )
            if stream:
                return self._stream_response(response)
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def _stream_response(self, response) -> AsyncIterator[str]:
        # Yield SSE chunks as they arrive
        ...
```

---

## Phase 8 — API Layer (steps 25–30)

### Step 25 — api/app.py
**Status**: ⬜ Pending

Purpose: FastAPI application factory with lifespan.

```python
def create_app(config: AppConfig) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup:
        #   1. Create asyncpg pool from config
        #   2. Warm up embedding model (load to GPU)
        #   3. Warm up reranker model
        #   4. Store in app.state
        yield
        # Shutdown:
        #   1. Close pool
        #   2. Unload models

    app = FastAPI(title="RAG/KAG OCPP 2.1", lifespan=lifespan)
    app.include_router(ingest_router, prefix="/ingest")
    app.include_router(query_router)
    app.include_router(admin_router)
    return app
```

### Step 26 — api/dependencies.py
**Status**: ⬜ Pending

Purpose: FastAPI dependency injection.

```python
async def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool

async def get_vector_store(pool=Depends(get_pool)) -> VectorStore:
    return VectorStore(pool)

async def get_graph_store(pool=Depends(get_pool)) -> GraphStore:
    return GraphStore(pool)

async def get_embedding_model(request: Request) -> EmbeddingModel:
    return request.app.state.embedding_model

async def get_reranker(request: Request) -> CrossEncoderReranker:
    return request.app.state.reranker

async def get_llm(request: Request) -> DeepSeekClient:
    return request.app.state.llm_client

async def get_hybrid_retriever(
    vs=Depends(get_vector_store),
    gs=Depends(get_graph_store),
    em=Depends(get_embedding_model),
    reranker=Depends(get_reranker),
) -> HybridRetriever:
    return HybridRetriever(vs, gs, em, reranker)
```

### Step 27 — api/schemas.py
**Status**: ⬜ Pending

Purpose: Pydantic request/response models.

```python
class IngestRequest(BaseModel):
    file: UploadFile
    doc_type: Literal["spec", "test_suite", "json_config", "other"] = "spec"
    protocol: str = "ocpp21"
    version: str = "2.1"

class IngestResponse(BaseModel):
    document_id: UUID
    chunks_created: int
    entities_extracted: int
    embedding_model: str

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    stream: bool = False
    protocol: str = "ocpp21"

class SearchResult(BaseModel):
    chunk_id: UUID
    content: str
    score: float
    section_title: str | None
    document_title: str
    page_start: int | None

class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: list[SearchResult]
    latency_ms: int

class SearchFilters(BaseModel):
    protocol: str | None = None
    doc_type: str | None = None
    entity_types: list[str] | None = None
```

### Step 28 — api/routes/ingest.py
**Status**: ⬜ Pending

Endpoint: `POST /ingest`

Full pipeline per file:
```
Upload PDF/JSON
  → save to temp file
  → DocumentParser.parse()
  → TextCleaner.clean()
  → OCPPMetadataExtractor.extract()
  → INSERT INTO documents
  → ChunkingEngine.chunk()
  → BatchEmbedder.embed()
  → VectorStore.insert_chunks()  (COPY protocol)
  → EntityExtractor.extract_entities()
  → EntityLinker.resolve()
  → GraphStore.upsert_entity()
  → GraphStore.link_chunk_entity()
  → return IngestResponse
```

### Step 29 — api/routes/query.py
**Status**: ⬜ Pending

Endpoints: `POST /query`, `POST /query/stream`

```
POST /query:
  → HybridRetriever.retrieve(query, top_k)
  → DeepSeekClient.generate(query, context, stream=False)
  → INSERT INTO query_log
  → return QueryResponse(answer, sources, latency)

POST /query/stream:
  → Same retrieve step
  → DeepSeekClient.generate(query, context, stream=True)
  → SSE response (text/event-stream)
```

### Step 30 — api/routes/admin.py
**Status**: ⬜ Pending

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/documents` | List ingested docs with chunk/entity counts |
| GET | `/documents/{id}` | Single document detail |
| DELETE | `/documents/{id}` | Cascade delete (chunks, entities) |
| GET | `/entities/{name}` | Entity + outgoing/incoming relationships |
| GET | `/entities/{name}/chunks` | Chunks mentioning this entity |
| GET | `/search` | Retrieval-only (no generation), `?q=...&top_k=...` |
| GET | `/health` | Pool status, model loaded, GPU available, DB size |

---

## Phase 9 — CLI (steps 31–33)

### Step 31 — cli/main.py
**Status**: ⬜ Pending

```python
import typer

app = typer.Typer(
    name="rag",
    help="RAG/KAG pipeline CLI for OCPP 2.1",
)

app.add_typer(ingest_app, name="ingest")
app.add_typer(query_app, name="query")
app.add_typer(eval_app, name="eval")
```

### Step 32 — cli/ingest.py
**Status**: ⬜ Pending

```bash
# Single file
rag ingest OCPP-2.1-Part2-Core.pdf --doc-type spec --version 2.1

# Directory
rag ingest data/specs/ --doc-type spec --version 2.1

# Options
--protocol        ocpp21 (default)
--doc-type        spec | test_suite | json_config | other
--version         2.1 (default)
--no-entities     skip entity extraction
--dry-run         chunk only, no DB write
```

### Step 33 — cli/query.py
**Status**: ⬜ Pending

```bash
# Single query
rag query "What fields are required in Authorize.req?"

# With options
rag query "..." --top-k 10 --stream --protocol ocpp21

# From file
rag query --file questions.txt
```

---

## Phase 10 — Tests (steps 34–36)

### Step 34 — Unit tests
**Status**: ⬜ Pending

- `tests/test_ingestion/test_cleaner.py` — whitespace, OCR fix, OCPP term normalization
- `tests/test_ingestion/test_metadata.py` — filename pattern extraction
- `tests/test_chunking/test_engine.py` — chunk size, overlap, strategy correctness

### Step 35 — Integration tests
**Status**: ⬜ Pending

Using `testcontainers[postgres]` for isolated PostgreSQL:

- `tests/test_retrieval/test_vector_search.py` — insert chunks with known embeddings, search, verify scores
- `tests/test_retrieval/test_hybrid.py` — end-to-end hybrid retrieval
- `tests/test_knowledge/test_extractor.py` — regex entity extraction on sample OCPP text

### Step 36 — End-to-end test
**Status**: ⬜ Pending

```
1. Create sample PDF (1-2 pages of OCPP-like text)
2. POST /ingest with sample PDF
3. POST /query "What is the purpose of Authorize.req?"
4. Assert response contains citations with page numbers
5. Assert response references at least one expected entity
```

---

## Phase 11 — Evaluation (steps 37–38)

### Step 37 — eval/metrics.py
**Status**: ⬜ Pending

```python
@dataclass
class EvalQuery:
    query: str
    relevant_chunk_ids: list[str]  # ground truth

class RetrievalEvaluator:
    def evaluate(self, retriever, queries) -> dict:
        metrics = defaultdict(list)
        for q in queries:
            results = await retriever.retrieve(q.query, top_k=10)
            metrics["mrr"].append(self._mrr(results, q.relevant_ids))
            metrics["recall@5"].append(self._recall_at_k(results, q.relevant_ids, 5))
            metrics["recall@10"].append(self._recall_at_k(results, q.relevant_ids, 10))
            metrics["ndcg@10"].append(self._ndcg_at_k(results, q.relevant_ids, 10))
        return {k: np.mean(v) for k, v in metrics.items()}

    def _mrr(results, relevant) -> float:
        """Mean Reciprocal Rank. 1 / rank of first relevant result."""

    def _recall_at_k(results, relevant, k) -> float:
        """|retrieved ∩ relevant| / |relevant| at top-k."""

    def _ndcg_at_k(results, relevant, k) -> float:
        """Normalized Discounted Cumulative Gain."""
```

### Step 38 — cli/eval.py
**Status**: ⬜ Pending

```bash
# Evaluate on a test set
rag eval data/eval/queries.jsonl --metrics mrr,recall,ndcg

# queries.jsonl format:
# {"query": "What is BootNotification?", "relevant": ["uuid1", "uuid2"]}
# {"query": "How does authorization work?", "relevant": ["uuid3"]}

# Benchmark chunking strategies
rag eval --benchmark-chunking

# Compare embedding models
rag eval --compare-embeddings bge-base bge-large gte-base
```

---

## Execution Order & Dependencies

```
Phase 1 (steps 1-6)     Scaffold           [COMPLETE: 1-5, PENDING: 6]
    │
Phase 2 (steps 7-8)     Storage layer       ← depends on Phase 1
    │
Phase 3 (steps 9-12)    Ingestion           ← depends on Phase 2
    │
    ├── Phase 4 (steps 13-14)  Embedding    ← depends on Phase 3
    │
    └── Phase 5 (steps 15-17)  Knowledge    ← depends on Phase 3
         │
         └── Phase 6 (steps 18-22)  Retrieval  ← depends on Phases 4, 5
              │
              └── Phase 7 (steps 23-24)  Generation  ← depends on Phase 6
                   │
                   ├── Phase 8 (steps 25-30)  API  ← depends on Phase 7
                   │
                   └── Phase 9 (steps 31-33)  CLI  ← depends on Phase 7
                        │
                        ├── Phase 10 (steps 34-36)  Tests  ← parallel with 8, 9
                        │
                        └── Phase 11 (steps 37-38)  Eval  ← depends on Phase 10
```

---

## Estimated Effort

| Phase | Steps | Days | Dependencies |
|-------|-------|------|-------------|
| 1 — Scaffold | 1–6 | 0.5 | None |
| 2 — Storage | 7–8 | 0.5 | Phase 1 |
| 3 — Ingestion | 9–12 | 1.5 | Phase 2 |
| 4 — Embedding | 13–14 | 0.5 | Phase 3 |
| 5 — Knowledge Graph | 15–17 | 1.5 | Phase 3 |
| 6 — Retrieval | 18–22 | 1.0 | Phases 4, 5 |
| 7 — Generation | 23–24 | 0.5 | Phase 6 |
| 8 — API | 25–30 | 1.0 | Phase 7 |
| 9 — CLI | 31–33 | 0.5 | Phase 7 |
| 10 — Tests | 34–36 | 1.0 | Phases 8, 9 (parallel) |
| 11 — Eval | 37–38 | 1.0 | Phase 10 |
| **Total** | **38** | **~9 days** | |

---

## Key Design Decisions

1. **Single PostgreSQL for vectors + graph** — eliminates sync issues between separate stores. A chunk links directly to entities in the same transaction via `chunk_entities`.

2. **SDPM chunking for specs** — OCPP specifications have strong hierarchical structure. SDPM's threshold-based merging respects section/topic boundaries that fixed-size chunkers would break.

3. **Two-pass entity extraction** — Regex for high-precision OCPP patterns (commands like `Authorize`, datatypes like `IdToken`). LLM for relationship extraction. Regex pass is free and instant; LLM pass is batched and cached.

4. **BGE model family for both embedding and reranking** — Consistent architecture and tokenizer. BGE query/passage asymmetry (`Represent this sentence...` prefix) is critical for retrieval quality.

5. **RRF over weighted fusion** — No need to normalize scores across strategies. Robust to outlier scores from one search path. Proven in academic IR benchmarks.

6. **asyncpg over psycopg2** — 3-5× faster for PostgreSQL. Non-blocking I/O is essential when the API serves concurrent queries with vector search + graph traversal.

7. **No LangChain/LlamaIndex** — These frameworks add abstraction layers that obscure retrieval logic. For domain-specific pipelines (OCPP), direct control over chunking, retrieval fusion, and graph traversal produces better results.

---

## Multi-Protocol Extension (Future)

The architecture, schema, and pipeline are protocol-agnostic. Adding a new protocol requires
only configuration + domain-specific regex patterns — no code changes to chunking, embedding,
retrieval, or generation layers.

### Full Protocol Roster

#### EV Charging Protocol

| Protocol | Scope | Input formats |
|----------|-------|---------------|
| **OCPP 2.1** 🔵 | Open Charge Point Protocol — CSMS ↔ ChargePoint messaging, security, smart charging, ISO 15118 integration | PDF spec, JSON schemas, test suites |
| **OCPI 2.2.1** | Open Charge Point Interface — roaming: CPO ↔ eMSP, locations, tokens, sessions, tariffs, CDRs | PDF spec, JSON modules |
| **ISO 15118-3** | Wired communication — physical layer and data link layer requirements for high-level communication | PDF spec |
| **ISO 15118-20 + Amd1** | 2nd gen network/application protocol — AC, DC, WPT, bidirectional (V2G), dynamic mode, multiplexed communication | PDF spec, EXI schemas |
| **ISO 15118-10** | Physical and data link layer conformance tests for ISO 15118 implementations | PDF spec, test procedures |
| **CharIN MCS** | Megawatt Charging System — implementation guidelines for >1MW DC charging (heavy-duty vehicles, marine, aviation) | PDF guidelines |

#### Electrical Safety & Hardware

| Protocol | Scope | Input formats |
|----------|-------|---------------|
| **IEC 61851-1 Ed1** | EV conductive charging system — general safety requirements, charging modes 1-4, control pilot, connector types, protection | PDF spec, test suites |
| **EN 50549** | Requirements for generating plants connected to distribution networks — type A/B/C/D, protection settings, frequency/voltage ride-through | PDF standard |
| **IEC 63380** | Local energy management systems — architecture, functional blocks, interface definitions for distributed energy resources | PDF spec |
| **IEC 63382** | Energy management systems — interface specification between EV and local EMS, demand-side flexibility | PDF spec |
| **IEC 61850-7-420** | Basic communication structure for distributed energy resources — logical nodes for DER (PV, battery, EV charger, CHP), grid automation integration, MMS/GOOSE/SV mapping | PDF standard |

#### Grid Code & Regulation

| Protocol | Scope | Input formats |
|----------|-------|---------------|
| **RfG v2 + ACER** | Requirements for Generators — EU grid code for power-generating modules, frequency stability, voltage control, fault ride-through, ACER amendment on non-exhaustive parameters | PDF regulation, parameter tables |
| **DCC 2.0 + ACER** | Demand Connection Code — grid connection requirements for demand facilities, demand response, power quality, ACER amendment on demand-side flexibility | PDF regulation |
| **AFIR** | Alternative Fuels Infrastructure Regulation — EU regulation on EV charging/refueling infrastructure deployment, payment, pricing transparency, ad-hoc access | PDF regulation |

#### Demand Response & Building Energy

| Protocol | Scope | Input formats |
|----------|-------|---------------|
| **OpenADR 3.0** | Open Automated Demand Response — VEN/VTN signaling, demand response events, price/load/setpoint signals, report telemetry | PDF spec, XSD schemas |
| **eeBus** | Smart building/home energy management — SHIP/E-Mobility profiles, heat pump, PV, battery, EV charging integration, energy monitoring | PDF spec, XML profiles |

#### Test Suites (Normalization Bodies)

| Source | Scope |
|--------|-------|
| **OCA** (Open Charge Alliance) | OCPP 2.1 conformance test suites — core, security, smart charging, ISO 15118 profiles |
| **CharIN** | CCS/ISO 15118 interoperability test cases, MCS conformance, Plug & Charge certification |
| **DNV / TÜV / DEKRA** | IEC 61851 compliance testing, grid code certification procedures |
| **CEN/CENELEC** | EN 50549 harmonized test procedures, EU grid code compliance verification |
| **VDE / FNN** | German grid connection rules, VDE-AR-N 4105/4110/4120 test suites |

### Extension Procedure (per protocol)

Same 5 steps, repeated:

1. **`protocols` table**: INSERT one row — id, name, full_name, namespace
2. **`entity_types` table**: INSERT protocol-specific entity types (command, datatype, module, role, signal_type, etc.)
3. **`knowledge/entities.py`**: Add per-type regex patterns for Pass 1 extraction
4. **`cross_protocol_mappings`**: Populate equivalent-concept mappings (see examples below)
5. **`chunking` config**: Add per-protocol chunking strategy in `default.yaml` (SDPM for specs, sentence for test suites)

### Cross-Protocol Mapping Examples

These are the high-value links that make KAG queryable across protocols:

| Source concept | Target concept | Relation |
|----------------|----------------|----------|
| OCPP.Authorize | OCPI.Tokens | equivalent — both represent EV driver authentication |
| OCPP.Transaction | OCPI.Session / CDR | equivalent — same real-world charging session |
| OCPP.ChargingSchedule | OpenADR.DemandResponseEvent | overlaps — both express power/time constraints |
| OCPP.SmartCharging | IEC 63380.load_management | overlaps — local vs. centralized optimization |
| ISO15118-20.V2G | RfG.FRT | overlaps — vehicle-to-grid frequency response overlaps grid code fault ride-through |
| ISO15118-20.dynamic_mode | OCPP.SmartCharging | subsumes — ISO dynamic mode extends OCPP smart charging with real-time negotiation |
| IEC 61851.Mode4 | ISO15118-20.DC_BPT | enables — IEC physical layer enables ISO communication for bidirectional DC |
| IEC 61851.control_pilot | ISO15118-3 | enables — IEC PWM states are the transport for ISO 15118-3 data link |
| CharIN.MCS | IEC 61851.Mode4_extension | extends — MCS extends Mode4 to >1MW, new connector/pin definitions |
| AFIR.payment_transparency | OCPI.Tariffs | overlaps — AFIR regulatory requirement maps to OCPI tariff data model |
| RfG.FSM | EN 50549.protection_settings | subsumes — grid code frequency-sensitive mode subsumes national protection parameters |
| DCC 2.0.demand_response | OpenADR 3.0.event | equivalent — demand-side flexibility through OpenADR signaling |
| IEC 61850-7-420.DER_logical_node | IEC 63380.EMS_interface | enables — IEC 61850 logical nodes underpin EMS DER modeling |
| eeBus.heat_pump_profile | IEC 63380.EMS_interface | equivalent — building EMS ↔ DER communication |
| ISO15118-20.WPT | ISO 15118-10.WPT_tests | tested_by — wireless power transfer spec tested by conformance procedures |

### Estimated Impact

| Metric | OCPP-only | Full roster (16+ protocols) |
|--------|-----------|---------------------------|
| `protocols` rows | 1 | ~16 |
| `entity_types` rows | 9 | ~80-120 |
| Regex patterns | 9 | ~80-120 |
| Cross-protocol mappings | 0 | ~50-100 (manually curated) |
| Chunking strategies | 3 (spec/test/fallback) | 3 (same — all specs use SDPM) |
| Schema changes | 0 | 0 |
| Pipeline code changes | 0 | 0 (only config + patterns) |
| `config/default.yaml` additions | 0 | ~16 protocol entries under `chunking` |
| **Additional effort** | — | **~3-4 days** (mostly entity type definition + cross-protocol mapping curation) |
