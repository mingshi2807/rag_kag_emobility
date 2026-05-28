"""Audit event storage tests."""

from __future__ import annotations

import json

from rag_ocpp.privacy import set_redaction_enabled
from rag_ocpp.storage.audit import AuditEvent, sensitive_text_ref


async def test_audit_event_stores_redacted_metadata_even_when_log_redaction_disabled(
    audit_store,
    pool,
):
    set_redaction_enabled(False)
    try:
        event_id = await audit_store.record(
            AuditEvent(
                event_type="generation.completed",
                surface="test",
                action="generate",
                resource_type="query",
                resource_id="abc",
                latency_ms=42,
                metadata={
                    "query": sensitive_text_ref("What is BootNotification?"),
                    "api_key": "sk-test-secret",
                    "payload": "Bearer sk-bearer " + ("private context " * 30),
                },
            )
        )
    finally:
        set_redaction_enabled(True)

    row = await pool.fetchrow("SELECT * FROM audit_events WHERE id=$1", event_id)

    assert row is not None
    assert row["event_type"] == "generation.completed"
    assert row["surface"] == "test"
    assert row["resource_type"] == "query"
    assert row["resource_id"] == "abc"
    assert row["latency_ms"] == 42
    metadata = row["metadata"]
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    assert metadata["query"]["length"] == len("What is BootNotification?")
    assert "What is BootNotification?" not in str(metadata)
    assert metadata["api_key"] == "[REDACTED]"
    assert "sk-test-secret" not in str(metadata)
    assert "private context" not in str(metadata)
    assert "[REDACTED_TEXT" in metadata["payload"]
