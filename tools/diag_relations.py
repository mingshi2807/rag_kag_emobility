"""Diagnostic: show entity counts for chunks missing relationships."""
import asyncio
import asyncpg
from rag_ocpp.config import get_config, load_config

async def diag():
    load_config(); cfg = get_config()
    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn)
    rows = await pool.fetch("""
        SELECT c.id, c.section_title, c.page_start,
               COUNT(DISTINCT ce.entity_id) AS ec,
               COUNT(DISTINCT et.name) AS tc,
               string_agg(DISTINCT e.name, ', ') AS ents,
               LEFT(c.content, 120) AS preview
        FROM chunks c
        JOIN chunk_entities ce ON ce.chunk_id = c.id
        JOIN entities e ON e.id = ce.entity_id
        JOIN entity_types et ON et.id = e.type_id
        WHERE et.protocol_id = 1
        GROUP BY c.id
        HAVING COUNT(DISTINCT r.id) = 0
        FROM relationships r ON r.source_id = ce.entity_id
        ORDER BY ec, c.chunk_index
    """)
    print(f"\n{len(rows)} chunks missing relationships:\n")
    for i, r in enumerate(rows):
        flag = "OK" if r["ec"] > 1 else "1-entity"
        print(f"[{i+1}] {flag} | {r['ec']} ent | {r['tc']} types | {r['ents'][:80]}")
        print(f"    p.{r['page_start']} | {r['preview'][:100]}")
    await pool.close()

asyncio.run(diag())
