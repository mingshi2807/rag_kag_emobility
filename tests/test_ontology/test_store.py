"""Tests for the source-aware ontology catalog."""

from __future__ import annotations

import json
import uuid

from rag_ocpp.corpus.indexer import CorpusIndexer
from rag_ocpp.ontology.store import OntologyStore
from rag_ocpp.storage.vector import ChunkInsert


async def test_ontology_seed_loads_idempotently(pool):
    store = OntologyStore(pool)

    first = await store.load_seed()
    second = await store.load_seed()
    status = await store.status()
    rel = await store.resolve_relation(
        record_type="dm_component_variable",
        source_type="device_model_table",
        evidence_layer="device_model",
        preferred_rule="dm_component_variable",
    )

    assert first.version == "ocpp21-ed2-v1"
    assert second.mapping_rules == first.mapping_rules
    assert status.version == "ocpp21-ed2-v1"
    assert status.relation_types >= 10
    assert status.mapping_rules >= 6
    assert rel is not None
    assert rel.name == "component_has_variable"
    assert rel.mapping_rule == "dm_component_variable"


async def test_graph_validation_rejects_unknown_relation(graph_store, pool):
    await OntologyStore(pool).load_seed()
    source = await graph_store.upsert_entity(
        protocol_id=1,
        type_id=16,
        name="source:test",
    )
    target = await graph_store.upsert_entity(
        protocol_id=1,
        type_id=4,
        name="HeartbeatInterval",
    )

    try:
        await graph_store.upsert_relationship(
            source_id=source,
            target_id=target,
            rel_type="unknown_relation",
            validate_ontology=True,
        )
    except ValueError as exc:
        assert "not in active ontology" in str(exc)
    else:
        raise AssertionError("unknown ontology relation was accepted")


async def test_relationship_upsert_merges_ontology_properties(graph_store, pool):
    await OntologyStore(pool).load_seed()
    source = await graph_store.upsert_entity(
        protocol_id=1,
        type_id=3,
        name="ChargingStation",
    )
    target = await graph_store.upsert_entity(
        protocol_id=1,
        type_id=4,
        name="HeartbeatInterval",
    )

    relationship_id = await graph_store.upsert_relationship(
        source_id=source,
        target_id=target,
        rel_type="component_has_variable",
        properties={"legacy": True},
        validate_ontology=True,
    )
    updated_id = await graph_store.upsert_relationship(
        source_id=source,
        target_id=target,
        rel_type="component_has_variable",
        properties={
            "ontology_version": "ocpp21-ed2-v1",
            "mapping_rule": "dm_component_variable",
        },
        validate_ontology=True,
    )
    rels = await graph_store.get_relationships(source, direction="outgoing")

    assert updated_id == relationship_id
    assert len(rels) == 1
    props = rels[0].properties
    if isinstance(props, str):
        props = json.loads(props)
    assert props["legacy"] is True
    assert props["ontology_version"] == "ocpp21-ed2-v1"
    assert props["mapping_rule"] == "dm_component_variable"


async def test_semantic_links_for_chunks_include_ontology_properties(
    graph_store, vector_store, pool
):
    await OntologyStore(pool).load_seed()
    doc_id = await vector_store.insert_document(
        protocol_id=1,
        source_path="corpus:test",
        doc_type="other",
        title="test",
    )
    chunk_id = uuid.uuid4()
    await vector_store.insert_chunks([
        ChunkInsert(
            id=chunk_id,
            document_id=doc_id,
            chunk_index=0,
            content="Component: ChargingStation. Variable: HeartbeatInterval.",
            content_hash="semantic-link-test",
            strategy="corpus_record",
        )
    ])
    component = await graph_store.upsert_entity(
        protocol_id=1,
        type_id=3,
        name="ChargingStation",
    )
    variable = await graph_store.upsert_entity(
        protocol_id=1,
        type_id=4,
        name="HeartbeatInterval",
    )
    await graph_store.link_chunk_entity(chunk_id=chunk_id, entity_id=variable)
    await graph_store.upsert_relationship(
        source_id=component,
        target_id=variable,
        rel_type="component_has_variable",
        properties={
            "ontology_version": "ocpp21-ed2-v1",
            "mapping_rule": "dm_component_variable",
            "confidence": 0.98,
        },
        validate_ontology=True,
    )

    links = await graph_store.get_semantic_links_for_chunks([chunk_id])

    assert chunk_id in links
    assert links[chunk_id][0].rel_type == "component_has_variable"
    assert links[chunk_id][0].direction == "incoming"
    assert links[chunk_id][0].entity_name == "HeartbeatInterval"
    assert links[chunk_id][0].related_entity_name == "ChargingStation"
    props = links[chunk_id][0].properties
    if isinstance(props, str):
        props = json.loads(props)
    assert props["ontology_version"] == "ocpp21-ed2-v1"
    assert props["mapping_rule"] == "dm_component_variable"


async def test_corpus_indexer_adds_ontology_provenance(pool):
    await OntologyStore(pool).load_seed()
    source_id = uuid.uuid4()
    record_id = uuid.uuid4()
    source = {
        "id": source_id,
        "protocol_id": 1,
        "source_type": "device_model_table",
        "source_path": "data/csv/dm_components_vars.csv",
        "title": "dm_components_vars",
        "version": "2.1",
        "raw_bytes": 128,
        "content_hash": "source-hash",
        "metadata": {"evidence_layer": "device_model"},
    }
    records = [
        {
            "id": record_id,
            "source_document_id": source_id,
            "record_type": "dm_component_variable",
            "stable_key": "dm:ChargingStation:HeartbeatInterval",
            "title": "ChargingStation / HeartbeatInterval",
            "content": "Component: ChargingStation. Variable: HeartbeatInterval.",
            "content_hash": "record-hash",
            "page_start": None,
            "page_end": None,
            "row_number": 1,
            "section_title": None,
            "entity_name": "HeartbeatInterval",
            "entity_type": "variable",
            "metadata": {
                "source_type": "device_model_table",
                "evidence_layer": "device_model",
                "specific_component": "ChargingStation",
                "variable": "HeartbeatInterval",
                "required": "yes",
                "datatype": "integer",
                "unit": "s",
            },
        }
    ]

    result = await CorpusIndexer(pool, None).index_source(
        source,
        records,
        embed=False,
    )
    rows = await pool.fetch(
        """
        SELECT rel_type, properties
        FROM relationships
        WHERE rel_type IN ('dm_defines_entity', 'component_has_variable')
        ORDER BY rel_type
        """
    )

    assert result.entities_linked == 1
    assert result.relationships_created == 2
    assert {row["rel_type"] for row in rows} == {
        "component_has_variable",
        "dm_defines_entity",
    }
    by_type = {
        row["rel_type"]: (
            json.loads(row["properties"])
            if isinstance(row["properties"], str)
            else row["properties"]
        )
        for row in rows
    }
    assert by_type["component_has_variable"]["ontology_version"] == "ocpp21-ed2-v1"
    assert by_type["component_has_variable"]["mapping_rule"] == "dm_component_variable"
    assert by_type["dm_defines_entity"]["mapping_rule"] == "source_dm_records"
