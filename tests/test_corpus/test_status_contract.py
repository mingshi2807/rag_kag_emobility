"""Corpus status contract tests shared by API and MCP surfaces."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rag_ocpp.api.dependencies import get_pool
from rag_ocpp.api.routes.corpus import router as corpus_router
from rag_ocpp.cli import corpus as corpus_cli
from rag_ocpp.corpus.status import load_corpus_status
from rag_ocpp.mcp.server import _corpus_status


@pytest.mark.asyncio
async def test_corpus_status_helper_maps_counts_without_content():
    status = await load_corpus_status(FakeStatusPool())

    assert status.source_documents == 3
    assert status.corpus_records == 30
    assert status.corpus_chunks == 12
    assert status.embedded_corpus_chunks == 10
    assert status.by_source_type == {"spec_pdf": 1, "device_model_table": 2}
    assert status.by_evidence_layer == {"spec": 1, "device_model": 2}


def test_api_corpus_status_uses_shared_count_contract():
    app = FastAPI()
    app.include_router(corpus_router, prefix="/corpus")
    app.dependency_overrides[get_pool] = lambda: FakeStatusPool()

    response = TestClient(app).get("/corpus/status")

    assert response.status_code == 200
    assert response.json() == {
        "source_documents": 3,
        "corpus_records": 30,
        "corpus_documents": 3,
        "corpus_chunks": 12,
        "embedded_corpus_chunks": 10,
        "by_source_type": {"spec_pdf": 1, "device_model_table": 2},
        "by_evidence_layer": {"spec": 1, "device_model": 2},
    }


@pytest.mark.asyncio
async def test_mcp_corpus_status_uses_shared_count_contract():
    response = await _corpus_status(SimpleNamespace(pool=FakeStatusPool()), {})

    assert response.startswith("# OCPP Corpus Status")
    assert '"sources": 3' in response
    assert '"records": 30' in response
    assert '"chunks": 44' in response
    assert '"embeddings": 40' in response
    assert "raw source content" not in response
    assert _extract_first_json_block(response)["sources"] == 3


@pytest.mark.asyncio
async def test_cli_corpus_status_uses_shared_count_contract(monkeypatch, capsys):
    async def fake_create_pool(**kwargs):
        return FakeStatusPool()

    monkeypatch.setattr(corpus_cli.asyncpg, "create_pool", fake_create_pool)

    await corpus_cli._corpus_status_async()

    body = json.loads(capsys.readouterr().out)
    assert body["source_documents"] == 3
    assert body["corpus_records"] == 30
    assert body["total_chunks"] == 44
    assert body["by_evidence_layer"] == {"device_model": 2, "spec": 1}


class FakeStatusPool:
    async def fetch(self, query: str):
        if "FROM source_documents" in query:
            return [
                {
                    "evidence_layer": "device_model",
                    "source_type": "device_model_table",
                    "count": 2,
                },
                {"evidence_layer": "spec", "source_type": "spec_pdf", "count": 1},
            ]
        if "vector_dims" in query:
            return [{"dims": 1024, "count": 40}]
        return [
            {
                "evidence_layer": "device_model",
                "source_type": "device_model_table",
                "chunks": 20,
                "embeddings": 18,
            },
            {
                "evidence_layer": "spec",
                "source_type": "spec_pdf",
                "chunks": 24,
                "embeddings": 22,
            },
        ]

    async def fetchrow(self, query: str):
        return {
            "source_documents": 3,
            "corpus_records": 30,
            "corpus_documents": 3,
            "corpus_chunks": 12,
            "embedded_corpus_chunks": 10,
            "total_chunks": 44,
            "total_embeddings": 40,
            "entity_links": 7,
            "relationships": 5,
        }

    async def close(self):
        return None


def _extract_first_json_block(markdown: str):
    _, rest = markdown.split("```json\n", 1)
    json_text, _ = rest.split("\n```", 1)
    return json.loads(json_text)
