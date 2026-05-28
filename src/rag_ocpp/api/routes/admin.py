"""Admin endpoints — documents, entities, health."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from rag_ocpp.api.dependencies import (
    get_audit_store,
    get_embedding_model,
    get_graph_store,
    get_reranker,
    get_vector_store,
)
from rag_ocpp.api.schemas import DocumentResponse, EntityResponse, HealthResponse
from rag_ocpp.api.security import require_admin
from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.privacy import redact_value
from rag_ocpp.retrieval.reranker import CrossEncoderReranker
from rag_ocpp.storage.audit import AuditEvent, AuditStore
from rag_ocpp.storage.graph import GraphStore
from rag_ocpp.storage.vector import VectorStore

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(
    vs: VectorStore = Depends(get_vector_store),
    emb: EmbeddingModel = Depends(get_embedding_model),
    reranker: CrossEncoderReranker = Depends(get_reranker),
):
    db = "disconnected"
    try:
        await vs._pool.fetchrow("SELECT 1")
        db = "connected"
    except Exception:
        pass
    return HealthResponse(
        status="ok" if db == "connected" else "degraded",
        database=db, embedding_model=emb.model_name,
        embedding_loaded=emb.is_loaded, reranker_loaded=reranker.is_loaded,
    )


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    protocol: str | None = None,
    vs: VectorStore = Depends(get_vector_store),
):
    pid = 1 if protocol == "ocpp21" else None
    rows = await vs.list_documents(protocol_id=pid)
    return [
        DocumentResponse(
            id=r["id"], protocol_id=r["protocol_id"], source_path=r["source_path"],
            doc_type=r["doc_type"], title=r["title"], version=r["version"],
            part=r["part"], page_count=r["page_count"], ingested_at=r["ingested_at"],
            chunk_count=r.get("chunk_count", 0), entity_count=r.get("entity_count", 0),
        ) for r in rows
    ]


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    _: None = Depends(require_admin),
    vs: VectorStore = Depends(get_vector_store),
    audit: AuditStore = Depends(get_audit_store),
):
    document_uuid = UUID(document_id)
    try:
        count = await vs.delete_document(document_uuid)
    except Exception as exc:
        await _audit(
            audit,
            AuditEvent(
                event_type="admin.document_delete",
                surface="api",
                action="delete_document",
                status="failure",
                resource_type="document",
                resource_id=document_id,
                metadata={"error": redact_value(exc, force=True)},
            ),
        )
        raise
    if count == 0:
        await _audit(
            audit,
            AuditEvent(
                event_type="admin.document_delete",
                surface="api",
                action="delete_document",
                status="failure",
                resource_type="document",
                resource_id=document_id,
                metadata={"reason": "not_found"},
            ),
        )
        raise HTTPException(status_code=404, detail="Not found")
    await _audit(
        audit,
        AuditEvent(
            event_type="admin.document_delete",
            surface="api",
            action="delete_document",
            resource_type="document",
            resource_id=document_id,
            metadata={"deleted_chunks": count},
        ),
    )
    return {"status": "deleted", "document_id": document_id}


@router.get("/entities/{name}", response_model=EntityResponse)
async def get_entity(
    name: str,
    graph: GraphStore = Depends(get_graph_store),
):
    entity = await graph.find_entity(protocol_id=1, name=name)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity '{name}' not found")
    rels = await graph.get_relationships(entity.id, direction="both")
    chunks = await graph.get_chunks_for_entity(entity.id, top_k=5)
    return EntityResponse(
        id=entity.id, name=entity.name, description=entity.description,
        aliases=entity.aliases, chunk_count=len(chunks),
        relationships=[
            {"id": str(r.id), "source_id": str(r.source_id),
             "target_id": str(r.target_id), "rel_type": r.rel_type,
             "properties": r.properties}
            for r in rels
        ],
    )


async def _audit(audit: AuditStore, event: AuditEvent) -> None:
    try:
        await audit.record(event)
    except Exception:
        pass
