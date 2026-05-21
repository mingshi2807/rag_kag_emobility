"""Document parser — PDF (PyMuPDF + pdfplumber) and JSON input files."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import pdfplumber


# ── Data types ────────────────────────────────────────────

@dataclass
class ParsedPage:
    """A single document page with text and extracted tables."""
    page_num: int
    text: str
    tables: list[list[list[str | None]]] = field(default_factory=list)


@dataclass
class DocumentMetadata:
    """Document-level metadata extracted during parsing."""
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    creator: str | None = None
    producer: str | None = None
    page_count: int = 0
    file_size_bytes: int = 0
    toc: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ParsedDocument:
    """A fully parsed document ready for cleaning and chunking."""
    source_path: Path
    doc_type: str
    pages: list[ParsedPage] = field(default_factory=list)
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    json_structure: dict[str, Any] | None = None

    @property
    def flat_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)

    @property
    def all_tables(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for page in self.pages:
            for ti, table in enumerate(page.tables):
                result.append({
                    "page": page.page_num,
                    "table_index": ti,
                    "rows": table,
                })
        return result


# ── Parser ────────────────────────────────────────────────

class DocumentParser:
    """Parse PDF and JSON input files into ParsedDocument.

    PDF:  PyMuPDF for text + ToC, pdfplumber for tables.
    JSON: stdlib json → flattened text + preserved structure.
    """

    def parse(self, path: str | Path) -> ParsedDocument:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return self._parse_pdf(path)
        elif suffix == ".json":
            return self._parse_json(path)
        else:
            raise ValueError(
                f"Unsupported file type: {suffix}. Supported: .pdf, .json"
            )

    def parse_directory(
        self, directory: str | Path, pattern: str = "*"
    ) -> list[ParsedDocument]:
        directory = Path(directory)
        docs: list[ParsedDocument] = []
        for p in sorted(directory.rglob(pattern)):
            if p.suffix.lower() in (".pdf", ".json"):
                try:
                    docs.append(self.parse(p))
                except Exception as exc:
                    print(f"Warning: failed to parse {p}: {exc}")
        return docs

    # ── PDF ─────────────────────────────────────────────

    def _parse_pdf(self, path: Path) -> ParsedDocument:
        file_size = path.stat().st_size

        pymu_doc = fitz.open(str(path))
        pages: list[ParsedPage] = []

        for i, pymu_page in enumerate(pymu_doc):
            text = pymu_page.get_text(sort=True)
            pages.append(ParsedPage(
                page_num=i + 1,
                text=text.strip() if text else "",
            ))

        raw_toc = pymu_doc.get_toc(simple=False)
        toc = [
            {"level": entry[0], "title": entry[1], "page": entry[2]}
            for entry in raw_toc
        ] if raw_toc else []

        pymu_meta = pymu_doc.metadata or {}
        meta = DocumentMetadata(
            title=pymu_meta.get("title"),
            author=pymu_meta.get("author"),
            subject=pymu_meta.get("subject"),
            creator=pymu_meta.get("creator"),
            producer=pymu_meta.get("producer"),
            page_count=len(pages),
            file_size_bytes=file_size,
            toc=toc,
        )
        pymu_doc.close()

        # pdfplumber pass for tables
        try:
            with pdfplumber.open(str(path)) as plumber_doc:
                for i, plumber_page in enumerate(plumber_doc.pages):
                    raw_tables = plumber_page.extract_tables()
                    if raw_tables:
                        pages[i].tables = [
                            [
                                [str(cell) if cell is not None else "" for cell in row]
                                for row in table
                            ]
                            for table in raw_tables
                        ]
        except Exception:
            pass

        return ParsedDocument(
            source_path=path,
            doc_type="other",
            pages=pages,
            metadata=meta,
        )

    # ── JSON ────────────────────────────────────────────

    def _parse_json(self, path: Path) -> ParsedDocument:
        file_size = path.stat().st_size

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        text_lines = self._flatten_json(data)

        return ParsedDocument(
            source_path=path,
            doc_type="json_config",
            pages=[
                ParsedPage(page_num=1, text="\n".join(text_lines)),
            ],
            metadata=DocumentMetadata(
                page_count=1,
                file_size_bytes=file_size,
            ),
            json_structure=data,
        )

    def _flatten_json(
        self,
        data: Any,
        prefix: str = "",
        max_depth: int = 8,
        max_list_items: int = 20,
    ) -> list[str]:
        lines: list[str] = []
        path = prefix if prefix else "$"

        if isinstance(data, dict):
            lines.append(f"{path}: <object>")
            if max_depth > 0:
                for key, value in data.items():
                    sub_path = f"{path}.{key}"
                    lines.extend(self._flatten_json(
                        value, sub_path, max_depth - 1, max_list_items
                    ))
        elif isinstance(data, list):
            lines.append(f"{path}: <array[{len(data)}]>")
            if max_depth > 0:
                for i, item in enumerate(data[:max_list_items]):
                    sub_path = f"{path}[{i}]"
                    lines.extend(self._flatten_json(
                        item, sub_path, max_depth - 1, max_list_items
                    ))
                if len(data) > max_list_items:
                    lines.append(f"{path}: ... ({len(data) - max_list_items} more items)")
        elif isinstance(data, str):
            lines.append(f"{path}: {data}")
        elif data is None:
            lines.append(f"{path}: null")
        else:
            lines.append(f"{path}: {data}")

        return lines
