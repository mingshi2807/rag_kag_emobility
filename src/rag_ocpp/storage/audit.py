"""Audit event storage for private knowledge operations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import asyncpg

from rag_ocpp.privacy import redact_value


def text_sha256(text: str) -> str:
    """Return a stable digest for sensitive text without storing the text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sensitive_text_ref(text: str) -> dict[str, Any]:
    """Return non-reversible metadata for a sensitive text value."""
    return {"sha256": text_sha256(text), "length": len(text)}


@dataclass
class AuditEvent:
    """A privacy-preserving audit event."""

    event_type: str
    surface: str
    action: str
    status: str = "success"
    actor_id: str | None = None
    session_id: str | None = None
    correlation_id: str | None = None
    resource_type: str | None = None
    resource_id: str | UUID | None = None
    latency_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditStore:
    """Async PostgreSQL adapter for enterprise audit events."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def record(self, event: AuditEvent) -> UUID:
        """Insert an audit event and return its UUID.

        Audit metadata is force-redacted independently of the log redaction
        debug switch. Audit tables should never store raw prompts, chunks,
        generated answers, secrets, or full query text.
        """
        row = await self._pool.fetchrow(
            """
            INSERT INTO audit_events
                (event_type, surface, action, status, actor_id, session_id,
                 correlation_id, resource_type, resource_id, latency_ms, metadata)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            RETURNING id
            """,
            event.event_type,
            event.surface,
            event.action,
            event.status,
            event.actor_id,
            event.session_id,
            event.correlation_id,
            event.resource_type,
            str(event.resource_id) if event.resource_id is not None else None,
            event.latency_ms,
            _json(redact_value(event.metadata, force=True)),
        )
        assert row is not None
        return row["id"]


def _json(value: Any) -> str:
    return json.dumps(value, default=str)
