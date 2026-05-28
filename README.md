# RAG-KAG OCPP Knowledge Backend

Private enterprise knowledge backend for OCPP 2.1 Ed2 protocol material using
RAG plus KAG: source-aware ingestion, chunking, embeddings, PostgreSQL/pgvector
storage, graph relationships, hybrid retrieval, generation, evaluation, CLI,
API, and MCP access.

Stable release target: `v0.2.0`.

## What This Project Does

This repository builds an OCPP-first knowledge backend for private e-mobility
protocol work. The current stable scope focuses on OCPP 2.1 Ed2 Part 2
specification evidence, associated Device Model tables, and JSON schemas.

The product goal is not only to answer questions. The goal is to provide
traceable, source-aware implementation guidance that can be evaluated, audited,
and used by coding agents without leaking private protocol material into logs or
uncontrolled generation flows.

## v0.2.0 Status

Implemented:

- Source-aware OCPP 2.1 Ed2 corpus model for specification, Device Model, and
  JSON schema evidence.
- PostgreSQL plus pgvector storage with 1024-dimensional BGE-large embeddings.
- Hybrid retrieval using vector, keyword, graph, fusion, and reranking.
- DeepSeek generation path with default model `deepseek-v4-pro`.
- MCP evidence tools for Codex and other coding agents.
- Query quality evaluation for Section R DER, Section Q V2X, and Section K
  smart charging.
- Golden Markdown answer evaluation and offline benchmark scoring.
- Configurable redacted logging for private-knowledge operations.
- Privacy-preserving audit events for query, retrieval, generation, corpus
  ingestion/indexing, and MCP access.
- Explicit SQL migrations with a `schema_migrations` ledger.

Not yet enterprise-complete:

- Source-level ACLs and tenant isolation.
- Retention/deletion policy.
- CI wiring for eval and migration gates.
- API/MCP generated-answer contract tests.
- Backup, restore, rollback, and re-embedding runbooks.

## Architecture

```text
PDF / CSV-XLSX / JSON schema
  -> source-aware corpus parser
  -> normalized corpus records
  -> chunking
  -> embeddings
  -> PostgreSQL + pgvector
  -> graph entities and relationships

Query
  -> vector + keyword + graph retrieval
  -> weighted RRF fusion
  -> reranker
  -> source-aware evidence
  -> generated Markdown answer / MCP evidence pack / implementation brief
```

## Repository Layout

```text
config/default.yaml                 Runtime configuration
data/                               Local corpus and eval data
docs/                               Operator, audit, MCP, migration docs
reports/                            Evaluation and benchmark reports
src/rag_ocpp/api/                   FastAPI application surface
src/rag_ocpp/cli/                   Typer CLI commands
src/rag_ocpp/corpus/                OCPP 2.1 Ed2 source-aware corpus pipeline
src/rag_ocpp/storage/               PostgreSQL, vector, graph, audit, migrations
src/rag_ocpp/retrieval/             Hybrid retrieval, fusion, reranking
src/rag_ocpp/generation/            Prompting and DeepSeek client
src/rag_ocpp/mcp/                   MCP server for coding agents
tests/                              Unit and Docker-backed integration tests
```

## Requirements

- Python `3.12+`
- Docker with Compose
- PostgreSQL/pgvector, provided by `docker-compose.yml`
- Optional DeepSeek API key for generated answers
- Local Hugging Face model cache recommended at `./models`

Install:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

Default runtime configuration is in `config/default.yaml`.

Important defaults:

```text
PG_HOST=localhost
PG_PORT=55432
PG_DATABASE=rag_kag
PG_USER=rag_kag
PG_PASSWORD=rag_kag
DEEPSEEK_MODEL=deepseek-v4-pro
LOG_REDACTION_ENABLED=true
API_ADMIN_TOKEN=
```

Use a repo-local Hugging Face cache:

```bash
export HF_HOME=./models
```

Set DeepSeek credentials only when generation is needed:

```bash
export DEEPSEEK_API_KEY=<your-key>
```

Set an admin token only when mutating API endpoints are needed:

```bash
export API_ADMIN_TOKEN=<admin-token>
```

## Database Setup

Start PostgreSQL:

```bash
docker compose up -d
```

Check migration status:

```bash
.venv/bin/rag migrate-status
```

For a fresh empty database:

```bash
.venv/bin/rag migrate --dry-run
.venv/bin/rag migrate
.venv/bin/rag migrate-status
```

For an existing local database created before migrations existed:

```bash
.venv/bin/rag migrate --baseline
.venv/bin/rag migrate --dry-run
.venv/bin/rag migrate
.venv/bin/rag migrate-status
```

Expected final migration state:

```text
001 initial_schema: applied at <timestamp>
002 ensure_audit_events: applied at <timestamp>
```

See [docs/db_migrations.md](docs/db_migrations.md) for migration rules and
legacy database adoption details.

## Corpus Ingestion

The v0.2.0 priority corpus is OCPP 2.1 Ed2:

- Part 2 specification PDF
- Device Model CSV/XLSX tables
- JSON schemas

Expected local source layout:

```text
data/pdf/
data/csv/
data/json/
```

Preview source-aware corpus records:

```bash
HF_HOME=./models .venv/bin/rag corpus
```

Store corpus records:

```bash
HF_HOME=./models .venv/bin/rag corpus --store
```

Index stored records into chunks, embeddings, and graph links:

```bash
HF_HOME=./models .venv/bin/rag index-corpus
```

## Query Examples

General query:

```bash
HF_HOME=./models .venv/bin/rag query \
  "What is the purpose of BootNotification in OCPP 2.1 Ed2?" \
  --top-k 8
```

Spec-only query:

```bash
HF_HOME=./models .venv/bin/rag query \
  "Explain Section R DER control implementation responsibilities" \
  --top-k 8 \
  --evidence-layer spec
```

Device Model query:

```bash
HF_HOME=./models .venv/bin/rag query \
  "Which Device Model components and variables support smart charging?" \
  --top-k 12 \
  --evidence-layer device_model
```

Fusion query for implementation guidance:

```bash
HF_HOME=./models .venv/bin/rag query \
  "Build senior backend implementation guidance for OCPP 2.1 Ed2 DER control using Part 2 spec behavior, Device Model components and variables, and JSON schema validation." \
  --top-k 12
```

## Evaluation

Run the R/Q/K retrieval quality suite:

```bash
HF_HOME=./models .venv/bin/rag eval-quality --top-k 12 --fail-under 0.80
```

Score cached DeepSeek golden answers:

```bash
HF_HOME=./models .venv/bin/rag eval-answers \
  --from-answers-dir \
  --answers-dir reports/golden_answers \
  --output reports/ocpp21-ed2-rqk-golden-answers.md
```

Score cached Codex-assisted answers:

```bash
HF_HOME=./models .venv/bin/rag eval-answers \
  --from-answers-dir \
  --answers-dir reports/golden_answers_codex-only \
  --output reports/ocpp21-ed2-rqk-golden-answers-codex-only.md
```

Current baseline reports:

- `reports/ocpp21-ed2-rqk-quality-baseline.md`: `12/12` retrieval cases passed,
  score `0.976`.
- `reports/ocpp21-ed2-rqk-golden-answers.md`: `3/3` DeepSeek generated-answer
  cases passed, score `1.000`.
- `reports/ocpp21-ed2-rqk-golden-answers-codex-only.md`: `3/3`
  Codex-assisted answer cases passed, score `1.000`.

## MCP Server

Start the MCP server:

```bash
HF_HOME=./models .venv/bin/rag-mcp
```

The MCP server exposes nine read tools for coding agents:

- `search_ocpp_knowledge`
- `get_ocpp_evidence_pack`
- `build_ocpp_implementation_brief`
- `inspect_ocpp_corpus`
- `get_ocpp_chunk`
- `list_ocpp_entities`
- `get_ocpp_entity`
- `list_ocpp_documents`
- `search_ocpp_by_section`

Example Codex MCP configuration:

```toml
[mcp_servers.rag-kag-ocpp]
command = "/home/ming/workspace/rag-kag-emobility.git/.venv/bin/rag-mcp"

[mcp_servers.rag-kag-ocpp.env]
PG_HOST = "localhost"
PG_PORT = "55432"
PG_DATABASE = "rag_kag"
PG_USER = "rag_kag"
PG_PASSWORD = "rag_kag"
HF_HOME = "/home/ming/workspace/rag-kag-emobility.git/models"
```

See [docs/mcp.md](docs/mcp.md) for full MCP tool schemas and client examples.

## FastAPI Surface

Run the API:

```bash
.venv/bin/uvicorn "rag_ocpp.api.app:create_app" --factory --host 0.0.0.0 --port 8000
```

Read endpoints:

- `GET /health`
- `GET /documents`
- `GET /entities/{name}`
- `GET /search`
- `POST /query`
- `POST /query/stream`

Admin mutation endpoints:

- `POST /ingest`
- `DELETE /documents/{document_id}`

Admin mutation endpoints are disabled unless `API_ADMIN_TOKEN` is configured.
When enabled, call them with:

```text
Authorization: Bearer <admin-token>
```

`POST /ingest` is a legacy direct PDF/JSON ingestion endpoint. Prefer the
source-aware corpus CLI flow for OCPP 2.1 Ed2 PDF, Device Model, and JSON schema
ingestion until a dedicated corpus API is added.

## Private Knowledge Controls

Log redaction is enabled by default:

```bash
LOG_REDACTION_ENABLED=true
```

For controlled local debugging only:

```bash
LOG_REDACTION_ENABLED=false
```

Audit events are stored in `audit_events` and are designed not to store raw
prompts, retrieved chunks, generated answers, full query text, source text,
tokens, passwords, or API keys.

Sensitive text is represented through non-reversible references such as SHA-256
hashes and lengths. See
[docs/private_knowledge_controls.md](docs/private_knowledge_controls.md).

## Testing and Verification

Fast checks:

```bash
.venv/bin/ruff check .
.venv/bin/python -m compileall -q src/rag_ocpp
```

Targeted tests:

```bash
.venv/bin/pytest tests/test_storage/test_migrations.py -q
.venv/bin/pytest tests/test_storage/test_audit.py -q
.venv/bin/pytest tests/test_privacy.py -q
.venv/bin/pytest tests/test_retrieval/test_vector_search.py -q
```

Full test suite:

```bash
.venv/bin/pytest
```

Note: Docker-backed tests skip when Docker is unavailable.

Known local validation caveat: in the current local environment, `mypy` can fail
before project type checking if the Python interpreter is missing `_sqlite3`.

## Release Notes

- Current stable tag target: `v0.2.0`
- API reference: [api.json](api.json)
- Release notes: [release_notes.md](release_notes.md)
- Changelog: [changelog.md](changelog.md)

Recommended release commit message:

```text
release: publish v0.2.0 enterprise controls
```

## Documentation Index

- [docs/HANDOFF.md](docs/HANDOFF.md): current control document and next actions.
- [docs/AUDIT_REPORT.md](docs/AUDIT_REPORT.md): enterprise-readiness audit.
- [docs/db_migrations.md](docs/db_migrations.md): DB migration workflow.
- [docs/private_knowledge_controls.md](docs/private_knowledge_controls.md):
  redaction and audit-event controls.
- [docs/mcp.md](docs/mcp.md): MCP server and coding-agent usage.
- [docs/query_quality_eval.md](docs/query_quality_eval.md): retrieval and
  golden-answer evaluation gates.

## Enterprise Readiness Roadmap

Next recommended engineering work:

1. Align API, CLI, and MCP generated-answer behavior with the golden-answer
   citation and Markdown contract.
2. Extend private-knowledge controls with source ACLs, tenant isolation,
   retention/deletion policy, and secret-handling documentation.
3. Extend eval coverage beyond R/Q/K into BootNotification, Device Model
   reporting, transactions, security, firmware, and diagnostics.
4. Add operational runbooks for ingestion, re-embedding, eval, rollback, backup,
   restore, and migration rollback policy.
5. Wire migration, retrieval-quality, and generated-answer gates into CI.

## License

This project declares an MIT license in `pyproject.toml`.
