"""One-shot fix: re-extract LLM relationships for chunks missing them."""
import asyncio

import asyncpg

from rag_ocpp.config import get_config, load_config
from rag_ocpp.knowledge.extractor import EntityExtractor
from rag_ocpp.knowledge.linker import EntityLinker


async def fix():
    load_config()
    cfg = get_config()
    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn)
    linker = EntityLinker(pool)
    extractor = EntityExtractor(enable_llm=True)

    rows = await pool.fetch("""
        SELECT c.id, c.content, c.content_hash
        FROM chunks c
        JOIN chunk_entities ce ON ce.chunk_id = c.id
        LEFT JOIN relationships r ON r.source_id = ce.entity_id
        GROUP BY c.id
        HAVING COUNT(r.id) = 0
        LIMIT 100
    """)

    print(f"Re-extracting {len(rows)} chunks with missing relationships...")
    for i, row in enumerate(rows):
        result = await extractor.extract(row["content"], row["content_hash"], force=True)
        if result.relations:
            n = await linker.resolve_relations(result.relations)
            print(f"  [{i+1}/{len(rows)}] {n} relations added")
        else:
            print(f"  [{i+1}/{len(rows)}] no relations found")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(fix())
