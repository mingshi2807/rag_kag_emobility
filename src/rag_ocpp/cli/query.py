"""CLI query — `rag query <text>` command."""

from __future__ import annotations

import asyncio
import logging
import time

import asyncpg
import typer

from rag_ocpp.config import get_config, load_config
from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.generation.client import DeepSeekClient
from rag_ocpp.retrieval.hybrid import HybridRetriever, SearchFilters
from rag_ocpp.retrieval.reranker import CrossEncoderReranker

query_app = typer.Typer(no_args_is_help=True)


@query_app.command()
def query(
    query_text: str = typer.Argument(..., help="Your question about OCPP 2.1"),
    top_k: int = typer.Option(5, "--top-k", "-k"),
    stream: bool = typer.Option(False, "--stream", "-s"),
    doc_type: str = typer.Option(None, "--doc-type"),
):
    """Query the OCPP 2.1 knowledge base."""
    asyncio.run(_query_async(query_text, top_k, stream, doc_type))


async def _query_async(query_text, top_k, stream, doc_type):
    load_config(); cfg = get_config()
    logging.basicConfig(level=getattr(logging, cfg.logging.level))

    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn)
    assert pool

    try:
        embedding = EmbeddingModel(cfg.embedding); embedding.load()
        reranker = CrossEncoderReranker(cfg.reranker); reranker.load()
        retriever = HybridRetriever(pool=pool, embedding_model=embedding, reranker=reranker, final_top_k=top_k)
        llm = DeepSeekClient(cfg.deepseek)

        t0 = time.monotonic()
        retrieval = await retriever.retrieve(query_text, filters=SearchFilters(doc_type=doc_type))
        rms = int((time.monotonic() - t0) * 1000)

        typer.echo(f"\n{len(retrieval.chunks)} chunks ({retrieval.strategy_breakdown}) in {rms}ms\n")
        typer.echo("─" * 60)
        for i, c in enumerate(retrieval.chunks):
            src = f"[{c.section_title or 'Section'}]"
            if c.page_start: src += f" p.{c.page_start}"
            typer.echo(f"  [{i+1}] {src} ({c.strategy}, {c.score:.3f})")
            typer.echo(f"      {c.content[:120]}...")
        typer.echo("─" * 60)

        ctx = [{"content": c.content, "section_title": c.section_title or "Section",
                "document_title": str(c.document_id)[:36], "page_start": c.page_start}
               for c in retrieval.chunks]

        if stream:
            typer.echo("\nAnswer:\n")
            async for token in llm.generate_stream(query_text, ctx):
                typer.echo(token, nl=False)
            typer.echo()
        else:
            typer.echo("\nGenerating...")
            answer = await llm.generate(query_text, ctx)
            typer.echo(f"\n{answer}\n")

        typer.echo(f"(total: {int((time.monotonic()-t0)*1000)}ms)")
    finally:
        await pool.close()
