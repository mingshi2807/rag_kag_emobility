"""FastAPI dependency injection."""

from __future__ import annotations

import asyncpg
from fastapi import Request

from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.generation.client import DeepSeekClient
from rag_ocpp.retrieval.hybrid import HybridRetriever
from rag_ocpp.retrieval.reranker import CrossEncoderReranker
from rag_ocpp.storage.audit import AuditStore
from rag_ocpp.storage.graph import GraphStore
from rag_ocpp.storage.vector import VectorStore


def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool

def get_config(request: Request):
    return request.app.state.config

def get_embedding_model(request: Request) -> EmbeddingModel:
    return request.app.state.embedding

def get_reranker(request: Request) -> CrossEncoderReranker:
    return request.app.state.reranker

def get_vector_store(request: Request) -> VectorStore:
    return VectorStore(request.app.state.pool)

def get_graph_store(request: Request) -> GraphStore:
    return GraphStore(request.app.state.pool)

def get_audit_store(request: Request) -> AuditStore:
    return AuditStore(request.app.state.pool)

def get_llm_client(request: Request) -> DeepSeekClient:
    return DeepSeekClient(request.app.state.config.deepseek)

def get_hybrid_retriever(request: Request) -> HybridRetriever:
    cfg = request.app.state.config.retrieval
    return HybridRetriever(
        pool=request.app.state.pool,
        embedding_model=request.app.state.embedding,
        reranker=request.app.state.reranker,
        vector_top_k=cfg.vector_top_k,
        keyword_top_k=cfg.keyword_top_k,
        graph_top_k=cfg.graph_top_k,
        fusion_k=cfg.fusion_k,
        final_top_k=cfg.final_top_k,
    )
