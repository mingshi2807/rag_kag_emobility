"""Chunking engine — chonkie wrappers with per-document-type strategy dispatch."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from chonkie import RecursiveChunker, SDPMChunker, SentenceChunker

from rag_ocpp.config import ChunkingConfig, get_config
from rag_ocpp.ingestion.metadata import OCPPMetadataExtractor
from rag_ocpp.ingestion.parser import ParsedDocument


# ── Data types ────────────────────────────────────────────

@dataclass
class Chunk:
    """A single text chunk ready for embedding and storage."""
    index: int
    content: str
    content_hash: str
    strategy: str
    section_title: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    token_count: int = 0
    metadata: dict[str, Any] | None = None


# ── Engine ────────────────────────────────────────────────

class ChunkingEngine:
    """Chunk documents using chonkie with strategy dispatch.

    Strategies by document type:
        spec        → SDPMChunker   (semantic boundary aware, 512/64 tokens)
        test_suite  → SentenceChunker (fine-grained, 256/32 tokens)
        json_config → SentenceChunker
        fallback    → RecursiveChunker (character-based, 1024/128)

    Why SDPM for OCPP specs:
        OCPP specifications are hierarchically structured
        (Part -> Section -> Subsection -> Paragraph).
        SDPM's threshold-based semantic merging preserves these boundaries —
        chunks won't span across section breaks when semantic similarity
        drops at topic boundaries.
    """

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        if config is None:
            config = get_config().chunking
        self._config = config

        self._sdpm = SDPMChunker(
            chunk_size=config.spec.chunk_size,
            chunk_overlap=config.spec.chunk_overlap,
            min_sentences_per_chunk=config.spec.min_sentences_per_chunk,
            threshold=config.spec.threshold,
        )
        self._sentence = SentenceChunker(
            chunk_size=config.test_suite.chunk_size,
            chunk_overlap=config.test_suite.chunk_overlap,
        )
        self._recursive = RecursiveChunker(
            chunk_size=config.fallback.chunk_size,
            chunk_overlap=config.fallback.chunk_overlap,
        )

    def chunk(self, doc: ParsedDocument, doc_type: str) -> list[Chunk]:
        """Chunk a parsed document using the strategy for its document type."""
        strategy = self._select_strategy(doc_type)
        strategy_name = self._strategy_name(doc_type)
        section_map = self._build_section_map(doc)

        flat_text = doc.flat_text
        if not flat_text.strip():
            return []

        raw_chunks = strategy.chunk(flat_text)
        page_map = self._build_page_char_map(doc)

        chunks: list[Chunk] = []
        for i, raw in enumerate(raw_chunks):
            text = raw if isinstance(raw, str) else raw.text
            tokens = 0 if isinstance(raw, str) else getattr(raw, "token_count", 0)

            char_start = flat_text.find(text[:80])
            char_end = char_start + len(text) if char_start >= 0 else -1
            page_start, page_end = self._char_to_page(page_map, char_start, char_end)
            section = self._find_section(section_map, page_start)

            chunks.append(Chunk(
                index=i,
                content=text,
                content_hash=hashlib.sha256(text.encode()).hexdigest(),
                strategy=strategy_name,
                section_title=section,
                page_start=page_start,
                page_end=page_end,
                token_count=tokens,
            ))

        return chunks

    def chunk_page_by_page(
        self, doc: ParsedDocument, doc_type: str
    ) -> list[Chunk]:
        """Chunk page by page — exact page attribution, no cross-page coherence."""
        strategy = self._select_strategy(doc_type)
        strategy_name = self._strategy_name(doc_type)
        section_map = self._build_section_map(doc)

        all_chunks: list[Chunk] = []
        chunk_index = 0

        for page in doc.pages:
            if not page.text.strip():
                continue
            raw_chunks = strategy.chunk(page.text)
            section = self._find_section(section_map, page.page_num)

            for raw in raw_chunks:
                text = raw if isinstance(raw, str) else raw.text
                tokens = 0 if isinstance(raw, str) else getattr(raw, "token_count", 0)

                all_chunks.append(Chunk(
                    index=chunk_index,
                    content=text,
                    content_hash=hashlib.sha256(text.encode()).hexdigest(),
                    strategy=strategy_name,
                    section_title=section,
                    page_start=page.page_num,
                    page_end=page.page_num,
                    token_count=tokens,
                ))
                chunk_index += 1

        return all_chunks

    # ── Internal ────────────────────────────────────────

    def _select_strategy(
        self, doc_type: str
    ) -> SDPMChunker | SentenceChunker | RecursiveChunker:
        match doc_type:
            case "spec":
                return self._sdpm
            case "test_suite":
                return self._sentence
            case "json_config":
                return self._sentence
            case _:
                return self._recursive

    def _strategy_name(self, doc_type: str) -> str:
        match doc_type:
            case "spec":
                return self._config.spec.strategy
            case "test_suite":
                return self._config.test_suite.strategy
            case _:
                return self._config.fallback.strategy

    def _build_section_map(self, doc: ParsedDocument) -> dict[int, str]:
        extractor = OCPPMetadataExtractor()
        sections = extractor.detect_sections(doc)
        section_map: dict[int, str] = {}
        for sec in sections:
            for p in range(sec.get("page_start", 1), sec.get("page_end", 9999) + 1):
                title = sec.get("title", "")
                if p not in section_map:
                    section_map[p] = title
        return section_map

    def _build_page_char_map(self, doc: ParsedDocument) -> list[tuple[int, int]]:
        char_map: list[tuple[int, int]] = []
        offset = 0
        for page in doc.pages:
            char_start = offset
            char_end = offset + len(page.text)
            char_map.append((char_start, char_end))
            offset = char_end + 2
        return char_map

    def _char_to_page(
        self, page_map: list[tuple[int, int]], char_start: int, char_end: int
    ) -> tuple[int | None, int | None]:
        page_start: int | None = None
        page_end: int | None = None
        for i, (cs, ce) in enumerate(page_map):
            if page_start is None and char_start >= cs and char_start <= ce:
                page_start = i + 1
            if page_end is None and char_end >= cs and char_end <= ce:
                page_end = i + 1
            if page_start is not None and page_end is not None:
                break
        return page_start, page_end

    def _find_section(
        self, section_map: dict[int, str], page_num: int | None
    ) -> str | None:
        if page_num is None:
            return None
        return section_map.get(page_num)
