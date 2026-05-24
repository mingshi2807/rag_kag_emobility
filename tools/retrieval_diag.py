"""Diagnostic: per-query retrieval breakdown."""
import asyncio, json, asyncpg
from rag_ocpp.config import get_config, load_config
from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.retrieval.hybrid import HybridRetriever
from rag_ocpp.retrieval.reranker import CrossEncoderReranker

async def diag():
    load_config(); cfg = get_config()
    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn)
    emb = EmbeddingModel(cfg.embedding); emb.load()
    reranker = CrossEncoderReranker(cfg.reranker); reranker.load()
    retriever = HybridRetriever(pool=pool, embedding_model=emb, reranker=reranker, final_top_k=10)

    with open("data/eval/queries.jsonl") as f:
        queries = [json.loads(l) for l in f if l.strip()]

    for i, q in enumerate(queries[:5]):
        result = await retriever.retrieve(q["query"])
        hits = [c.chunk_id for c in result.chunks]
        rel = set(q["relevant"])
        match = sum(1 for h in hits if str(h) in rel)
        ranks = [j+1 for j,h in enumerate(hits) if str(h) in rel]
        print(f"[{i+1}] match={match}/{len(rel)} ranks={ranks} | {q['query'][:65]}")
        for rid in list(rel)[:2]:
            row = await pool.fetchrow("SELECT section_title,page_start FROM chunks WHERE id=$1", rid)
            ok = f"{row['section_title']} p.{row['page_start']}" if row else "MISSING"
            print(f"    {rid[:8]}... → {ok}")
    await pool.close()

asyncio.run(diag())
