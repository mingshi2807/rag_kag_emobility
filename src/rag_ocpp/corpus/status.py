"""Shared source-aware corpus status queries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import asyncpg


@dataclass(frozen=True)
class CorpusStatus:
    """Corpus and index health summary shared by API and MCP surfaces."""

    source_documents: int = 0
    corpus_records: int = 0
    corpus_documents: int = 0
    corpus_chunks: int = 0
    embedded_corpus_chunks: int = 0
    total_chunks: int = 0
    total_embeddings: int = 0
    entity_links: int = 0
    relationships: int = 0
    by_source_type: dict[str, int] = field(default_factory=dict)
    by_evidence_layer: dict[str, int] = field(default_factory=dict)
    source_documents_by_evidence_layer: list[dict[str, Any]] = field(
        default_factory=list
    )
    chunks_by_evidence_layer: list[dict[str, Any]] = field(default_factory=list)
    embedding_dimensions: list[dict[str, Any]] = field(default_factory=list)


async def load_corpus_status(pool: asyncpg.Pool) -> CorpusStatus:
    """Return source-aware corpus/index counts without exposing raw source text."""
    source_rows = await pool.fetch(
        """
        SELECT metadata->>'evidence_layer' AS evidence_layer, source_type, count(*) AS count
        FROM source_documents
        GROUP BY 1,2
        ORDER BY 1,2
        """
    )
    chunk_rows = await pool.fetch(
        """
        SELECT metadata->>'evidence_layer' AS evidence_layer,
               metadata->>'source_type' AS source_type,
               count(*) AS chunks,
               count(embedding) AS embeddings
        FROM chunks
        GROUP BY 1,2
        ORDER BY 1,2
        """
    )
    dim_rows = await pool.fetch(
        """
        SELECT vector_dims(embedding) AS dims, count(*) AS count
        FROM chunks
        WHERE embedding IS NOT NULL
        GROUP BY 1
        ORDER BY 1
        """
    )
    totals = await pool.fetchrow(
        """
        SELECT
          (SELECT count(*) FROM source_documents) AS source_documents,
          (SELECT count(*) FROM corpus_records) AS corpus_records,
          (SELECT count(*) FROM documents WHERE source_path LIKE 'corpus:%') AS corpus_documents,
          (SELECT count(*) FROM chunks WHERE metadata ? 'corpus_record_id') AS corpus_chunks,
          (SELECT count(*) FROM chunks
           WHERE metadata ? 'corpus_record_id'
             AND embedding IS NOT NULL) AS embedded_corpus_chunks,
          (SELECT count(*) FROM chunks) AS total_chunks,
          (SELECT count(embedding) FROM chunks) AS total_embeddings,
          (SELECT count(*) FROM chunk_entities) AS entity_links,
          (SELECT count(*) FROM relationships) AS relationships
        """
    )
    total_values = dict(totals or {})
    source_documents_by_evidence_layer = [dict(row) for row in source_rows]
    chunks_by_evidence_layer = [dict(row) for row in chunk_rows]
    by_source_type: dict[str, int] = {}
    by_evidence_layer: dict[str, int] = {}
    for row in source_documents_by_evidence_layer:
        source_type = row.get("source_type") or "unknown"
        evidence_layer = row.get("evidence_layer") or "unknown"
        count = int(row.get("count") or 0)
        by_source_type[source_type] = by_source_type.get(source_type, 0) + count
        by_evidence_layer[evidence_layer] = by_evidence_layer.get(evidence_layer, 0) + count

    return CorpusStatus(
        source_documents=int(total_values.get("source_documents") or 0),
        corpus_records=int(total_values.get("corpus_records") or 0),
        corpus_documents=int(total_values.get("corpus_documents") or 0),
        corpus_chunks=int(total_values.get("corpus_chunks") or 0),
        embedded_corpus_chunks=int(total_values.get("embedded_corpus_chunks") or 0),
        total_chunks=int(total_values.get("total_chunks") or 0),
        total_embeddings=int(total_values.get("total_embeddings") or 0),
        entity_links=int(total_values.get("entity_links") or 0),
        relationships=int(total_values.get("relationships") or 0),
        by_source_type=by_source_type,
        by_evidence_layer=by_evidence_layer,
        source_documents_by_evidence_layer=source_documents_by_evidence_layer,
        chunks_by_evidence_layer=chunks_by_evidence_layer,
        embedding_dimensions=[dict(row) for row in dim_rows],
    )
