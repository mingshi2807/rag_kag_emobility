"""Shared test fixtures — testcontainers PostgreSQL, async pool, stores."""

import asyncio
from pathlib import Path

import asyncpg
import pytest
from testcontainers.postgres import PostgresContainer

from rag_ocpp.storage.graph import GraphStore
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

    schema_path = Path(__file__).parent.parent / "src" / "rag_ocpp" / "storage" / "schema.sql"
    if schema_path.exists():
        async with pool.acquire() as conn:
            await conn.execute(schema_path.read_text())

    yield pool
    await pool.close()


@pytest.fixture
async def vector_store(pool) -> VectorStore:
    return VectorStore(pool)


@pytest.fixture
async def graph_store(pool) -> GraphStore:
    return GraphStore(pool)


@pytest.fixture(autouse=True)
async def cleanup(pool):
    yield
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE chunk_entities, relationships, entities, chunks, documents, query_log CASCADE")
