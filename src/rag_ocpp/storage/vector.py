"""PostgreSQL pgvector operations — chunk insert, vector search, keyword search."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import asyncpg


def _vec(embedding: list[float] | None) -> str | None:
    """Convert list[float] to pgvector string: '[0.1,0.2,...]'."""
    if embedding is None:
        return None
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _json(value: Any) -> str | None:
    """Convert structured metadata to JSON for PostgreSQL JSONB columns."""
    if value is None:
        return None
    return json.dumps(value)


def _prepare_tsquery(text: str) -> str:
    """Split camelCase/PascalCase for PostgreSQL full-text search.
    'VoltWattCurve' → 'Volt Watt Curve' so tsquery tokenizes correctly.
    """
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    return text.replace("_", " ")


_STOPWORDS = {
    "what",
    "which",
    "where",
    "when",
    "with",
    "from",
    "into",
    "that",
    "this",
    "does",
    "the",
    "and",
    "for",
    "are",
    "is",
    "in",
    "of",
    "to",
}


def _keyword_terms(query: str) -> list[str]:
    terms = [
        term
        for term in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", _prepare_tsquery(query))
        if term.lower() not in _STOPWORDS
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(term)
    return deduped[:12] or [query]


# ── Data types ────────────────────────────────────────────

@dataclass
class ChunkInsert:
    """A chunk ready for database insertion."""
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    content_hash: str | None = None
    embedding: list[float] | None = None       # bge-large → 1024 floats
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
    metadata: dict[str, Any] = field(default_factory=dict)


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
    metadata: dict[str, Any] = field(default_factory=dict)


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
            page_count, raw_bytes, _json(metadata),
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
                    embedding = COALESCE(EXCLUDED.embedding, chunks.embedding),
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
                        _json(c.metadata),
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
                _json(c.metadata),
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
        evidence_layer: str | None = None,
        source_type: str | None = None,
        ef_search: int = 100,
    ) -> list[VectorSearchResult]:
        """Cosine similarity search via pgvector HNSW index.

        The ``<=>`` operator returns cosine *distance* (0 = identical, 2 = opposite).
        We compute *similarity* = 1 - distance so higher is better.
        """
        # Use single connection for SET + FETCH to share session state
        async with self._pool.acquire() as conn:
            await conn.execute(f"SET LOCAL hnsw.ef_search = {int(ef_search)}")
            rows = await conn.fetch(
                """SELECT c.id, c.document_id, c.chunk_index, c.content,
                       c.section_title, c.page_start, c.page_end,
                       1.0 - (c.embedding <=> $1) AS similarity,
                       c.metadata
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.embedding IS NOT NULL
                  AND ($3::int IS NULL OR d.protocol_id = $3)
                  AND ($4::text IS NULL OR d.doc_type = $4)
                  AND ($5::text IS NULL OR c.metadata->>'evidence_layer' = $5)
                  AND ($6::text IS NULL OR c.metadata->>'source_type' = $6)
                ORDER BY c.embedding <=> $1
                LIMIT $2""",
                _vec(query_embedding),
                top_k,
                protocol_id,
                doc_type,
                evidence_layer,
                source_type,
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
                metadata=_metadata_dict(r["metadata"]),
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
        evidence_layer: str | None = None,
        source_type: str | None = None,
    ) -> list[KeywordSearchResult]:
        """PostgreSQL full-text search via tsvector/tsquery.

        Uses ``plainto_tsquery('english', $1)`` to parse the user query
        into a tsquery, then ``ts_rank`` for scoring.
        """
        top_k = max(1, min(int(top_k), 100))
        clauses = [
            "c.tsv @@ plainto_tsquery('english', $1)",
            "COALESCE(c.section_title, '') <> 'Table of Contents'",
        ]
        params: list[Any] = [_prepare_tsquery(query)]

        if protocol_id is not None:
            clauses.append(
                "c.document_id IN "
                f"(SELECT id FROM documents WHERE protocol_id = ${len(params) + 1})"
            )
            params.append(protocol_id)

        if doc_type is not None:
            clauses.append(
                f"c.document_id IN (SELECT id FROM documents WHERE doc_type = ${len(params) + 1})"
            )
            params.append(doc_type)

        if evidence_layer is not None:
            clauses.append(f"c.metadata->>'evidence_layer' = ${len(params) + 1}")
            params.append(evidence_layer)

        if source_type is not None:
            clauses.append(f"c.metadata->>'source_type' = ${len(params) + 1}")
            params.append(source_type)

        limit_ref = f"${len(params) + 1}"
        params.append(top_k)
        where = " AND ".join(clauses)

        rows = await self._pool.fetch(
            f"""
            SELECT c.id, c.document_id, c.chunk_index, c.content,
                   c.section_title, c.page_start, c.page_end, c.metadata,
                   ts_rank(c.tsv, plainto_tsquery('english', $1)) AS rank
            FROM chunks c
            WHERE {where}
            ORDER BY rank DESC
            LIMIT {limit_ref}
            """,
            *params,
        )
        # Always supplement with ILIKE (tsquery stemming often misses key terms)
        terms = _keyword_terms(query)
        ilike_params: list[Any] = []
        ilike_clauses = []
        score_parts = []
        for term in terms:
            ilike_params.append(f"%{term}%")
            ref = f"${len(ilike_params)}"
            ilike_clauses.append(
                f"(c.content ILIKE {ref} OR c.section_title ILIKE {ref})"
            )
            score_parts.append(
                f"(CASE WHEN c.section_title ILIKE {ref} THEN 0.5 ELSE 0 END)"
            )
            score_parts.append(
                f"(CASE WHEN c.content ILIKE {ref} THEN 0.1 ELSE 0 END)"
            )
        score_expr = " + ".join(score_parts) or "0.3"
        ilike_filters = [f"({' OR '.join(ilike_clauses)})"]
        ilike_filters.append("COALESCE(c.section_title, '') <> 'Table of Contents'")
        if protocol_id is not None:
            ilike_params.append(protocol_id)
            ilike_filters.append(
                "c.document_id IN "
                f"(SELECT id FROM documents WHERE protocol_id = ${len(ilike_params)})"
            )
        if doc_type is not None:
            ilike_params.append(doc_type)
            ilike_filters.append(
                f"c.document_id IN (SELECT id FROM documents WHERE doc_type = ${len(ilike_params)})"
            )
        if evidence_layer is not None:
            ilike_params.append(evidence_layer)
            ilike_filters.append(
                f"c.metadata->>'evidence_layer' = ${len(ilike_params)}"
            )
        if source_type is not None:
            ilike_params.append(source_type)
            ilike_filters.append(
                f"c.metadata->>'source_type' = ${len(ilike_params)}"
            )
        ilike_params.append(top_k)
        ilike_limit_ref = f"${len(ilike_params)}"
        ilike_where = " AND ".join(ilike_filters)
        ilike_rows = await self._pool.fetch(
            f"""SELECT c.id, c.document_id, c.chunk_index, c.content,
                   c.section_title, c.page_start, c.page_end, c.metadata,
                   ({score_expr})::real AS rank
            FROM chunks c
            WHERE {ilike_where}
            ORDER BY rank DESC, c.page_start
            LIMIT {ilike_limit_ref}""",
            *ilike_params,
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
                metadata=_metadata_dict(r["metadata"]),
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


def _metadata_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}
