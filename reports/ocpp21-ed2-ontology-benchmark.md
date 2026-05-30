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

## Evidence-Pack Explainability Benchmark

The next concrete improvement exposes ontology provenance at retrieval output
time instead of keeping it only in database relationship properties.

Validation:

```bash
.venv/bin/pytest tests/test_api/test_query_routes.py tests/test_api/test_openapi_schema.py tests/test_ontology/test_store.py tests/test_mcp/test_server_formatting.py -q
```

Result:

- `10 passed`
- FastAPI `/query` and `/search` response chunks include `semantic_links`.
- MCP `search_ocpp_knowledge`, `get_ocpp_evidence_pack`, and
  `build_ocpp_implementation_brief` render chunk-level `Semantic Links` in
  Markdown when graph provenance is available.
- MCP `get_ocpp_entity` relationship output includes ontology version and
  mapping-rule provenance when present.

| Metric | Before exposure | After exposure | Delta |
| --- | ---: | ---: | ---: |
| API chunk semantic-link field | 0 | 1 | +1 |
| MCP evidence-pack semantic-link block | 0 | 1 | +1 |
| MCP formatting contract tests | 0 | 1 | +1 |
| Graph semantic-link store tests | 0 | 1 | +1 |

This does not change ranking. The concrete improvement is explainability:
coding agents and API clients can now see which ontology rule connected a
retrieved chunk to related OCPP entities.

## Ontology-Aware Retrieval Benchmark

The next improvement makes graph retrieval consume ontology provenance directly.
Graph retrieval now:

- uses active ontology relation types for traversal when the ontology catalog is
  loaded;
- ignores non-ontology relation strings during ontology-aware traversal;
- applies a bounded score boost to graph hits with ontology-provenance semantic
  links;
- writes graph-hit metadata with semantic-link count, ontology versions,
  relation names, and mapping rules.

Validation:

```bash
.venv/bin/pytest tests/test_retrieval/test_graph_search.py tests/test_ontology/test_store.py tests/test_api/test_query_routes.py tests/test_mcp/test_server_formatting.py -q
HF_HOME=./models .venv/bin/rag eval-quality --top-k 12 --fail-under 0.80 \
  --output reports/ocpp21-ed2-rqk-quality-ontology-aware-retrieval.md
```

Results:

- Targeted tests: `11 passed`
- R/Q/K quality gate: `12/12` passed
- Retrieval score: `0.976`
- Fail-under: `0.800`
- Status: `PASS`

| Metric | Before ontology-aware retrieval | After ontology-aware retrieval | Delta |
| --- | ---: | ---: | ---: |
| Retrieval cases passed | 12/12 | 12/12 | 0 |
| Retrieval score | 0.976 | 0.976 | 0.000 |
| Graph traversal relation filter | none | active ontology relation types | improved control |
| Graph semantic-link score boost | no | yes | improved ranking signal |
| Eval graph candidate chunks | not reported | 30 | +30 observed |
| Eval graph candidate semantic links | not reported | 110 | +110 observed |
| Eval max graph traversal depth | not reported | 2 | +2 observed |
| Graph retrieval unit tests | 0 | 2 | +2 |

Observed top-evidence changes stayed within the passing envelope. Fusion cases
still include the required spec, Device Model, and schema layers. The concrete
improvement is controlled graph behavior: private/non-ontology graph edges no
longer participate in ontology-aware traversal, and ontology-provenance graph
hits can outrank plain graph hits.

## Ontology Metrics In Eval Reports

`rag eval-quality` now reports ontology metrics at suite and case level. The
refreshed 12-case report is:

- `reports/ocpp21-ed2-rqk-quality-ontology-aware-retrieval.md`
- `12/12` passed
- Score: `0.976`
- Graph candidate chunks: `30`
- Graph candidate chunks with semantic links: `30`
- Graph candidate semantic links: `110`
- Final graph chunks: `0`
- Max traversal depth: `2`
- Relation types observed: `component_has_variable`, `dm_defines_entity`,
  `schema_defines_entity`, `spec_defines_entity`
- Mapping rules observed: `dm_component_variable`, `source_appendix_records`,
  `source_dm_records`, `source_schema_records`, `source_spec_records`

Focused DER fusion report:

- `reports/ocpp21-ed2-rqk-quality-ontology-metrics-der.md`
- `1/1` passed
- Graph candidate chunks: `10`
- Graph candidate semantic links: `39`
- Max traversal depth: `2`

Interpretation: ontology-aware graph retrieval is producing governed candidates,
but current vector/keyword/reranker and source-layer coverage logic still win
the final top-k for the R/Q/K suite. This is a useful enterprise signal: graph
candidate contribution is measurable without silently altering answer evidence.

## Conclusion

Status: PASS.

Introducing the ontology catalog and relinking the graph is safe for the current
retrieval quality baseline and adds enterprise semantic governance. The concrete
improvement is 100% ontology provenance coverage across existing graph
relationships without losing embeddings, plus source-aware semantic-link
explanations in API and MCP evidence outputs, plus ontology-aware graph
traversal and graph-hit scoring.

## Next Benchmark

The next benchmark should use these metrics to tune graph promotion:

- compare final top-k quality when one high-confidence ontology graph candidate
  is promoted in fusion cases;
- measure whether graph promotion improves source-layer coverage or answer
  faithfulness;
- keep the R/Q/K score at or above `0.976`.
