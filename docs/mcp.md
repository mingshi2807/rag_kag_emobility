# MCP Server — RAG/KAG OCPP 2.1

> Transport: stdio | Entry: `rag-mcp` | Source: `src/rag_ocpp/mcp/server.py`

---

## What It Does

Exposes the knowledge base as MCP tools for any MCP-compatible coding agent
(Codex, Claude Desktop, Cursor, DeepSeek TUI, etc.).

```
Agent → stdio → rag-mcp → PostgreSQL + pgvector + graph tables
```

---

## Tools (9)

### `search_ocpp_knowledge`

Hybrid retrieval (vector + keyword + graph) → RRF fusion → cross-encoder rerank.
Use this for direct evidence search.

| Field | Type | Required |
|-------|------|----------|
| `query` | string | yes |
| `top_k` | integer | no (default 8, max 20) |
| `evidence_layer` | string | no (`spec`, `device_model`, `schema`) |
| `source_type` | string | no (`spec_pdf`, `device_model_table`, `json_schema`, `appendix_csv`) |
| `doc_type` | string | no |
| `max_chars` | integer | no (default 1200, max 6000) |

Returns Markdown chunks with chunk ID, document ID, score, strategy, evidence
layer, source type, source path, and clipped content.

### `get_ocpp_evidence_pack`

Retrieves a grouped evidence pack for a coding agent.

| Field | Type | Required |
|-------|------|----------|
| `query` | string | yes |
| `top_k` | integer | no (default 12, max 20) |
| `max_chars` | integer | no (default 1800, max 8000) |

Groups results by evidence layer: `spec`, `device_model`, `schema`, `unknown`.
Use this before asking an agent to make implementation decisions.

### `build_ocpp_implementation_brief`

Builds a Markdown implementation brief from retrieved OCPP evidence without
calling any LLM provider. The consuming coding agent can then reason over the
brief using its own model.

| Field | Type | Required |
|-------|------|----------|
| `feature` | string | yes |
| `query` | string | no |
| `top_k` | integer | no (default 14, max 20) |
| `max_chars` | integer | no (default 1600, max 6000) |

The output instructs the consuming agent to cover purpose, normative behavior,
schema, Device Model mapping, backend sequence, smoke tests, conformance focus,
and evidence gaps.

### `inspect_ocpp_corpus`

Returns corpus/index health for agent preflight checks.

| Field | Type | Required |
|-------|------|----------|
| none | — | — |

Returns totals plus evidence-layer/source-type counts and embedding dimensions.
The core count contract is shared with `GET /corpus/status` and
`rag corpus-status`.

### `get_ocpp_chunk`

Full chunk content by UUID.

| Field | Type | Required |
|-------|------|----------|
| `chunk_id` | string | yes |

Returns full content with metadata, evidence layer, source type, and source path.

### `list_ocpp_entities`

List entities, optionally filtered by type.

| Field | Type | Required |
|-------|------|----------|
| `entity_type` | string | no (`message`, `request`, `response`, `field`, `attribute`, `requirement`, `schema`, `command`, `datatype`, `component`, `variable`, `enum`, `functional_block`, `error_code`, `test_case`) |
| `limit` | integer | no (default 20, max 100) |

Returns entity names with type labels.

### `get_ocpp_entity`

Entity details by name with relationships and linked chunks.

| Field | Type | Required |
|-------|------|----------|
| `name` | string | yes |

Returns description, aliases, relationships (incoming/outgoing), linked chunk count.

### `list_ocpp_documents`

All ingested documents with stats. No parameters.

Returns one line per document: title, chunk count, entity count, type.

### `search_ocpp_by_section`

Chunks matching section title (case-insensitive), with optional evidence filters.

| Field | Type | Required |
|-------|------|----------|
| `section_title` | string | yes |
| `top_k` | integer | no (default 10, max 20) |
| `evidence_layer` | string | no |
| `source_type` | string | no |
| `max_chars` | integer | no (default 800, max 4000) |

Returns chunks with page numbers.

---

## Recommended Agent Usage

For implementation work:

1. Call `inspect_ocpp_corpus` to verify the backend is indexed.
2. Call `get_ocpp_evidence_pack` for the feature question.
3. Call `get_ocpp_chunk` for any chunk that needs full context.
4. Produce implementation guidance with explicit evidence gaps.

Example feature prompt for a coding agent:

```json
{
  "feature": "Section R DER control",
  "top_k": 16
}
```

For debugging retrieval quality:

```json
{
  "query": "BootNotification purpose implementation conformance",
  "top_k": 8,
  "evidence_layer": "spec"
}
```

For schema-only checks:

```json
{
  "query": "BootNotificationRequest required fields JSON schema",
  "top_k": 8,
  "evidence_layer": "schema"
}
```

### Codex-Assisted Golden Answer Benchmark

Use this workflow when Codex should generate benchmark Markdown answers from MCP
evidence without an OpenAI API key and without a DeepSeek generation call.

1. Use MCP evidence tools from Codex:
   - `inspect_ocpp_corpus`
   - `build_ocpp_implementation_brief`
   - `get_ocpp_evidence_pack`
   - `get_ocpp_chunk` when a cited chunk needs full context
2. Ask Codex to write one Markdown file per golden answer case under a provider
   directory, for example `reports/golden_answers_codex-only/`.
3. Keep the exact golden answer filenames:
   - `R-FUSION-DER-IMPLEMENTATION-ANSWER.md`
   - `Q-FUSION-V2X-IMPLEMENTATION-ANSWER.md`
   - `K-FUSION-SMART-CHARGING-IMPLEMENTATION-ANSWER.md`
4. Each answer must contain these H2 headings:
   - `Purpose`
   - `Normative behavior`
   - `Implementation guidance`
   - `Conformance-test focus`
   - `Evidence gaps`
5. Score the saved answers offline:

```bash
HF_HOME=./models .venv/bin/rag eval-answers \
  --from-answers-dir \
  --answers-dir reports/golden_answers_codex-only \
  --output reports/ocpp21-ed2-rqk-golden-answers-codex-only.md
```

The command above reads Markdown files only. It does not call DeepSeek, OpenAI, or
any other generation provider.

---

## Configuration

All examples assume the repo venv has been installed with:

```bash
pip install -e ".[dev]"
```

Use repo-local Hugging Face cache so agents do not write to `~/.cache`:

```json
"HF_HOME": "./models"
```

If PostgreSQL is exposed through the project Docker Compose defaults, use:

```json
"PG_PORT": "55432"
```

### Codex / Generic MCP Client

Use `rag-mcp` when the Python environment is active. For clients that do not
activate the venv automatically, call the script by absolute path:

```json
{
  "mcpServers": {
    "rag-kag-ocpp": {
      "command": "/home/ming/workspace/rag-kag-emobility.git/.venv/bin/rag-mcp",
      "env": {
        "PG_HOST": "localhost",
        "PG_PORT": "55432",
        "PG_DATABASE": "rag_kag",
        "PG_USER": "rag_kag",
        "PG_PASSWORD": "rag_kag",
        "HF_HOME": "/home/ming/workspace/rag-kag-emobility.git/models"
      }
    }
  }
}
```

### DeepSeek TUI

`~/.deepseek/mcp.json`:
```json
{
  "mcpServers": {
    "rag-kag-ocpp": {
      "command": "rag-mcp",
      "env": {
        "PG_HOST": "localhost",
        "PG_PORT": "55432",
        "PG_PASSWORD": "rag_kag",
        "HF_HOME": "./models"
      }
    }
  }
}
```

Verify:
```bash
deepseek mcp validate
deepseek mcp tools
```

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "rag-kag-ocpp": {
      "command": "rag-mcp",
      "env": {
        "PG_HOST": "localhost",
        "PG_PORT": "55432",
        "PG_PASSWORD": "rag_kag",
        "HF_HOME": "./models"
      }
    }
  }
}
```

### Cursor

`.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "rag-kag-ocpp": {
      "command": "rag-mcp",
      "env": {
        "PG_HOST": "localhost",
        "PG_PORT": "55432",
        "PG_PASSWORD": "rag_kag",
        "HF_HOME": "./models"
      }
    }
  }
}
```

---

## Architecture

```
src/rag_ocpp/mcp/server.py
  TOOLS                9 tool definitions (JSON schemas)
  OcppKnowledgeServer  Pool + retriever + stores + model lifecycle
  _search/_chunk/...   Async handler per tool
  main()               stdio loop entry point
```

Reuses: VectorStore, GraphStore, HybridRetriever, EmbeddingModel, CrossEncoderReranker.
The implementation brief and evidence-pack tools do not call DeepSeek or any
other generation provider.

Startup: config → pool → embedding model → reranker → retriever → stdio loop.
Shutdown: close pool, unload models.

---

## Prerequisites

PostgreSQL running with data ingested. MCP server reads `config/default.yaml` + `.env`.

---

## Limitations

- Stdio only (HTTP variant: add `rag-mcp-http`)
- OCPP 2.1 only (hardcoded protocol_id=1)
- No ingest tools by design; agents query and improve from evidence, but do not mutate the corpus.
- First start downloads HF models unless `HF_HOME=./models` already contains the cache.
