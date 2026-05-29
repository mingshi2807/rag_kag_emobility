"""Knowledge graph operations — entity CRUD, relationships, recursive traversal."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import asyncpg


def _json(v: Any) -> str | None:
    """Convert list/dict to JSON string for PostgreSQL JSONB columns."""
    if v is None:
        return None
    return json.dumps(v)


# ── Data types ────────────────────────────────────────────

@dataclass
class EntityRecord:
    """A knowledge graph entity (node)."""
    id: UUID
    type_id: int
    protocol_id: int
    name: str
    description: str | None = None
    aliases: list[str] | None = None
    properties: dict[str, Any] | None = None


@dataclass
class EntityMention:
    """An entity mention extracted from text, not yet resolved to an ID."""
    type_id: int
    name: str
    confidence: float = 1.0
    span_start: int | None = None
    span_end: int | None = None


@dataclass
class RelationshipRecord:
    """A knowledge graph relationship (edge)."""
    id: UUID
    source_id: UUID
    target_id: UUID
    rel_type: str
    properties: dict[str, Any] | None = None


@dataclass
class TraversalNode:
    """A node visited during graph traversal."""
    entity_id: UUID
    name: str
    type_name: str
    depth: int
    path: list[str] = field(default_factory=list)  # chain of entity names


@dataclass
class EntityChunkResult:
    """A chunk linked to an entity via the chunk_entities bridge."""
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    section_title: str | None
    page_start: int | None
    page_end: int | None
    entity_name: str
    entity_type: str
    confidence: float


# ── Store ─────────────────────────────────────────────────

class GraphStore:
    """Async PostgreSQL knowledge graph operations.

    Manages entities (nodes), relationships (edges), and the
    chunk_entities bridge table for the KAG pipeline.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Entity CRUD ──────────────────────────────────────

    async def upsert_entity(
        self,
        *,
        protocol_id: int,
        type_id: int,
        name: str,
        description: str | None = None,
        aliases: list[str] | None = None,
        properties: dict[str, Any] | None = None,
    ) -> UUID:
        """Insert or update an entity. Returns the entity UUID.

        If an entity with the same (protocol_id, type_id, name) already
        exists, its description/aliases/properties are merged.
        """
        row = await self._pool.fetchrow(
            """
            INSERT INTO entities (type_id, protocol_id, name, description, aliases, properties)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (protocol_id, type_id, name) DO UPDATE SET
                description = COALESCE(EXCLUDED.description, entities.description),
                aliases = COALESCE(EXCLUDED.aliases, entities.aliases),
                properties = COALESCE(EXCLUDED.properties, entities.properties)
            RETURNING id
            """,
            type_id, protocol_id, name, description, _json(aliases), _json(properties),
        )
        assert row is not None
        return row["id"]

    async def upsert_entities_batch(
        self, mentions: list[EntityMention], protocol_id: int
    ) -> list[UUID]:
        """Batch-upsert entities from extracted mentions.

        Returns the list of entity UUIDs in the same order as input.
        """
        ids: list[UUID] = []
        async with self._pool.acquire() as conn:
            for m in mentions:
                row = await conn.fetchrow(
                    """
                    INSERT INTO entities (type_id, protocol_id, name)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (protocol_id, type_id, name) DO NOTHING
                    RETURNING id
                    """,
                    m.type_id, protocol_id, m.name,
                )
                if row is not None:
                    ids.append(row["id"])
                else:
                    # Already exists — fetch the existing id
                    existing = await conn.fetchrow(
                        """
                        SELECT id FROM entities
                        WHERE protocol_id = $1 AND type_id = $2 AND name = $3
                        """,
                        protocol_id, m.type_id, m.name,
                    )
                    assert existing is not None
                    ids.append(existing["id"])
        return ids

    async def find_entity(
        self,
        *,
        protocol_id: int,
        type_id: int | None = None,
        name: str,
    ) -> EntityRecord | None:
        """Find an entity by protocol + type + name (exact match)."""
        if type_id is not None:
            row = await self._pool.fetchrow(
                """
                SELECT id, type_id, protocol_id, name, description, aliases, properties
                FROM entities
                WHERE protocol_id = $1 AND type_id = $2 AND name = $3
                """,
                protocol_id, type_id, name,
            )
        else:
            row = await self._pool.fetchrow(
                """
                SELECT id, type_id, protocol_id, name, description, aliases, properties
                FROM entities
                WHERE protocol_id = $1 AND name = $2
                """,
                protocol_id, name,
            )
        if row is None:
            return None
        return EntityRecord(
            id=row["id"],
            type_id=row["type_id"],
            protocol_id=row["protocol_id"],
            name=row["name"],
            description=row["description"],
            aliases=row["aliases"],
            properties=row["properties"],
        )

    async def find_entity_fuzzy(
        self,
        *,
        protocol_id: int,
        name: str,
        threshold: float = 0.3,
        limit: int = 10,
    ) -> list[EntityRecord]:
        """Find entities by pg_trgm fuzzy name matching."""
        rows = await self._pool.fetch(
            """
            SELECT id, type_id, protocol_id, name, description, aliases, properties,
                   similarity(name, $2) AS sim
            FROM entities
            WHERE protocol_id = $1
              AND similarity(name, $2) > $3
            ORDER BY sim DESC
            LIMIT $4
            """,
            protocol_id, name, threshold, limit,
        )
        return [
            EntityRecord(
                id=r["id"],
                type_id=r["type_id"],
                protocol_id=r["protocol_id"],
                name=r["name"],
                description=r["description"],
                aliases=r["aliases"],
                properties=r["properties"],
            )
            for r in rows
        ]

    async def find_entity_by_alias(
        self,
        *,
        protocol_id: int,
        alias: str,
    ) -> EntityRecord | None:
        """Find an entity whose aliases array contains the given string."""
        row = await self._pool.fetchrow(
            """
            SELECT id, type_id, protocol_id, name, description, aliases, properties
            FROM entities
            WHERE protocol_id = $1 AND $2 = ANY(aliases)
            LIMIT 1
            """,
            protocol_id, alias,
        )
        if row is None:
            return None
        return EntityRecord(
            id=row["id"],
            type_id=row["type_id"],
            protocol_id=row["protocol_id"],
            name=row["name"],
            description=row["description"],
            aliases=row["aliases"],
            properties=row["properties"],
        )

    async def get_entity(self, entity_id: UUID) -> EntityRecord | None:
        """Get a single entity by UUID."""
        row = await self._pool.fetchrow(
            """
            SELECT e.id, e.type_id, e.protocol_id, e.name,
                   e.description, e.aliases, e.properties,
                   et.name AS type_name
            FROM entities e
            JOIN entity_types et ON et.id = e.type_id AND et.protocol_id = e.protocol_id
            WHERE e.id = $1
            """,
            entity_id,
        )
        if row is None:
            return None
        return EntityRecord(
            id=row["id"],
            type_id=row["type_id"],
            protocol_id=row["protocol_id"],
            name=row["name"],
            description=row["description"],
            aliases=row["aliases"],
            properties=row["properties"],
        )

    # ── Relationship CRUD ──────────────────────────────

    async def upsert_relationship(
        self,
        *,
        source_id: UUID,
        target_id: UUID,
        rel_type: str,
        properties: dict[str, Any] | None = None,
        validate_ontology: bool = False,
        protocol_id: int = 1,
    ) -> UUID:
        """Create a relationship edge. No-op if (source, target, type) already exists."""
        if validate_ontology:
            await self._validate_relation_type(rel_type, protocol_id=protocol_id)
        row = await self._pool.fetchrow(
            """
            INSERT INTO relationships (source_id, target_id, rel_type, properties)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (source_id, target_id, rel_type) DO NOTHING
            RETURNING id
            """,
            source_id, target_id, rel_type, _json(properties),
        )
        if row is not None:
            return row["id"]
        # Already exists — fetch existing
        existing = await self._pool.fetchrow(
            """
            SELECT id FROM relationships
            WHERE source_id = $1 AND target_id = $2 AND rel_type = $3
            """,
            source_id, target_id, rel_type,
        )
        assert existing is not None
        return existing["id"]

    async def _validate_relation_type(self, rel_type: str, *, protocol_id: int) -> None:
        """Validate a relationship type when the ontology catalog is installed."""
        catalog = await self._pool.fetchval("SELECT to_regclass('ontology_relation_types')")
        if catalog is None:
            return
        row = await self._pool.fetchrow(
            """
            SELECT 1
            FROM ontology_relation_types rt
            JOIN ontology_versions ov
              ON ov.protocol_id = rt.protocol_id
             AND ov.version = rt.ontology_version
             AND ov.status = 'active'
            WHERE rt.protocol_id = $1 AND rt.name = $2
            LIMIT 1
            """,
            protocol_id,
            rel_type,
        )
        if row is None:
            raise ValueError(f"Relationship type is not in active ontology: {rel_type}")

    async def get_relationships(
        self,
        entity_id: UUID,
        *,
        direction: str = "both",  # "outgoing", "incoming", "both"
        rel_types: list[str] | None = None,
    ) -> list[RelationshipRecord]:
        """Get relationships for an entity."""
        type_clause = ""
        type_params: list[Any] = []
        if rel_types:
            type_clause = f"AND r.rel_type = ANY(${3 if direction == 'outgoing' else 3})"
            type_params = [rel_types]

        if direction == "outgoing":
            rows = await self._pool.fetch(
                f"""
                SELECT r.id, r.source_id, r.target_id, r.rel_type, r.properties
                FROM relationships r
                WHERE r.source_id = $1 {type_clause}
                """,
                entity_id, *type_params,
            )
        elif direction == "incoming":
            rows = await self._pool.fetch(
                f"""
                SELECT r.id, r.source_id, r.target_id, r.rel_type, r.properties
                FROM relationships r
                WHERE r.target_id = $1 {type_clause}
                """,
                entity_id, *type_params,
            )
        else:
            rows = await self._pool.fetch(
                f"""
                SELECT r.id, r.source_id, r.target_id, r.rel_type, r.properties
                FROM relationships r
                WHERE (r.source_id = $1 OR r.target_id = $1) {type_clause}
                """,
                entity_id, *type_params,
            )

        return [
            RelationshipRecord(
                id=r["id"],
                source_id=r["source_id"],
                target_id=r["target_id"],
                rel_type=r["rel_type"],
                properties=r["properties"],
            )
            for r in rows
        ]

    # ── Chunk–Entity Bridge ────────────────────────────

    async def link_chunk_entity(
        self,
        *,
        chunk_id: UUID,
        entity_id: UUID,
        confidence: float = 1.0,
        span_start: int | None = None,
        span_end: int | None = None,
    ) -> None:
        """Link a chunk to an entity (upsert — overwrites on conflict)."""
        await self._pool.execute(
            """
            INSERT INTO chunk_entities (chunk_id, entity_id, confidence, span_start, span_end)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (chunk_id, entity_id) DO UPDATE SET
                confidence = EXCLUDED.confidence,
                span_start = EXCLUDED.span_start,
                span_end = EXCLUDED.span_end
            """,
            chunk_id, entity_id, confidence, span_start, span_end,
        )

    async def get_chunks_for_entity(
        self, entity_id: UUID, *, top_k: int = 10
    ) -> list[EntityChunkResult]:
        """Retrieve chunks linked to a given entity, ordered by confidence."""
        rows = await self._pool.fetch(
            """
            SELECT c.id, c.document_id, c.chunk_index, c.content,
                   c.section_title, c.page_start, c.page_end,
                   e.name AS entity_name,
                   et.name AS entity_type,
                   ce.confidence
            FROM chunk_entities ce
            JOIN chunks c ON c.id = ce.chunk_id
            JOIN entities e ON e.id = ce.entity_id
            JOIN entity_types et ON et.id = e.type_id AND et.protocol_id = e.protocol_id
            WHERE ce.entity_id = $1
            ORDER BY ce.confidence DESC, c.chunk_index
            LIMIT $2
            """,
            entity_id, top_k,
        )
        return [
            EntityChunkResult(
                chunk_id=r["id"],
                document_id=r["document_id"],
                chunk_index=r["chunk_index"],
                content=r["content"],
                section_title=r["section_title"],
                page_start=r["page_start"],
                page_end=r["page_end"],
                entity_name=r["entity_name"],
                entity_type=r["entity_type"],
                confidence=float(r["confidence"]),
            )
            for r in rows
        ]

    # ── Recursive Graph Traversal ───────────────────────

    async def traverse(
        self,
        start_entity_id: UUID,
        *,
        rel_types: list[str] | None = None,
        max_depth: int = 3,
        follow_both_directions: bool = True,
    ) -> list[TraversalNode]:
        """Recursive CTE traversal from a starting entity.

        Returns all visited nodes with depth and path information.

        Example: traverse from "IdToken" entity, follow "uses" edges
        backward to find all commands that reference IdToken.
        """
        max_depth = max(0, min(int(max_depth), 5))
        params: list[Any] = [start_entity_id]
        type_filter = ""
        if rel_types:
            params.append(rel_types)
            type_filter = f"AND r.rel_type = ANY(${len(params)}::text[])"
        params.append(max_depth)
        depth_ref = f"${len(params)}"

        if follow_both_directions:
            join_clause = f"""
                SELECT e.id, e.name, et.name AS type_name, chain.depth + 1,
                       chain.path || e.name
                FROM entity_chain chain
                JOIN relationships r
                    ON r.source_id = chain.entity_id OR r.target_id = chain.entity_id
                JOIN entities e
                    ON e.id = CASE
                        WHEN r.source_id = chain.entity_id THEN r.target_id
                        ELSE r.source_id
                    END
                JOIN entity_types et
                    ON et.id = e.type_id AND et.protocol_id = e.protocol_id
                WHERE chain.depth < {depth_ref}
                {type_filter}
            """
        else:
            join_clause = f"""
                SELECT e.id, e.name, et.name AS type_name, chain.depth + 1,
                       chain.path || e.name
                FROM entity_chain chain
                JOIN relationships r ON r.source_id = chain.entity_id
                JOIN entities e ON e.id = r.target_id
                JOIN entity_types et
                    ON et.id = e.type_id AND et.protocol_id = e.protocol_id
                WHERE chain.depth < {depth_ref}
                {type_filter}
            """

        rows = await self._pool.fetch(
            f"""
            WITH RECURSIVE entity_chain AS (
                SELECT e.id AS entity_id, e.name,
                       et.name AS type_name,
                       0 AS depth,
                       ARRAY[e.name] AS path
                FROM entities e
                JOIN entity_types et
                    ON et.id = e.type_id AND et.protocol_id = e.protocol_id
                WHERE e.id = $1

                UNION ALL

                {join_clause}
            )
            SELECT DISTINCT ON (entity_id, depth) entity_id, name, type_name, depth, path
            FROM entity_chain
            ORDER BY entity_id, depth, path
            """,
            *params,
        )
        return [
            TraversalNode(
                entity_id=r["entity_id"],
                name=r["name"],
                type_name=r["type_name"],
                depth=r["depth"],
                path=list(r["path"]),
            )
            for r in rows
        ]

    async def traverse_by_name(
        self,
        *,
        protocol_id: int,
        entity_name: str,
        entity_type_id: int | None = None,
        rel_types: list[str] | None = None,
        max_depth: int = 3,
        follow_both_directions: bool = True,
    ) -> list[TraversalNode]:
        """Like traverse(), but resolves the starting entity by name first."""
        entity = await self.find_entity(
            protocol_id=protocol_id, type_id=entity_type_id, name=entity_name
        )
        if entity is None:
            return []
        return await self.traverse(
            start_entity_id=entity.id,
            rel_types=rel_types,
            max_depth=max_depth,
            follow_both_directions=follow_both_directions,
        )

    async def search_by_entity_names(
        self,
        *,
        protocol_id: int,
        entity_names: list[str],
        top_k: int = 10,
    ) -> list[EntityChunkResult]:
        """Find chunks linked to any of the given entity names.

        This is the primary graph-based retrieval entry point:
        given query-extracted entity names, return relevant chunks.
        """
        rows = await self._pool.fetch(
            """
            SELECT DISTINCT ON (c.id)
                   c.id, c.document_id, c.chunk_index, c.content,
                   c.section_title, c.page_start, c.page_end,
                   e.name AS entity_name,
                   et.name AS entity_type,
                   ce.confidence
            FROM entities e
            JOIN chunk_entities ce ON ce.entity_id = e.id
            JOIN chunks c ON c.id = ce.chunk_id
            JOIN entity_types et ON et.id = e.type_id AND et.protocol_id = e.protocol_id
            WHERE e.protocol_id = $1
              AND e.name = ANY($2::text[])
            ORDER BY c.id, ce.confidence DESC
            LIMIT $3
            """,
            protocol_id, entity_names, top_k,
        )
        return [
            EntityChunkResult(
                chunk_id=r["id"],
                document_id=r["document_id"],
                chunk_index=r["chunk_index"],
                content=r["content"],
                section_title=r["section_title"],
                page_start=r["page_start"],
                page_end=r["page_end"],
                entity_name=r["entity_name"],
                entity_type=r["entity_type"],
                confidence=float(r["confidence"]),
            )
            for r in rows
        ]

    # ── Query log ───────────────────────────────────────

    async def find_entity_names_by_terms(
        self, query: str, *, limit: int = 5, protocol_id: int | None = 1,
    ) -> list[str]:
        """Find entity names matching query substrings (ILIKE fallback for regex misses)."""
        words = [w for w in query.split() if len(w) > 2]
        if not words:
            return []
        params: list[Any] = []
        clauses = []
        for word in words[:4]:
            params.append(f"%{word}%")
            clauses.append(f"name ILIKE ${len(params)}")
        filters = [f"({' OR '.join(clauses)})"]
        if protocol_id is not None:
            params.append(protocol_id)
            filters.append(f"protocol_id = ${len(params)}")
        params.append(max(1, min(int(limit), 100)))
        rows = await self._pool.fetch(
            f"""
            SELECT name
            FROM entities
            WHERE {' AND '.join(filters)}
            ORDER BY name
            LIMIT ${len(params)}
            """,
            *params,
        )
        return [r["name"] for r in rows]

    async def record_query(
        self,
        *,
        query_text: str,
        top_chunks: list[str],
        top_scores: list[float],
        strategy: str = "hybrid",
        latency_ms: int,
    ) -> UUID:
        """Record a query for evaluation / observability."""
        row = await self._pool.fetchrow(
            """
            INSERT INTO query_log (query_text, top_chunks, top_scores, strategy, latency_ms)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            query_text, _json(top_chunks), _json(top_scores), strategy, latency_ms,
        )
        assert row is not None
        return row["id"]
