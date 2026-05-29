# Source-Aware Ontology Layer

This project now has a lightweight ontology catalog for OCPP 2.1 Ed2 graph
semantics. The ontology does not replace the knowledge graph. It defines the
allowed semantic classes, relation types, evidence layers, source types, and
mapping rules used to create graph relationships.

## Purpose

- Make graph edges explainable: each ontology-driven relationship records the
  ontology version, mapping rule, evidence layer, source type, confidence,
  stable key, and corpus record ID.
- Improve spec / Device Model / JSON schema fusion by using controlled relation
  names instead of ungoverned string literals.
- Prepare future protocol support without adopting RDF/OWL complexity yet.

## Operator Flow

Apply migrations, then load the default ontology seed:

```bash
.venv/bin/rag migrate
.venv/bin/rag ontology-load --dry-run
.venv/bin/rag ontology-load
.venv/bin/rag ontology-status
```

`rag index-corpus` auto-loads the default seed when ontology tables exist but no
active ontology version is present.

## Retrieval Provenance

FastAPI query/search responses and MCP evidence-pack outputs now expose semantic
links for retrieved chunks when the chunk is connected to graph entities. These
links are compact ontology-backed explanations, not extra private source text.

FastAPI `sources[]` / `results[]` include a `semantic_links` array with fields
such as:

```json
{
  "entity_name": "ChargingStation",
  "entity_type": "component",
  "rel_type": "component_has_variable",
  "direction": "outgoing",
  "related_entity_name": "HeartbeatInterval",
  "related_entity_type": "variable",
  "ontology_version": "ocpp21-ed2-v1",
  "mapping_rule": "dm_component_variable",
  "evidence_layer": "device_model",
  "source_type": "device_model_table",
  "confidence": 0.98
}
```

MCP `search_ocpp_knowledge`, `get_ocpp_evidence_pack`, and
`build_ocpp_implementation_brief` render the same relation provenance under
`Semantic Links` in Markdown. Coding agents should use this block to explain why
a spec, Device Model, or schema chunk is semantically connected to another OCPP
entity.

Graph retrieval also consumes the ontology catalog:

- Traversal uses active ontology relation types when the catalog is loaded.
- Non-ontology relationship strings are ignored by ontology-aware traversal.
- Graph hits with ontology provenance receive a small deterministic score boost.
- Graph-hit metadata records semantic-link count, ontology versions, relation
  names, and mapping rules.

This is intentionally conservative. Ontology provenance can change graph hit
ordering, but it does not override vector/keyword/reranker evidence by itself.

## Current OCPP Relations

The first seed is `ocpp21-ed2-v1` and includes these active graph relations:

- `spec_defines_entity`
- `dm_defines_entity`
- `schema_defines_entity`
- `component_has_variable`
- `message_has_field`
- `schema_validates_message`
- `field_uses_datatype`
- `requirement_constrains_entity`
- `section_describes_feature`
- `protocol_equivalent_to`

The indexer currently uses ontology rules for source-definition links,
Device Model `component_has_variable` links, and JSON schema
`message_has_field` links.

## Extension Rule

Add future protocol semantics by creating a new ontology seed/version and a new
migration only when schema changes are needed. Do not introduce new graph
relationship strings in indexing or retrieval code without adding them to the
ontology catalog and tests.
