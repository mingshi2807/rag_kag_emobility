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
        JOIN entity_types et ON et.id = e.type_id AND et.protocol_id = e.protocol_id
        LEFT JOIN relationships r ON r.source_id = ce.entity_id
        GROUP BY c.id
        HAVING COUNT(r.id) = 0
        ORDER BY ec, c.chunk_index
    """)
    print(f"\n{len(rows)} chunks missing relationships:\n")
    for i, r in enumerate(rows):
        flag = "≥2 entities — LLM should work" if r["ec"] > 1 else "1 entity only — no rel possible"
        print(f"[{i+1}] {flag}")
        print(f"    Entities: {r['ec']} ({r['tc']} types) — {r['ents'][:100]}")
        print(f"    Section: {r['section_title']}, p.{r['page_start']}")
        print(f"    Preview: {r['preview'][:120]}")
        print()
    await pool.close()

asyncio.run(diag())
