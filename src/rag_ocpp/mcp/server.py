"""MCP server — exposes RAG/KAG tools for coding agents (Codex, Claude, Cursor, etc.)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

import asyncpg
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from rag_ocpp.config import get_config, load_config
from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.privacy import configure_redacted_logging
from rag_ocpp.retrieval.hybrid import HybridRetriever, SearchFilters
from rag_ocpp.retrieval.reranker import CrossEncoderReranker
from rag_ocpp.storage.graph import GraphStore
from rag_ocpp.storage.vector import VectorStore

logger = logging.getLogger(__name__)

EVIDENCE_LAYERS = ["spec", "device_model", "schema"]
SOURCE_TYPES = ["spec_pdf", "device_model_table", "json_schema", "appendix_csv"]

TOOLS = [
    Tool(
        name="search_ocpp_knowledge",
        description=(
            "Search the OCPP 2.1 Ed2 knowledge base using hybrid retrieval. "
            "Supports evidence-layer filters for spec, Device Model, and JSON schema."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {"type": "integer", "default": 8, "minimum": 1, "maximum": 20},
                "evidence_layer": {
                    "type": "string",
                    "enum": EVIDENCE_LAYERS,
                    "description": "Optional evidence layer filter.",
                },
                "source_type": {
                    "type": "string",
                    "enum": SOURCE_TYPES,
                    "description": "Optional source type filter.",
                },
                "doc_type": {"type": "string", "description": "Optional document type filter."},
                "max_chars": {
                    "type": "integer",
                    "default": 1200,
                    "minimum": 200,
                    "maximum": 6000,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_ocpp_evidence_pack",
        description=(
            "Retrieve a source-aware evidence pack for a coding agent. Groups chunks by "
            "spec, Device Model, schema, and unknown evidence layers."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 12, "minimum": 1, "maximum": 20},
                "max_chars": {
                    "type": "integer",
                    "default": 1800,
                    "minimum": 200,
                    "maximum": 8000,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="build_ocpp_implementation_brief",
        description=(
            "Build a Markdown implementation brief from retrieved OCPP evidence. "
            "Use this when a coding agent needs spec + Device Model + schema guidance."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "feature": {"type": "string", "description": "Feature or protocol area."},
                "query": {
                    "type": "string",
                    "description": "Optional exact retrieval query. Defaults to a fusion implementation query.",
                },
                "top_k": {"type": "integer", "default": 14, "minimum": 1, "maximum": 20},
                "max_chars": {
                    "type": "integer",
                    "default": 1600,
                    "minimum": 200,
                    "maximum": 6000,
                },
            },
            "required": ["feature"],
        },
    ),
    Tool(
        name="inspect_ocpp_corpus",
        description="Return corpus/index health, evidence-layer counts, embedding counts, and model dimensions.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_ocpp_chunk",
        description="Get full content and metadata of a chunk by UUID.",
        inputSchema={
            "type": "object",
            "properties": {"chunk_id": {"type": "string"}},
            "required": ["chunk_id"],
        },
    ),
    Tool(
        name="list_ocpp_entities",
        description="List OCPP entities by optional type filter.",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": (
                        "message,request,response,field,attribute,requirement,schema,"
                        "command,datatype,component,variable,enum,functional_block,error_code,test_case"
                    ),
                },
                "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
            },
        },
    ),
    Tool(
        name="get_ocpp_entity",
        description="Get entity details by name with relationships and linked chunks.",
        inputSchema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    ),
    Tool(
        name="list_ocpp_documents",
        description="List all indexed documents with stats.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="search_ocpp_by_section",
        description="Search chunks by section title with optional evidence-layer/source filters.",
        inputSchema={
            "type": "object",
            "properties": {
                "section_title": {"type": "string"},
                "top_k": {"type": "integer", "default": 10, "minimum": 1, "maximum": 20},
                "evidence_layer": {"type": "string", "enum": EVIDENCE_LAYERS},
                "source_type": {"type": "string", "enum": SOURCE_TYPES},
                "max_chars": {
                    "type": "integer",
                    "default": 800,
                    "minimum": 100,
                    "maximum": 4000,
                },
            },
            "required": ["section_title"],
        },
    ),
]


class OcppKnowledgeServer:
    def __init__(self):
        self.pool: asyncpg.Pool | None = None
        self.retriever: HybridRetriever | None = None
        self.vector_store: VectorStore | None = None
        self.graph_store: GraphStore | None = None

    async def start(self):
        load_config(); cfg = get_config()
        self.pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn, min_size=2, max_size=10)
        embedding = EmbeddingModel(cfg.embedding); embedding.load()
        reranker = CrossEncoderReranker(cfg.reranker); reranker.load()
        self.retriever = HybridRetriever(pool=self.pool, embedding_model=embedding, reranker=reranker, final_top_k=20)
        self.vector_store = VectorStore(self.pool)
        self.graph_store = GraphStore(self.pool)
        logger.info("MCP server started.")

    async def stop(self):
        if self.pool: await self.pool.close()


async def _search(srv, args):
    top_k = _clamp_int(args.get("top_k", 8), 1, 20)
    max_chars = _clamp_int(args.get("max_chars", 1200), 200, 6000)
    filters = _filters(args)
    r = await srv.retriever.retrieve(args["query"], filters=filters)
    chunks = r.chunks[:top_k]
    lines = [
        f"# OCPP Knowledge Search\n\nQuery: `{args['query']}`\n\n"
        f"Returned: `{len(chunks)}` chunks. Strategy breakdown: `{r.strategy_breakdown}`.\n"
    ]
    for i, c in enumerate(chunks, 1):
        lines.append(_format_chunk(c, i, max_chars=max_chars))
    return "\n".join(lines)


async def _evidence_pack(srv, args):
    top_k = _clamp_int(args.get("top_k", 12), 1, 20)
    max_chars = _clamp_int(args.get("max_chars", 1800), 200, 8000)
    r = await srv.retriever.retrieve(args["query"])
    chunks = r.chunks[:top_k]
    groups: dict[str, list[Any]] = {"spec": [], "device_model": [], "schema": [], "unknown": []}
    for chunk in chunks:
        layer = (chunk.metadata or {}).get("evidence_layer") or "unknown"
        groups.setdefault(layer, []).append(chunk)

    lines = [
        "# OCPP Evidence Pack",
        "",
        f"Query: `{args['query']}`",
        f"Strategy breakdown: `{r.strategy_breakdown}`",
        "",
        "Use this as source evidence. Do not invent fields, enum values, or requirements.",
    ]
    for layer in ["spec", "device_model", "schema", "unknown"]:
        if not groups.get(layer):
            continue
        lines.extend(["", f"## {layer}", ""])
        for i, chunk in enumerate(groups[layer], 1):
            lines.append(_format_chunk(chunk, i, max_chars=max_chars))
    return "\n".join(lines)


async def _implementation_brief(srv, args):
    feature = args["feature"]
    query = args.get("query") or (
        f"For {feature} implementation in OCPP 2.1 Ed2, combine Part 2 normative "
        "behavior, Device Model components/variables, and JSON schema validation. "
        "Provide senior backend developer guidance."
    )
    pack = await _evidence_pack(
        srv,
        {
            "query": query,
            "top_k": args.get("top_k", 14),
            "max_chars": args.get("max_chars", 1600),
        },
    )
    return (
        f"# {feature} Implementation Brief\n\n"
        "## Instructions For The Coding Agent\n\n"
        "- Produce Markdown only.\n"
        "- Separate direct evidence from evidence-grounded synthesis.\n"
        "- Cover: Purpose, Normative behavior, Data model/schema, Device Model mapping, "
        "Backend sequence, Error handling, Smoke tests, Conformance-test focus, Evidence gaps.\n"
        "- Do not invent missing fields, enum values, or protocol requirements.\n"
        "- Distinguish Charging Station behavior from CSMS behavior.\n\n"
        f"{pack}"
    )


async def _corpus_status(srv, args):
    source_rows = await srv.pool.fetch(
        """
        SELECT metadata->>'evidence_layer' AS evidence_layer, source_type, count(*) AS count
        FROM source_documents
        GROUP BY 1,2
        ORDER BY 1,2
        """
    )
    chunk_rows = await srv.pool.fetch(
        """
        SELECT metadata->>'evidence_layer' AS evidence_layer,
               metadata->>'source_type' AS source_type,
               count(*) AS chunks,
               count(embedding) AS embeddings
        FROM chunks
        GROUP BY 1,2
        ORDER BY 1,2
        """
    )
    dim_rows = await srv.pool.fetch(
        """
        SELECT vector_dims(embedding) AS dims, count(*) AS count
        FROM chunks
        WHERE embedding IS NOT NULL
        GROUP BY 1
        ORDER BY 1
        """
    )
    totals = await srv.pool.fetchrow(
        """
        SELECT
          (SELECT count(*) FROM source_documents) AS sources,
          (SELECT count(*) FROM corpus_records) AS records,
          (SELECT count(*) FROM chunks) AS chunks,
          (SELECT count(embedding) FROM chunks) AS embeddings,
          (SELECT count(*) FROM chunk_entities) AS entity_links,
          (SELECT count(*) FROM relationships) AS relationships
        """
    )
    lines = [
        "# OCPP Corpus Status",
        "",
        "## Totals",
        "",
        _json_block(dict(totals or {})),
        "",
        "## Source Documents By Evidence Layer",
        "",
        _json_block([dict(r) for r in source_rows]),
        "",
        "## Chunks By Evidence Layer",
        "",
        _json_block([dict(r) for r in chunk_rows]),
        "",
        "## Embedding Dimensions",
        "",
        _json_block([dict(r) for r in dim_rows]),
    ]
    return "\n".join(lines)


async def _chunk(srv, args):
    row = await srv.pool.fetchrow(
        """
        SELECT content, section_title, page_start, page_end, strategy, metadata
        FROM chunks
        WHERE id=$1
        """,
        UUID(args["chunk_id"]),
    )
    if not row: return "Not found."
    metadata = _metadata(row["metadata"])
    return (
        f"# OCPP Chunk\n\n"
        f"- Section: `{row['section_title'] or 'N/A'}`\n"
        f"- Pages: `{row['page_start']}-{row['page_end']}`\n"
        f"- Strategy: `{row['strategy']}`\n"
        f"- Evidence layer: `{metadata.get('evidence_layer', 'unknown')}`\n"
        f"- Source type: `{metadata.get('source_type', 'unknown')}`\n"
        f"- Source path: `{metadata.get('source_path', 'unknown')}`\n\n"
        "## Metadata\n\n"
        f"{_json_block(metadata)}\n\n"
        "## Content\n\n"
        f"{row['content']}"
    )

async def _entities(srv, args):
    tmap = {
        "command": 1, "datatype": 2, "component": 3, "variable": 4, "enum": 5,
        "functional_block": 7, "error_code": 8, "test_case": 9,
        "message": 10, "request": 11, "response": 12, "field": 13,
        "attribute": 14, "requirement": 15, "schema": 16,
    }
    tid = tmap.get(args.get("entity_type"))
    limit = _clamp_int(args.get("limit",20), 1, 100)
    if tid:
        rows = await srv.pool.fetch("SELECT name, description FROM entities WHERE protocol_id=1 AND type_id=$1 ORDER BY name LIMIT $2", tid, limit)
    else:
        rows = await srv.pool.fetch("SELECT e.name, et.name as t FROM entities e JOIN entity_types et ON et.id=e.type_id WHERE e.protocol_id=1 ORDER BY et.name, e.name LIMIT $1", limit)
    if not rows: return "No entities."
    lines = ["# OCPP Entities", ""]
    for row in rows:
        row_dict = dict(row)
        lines.append(f"- [{row_dict.get('t', args.get('entity_type', ''))}] {row_dict['name']}")
    return "\n".join(lines)

async def _entity(srv, args):
    e = await srv.graph_store.find_entity(protocol_id=1, name=args["name"])
    if not e:
        cs = await srv.graph_store.find_entity_fuzzy(protocol_id=1, name=args["name"], threshold=0.3, limit=3)
        return f"Not found. Did you mean: {', '.join(c.name for c in cs)}?" if cs else "Not found."
    rels = await srv.graph_store.get_relationships(e.id, direction="both")
    chunks = await srv.graph_store.get_chunks_for_entity(e.id, top_k=5)
    out = [f"# {e.name}", "", f"- Type ID: `{e.type_id}`", f"- Description: {e.description or 'N/A'}",
           f"- Aliases: `{e.aliases}`", f"- Linked chunks: `{len(chunks)}`", "", f"## Relationships ({len(rels)})"]
    for r in rels: out.append(f"  {r.rel_type} → {r.target_id}" if r.source_id==e.id else f"  ← {r.rel_type} {r.source_id}")
    if chunks:
        out.extend(["", "## Linked Chunks"])
        for i, c in enumerate(chunks, 1):
            out.append(
                f"{i}. `{c.chunk_id}` — {c.section_title or 'Section'}"
                f"{f' p.{c.page_start}' if c.page_start else ''}"
            )
    return "\n".join(out)

async def _docs(srv, args):
    rows = await srv.vector_store.list_documents(protocol_id=1)
    if not rows: return "No documents."
    return "\n".join(f"  {r['title'] or r['source_path']} — {r['chunk_count']} chunks, {r['entity_count']} entities" for r in rows)

async def _section(srv, args):
    top_k = _clamp_int(args.get("top_k", 10), 1, 20)
    max_chars = _clamp_int(args.get("max_chars", 800), 100, 4000)
    evidence_layer = _optional_choice(args, "evidence_layer", EVIDENCE_LAYERS)
    source_type = _optional_choice(args, "source_type", SOURCE_TYPES)
    rows = await srv.pool.fetch(
        """
        SELECT id, content, section_title, page_start, page_end, metadata
        FROM chunks
        WHERE section_title ILIKE $1
          AND ($2::text IS NULL OR metadata->>'evidence_layer' = $2)
          AND ($3::text IS NULL OR metadata->>'source_type' = $3)
        ORDER BY page_start NULLS LAST, section_title
        LIMIT $4
        """,
        f"%{args['section_title']}%",
        evidence_layer,
        source_type,
        top_k,
    )
    if not rows: return f"No chunks for '{args['section_title']}'."
    lines = [f"# Section Search\n\nSection title contains: `{args['section_title']}`\n"]
    for i, r in enumerate(rows, 1):
        metadata = _metadata(r["metadata"])
        lines.append(
            f"## {i}. {r['section_title'] or 'Section'}\n\n"
            f"- Chunk ID: `{r['id']}`\n"
            f"- Page: `{r['page_start']}`\n"
            f"- Evidence layer: `{metadata.get('evidence_layer', 'unknown')}`\n"
            f"- Source type: `{metadata.get('source_type', 'unknown')}`\n"
            f"- Source path: `{metadata.get('source_path', 'unknown')}`\n\n"
            f"{_clip(r['content'], max_chars)}"
        )
    return "\n\n".join(lines)


def _filters(args: dict[str, Any]) -> SearchFilters:
    return SearchFilters(
        doc_type=args.get("doc_type"),
        evidence_layer=_optional_choice(args, "evidence_layer", EVIDENCE_LAYERS),
        source_type=_optional_choice(args, "source_type", SOURCE_TYPES),
    )


def _optional_choice(args: dict[str, Any], key: str, allowed: list[str]) -> str | None:
    value = args.get(key)
    if value is None or value == "":
        return None
    if value not in allowed:
        raise ValueError(f"{key} must be one of: {', '.join(allowed)}")
    return value


def _clamp_int(value: Any, lower: int, upper: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = lower
    return max(lower, min(parsed, upper))


def _metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _source_label(metadata: dict[str, Any]) -> str:
    return metadata.get("source_path") or metadata.get("source_type") or "unknown source"


def _format_chunk(chunk, index: int, *, max_chars: int) -> str:
    metadata = chunk.metadata or {}
    page = f" p.{chunk.page_start}" if chunk.page_start else ""
    return (
        f"## {index}. {chunk.section_title or 'Section'}{page}\n\n"
        f"- Chunk ID: `{chunk.chunk_id}`\n"
        f"- Document ID: `{chunk.document_id}`\n"
        f"- Score: `{chunk.score:.3f}`\n"
        f"- Strategy: `{chunk.strategy}`\n"
        f"- Evidence layer: `{metadata.get('evidence_layer', 'unknown')}`\n"
        f"- Source type: `{metadata.get('source_type', 'unknown')}`\n"
        f"- Source: `{_source_label(metadata)}`\n\n"
        f"{_clip(chunk.content, max_chars)}\n"
    )


def _clip(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n..."


def _json_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, indent=2, default=str) + "\n```"


async def main():
    load_config()
    cfg = get_config()
    configure_redacted_logging(
        level=logging.WARNING,
        enabled=cfg.logging.redaction_enabled,
    )
    srv = Server("rag-kag-ocpp")
    ocpp = OcppKnowledgeServer(); await ocpp.start()

    @srv.list_tools()
    async def lt(): return TOOLS

    @srv.call_tool()
    async def ct(name: str, arguments: dict | None):
        args = arguments or {}
        handlers = {
            "search_ocpp_knowledge": _search,
            "get_ocpp_evidence_pack": _evidence_pack,
            "build_ocpp_implementation_brief": _implementation_brief,
            "inspect_ocpp_corpus": _corpus_status,
            "get_ocpp_chunk": _chunk,
            "list_ocpp_entities": _entities,
            "get_ocpp_entity": _entity,
            "list_ocpp_documents": _docs,
            "search_ocpp_by_section": _section,
        }
        h = handlers.get(name)
        if not h: return [TextContent(type="text", text=f"Unknown: {name}")]
        try:
            return [TextContent(type="text", text=await h(ocpp, args))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    async with stdio_server() as (rs, ws):
        await srv.run(rs, ws, srv.create_initialization_options())
    await ocpp.stop()

if __name__ == "__main__":
    asyncio.run(main())


# Sync wrapper for console_scripts entry point
def main_cli() -> None:
    asyncio.run(main())
