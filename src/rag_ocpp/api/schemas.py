"""Pydantic request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

EvidenceLayer = Literal["spec", "device_model", "schema"]
SourceType = Literal["spec_pdf", "device_model_table", "json_schema", "appendix_csv"]


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


class CorpusBuildRequest(BaseModel):
    spec_pdf: str | None = None
    dm_dir: str | None = None
    schema_dir: str | None = None
    include_pdf: bool = True
    include_dm: bool = True
    include_schemas: bool = True


class CorpusSourceSummary(BaseModel):
    source_path: str
    parser: str
    source_type: str | None = None
    evidence_layer: str | None = None
    title: str | None = None
    content_hash: str | None = None
    raw_bytes: int | None = None
    records: int = 0


class CorpusPreviewResponse(BaseModel):
    planned_sources: int
    total_records: int
    sources: list[CorpusSourceSummary] = Field(default_factory=list)


class CorpusStoreResponse(CorpusPreviewResponse):
    stored_sources: int = 0
    stored_records: int = 0


class CorpusIndexRequest(BaseModel):
    no_embed: bool = False
    batch_size: int = Field(default=128, ge=1, le=1024)
    limit: int | None = Field(default=None, ge=1)


class CorpusIndexResponse(BaseModel):
    sources_indexed: int = 0
    records_indexed: int = 0
    chunks_upserted: int = 0
    chunks_embedded: int = 0
    entities_linked: int = 0
    relationships_created: int = 0


class CorpusStatusResponse(BaseModel):
    source_documents: int = 0
    corpus_records: int = 0
    corpus_documents: int = 0
    corpus_chunks: int = 0
    embedded_corpus_chunks: int = 0
    by_source_type: dict[str, int] = Field(default_factory=dict)
    by_evidence_layer: dict[str, int] = Field(default_factory=dict)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    stream: bool = False
    doc_type: str | None = None
    evidence_layer: EvidenceLayer | None = None
    source_type: SourceType | None = None
    max_chars: int = Field(default=500, ge=0, le=6000)
    include_content: bool = True
    include_answer: bool = True
    include_query: bool = True


class ScoredChunkResponse(BaseModel):
    chunk_id: UUID
    document_id: UUID
    content: str | None = None
    score: float
    strategy: str
    section_title: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    evidence_layer: str | None = None
    source_type: str | None = None
    source_path: str | None = None
    content_hash: str | None = None


class QueryResponse(BaseModel):
    correlation_id: str
    query: str | None = None
    query_ref: dict[str, Any]
    answer: str | None = None
    sources: list[ScoredChunkResponse]
    strategy_breakdown: dict[str, int] = Field(default_factory=dict)
    latency_ms: int = 0


class SearchResponse(BaseModel):
    correlation_id: str
    query: str | None = None
    query_ref: dict[str, Any]
    results: list[ScoredChunkResponse]
    strategy_breakdown: dict[str, int] = Field(default_factory=dict)
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
    relationships: list[dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
    database: str = "disconnected"
    embedding_model: str = ""
    embedding_loaded: bool = False
    reranker_loaded: bool = False
