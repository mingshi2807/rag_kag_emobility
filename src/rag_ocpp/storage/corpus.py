"""Storage adapter for source-aware corpus records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import json
from typing import Any
from uuid import UUID

import asyncpg

from rag_ocpp.corpus.models import EvidenceRecord, SourceDocument


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value)


def _date(value: str | date | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(value)


@dataclass
class SourceDocumentInsert:
    """A source artifact ready for insertion."""

    protocol_id: int
    source_type: str
    source_path: str
    title: str
    version: str = "2.1"
    edition: str = "Edition 2"
    document_date: str | None = None
    content_hash: str = ""
    raw_bytes: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_source_document(
        cls, source: SourceDocument, *, protocol_id: int = 1
    ) -> SourceDocumentInsert:
        return cls(
            protocol_id=protocol_id,
            source_type=source.source_type,
            source_path=source.source_path,
            title=source.title,
            version=source.version,
            edition=source.edition,
            document_date=source.document_date,
            content_hash=source.content_hash or "",
            raw_bytes=source.raw_bytes,
            metadata={
                **source.metadata,
                "evidence_layer": source.evidence_layer,
            },
        )


@dataclass
class CorpusRecordInsert:
    """A normalized evidence record ready for insertion."""

    source_document_id: UUID
    record_type: str
    stable_key: str
    title: str
    content: str
    content_hash: str
    page_start: int | None = None
    page_end: int | None = None
    row_number: int | None = None
    section_title: str | None = None
    entity_name: str | None = None
    entity_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_evidence_record(
        cls, source_document_id: UUID, record: EvidenceRecord
    ) -> CorpusRecordInsert:
        return cls(
            source_document_id=source_document_id,
            record_type=record.record_type,
            stable_key=record.stable_key,
            title=record.title,
            content=record.content,
            content_hash=record.content_hash,
            page_start=record.page_start,
            page_end=record.page_end,
            row_number=record.row_number,
            section_title=record.section_title,
            entity_name=record.entity_name,
            entity_type=record.entity_type,
            metadata={
                **record.metadata,
                "source_type": record.source_type,
                "evidence_layer": record.evidence_layer,
            },
        )


class CorpusStore:
    """Async PostgreSQL adapter for source documents and corpus records."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def upsert_source_document(self, source: SourceDocumentInsert) -> UUID:
        """Insert or update a source document and return its UUID."""
        row = await self._pool.fetchrow(
            """
            INSERT INTO source_documents
                (protocol_id, source_type, source_path, title, version, edition,
                 document_date, content_hash, raw_bytes, metadata)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            ON CONFLICT (protocol_id, source_path, content_hash) DO UPDATE SET
                source_type = EXCLUDED.source_type,
                title = EXCLUDED.title,
                version = EXCLUDED.version,
                edition = EXCLUDED.edition,
                document_date = EXCLUDED.document_date,
                raw_bytes = EXCLUDED.raw_bytes,
                metadata = EXCLUDED.metadata
            RETURNING id
            """,
            source.protocol_id,
            source.source_type,
            source.source_path,
            source.title,
            source.version,
            source.edition,
            _date(source.document_date),
            source.content_hash,
            source.raw_bytes,
            _json(source.metadata),
        )
        assert row is not None
        return row["id"]

    async def upsert_corpus_records(self, records: list[CorpusRecordInsert]) -> int:
        """Insert or update normalized corpus records."""
        if not records:
            return 0
        async with self._pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO corpus_records
                    (source_document_id, record_type, stable_key, title, content,
                     content_hash, page_start, page_end, row_number,
                     section_title, entity_name, entity_type, metadata)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                ON CONFLICT (source_document_id, stable_key) DO UPDATE SET
                    record_type = EXCLUDED.record_type,
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    content_hash = EXCLUDED.content_hash,
                    page_start = EXCLUDED.page_start,
                    page_end = EXCLUDED.page_end,
                    row_number = EXCLUDED.row_number,
                    section_title = EXCLUDED.section_title,
                    entity_name = EXCLUDED.entity_name,
                    entity_type = EXCLUDED.entity_type,
                    metadata = EXCLUDED.metadata
                """,
                [
                    (
                        r.source_document_id,
                        r.record_type,
                        r.stable_key,
                        r.title,
                        r.content,
                        r.content_hash,
                        r.page_start,
                        r.page_end,
                        r.row_number,
                        r.section_title,
                        r.entity_name,
                        r.entity_type,
                        _json(r.metadata),
                    )
                    for r in records
                ],
            )
        return len(records)

    async def records_for_source(self, source_document_id: UUID) -> list[dict[str, Any]]:
        """Return all corpus records for a source document."""
        rows = await self._pool.fetch(
            """
            SELECT id, source_document_id, record_type, stable_key, title,
                   content, content_hash, page_start, page_end, row_number,
                   section_title, entity_name, entity_type, metadata
            FROM corpus_records
            WHERE source_document_id = $1
            ORDER BY row_number NULLS LAST, page_start NULLS LAST, stable_key
            """,
            source_document_id,
        )
        return [dict(row) for row in rows]
