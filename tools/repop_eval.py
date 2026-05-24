"""Re-populate queries.jsonl with chunk UUIDs from current DB."""
import asyncio, json, asyncpg
from rag_ocpp.config import get_config, load_config
from rag_ocpp.storage.vector import VectorStore, _prepare_tsquery

async def repop():
    load_config(); cfg = get_config()
    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn)
    store = VectorStore(pool)

    with open("data/eval/queries.jsonl") as f:
        queries = [json.loads(l) for l in f if l.strip()]

    updated = []
    for q in queries:
        results = await store.keyword_search(q["query"], top_k=5)
        ids = [str(r.chunk_id) for r in results]
        updated.append({"query": q["query"], "relevant": ids})
        print(f"{q['query'][:60]}: {len(ids)} new UUIDs")

    with open("data/eval/queries.jsonl", "w") as f:
        for u in updated:
            f.write(json.dumps(u) + "\n")
    print(f"\nDone. {len(updated)} queries updated.")
    await pool.close()

asyncio.run(repop())
