"""FastAPI application factory with lifespan management."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

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
        enabled=config.logging.redaction_enabled,
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
        version="0.3.0",
        lifespan=lifespan,
    )
    app.openapi_version = "3.0.3"

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            routes=app.routes,
        )
        app.openapi_schema = _normalize_openapi_30(schema)
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    from rag_ocpp.api.routes.admin import router as admin_router
    from rag_ocpp.api.routes.corpus import router as corpus_router
    from rag_ocpp.api.routes.ingest import router as ingest_router
    from rag_ocpp.api.routes.query import router as query_router

    app.include_router(ingest_router, prefix="/ingest", tags=["ingest"])
    app.include_router(corpus_router, prefix="/corpus", tags=["corpus"])
    app.include_router(query_router, tags=["query"])
    app.include_router(admin_router, tags=["admin"])

    return app


def run():
    import uvicorn
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)


def _normalize_openapi_30(value: Any) -> Any:
    """Convert common Pydantic nullable schema forms to OpenAPI 3.0 nullable."""
    if isinstance(value, list):
        return [_normalize_openapi_30(item) for item in value]
    if not isinstance(value, dict):
        return value

    normalized = {key: _normalize_openapi_30(item) for key, item in value.items()}
    any_of = normalized.get("anyOf")
    if isinstance(any_of, list):
        non_null = [
            item
            for item in any_of
            if not (isinstance(item, dict) and item.get("type") == "null")
        ]
        if len(non_null) != len(any_of):
            normalized["nullable"] = True
            if len(non_null) == 1 and isinstance(non_null[0], dict):
                replacement = {
                    key: item
                    for key, item in normalized.items()
                    if key not in {"anyOf", "nullable"}
                }
                replacement.update(non_null[0])
                replacement["nullable"] = True
                return replacement
            normalized["anyOf"] = non_null
    return normalized
