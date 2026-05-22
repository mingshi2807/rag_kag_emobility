# MCP Server — RAG/KAG OCPP 2.1

> Transport: stdio | Entry: `rag-mcp` | Source: `src/rag_ocpp/mcp/server.py`

---

## What It Does

Exposes the knowledge base as MCP tools for any MCP-compatible agent (DeepSeek TUI, Claude Desktop, Cursor).

```
Agent → stdio → rag-mcp → PostgreSQL + pgvector
```

---

## Tools (6)

### `search_ocpp_knowledge`

Hybrid retrieval (vector + keyword + graph) → RRF fusion → cross-encoder rerank.

| Field | Type | Required |
|-------|------|----------|
| `query` | string | yes |
| `top_k` | integer | no (default 5, max 20) |

Returns ranked chunks with section, page, strategy, and score.

### `get_ocpp_chunk`

Full chunk content by UUID.

| Field | Type | Required |
|-------|------|----------|
| `chunk_id` | string | yes |

Returns content with section title, page range, chunking strategy.

### `list_ocpp_entities`

List entities, optionally filtered by type.

| Field | Type | Required |
|-------|------|----------|
| `entity_type` | string | no (command, datatype, component, variable, enum, functional_block, error_code, test_case) |
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

Chunks matching section title (case-insensitive).

| Field | Type | Required |
|-------|------|----------|
| `section_title` | string | yes |
| `top_k` | integer | no (default 10, max 20) |

Returns chunks with page numbers.

---

## Configuration

### DeepSeek TUI

`~/.deepseek/mcp.json`:
```json
{
  "mcpServers": {
    "rag-kag-ocpp": {
      "command": "rag-mcp",
      "env": {
        "PG_HOST": "localhost",
        "PG_PASSWORD": "rag_dev",
        "DEEPSEEK_API_KEY": "sk-..."
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
        "PG_PASSWORD": "rag_dev",
        "DEEPSEEK_API_KEY": "sk-..."
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
      "env": { "PG_HOST": "localhost", "PG_PASSWORD": "rag_dev" }
    }
  }
}
```

---

## Architecture

```
src/rag_ocpp/mcp/server.py
  TOOLS                6 tool definitions (JSON schemas)
  OcppKnowledgeServer  Pool + retriever + stores + model lifecycle
  _search/_chunk/...   Async handler per tool
  main()               stdio loop entry point
```

Reuses: VectorStore, GraphStore, HybridRetriever, EmbeddingModel, CrossEncoderReranker.

Startup: config → pool → embedding model → reranker → retriever → stdio loop.
Shutdown: close pool, unload models.

---

## Prerequisites

PostgreSQL running with data ingested. MCP server reads `config/default.yaml` + `.env`.

---

## Limitations

- Stdio only (HTTP variant: add `rag-mcp-http`)
- OCPP 2.1 only (hardcoded protocol_id=1)
- No ingest tools (agents query, don't add documents)
- First start downloads HF models (10-30s)
