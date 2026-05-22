"""Unit tests — OCPPMetadataExtractor."""

from pathlib import Path

from rag_ocpp.ingestion.metadata import OCPPMetadataExtractor
from rag_ocpp.ingestion.parser import DocumentMetadata, ParsedDocument, ParsedPage


def _doc(name: str, text: str = "") -> ParsedDocument:
    return ParsedDocument(
        source_path=Path(name), doc_type="spec",
        pages=[ParsedPage(page_num=1, text=text)],
        metadata=DocumentMetadata(page_count=1, toc=[]),
    )


class TestMetadata:
    def test_oca_filename(self):
        m = OCPPMetadataExtractor().extract("OCA_OCPP_2.1_edition2.pdf", _doc("OCA_OCPP_2.1_edition2.pdf"))
        assert m.version == "2.1" and m.doc_type == "spec" and m.filename_confidence == 0.9

    def test_spec_filename(self):
        m = OCPPMetadataExtractor().extract("OCPP-2.1-Part2-Core.pdf", _doc("OCPP-2.1-Part2-Core.pdf"))
        assert m.version == "2.1" and m.part == "Part 2: Core" and m.filename_confidence == 0.95

    def test_suite_filename(self):
        m = OCPPMetadataExtractor().extract("OCPP-2.1-TestCases-ProfileA.json", _doc("OCPP-2.1-TestCases-ProfileA.json"))
        assert m.doc_type == "test_suite" and m.profile == "A"

    def test_content_version(self):
        m = OCPPMetadataExtractor().extract("x.pdf", _doc("x.pdf", "OCPP version 2.1 Core spec"))
        assert m.version == "2.1"

    def test_content_part(self):
        m = OCPPMetadataExtractor().extract("d.pdf", _doc("d.pdf", "Smart Charging functionality"))
        assert m.part == "Part 5: Smart Charging"

    def test_override(self):
        m = OCPPMetadataExtractor().extract("w.pdf", _doc("w.pdf"), version="3.0", part="X", doc_type="test_suite")
        assert m.version == "3.0" and m.part == "X" and m.doc_type == "test_suite"
