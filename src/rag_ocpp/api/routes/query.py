"""Retrieval and generation API endpoints."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from rag_ocpp.api.dependencies import (
    get_audit_store,
    get_graph_store,
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
from rag_ocpp.retrieval.searchers import ScoredChunk
from rag_ocpp.storage.audit import AuditEvent, AuditStore, sensitive_text_ref
from rag_ocpp.storage.graph import ChunkSemanticLink, GraphStore

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    retriever: HybridRetriever = Depends(get_hybrid_retriever),
    llm: DeepSeekClient = Depends(get_llm_client),
    audit: AuditStore = Depends(get_audit_store),
    graph: GraphStore = Depends(get_graph_store),
):
    t0 = time.monotonic()
    correlation_id = str(uuid.uuid4())
    filters = _filters(req.doc_type, req.evidence_layer, req.source_type)

    await _audit(
        audit,
        AuditEvent(
            event_type="query.requested",
            surface="api",
            action="query",
            correlation_id=correlation_id,
            metadata=_request_metadata(req),
        ),
    )

    retrieval = await retriever.retrieve(req.query, filters=filters, top_k=req.top_k)
    await _audit_retrieval(audit, correlation_id, req.query, retrieval)
    semantic_links = await _semantic_links(graph, retrieval.chunks)

    context = [
        _context_chunk(chunk, semantic_links.get(chunk.chunk_id, []))
        for chunk in retrieval.chunks
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
        await _audit_generation_failure(audit, correlation_id, req.query, llm.model, exc)
        raise HTTPException(
            status_code=502,
            detail={
                "error": "generation_failed",
                "message": "Answer generation failed.",
                "correlation_id": correlation_id,
            },
        ) from exc

    return QueryResponse(
        correlation_id=correlation_id,
        query=req.query if req.include_query else None,
        query_ref=sensitive_text_ref(req.query),
        answer=answer if req.include_answer else None,
        sources=[
            _chunk_response(
                chunk,
                include_content=req.include_content,
                max_chars=req.max_chars,
                semantic_links=semantic_links.get(chunk.chunk_id, []),
            )
            for chunk in retrieval.chunks
        ],
        strategy_breakdown=retrieval.strategy_breakdown,
        latency_ms=int((time.monotonic() - t0) * 1000),
    )


@router.post("/query/stream")
async def query_stream(
    req: QueryRequest,
    retriever: HybridRetriever = Depends(get_hybrid_retriever),
    llm: DeepSeekClient = Depends(get_llm_client),
    audit: AuditStore = Depends(get_audit_store),
    graph: GraphStore = Depends(get_graph_store),
):
    correlation_id = str(uuid.uuid4())
    filters = _filters(req.doc_type, req.evidence_layer, req.source_type)

    await _audit(
        audit,
        AuditEvent(
            event_type="query.requested",
            surface="api",
            action="query_stream",
            correlation_id=correlation_id,
            metadata=_request_metadata(req),
        ),
    )

    retrieval = await retriever.retrieve(req.query, filters=filters, top_k=req.top_k)
    await _audit_retrieval(audit, correlation_id, req.query, retrieval)
    semantic_links = await _semantic_links(graph, retrieval.chunks)
    context = [
        _context_chunk(chunk, semantic_links.get(chunk.chunk_id, []))
        for chunk in retrieval.chunks
    ]

    async def events():
        yield {
            "event": "sources",
            "data": json.dumps(
                [
                    _chunk_response(
                        chunk,
                        include_content=req.include_content,
                        max_chars=req.max_chars,
                        semantic_links=semantic_links.get(chunk.chunk_id, []),
                    ).model_dump(mode="json")
                    for chunk in retrieval.chunks
                ]
            ),
        }
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
            await _audit_generation_failure(
                audit,
                correlation_id,
                req.query,
                llm.model,
                exc,
                action="generate_stream",
            )
            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "error": "generation_failed",
                        "message": "Answer generation failed.",
                        "correlation_id": correlation_id,
                    }
                ),
            }
        yield {"event": "done", "data": ""}

    return EventSourceResponse(events())


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, max_length=2000),
    top_k: int = Query(8, ge=1, le=20),
    doc_type: str | None = None,
    evidence_layer: str | None = Query(None, pattern="^(spec|device_model|schema)$"),
    source_type: str | None = Query(
        None,
        pattern="^(spec_pdf|device_model_table|json_schema|appendix_csv)$",
    ),
    max_chars: int = Query(300, ge=0, le=6000),
    include_content: bool = True,
    include_query: bool = True,
    retriever: HybridRetriever = Depends(get_hybrid_retriever),
    audit: AuditStore = Depends(get_audit_store),
    graph: GraphStore = Depends(get_graph_store),
):
    correlation_id = str(uuid.uuid4())
    await _audit(
        audit,
        AuditEvent(
            event_type="query.requested",
            surface="api",
            action="search",
            correlation_id=correlation_id,
            metadata={
                "query": sensitive_text_ref(q),
                "doc_type": doc_type,
                "evidence_layer": evidence_layer,
                "source_type": source_type,
                "top_k": top_k,
            },
        ),
    )

    result = await retriever.search_only(
        q,
        filters=_filters(doc_type, evidence_layer, source_type),
        top_k=top_k,
    )
    await _audit_retrieval(audit, correlation_id, q, result, action="search_only")
    semantic_links = await _semantic_links(graph, result.chunks)

    return SearchResponse(
        correlation_id=correlation_id,
        query=q if include_query else None,
        query_ref=sensitive_text_ref(q),
        results=[
            _chunk_response(
                chunk,
                include_content=include_content,
                max_chars=max_chars,
                semantic_links=semantic_links.get(chunk.chunk_id, []),
            )
            for chunk in result.chunks
        ],
        strategy_breakdown=result.strategy_breakdown,
        latency_ms=result.latency_ms,
    )


async def _audit(audit: AuditStore, event: AuditEvent) -> None:
    try:
        await audit.record(event)
    except Exception as exc:
        logger.warning("Audit event write failed: %s", redact_value(exc))


async def _audit_retrieval(
    audit: AuditStore,
    correlation_id: str,
    query_text: str,
    retrieval,
    *,
    action: str = "retrieve",
) -> None:
    await _audit(
        audit,
        AuditEvent(
            event_type="retrieval.completed",
            surface="api",
            action=action,
            correlation_id=correlation_id,
            latency_ms=retrieval.latency_ms,
            metadata={
                "query": sensitive_text_ref(query_text),
                "chunks": len(retrieval.chunks),
                "strategy_breakdown": retrieval.strategy_breakdown,
                "chunk_ids": [str(chunk.chunk_id) for chunk in retrieval.chunks],
            },
        ),
    )


async def _audit_generation_failure(
    audit: AuditStore,
    correlation_id: str,
    query_text: str,
    model: str,
    exc: Exception,
    *,
    action: str = "generate",
) -> None:
    await _audit(
        audit,
        AuditEvent(
            event_type="generation.failed",
            surface="api",
            action=action,
            status="failure",
            correlation_id=correlation_id,
            metadata={
                "query": sensitive_text_ref(query_text),
                "model": model,
                "error": redact_value(exc, force=True),
            },
        ),
    )


def _filters(
    doc_type: str | None,
    evidence_layer: str | None,
    source_type: str | None,
) -> SearchFilters:
    return SearchFilters(
        doc_type=doc_type,
        evidence_layer=evidence_layer,
        source_type=source_type,
    )


def _request_metadata(req: QueryRequest) -> dict[str, Any]:
    return {
        "query": sensitive_text_ref(req.query),
        "doc_type": req.doc_type,
        "evidence_layer": req.evidence_layer,
        "source_type": req.source_type,
        "top_k": req.top_k,
        "stream": req.stream,
        "include_content": req.include_content,
        "include_answer": req.include_answer,
    }


async def _semantic_links(
    graph: GraphStore,
    chunks: list[ScoredChunk],
) -> dict[Any, list[ChunkSemanticLink]]:
    try:
        return await graph.get_semantic_links_for_chunks(
            [chunk.chunk_id for chunk in chunks],
            max_links_per_chunk=5,
        )
    except Exception as exc:
        logger.warning("Semantic link lookup failed: %s", redact_value(exc))
        return {}


def _context_chunk(
    chunk: ScoredChunk,
    semantic_links: list[ChunkSemanticLink] | None = None,
) -> dict[str, Any]:
    metadata = chunk.metadata or {}
    return {
        "content": chunk.content,
        "section_title": chunk.section_title or "Section",
        "document_title": metadata.get("source_path") or str(chunk.document_id)[:36],
        "page_start": chunk.page_start,
        "evidence_layer": metadata.get("evidence_layer"),
        "source_type": metadata.get("source_type"),
        "semantic_links": [_semantic_link_context(link) for link in semantic_links or []],
    }


def _chunk_response(
    chunk: ScoredChunk,
    *,
    include_content: bool,
    max_chars: int,
    semantic_links: list[ChunkSemanticLink] | None = None,
) -> ScoredChunkResponse:
    metadata = chunk.metadata or {}
    content = chunk.content[:max_chars] if include_content and max_chars > 0 else None
    return ScoredChunkResponse(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        content=content,
        score=chunk.score,
        strategy=chunk.strategy,
        section_title=chunk.section_title,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        evidence_layer=metadata.get("evidence_layer"),
        source_type=metadata.get("source_type"),
        source_path=metadata.get("source_path"),
        content_hash=metadata.get("content_hash"),
        semantic_links=[_semantic_link_response(link) for link in semantic_links or []],
    )


def _semantic_link_response(link: ChunkSemanticLink) -> dict[str, Any]:
    properties = link.properties or {}
    return {
        "entity_name": link.entity_name,
        "entity_type": link.entity_type,
        "rel_type": link.rel_type,
        "direction": link.direction,
        "related_entity_name": link.related_entity_name,
        "related_entity_type": link.related_entity_type,
        "ontology_version": properties.get("ontology_version"),
        "mapping_rule": properties.get("mapping_rule"),
        "evidence_layer": properties.get("evidence_layer"),
        "source_type": properties.get("source_type"),
        "confidence": properties.get("confidence"),
    }


def _semantic_link_context(link: ChunkSemanticLink) -> dict[str, Any]:
    properties = link.properties or {}
    return {
        "relation": link.rel_type,
        "entity": link.entity_name,
        "related_entity": link.related_entity_name,
        "mapping_rule": properties.get("mapping_rule"),
        "ontology_version": properties.get("ontology_version"),
    }
