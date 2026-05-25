"""PostgreSQL pgvector operations — chunk insert, vector search, keyword search."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import asyncpg


import re


def _vec(embedding: list[float] | None) -> str | None:
    """Convert list[float] to pgvector string: '[0.1,0.2,...]'."""
    if embedding is None:
        return None
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _prepare_tsquery(text: str) -> str:
    """Split camelCase/PascalCase for PostgreSQL full-text search.
    'VoltWattCurve' → 'Volt Watt Curve' so tsquery tokenizes correctly.
    """
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    return text.replace("_", " ")


# ── Data types ────────────────────────────────────────────

@dataclass
class ChunkInsert:
    """A chunk ready for database insertion."""
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    content_hash: str | None = None
    embedding: list[float] | None = None       # bge-base → 768 floats
    strategy: str = ""
    section_title: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    token_count: int | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.content_hash is None:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()


@dataclass
class VectorSearchResult:
    """A single result from pgvector cosine similarity search."""
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    section_title: str | None
    page_start: int | None
    page_end: int | None
    similarity: float           # 1 - cosine_distance, higher = more similar


@dataclass
class KeywordSearchResult:
    """A single result from PostgreSQL full-text search."""
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    section_title: str | None
    page_start: int | None
    page_end: int | None
    rank: float                 # ts_rank, higher = more relevant


# ── Store ─────────────────────────────────────────────────

class VectorStore:
    """Async PostgreSQL pgvector operations.

    All methods accept an asyncpg Pool and are safe for concurrent use.
    The pool should be created externally (e.g. FastAPI lifespan) and
    passed to the store — the store never owns the connection lifecycle.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Write ───────────────────────────────────────────

    async def insert_document(
        self,
        *,
        protocol_id: int,
        source_path: str,
        doc_type: str,
        title: str | None = None,
        version: str | None = None,
        part: str | None = None,
        page_count: int | None = None,
        raw_bytes: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        """Insert a document record and return its UUID."""
        row = await self._pool.fetchrow(
            """
            INSERT INTO documents
                (protocol_id, source_path, doc_type, title, version, part,
                 page_count, raw_bytes, metadata)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            RETURNING id
            """,
            protocol_id, source_path, doc_type, title, version, part,
            page_count, raw_bytes, metadata,
        )
        assert row is not None
        return row["id"]

    async def insert_chunks(self, chunks: list[ChunkInsert]) -> int:
        """Bulk-insert chunks via asyncpg executemany.

        Returns the number of rows inserted.
        """
        if not chunks:
            return 0

        async with self._pool.acquire() as conn:
            count = await conn.executemany(
                """
                INSERT INTO chunks
                    (id, document_id, chunk_index, content, content_hash,
                     embedding, strategy, section_title, page_start, page_end,
                     token_count, metadata)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                ON CONFLICT (document_id, chunk_index) DO UPDATE SET
                    content = EXCLUDED.content,
                    content_hash = EXCLUDED.content_hash,
                    embedding = EXCLUDED.embedding,
                    section_title = EXCLUDED.section_title,
                    token_count = EXCLUDED.token_count,
                    metadata = EXCLUDED.metadata
                """,
                [
                    (
                        c.id,
                        c.document_id,
                        c.chunk_index,
                        c.content,
                        c.content_hash,
                        _vec(c.embedding),
                        c.strategy,
                        c.section_title,
                        c.page_start,
                        c.page_end,
                        c.token_count,
                        c.metadata,
                    )
                    for c in chunks
                ],
            )
        return count

    async def insert_chunks_copy(self, chunks: list[ChunkInsert]) -> int:
        """Bulk-insert chunks via COPY protocol (faster for large batches).

        Returns the number of rows inserted.
        """
        if not chunks:
            return 0

        columns = [
            "id", "document_id", "chunk_index", "content", "content_hash",
            "embedding", "strategy", "section_title", "page_start", "page_end",
            "token_count", "metadata",
        ]
        records = [
            (
                c.id,
                c.document_id,
                c.chunk_index,
                c.content,
                c.content_hash,
                _vec(c.embedding),
                c.strategy,
                c.section_title,
                c.page_start,
                c.page_end,
                c.token_count,
                c.metadata,
            )
            for c in chunks
        ]

        async with self._pool.acquire() as conn:
            await conn.copy_records_to_table("chunks", records=records, columns=columns)
        return len(chunks)

    async def update_embeddings(
        self, updates: list[tuple[UUID, list[float]]]
    ) -> int:
        """Batch-update embedding vectors for existing chunks.

        Each update is (chunk_id, embedding_list).
        """
        if not updates:
            return 0

        async with self._pool.acquire() as conn:
            count = await conn.executemany(
                "UPDATE chunks SET embedding = $2 WHERE id = $1",
                [(uid, _vec(emb)) for uid, emb in updates],
            )
        return count

    # ── Read ────────────────────────────────────────────

    async def vector_search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 20,
        protocol_id: int | None = None,
        doc_type: str | None = None,
        ef_search: int = 100,
    ) -> list[VectorSearchResult]:
        """Cosine similarity search via pgvector HNSW index.

        The ``<=>`` operator returns cosine *distance* (0 = identical, 2 = opposite).
        We compute *similarity* = 1 - distance so higher is better.
        """
        clauses = ["TRUE"]
        params: list[Any] = [_vec(query_embedding), ef_search, top_k]

        if protocol_id is not None:
            clauses.append(
                "document_id IN (SELECT id FROM documents WHERE protocol_id = $4)"
            )
            params.append(protocol_id)
            offset = 1
        else:
            offset = 0

        if doc_type is not None:
            idx = 4 + offset
            clauses.append(
                f"document_id IN (SELECT id FROM documents WHERE doc_type = ${idx})"
            )
            params.append(doc_type)

        where = " AND ".join(clauses)

        # asyncpg: one statement per execute(); run SET before SELECT
        await self._pool.execute("SET LOCAL hnsw.ef_search = $1", ef_search)
        rows = await self._pool.fetch(
            f"""SELECT c.id, c.document_id, c.chunk_index, c.content,
                   c.section_title, c.page_start, c.page_end,
                   1.0 - (c.embedding <=> $1) AS similarity
            FROM chunks c
            WHERE c.embedding IS NOT NULL AND {where}
            ORDER BY c.embedding <=> $1
            LIMIT $2""",
            *[query_embedding, top_k],
        )
        return [
            VectorSearchResult(
                chunk_id=r["id"],
                document_id=r["document_id"],
                chunk_index=r["chunk_index"],
                content=r["content"],
                section_title=r["section_title"],
                page_start=r["page_start"],
                page_end=r["page_end"],
                similarity=float(r["similarity"]),
            )
            for r in rows
        ]

    async def keyword_search(
        self,
        query: str,
        *,
        top_k: int = 10,
        protocol_id: int | None = None,
        doc_type: str | None = None,
    ) -> list[KeywordSearchResult]:
        """PostgreSQL full-text search via tsvector/tsquery.

        Uses ``plainto_tsquery('english', $1)`` to parse the user query
        into a tsquery, then ``ts_rank`` for scoring.
        """
        clauses = ["c.tsv @@ plainto_tsquery('english', $1)"]
        params: list[Any] = [_prepare_tsquery(query), top_k]

        if protocol_id is not None:
            clauses.append(
                "c.document_id IN (SELECT id FROM documents WHERE protocol_id = $3)"
            )
            params.append(protocol_id)
            offset = 1
        else:
            offset = 0

        if doc_type is not None:
            idx = 3 + offset
            clauses.append(
                f"c.document_id IN (SELECT id FROM documents WHERE doc_type = ${idx})"
            )
            params.append(doc_type)

        where = " AND ".join(clauses)

        rows = await self._pool.fetch(
            f"""
            SELECT c.id, c.document_id, c.chunk_index, c.content,
                   c.section_title, c.page_start, c.page_end,
                   ts_rank(c.tsv, plainto_tsquery('english', $1)) AS rank
            FROM chunks c
            WHERE {where}
            ORDER BY rank DESC
            LIMIT $2
            """,
            *params,
        )
        # Always supplement with ILIKE (tsquery stemming often misses key terms)
        ilike_rows = await self._pool.fetch(
            """SELECT c.id, c.document_id, c.chunk_index, c.content,
                   c.section_title, c.page_start, c.page_end,
                   0.5::real AS rank
            FROM chunks c
            WHERE c.content ILIKE $1 OR c.section_title ILIKE $1
            ORDER BY c.page_start
            LIMIT $2""",
            f"%{query}%", top_k,
        )
        # Merge tsquery + ILIKE results, deduplicate by id, keep higher rank
        seen: dict[str, dict[str, Any]] = {}
        for r in list(rows) + list(ilike_rows):
            cid = r["id"]
            if cid not in seen or r["rank"] > seen[cid]["rank"]:
                seen[cid] = dict(r)
        rows = sorted(seen.values(), key=lambda r: r["rank"], reverse=True)[:top_k]

        return [
            KeywordSearchResult(
                chunk_id=r["id"],
                document_id=r["document_id"],
                chunk_index=r["chunk_index"],
                content=r["content"],
                section_title=r["section_title"],
                page_start=r["page_start"],
                page_end=r["page_end"],
                rank=float(r["rank"]),
            )
            for r in rows
        ]

    async def get_pending_chunks(
        self, batch_size: int = 256
    ) -> list[tuple[UUID, str]]:
        """Return (chunk_id, content) for chunks without an embedding."""
        rows = await self._pool.fetch(
            """
            SELECT id, content
            FROM chunks
            WHERE embedding IS NULL
            ORDER BY created_at
            LIMIT $1
            """,
            batch_size,
        )
        return [(r["id"], r["content"]) for r in rows]

    async def delete_document(self, document_id: UUID) -> int:
        """Cascade-delete a document and all its chunks/entities.

        Returns the number of document rows deleted (should be 1 or 0).
        """
        result = await self._pool.execute(
            "DELETE FROM documents WHERE id = $1", document_id
        )
        # asyncpg.execute returns a status string like "DELETE 1"
        return int(result.split()[-1]) if result else 0

    async def list_documents(
        self, protocol_id: int | None = None
    ) -> list[dict[str, Any]]:
        """List ingested documents with chunk/entity counts."""
        rows = await self._pool.fetch(
            """
            SELECT
                d.id, d.protocol_id, d.source_path, d.doc_type,
                d.title, d.version, d.part, d.page_count,
                d.ingested_at, d.metadata,
                COUNT(DISTINCT c.id) AS chunk_count,
                COUNT(DISTINCT ce.entity_id) AS entity_count
            FROM documents d
            LEFT JOIN chunks c ON c.document_id = d.id
            LEFT JOIN chunk_entities ce ON ce.chunk_id = c.id
            WHERE ($1::int IS NULL OR d.protocol_id = $1)
            GROUP BY d.id
            ORDER BY d.ingested_at DESC
            """,
            protocol_id,
        )
        return [dict(r) for r in rows]
