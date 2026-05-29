# OCPP 2.1 Ed2 Ontology Benchmark

Date: 2026-05-29

## Purpose

Compare the current RAG/KAG backend behavior before and after adding the
lightweight source-aware ontology catalog.

This benchmark focuses on the first ontology milestone:

- Retrieval regression risk.
- Ontology catalog availability.
- Graph semantic governance.
- Current limitation before a full ontology-aware reindex.

## Method

Baseline without ontology:

- Existing full corpus DB before applying migration `003_ontology_catalog`.
- Existing report: `reports/ocpp21-ed2-rqk-quality-baseline.md`.
- Pre-migration state:
  - `003 ontology_catalog: pending`
  - `relationships: 4270`
  - `entity_links: 4658`
  - `embedded_corpus_chunks: 4884`

Run with ontology:

```bash
.venv/bin/rag migrate
.venv/bin/rag ontology-load --dry-run
.venv/bin/rag ontology-load
HF_HOME=./models .venv/bin/rag eval-quality --top-k 12 --fail-under 0.80 \
  --output reports/ocpp21-ed2-rqk-quality-with-ontology.md
```

## Results

| Metric | Without ontology | With ontology | Delta |
| --- | ---: | ---: | ---: |
| Retrieval cases passed | 12/12 | 12/12 | 0 |
| Retrieval score | 0.976 | 0.976 | 0.000 |
| Fail-under | 0.800 | 0.800 | 0 |
| Total measured latency | 166080 ms | 168703 ms | +2623 ms |
| Average latency per case | 13840 ms | 14059 ms | +219 ms |
| Ontology versions loaded | 0 | 1 | +1 |
| Ontology entity classes | 0 | 11 | +11 |
| Ontology relation types | 0 | 10 | +10 |
| Ontology mapping rules | 0 | 6 | +6 |
| Graph relationships | 4270 | 4270 | 0 |
| Distinct graph relationship types | 4 | 4 | 0 |
| Existing relationships with ontology provenance | 0 | 0 | 0 |

## Relink Benchmark

The first benchmark only loaded the ontology catalog. The next concrete
improvement made no-embed graph relinking safe by preserving existing embeddings
on chunk upsert and merging ontology provenance into existing relationship
properties.

Command:

```bash
.venv/bin/rag index-corpus --no-embed
HF_HOME=./models .venv/bin/rag eval-quality --top-k 12 --fail-under 0.80 \
  --output reports/ocpp21-ed2-rqk-quality-ontology-relinked.md
```

| Metric | Before relink | After ontology relink | Delta |
| --- | ---: | ---: | ---: |
| Embedded chunks | 4884 | 4884 | 0 |
| Pending chunks | 1 | 1 | 0 |
| Graph relationships | 4270 | 4270 | 0 |
| Relationships with ontology provenance | 0 | 4270 | +4270 |
| Provenance coverage | 0.0% | 100.0% | +100.0 pp |
| Retrieval cases passed | 12/12 | 12/12 | 0 |
| Retrieval score | 0.976 | 0.976 | 0.000 |
| Total measured latency | 166080 ms | 167795 ms | +1715 ms |
| Average latency per case | 13840 ms | 13983 ms | +143 ms |

Ontology provenance by relationship type after relink:

| Relation type | Count | With ontology provenance |
| --- | ---: | ---: |
| `component_has_variable` | 414 | 414 |
| `dm_defines_entity` | 987 | 987 |
| `schema_defines_entity` | 2278 | 2278 |
| `spec_defines_entity` | 591 | 591 |

## Interpretation

The ontology layer did not regress retrieval quality. The 12-case R/Q/K suite
still passes with the same score, and the small latency difference is runtime
noise from model/reranker execution rather than an ontology traversal cost.
Current retrieval does not consult the ontology catalog yet.

The first improvement is governance, not ranking: the database now has an active
OCPP ontology catalog, allowed relation types, source/evidence catalogs, mapping
rules, and graph write-time validation support.

After ontology relinking, every existing graph relationship now records:

- `ontology_version`
- `ontology_relation`
- `mapping_rule`
- `evidence_layer`
- `source_type`
- `confidence`
- `stable_key`
- `corpus_record_id`

## Conclusion

Status: PASS.

Introducing the ontology catalog and relinking the graph is safe for the current
retrieval quality baseline and adds enterprise semantic governance. The concrete
improvement is 100% ontology provenance coverage across existing graph
relationships without losing embeddings.

## Next Benchmark

The next benchmark should make retrieval consume ontology provenance directly:

- expose relation provenance in evidence packs;
- add ontology-aware graph traversal explanations;
- compare graph contribution and answer trust before/after explainability.
