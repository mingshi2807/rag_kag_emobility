# Repository Agent Guide

## Purpose

This repository builds a private enterprise knowledge base for e-mobility protocol material using RAG plus KAG: ingestion, chunking, embeddings, PostgreSQL/pgvector storage, graph relationships, hybrid retrieval, generation, API, CLI, and MCP access.

Treat correctness, traceability, source control, and evaluation as product requirements. Do not optimize only for demos or subjective answer quality.

## Project Layout

- `src/rag_ocpp/` contains the Python package.
- `src/rag_ocpp/storage/` owns PostgreSQL schema, vector search, and graph storage.
- `src/rag_ocpp/corpus/` owns source-aware OCPP 2.1 Ed2 evidence extraction.
- `src/rag_ocpp/retrieval/` owns vector, keyword, graph, fusion, rerank, and orchestration.
- `src/rag_ocpp/ingestion/`, `chunking/`, `embedding/`, and `knowledge/` own document-to-index pipelines.
- `src/rag_ocpp/api/`, `cli/`, and `mcp/` are external access surfaces.
- `config/default.yaml` is the default runtime contract.
- `docs/HANDOFF.md` is the current control document. Update it when operational state changes.
- `docs/AUDIT_REPORT.md` is the strict enterprise-readiness audit and ordered improvement backlog.

## Commands

Use Python 3.12 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
mypy src
pytest
docker compose up -d
rag --help
rag-mcp
```

Integration tests use Docker and may skip when Docker is unavailable.

## Engineering Rules

- Keep configuration, schema, docs, tests, and operational handoff in sync.
- Prefer parameterized SQL. Do not add f-string SQL for user-controlled values.
- Treat protocol documents as private enterprise data. Do not log full source chunks, secrets, prompts, retrieved context, or generated answers unless explicitly required and redacted.
- Every retrieval change needs an evaluation path: baseline metrics, fixture queries, or a clear documented gap.
- Every schema/model dimension change needs a migration and re-embedding plan.
- Keep API, CLI, and MCP behavior aligned. If one surface changes, inspect the others.

## Commit Messages

Follow the Lore protocol from the workspace instructions. The first line should explain why the change exists. Add trailers only when they clarify constraints, rejected alternatives, risk, directives, or validation.
