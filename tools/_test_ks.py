import asyncio, asyncpg, sys
sys.path.insert(0,'/home/ming-dev/workspace/rag-kag-ocpp/src')
from rag_ocpp.config import load_config, get_config
from rag_ocpp.retrieval.searchers import KeywordSearcher, VectorSearcher
from rag_ocpp.embedding.model import EmbeddingModel

async def t():
    load_config(); c=get_config()
    p = await asyncpg.create_pool(dsn=c.postgres.dsn)

    ks = KeywordSearcher(p)
    r = await ks.search('Certificate Management', top_k=20)
    print(f'KeywordSearcher: {len(r)} results')
    for x in r[:3]: print(f'  {x.section_title}')

    emb = EmbeddingModel(c.embedding); emb.load()
    vs = VectorSearcher(p, emb)
    r2 = await vs.search('Certificate Management', top_k=20)
    print(f'VectorSearcher: {len(r2)} results')
    for x in r2[:3]: print(f'  {x.section_title} score={x.score:.4f}')

    from rag_ocpp.retrieval.hybrid import HybridRetriever
    from rag_ocpp.retrieval.reranker import CrossEncoderReranker
    reranker = CrossEncoderReranker(c.reranker); reranker.load()
    hr = HybridRetriever(pool=p, embedding_model=emb, reranker=reranker, final_top_k=5)
    result = await hr.retrieve('Certificate Management')
    print(f'HybridRetriever: {len(result.chunks)} chunks, breakdown={result.strategy_breakdown}')
    for x in result.chunks[:3]: print(f'  {x.section_title}')

    await p.close()

asyncio.run(t())
