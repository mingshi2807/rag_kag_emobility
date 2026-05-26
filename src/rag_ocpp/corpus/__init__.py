"""Source-aware corpus extraction for OCPP knowledge backends."""

from rag_ocpp.corpus.models import EvidenceRecord, SourceDocument
from rag_ocpp.corpus.ocpp21 import (
    OCPP21_ED2_DM_DIR,
    OCPP21_ED2_JSON_SCHEMA_DIR,
    OCPP21_ED2_PART2_SPEC_PDF,
    parse_device_model_csv,
    parse_json_schema_file,
    parse_spec_pdf_sections,
)

__all__ = [
    "EvidenceRecord",
    "SourceDocument",
    "OCPP21_ED2_DM_DIR",
    "OCPP21_ED2_JSON_SCHEMA_DIR",
    "OCPP21_ED2_PART2_SPEC_PDF",
    "parse_device_model_csv",
    "parse_json_schema_file",
    "parse_spec_pdf_sections",
]
