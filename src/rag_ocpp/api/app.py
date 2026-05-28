"""FastAPI application factory with lifespan management."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from rag_ocpp.config import AppConfig, load_config
from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.privacy import configure_redacted_logging
from rag_ocpp.retrieval.reranker import CrossEncoderReranker

logger = logging.getLogger(__name__)


def create_app(config: AppConfig | None = None) -> FastAPI:
    if config is None:
        config = load_config()

    configure_redacted_logging(
        level=getattr(logging, config.logging.level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting RAG/KAG OCPP 2.1 API...")

        pool = await asyncpg.create_pool(
            dsn=config.postgres.dsn,
            min_size=config.postgres.min_connections,
            max_size=config.postgres.max_connections,
        )
        app.state.pool = pool

        embedding = EmbeddingModel(config.embedding)
        embedding.load()
        app.state.embedding = embedding

        reranker = CrossEncoderReranker(config.reranker)
        reranker.load()
        app.state.reranker = reranker

        app.state.config = config
        logger.info("API ready.")

        yield

        logger.info("Shutting down...")
        app.state.reranker.unload()
        app.state.embedding.unload()
        await pool.close()

    app = FastAPI(
        title="RAG/KAG OCPP 2.1",
        version="0.1.0",
        lifespan=lifespan,
    )

    from rag_ocpp.api.routes.admin import router as admin_router
    from rag_ocpp.api.routes.ingest import router as ingest_router
    from rag_ocpp.api.routes.query import router as query_router

    app.include_router(ingest_router, prefix="/ingest", tags=["ingest"])
    app.include_router(query_router, tags=["query"])
    app.include_router(admin_router, tags=["admin"])

    return app


def run():
    import uvicorn
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)
