"""POST /ingest — document ingestion endpoint."""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path

import asyncpg
from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import JSONResponse

from rag_ocpp.api.dependencies import (
    get_embedding_model,
    get_graph_store,
    get_pool,
    get_vector_store,
)
from rag_ocpp.api.schemas import IngestResponse
from rag_ocpp.chunking.engine import ChunkingEngine
from rag_ocpp.embedding.batch import BatchEmbedder
from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.ingestion.cleaner import TextCleaner
from rag_ocpp.ingestion.metadata import OCPPMetadataExtractor
from rag_ocpp.ingestion.parser import DocumentParser
from rag_ocpp.knowledge.extractor import EntityExtractor
from rag_ocpp.knowledge.linker import EntityLinker
from rag_ocpp.storage.graph import GraphStore
from rag_ocpp.storage.vector import ChunkInsert, VectorStore

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile,
    doc_type: str = "spec",
    protocol: str = "ocpp21",
    version: str = "2.1",
    request: Request = None,  # type: ignore[assignment]
    pool: asyncpg.Pool = Depends(get_pool),
    vector_store: VectorStore = Depends(get_vector_store),
    graph_store: GraphStore = Depends(get_graph_store),
    embedding_model: EmbeddingModel = Depends(get_embedding_model),
):
    if not file.filename:
        return JSONResponse(status_code=400, content={"detail": "No filename"})

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf", ".json"):
        return JSONResponse(status_code=400, content={"detail": f"Unsupported: {suffix}"})

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        parser = DocumentParser()
        parsed = parser.parse(tmp_path)
        parsed.doc_type = doc_type

        cleaner = TextCleaner()
        for page in parsed.pages:
            page.text = cleaner.clean(page.text)

        meta = OCPPMetadataExtractor().extract(
            tmp_path, parsed, protocol=protocol, version=version, doc_type=doc_type,
        )

        file_size = tmp_path.stat().st_size
        doc_id = await vector_store.insert_document(
            protocol_id=1, source_path=file.filename, doc_type=doc_type,
            title=meta.part or file.filename, version=meta.version,
            part=meta.part, page_count=parsed.metadata.page_count,
            raw_bytes=file_size,
        )

        engine = ChunkingEngine()
        chunks = engine.chunk(parsed, doc_type)

        chunk_inserts = [
            ChunkInsert(
                id=uuid.uuid4(), document_id=doc_id, chunk_index=i,
                content=c.content, content_hash=c.content_hash,
                strategy=c.strategy, section_title=c.section_title,
                page_start=c.page_start, page_end=c.page_end,
                token_count=c.token_count,
            )
            for i, c in enumerate(chunks)
        ]

        await vector_store.insert_chunks(chunk_inserts)

        embedder = BatchEmbedder(pool, embedding_model, vector_store)
        await embedder.embed_batch(
            [ci.id for ci in chunk_inserts], [ci.content for ci in chunk_inserts],
        )

        linker = EntityLinker(pool)
        extractor = EntityExtractor(enable_llm=True)
        entity_count = 0

        for ci in chunk_inserts:
            result = await extractor.extract(ci.content, ci.content_hash)
            if result.entities:
                await linker.resolve_and_link(ci.id, result.entities)
                entity_count += len(result.entities)
            if result.relations:
                await linker.resolve_relations(result.relations)

        return IngestResponse(
            document_id=doc_id, source_path=file.filename, doc_type=doc_type,
            protocol=protocol, version=version, part=meta.part,
            page_count=parsed.metadata.page_count,
            chunks_created=len(chunks), entities_extracted=entity_count,
            embedding_model=embedding_model.model_name,
        )

    finally:
        tmp_path.unlink(missing_ok=True)
