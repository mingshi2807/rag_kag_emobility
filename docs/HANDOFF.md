# Handoff: RAG-KAG-OCPP Repository Control

**Date:** 2026-05-27
**Control status:** OCPP 2.1 Ed2 source-aware corpus, full embedded index, project-local skills, upgraded MCP evidence tools, retrieval quality evals, and golden generated-answer evals are implemented. Root `AGENTS.md` defines agent operating rules. Enterprise audit is captured in `docs/AUDIT_REPORT.md`.
**Current conclusion:** The project now has a first-class corpus record layer for Part 2 spec, Device Model tables, and JSON schemas, plus agent-facing MCP tools and repeatable R/Q/K retrieval and generated-answer gates. It is still not enterprise-ready until private-data controls, migrations, CI wiring, and broader integration tests are complete.

## Mission

Build a private e-mobility knowledge base with LLM, RAG, and KAG integration for OCPP first, then broader protocol coverage. The required product bar is answer traceability, private-data protection, reproducible ingestion, measurable retrieval quality, and stable API/CLI/MCP access.

## Current Architecture

```
PDF/JSON -> parser -> cleaner -> metadata -> chunking
        -> embeddings -> PostgreSQL + pgvector
        -> entity extraction/linking -> graph tables

Query -> vector + keyword + graph retrieval
      -> weighted RRF -> reranker -> top chunks
      -> DeepSeek generation / API / CLI / MCP evidence tools
```

## Current Evidence Snapshot

- `pyproject.toml` defines a Python 3.12 package named `rag-kag-ocpp` with CLI entries `rag` and `rag-mcp`.
- `config/default.yaml` currently sets BGE-large embeddings at 1024 dimensions and recursive spec chunking at 1024 tokens.
- `src/rag_ocpp/storage/schema.sql` now declares `chunks.embedding VECTOR(1024)` and adds `source_documents` plus `corpus_records`.
- `src/rag_ocpp/corpus/` normalizes source-aware evidence records from the OCPP 2.1 Ed2 Part 2 PDF, Device Model CSV/XLSX files, and JSON schemas.
- `src/rag_ocpp/cli/corpus.py` adds `rag corpus`, defaulting to dry-run preview; use `--store` to write source/corpus records.
- `rag index-corpus` indexes stored corpus records into `chunks`, embeddings, graph entities, chunk/entity links, and source-definition relationships.
- `src/rag_ocpp/storage/vector.py` and `src/rag_ocpp/storage/graph.py` now parameterize the previous keyword/entity ILIKE fallback SQL paths.
- `docs/ingest.md`, `docs/dev_journey.md`, and `docs/plan_note.md` still describe older BGE-base, 768-dimensional, SDPM/512-token assumptions.
- `docs/mcp.md` documents nine MCP read tools, including filtered search, evidence packs, implementation briefs, corpus status, chunk/entity lookup, and section search.
- `.codex/skills/` contains repo-local OCPP RAG/KAG workflow skills for improvement, expert review, query eval, implementation guides, and smoke testing.
- `docs/query_quality_eval.md` documents `rag eval-quality` and `rag eval-answers` gates for Section R DER, Section Q V2X, and Section K smart charging.
- `reports/ocpp21-ed2-rqk-quality-baseline.md` records a 12-case retrieval baseline: `12/12` passed, score `0.976`.
- `reports/ocpp21-ed2-rqk-golden-answers.md` records a 3-case generated Markdown answer baseline: `3/3` passed, score `1.000`.
- `reports/golden_answers/` stores the generated DER, V2X, and Smart Charging Markdown answers that can be rescored without another LLM call.
- `reports/ocpp21-ed2-rqk-golden-answers-codex-only.md` records a Codex-authored, MCP-evidence-assisted 3-case generated-answer benchmark: `3/3` passed, score `1.000`.
- `reports/golden_answers_codex-only/` stores Codex-authored DER, V2X, and Smart Charging answers refreshed from MCP evidence for offline rescoring without DeepSeek or OpenAI API calls.
- `docs/mcp.md` now documents the Codex-assisted manual benchmark workflow: Codex uses MCP evidence tools, writes Markdown answers, and `rag eval-answers --from-answers-dir` scores them offline without DeepSeek or OpenAI API calls.
- `tests/test_retrieval/test_vector_search.py` appears to use random document UUIDs instead of the ID returned by `insert_document`, so retrieval integration tests are likely not proving the intended path.

## Strict Control Rules

1. Do not make retrieval or generation changes without a measurable eval baseline.
2. Do not change embedding dimensions without schema migration, re-embedding, and documentation updates in the same branch.
3. Do not add SQL built from raw user/query terms. Parameterize all query inputs.
4. Do not log private source chunks, retrieved context, prompts, answers, or secrets without a redaction policy.
5. Keep `AGENTS.md`, this handoff, and `docs/AUDIT_REPORT.md` current after material changes.

## Ordered Next Actions

1. Wire `rag eval-quality` and `rag eval-answers` into CI with controlled model/API availability assumptions.
2. Repair retrieval integration tests and run a clean `pytest` baseline.
3. Add private-knowledge controls: secret handling, log redaction, source access model, data retention, and audit events.
4. Make migrations explicit instead of relying on manual DB mutation.
5. Align API, CLI, and MCP generated-answer behavior with the golden-answer citation and Markdown contract.
6. Extend eval coverage beyond R/Q/K into BootNotification, Device Model reporting, transactions, security, and firmware/diagnostics.
7. Add operational runbooks for ingestion, re-embedding, eval, rollback, backup, and restore.

## Verification Commands

```bash
ruff check .
mypy src
pytest
docker compose up -d
rag eval data/eval/queries.jsonl --top-k 10
HF_HOME=./models .venv/bin/rag eval-quality --top-k 12 --fail-under 0.80
HF_HOME=./models .venv/bin/rag eval-answers --from-answers-dir --answers-dir reports/golden_answers --output reports/ocpp21-ed2-rqk-golden-answers.md
HF_HOME=./models .venv/bin/rag eval-answers --from-answers-dir --answers-dir reports/golden_answers_codex-only --output reports/ocpp21-ed2-rqk-golden-answers-codex-only.md
```

If Docker, model downloads, or DeepSeek credentials are unavailable, record the gap in this file and keep local static checks as the minimum validation.

## Critical Files

- `AGENTS.md` - agent and contributor operating rules.
- `docs/AUDIT_REPORT.md` - strict enterprise-readiness audit and improvement order.
- `config/default.yaml` - current runtime tunables.
- `src/rag_ocpp/storage/schema.sql` - database contract.
- `src/rag_ocpp/corpus/ocpp21.py` - OCPP 2.1 Ed2 source-aware corpus parsers.
- `src/rag_ocpp/corpus/indexer.py` - indexes corpus records into chunks, embeddings, and graph links.
- `src/rag_ocpp/storage/corpus.py` - DB adapter for source documents and corpus records.
- `src/rag_ocpp/cli/corpus.py` - corpus preview/store CLI command.
- `src/rag_ocpp/storage/vector.py` - vector and keyword retrieval.
- `src/rag_ocpp/storage/graph.py` - entity, relationship, and graph fallback lookup.
- `src/rag_ocpp/retrieval/hybrid.py` - retrieval orchestration and strategy fusion.
- `src/rag_ocpp/mcp/server.py` - agent-facing knowledge tools.
- `src/rag_ocpp/eval/answers.py` - golden generated-answer cases and Markdown scoring.
- `src/rag_ocpp/generation/prompt.py` - standard generation prompt plus strict golden-answer prompt.
