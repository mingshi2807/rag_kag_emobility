"""MCP server — exposes RAG/KAG tools for coding agents (Claude, Cursor, etc.)."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import asyncpg
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from rag_ocpp.config import get_config, load_config
from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.retrieval.hybrid import HybridRetriever, SearchFilters
from rag_ocpp.retrieval.reranker import CrossEncoderReranker
from rag_ocpp.storage.graph import GraphStore
from rag_ocpp.storage.vector import VectorStore

logger = logging.getLogger(__name__)

TOOLS = [
    Tool(name="search_ocpp_knowledge",
         description="Search OCPP 2.1 knowledge base using hybrid retrieval (vector+keyword+graph). Returns top-k chunks with citations.",
         inputSchema={"type":"object","properties":{"query":{"type":"string","description":"Search query"},"top_k":{"type":"integer","default":5}},"required":["query"]}),
    Tool(name="get_ocpp_chunk",
         description="Get full content of a chunk by UUID.",
         inputSchema={"type":"object","properties":{"chunk_id":{"type":"string"}},"required":["chunk_id"]}),
    Tool(name="list_ocpp_entities",
         description="List OCPP entities by optional type filter.",
         inputSchema={"type":"object","properties":{"entity_type":{"type":"string","description":"command,datatype,component,variable,enum,functional_block,error_code,test_case"},"limit":{"type":"integer","default":20}}}),
    Tool(name="get_ocpp_entity",
         description="Get entity details by name with relationships.",
         inputSchema={"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}),
    Tool(name="list_ocpp_documents",
         description="List all ingested documents with stats.",
         inputSchema={"type":"object","properties":{}}),
    Tool(name="search_ocpp_by_section",
         description="Search chunks by section title.",
         inputSchema={"type":"object","properties":{"section_title":{"type":"string"},"top_k":{"type":"integer","default":10}},"required":["section_title"]}),
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
    r = await srv.retriever.retrieve(args["query"])
    lines = [f"{len(r.chunks)} chunks ({r.strategy_breakdown}):\n"]
    for i, c in enumerate(r.chunks):
        src = c.section_title or "Section"
        page = f" p.{c.page_start}" if c.page_start else ""
        lines.append(f"[{i+1}] [{src}]{page} ({c.strategy}, {c.score:.3f})\n    {c.content[:300]}...\n")
    return "\n".join(lines)

async def _chunk(srv, args):
    row = await srv.pool.fetchrow("SELECT content, section_title, page_start, page_end, strategy FROM chunks WHERE id=$1", UUID(args["chunk_id"]))
    if not row: return "Not found."
    return f"Section: {row['section_title'] or 'N/A'}\nPages: {row['page_start']}-{row['page_end']}\nStrategy: {row['strategy']}\n\n{row['content']}"

async def _entities(srv, args):
    tmap = {"command":1,"datatype":2,"component":3,"variable":4,"enum":5,"functional_block":7,"error_code":8,"test_case":9}
    tid = tmap.get(args.get("entity_type"))
    limit = min(args.get("limit",20), 100)
    if tid:
        rows = await srv.pool.fetch("SELECT name, description FROM entities WHERE protocol_id=1 AND type_id=$1 ORDER BY name LIMIT $2", tid, limit)
    else:
        rows = await srv.pool.fetch("SELECT e.name, et.name as t FROM entities e JOIN entity_types et ON et.id=e.type_id WHERE e.protocol_id=1 ORDER BY et.name, e.name LIMIT $1", limit)
    if not rows: return "No entities."
    return "\n".join(f"  [{r.get('t',args.get('entity_type',''))}] {r['name']}" for r in rows)

async def _entity(srv, args):
    e = await srv.graph_store.find_entity(protocol_id=1, name=args["name"])
    if not e:
        cs = await srv.graph_store.find_entity_fuzzy(protocol_id=1, name=args["name"], threshold=0.3, limit=3)
        return f"Not found. Did you mean: {', '.join(c.name for c in cs)}?" if cs else "Not found."
    rels = await srv.graph_store.get_relationships(e.id, direction="both")
    chunks = await srv.graph_store.get_chunks_for_entity(e.id, top_k=5)
    out = [f"**{e.name}** (type_id={e.type_id})", f"Description: {e.description or 'N/A'}",
           f"Aliases: {e.aliases}", f"Linked chunks: {len(chunks)}", f"Relationships ({len(rels)}):"]
    for r in rels: out.append(f"  {r.rel_type} → {r.target_id}" if r.source_id==e.id else f"  ← {r.rel_type} {r.source_id}")
    return "\n".join(out)

async def _docs(srv, args):
    rows = await srv.vector_store.list_documents(protocol_id=1)
    if not rows: return "No documents."
    return "\n".join(f"  {r['title'] or r['source_path']} — {r['chunk_count']} chunks, {r['entity_count']} entities" for r in rows)

async def _section(srv, args):
    rows = await srv.pool.fetch("SELECT content, page_start, page_end FROM chunks WHERE section_title ILIKE $1 LIMIT $2", f"%{args['section_title']}%", min(args.get("top_k",10), 20))
    if not rows: return f"No chunks for '{args['section_title']}'."
    return "\n\n".join(f"[p.{r['page_start']}] {r['content'][:300]}..." for r in rows)


async def main():
    logging.basicConfig(level=logging.WARNING)
    srv = Server("rag-kag-ocpp")
    ocpp = OcppKnowledgeServer(); await ocpp.start()

    @srv.list_tools()
    async def lt(): return TOOLS

    @srv.call_tool()
    async def ct(name: str, arguments: dict | None):
        args = arguments or {}
        handlers = {"search_ocpp_knowledge":_search,"get_ocpp_chunk":_chunk,"list_ocpp_entities":_entities,
                    "get_ocpp_entity":_entity,"list_ocpp_documents":_docs,"search_ocpp_by_section":_section}
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
