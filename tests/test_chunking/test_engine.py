"""Unit tests — ChunkingEngine."""

from pathlib import Path

from rag_ocpp.chunking.engine import ChunkingEngine
from rag_ocpp.ingestion.parser import DocumentMetadata, ParsedDocument, ParsedPage


def _doc(text: str) -> ParsedDocument:
    return ParsedDocument(
        source_path=Path("t.pdf"), doc_type="spec",
        pages=[ParsedPage(page_num=1, text=text)],
        metadata=DocumentMetadata(page_count=1, toc=[]),
    )


class TestChunking:
    def test_spec_uses_sdpm(self):
        chunks = ChunkingEngine().chunk(_doc("A " * 600), "spec")
        assert len(chunks) > 0 and all(c.strategy == "sdpm" for c in chunks)

    def test_hash_is_sha256_hex(self):
        chunks = ChunkingEngine().chunk(_doc("A" * 2000), "spec")
        assert all(len(c.content_hash) == 64 for c in chunks)

    def test_page_by_page(self):
        engine = ChunkingEngine()
        doc = ParsedDocument(
            source_path=Path("t.pdf"), doc_type="spec",
            pages=[ParsedPage(page_num=1, text="P1 " * 50), ParsedPage(page_num=2, text="P2 " * 50)],
            metadata=DocumentMetadata(page_count=2, toc=[]),
        )
        chunks = engine.chunk_page_by_page(doc, "spec")
        assert any(c.page_start == 1 for c in chunks)
        assert any(c.page_start == 2 for c in chunks)

    def test_empty(self):
        assert ChunkingEngine().chunk(_doc(""), "spec") == []

    def test_fallback(self):
        chunks = ChunkingEngine().chunk(_doc("X " * 200), "other")
        assert all(c.strategy == "recursive" for c in chunks)
