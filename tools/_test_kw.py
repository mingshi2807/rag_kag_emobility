import asyncio, asyncpg, sys
sys.path.insert(0,'/home/ming-dev/workspace/rag-kag-ocpp/src')
from rag_ocpp.config import load_config, get_config
from rag_ocpp.storage.vector import VectorStore

async def t():
    load_config(); c=get_config()
    p = await asyncpg.create_pool(dsn=c.postgres.dsn)
    vs = VectorStore(p)
    r = await vs.keyword_search('Certificate Management', top_k=3)
    print(f'results: {len(r)}')
    for x in r: print(f'  {x.section_title}')
    await p.close()

asyncio.run(t())
