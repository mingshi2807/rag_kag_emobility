"""Eval: keyword-search ONLY (no vector, no graph, no reranker)."""
import asyncio, json, asyncpg, time, sys
sys.path.insert(0,'/home/ming-dev/workspace/rag-kag-ocpp/src')
from rag_ocpp.storage.vector import VectorStore
from rag_ocpp.config import load_config, get_config

async def eval_kw():
    load_config(); c=get_config()
    p = await asyncpg.create_pool(dsn=c.postgres.dsn)
    vs = VectorStore(p)
    with open("data/eval/queries.jsonl") as f:
        queries = [json.loads(l) for l in f if l.strip()]
    t0=time.monotonic(); mrr=rec5=rec10=0.0; nv=0
    for q in queries:
        results = await vs.keyword_search(q["query"], top_k=10)
        cids=[str(r.chunk_id) for r in results]
        rel=set(q["relevant"])
        if rel:
            nv+=1
            for j,cid in enumerate(cids):
                if cid in rel: mrr+=1.0/(j+1); break
            h5=sum(1 for c in cids[:5] if c in rel)
            h10=sum(1 for c in cids[:10] if c in rel)
            rec5+=h5/len(rel); rec10+=h10/len(rel)
        print(f"{q['query'][:60]}: {sum(1 for c in cids[:10] if c in rel)}/{len(rel)}")
    t=time.monotonic()-t0
    print(f"\nMRR={mrr/nv:.4f} R@5={rec5/nv:.4f} R@10={rec10/nv:.4f} ({nv}q, {t:.1f}s)")
    await p.close()
asyncio.run(eval_kw())
