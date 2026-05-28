"""FastAPI admin mutation guard tests."""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rag_ocpp.api.dependencies import get_audit_store, get_vector_store
from rag_ocpp.api.routes.admin import router as admin_router
from rag_ocpp.api.routes.ingest import router as ingest_router
from rag_ocpp.config import ApiConfig, AppConfig

DOCUMENT_ID = "11111111-1111-1111-1111-111111111111"


class FakeVectorStore:
    async def delete_document(self, document_id: UUID) -> int:
        assert str(document_id) == DOCUMENT_ID
        return 3


class FakeAudit:
    def __init__(self) -> None:
        self.events = []

    async def record(self, event):
        self.events.append(event)
        return UUID("22222222-2222-2222-2222-222222222222")


def test_admin_mutation_is_disabled_without_configured_token():
    client = _client(admin_token="")

    response = client.delete(
        f"/documents/{DOCUMENT_ID}",
        headers={"Authorization": "Bearer any-token"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "admin_api_disabled"


def test_document_delete_requires_admin_bearer_token():
    client = _client(admin_token="secret-token")

    missing = client.delete(f"/documents/{DOCUMENT_ID}")
    forbidden = client.delete(
        f"/documents/{DOCUMENT_ID}",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert missing.status_code == 401
    assert forbidden.status_code == 403


def test_document_delete_with_admin_token_writes_audit_event():
    audit = FakeAudit()
    client = _client(admin_token="secret-token", audit=audit)

    response = client.delete(
        f"/documents/{DOCUMENT_ID}",
        headers={"Authorization": "Bearer secret-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "document_id": DOCUMENT_ID}
    assert len(audit.events) == 1
    event = audit.events[0]
    assert event.event_type == "admin.document_delete"
    assert event.resource_id == DOCUMENT_ID
    assert event.metadata["deleted_chunks"] == 3


def test_legacy_ingest_requires_admin_bearer_token_before_handler_work():
    client = _client(admin_token="secret-token", include_ingest=True)

    response = client.post(
        "/ingest",
        files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 401


def _client(
    *,
    admin_token: str,
    audit: FakeAudit | None = None,
    include_ingest: bool = False,
) -> TestClient:
    app = FastAPI()
    app.state.config = AppConfig(api=ApiConfig(admin_token=admin_token))
    app.include_router(admin_router)
    if include_ingest:
        app.include_router(ingest_router, prefix="/ingest")
    app.dependency_overrides[get_vector_store] = lambda: FakeVectorStore()
    app.dependency_overrides[get_audit_store] = lambda: audit or FakeAudit()
    return TestClient(app)
