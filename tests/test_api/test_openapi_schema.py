"""OpenAPI schema contract tests."""

from __future__ import annotations

import json
from pathlib import Path

from rag_ocpp.api.app import create_app


def test_openapi_schema_is_v3_0_and_matches_exported_api_json():
    schema = create_app().openapi()
    exported = json.loads(Path("api.json").read_text(encoding="utf-8"))

    assert schema["openapi"] == "3.0.3"
    assert schema["info"]["version"] == "0.3.0"
    assert exported == schema
    assert '"type": "null"' not in json.dumps(schema)
    assert "/query" in schema["paths"]
    assert "/search" in schema["paths"]
