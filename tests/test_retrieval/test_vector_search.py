"""Integration tests — vector and keyword search via testcontainers PG."""

import uuid

import numpy as np
import pytest

from rag_ocpp.storage.vector import ChunkInsert


@pytest.mark.asyncio
class TestVectorSearch:
    async def test_insert_and_search(self, vector_store):
        doc_id = uuid.uuid4()
        await vector_store.insert_document(protocol_id=1, source_path="t.pdf", doc_type="spec", title="T", page_count=1, raw_bytes=100)
        emb = np.random.randn(768).astype(np.float32); emb = emb / np.linalg.norm(emb)
        chunk = ChunkInsert(id=uuid.uuid4(), document_id=doc_id, chunk_index=0,
                            content="The Authorize.req message requires an IdToken.",
                            content_hash="abc", embedding=emb.tolist(), strategy="sdpm",
                            page_start=1, page_end=1)
        await vector_store.insert_chunks([chunk])
        results = await vector_store.vector_search(emb.tolist(), top_k=5)
        assert len(results) == 1 and results[0].similarity > 0.99

    async def test_keyword_search(self, vector_store):
        doc_id = uuid.uuid4()
        await vector_store.insert_document(protocol_id=1, source_path="t.pdf", doc_type="spec", title="T", page_count=1, raw_bytes=100)
        chunk = ChunkInsert(id=uuid.uuid4(), document_id=doc_id, chunk_index=0,
                            content="BootNotification is sent when a ChargePoint starts.",
                            content_hash="def", embedding=None, strategy="sdpm")
        await vector_store.insert_chunks([chunk])
        results = await vector_store.keyword_search("BootNotification")
        assert len(results) == 1 and "BootNotification" in results[0].content

    async def test_pending_and_update(self, vector_store):
        doc_id = uuid.uuid4()
        await vector_store.insert_document(protocol_id=1, source_path="t.pdf", doc_type="spec", title="T", page_count=1, raw_bytes=100)
        chunk = ChunkInsert(id=uuid.uuid4(), document_id=doc_id, chunk_index=0,
                            content="Test", content_hash="ghi", embedding=None, strategy="sdpm")
        await vector_store.insert_chunks([chunk])
        assert len(await vector_store.get_pending_chunks(10)) == 1
        emb = np.random.randn(768).astype(np.float32).tolist()
        await vector_store.update_embeddings([(chunk.id, emb)])
        assert len(await vector_store.get_pending_chunks(10)) == 0

    async def test_delete(self, vector_store):
        doc_id = uuid.uuid4()
        await vector_store.insert_document(protocol_id=1, source_path="t.pdf", doc_type="spec", title="X", page_count=1, raw_bytes=100)
        await vector_store.delete_document(doc_id)
        assert len(await vector_store.list_documents()) == 0
