"""FastAPI source-aware corpus route tests."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rag_ocpp.api.dependencies import get_audit_store, get_corpus_store
from rag_ocpp.api.routes.corpus import router
from rag_ocpp.config import ApiConfig, AppConfig
from rag_ocpp.corpus.models import EvidenceRecord, SourceDocument


class FakeCorpusStore:
    def __init__(self) -> None:
        self.sources = []
        self.records = []

    async def upsert_source_document(self, source):
        self.sources.append(source)
        return UUID("11111111-1111-1111-1111-111111111111")

    async def upsert_corpus_records(self, records):
        self.records.extend(records)
        return len(records)


class FakeAudit:
    def __init__(self) -> None:
        self.events = []

    async def record(self, event):
        self.events.append(event)
        return UUID("22222222-2222-2222-2222-222222222222")


def test_corpus_preview_requires_admin_and_returns_counts(monkeypatch):
    _patch_source_build(monkeypatch)
    client = _client(admin_token="secret-token")

    unauthorized = client.post("/corpus/preview", json={"include_pdf": True})
    authorized = client.post(
        "/corpus/preview",
        json={"include_pdf": True},
        headers={"Authorization": "Bearer secret-token"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    body = authorized.json()
    assert body["planned_sources"] == 1
    assert body["total_records"] == 2
    assert body["sources"][0]["source_type"] == "spec_pdf"
    assert "Source content one" not in str(body)
    assert "Source content two" not in str(body)


def test_corpus_store_requires_admin_and_writes_audit(monkeypatch):
    _patch_source_build(monkeypatch)
    store = FakeCorpusStore()
    audit = FakeAudit()
    client = _client(admin_token="secret-token", store=store, audit=audit)

    response = client.post(
        "/corpus/store",
        json={"include_pdf": True},
        headers={"Authorization": "Bearer secret-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["stored_sources"] == 1
    assert body["stored_records"] == 2
    assert len(store.sources) == 1
    assert len(store.records) == 2
    assert [event.event_type for event in audit.events] == ["corpus.ingested"]


def _client(
    *,
    admin_token: str,
    store: FakeCorpusStore | None = None,
    audit: FakeAudit | None = None,
) -> TestClient:
    app = FastAPI()
    app.state.config = AppConfig(api=ApiConfig(admin_token=admin_token))
    app.include_router(router, prefix="/corpus")
    app.dependency_overrides[get_corpus_store] = lambda: store or FakeCorpusStore()
    app.dependency_overrides[get_audit_store] = lambda: audit or FakeAudit()
    return TestClient(app)


def _patch_source_build(monkeypatch) -> None:
    path = Path("data/pdf/spec.pdf")
    monkeypatch.setattr(
        "rag_ocpp.api.routes.corpus._planned_sources",
        lambda **kwargs: [(path, "spec_pdf")],
    )
    monkeypatch.setattr(
        "rag_ocpp.api.routes.corpus._parse_source",
        lambda source_path, parser: [
            EvidenceRecord.build(
                stable_key="record-1",
                source_path=source_path,
                source_type="spec_pdf",
                evidence_layer="spec",
                record_type="spec_section",
                title="Section 1",
                content="Source content one",
            ),
            EvidenceRecord.build(
                stable_key="record-2",
                source_path=source_path,
                source_type="spec_pdf",
                evidence_layer="spec",
                record_type="spec_section",
                title="Section 2",
                content="Source content two",
            ),
        ],
    )
    monkeypatch.setattr(
        "rag_ocpp.api.routes.corpus._source_document_for",
        lambda source_path, parser: SourceDocument(
            source_path=str(source_path),
            source_type="spec_pdf",
            evidence_layer="spec",
            title="Spec",
            content_hash="hash",
            raw_bytes=123,
        ),
    )
