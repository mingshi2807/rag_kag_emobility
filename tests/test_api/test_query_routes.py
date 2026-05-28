"""FastAPI query/search contract tests."""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rag_ocpp.api.dependencies import (
    get_audit_store,
    get_hybrid_retriever,
    get_llm_client,
)
from rag_ocpp.api.routes.query import router
from rag_ocpp.retrieval.hybrid import RetrievalResult
from rag_ocpp.retrieval.searchers import ScoredChunk

CHUNK_ID = UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")


class FakeRetriever:
    def __init__(self) -> None:
        self.retrieve_calls = []
        self.search_calls = []

    async def retrieve(self, query, *, filters=None, top_k=None):
        self.retrieve_calls.append({"query": query, "filters": filters, "top_k": top_k})
        return _retrieval(top_k or 1)

    async def search_only(self, query, *, filters=None, top_k=None):
        self.search_calls.append({"query": query, "filters": filters, "top_k": top_k})
        return _retrieval(top_k or 1)


class FakeLlm:
    model = "test-model"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def generate(self, query, context):
        if self.fail:
            raise RuntimeError("Bearer sk-secret private provider failure")
        return "## Purpose\nGenerated answer."

    async def generate_stream(self, query, context):
        if self.fail:
            raise RuntimeError("Bearer sk-secret private provider failure")
        yield "Generated"
        yield " answer."


class FakeAudit:
    def __init__(self) -> None:
        self.events = []

    async def record(self, event):
        self.events.append(event)
        return UUID("33333333-3333-3333-3333-333333333333")


def test_query_honors_top_k_filters_and_source_metadata():
    retriever = FakeRetriever()
    audit = FakeAudit()
    client = _client(retriever=retriever, audit=audit)

    response = client.post(
        "/query",
        json={
            "query": "DER implementation guidance",
            "top_k": 3,
            "evidence_layer": "schema",
            "source_type": "json_schema",
            "max_chars": 12,
            "include_query": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] is None
    assert body["query_ref"]["length"] == len("DER implementation guidance")
    assert body["answer"] == "## Purpose\nGenerated answer."
    assert len(body["sources"]) == 3
    assert body["sources"][0]["content"] == "OCPP source "
    assert body["sources"][0]["evidence_layer"] == "schema"
    assert body["sources"][0]["source_type"] == "json_schema"
    assert body["sources"][0]["source_path"] == "data/json/test.schema.json"

    call = retriever.retrieve_calls[0]
    assert call["top_k"] == 3
    assert call["filters"].evidence_layer == "schema"
    assert call["filters"].source_type == "json_schema"
    assert [event.event_type for event in audit.events] == [
        "query.requested",
        "retrieval.completed",
        "generation.completed",
    ]


def test_search_honors_source_filters_and_can_hide_content():
    retriever = FakeRetriever()
    client = _client(retriever=retriever)

    response = client.get(
        "/search",
        params={
            "q": "BootNotification schema",
            "top_k": 2,
            "evidence_layer": "schema",
            "source_type": "json_schema",
            "include_content": "false",
            "include_query": "false",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] is None
    assert len(body["results"]) == 2
    assert body["results"][0]["content"] is None
    assert body["results"][0]["content_hash"] == "hash-1"

    call = retriever.search_calls[0]
    assert call["top_k"] == 2
    assert call["filters"].evidence_layer == "schema"
    assert call["filters"].source_type == "json_schema"


def test_query_generation_failure_returns_redacted_structured_error():
    retriever = FakeRetriever()
    audit = FakeAudit()
    client = _client(retriever=retriever, llm=FakeLlm(fail=True), audit=audit)

    response = client.post(
        "/query",
        json={"query": "What is BootNotification?", "top_k": 1},
    )

    assert response.status_code == 502
    body = response.json()
    assert body["detail"]["error"] == "generation_failed"
    assert body["detail"]["correlation_id"]
    assert "sk-secret" not in response.text
    assert audit.events[-1].event_type == "generation.failed"
    assert "sk-secret" not in str(audit.events[-1].metadata)


def _client(
    *,
    retriever: FakeRetriever | None = None,
    llm: FakeLlm | None = None,
    audit: FakeAudit | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_hybrid_retriever] = lambda: retriever or FakeRetriever()
    app.dependency_overrides[get_llm_client] = lambda: llm or FakeLlm()
    app.dependency_overrides[get_audit_store] = lambda: audit or FakeAudit()
    return TestClient(app)


def _retrieval(count: int) -> RetrievalResult:
    chunks = [
        ScoredChunk(
            chunk_id=CHUNK_ID,
            document_id=DOCUMENT_ID,
            chunk_index=index,
            content=f"OCPP source content {index}",
            section_title="Test Section",
            page_start=10 + index,
            page_end=10 + index,
            score=0.9 - (index * 0.01),
            strategy="keyword",
            metadata={
                "evidence_layer": "schema",
                "source_type": "json_schema",
                "source_path": "data/json/test.schema.json",
                "content_hash": f"hash-{index + 1}",
            },
        )
        for index in range(count)
    ]
    return RetrievalResult(
        chunks=chunks,
        strategy_breakdown={"keyword": len(chunks)},
        latency_ms=12,
    )
