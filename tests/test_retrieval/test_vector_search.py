"""Integration tests — vector and keyword search via testcontainers PG."""

import uuid

import numpy as np
import pytest

from rag_ocpp.storage.vector import ChunkInsert

EMBEDDING_DIM = 1024


def _normalized_embedding(seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    embedding = rng.normal(size=EMBEDDING_DIM).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)
    return embedding.tolist()


@pytest.mark.asyncio
class TestVectorSearch:
    async def test_insert_and_search(self, vector_store):
        doc_id = await vector_store.insert_document(
            protocol_id=1,
            source_path="t.pdf",
            doc_type="spec",
            title="T",
            page_count=1,
            raw_bytes=100,
        )
        emb = _normalized_embedding(seed=1)
        chunk = ChunkInsert(id=uuid.uuid4(), document_id=doc_id, chunk_index=0,
                            content="The Authorize.req message requires an IdToken.",
                            content_hash="abc", embedding=emb, strategy="sdpm",
                            page_start=1, page_end=1)
        await vector_store.insert_chunks([chunk])
        results = await vector_store.vector_search(emb, top_k=5)
        assert len(results) == 1 and results[0].similarity > 0.99
        assert results[0].document_id == doc_id

    async def test_keyword_search(self, vector_store):
        doc_id = await vector_store.insert_document(
            protocol_id=1,
            source_path="t.pdf",
            doc_type="spec",
            title="T",
            page_count=1,
            raw_bytes=100,
        )
        chunk = ChunkInsert(id=uuid.uuid4(), document_id=doc_id, chunk_index=0,
                            content="BootNotification is sent when a ChargePoint starts.",
                            content_hash="def", embedding=None, strategy="sdpm")
        await vector_store.insert_chunks([chunk])
        results = await vector_store.keyword_search("BootNotification")
        assert len(results) == 1 and "BootNotification" in results[0].content
        assert results[0].document_id == doc_id

    async def test_pending_and_update(self, vector_store):
        doc_id = await vector_store.insert_document(
            protocol_id=1,
            source_path="t.pdf",
            doc_type="spec",
            title="T",
            page_count=1,
            raw_bytes=100,
        )
        chunk = ChunkInsert(id=uuid.uuid4(), document_id=doc_id, chunk_index=0,
                            content="Test", content_hash="ghi", embedding=None, strategy="sdpm")
        await vector_store.insert_chunks([chunk])
        assert len(await vector_store.get_pending_chunks(10)) == 1
        emb = _normalized_embedding(seed=2)
        await vector_store.update_embeddings([(chunk.id, emb)])
        assert len(await vector_store.get_pending_chunks(10)) == 0

    async def test_no_embed_upsert_preserves_existing_embedding(self, vector_store):
        doc_id = await vector_store.insert_document(
            protocol_id=1,
            source_path="t.pdf",
            doc_type="spec",
            title="T",
            page_count=1,
            raw_bytes=100,
        )
        emb = _normalized_embedding(seed=3)
        chunk_id = uuid.uuid4()
        await vector_store.insert_chunks([
            ChunkInsert(
                id=chunk_id,
                document_id=doc_id,
                chunk_index=0,
                content="Original chunk",
                content_hash="original",
                embedding=emb,
                strategy="corpus_record",
            )
        ])

        await vector_store.insert_chunks([
            ChunkInsert(
                id=chunk_id,
                document_id=doc_id,
                chunk_index=0,
                content="Relinked chunk without embedding",
                content_hash="relinked",
                embedding=None,
                strategy="corpus_record",
            )
        ])

        assert len(await vector_store.get_pending_chunks(10)) == 0
        results = await vector_store.vector_search(emb, top_k=5)
        assert len(results) == 1
        assert results[0].content == "Relinked chunk without embedding"
        assert results[0].similarity > 0.99

    async def test_delete(self, vector_store):
        doc_id = await vector_store.insert_document(
            protocol_id=1,
            source_path="t.pdf",
            doc_type="spec",
            title="X",
            page_count=1,
            raw_bytes=100,
        )
        await vector_store.delete_document(doc_id)
        assert len(await vector_store.list_documents()) == 0
