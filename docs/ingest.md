# Ingestion Scale — Chunk Thresholds & Document Estimates

> Last updated: 2026-05-22

---

## Chunking Parameters (current)

| Parameter | Value | Purpose |
|-----------|-------|---------|
| Strategy (specs) | SDPM | Semantic Double-Pass Merging — preserves section boundaries |
| Chunk size | 512 tokens | ~350–400 words, 1–2 paragraphs |
| Overlap | 64 tokens | ~50 words of context bridging |
| Semantic threshold | 0.5 | Merge sentences where cosine similarity > 0.5 |
| Min sentences | 3 | Prevent orphan single-sentence chunks |

**Why 512 tokens for OCPP specs**: Each chunk captures a complete concept (command definition, parameter table preamble, message flow description) without mixing unrelated sections. SDPM's threshold-based merging respects the hierarchical structure of technical specifications (Part → Section → Subsection → Paragraph).

---

## Per-Chunk Calculation

```
1 page (technical spec) ≈ 300 words (tables, diagrams reduce density)
1 word ≈ 1.33 tokens (English technical prose)
1 page ≈ 400 tokens
1 chunk = 512 tokens ≈ 1.28 pages per chunk

Formula: chunks ≈ pages × 300 × 1.33 ÷ 512 ≈ pages × 0.78
```

---

## OCPP 2.1 Suite (Current Scope)

| Source | Pages | Est. chunks |
|--------|-------|-------------|
| OCPP 2.1 Core Specification (all parts) | 1,000 | 780 |
| OCPP 2.1 Test Suites (OCA) | 1,500 | 1,170 |
| **OCPP 2.1 Total** | **2,500** | **1,950** |

---

## Full 16-Protocol Roster (Future Scope)

### EV Charging Protocol

| Protocol | Est. pages | Est. chunks |
|----------|-----------|-------------|
| OCPP 2.1 (spec + tests) | 2,500 | 1,950 |
| OCPI 2.2.1 | 500 | 390 |
| ISO 15118-20 + Amd1 | 800 | 625 |
| ISO 15118-3 | 200 | 155 |
| ISO 15118-10 | 150 | 115 |
| CharIN MCS | 200 | 155 |
| **Subtotal** | **4,350** | **3,390** |

### Electrical Safety & Hardware

| Protocol | Est. pages | Est. chunks |
|----------|-----------|-------------|
| IEC 61851-1 Ed1 | 300 | 235 |
| EN 50549 | 200 | 155 |
| IEC 63380 | 150 | 115 |
| IEC 63382 | 150 | 115 |
| IEC 61850-7-420 | 400 | 310 |
| **Subtotal** | **1,200** | **930** |

### Grid Code & Regulation

| Protocol | Est. pages | Est. chunks |
|----------|-----------|-------------|
| RfG v2 + ACER amendment | 600 | 470 |
| DCC 2.0 + ACER amendment | 500 | 390 |
| AFIR | 150 | 115 |
| **Subtotal** | **1,250** | **975** |

### Demand Response & Building Energy

| Protocol | Est. pages | Est. chunks |
|----------|-----------|-------------|
| OpenADR 3.0 | 400 | 310 |
| eeBus | 300 | 235 |
| **Subtotal** | **700** | **545** |

### Test Suites (Normalization Bodies)

| Source | Est. pages | Est. chunks |
|--------|-----------|-------------|
| OCA (OCPP 2.1 conformance) | 1,500 | 1,170 |
| CharIN (CCS/ISO 15118/MCS) | 1,000 | 780 |
| DNV / TÜV / DEKRA (IEC 61851, grid code) | 800 | 625 |
| CEN/CENELEC (EN 50549, EU grid code) | 1,000 | 780 |
| VDE / FNN (German grid rules) | 700 | 545 |
| **Subtotal** | **5,000** | **3,900** |

### Full Roster Summary

| Category | Pages | Chunks |
|----------|-------|--------|
| EV Charging Protocol | 4,350 | 3,390 |
| Electrical Safety & Hardware | 1,200 | 930 |
| Grid Code & Regulation | 1,250 | 975 |
| Demand Response & Building | 700 | 545 |
| Test Suites | 5,000 | 3,900 |
| **Full Roster** | **12,500** | **9,750** |

---

## Threshold Analysis

### Where is 50,000 chunks?

| Scenario | Pages | Chunks | % of 50K |
|----------|-------|--------|----------|
| OCPP 2.1 only (current) | 2,500 | 1,950 | 3.9% |
| Full 16-protocol roster | 12,500 | 9,750 | 19.5% |
| 5× full roster | 62,500 | 48,750 | 97.5% |
| **50,000 chunks reached at** | **~64,000 pages** | | |

### What 50,000 chunks actually means

- ~64,000 pages of technical specifications
- ~5 full copies of the entire 16-protocol knowledge base
- ~80 OCPP-sized specification suites

### At what scale should parameters change?

| Threshold | Action needed |
|-----------|--------------|
| < 10,000 chunks | No changes. Current parameters are optimal. |
| 10,000–50,000 chunks | No parameter changes. Consider increasing ef_search for HNSW quality. |
| 50,000+ chunks | Consider: increase chunk_size to 768 tokens. Increase max_connections pool. Tune ef_search and ef_construction. |
| 100,000+ chunks | Add max_chunks_per_doc safety cap. Consider partitioning by protocol. |

---

## PostgreSQL Scaling Context

pgvector with HNSW index scales to millions of vectors at sub-10ms latency:

| Chunks | HNSW latency (cosine, ef_search=100) | RAM (768-dim) |
|--------|--------------------------------------|---------------|
| 1,000 | < 1ms | ~3 MB |
| 10,000 | ~1ms | ~30 MB |
| 50,000 | ~2ms | ~150 MB |
| 100,000 | ~3ms | ~300 MB |
| 1,000,000 | ~10ms | ~3 GB |

The current `docker-compose.yml` allocates `shared_buffers=2GB` and `effective_cache_size=6GB`, which comfortably handles the full 16-protocol roster entirely in PostgreSQL shared memory.

---

## Ingestion Pipeline Flow

```
PDF file (11MB, 500 pages)
    │
    ▼
DocumentParser.parse()          ← PyMuPDF text + pdfplumber tables
    │  ~2-5 seconds
    ▼
TextCleaner.clean()             ← NFKC, strip headers, fix OCR, normalize terms
    │  < 1 second
    ▼
OCPPMetadataExtractor.extract() ← Filename patterns + content heuristics
    │  < 0.1 seconds
    ▼
ChunkingEngine.chunk()          ← SDPM: 512/64, threshold 0.5
    │  ~1-3 seconds (Rust core)
    ▼
[~390 chunks]                   ← each: content, hash, page range, section title
    │
    ▼
BatchEmbedder.embed_all_pending() ← BGE-base-en, GPU batch=256
    │  ~5-15 seconds (GPU)
    ▼
VectorStore.insert_chunks()     ← asyncpg COPY protocol
    │  < 1 second
    ▼
[~390 rows in chunks table]     ← vectors stored, HNSW index updated
    │  ~30 seconds total per 500-page PDF
    ▼
EntityExtractor (Phase 5)       ← Regex + LLM, ~10-60 seconds
    │
    ▼
Done. Ready for retrieval.
```
