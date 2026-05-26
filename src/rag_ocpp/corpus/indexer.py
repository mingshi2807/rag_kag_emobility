"""Index stored source-aware corpus records into chunks and graph entities."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg

from rag_ocpp.embedding.batch import BatchEmbedder
from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.knowledge.entities import OCPPEntityType
from rag_ocpp.storage.corpus import CorpusStore
from rag_ocpp.storage.graph import GraphStore
from rag_ocpp.storage.vector import ChunkInsert, VectorStore


ENTITY_TYPE_IDS = {member.label: member.type_id for member in OCPPEntityType}


@dataclass
class CorpusIndexResult:
    """Summary of corpus indexing work."""

    sources_indexed: int = 0
    records_indexed: int = 0
    chunks_upserted: int = 0
    chunks_embedded: int = 0
    entities_linked: int = 0
    relationships_created: int = 0


class CorpusIndexer:
    """Build vector chunks and graph links from normalized corpus records."""

    def __init__(
        self, pool: asyncpg.Pool, embedding_model: EmbeddingModel | None = None
    ) -> None:
        self._pool = pool
        self._corpus = CorpusStore(pool)
        self._vector = VectorStore(pool)
        self._graph = GraphStore(pool)
        self._embedding_model = embedding_model
        self._embedder: BatchEmbedder | None = None

    async def index_all(
        self,
        *,
        protocol_id: int = 1,
        embed: bool = True,
        batch_size: int = 128,
        limit: int | None = None,
    ) -> CorpusIndexResult:
        """Index stored corpus records into chunks and graph links."""
        result = CorpusIndexResult()
        sources = await self._corpus.list_source_documents()
        remaining = limit

        for source in sources:
            if remaining is not None and remaining <= 0:
                break
            records = await self._corpus.list_corpus_records(
                source_document_id=source["id"], limit=remaining
            )
            if not records:
                continue
            if remaining is not None:
                remaining -= len(records)
            source_result = await self.index_source(
                source, records, protocol_id=protocol_id, embed=embed, batch_size=batch_size
            )
            result.sources_indexed += source_result.sources_indexed
            result.records_indexed += source_result.records_indexed
            result.chunks_upserted += source_result.chunks_upserted
            result.chunks_embedded += source_result.chunks_embedded
            result.entities_linked += source_result.entities_linked
            result.relationships_created += source_result.relationships_created

        return result

    async def index_source(
        self,
        source: dict[str, Any],
        records: list[dict[str, Any]],
        *,
        protocol_id: int = 1,
        embed: bool = True,
        batch_size: int = 128,
    ) -> CorpusIndexResult:
        """Index records for one source document."""
        doc_id = await self._document_for_source(source, protocol_id=protocol_id)
        chunks = [
            self._chunk_for_record(doc_id, index, record, source)
            for index, record in enumerate(records)
        ]
        await self._vector.insert_chunks(chunks)
        chunks_upserted = len(chunks)

        embedded = 0
        if embed:
            embedder = self._get_embedder()
            for start in range(0, len(chunks), batch_size):
                batch = chunks[start:start + batch_size]
                embedded += await embedder.embed_batch(
                    [chunk.id for chunk in batch],
                    [chunk.content for chunk in batch],
                )

        entities, relationships = await self._link_graph(chunks, records, source)
        return CorpusIndexResult(
            sources_indexed=1,
            records_indexed=len(records),
            chunks_upserted=chunks_upserted,
            chunks_embedded=embedded,
            entities_linked=entities,
            relationships_created=relationships,
        )

    async def _document_for_source(
        self, source: dict[str, Any], *, protocol_id: int
    ) -> UUID:
        source_path = f"corpus:{source['id']}"
        row = await self._pool.fetchrow(
            "SELECT id FROM documents WHERE protocol_id = $1 AND source_path = $2 LIMIT 1",
            protocol_id,
            source_path,
        )
        if row is not None:
            return row["id"]
        return await self._vector.insert_document(
            protocol_id=protocol_id,
            source_path=source_path,
            doc_type="json_config" if source["source_type"] == "json_schema" else "other",
            title=source.get("title") or source.get("source_path"),
            version=source.get("version"),
            part="Part 2",
            raw_bytes=source.get("raw_bytes"),
            metadata={
                "source_document_id": str(source["id"]),
                "source_type": source["source_type"],
                "source_path": source["source_path"],
                "content_hash": source["content_hash"],
                "evidence_layer": _metadata(source).get("evidence_layer"),
            },
        )

    def _chunk_for_record(
        self,
        document_id: UUID,
        chunk_index: int,
        record: dict[str, Any],
        source: dict[str, Any],
    ) -> ChunkInsert:
        metadata = _metadata(record)
        metadata.update(
            {
                "corpus_record_id": str(record["id"]),
                "source_document_id": str(record["source_document_id"]),
                "stable_key": record["stable_key"],
                "record_type": record["record_type"],
                "source_type": source["source_type"],
                "source_path": source["source_path"],
                "entity_type": record.get("entity_type"),
                "entity_name": record.get("entity_name"),
            }
        )
        return ChunkInsert(
            id=uuid.uuid5(uuid.NAMESPACE_URL, f"chunk:{record['id']}"),
            document_id=document_id,
            chunk_index=chunk_index,
            content=record["content"],
            content_hash=record["content_hash"],
            strategy="corpus_record",
            section_title=record.get("section_title") or record.get("title"),
            page_start=record.get("page_start"),
            page_end=record.get("page_end"),
            token_count=None,
            metadata=metadata,
        )

    async def _link_graph(
        self,
        chunks: list[ChunkInsert],
        records: list[dict[str, Any]],
        source: dict[str, Any],
    ) -> tuple[int, int]:
        entities_linked = 0
        relationships_created = 0
        source_entity_id = await self._source_entity(source)

        for chunk, record in zip(chunks, records, strict=True):
            entity_id = await self._record_entity(record)
            if entity_id is None:
                continue
            await self._graph.link_chunk_entity(
                chunk_id=chunk.id,
                entity_id=entity_id,
                confidence=1.0,
            )
            entities_linked += 1
            rel_type = self._source_relationship_type(record)
            await self._graph.upsert_relationship(
                source_id=source_entity_id,
                target_id=entity_id,
                rel_type=rel_type,
                properties={
                    "corpus_record_id": str(record["id"]),
                    "stable_key": record["stable_key"],
                    "record_type": record["record_type"],
                },
            )
            relationships_created += 1
            relationships_created += await self._record_relationships(record, entity_id)

        return entities_linked, relationships_created

    async def _source_entity(self, source: dict[str, Any]) -> UUID:
        return await self._graph.upsert_entity(
            protocol_id=source["protocol_id"],
            type_id=ENTITY_TYPE_IDS["schema"],
            name=f"source:{source['source_path']}",
            description=source.get("title"),
            properties={
                "source_document_id": str(source["id"]),
                "source_type": source["source_type"],
                "content_hash": source["content_hash"],
            },
        )

    async def _record_entity(self, record: dict[str, Any]) -> UUID | None:
        entity_type = record.get("entity_type")
        entity_name = record.get("entity_name")
        type_id = ENTITY_TYPE_IDS.get(entity_type or "")
        if type_id is None or not entity_name:
            return None
        return await self._graph.upsert_entity(
            protocol_id=1,
            type_id=type_id,
            name=entity_name,
            description=record.get("title"),
            properties={
                "corpus_record_id": str(record["id"]),
                "stable_key": record["stable_key"],
                "record_type": record["record_type"],
            },
        )

    async def _record_relationships(self, record: dict[str, Any], entity_id: UUID) -> int:
        metadata = _metadata(record)
        rels = 0
        if record["record_type"] == "schema_field":
            message = metadata.get("message")
            path = metadata.get("path")
            if message and path and "." not in path:
                message_id = await self._graph.upsert_entity(
                    protocol_id=1,
                    type_id=ENTITY_TYPE_IDS["message"],
                    name=message,
                    properties={"source": "json_schema"},
                )
                await self._graph.upsert_relationship(
                    source_id=message_id,
                    target_id=entity_id,
                    rel_type="message_has_field",
                    properties={
                        "required": metadata.get("required", False),
                        "path": path,
                    },
                )
                rels += 1
        elif record["record_type"] == "dm_component_variable":
            component = metadata.get("specific_component") or metadata.get("component")
            variable = metadata.get("variable")
            if component and variable:
                component_id = await self._graph.upsert_entity(
                    protocol_id=1,
                    type_id=ENTITY_TYPE_IDS["component"],
                    name=component,
                    properties={"source": "device_model"},
                )
                await self._graph.upsert_relationship(
                    source_id=component_id,
                    target_id=entity_id,
                    rel_type="component_has_variable",
                    properties={
                        "required": metadata.get("required"),
                        "datatype": metadata.get("datatype"),
                        "unit": metadata.get("unit"),
                    },
                )
                rels += 1
        return rels

    def _source_relationship_type(self, record: dict[str, Any]) -> str:
        if record["record_type"].startswith("schema"):
            return "schema_defines_entity"
        if record["record_type"].startswith("dm"):
            return "dm_defines_entity"
        return "spec_defines_entity"

    def _get_embedder(self) -> BatchEmbedder:
        if self._embedding_model is None:
            raise ValueError("Embedding model is required when embed=True")
        if self._embedder is None:
            self._embedder = BatchEmbedder(
                self._pool, self._embedding_model, self._vector
            )
        return self._embedder


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("metadata") or {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}
