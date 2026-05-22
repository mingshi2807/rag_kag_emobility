"""Vector and keyword searchers — thin wrappers around VectorStore."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import asyncpg

from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.storage.vector import VectorStore


@dataclass
class ScoredChunk:
    """Unified result type shared across all retrieval strategies."""
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    section_title: str | None
    page_start: int | None
    page_end: int | None
    score: float
    strategy: str


class VectorSearcher:
    """Cosine similarity search via pgvector HNSW index."""

    def __init__(
        self, pool: asyncpg.Pool, model: EmbeddingModel,
        vector_store: VectorStore | None = None,
    ) -> None:
        self._model = model
        self._store = vector_store or VectorStore(pool)
        self._model.load()

    async def search(
        self, query: str, *, top_k: int = 20,
        protocol_id: int | None = None, doc_type: str | None = None,
        ef_search: int = 100,
    ) -> list[ScoredChunk]:
        qemb = self._model.embed_query(query)
        results = await self._store.vector_search(
            qemb.tolist(), top_k=top_k, protocol_id=protocol_id,
            doc_type=doc_type, ef_search=ef_search,
        )
        return [
            ScoredChunk(r.chunk_id, r.document_id, r.chunk_index,
                        r.content, r.section_title, r.page_start,
                        r.page_end, r.similarity, "vector")
            for r in results
        ]


class KeywordSearcher:
    """Full-text search via PostgreSQL tsvector/tsquery."""

    def __init__(
        self, pool: asyncpg.Pool,
        vector_store: VectorStore | None = None,
    ) -> None:
        self._store = vector_store or VectorStore(pool)

    async def search(
        self, query: str, *, top_k: int = 10,
        protocol_id: int | None = None, doc_type: str | None = None,
    ) -> list[ScoredChunk]:
        results = await self._store.keyword_search(
            query, top_k=top_k, protocol_id=protocol_id, doc_type=doc_type,
        )
        return [
            ScoredChunk(r.chunk_id, r.document_id, r.chunk_index,
                        r.content, r.section_title, r.page_start,
                        r.page_end, r.rank, "keyword")
            for r in results
        ]
