# OCPP Query Quality Evaluation: ocpp21-ed2-rqk-source-aware

- Cases: `1`
- Passed: `1/1`
- Score: `1.000`
- Fail-under: `0.800`
- Status: `PASS`

## Ontology Metrics

- Graph candidate chunks: `10`
- Graph candidate chunks with semantic links: `10`
- Graph candidate semantic links: `39`
- Final graph chunks: `0`
- Final graph chunks with semantic links: `0`
- Max traversal depth: `2`
- Ontology relation types: `component_has_variable, dm_defines_entity`
- Ontology mapping rules: `dm_component_variable, source_appendix_records, source_dm_records`

## Cases

### R-FUSION-DER-IMPLEMENTATION - PASS

- Topic: `Section R DER control`
- Mode: `fusion`
- Score: `1.000`
- Layer score: `1.000`
- Required term score: `1.000`
- Optional term score: `1.000`
- Latency: `28687ms`
- Strategy: `{'vector': 5, 'keyword': 7}`
- Query: Build senior backend implementation guidance for OCPP 2.1 Ed2 DER control using Part 2 spec behavior, Device Model components and variables, and JSON schema validation.
- Ontology metrics: `candidate_graph_chunks=10, candidate_semantic_link_chunks=10, candidate_semantic_links=39, final_graph_chunks=0, max_depth=2`
- Matched optional terms: `Response, Variable, requirements, validation`

Evidence layer coverage:
- `spec` `spec_pdf` `2.18. DER Control related` `b719b1bf-277d-5549-b455-818f73515901`
- `schema` `json_schema` `ReportDERControl.req.tbc` `907e1c0c-ec7d-5605-9769-2dab64c0203c`
- `device_model` `device_model_table` `DCDERCtrlr / ModesSupported` `6c5cca30-db74-5ad3-9060-2f84f4ed4062`

Top evidence:
- `spec` `spec_pdf` `2.18. DER Control related` `b719b1bf-277d-5549-b455-818f73515901`
- `spec` `spec_pdf` `2.15. ISO 15118 related` `38bd2b05-3eb6-53ea-96fe-7a8e1b99e832`
- `schema` `json_schema` `ReportDERControl.req.tbc` `907e1c0c-ec7d-5605-9769-2dab64c0203c`
- `spec` `spec_pdf` `Chapter 2. DER Control using OCPP and ISO 15118-20` `8e776275-8447-5707-abec-4851153b648d`
- `spec` `spec_pdf` `2.6. Local Authorization List Management related` `261d153a-e3d3-579e-8d05-75161a23e241`
