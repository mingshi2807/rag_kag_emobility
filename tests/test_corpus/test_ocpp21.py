"""Tests for source-aware OCPP 2.1 corpus parsing."""

import json

from rag_ocpp.corpus.ocpp21 import parse_device_model_csv, parse_json_schema_file


def test_parse_device_model_csv(tmp_path):
    csv_path = tmp_path / "dm_components_vars.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Specific Component;Variable;Instance;Required?;DataType;Unit;Description",
                "ChargingStation;HeartbeatInterval;;yes;integer;s;Interval in seconds",
            ]
        ),
        encoding="utf-8",
    )

    records = parse_device_model_csv(csv_path)

    assert len(records) == 1
    record = records[0]
    assert record.evidence_layer == "device_model"
    assert record.record_type == "dm_component_variable"
    assert record.entity_type == "variable"
    assert record.entity_name == "HeartbeatInterval"
    assert "Component: ChargingStation." in record.content
    assert record.metadata["required"] == "yes"


def test_parse_json_schema_file(tmp_path):
    schema_path = tmp_path / "BootNotificationRequest.json"
    schema_path.write_text(
        json.dumps(
            {
                "$id": "urn:OCPP:Cp:2:2025:1:BootNotificationRequest",
                "definitions": {
                    "BootReasonEnumType": {
                        "type": "string",
                        "enum": ["PowerUp", "Triggered"],
                    },
                    "ChargingStationType": {
                        "type": "object",
                        "properties": {
                            "model": {"type": "string"},
                            "vendorName": {"type": "string"},
                        },
                        "required": ["model", "vendorName"],
                    },
                },
                "type": "object",
                "properties": {
                    "chargingStation": {
                        "$ref": "#/definitions/ChargingStationType",
                    },
                    "reason": {
                        "$ref": "#/definitions/BootReasonEnumType",
                    },
                },
                "required": ["reason", "chargingStation"],
            }
        ),
        encoding="utf-8",
    )

    records = parse_json_schema_file(schema_path)
    titles = {record.title for record in records}

    assert "BootNotification.req" in titles
    assert "BootNotification.req.reason" in titles
    assert "BootNotification.req.chargingStation.model" in titles
    reason = next(record for record in records if record.title == "BootNotification.req.reason")
    assert reason.record_type == "schema_field"
    assert reason.metadata["required"] is True
    assert reason.metadata["enum"] == ["PowerUp", "Triggered"]
