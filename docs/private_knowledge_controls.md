# Private Knowledge Controls

This document defines the first enterprise controls for private OCPP knowledge
operations.

## Log Redaction

Log redaction is enabled by default.

```bash
LOG_REDACTION_ENABLED=true
```

For controlled local debugging only, raw log redaction can be disabled:

```bash
LOG_REDACTION_ENABLED=false
```

This switch affects log/debug redaction helpers. Audit storage remains
privacy-preserving and force-redacts metadata before insertion.

## Audit Events

Audit events are stored in `audit_events`.

The table is designed for traceability without storing raw private content. Do
not store raw prompts, full query text, retrieved chunks, generated answers,
source text, API keys, tokens, or passwords in audit metadata.

### Common Fields

- `event_type`: event name such as `query.requested`.
- `surface`: access surface, for example `api`, `cli`, or `mcp`.
- `action`: local command, endpoint, or MCP tool action.
- `status`: `success` or `failure`.
- `correlation_id`: groups events from one request or tool call.
- `resource_type` and `resource_id`: optional audited resource reference.
- `latency_ms`: elapsed time for measurable operations.
- `metadata`: redacted JSONB metadata.

### Event Types

- `query.requested`: a user query or search request was accepted.
- `retrieval.completed`: retrieval completed and returned chunk IDs/counts.
- `generation.completed`: answer generation completed.
- `generation.failed`: answer generation failed.
- `corpus.ingested`: source document or corpus records were ingested.
- `corpus.indexed`: corpus records were indexed into chunks/embeddings/graph.
- `mcp.access`: an MCP tool call completed or failed.

### Sensitive Text References

Sensitive text is represented with non-reversible references:

```json
{
  "query": {
    "sha256": "6f...",
    "length": 42
  }
}
```

This allows correlation and debugging without storing the private text itself.

## Current Coverage

- API query/search routes write query, retrieval, and generation events.
- CLI query writes query, retrieval, and generation events.
- CLI corpus store/index writes corpus ingestion/indexing events.
- Legacy CLI ingest writes corpus ingestion events.
- MCP writes tool access events and retrieval events for search/evidence tools.
- FastAPI admin mutation endpoints require `API_ADMIN_TOKEN` bearer auth and
  write audit events for source-aware corpus ingestion/indexing, legacy
  ingestion, and document deletion.

## Admin Mutation Guard

Read-only FastAPI endpoints remain available without this guard. Mutating admin
endpoints are disabled by default:

```bash
API_ADMIN_TOKEN=
```

Set a token only for controlled environments that need API mutation endpoints:

```bash
API_ADMIN_TOKEN=<admin-token>
```

Then call admin mutation endpoints with:

```text
Authorization: Bearer <admin-token>
```

Currently protected endpoints:

- `POST /corpus/preview` - source-aware OCPP corpus preview. It is guarded
  because it reads private local source files, even though it returns only
  counts and source summaries.
- `POST /corpus/store` - source-aware OCPP corpus storage endpoint.
- `POST /corpus/index` - source-aware OCPP corpus indexing endpoint.
- `POST /ingest` - legacy direct PDF/JSON ingestion endpoint.
- `DELETE /documents/{document_id}` - document deletion endpoint.

Read-only status endpoint:

- `GET /corpus/status` - returns corpus/index counts by source type and
  evidence layer.

## Remaining Controls

- Source access control metadata and enforcement.
- Retention and deletion policy.
- Audit read API or admin CLI with access restrictions.
- CI checks that reject raw prompt/chunk/answer logging.
