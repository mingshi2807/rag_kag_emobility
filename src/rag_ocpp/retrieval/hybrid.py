"""Hybrid retriever — orchestrates vector, keyword, and graph search with fusion + rerank."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import asyncpg

from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.retrieval.fusion import reciprocal_rank_fusion
from rag_ocpp.retrieval.graph_search import GraphSearcher
from rag_ocpp.retrieval.reranker import CrossEncoderReranker
from rag_ocpp.retrieval.searchers import KeywordSearcher, ScoredChunk, VectorSearcher


@dataclass
class SearchFilters:
    protocol_id: int | None = None
    doc_type: str | None = None


@dataclass
class RetrievalResult:
    chunks: list[ScoredChunk]
    strategy_breakdown: dict[str, int]
    latency_ms: int


class HybridRetriever:
    """Multi-strategy retrieval: vector + keyword + graph → RRF → rerank.

    Pipeline:
        1. Embed query
        2. Parallel: vector, keyword, graph searches
        3. RRF fusion (k=60)
        4. Cross-encoder rerank on top-30 fused
        5. Return top-k
    """

    def __init__(
        self, pool: asyncpg.Pool, embedding_model: EmbeddingModel,
        reranker: CrossEncoderReranker, *,
        vector_top_k: int = 20, keyword_top_k: int = 20,
        graph_top_k: int = 10, fusion_k: int = 60, final_top_k: int = 5,
        enable_graph: bool = True, enable_rerank: bool = True,
    ) -> None:
        self._vector = VectorSearcher(pool, embedding_model)
        self._keyword = KeywordSearcher(pool)
        self._graph = GraphSearcher(pool)
        self._reranker = reranker
        self._model = embedding_model
        self._vector_top_k = vector_top_k
        self._keyword_top_k = keyword_top_k
        self._graph_top_k = graph_top_k
        self._fusion_k = fusion_k
        self._final_top_k = final_top_k
        self._enable_graph = enable_graph
        self._enable_rerank = enable_rerank

    async def retrieve(
        self, query: str, *, filters: SearchFilters | None = None,
    ) -> RetrievalResult:
        t0 = time.monotonic()
        pid = filters.protocol_id if filters else None
        dt = filters.doc_type if filters else None

        self._model.embed_query(query)  # warm BGE cache

        tasks: list[asyncio.Task[list[ScoredChunk]]] = [
            asyncio.create_task(self._vector.search(
                query, top_k=self._vector_top_k, protocol_id=pid, doc_type=dt)),
            asyncio.create_task(self._keyword.search(
                query, top_k=self._keyword_top_k, protocol_id=pid, doc_type=dt)),
        ]
        if self._enable_graph:
            tasks.append(asyncio.create_task(self._graph.search(
                query, top_k=self._graph_top_k, protocol_id=pid or 1,
                expand_via_traversal=True)))

        import logging
        _log = logging.getLogger(__name__)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        vec = results[0] if not isinstance(results[0], Exception) else []
        kw = results[1] if not isinstance(results[1], Exception) else []
        gr = results[2] if len(results) > 2 and not isinstance(results[2], Exception) else []
        for label, r in zip(["vec","kw","gr"], results):
            if isinstance(r, Exception):
                _log.warning("%s search failed: %s", label, r)
        _log.info("vec=%d kw=%d gr=%d", len(vec), len(kw), len(gr))

        # Weighted RRF: keyword 3x (tech specs), graph 2x (entity-linked)
        weights = [1.0, 3.0, 2.0]  # vector, keyword, graph
        fused = reciprocal_rank_fusion([vec, kw, gr], k=self._fusion_k, weights=weights)
        top_fused = fused[:max(30, self._final_top_k)]

        if self._enable_rerank:
            candidates = [c for c, _ in top_fused]
            final = self._reranker.rerank(query, candidates, top_k=self._final_top_k)
        else:
            final = [c for c, _ in top_fused[:self._final_top_k]]

        # Graph floor: ensure at least 1 entity-linked chunk if graph returned results
        if gr and not any(c.strategy == "graph" for c in final):
            best_gr = max(gr, key=lambda c: c.score)
            if final:
                final[-1] = best_gr
            else:
                final = [best_gr]

        breakdown: dict[str, int] = {}
        for c in final:
            breakdown[c.strategy] = breakdown.get(c.strategy, 0) + 1

        return RetrievalResult(
            chunks=final,
            strategy_breakdown=breakdown,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    async def search_only(
        self, query: str, *, filters: SearchFilters | None = None,
        top_k: int | None = None,
    ) -> RetrievalResult:
        """Retrieval without reranking (faster, for search-only endpoints)."""
        save_k = self._final_top_k
        if top_k is not None:
            self._final_top_k = top_k

        t0 = time.monotonic()
        pid = filters.protocol_id if filters else None
        dt = filters.doc_type if filters else None

        tasks = [
            asyncio.create_task(self._vector.search(
                query, top_k=self._vector_top_k, protocol_id=pid, doc_type=dt)),
            asyncio.create_task(self._keyword.search(
                query, top_k=self._keyword_top_k, protocol_id=pid, doc_type=dt)),
        ]
        if self._enable_graph:
            tasks.append(asyncio.create_task(self._graph.search(
                query, top_k=self._graph_top_k, protocol_id=pid or 1,
                expand_via_traversal=True)))

        import logging
        _log = logging.getLogger(__name__)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        vec = results[0] if not isinstance(results[0], Exception) else []
        kw = results[1] if not isinstance(results[1], Exception) else []
        gr = results[2] if len(results) > 2 and not isinstance(results[2], Exception) else []
        for label, r in zip(["vec","kw","gr"], results):
            if isinstance(r, Exception):
                _log.warning("%s search failed: %s", label, r)
        _log.info("vec=%d kw=%d gr=%d", len(vec), len(kw), len(gr))

        fused = reciprocal_rank_fusion([vec, kw, gr], k=self._fusion_k, weights=[1.0, 3.0, 2.0])
        top = [c for c, _ in fused[:self._final_top_k]]
        self._final_top_k = save_k

        breakdown: dict[str, int] = {}
        for c in top:
            breakdown[c.strategy] = breakdown.get(c.strategy, 0) + 1
 
        return RetrievalResult(
            chunks=top,
            strategy_breakdown=breakdown,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
