"""Graph-based retrieval — entity extraction, ontology traversal, chunk lookup."""

from __future__ import annotations

import asyncpg

from rag_ocpp.knowledge.entities import extract_entity_names
from rag_ocpp.retrieval.searchers import ScoredChunk
from rag_ocpp.storage.graph import ChunkSemanticLink, GraphStore

_ONTOLOGY_VERSION_BOOST = 0.08
_ONTOLOGY_MAPPING_RULE_BOOST = 0.04
_ONTOLOGY_CONFIDENCE_BOOST = 0.08


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
        ontology_aware: bool = True,
    ) -> list[ScoredChunk]:
        entity_names = extract_entity_names(query)
        # Fallback: query DB for entity names matching query words
        if not entity_names:
            entity_names = await self._graph.find_entity_names_by_terms(query, limit=5)
        if not entity_names:
            return []

        results = await self._graph.search_by_entity_names(
            protocol_id=protocol_id, entity_names=entity_names, top_k=top_k,
        )

        scored = []
        for r in results:
            # Boost spec chunks (Part 0-5) vs test case chunks (Part 6)
            section = r.section_title or ""
            page = r.page_start or 0
            is_test = (
                "Test Case" in section
                or section.startswith("TC_")
                or page > 1500
            )
            confidence = 0.5 if is_test else 0.9
            metadata = dict(r.metadata or {})
            metadata.setdefault("graph_traversal_depth", 0)
            scored.append(ScoredChunk(
                r.chunk_id, r.document_id, r.chunk_index,
                r.content, section, r.page_start,
                r.page_end, confidence, "graph", metadata,
            ))

        if expand_via_traversal and len(scored) < top_k:
            expanded = await self._expand(
                entity_names,
                protocol_id,
                top_k - len(scored),
                max_traversal_depth,
                ontology_aware=ontology_aware,
            )
            scored.extend(expanded)

        if ontology_aware:
            scored = await self._apply_ontology_boost(scored)
        scored = _dedupe_keep_best(scored)
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]

    async def _expand(
        self, entity_names: list[str], protocol_id: int,
        needed: int, max_depth: int, *, ontology_aware: bool,
    ) -> list[ScoredChunk]:
        all_chunks: list[ScoredChunk] = []
        rel_types = (
            await self._graph.get_active_ontology_relation_types(protocol_id=protocol_id)
            if ontology_aware
            else []
        )
        for name in entity_names:
            nodes = await self._graph.traverse_by_name(
                protocol_id=protocol_id, entity_name=name,
                rel_types=rel_types or None,
                max_depth=max_depth,
                follow_both_directions=True,
            )
            related_depths = {n.entity_id: n.depth for n in nodes if n.depth > 0}
            for eid, depth in related_depths.items():
                chunks = await self._graph.get_chunks_for_entity(eid, top_k=min(needed, 5))
                for c in chunks:
                    metadata = dict(c.metadata or {})
                    metadata["graph_traversal_depth"] = depth
                    all_chunks.append(ScoredChunk(
                        c.chunk_id, c.document_id, c.chunk_index,
                        c.content, c.section_title, c.page_start,
                        c.page_end, c.confidence * 0.7, "graph", metadata,
                    ))
                if len(all_chunks) >= needed:
                    break
            if len(all_chunks) >= needed:
                break
        return all_chunks

    async def _apply_ontology_boost(
        self,
        chunks: list[ScoredChunk],
    ) -> list[ScoredChunk]:
        links_by_chunk = await self._graph.get_semantic_links_for_chunks(
            [chunk.chunk_id for chunk in chunks],
            max_links_per_chunk=5,
        )
        boosted: list[ScoredChunk] = []
        for chunk in chunks:
            links = links_by_chunk.get(chunk.chunk_id, [])
            if not links:
                boosted.append(chunk)
                continue
            score = min(1.0, chunk.score + _ontology_link_boost(links))
            metadata = dict(chunk.metadata or {})
            metadata.update(_ontology_metadata(links))
            boosted.append(
                ScoredChunk(
                    chunk.chunk_id,
                    chunk.document_id,
                    chunk.chunk_index,
                    chunk.content,
                    chunk.section_title,
                    chunk.page_start,
                    chunk.page_end,
                    score,
                    chunk.strategy,
                    metadata,
                )
            )
        return boosted


def _ontology_link_boost(links: list[ChunkSemanticLink]) -> float:
    best = 0.0
    for link in links:
        props = link.properties or {}
        confidence = props.get("confidence")
        try:
            confidence_value = float(confidence) if confidence is not None else 0.0
        except (TypeError, ValueError):
            confidence_value = 0.0
        boost = 0.0
        if props.get("ontology_version"):
            boost += _ONTOLOGY_VERSION_BOOST
        if props.get("mapping_rule"):
            boost += _ONTOLOGY_MAPPING_RULE_BOOST
        boost += min(max(confidence_value, 0.0), 1.0) * _ONTOLOGY_CONFIDENCE_BOOST
        best = max(best, boost)
    return best


def _ontology_metadata(links: list[ChunkSemanticLink]) -> dict[str, object]:
    rules = sorted(
        {
            str((link.properties or {}).get("mapping_rule"))
            for link in links
            if (link.properties or {}).get("mapping_rule")
        }
    )
    relations = sorted({link.rel_type for link in links})
    versions = sorted(
        {
            str((link.properties or {}).get("ontology_version"))
            for link in links
            if (link.properties or {}).get("ontology_version")
        }
    )
    return {
        "graph_semantic_links": len(links),
        "graph_ontology_relations": relations,
        "graph_ontology_rules": rules,
        "graph_ontology_versions": versions,
    }


def _dedupe_keep_best(chunks: list[ScoredChunk]) -> list[ScoredChunk]:
    by_id: dict[object, ScoredChunk] = {}
    for chunk in chunks:
        existing = by_id.get(chunk.chunk_id)
        if existing is None or chunk.score > existing.score:
            by_id[chunk.chunk_id] = chunk
    return list(by_id.values())
