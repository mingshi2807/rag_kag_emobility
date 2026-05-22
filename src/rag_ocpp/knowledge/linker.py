"""Entity linker — resolve extracted mentions to database entity IDs."""

from __future__ import annotations

import logging
from uuid import UUID

import asyncpg

from rag_ocpp.knowledge.extractor import EntityMention, RelationMention
from rag_ocpp.storage.graph import GraphStore

logger = logging.getLogger(__name__)


class EntityLinker:
    """Resolve entity mentions to database UUIDs.

    Resolution chain: exact → alias → fuzzy → create new.

    Usage:
        linker = EntityLinker(pool)
        ids = await linker.resolve(mentions, protocol_id=1)
        await linker.link_chunks(chunk_id, ids)
    """

    def __init__(
        self, pool: asyncpg.Pool, fuzzy_threshold: float = 0.5
    ) -> None:
        self._graph = GraphStore(pool)
        self._fuzzy_threshold = fuzzy_threshold

    # ── Entity resolution ───────────────────────────────

    async def resolve(
        self,
        mentions: list[EntityMention],
        protocol_id: int = 1,
    ) -> list[UUID]:
        """Resolve mentions to UUIDs, deduplicating by (type_id, name)."""
        seen: dict[tuple[int, str], UUID] = {}
        results: list[UUID] = []

        for m in mentions:
            key = (m.type_id, m.name)
            if key in seen:
                results.append(seen[key])
                continue

            entity_id = await self._resolve_one(protocol_id, m.type_id, m.name)
            seen[key] = entity_id
            results.append(entity_id)

        return results

    async def resolve_one(
        self, mention: EntityMention, protocol_id: int = 1
    ) -> UUID:
        return await self._resolve_one(protocol_id, mention.type_id, mention.name)

    # ── Chunk linking ───────────────────────────────────

    async def link_chunks(
        self,
        chunk_id: UUID,
        entity_ids: list[UUID],
        confidences: list[float] | None = None,
    ) -> int:
        count = 0
        for i, eid in enumerate(entity_ids):
            conf = confidences[i] if confidences else 1.0
            await self._graph.link_chunk_entity(
                chunk_id=chunk_id, entity_id=eid, confidence=conf,
            )
            count += 1
        return count

    async def resolve_and_link(
        self,
        chunk_id: UUID,
        mentions: list[EntityMention],
        protocol_id: int = 1,
    ) -> int:
        entity_ids = await self.resolve(mentions, protocol_id)
        return await self.link_chunks(
            chunk_id, entity_ids, [m.confidence for m in mentions],
        )

    # ── Relationship linking ────────────────────────────

    async def resolve_relations(
        self,
        relations: list[RelationMention],
        protocol_id: int = 1,
    ) -> int:
        count = 0
        for rel in relations:
            sid = await self._resolve_one(
                protocol_id, rel.source_type_id, rel.source_name
            )
            tid = await self._resolve_one(
                protocol_id, rel.target_type_id, rel.target_name
            )
            if sid and tid:
                await self._graph.upsert_relationship(
                    source_id=sid, target_id=tid,
                    rel_type=rel.rel_type,
                    properties={"confidence": rel.confidence},
                )
                count += 1
        return count

    # ── Batch processing ────────────────────────────────

    async def batch_process(
        self,
        chunk_contents: list[tuple[UUID, str, str]],
        protocol_id: int = 1,
    ) -> dict[UUID, list[UUID]]:
        """Process chunks: regex extract → resolve → link. Returns chunk→entity map."""
        from rag_ocpp.knowledge.entities import extract_pattern_matches

        results: dict[UUID, list[UUID]] = {}
        for chunk_id, text, _ in chunk_contents:
            matches = extract_pattern_matches(text)
            seen: set[tuple[int, str]] = set()
            mentions: list[EntityMention] = []

            for m in matches:
                key = (m.entity_type.type_id, m.name)
                if key not in seen:
                    seen.add(key)
                    mentions.append(EntityMention(
                        type_id=m.entity_type.type_id,
                        name=m.name,
                        span_start=m.span_start,
                        span_end=m.span_end,
                        source="regex",
                    ))

            eids = await self.resolve(mentions, protocol_id)
            await self.link_chunks(
                chunk_id, eids, [m.confidence for m in mentions],
            )
            results[chunk_id] = eids

        return results

    # ── Internal ────────────────────────────────────────

    async def _resolve_one(
        self, protocol_id: int, type_id: int, name: str
    ) -> UUID:
        # 1. Exact match
        entity = await self._graph.find_entity(
            protocol_id=protocol_id, type_id=type_id, name=name,
        )
        if entity:
            return entity.id

        # 2. Alias match
        entity = await self._graph.find_entity_by_alias(
            protocol_id=protocol_id, alias=name,
        )
        if entity:
            return entity.id

        # 3. Fuzzy match
        candidates = await self._graph.find_entity_fuzzy(
            protocol_id=protocol_id, name=name,
            threshold=self._fuzzy_threshold, limit=3,
        )
        if candidates:
            return candidates[0].id

        # 4. Create new
        return await self._graph.upsert_entity(
            protocol_id=protocol_id, type_id=type_id, name=name,
        )
