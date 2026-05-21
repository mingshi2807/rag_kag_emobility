"""OCPP metadata extraction — filename patterns, content heuristics, section detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_ocpp.ingestion.parser import ParsedDocument


@dataclass
class OCPPDocumentMeta:
    """Structured OCPP-specific metadata for a document."""
    protocol: str = "ocpp21"
    version: str = "2.1"
    part: str | None = None
    doc_type: str = "spec"
    profile: str | None = None
    section_count: int = 0
    filename_confidence: float = 0.0


class OCPPMetadataExtractor:
    """Extract OCPP-specific metadata from filenames and document content.

    Resolution order: filename patterns → content heuristics → user override.
    """

    # Filename patterns
    SPEC_FILENAME_RE = re.compile(
        r"OCPP[_\s-]*"
        r"(?P<version>\d+[._]\d+)[_\s-]*"
        r"Part[_\s-]*(?P<part_num>\d+)[_\s-]*"
        r"(?P<part_name>[A-Za-z]+)",
        re.IGNORECASE,
    )

    TEST_FILENAME_RE = re.compile(
        r"OCPP[_\s-]*"
        r"(?P<version>\d+[._]\d+)[_\s-]*"
        r"Test[_\s-]*Cases?[_\s-]*"
        r"(?:Profile[_\s-]*(?P<profile>[A-Z]))?",
        re.IGNORECASE,
    )

    OCA_FILENAME_RE = re.compile(
        r"OCA[_\s-]*"
        r"OCPP[_\s-]*"
        r"(?P<version>\d+[._]\d+)[_\s-]*"
        r"(?:edition|ed)[_\s-]*(?P<edition>\d+)",
        re.IGNORECASE,
    )

    # Known OCPP part names
    KNOWN_PARTS: dict[str, str] = {
        "core": "Part 2: Core",
        "security": "Part 4: Security",
        "smart charging": "Part 5: Smart Charging",
        "local controller": "Part 6: Local Controller",
        "iso 15118": "Part 7: ISO 15118",
        "display": "Part 8: Display and Messaging",
        "firmware": "Part 9: Firmware Management",
        "provisioning": "Part 10: Provisioning",
    }

    SECTION_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+\w", re.MULTILINE)

    # ── Public API ──────────────────────────────────────

    def extract(
        self,
        path: str | Path,
        parsed: ParsedDocument,
        *,
        protocol: str | None = None,
        version: str | None = None,
        part: str | None = None,
        doc_type: str | None = None,
    ) -> OCPPDocumentMeta:
        path = Path(path)

        filename_meta = self._from_filename(path)
        content_meta = self._from_content(parsed)

        return OCPPDocumentMeta(
            protocol=protocol or filename_meta.protocol,
            version=version or filename_meta.version or content_meta.version or "2.1",
            part=part or filename_meta.part or content_meta.part,
            doc_type=doc_type or filename_meta.doc_type,
            profile=filename_meta.profile,
            section_count=content_meta.section_count,
            filename_confidence=filename_meta.filename_confidence,
        )

    # ── Filename extraction ─────────────────────────────

    def _from_filename(self, path: Path) -> OCPPDocumentMeta:
        name = path.stem

        m = self.OCA_FILENAME_RE.search(name)
        if m:
            return OCPPDocumentMeta(
                version=m.group("version").replace("_", ".").replace("-", "."),
                doc_type="spec",
                filename_confidence=0.9,
            )

        m = self.SPEC_FILENAME_RE.search(name)
        if m:
            version = m.group("version").replace("_", ".").replace("-", ".")
            part_num = m.group("part_num")
            part_name = m.group("part_name")
            part_label = f"Part {part_num}: {part_name}"
            return OCPPDocumentMeta(
                version=version,
                part=part_label,
                doc_type="spec",
                filename_confidence=0.95,
            )

        m = self.TEST_FILENAME_RE.search(name)
        if m:
            version = m.group("version").replace("_", ".").replace("-", ".")
            profile = m.group("profile")
            return OCPPDocumentMeta(
                version=version,
                profile=profile.upper() if profile else None,
                doc_type="test_suite",
                filename_confidence=0.9,
            )

        if "OCPP" in name.upper():
            return OCPPDocumentMeta(doc_type="spec", filename_confidence=0.2)

        return OCPPDocumentMeta(doc_type="other", filename_confidence=0.0)

    # ── Content heuristics ──────────────────────────────

    def _from_content(self, parsed: ParsedDocument) -> OCPPDocumentMeta:
        text = parsed.flat_text[:5000]
        text_lower = text.lower()

        part: str | None = None
        for keyword, part_label in self.KNOWN_PARTS.items():
            if keyword in text_lower:
                part = part_label
                break

        version: str | None = None
        version_match = re.search(
            r"OCPP\s+(?:version\s+)?(\d+[._]\d+)",
            text, re.IGNORECASE,
        )
        if version_match:
            version = version_match.group(1).replace("_", ".").replace("-", ".")

        sections = self.SECTION_RE.findall(text)
        section_count = len(set(sections))

        if parsed.metadata.toc:
            section_count = max(section_count, len(parsed.metadata.toc))

        return OCPPDocumentMeta(
            version=version,
            part=part,
            section_count=section_count,
        )

    # ── Section detection ───────────────────────────────

    def detect_sections(
        self, parsed: ParsedDocument
    ) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []

        if parsed.metadata.toc:
            for i, entry in enumerate(parsed.metadata.toc):
                title = entry["title"]
                page_start = entry["page"]
                page_end = (
                    parsed.metadata.toc[i + 1]["page"] - 1
                    if i + 1 < len(parsed.metadata.toc)
                    else parsed.metadata.page_count
                )
                sections.append({
                    "section": str(entry.get("level", "")),
                    "title": title,
                    "page_start": page_start,
                    "page_end": page_end,
                })
            return sections

        for page in parsed.pages:
            section_match = self.SECTION_RE.search(page.text)
            if section_match:
                sections.append({
                    "section": section_match.group(1),
                    "title": "",
                    "page_start": page.page_num,
                    "page_end": page.page_num,
                })

        return sections
