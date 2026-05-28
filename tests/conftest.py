"""Shared test fixtures — testcontainers PostgreSQL, async pool, stores."""

import asyncio

import asyncpg
import pytest
from testcontainers.postgres import PostgresContainer

from rag_ocpp.storage.graph import GraphStore
from rag_ocpp.storage.audit import AuditStore
from rag_ocpp.storage.vector import VectorStore


@pytest.fixture(scope="session")
def postgres_container():
    """Session-scoped pgvector PostgreSQL container."""
    import subprocess
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("Docker not available")
    container = PostgresContainer(
        image="pgvector/pgvector:pg16",
        username="test", password="test", dbname="test_rag",
    )
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def pool(postgres_container):
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    dsn = f"postgresql://test:test@{host}:{port}/test_rag"
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5)

    # Apply minimal schema for tests (one statement per execute for asyncpg compatibility)
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
        await conn.execute("""CREATE TABLE IF NOT EXISTS protocols (
            id SMALLINT PRIMARY KEY, name TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL, namespace TEXT NOT NULL)""")
        await conn.execute(
            "INSERT INTO protocols VALUES "
            "(1,'ocpp21','OCPP 2.1','ocpp') ON CONFLICT DO NOTHING"
        )
        await conn.execute("""CREATE TABLE IF NOT EXISTS entity_types (
            id SMALLINT, protocol_id SMALLINT REFERENCES protocols(id),
            name TEXT NOT NULL, PRIMARY KEY (id, protocol_id))""")
        await conn.execute("""INSERT INTO entity_types VALUES
            (1,1,'command'),(2,1,'datatype'),(3,1,'component'),
            (4,1,'variable'),(5,1,'enum'),(6,1,'message_flow'),
            (7,1,'functional_block'),(8,1,'error_code'),(9,1,'test_case')
            ON CONFLICT DO NOTHING""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS documents (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            protocol_id SMALLINT NOT NULL REFERENCES protocols(id),
            source_path TEXT NOT NULL, doc_type TEXT NOT NULL DEFAULT 'spec',
            title TEXT, version TEXT, part TEXT, page_count INT,
            raw_bytes BIGINT, ingested_at TIMESTAMPTZ DEFAULT now(),
            metadata JSONB)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS chunks (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            chunk_index INT NOT NULL, content TEXT NOT NULL, content_hash TEXT NOT NULL,
            embedding vector(1024), strategy TEXT NOT NULL DEFAULT 'semantic',
            section_title TEXT, page_start INT, page_end INT,
            token_count INT, metadata JSONB, created_at TIMESTAMPTZ DEFAULT now(),
            tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
            UNIQUE (document_id, chunk_index))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS entities (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            type_id SMALLINT NOT NULL, protocol_id SMALLINT NOT NULL,
            name TEXT NOT NULL, description TEXT, aliases JSONB, properties JSONB,
            FOREIGN KEY (type_id, protocol_id) REFERENCES entity_types(id, protocol_id),
            UNIQUE (protocol_id, type_id, name))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS relationships (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            source_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            target_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            rel_type TEXT NOT NULL, properties JSONB,
            UNIQUE (source_id, target_id, rel_type))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS chunk_entities (
            chunk_id UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
            entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            confidence REAL DEFAULT 1.0,
            PRIMARY KEY (chunk_id, entity_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS query_log (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            query_text TEXT NOT NULL, top_chunks JSONB, top_scores JSONB,
            strategy TEXT, latency_ms INT, created_at TIMESTAMPTZ DEFAULT now())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS audit_events (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            event_type TEXT NOT NULL, surface TEXT NOT NULL, action TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'success', actor_id TEXT, session_id TEXT,
            correlation_id TEXT, resource_type TEXT, resource_id TEXT,
            latency_ms INT, metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT now())""")

    yield pool
    await pool.close()


@pytest.fixture
async def vector_store(pool) -> VectorStore:
    return VectorStore(pool)


@pytest.fixture
async def graph_store(pool) -> GraphStore:
    return GraphStore(pool)


@pytest.fixture
async def audit_store(pool) -> AuditStore:
    return AuditStore(pool)


@pytest.fixture(autouse=True)
async def cleanup(pool):
    yield
    async with pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE chunk_entities, relationships, entities, chunks, "
            "documents, query_log, audit_events CASCADE"
        )
