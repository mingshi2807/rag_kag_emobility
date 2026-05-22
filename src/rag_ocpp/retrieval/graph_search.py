"""Graph-based retrieval — entity extraction from query, graph traversal, chunk lookup."""

from __future__ import annotations

import asyncpg

from rag_ocpp.knowledge.entities import extract_entity_names
from rag_ocpp.retrieval.searchers import ScoredChunk
from rag_ocpp.storage.graph import GraphStore


class GraphSearcher:
    """Knowledge-graph-based retrieval.

    1. Extract entity names from query (regex)
    2. Look up chunks linked to those entities via chunk_entities bridge
    3. Optionally traverse relationships to expand the search
    """

    def __init__(
        self, pool: asyncpg.Pool,
        graph_store: GraphStore | None = None,
    ) -> None:
        self._graph = graph_store or GraphStore(pool)

    async def search(
        self, query: str, *, top_k: int = 10, protocol_id: int = 1,
        expand_via_traversal: bool = False, max_traversal_depth: int = 2,
    ) -> list[ScoredChunk]:
        entity_names = extract_entity_names(query)
        if not entity_names:
            return []

        results = await self._graph.search_by_entity_names(
            protocol_id=protocol_id, entity_names=entity_names, top_k=top_k,
        )

        scored = [
            ScoredChunk(r.chunk_id, r.document_id, r.chunk_index,
                        r.content, r.section_title, r.page_start,
                        r.page_end, r.confidence, "graph")
            for r in results
        ]

        if expand_via_traversal and len(scored) < top_k:
            expanded = await self._expand(
                entity_names, protocol_id, top_k - len(scored), max_traversal_depth,
            )
            scored.extend(expanded)

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]

    async def _expand(
        self, entity_names: list[str], protocol_id: int,
        needed: int, max_depth: int,
    ) -> list[ScoredChunk]:
        all_chunks: list[ScoredChunk] = []
        for name in entity_names:
            nodes = await self._graph.traverse_by_name(
                protocol_id=protocol_id, entity_name=name,
                max_depth=max_depth, follow_both_directions=True,
            )
            related_ids = [n.entity_id for n in nodes if n.depth > 0]
            for eid in related_ids:
                chunks = await self._graph.get_chunks_for_entity(eid, top_k=min(needed, 5))
                for c in chunks:
                    all_chunks.append(ScoredChunk(
                        c.chunk_id, c.document_id, c.chunk_index,
                        c.content, c.section_title, c.page_start,
                        c.page_end, c.confidence * 0.7, "graph",
                    ))
                if len(all_chunks) >= needed:
                    break
            if len(all_chunks) >= needed:
                break
        return all_chunks
