-- Source-aware ontology catalog for validated graph semantics.
-- The ontology defines allowed semantic classes, relation types, and mapping
-- rules; the existing entities/relationships tables remain the runtime graph.

CREATE TABLE IF NOT EXISTS ontology_versions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    protocol_id     SMALLINT NOT NULL REFERENCES protocols(id),
    version         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'draft', 'retired')),
    description     TEXT,
    properties      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT now(),

    UNIQUE(protocol_id, version)
);

CREATE TABLE IF NOT EXISTS ontology_entity_classes (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    protocol_id         SMALLINT NOT NULL REFERENCES protocols(id),
    ontology_version    TEXT NOT NULL,
    name                TEXT NOT NULL,
    label               TEXT,
    description         TEXT,
    parent_name         TEXT,
    properties          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ DEFAULT now(),

    UNIQUE(protocol_id, ontology_version, name)
);

CREATE TABLE IF NOT EXISTS ontology_relation_types (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    protocol_id         SMALLINT NOT NULL REFERENCES protocols(id),
    ontology_version    TEXT NOT NULL,
    name                TEXT NOT NULL,
    label               TEXT,
    description         TEXT,
    source_class        TEXT,
    target_class        TEXT,
    inverse_name        TEXT,
    is_transitive          BOOLEAN NOT NULL DEFAULT false,
    is_symmetric           BOOLEAN NOT NULL DEFAULT false,
    properties          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ DEFAULT now(),

    UNIQUE(protocol_id, ontology_version, name)
);

CREATE TABLE IF NOT EXISTS ontology_evidence_layers (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    protocol_id         SMALLINT NOT NULL REFERENCES protocols(id),
    ontology_version    TEXT NOT NULL,
    name                TEXT NOT NULL,
    description         TEXT,
    properties          JSONB NOT NULL DEFAULT '{}'::jsonb,

    UNIQUE(protocol_id, ontology_version, name)
);

CREATE TABLE IF NOT EXISTS ontology_source_types (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    protocol_id         SMALLINT NOT NULL REFERENCES protocols(id),
    ontology_version    TEXT NOT NULL,
    name                TEXT NOT NULL,
    evidence_layer      TEXT NOT NULL,
    description         TEXT,
    properties          JSONB NOT NULL DEFAULT '{}'::jsonb,

    UNIQUE(protocol_id, ontology_version, name)
);

CREATE TABLE IF NOT EXISTS ontology_mapping_rules (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    protocol_id         SMALLINT NOT NULL REFERENCES protocols(id),
    ontology_version    TEXT NOT NULL,
    name                TEXT NOT NULL,
    relation_type       TEXT NOT NULL,
    source_type         TEXT,
    evidence_layer      TEXT,
    record_type_pattern TEXT,
    description         TEXT,
    confidence          REAL NOT NULL DEFAULT 1.0,
    properties          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ DEFAULT now(),

    UNIQUE(protocol_id, ontology_version, name)
);

CREATE INDEX IF NOT EXISTS ontology_entity_classes_lookup
    ON ontology_entity_classes(protocol_id, ontology_version, name);
CREATE INDEX IF NOT EXISTS ontology_relation_types_lookup
    ON ontology_relation_types(protocol_id, ontology_version, name);
CREATE INDEX IF NOT EXISTS ontology_mapping_rules_lookup
    ON ontology_mapping_rules(protocol_id, ontology_version, relation_type);
CREATE INDEX IF NOT EXISTS ontology_mapping_rules_record_type
    ON ontology_mapping_rules(protocol_id, record_type_pattern);
