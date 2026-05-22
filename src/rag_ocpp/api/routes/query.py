"""POST /query, /query/stream, GET /search — retrieval + generation endpoints."""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from rag_ocpp.api.dependencies import get_hybrid_retriever, get_llm_client
from rag_ocpp.api.schemas import (
    QueryRequest, QueryResponse, ScoredChunkResponse, SearchResponse,
)
from rag_ocpp.generation.client import DeepSeekClient
from rag_ocpp.retrieval.hybrid import HybridRetriever, SearchFilters

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    retriever: HybridRetriever = Depends(get_hybrid_retriever),
    llm: DeepSeekClient = Depends(get_llm_client),
):
    t0 = time.monotonic()
    filters = SearchFilters(doc_type=req.doc_type)
    retrieval = await retriever.retrieve(req.query, filters=filters)

    context = [
        {"content": c.content, "section_title": c.section_title or "Section",
         "document_title": str(c.document_id)[:36], "page_start": c.page_start}
        for c in retrieval.chunks
    ]

    try:
        answer = await llm.generate(req.query, context)
    except Exception as exc:
        logger.error("Generation failed: %s", exc)
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
):
    filters = SearchFilters(doc_type=req.doc_type)
    retrieval = await retriever.retrieve(req.query, filters=filters)

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
            async for token in llm.generate_stream(req.query, context):
                yield {"event": "token", "data": token}
        except Exception as exc:
            yield {"event": "error", "data": str(exc)}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(events())


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str, top_k: int = 20, doc_type: str | None = None,
    retriever: HybridRetriever = Depends(get_hybrid_retriever),
):
    t0 = time.monotonic()
    result = await retriever.search_only(q, filters=SearchFilters(doc_type=doc_type), top_k=top_k)
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
