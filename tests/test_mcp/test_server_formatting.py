"""MCP Markdown formatting contract tests."""

from __future__ import annotations

from uuid import UUID

from rag_ocpp.mcp.server import _format_chunk
from rag_ocpp.retrieval.searchers import ScoredChunk
from rag_ocpp.storage.graph import ChunkSemanticLink


def test_format_chunk_includes_ontology_semantic_links():
    chunk = ScoredChunk(
        chunk_id=UUID("11111111-1111-1111-1111-111111111111"),
        document_id=UUID("22222222-2222-2222-2222-222222222222"),
        chunk_index=0,
        content="Device Model variable evidence.",
        score=0.91,
        strategy="graph",
        section_title="Device Model",
        page_start=None,
        page_end=None,
        metadata={
            "evidence_layer": "device_model",
            "source_type": "device_model_table",
            "source_path": "data/csv/device_model.csv",
        },
    )
    link = ChunkSemanticLink(
        chunk_id=chunk.chunk_id,
        entity_name="ChargingStation",
        entity_type="component",
        rel_type="component_has_variable",
        direction="outgoing",
        related_entity_name="HeartbeatInterval",
        related_entity_type="variable",
        properties={
            "ontology_version": "ocpp21-ed2-v1",
            "mapping_rule": "dm_component_variable",
            "confidence": 0.98,
        },
    )

    rendered = _format_chunk(chunk, 1, max_chars=500, semantic_links=[link])

    assert "### Semantic Links" in rendered
    assert "`component_has_variable` outgoing" in rendered
    assert "`ChargingStation` (component)" in rendered
    assert "`HeartbeatInterval` (variable)" in rendered
    assert "ontology `ocpp21-ed2-v1`" in rendered
    assert "rule `dm_component_variable`" in rendered
