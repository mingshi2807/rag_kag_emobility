"""Re-embed all chunks with current model (for model upgrades, no re-ingest)."""
import asyncio, asyncpg, numpy as np
from rag_ocpp.config import load_config, get_config
from rag_ocpp.embedding.model import EmbeddingModel

async def reembed():
    load_config(); cfg = get_config()
    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn, min_size=2, max_size=4)
    emb = EmbeddingModel(cfg.embedding); emb.load()

    # Drop old embeddings (768-dim) so we can re-insert 1024-dim
    await pool.execute("UPDATE chunks SET embedding = NULL")
    total = await pool.fetchval("SELECT COUNT(*) FROM chunks")
    print(f"Re-embedding {total} chunks with {cfg.embedding.model_name} (1024-dim)...")

    batch_size = cfg.embedding.batch_size
    offset = 0; updated = 0
    while offset < total:
        rows = await pool.fetch(
            "SELECT id, content FROM chunks ORDER BY chunk_index LIMIT $1 OFFSET $2",
            batch_size, offset)
        if not rows: break
        texts = [r["content"] for r in rows]
        ids = [r["id"] for r in rows]
        vectors = emb.embed_batch(texts, normalize=cfg.embedding.normalize)
        vec_strs = ["[" + ",".join(str(float(x)) for x in v) + "]" for v in vectors]
        async with pool.acquire() as conn:
            await conn.executemany("UPDATE chunks SET embedding = $1 WHERE id = $2",
                                   [(vs, uid) for vs, uid in zip(vec_strs, ids)])
        updated += len(rows)
        print(f"  {updated}/{total} ({100*updated//total}%)")
        offset += batch_size

    # Rebuild HNSW index (drops + recreates)
    await pool.execute("DROP INDEX IF EXISTS chunks_embedding_idx")
    await pool.execute("CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=200)")
    print(f"Done. {updated} chunks re-embedded + index rebuilt.")
    await pool.close()

if __name__ == "__main__":
    asyncio.run(reembed())
