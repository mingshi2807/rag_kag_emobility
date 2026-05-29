"""Graph retrieval tests for ontology-aware scoring and traversal."""

from __future__ import annotations

import uuid

from rag_ocpp.ontology.store import OntologyStore
from rag_ocpp.retrieval.graph_search import GraphSearcher
from rag_ocpp.storage.vector import ChunkInsert


async def test_graph_search_boosts_chunks_with_ontology_provenance(
    pool, graph_store, vector_store
):
    await OntologyStore(pool).load_seed()
    doc_id = await vector_store.insert_document(
        protocol_id=1,
        source_path="data/csv/device_model.csv",
        doc_type="device_model",
        title="Device Model",
    )
    charging_chunk = uuid.uuid4()
    connector_chunk = uuid.uuid4()
    await vector_store.insert_chunks(
        [
            ChunkInsert(
                id=charging_chunk,
                document_id=doc_id,
                chunk_index=0,
                content="ChargingStation has HeartbeatInterval.",
                content_hash="charging-station",
                strategy="corpus_record",
                metadata={"evidence_layer": "device_model"},
            ),
            ChunkInsert(
                id=connector_chunk,
                document_id=doc_id,
                chunk_index=1,
                content="Connector has no ontology provenance in this fixture.",
                content_hash="connector",
                strategy="corpus_record",
                metadata={"evidence_layer": "device_model"},
            ),
        ]
    )
    charging_station = await graph_store.upsert_entity(
        protocol_id=1, type_id=3, name="ChargingStation"
    )
    connector = await graph_store.upsert_entity(
        protocol_id=1, type_id=3, name="Connector"
    )
    heartbeat = await graph_store.upsert_entity(
        protocol_id=1, type_id=4, name="HeartbeatInterval"
    )
    await graph_store.link_chunk_entity(
        chunk_id=charging_chunk, entity_id=charging_station, confidence=0.9
    )
    await graph_store.link_chunk_entity(
        chunk_id=connector_chunk, entity_id=connector, confidence=0.9
    )
    await graph_store.upsert_relationship(
        source_id=charging_station,
        target_id=heartbeat,
        rel_type="component_has_variable",
        properties={
            "ontology_version": "ocpp21-ed2-v1",
            "mapping_rule": "dm_component_variable",
            "confidence": 0.98,
        },
        validate_ontology=True,
    )

    results = await GraphSearcher(pool).search(
        "ChargingStation Connector",
        top_k=2,
        ontology_aware=True,
    )

    assert [chunk.chunk_id for chunk in results] == [charging_chunk, connector_chunk]
    assert results[0].score > results[1].score
    assert results[0].metadata is not None
    assert results[0].metadata["graph_semantic_links"] == 1
    assert results[0].metadata["graph_ontology_rules"] == ["dm_component_variable"]


async def test_ontology_aware_traversal_uses_active_relation_types(
    pool, graph_store, vector_store
):
    await OntologyStore(pool).load_seed()
    doc_id = await vector_store.insert_document(
        protocol_id=1,
        source_path="data/csv/device_model.csv",
        doc_type="device_model",
        title="Device Model",
    )
    variable_chunk = uuid.uuid4()
    await vector_store.insert_chunks(
        [
            ChunkInsert(
                id=variable_chunk,
                document_id=doc_id,
                chunk_index=0,
                content="PrivateVariable is linked through a non-ontology edge.",
                content_hash="private-variable",
                strategy="corpus_record",
            )
        ]
    )
    charging_station = await graph_store.upsert_entity(
        protocol_id=1, type_id=3, name="ChargingStation"
    )
    private_variable = await graph_store.upsert_entity(
        protocol_id=1, type_id=4, name="PrivateVariable"
    )
    await graph_store.link_chunk_entity(
        chunk_id=variable_chunk, entity_id=private_variable, confidence=1.0
    )
    await graph_store.upsert_relationship(
        source_id=charging_station,
        target_id=private_variable,
        rel_type="private_non_ontology_edge",
        properties={"confidence": 1.0},
        validate_ontology=False,
    )

    searcher = GraphSearcher(pool)
    ontology_results = await searcher.search(
        "ChargingStation",
        top_k=1,
        expand_via_traversal=True,
        ontology_aware=True,
    )
    legacy_results = await searcher.search(
        "ChargingStation",
        top_k=1,
        expand_via_traversal=True,
        ontology_aware=False,
    )

    assert ontology_results == []
    assert [chunk.chunk_id for chunk in legacy_results] == [variable_chunk]
