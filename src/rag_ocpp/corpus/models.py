"""Dataclasses for source-aware enterprise evidence records."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

SourceType = Literal["spec_pdf", "device_model_table", "json_schema", "appendix_csv"]
EvidenceLayer = Literal["spec", "device_model", "schema"]


def sha256_text(value: str) -> str:
    """Return a stable SHA-256 hex digest for UTF-8 text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Return a stable SHA-256 hex digest for a file."""
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


@dataclass(frozen=True)
class SourceDocument:
    """A source artifact used to build the knowledge corpus."""

    source_path: str
    source_type: SourceType
    evidence_layer: EvidenceLayer
    title: str
    version: str = "2.1"
    edition: str = "Edition 2"
    document_date: str | None = None
    content_hash: str | None = None
    raw_bytes: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        source_type: SourceType,
        evidence_layer: EvidenceLayer,
        title: str,
        version: str = "2.1",
        edition: str = "Edition 2",
        document_date: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SourceDocument:
        p = Path(path)
        return cls(
            source_path=str(p),
            source_type=source_type,
            evidence_layer=evidence_layer,
            title=title,
            version=version,
            edition=edition,
            document_date=document_date,
            content_hash=sha256_file(p),
            raw_bytes=p.stat().st_size,
            metadata=metadata or {},
        )


@dataclass(frozen=True)
class EvidenceRecord:
    """A normalized fact or source segment with explicit provenance."""

    stable_key: str
    source_path: str
    source_type: SourceType
    evidence_layer: EvidenceLayer
    record_type: str
    title: str
    content: str
    content_hash: str
    page_start: int | None = None
    page_end: int | None = None
    row_number: int | None = None
    section_title: str | None = None
    entity_name: str | None = None
    entity_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        *,
        stable_key: str,
        source_path: str | Path,
        source_type: SourceType,
        evidence_layer: EvidenceLayer,
        record_type: str,
        title: str,
        content: str,
        page_start: int | None = None,
        page_end: int | None = None,
        row_number: int | None = None,
        section_title: str | None = None,
        entity_name: str | None = None,
        entity_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceRecord:
        return cls(
            stable_key=stable_key,
            source_path=str(source_path),
            source_type=source_type,
            evidence_layer=evidence_layer,
            record_type=record_type,
            title=title,
            content=content,
            content_hash=sha256_text(content),
            page_start=page_start,
            page_end=page_end,
            row_number=row_number,
            section_title=section_title,
            entity_name=entity_name,
            entity_type=entity_type,
            metadata=metadata or {},
        )
