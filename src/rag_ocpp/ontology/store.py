"""PostgreSQL-backed lightweight ontology catalog."""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncpg
from omegaconf import OmegaConf

DEFAULT_ONTOLOGY_PATH = Path(__file__).with_name("ocpp21_ed2.yaml")


def _json(value: Any) -> str:
    return json.dumps(value or {})


@dataclass(frozen=True)
class OntologyStatus:
    """Summary of loaded ontology catalog content."""

    protocol_id: int
    version: str | None
    versions: int = 0
    entity_classes: int = 0
    relation_types: int = 0
    evidence_layers: int = 0
    source_types: int = 0
    mapping_rules: int = 0


@dataclass(frozen=True)
class OntologyRelation:
    """A relation definition resolved from the ontology catalog."""

    name: str
    ontology_version: str
    label: str | None = None
    confidence: float = 1.0
    mapping_rule: str | None = None
    evidence_layer: str | None = None
    source_type: str | None = None

    def properties(
        self,
        *,
        source_record_id: str | None = None,
        stable_key: str | None = None,
        record_type: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return relationship provenance properties."""
        props = {
            "ontology_version": self.ontology_version,
            "ontology_relation": self.name,
            "mapping_rule": self.mapping_rule,
            "evidence_layer": self.evidence_layer,
            "source_type": self.source_type,
            "confidence": self.confidence,
        }
        if source_record_id is not None:
            props["corpus_record_id"] = source_record_id
        if stable_key is not None:
            props["stable_key"] = stable_key
        if record_type is not None:
            props["record_type"] = record_type
        if extra:
            props.update(extra)
        return {k: v for k, v in props.items() if v is not None}


class OntologyStore:
    """Load and query a lightweight ontology catalog."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def load_seed(
        self,
        path: Path = DEFAULT_ONTOLOGY_PATH,
        *,
        dry_run: bool = False,
    ) -> OntologyStatus:
        """Load ontology definitions from YAML into the database."""
        data = _load_yaml(path)
        version = str(data["version"])
        protocol_id = int(data.get("protocol_id", 1))
        status = str(data.get("status", "active"))

        summary = OntologyStatus(
            protocol_id=protocol_id,
            version=version,
            versions=1,
            entity_classes=len(data.get("entity_classes", [])),
            relation_types=len(data.get("relation_types", [])),
            evidence_layers=len(data.get("evidence_layers", [])),
            source_types=len(data.get("source_types", [])),
            mapping_rules=len(data.get("mapping_rules", [])),
        )
        if dry_run:
            return summary

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO ontology_versions
                        (protocol_id, version, status, description, properties)
                    VALUES ($1,$2,$3,$4,$5)
                    ON CONFLICT (protocol_id, version) DO UPDATE SET
                        status = EXCLUDED.status,
                        description = EXCLUDED.description,
                        properties = EXCLUDED.properties
                    """,
                    protocol_id,
                    version,
                    status,
                    data.get("description"),
                    _json(data.get("properties")),
                )
                await self._upsert_evidence_layers(conn, protocol_id, version, data)
                await self._upsert_source_types(conn, protocol_id, version, data)
                await self._upsert_entity_classes(conn, protocol_id, version, data)
                await self._upsert_relation_types(conn, protocol_id, version, data)
                await self._upsert_mapping_rules(conn, protocol_id, version, data)

        return summary

    async def status(self, *, protocol_id: int = 1) -> OntologyStatus:
        """Return loaded ontology catalog counts."""
        row = await self._pool.fetchrow(
            """
            SELECT
              (SELECT count(*) FROM ontology_versions WHERE protocol_id = $1) AS versions,
              (SELECT version FROM ontology_versions
                 WHERE protocol_id = $1 AND status = 'active'
                 ORDER BY created_at DESC LIMIT 1) AS active_version,
              (SELECT count(*) FROM ontology_entity_classes WHERE protocol_id = $1)
                AS entity_classes,
              (SELECT count(*) FROM ontology_relation_types WHERE protocol_id = $1)
                AS relation_types,
              (SELECT count(*) FROM ontology_evidence_layers WHERE protocol_id = $1)
                AS evidence_layers,
              (SELECT count(*) FROM ontology_source_types WHERE protocol_id = $1)
                AS source_types,
              (SELECT count(*) FROM ontology_mapping_rules WHERE protocol_id = $1)
                AS mapping_rules
            """,
            protocol_id,
        )
        assert row is not None
        return OntologyStatus(
            protocol_id=protocol_id,
            version=row["active_version"],
            versions=row["versions"],
            entity_classes=row["entity_classes"],
            relation_types=row["relation_types"],
            evidence_layers=row["evidence_layers"],
            source_types=row["source_types"],
            mapping_rules=row["mapping_rules"],
        )

    async def active_version(self, *, protocol_id: int = 1) -> str | None:
        """Return the active ontology version for a protocol."""
        row = await self._pool.fetchrow(
            """
            SELECT version
            FROM ontology_versions
            WHERE protocol_id = $1 AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            protocol_id,
        )
        return None if row is None else row["version"]

    async def relation_exists(
        self,
        rel_type: str,
        *,
        protocol_id: int = 1,
        ontology_version: str | None = None,
    ) -> bool:
        """Return whether the relation type exists in the ontology catalog."""
        version = ontology_version or await self.active_version(protocol_id=protocol_id)
        if version is None:
            return False
        row = await self._pool.fetchrow(
            """
            SELECT 1
            FROM ontology_relation_types
            WHERE protocol_id = $1 AND ontology_version = $2 AND name = $3
            """,
            protocol_id,
            version,
            rel_type,
        )
        return row is not None

    async def resolve_relation(
        self,
        *,
        record_type: str,
        source_type: str | None = None,
        evidence_layer: str | None = None,
        preferred_rule: str | None = None,
        protocol_id: int = 1,
    ) -> OntologyRelation | None:
        """Resolve the best relation type for a corpus mapping rule."""
        version = await self.active_version(protocol_id=protocol_id)
        if version is None:
            return None

        rows = await self._pool.fetch(
            """
            SELECT mr.name AS mapping_rule, mr.relation_type, mr.source_type,
                   mr.evidence_layer, mr.record_type_pattern, mr.confidence,
                   rt.label
            FROM ontology_mapping_rules mr
            JOIN ontology_relation_types rt
              ON rt.protocol_id = mr.protocol_id
             AND rt.ontology_version = mr.ontology_version
             AND rt.name = mr.relation_type
            WHERE mr.protocol_id = $1
              AND mr.ontology_version = $2
              AND ($3::text IS NULL OR mr.name = $3)
            ORDER BY mr.name
            """,
            protocol_id,
            version,
            preferred_rule,
        )
        candidates = [dict(row) for row in rows]
        candidates.sort(
            key=lambda row: _match_score(
                row,
                record_type=record_type,
                source_type=source_type,
                evidence_layer=evidence_layer,
            ),
            reverse=True,
        )
        for row in candidates:
            if _match_score(
                row,
                record_type=record_type,
                source_type=source_type,
                evidence_layer=evidence_layer,
            ) > 0:
                return OntologyRelation(
                    name=row["relation_type"],
                    ontology_version=version,
                    label=row["label"],
                    confidence=float(row["confidence"] or 1.0),
                    mapping_rule=row["mapping_rule"],
                    evidence_layer=row["evidence_layer"],
                    source_type=row["source_type"],
                )
        return None

    async def _upsert_evidence_layers(
        self, conn: asyncpg.Connection, protocol_id: int, version: str, data: dict[str, Any]
    ) -> None:
        for item in data.get("evidence_layers", []):
            await conn.execute(
                """
                INSERT INTO ontology_evidence_layers
                    (protocol_id, ontology_version, name, description, properties)
                VALUES ($1,$2,$3,$4,$5)
                ON CONFLICT (protocol_id, ontology_version, name) DO UPDATE SET
                    description = EXCLUDED.description,
                    properties = EXCLUDED.properties
                """,
                protocol_id, version, item["name"], item.get("description"),
                _json(item.get("properties")),
            )

    async def _upsert_source_types(
        self, conn: asyncpg.Connection, protocol_id: int, version: str, data: dict[str, Any]
    ) -> None:
        for item in data.get("source_types", []):
            await conn.execute(
                """
                INSERT INTO ontology_source_types
                    (protocol_id, ontology_version, name, evidence_layer,
                     description, properties)
                VALUES ($1,$2,$3,$4,$5,$6)
                ON CONFLICT (protocol_id, ontology_version, name) DO UPDATE SET
                    evidence_layer = EXCLUDED.evidence_layer,
                    description = EXCLUDED.description,
                    properties = EXCLUDED.properties
                """,
                protocol_id, version, item["name"], item["evidence_layer"],
                item.get("description"), _json(item.get("properties")),
            )

    async def _upsert_entity_classes(
        self, conn: asyncpg.Connection, protocol_id: int, version: str, data: dict[str, Any]
    ) -> None:
        for item in data.get("entity_classes", []):
            await conn.execute(
                """
                INSERT INTO ontology_entity_classes
                    (protocol_id, ontology_version, name, label, description,
                     parent_name, properties)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                ON CONFLICT (protocol_id, ontology_version, name) DO UPDATE SET
                    label = EXCLUDED.label,
                    description = EXCLUDED.description,
                    parent_name = EXCLUDED.parent_name,
                    properties = EXCLUDED.properties
                """,
                protocol_id, version, item["name"], item.get("label"),
                item.get("description"), item.get("parent_name"),
                _json(item.get("properties")),
            )

    async def _upsert_relation_types(
        self, conn: asyncpg.Connection, protocol_id: int, version: str, data: dict[str, Any]
    ) -> None:
        for item in data.get("relation_types", []):
            await conn.execute(
                """
                INSERT INTO ontology_relation_types
                    (protocol_id, ontology_version, name, label, description,
                     source_class, target_class, inverse_name, is_transitive,
                     is_symmetric, properties)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (protocol_id, ontology_version, name) DO UPDATE SET
                    label = EXCLUDED.label,
                    description = EXCLUDED.description,
                    source_class = EXCLUDED.source_class,
                    target_class = EXCLUDED.target_class,
                    inverse_name = EXCLUDED.inverse_name,
                    is_transitive = EXCLUDED.is_transitive,
                    is_symmetric = EXCLUDED.is_symmetric,
                    properties = EXCLUDED.properties
                """,
                protocol_id, version, item["name"], item.get("label"),
                item.get("description"), item.get("source_class"),
                item.get("target_class"), item.get("inverse_name"),
                bool(item.get("is_transitive", False)),
                bool(item.get("is_symmetric", False)),
                _json(item.get("properties")),
            )

    async def _upsert_mapping_rules(
        self, conn: asyncpg.Connection, protocol_id: int, version: str, data: dict[str, Any]
    ) -> None:
        for item in data.get("mapping_rules", []):
            await conn.execute(
                """
                INSERT INTO ontology_mapping_rules
                    (protocol_id, ontology_version, name, relation_type, source_type,
                     evidence_layer, record_type_pattern, description, confidence,
                     properties)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                ON CONFLICT (protocol_id, ontology_version, name) DO UPDATE SET
                    relation_type = EXCLUDED.relation_type,
                    source_type = EXCLUDED.source_type,
                    evidence_layer = EXCLUDED.evidence_layer,
                    record_type_pattern = EXCLUDED.record_type_pattern,
                    description = EXCLUDED.description,
                    confidence = EXCLUDED.confidence,
                    properties = EXCLUDED.properties
                """,
                protocol_id, version, item["name"], item["relation_type"],
                item.get("source_type"), item.get("evidence_layer"),
                item.get("record_type_pattern"), item.get("description"),
                float(item.get("confidence", 1.0)),
                _json(item.get("properties")),
            )


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
    if not isinstance(raw, dict):
        raise ValueError(f"Ontology seed must be a mapping: {path}")
    for key in ("version", "entity_classes", "relation_types", "mapping_rules"):
        if key not in raw:
            raise ValueError(f"Ontology seed missing required key '{key}': {path}")
    return raw


def _match_score(
    row: dict[str, Any],
    *,
    record_type: str,
    source_type: str | None,
    evidence_layer: str | None,
) -> int:
    score = 0
    pattern = row.get("record_type_pattern")
    if pattern:
        if not fnmatch.fnmatch(record_type, pattern):
            return 0
        score += 1 if pattern == "*" else 3
    if row.get("source_type"):
        if row["source_type"] != source_type:
            return 0
        score += 2
    if row.get("evidence_layer"):
        if row["evidence_layer"] != evidence_layer:
            return 0
        score += 2
    return score
