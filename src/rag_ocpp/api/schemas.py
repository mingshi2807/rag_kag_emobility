"""Pydantic request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    document_id: UUID
    source_path: str
    doc_type: str
    protocol: str
    version: str | None = None
    part: str | None = None
    page_count: int = 0
    chunks_created: int = 0
    entities_extracted: int = 0
    embedding_model: str = ""


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    stream: bool = False
    doc_type: str | None = None


class ScoredChunkResponse(BaseModel):
    chunk_id: UUID
    document_id: UUID
    content: str
    score: float
    strategy: str
    section_title: str | None = None
    page_start: int | None = None
    page_end: int | None = None


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: list[ScoredChunkResponse]
    strategy_breakdown: dict[str, int] = {}
    latency_ms: int = 0


class SearchResponse(BaseModel):
    query: str
    results: list[ScoredChunkResponse]
    strategy_breakdown: dict[str, int] = {}
    latency_ms: int = 0


class DocumentResponse(BaseModel):
    id: UUID
    protocol_id: int
    source_path: str
    doc_type: str
    title: str | None = None
    version: str | None = None
    part: str | None = None
    page_count: int | None = None
    ingested_at: datetime | None = None
    chunk_count: int = 0
    entity_count: int = 0


class EntityResponse(BaseModel):
    id: UUID
    type_name: str = ""
    name: str
    description: str | None = None
    aliases: list[str] | None = None
    chunk_count: int = 0
    relationships: list[dict[str, Any]] = []


class HealthResponse(BaseModel):
    status: str = "ok"
    database: str = "disconnected"
    embedding_model: str = ""
    embedding_loaded: bool = False
    reranker_loaded: bool = False
