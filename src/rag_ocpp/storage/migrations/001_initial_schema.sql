-- ============================================================================
-- RAG/KAG Pipeline — PostgreSQL Schema
-- Protocol: OCPP 2.1 (extensible to OCPI, IEC 61851, OpenADR, RfG)
-- ============================================================================

-- ── Extensions ────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Protocols registry ────────────────────────────────────────

CREATE TABLE protocols (
    id          SMALLINT PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,       -- machine key: 'ocpp21'
    full_name   TEXT NOT NULL,              -- human label: 'OCPP 2.1'
    namespace   TEXT NOT NULL               -- short prefix: 'ocpp'
);

INSERT INTO protocols (id, name, full_name, namespace) VALUES
    (1, 'ocpp21',   'OCPP 2.1',          'ocpp');

-- ── Documents ─────────────────────────────────────────────────

CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    protocol_id     SMALLINT NOT NULL REFERENCES protocols(id),
    source_path     TEXT NOT NULL,
    doc_type        TEXT NOT NULL CHECK (doc_type IN ('spec', 'test_suite', 'json_config', 'other')),
    title           TEXT,
    version         TEXT,           -- e.g. "2.1"
    part            TEXT,           -- e.g. "Part 2: Core", "Part 4: Security"
    page_count      INT,
    raw_bytes       BIGINT,
    ingested_at     TIMESTAMPTZ DEFAULT now(),
    metadata        JSONB
);

CREATE INDEX documents_protocol ON documents(protocol_id);
CREATE INDEX documents_type    ON documents(doc_type);

-- Source file registry for source-aware enterprise evidence.
-- One row per ingested PDF, CSV/XLSX, or JSON schema artifact.
CREATE TABLE source_documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    protocol_id     SMALLINT NOT NULL REFERENCES protocols(id),
    source_type     TEXT NOT NULL CHECK (
        source_type IN ('spec_pdf', 'device_model_table', 'json_schema', 'appendix_csv')
    ),
    source_path     TEXT NOT NULL,
    title           TEXT,
    version         TEXT,
    edition         TEXT,
    document_date   DATE,
    content_hash    TEXT NOT NULL,
    raw_bytes       BIGINT,
    metadata        JSONB,
    ingested_at     TIMESTAMPTZ DEFAULT now(),

    UNIQUE(protocol_id, source_path, content_hash)
);

CREATE INDEX source_documents_protocol ON source_documents(protocol_id);
CREATE INDEX source_documents_type ON source_documents(source_type);
CREATE INDEX source_documents_hash ON source_documents(content_hash);

-- Normalized source-aware evidence records extracted from source files.
-- These records are the stable bridge between raw sources, chunks, and graph nodes.
CREATE TABLE corpus_records (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_document_id  UUID NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    record_type         TEXT NOT NULL,
    stable_key          TEXT NOT NULL,
    title               TEXT,
    content             TEXT NOT NULL,
    content_hash        TEXT NOT NULL,
    page_start          INT,
    page_end            INT,
    row_number          INT,
    section_title       TEXT,
    entity_name         TEXT,
    entity_type         TEXT,
    metadata            JSONB,
    created_at          TIMESTAMPTZ DEFAULT now(),

    UNIQUE(source_document_id, stable_key)
);

CREATE INDEX corpus_records_source ON corpus_records(source_document_id);
CREATE INDEX corpus_records_type ON corpus_records(record_type);
CREATE INDEX corpus_records_entity ON corpus_records(entity_type, entity_name);
CREATE INDEX corpus_records_hash ON corpus_records(content_hash);

-- ── Chunks (vector store) ─────────────────────────────────────

CREATE TABLE chunks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL,
    content         TEXT NOT NULL,
    content_hash    TEXT NOT NULL,            -- SHA-256 hex, for dedup
    embedding       VECTOR(1024),            -- bge-large-en-v1.5 dimension
    strategy        TEXT,                    -- 'sdpm', 'sentence', 'recursive'
    section_title   TEXT,                    -- extracted from PDF ToC / heading
    page_start      INT,
    page_end        INT,
    token_count     INT,
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT now(),

    UNIQUE(document_id, chunk_index)
);

-- HNSW index for approximate nearest neighbor (cosine distance)
CREATE INDEX chunks_embedding_hnsw ON chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- Full-text search column (auto-generated)
ALTER TABLE chunks ADD COLUMN tsv TSVECTOR
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
CREATE INDEX chunks_tsv_gin ON chunks USING GIN (tsv);

-- Standard index for chunk dedup / lookups
CREATE INDEX chunks_content_hash ON chunks(content_hash);

-- ── Entity types (per protocol) ───────────────────────────────

CREATE TABLE entity_types (
    id          SMALLINT NOT NULL,
    protocol_id SMALLINT NOT NULL REFERENCES protocols(id),
    name        TEXT NOT NULL,              -- e.g. 'command', 'datatype', 'component'
    UNIQUE(protocol_id, name),
    PRIMARY KEY(id, protocol_id)
);

INSERT INTO entity_types (id, protocol_id, name) VALUES
    (1,  1, 'command'),
    (2,  1, 'datatype'),
    (3,  1, 'component'),
    (4,  1, 'variable'),
    (5,  1, 'enum'),
    (6,  1, 'message_flow'),
    (7,  1, 'functional_block'),
    (8,  1, 'error_code'),
    (9,  1, 'test_case'),
    (10, 1, 'message'),
    (11, 1, 'request'),
    (12, 1, 'response'),
    (13, 1, 'field'),
    (14, 1, 'attribute'),
    (15, 1, 'requirement'),
    (16, 1, 'schema');

-- ── Entities (knowledge graph nodes) ──────────────────────────

CREATE TABLE entities (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type_id     SMALLINT NOT NULL,
    protocol_id SMALLINT NOT NULL,
    name        TEXT NOT NULL,
    description TEXT,
    aliases     TEXT[],                     -- alternative names
    properties  JSONB,                      -- e.g. {"required": true, "cardinality": "1..*"}
    FOREIGN KEY(type_id, protocol_id) REFERENCES entity_types(id, protocol_id),
    UNIQUE(protocol_id, type_id, name)
);

CREATE INDEX entities_name     ON entities(name);
CREATE INDEX entities_aliases  ON entities USING GIN (aliases);
CREATE INDEX entities_protocol ON entities(protocol_id);

-- ── Relationships (knowledge graph edges) ─────────────────────

CREATE TABLE relationships (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id   UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_id   UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    rel_type    TEXT NOT NULL,      -- 'uses', 'extends', 'requires', 'responds_to',
                                    -- 'belongs_to', 'tested_by', 'references'
    properties  JSONB,
    UNIQUE(source_id, target_id, rel_type)
);

CREATE INDEX relationships_source ON relationships(source_id);
CREATE INDEX relationships_target ON relationships(target_id);
CREATE INDEX relationships_type   ON relationships(rel_type);

-- ── Bridge: chunk ↔ entity ────────────────────────────────────

CREATE TABLE chunk_entities (
    chunk_id    UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    entity_id   UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    confidence  REAL DEFAULT 1.0,
    span_start  INT,                    -- character offset within chunk content
    span_end    INT,
    PRIMARY KEY(chunk_id, entity_id)
);

CREATE INDEX chunk_entities_entity ON chunk_entities(entity_id);

-- ── Cross-protocol mappings (for future multi-protocol) ────────

CREATE TABLE cross_protocol_mappings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_entity   UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_entity   UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation        TEXT NOT NULL,      -- 'equivalent', 'subsumes', 'overlaps', 'contradicts'
    confidence      REAL DEFAULT 1.0,
    evidence_chunk  UUID REFERENCES chunks(id),
    UNIQUE(source_entity, target_entity, relation)
);

-- ── Query log (evaluation / observability) ─────────────────────

CREATE TABLE query_log (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_text  TEXT NOT NULL,
    top_chunks  UUID[],
    top_scores  REAL[],
    strategy    TEXT,                    -- 'hybrid', 'vector_only', 'keyword_only'
    latency_ms  INT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Privacy-preserving enterprise audit trail.
-- Do not store raw prompts, source chunks, generated answers, secrets, or full query text.
CREATE TABLE audit_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type      TEXT NOT NULL,
    surface         TEXT NOT NULL,
    action          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'success',
    actor_id        TEXT,
    session_id      TEXT,
    correlation_id  TEXT,
    resource_type   TEXT,
    resource_id     TEXT,
    latency_ms      INT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX audit_events_type_created ON audit_events(event_type, created_at DESC);
CREATE INDEX audit_events_surface_created ON audit_events(surface, created_at DESC);
CREATE INDEX audit_events_correlation ON audit_events(correlation_id);
CREATE INDEX audit_events_resource ON audit_events(resource_type, resource_id);
