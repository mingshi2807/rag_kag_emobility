"""Re-populate queries.jsonl with chunk UUIDs from current DB (direct SQL)."""
import asyncio, json, asyncpg, os, re

DSN = f"postgresql://{os.environ.get('PG_USER','rag_kag')}:{os.environ.get('PG_PASSWORD','rag_kag')}@{os.environ.get('PG_HOST','localhost')}:{os.environ.get('PG_PORT','5432')}/{os.environ.get('PG_DATABASE','rag_kag')}"

async def repop():
    pool = await asyncpg.create_pool(dsn=DSN)
    with open("data/eval/queries.jsonl") as f:
        queries = [json.loads(l) for l in f if l.strip()]
    updated = []
    for q in queries:
        qtext = q["query"]
        rows = await pool.fetch(
            "SELECT id FROM chunks WHERE content ILIKE $1 OR section_title ILIKE $1 ORDER BY page_start LIMIT 5",
            f"%{qtext}%")
        if not rows:
            words = [w for w in re.split(r'\s+', qtext) if len(w) > 3]
            if words:
                clause = " OR ".join([f"content ILIKE '%{w}%' OR section_title ILIKE '%{w}%'" for w in words[:3]])
                rows = await pool.fetch(f"SELECT id FROM chunks WHERE {clause} ORDER BY page_start LIMIT 5")
        ids = [str(r["id"]) for r in rows]
        updated.append({"query": q["query"], "relevant": ids})
        print(f"{q['query'][:65]}: {len(ids)} UUIDs")
    with open("data/eval/queries.jsonl", "w") as f:
        for u in updated:
            f.write(json.dumps(u) + "\n")
    print(f"\nDone. {len(updated)} queries updated.")
    await pool.close()

asyncio.run(repop())
