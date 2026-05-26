"""OCPP 2.1 Edition 2 source-aware corpus parsers."""

from __future__ import annotations

import csv
import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from rag_ocpp.corpus.models import EvidenceRecord

OCPP21_ED2_ROOT = Path("data")
OCPP21_ED2_PART2_SPEC_PDF = (
    OCPP21_ED2_ROOT
    / "pdf"
    / "ocpp2.1Ed2"
    / "OCPP-2.1_edition2_part2_specification.pdf"
)
OCPP21_ED2_DM_DIR = (
    OCPP21_ED2_ROOT / "csv" / "ocpp2.1Ed2" / "Appendices_CSV_v2.1"
)
OCPP21_ED2_JSON_SCHEMA_DIR = (
    OCPP21_ED2_ROOT / "json" / "ocpp2.1Ed2" / "OCPP-2.1_part3_JSON_schemas"
)


def parse_device_model_csv(path: str | Path) -> list[EvidenceRecord]:
    """Parse a semicolon-separated OCPP appendix CSV into evidence records."""
    p = Path(path)
    rows = _read_semicolon_csv(p)
    records: list[EvidenceRecord] = []

    for row_number, row in enumerate(rows, start=2):
        normalized = {_normalize_header(k): _clean(v) for k, v in row.items()}
        if not any(normalized.values()):
            continue

        component = _first(normalized, "specific_component", "component")
        variable = _first(normalized, "variable", "name")
        instance = _first(normalized, "instance")
        datatype = _first(normalized, "datatype", "data_type")
        unit = _first(normalized, "unit")
        required = _first(normalized, "required")
        description = _first(normalized, "description")

        record_type, entity_type, entity_name = _classify_dm_record(p, component, variable)
        title_parts = [x for x in [component, variable, instance] if x]
        title = " / ".join(title_parts) if title_parts else p.stem
        stable_key = ":".join(
            [
                "ocpp21ed2",
                "dm",
                p.stem.lower(),
                component or "_",
                variable or "_",
                instance or "_",
                str(row_number),
            ]
        )
        content = _dm_content(
            component=component,
            variable=variable,
            instance=instance,
            datatype=datatype,
            unit=unit,
            required=required,
            description=description,
        )

        records.append(
            EvidenceRecord.build(
                stable_key=stable_key,
                source_path=p,
                source_type="device_model_table"
                if p.name in {"dm_components_vars.csv", "dm_components_vars.xlsx"}
                else "appendix_csv",
                evidence_layer="device_model",
                record_type=record_type,
                title=title,
                content=content,
                row_number=row_number,
                entity_name=entity_name,
                entity_type=entity_type,
                metadata=normalized,
            )
        )

    return records


def parse_device_model_xlsx(path: str | Path) -> list[EvidenceRecord]:
    """Parse a simple .xlsx workbook without adding a runtime dependency.

    This handles shared strings and inline strings, which is enough for the
    current OCPP Device Model workbook shape.
    """
    p = Path(path)
    tables = _read_xlsx_first_sheet(p)
    if not tables:
        return []
    headers = [_normalize_header(h) for h in tables[0]]
    rows = [dict(zip(headers, values, strict=False)) for values in tables[1:]]
    tmp_csv_like: list[dict[str, str]] = []
    for row in rows:
        tmp_csv_like.append({k: _clean(v) for k, v in row.items()})

    records: list[EvidenceRecord] = []
    for row_number, row in enumerate(tmp_csv_like, start=2):
        if not any(row.values()):
            continue
        component = _first(row, "specific_component", "component")
        variable = _first(row, "variable", "name")
        instance = _first(row, "instance")
        datatype = _first(row, "datatype", "data_type")
        unit = _first(row, "unit")
        required = _first(row, "required")
        description = _first(row, "description")
        record_type, entity_type, entity_name = _classify_dm_record(p, component, variable)
        stable_key = ":".join(
            [
                "ocpp21ed2",
                "dm",
                p.stem.lower(),
                component or "_",
                variable or "_",
                instance or "_",
                str(row_number),
            ]
        )
        records.append(
            EvidenceRecord.build(
                stable_key=stable_key,
                source_path=p,
                source_type="device_model_table",
                evidence_layer="device_model",
                record_type=record_type,
                title=" / ".join(x for x in [component, variable, instance] if x) or p.stem,
                content=_dm_content(
                    component=component,
                    variable=variable,
                    instance=instance,
                    datatype=datatype,
                    unit=unit,
                    required=required,
                    description=description,
                ),
                row_number=row_number,
                entity_name=entity_name,
                entity_type=entity_type,
                metadata=row,
            )
        )
    return records


def parse_json_schema_file(path: str | Path) -> list[EvidenceRecord]:
    """Parse an OCPP JSON schema into message and field evidence records."""
    p = Path(path)
    with p.open(encoding="utf-8") as f:
        schema = json.load(f)

    message_name, direction = _message_from_schema_path(p)
    records = [
        EvidenceRecord.build(
            stable_key=f"ocpp21ed2:schema:{message_name}:{direction}:message",
            source_path=p,
            source_type="json_schema",
            evidence_layer="schema",
            record_type="schema_message",
            title=f"{message_name}.{direction}",
            content=_schema_message_content(message_name, direction, schema),
            entity_name=message_name,
            entity_type="message",
            metadata={
                "message": message_name,
                "direction": direction,
                "required": schema.get("required", []),
                "$id": schema.get("$id"),
            },
        )
    ]

    definitions = schema.get("definitions", {})
    for field in _iter_schema_fields(schema, definitions):
        records.append(
            EvidenceRecord.build(
                stable_key=(
                    f"ocpp21ed2:schema:{message_name}:{direction}:"
                    f"{field['path']}"
                ),
                source_path=p,
                source_type="json_schema",
                evidence_layer="schema",
                record_type="schema_field",
                title=f"{message_name}.{direction}.{field['path']}",
                content=_schema_field_content(message_name, direction, field),
                entity_name=field["name"],
                entity_type="field",
                metadata=field,
            )
        )

    for def_name, definition in definitions.items():
        records.append(
            EvidenceRecord.build(
                stable_key=f"ocpp21ed2:schema:{message_name}:{direction}:definition:{def_name}",
                source_path=p,
                source_type="json_schema",
                evidence_layer="schema",
                record_type="schema_definition",
                title=def_name,
                content=_schema_definition_content(def_name, definition),
                entity_name=def_name,
                entity_type="datatype" if definition.get("type") == "object" else "enum",
                metadata={
                    "definition": def_name,
                    "type": definition.get("type"),
                    "required": definition.get("required", []),
                    "enum": definition.get("enum", []),
                    "description": _clean(definition.get("description")),
                },
            )
        )

    return records


def parse_spec_pdf_sections(path: str | Path) -> list[EvidenceRecord]:
    """Parse the Part 2 PDF into section-level evidence records.

    The import is local so CSV/schema parsing remains usable in minimal
    environments without PDF dependencies.
    """
    import fitz  # type: ignore[import-not-found]

    p = Path(path)
    doc = fitz.open(str(p))
    try:
        toc = doc.get_toc(simple=True)
        if not toc:
            return _records_by_page(p, doc)

        sections: list[EvidenceRecord] = []
        for index, entry in enumerate(toc):
            level, title, page = entry
            next_page = toc[index + 1][2] if index + 1 < len(toc) else doc.page_count + 1
            page_start = max(1, int(page))
            page_end = max(page_start, int(next_page) - 1)
            text_parts = [
                doc.load_page(page_num - 1).get_text(sort=True).strip()
                for page_num in range(page_start, min(page_end, doc.page_count) + 1)
            ]
            content = "\n\n".join(part for part in text_parts if part)
            if not content:
                continue
            section_key = _slug(title)
            sections.append(
                EvidenceRecord.build(
                    stable_key=f"ocpp21ed2:spec:part2:section:{section_key}:{page_start}",
                    source_path=p,
                    source_type="spec_pdf",
                    evidence_layer="spec",
                    record_type="spec_section",
                    title=title,
                    content=content,
                    page_start=page_start,
                    page_end=page_end,
                    section_title=title,
                    entity_name=_message_name_from_title(title),
                    entity_type="message" if _message_name_from_title(title) else None,
                    metadata={"toc_level": level},
                )
            )
        return sections
    finally:
        doc.close()


def _read_semicolon_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _read_xlsx_first_sheet(path: Path) -> list[list[str]]:
    ns = {
        "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
    }
    with zipfile.ZipFile(path) as zf:
        shared = _xlsx_shared_strings(zf, ns)
        workbook = ElementTree.fromstring(zf.read("xl/workbook.xml"))
        first_sheet = workbook.find("main:sheets/main:sheet", ns)
        if first_sheet is None:
            return []
        rel_id = first_sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        rels = ElementTree.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        target = None
        for rel in rels:
            if rel.attrib.get("Id") == rel_id:
                target = rel.attrib["Target"]
                break
        if target is None:
            return []
        sheet_path = "xl/" + target.lstrip("/")
        sheet = ElementTree.fromstring(zf.read(sheet_path))
        rows: list[list[str]] = []
        for row in sheet.findall(".//main:sheetData/main:row", ns):
            values: list[str] = []
            for cell in row.findall("main:c", ns):
                values.append(_xlsx_cell_value(cell, shared, ns))
            rows.append(values)
        return rows


def _xlsx_shared_strings(zf: zipfile.ZipFile, ns: dict[str, str]) -> list[str]:
    try:
        root = ElementTree.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    strings: list[str] = []
    for si in root.findall("main:si", ns):
        text = "".join(t.text or "" for t in si.findall(".//main:t", ns))
        strings.append(text)
    return strings


def _xlsx_cell_value(
    cell: ElementTree.Element, shared: list[str], ns: dict[str, str]
) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(t.text or "" for t in cell.findall(".//main:t", ns))
    value = cell.find("main:v", ns)
    if value is None or value.text is None:
        return ""
    if cell_type == "s":
        index = int(value.text)
        return shared[index] if index < len(shared) else ""
    return value.text


def _iter_schema_fields(
    schema: dict[str, Any],
    definitions: dict[str, Any],
) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    required = set(schema.get("required", []))
    for name, prop in schema.get("properties", {}).items():
        fields.extend(
            _schema_property_records(
                name=name,
                prop=prop,
                definitions=definitions,
                path=name,
                required=name in required,
                depth=0,
            )
        )
    return fields


def _schema_property_records(
    *,
    name: str,
    prop: dict[str, Any],
    definitions: dict[str, Any],
    path: str,
    required: bool,
    depth: int,
) -> list[dict[str, Any]]:
    if depth > 4:
        return []
    resolved = _resolve_ref(prop, definitions)
    record = {
        "name": name,
        "path": path,
        "required": required,
        "type": resolved.get("type") or prop.get("type"),
        "ref": prop.get("$ref"),
        "enum": resolved.get("enum", []),
        "maxLength": resolved.get("maxLength") or prop.get("maxLength"),
        "description": _clean(resolved.get("description") or prop.get("description")),
    }
    records = [record]
    child_required = set(resolved.get("required", []))
    for child_name, child_prop in resolved.get("properties", {}).items():
        records.extend(
            _schema_property_records(
                name=child_name,
                prop=child_prop,
                definitions=definitions,
                path=f"{path}.{child_name}",
                required=child_name in child_required,
                depth=depth + 1,
            )
        )
    return records


def _resolve_ref(prop: dict[str, Any], definitions: dict[str, Any]) -> dict[str, Any]:
    ref = prop.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/definitions/"):
        return prop
    return definitions.get(ref.rsplit("/", 1)[-1], prop)


def _message_from_schema_path(path: Path) -> tuple[str, str]:
    stem = path.stem
    for suffix, direction in (("Request", "req"), ("Response", "conf")):
        if stem.endswith(suffix):
            return stem[: -len(suffix)], direction
    return stem, "message"


def _schema_message_content(
    message_name: str, direction: str, schema: dict[str, Any]
) -> str:
    required = ", ".join(schema.get("required", [])) or "none"
    properties = ", ".join(schema.get("properties", {}).keys()) or "none"
    return (
        f"JSON schema for {message_name}.{direction}. "
        f"Required top-level fields: {required}. "
        f"Top-level properties: {properties}."
    )


def _schema_field_content(message_name: str, direction: str, field: dict[str, Any]) -> str:
    required = "required" if field["required"] else "optional"
    datatype = field.get("type") or field.get("ref") or "unspecified"
    enum_values = field.get("enum") or []
    enum_text = f" Enum values: {', '.join(enum_values)}." if enum_values else ""
    description = field.get("description") or ""
    return (
        f"{message_name}.{direction} field {field['path']} is {required}. "
        f"Type: {datatype}.{enum_text} {description}"
    ).strip()


def _schema_definition_content(name: str, definition: dict[str, Any]) -> str:
    required = ", ".join(definition.get("required", [])) or "none"
    enum_values = definition.get("enum") or []
    if enum_values:
        return f"Schema definition {name} is an enum with values: {', '.join(enum_values)}."
    props = ", ".join(definition.get("properties", {}).keys()) or "none"
    return f"Schema definition {name}. Required fields: {required}. Properties: {props}."


def _records_by_page(path: Path, doc: Any) -> list[EvidenceRecord]:
    records: list[EvidenceRecord] = []
    for page_index in range(doc.page_count):
        page_num = page_index + 1
        text = doc.load_page(page_index).get_text(sort=True).strip()
        if not text:
            continue
        records.append(
            EvidenceRecord.build(
                stable_key=f"ocpp21ed2:spec:part2:page:{page_num}",
                source_path=path,
                source_type="spec_pdf",
                evidence_layer="spec",
                record_type="spec_page",
                title=f"Part 2 page {page_num}",
                content=text,
                page_start=page_num,
                page_end=page_num,
            )
        )
    return records


def _classify_dm_record(
    path: Path, component: str, variable: str
) -> tuple[str, str | None, str | None]:
    if path.name == "components.csv":
        return "dm_component", "component", component
    if path.name == "variables.csv":
        return "dm_variable", "variable", variable or component
    if component and variable:
        return "dm_component_variable", "variable", variable
    return "dm_appendix_record", None, variable or component or None


def _dm_content(
    *,
    component: str,
    variable: str,
    instance: str,
    datatype: str,
    unit: str,
    required: str,
    description: str,
) -> str:
    parts = []
    if component:
        parts.append(f"Component: {component}.")
    if variable:
        parts.append(f"Variable: {variable}.")
    if instance:
        parts.append(f"Instance: {instance}.")
    if datatype:
        parts.append(f"Data type: {datatype}.")
    if unit:
        parts.append(f"Unit: {unit}.")
    if required:
        parts.append(f"Required: {required}.")
    if description:
        parts.append(f"Description: {description}")
    return " ".join(parts) or "Device Model appendix record."


def _normalize_header(value: str | None) -> str:
    value = _clean(value)
    value = value.replace("?", "")
    value = re.sub(r"[^0-9A-Za-z]+", "_", value)
    return value.strip("_").lower()


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\r", "\n")).strip()


def _first(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key, "")
        if value:
            return value
    return ""


def _slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "-", value.lower()).strip("-")
    return slug or "untitled"


def _message_name_from_title(title: str) -> str | None:
    match = re.search(r"\b([A-Z][A-Za-z0-9]+)(?:\.(?:req|conf))?\b", title)
    return match.group(1) if match else None
