# FastAPI HTTP Client Smoke Tests

This guide validates the FastAPI surface from an external HTTP client such as
`curl` or Postman against a running uvicorn server.

The checks are intended for local development and smoke testing. They prove that
the API process can connect to PostgreSQL, load models, expose OpenAPI, retrieve
source-aware evidence, call DeepSeek generation, and enforce admin guards.

## Prerequisites

- PostgreSQL is running, usually with `docker compose up -d`.
- The corpus has already been stored and indexed.
- The virtual environment is installed with `pip install -e ".[dev]"`.
- `.env` contains `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and
  `DEEPSEEK_MODEL=deepseek-v4-pro` if generation endpoints will be tested.
- `jq` is optional but useful for readable JSON output.

## Start The Server

Source `.env` explicitly so the shell environment and app configuration agree:

```bash
set -a
source .env
set +a

HF_HOME=./models API_ADMIN_TOKEN=local-test-token \
  .venv/bin/uvicorn "rag_ocpp.api.app:create_app" \
  --factory \
  --host 127.0.0.1 \
  --port 8000
```

Base URL:

```text
http://127.0.0.1:8000
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

OpenAPI import URL for Postman:

```text
http://127.0.0.1:8000/openapi.json
```

## Read-Only Checks

Health:

```bash
curl -s http://127.0.0.1:8000/health | jq
```

Expected:

- HTTP `200`
- `database` is `connected`
- `embedding_loaded` is `true`
- `reranker_loaded` is `true`

OpenAPI:

```bash
curl -s http://127.0.0.1:8000/openapi.json | jq '.openapi, .info'
```

Expected:

- OpenAPI is `3.0.3`
- API version is `0.2.0`

Corpus status:

```bash
curl -s http://127.0.0.1:8000/corpus/status | jq
```

Expected on the current indexed OCPP 2.1 Ed2 corpus:

- `source_documents` is non-zero
- `corpus_records` is non-zero
- `corpus_chunks` equals indexed corpus chunk count
- `embedded_corpus_chunks` is non-zero after full embedding indexing
- `by_evidence_layer` includes `spec`, `device_model`, and `schema`

Documents:

```bash
curl -s http://127.0.0.1:8000/documents | jq 'length, .[0]'
```

Expected:

- HTTP `200`
- At least one indexed document

Entity lookup:

```bash
curl -s http://127.0.0.1:8000/entities/DeviceDataCtrlr | jq
```

Expected:

- HTTP `200`
- Entity name is `DeviceDataCtrlr`
- Relationships include Device Model variable links when the graph is indexed

Source-aware search without generation:

```bash
curl -s \
  "http://127.0.0.1:8000/search?q=Device%20Model%20purpose&top_k=3&evidence_layer=device_model&include_content=false" \
  | jq
```

Expected:

- HTTP `200`
- `results` contains up to three chunks
- each returned chunk has `evidence_layer=device_model`
- `content` is `null` when `include_content=false`

## Generated Answer Checks

Non-streaming DeepSeek generation:

```bash
curl -s -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the purpose of BootNotification in OCPP 2.1 Ed2?",
    "top_k": 3,
    "max_chars": 500,
    "include_content": false
  }' | jq
```

Expected:

- HTTP `200`
- `answer` is non-empty Markdown
- `sources` contains source-aware chunks
- server logs show a DeepSeek request using `deepseek-v4-pro`

Streaming generation:

```bash
curl -N -X POST http://127.0.0.1:8000/query/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain Device Model purpose in OCPP 2.1 Ed2.",
    "top_k": 3,
    "include_content": false
  }'
```

Expected:

- HTTP `200`
- first event is `sources`
- following events are `token`
- final event is `done`

If `DEEPSEEK_API_KEY` is missing or invalid, generation endpoints should fail
with a redacted generation error instead of exposing the secret or raw prompt.

## Admin Guard Checks

Admin endpoints require:

```text
Authorization: Bearer local-test-token
```

Unauthorized corpus preview should fail:

```bash
curl -s -X POST http://127.0.0.1:8000/corpus/preview \
  -H "Content-Type: application/json" \
  -d '{"include_pdf": false, "include_dm": false, "include_schemas": false}' \
  | jq
```

Expected:

- HTTP `401`
- `error` is `admin_auth_required`

Authorized corpus preview:

```bash
curl -s -X POST http://127.0.0.1:8000/corpus/preview \
  -H "Authorization: Bearer local-test-token" \
  -H "Content-Type: application/json" \
  -d '{"include_pdf": true, "include_dm": false, "include_schemas": false}' \
  | jq
```

Expected:

- HTTP `200`
- `planned_sources` is `1`
- `total_records` reflects parsed PDF section records
- response contains counts and source summaries, not raw PDF text

Safe no-op corpus store:

```bash
curl -s -X POST http://127.0.0.1:8000/corpus/store \
  -H "Authorization: Bearer local-test-token" \
  -H "Content-Type: application/json" \
  -d '{"include_pdf": false, "include_dm": false, "include_schemas": false}' \
  | jq
```

Expected:

- HTTP `200`
- `stored_sources` is `0`
- `stored_records` is `0`

Safe limited indexing without embeddings:

```bash
curl -s -X POST http://127.0.0.1:8000/corpus/index \
  -H "Authorization: Bearer local-test-token" \
  -H "Content-Type: application/json" \
  -d '{"no_embed": true, "limit": 1, "batch_size": 1}' \
  | jq
```

Expected:

- HTTP `200`
- at most one record is indexed
- `chunks_embedded` is `0`

Legacy ingest without auth should fail:

```bash
curl -s -X POST http://127.0.0.1:8000/ingest | jq
```

Expected:

- HTTP `401`
- `error` is `admin_auth_required`

Legacy ingest with auth but no file should validate the request:

```bash
curl -s -X POST http://127.0.0.1:8000/ingest \
  -H "Authorization: Bearer local-test-token" \
  | jq
```

Expected:

- HTTP `422`
- missing multipart `file`

Document deletion should not be tested against real corpus IDs unless the caller
intends to delete data. A safe not-found check is:

```bash
curl -s -X DELETE \
  http://127.0.0.1:8000/documents/00000000-0000-0000-0000-000000000000 \
  -H "Authorization: Bearer local-test-token" \
  | jq
```

Expected:

- HTTP `404`
- no real document is deleted

## Postman Workflow

1. Import the OpenAPI URL:

   ```text
   http://127.0.0.1:8000/openapi.json
   ```

2. Create an environment:

   ```text
   base_url=http://127.0.0.1:8000
   admin_token=local-test-token
   ```

3. For admin endpoints, set bearer token auth to:

   ```text
   {{admin_token}}
   ```

4. Run read-only requests first:
   - `GET /health`
   - `GET /corpus/status`
   - `GET /search`
   - `POST /query`

5. Run admin checks only after confirming the target database is disposable or
   the request is a no-op.

## Troubleshooting

- `401 admin_auth_required`: missing `Authorization: Bearer ...` header.
- `403 admin_auth_forbidden`: token does not match `API_ADMIN_TOKEN`.
- `502 generation_failed`: DeepSeek generation failed; check `.env`,
  `DEEPSEEK_API_KEY`, and network access.
- Slow `/corpus/preview`: PDF parsing is synchronous in the current API.
- Slow startup: embedding and reranker models load during FastAPI lifespan.
- Empty retrieval results: verify `rag corpus-status` and `GET /corpus/status`
  show indexed and embedded chunks.
