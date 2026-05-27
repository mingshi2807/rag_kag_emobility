---
name: ocpp-smoke-test
description: Run or plan reproducible smoke tests for the OCPP 2.1 Ed2 RAG/KAG backend, including corpus load, full indexing with embeddings, DB counts, retrieval checks, generation checks, and regression interpretation.
---

# OCPP Smoke Test

Use this skill after indexing, retrieval changes, prompt changes, schema changes,
environment changes, or before handing off a working RAG/KAG state.

## Preflight

Use the repo venv explicitly:

```bash
.venv/bin/rag --help
.venv/bin/python -m compileall -q src/rag_ocpp
```

Use local Hugging Face cache for embedding/reranker commands:

```bash
HF_HOME=./models .venv/bin/rag ...
```

## Corpus and Index Checks

```bash
.venv/bin/rag corpus --store
HF_HOME=./models .venv/bin/rag index-corpus --batch-size 32
```

Verify PostgreSQL counters:

```bash
docker compose exec -T postgres psql -U rag_kag -d rag_kag -c "select count(*) as sources from source_documents; select count(*) as records from corpus_records; select count(*) as chunks, count(embedding) as embeddings, count(*) filter (where embedding is null) as missing_embeddings from chunks; select vector_dims(embedding) as dims, count(*) from chunks where embedding is not null group by 1;"
```

Current healthy baseline after full OCPP 2.1 Ed2 indexing:

- `197` source documents.
- `4885` corpus records.
- `4885` chunks.
- `4885` embeddings.
- `0` missing embeddings.
- `1024` embedding dimensions.

## Retrieval Smoke Queries

```bash
HF_HOME=./models .venv/bin/rag query "What is the purpose of BootNotification in OCPP 2.1 Ed2?" --top-k 8 --evidence-layer spec
HF_HOME=./models .venv/bin/rag query "What is the Device Model purpose in OCPP 2.1 Ed2?" --top-k 8
HF_HOME=./models .venv/bin/rag query "For OCPP 2.1 Ed2 Section R DER, provide a Markdown senior developer implementation guide combining Part 2 use cases, DER Device Model components/variables, and JSON schema validation for DER control messages." --top-k 16
```

Expected signs:

- BootNotification retrieves `1.5. BootNotification`, `B01`, `B02`, or `B03`.
- Device Model retrieves `B06`, `B07`, `B08`, referenced components/variables, or DM table rows.
- Fusion queries show a useful mix of `spec`, `device_model`, and `schema` when evidence exists.

## Targeted Tests

```bash
.venv/bin/pytest tests/test_corpus/test_ocpp21.py -q
```

Add broader tests only when the touched behavior has existing coverage or a new
fixture can be kept small and deterministic.

## Output Contract

```markdown
## Smoke Result

| Check | Expected | Actual | Status |
|---|---|---|---|

## Failures

## Interpretation

## Next Action
```

## Stop Condition

Stop when the requested smoke surface has clear pass/fail evidence and any
failure has a concrete next diagnostic command.
