"""POST /query, /query/stream, GET /search — retrieval + generation endpoints."""

from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from rag_ocpp.api.dependencies import (
    get_audit_store,
    get_hybrid_retriever,
    get_llm_client,
)
from rag_ocpp.api.schemas import (
    QueryRequest,
    QueryResponse,
    ScoredChunkResponse,
    SearchResponse,
)
from rag_ocpp.generation.client import DeepSeekClient
from rag_ocpp.privacy import redact_value
from rag_ocpp.retrieval.hybrid import HybridRetriever, SearchFilters
from rag_ocpp.storage.audit import AuditEvent, AuditStore, sensitive_text_ref

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    retriever: HybridRetriever = Depends(get_hybrid_retriever),
    llm: DeepSeekClient = Depends(get_llm_client),
    audit: AuditStore = Depends(get_audit_store),
):
    t0 = time.monotonic()
    correlation_id = str(uuid.uuid4())
    await _audit(
        audit,
        AuditEvent(
            event_type="query.requested",
            surface="api",
            action="query",
            correlation_id=correlation_id,
            metadata={"query": sensitive_text_ref(req.query), "doc_type": req.doc_type},
        ),
    )
    filters = SearchFilters(doc_type=req.doc_type)
    retrieval = await retriever.retrieve(req.query, filters=filters)
    await _audit(
        audit,
        AuditEvent(
            event_type="retrieval.completed",
            surface="api",
            action="retrieve",
            correlation_id=correlation_id,
            latency_ms=retrieval.latency_ms,
            metadata={
                "query": sensitive_text_ref(req.query),
                "chunks": len(retrieval.chunks),
                "strategy_breakdown": retrieval.strategy_breakdown,
                "chunk_ids": [str(c.chunk_id) for c in retrieval.chunks],
            },
        ),
    )

    context = [
        {"content": c.content, "section_title": c.section_title or "Section",
         "document_title": str(c.document_id)[:36], "page_start": c.page_start}
        for c in retrieval.chunks
    ]

    try:
        answer = await llm.generate(req.query, context)
        await _audit(
            audit,
            AuditEvent(
                event_type="generation.completed",
                surface="api",
                action="generate",
                correlation_id=correlation_id,
                metadata={
                    "query": sensitive_text_ref(req.query),
                    "model": llm.model,
                    "context_chunks": len(context),
                    "answer_length": len(answer),
                },
            ),
        )
    except Exception as exc:
        logger.error("Generation failed: %s", redact_value(exc))
        await _audit(
            audit,
            AuditEvent(
                event_type="generation.failed",
                surface="api",
                action="generate",
                status="failure",
                correlation_id=correlation_id,
                metadata={
                    "query": sensitive_text_ref(req.query),
                    "model": llm.model,
                    "error": redact_value(exc, force=True),
                },
            ),
        )
        answer = f"Error: {exc}"

    return QueryResponse(
        query=req.query, answer=answer,
        sources=[ScoredChunkResponse(
            chunk_id=c.chunk_id, document_id=c.document_id,
            content=c.content[:500], score=c.score, strategy=c.strategy,
            section_title=c.section_title, page_start=c.page_start,
            page_end=c.page_end,
        ) for c in retrieval.chunks],
        strategy_breakdown=retrieval.strategy_breakdown,
        latency_ms=int((time.monotonic() - t0) * 1000),
    )


@router.post("/query/stream")
async def query_stream(
    req: QueryRequest,
    retriever: HybridRetriever = Depends(get_hybrid_retriever),
    llm: DeepSeekClient = Depends(get_llm_client),
    audit: AuditStore = Depends(get_audit_store),
):
    correlation_id = str(uuid.uuid4())
    await _audit(
        audit,
        AuditEvent(
            event_type="query.requested",
            surface="api",
            action="query_stream",
            correlation_id=correlation_id,
            metadata={"query": sensitive_text_ref(req.query), "doc_type": req.doc_type},
        ),
    )
    filters = SearchFilters(doc_type=req.doc_type)
    retrieval = await retriever.retrieve(req.query, filters=filters)
    await _audit(
        audit,
        AuditEvent(
            event_type="retrieval.completed",
            surface="api",
            action="retrieve",
            correlation_id=correlation_id,
            latency_ms=retrieval.latency_ms,
            metadata={
                "query": sensitive_text_ref(req.query),
                "chunks": len(retrieval.chunks),
                "strategy_breakdown": retrieval.strategy_breakdown,
            },
        ),
    )

    context = [
        {"content": c.content, "section_title": c.section_title or "Section",
         "document_title": str(c.document_id)[:36], "page_start": c.page_start}
        for c in retrieval.chunks
    ]

    async def events():
        yield {"event": "sources", "data": json.dumps([
            {"chunk_id": str(c.chunk_id), "section_title": c.section_title,
             "page_start": c.page_start, "score": c.score, "strategy": c.strategy}
            for c in retrieval.chunks
        ])}
        try:
            token_count = 0
            async for token in llm.generate_stream(req.query, context):
                token_count += 1
                yield {"event": "token", "data": token}
            await _audit(
                audit,
                AuditEvent(
                    event_type="generation.completed",
                    surface="api",
                    action="generate_stream",
                    correlation_id=correlation_id,
                    metadata={
                        "query": sensitive_text_ref(req.query),
                        "model": llm.model,
                        "context_chunks": len(context),
                        "stream_tokens": token_count,
                    },
                ),
            )
        except Exception as exc:
            await _audit(
                audit,
                AuditEvent(
                    event_type="generation.failed",
                    surface="api",
                    action="generate_stream",
                    status="failure",
                    correlation_id=correlation_id,
                    metadata={
                        "query": sensitive_text_ref(req.query),
                        "model": llm.model,
                        "error": redact_value(exc, force=True),
                    },
                ),
            )
            yield {"event": "error", "data": str(exc)}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(events())


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str, top_k: int = 20, doc_type: str | None = None,
    retriever: HybridRetriever = Depends(get_hybrid_retriever),
    audit: AuditStore = Depends(get_audit_store),
):
    correlation_id = str(uuid.uuid4())
    await _audit(
        audit,
        AuditEvent(
            event_type="query.requested",
            surface="api",
            action="search",
            correlation_id=correlation_id,
            metadata={"query": sensitive_text_ref(q), "doc_type": doc_type, "top_k": top_k},
        ),
    )
    result = await retriever.search_only(q, filters=SearchFilters(doc_type=doc_type), top_k=top_k)
    await _audit(
        audit,
        AuditEvent(
            event_type="retrieval.completed",
            surface="api",
            action="search_only",
            correlation_id=correlation_id,
            latency_ms=result.latency_ms,
            metadata={
                "query": sensitive_text_ref(q),
                "chunks": len(result.chunks),
                "strategy_breakdown": result.strategy_breakdown,
                "chunk_ids": [str(c.chunk_id) for c in result.chunks],
            },
        ),
    )
    return SearchResponse(
        query=q,
        results=[ScoredChunkResponse(
            chunk_id=c.chunk_id, document_id=c.document_id,
            content=c.content[:300], score=c.score, strategy=c.strategy,
            section_title=c.section_title, page_start=c.page_start,
            page_end=c.page_end,
        ) for c in result.chunks],
        strategy_breakdown=result.strategy_breakdown,
        latency_ms=result.latency_ms,
    )


async def _audit(audit: AuditStore, event: AuditEvent) -> None:
    try:
        await audit.record(event)
    except Exception as exc:
        logger.warning("Audit event write failed: %s", redact_value(exc))
