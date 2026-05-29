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

## Interpretation

The ontology layer did not regress retrieval quality. The 12-case R/Q/K suite
still passes with the same score, and the small latency difference is runtime
noise from model/reranker execution rather than an ontology traversal cost.
Current retrieval does not consult the ontology catalog yet.

The main improvement is governance, not ranking: the database now has an active
OCPP ontology catalog, allowed relation types, source/evidence catalogs, mapping
rules, and graph write-time validation support.

Existing graph relationships were created before ontology-aware indexing, so
they do not yet contain ontology provenance properties. New or reindexed graph
relationships created by `CorpusIndexer` will record:

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

Introducing the ontology catalog is safe for the current retrieval quality
baseline and adds enterprise semantic governance. The next measurable gain will
come from an ontology-aware reindex plus retrieval explainability that exposes
why spec, Device Model, and schema evidence are semantically connected.

## Next Benchmark

Do not run `rag index-corpus --no-embed` on the production corpus because the
current chunk upsert path can overwrite embeddings with `NULL`. For the next
benchmark, either:

- fix chunk upsert so no-embed reindex preserves existing embeddings, then run an
  ontology-aware graph relink benchmark; or
- run full `rag index-corpus` with embeddings and compare ontology provenance
  coverage, graph traversal contribution, and R/Q/K quality again.
