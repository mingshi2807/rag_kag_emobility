"""Source-aware corpus admin API."""

from __future__ import annotations

from pathlib import Path

import asyncpg
from fastapi import APIRouter, Depends

from rag_ocpp.api.dependencies import (
    get_audit_store,
    get_corpus_store,
    get_embedding_model,
    get_pool,
)
from rag_ocpp.api.schemas import (
    CorpusBuildRequest,
    CorpusIndexRequest,
    CorpusIndexResponse,
    CorpusPreviewResponse,
    CorpusSourceSummary,
    CorpusStatusResponse,
    CorpusStoreResponse,
)
from rag_ocpp.api.security import require_admin
from rag_ocpp.cli.corpus import _parse_source, _planned_sources, _source_document_for
from rag_ocpp.corpus.indexer import CorpusIndexer
from rag_ocpp.corpus.ocpp21 import (
    OCPP21_ED2_DM_DIR,
    OCPP21_ED2_JSON_SCHEMA_DIR,
    OCPP21_ED2_PART2_SPEC_PDF,
)
from rag_ocpp.corpus.status import load_corpus_status
from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.storage.audit import AuditEvent, AuditStore
from rag_ocpp.storage.corpus import (
    CorpusRecordInsert,
    CorpusStore,
    SourceDocumentInsert,
)

router = APIRouter()


@router.get("/status", response_model=CorpusStatusResponse)
async def corpus_status(pool: asyncpg.Pool = Depends(get_pool)):
    """Return source-aware corpus storage/index health."""
    counts = await load_corpus_status(pool)
    return CorpusStatusResponse(
        source_documents=counts.source_documents,
        corpus_records=counts.corpus_records,
        corpus_documents=counts.corpus_documents,
        corpus_chunks=counts.corpus_chunks,
        embedded_corpus_chunks=counts.embedded_corpus_chunks,
        by_source_type=counts.by_source_type,
        by_evidence_layer=counts.by_evidence_layer,
    )


@router.post("/preview", response_model=CorpusPreviewResponse)
async def corpus_preview(
    req: CorpusBuildRequest,
    _: None = Depends(require_admin),
):
    """Parse selected OCPP 2.1 Ed2 sources and return record counts only."""
    return _preview(req)


@router.post("/store", response_model=CorpusStoreResponse)
async def corpus_store(
    req: CorpusBuildRequest,
    _: None = Depends(require_admin),
    store: CorpusStore = Depends(get_corpus_store),
    audit: AuditStore = Depends(get_audit_store),
):
    """Parse and store selected OCPP 2.1 Ed2 source-aware corpus records."""
    summaries, total_records = _build_summaries(req)
    stored_sources = 0
    stored_records = 0
    for summary in summaries:
        source_path = Path(summary.source_path)
        source = _source_document_for(source_path, summary.parser)
        records = _parse_source(source_path, summary.parser)
        source_id = await store.upsert_source_document(
            SourceDocumentInsert.from_source_document(source)
        )
        inserts = [
            CorpusRecordInsert.from_evidence_record(source_id, record)
            for record in records
        ]
        stored_records += await store.upsert_corpus_records(inserts)
        stored_sources += 1
        await _audit(
            audit,
            AuditEvent(
                event_type="corpus.ingested",
                surface="api",
                action="corpus_store",
                resource_type="source_document",
                resource_id=source_id,
                metadata={
                    "source_type": source.source_type,
                    "source_path": source.source_path,
                    "content_hash": source.content_hash,
                    "records": len(records),
                    "raw_bytes": source.raw_bytes,
                },
            ),
        )

    return CorpusStoreResponse(
        planned_sources=len(summaries),
        total_records=total_records,
        sources=summaries,
        stored_sources=stored_sources,
        stored_records=stored_records,
    )


@router.post("/index", response_model=CorpusIndexResponse)
async def corpus_index(
    req: CorpusIndexRequest,
    _: None = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
    embedding: EmbeddingModel = Depends(get_embedding_model),
    audit: AuditStore = Depends(get_audit_store),
):
    """Index stored corpus records into chunks, embeddings, and graph links."""
    indexer = CorpusIndexer(pool, None if req.no_embed else embedding)
    result = await indexer.index_all(
        embed=not req.no_embed,
        batch_size=req.batch_size,
        limit=req.limit,
    )
    await _audit(
        audit,
        AuditEvent(
            event_type="corpus.indexed",
            surface="api",
            action="corpus_index",
            metadata={
                "embed": not req.no_embed,
                "batch_size": req.batch_size,
                "limit": req.limit,
                "sources_indexed": result.sources_indexed,
                "records_indexed": result.records_indexed,
                "chunks_upserted": result.chunks_upserted,
                "chunks_embedded": result.chunks_embedded,
                "entities_linked": result.entities_linked,
                "relationships_created": result.relationships_created,
            },
        ),
    )
    return CorpusIndexResponse(**result.__dict__)


def _preview(req: CorpusBuildRequest) -> CorpusPreviewResponse:
    summaries, total_records = _build_summaries(req)
    return CorpusPreviewResponse(
        planned_sources=len(summaries),
        total_records=total_records,
        sources=summaries,
    )


def _build_summaries(req: CorpusBuildRequest) -> tuple[list[CorpusSourceSummary], int]:
    planned = _planned_sources(
        spec_pdf=Path(req.spec_pdf) if req.spec_pdf else OCPP21_ED2_PART2_SPEC_PDF,
        dm_dir=Path(req.dm_dir) if req.dm_dir else OCPP21_ED2_DM_DIR,
        schema_dir=Path(req.schema_dir) if req.schema_dir else OCPP21_ED2_JSON_SCHEMA_DIR,
        include_pdf=req.include_pdf,
        include_dm=req.include_dm,
        include_schemas=req.include_schemas,
    )
    summaries: list[CorpusSourceSummary] = []
    total_records = 0
    for source_path, parser in planned:
        records = _parse_source(source_path, parser)
        source = _source_document_for(source_path, parser)
        total_records += len(records)
        summaries.append(
            CorpusSourceSummary(
                source_path=str(source_path),
                parser=parser,
                source_type=source.source_type,
                evidence_layer=source.evidence_layer,
                title=source.title,
                content_hash=source.content_hash,
                raw_bytes=source.raw_bytes,
                records=len(records),
            )
        )
    return summaries, total_records


async def _audit(audit: AuditStore, event: AuditEvent) -> None:
    try:
        await audit.record(event)
    except Exception:
        pass
