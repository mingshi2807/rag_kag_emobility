---
name: ocpp-rag-kag-improve
description: Improve this OCPP 2.1 Ed2 RAG/KAG knowledge backend. Use when changing or diagnosing corpus ingestion, indexing, chunking, embeddings, hybrid retrieval, fusion, reranking, graph links, evidence-layer routing, generation prompts, answer citation behavior, or enterprise quality controls.
---

# OCPP RAG/KAG Improve

Use this skill for continuous improvement of the OCPP 2.1 Ed2 knowledge backend.
The goal is a measurable improvement, not a subjective prompt tweak.

## Required Context

Read these first when relevant:

- `AGENTS.md` for repo operating rules and quality gates.
- `docs/HANDOFF.md` for current state, backlog, and commands.
- `docs/AUDIT_REPORT.md` for enterprise-readiness gaps.

## Workflow

1. State the target symptom and success criterion.
2. Inspect the relevant code path before editing:
   - ingestion/corpus: `src/rag_ocpp/corpus/`, `src/rag_ocpp/cli/corpus.py`
   - retrieval/fusion: `src/rag_ocpp/retrieval/`, `src/rag_ocpp/storage/vector.py`
   - generation: `src/rag_ocpp/generation/`
   - API/CLI/MCP: `src/rag_ocpp/api/`, `src/rag_ocpp/cli/`, `src/rag_ocpp/mcp/`
3. Reproduce the issue with at least one command or DB query when feasible.
4. Make the smallest scoped change that improves source-aware behavior.
5. Validate with a before/after query, targeted tests, and any relevant DB counts.

## Evidence Contract

Every improvement report must include:

- Baseline symptom and command.
- Expected evidence layers: `spec`, `device_model`, `schema`.
- Retrieved anchors before/after, when available.
- Validation commands and result.
- Residual risk or missing eval coverage.

## Preferred Commands

```bash
HF_HOME=./models .venv/bin/rag query "..." --top-k 8
HF_HOME=./models .venv/bin/rag query "..." --top-k 12
.venv/bin/pytest tests/test_corpus/test_ocpp21.py -q
.venv/bin/python -m compileall -q src/rag_ocpp
```

Use `--evidence-layer spec`, `--evidence-layer device_model`, or
`--evidence-layer schema` to isolate retrieval failures.

## Stop Condition

Stop when the target query or workflow has visibly better source-aware evidence,
the code compiles, targeted tests pass, and remaining gaps are explicitly stated.
