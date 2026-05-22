"""CLI eval — `rag eval <queries.jsonl>` command."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

import asyncpg
import typer

from rag_ocpp.config import get_config, load_config
from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.eval.metrics import EvalQuery, evaluate
from rag_ocpp.retrieval.hybrid import HybridRetriever
from rag_ocpp.retrieval.reranker import CrossEncoderReranker

def eval_retrieval(
    queries_path: str = typer.Argument(..., help="queries.jsonl"),
    top_k: int = typer.Option(10, "--top-k", "-k"),
):
    """Evaluate retrieval against ground-truth queries.

    queries.jsonl: {"query":"...","relevant":["uuid1","uuid2"]}
    """
    asyncio.run(_eval_async(queries_path, top_k))


async def _eval_async(queries_path: str, top_k: int):
    load_config(); cfg = get_config()
    logging.basicConfig(level=getattr(logging, cfg.logging.level))

    path = Path(queries_path)
    if not path.exists():
        typer.echo(f"Not found: {path}"); raise typer.Exit(1)

    queries: list[EvalQuery] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            obj = json.loads(line)
            queries.append(EvalQuery(query=obj["query"], relevant_chunk_ids=obj["relevant"]))

    typer.echo(f"Loaded {len(queries)} queries.\n")

    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn); assert pool
    try:
        emb = EmbeddingModel(cfg.embedding); emb.load()
        reranker = CrossEncoderReranker(cfg.reranker); reranker.load()
        retriever = HybridRetriever(pool=pool, embedding_model=emb, reranker=reranker, final_top_k=top_k)

        retrieved: list[list[str]] = []
        t0 = time.monotonic()

        for i, q in enumerate(queries):
            result = await retriever.retrieve(q.query)
            cids = [str(c.chunk_id) for c in result.chunks]
            retrieved.append(cids)
            hits = sum(1 for c in cids if c in q.relevant_chunk_ids)
            typer.echo(f"[{i+1}/{len(queries)}] {q.query[:60]} → {hits}/{len(q.relevant_chunk_ids)} hits")

        elapsed = time.monotonic() - t0
        m = evaluate(queries, retrieved)

        typer.echo(f"\n{'='*50}")
        typer.echo(f"Queries:   {m.num_queries}")
        typer.echo(f"MRR:       {m.mrr:.4f}")
        typer.echo(f"Recall@5:  {m.recall_at_5:.4f}")
        typer.echo(f"Recall@10: {m.recall_at_10:.4f}")
        typer.echo(f"NDCG@10:   {m.ndcg_at_10:.4f}")
        typer.echo(f"Time:      {elapsed:.1f}s ({elapsed/len(queries):.1f}s/q)")

    finally:
        await pool.close()
