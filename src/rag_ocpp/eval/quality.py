"""Manifest-driven retrieval quality evaluation for OCPP 2.1 Ed2."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from rag_ocpp.retrieval.searchers import ScoredChunk


@dataclass(frozen=True)
class QualityCase:
    """A source-aware retrieval evaluation case.

    The case avoids hard-coded chunk UUIDs so the suite remains usable after a
    fresh corpus rebuild. It checks whether top-k retrieval contains the
    expected evidence layers and domain vocabulary for implementation-grade
    OCPP answers.
    """

    case_id: str
    topic: str
    mode: str
    query: str
    required_layers: tuple[str, ...]
    required_terms: tuple[str, ...]
    optional_terms: tuple[str, ...] = ()
    evidence_layer: str | None = None
    min_score: float = 0.75


@dataclass
class QualityCaseResult:
    case_id: str
    topic: str
    mode: str
    query: str
    passed: bool
    score: float
    layer_score: float
    required_term_score: float
    optional_term_score: float
    missing_layers: list[str] = field(default_factory=list)
    missing_required_terms: list[str] = field(default_factory=list)
    matched_optional_terms: list[str] = field(default_factory=list)
    top_chunks: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: int = 0
    strategy_breakdown: dict[str, int] = field(default_factory=dict)
    ontology_metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityReport:
    suite: str
    top_k: int
    fail_under: float
    passed: bool
    score: float
    cases: list[QualityCaseResult]
    ontology_metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def num_cases(self) -> int:
        return len(self.cases)

    @property
    def num_passed(self) -> int:
        return sum(1 for case in self.cases if case.passed)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        om = self.ontology_metrics
        graph_candidate_chunks = om.get("graph_candidate_chunks", 0)
        graph_candidate_link_chunks = om.get(
            "graph_candidate_chunks_with_semantic_links", 0
        )
        graph_candidate_links = om.get("graph_candidate_semantic_links_total", 0)
        final_graph_chunks = om.get("final_graph_chunks", om.get("graph_chunks", 0))
        final_graph_link_chunks = om.get(
            "final_graph_chunks_with_semantic_links",
            om.get("graph_chunks_with_semantic_links", 0),
        )
        max_depth = om.get(
            "graph_candidate_max_traversal_depth",
            om.get("max_traversal_depth", 0),
        )
        relations = om.get("graph_candidate_ontology_relations", om.get("ontology_relations", []))
        rules = om.get("graph_candidate_ontology_rules", om.get("ontology_rules", []))
        lines = [
            f"# OCPP Query Quality Evaluation: {self.suite}",
            "",
            f"- Cases: `{self.num_cases}`",
            f"- Passed: `{self.num_passed}/{self.num_cases}`",
            f"- Score: `{self.score:.3f}`",
            f"- Fail-under: `{self.fail_under:.3f}`",
            f"- Status: `{'PASS' if self.passed else 'FAIL'}`",
            "",
            "## Ontology Metrics",
            "",
            f"- Graph candidate chunks: `{graph_candidate_chunks}`",
            f"- Graph candidate chunks with semantic links: `{graph_candidate_link_chunks}`",
            f"- Graph candidate semantic links: `{graph_candidate_links}`",
            f"- Final graph chunks: `{final_graph_chunks}`",
            f"- Final graph chunks with semantic links: `{final_graph_link_chunks}`",
            f"- Max traversal depth: `{max_depth}`",
            f"- Ontology relation types: `{', '.join(relations) or 'none'}`",
            f"- Ontology mapping rules: `{', '.join(rules) or 'none'}`",
            "",
            "## Cases",
            "",
        ]
        for case in self.cases:
            case_om = case.ontology_metrics
            case_candidate_chunks = case_om.get(
                "graph_candidate_chunks", case_om.get("graph_chunks", 0)
            )
            case_candidate_link_chunks = case_om.get(
                "graph_candidate_chunks_with_semantic_links",
                case_om.get("graph_chunks_with_semantic_links", 0),
            )
            case_candidate_links = case_om.get(
                "graph_candidate_semantic_links_total",
                case_om.get("semantic_links_total", 0),
            )
            case_final_chunks = case_om.get(
                "final_graph_chunks", case_om.get("graph_chunks", 0)
            )
            case_max_depth = case_om.get(
                "graph_candidate_max_traversal_depth",
                case_om.get("max_traversal_depth", 0),
            )
            lines.extend(
                [
                    f"### {case.case_id} - {'PASS' if case.passed else 'FAIL'}",
                    "",
                    f"- Topic: `{case.topic}`",
                    f"- Mode: `{case.mode}`",
                    f"- Score: `{case.score:.3f}`",
                    f"- Layer score: `{case.layer_score:.3f}`",
                    f"- Required term score: `{case.required_term_score:.3f}`",
                    f"- Optional term score: `{case.optional_term_score:.3f}`",
                    f"- Latency: `{case.latency_ms}ms`",
                    f"- Strategy: `{case.strategy_breakdown}`",
                    f"- Query: {case.query}",
                    "- Ontology metrics: "
                    f"`candidate_graph_chunks={case_candidate_chunks}, "
                    f"candidate_semantic_link_chunks={case_candidate_link_chunks}, "
                    f"candidate_semantic_links={case_candidate_links}, "
                    f"final_graph_chunks={case_final_chunks}, "
                    f"max_depth={case_max_depth}`",
                ]
            )
            if case.missing_layers:
                lines.append(f"- Missing layers: `{', '.join(case.missing_layers)}`")
            if case.missing_required_terms:
                lines.append(
                    f"- Missing required terms: `{', '.join(case.missing_required_terms)}`"
                )
            if case.matched_optional_terms:
                lines.append(
                    f"- Matched optional terms: `{', '.join(case.matched_optional_terms)}`"
                )
            coverage = _layer_coverage(case.top_chunks)
            if coverage:
                lines.extend(["", "Evidence layer coverage:"])
                for layer, chunk in coverage.items():
                    lines.append(
                        "- "
                        f"`{layer}` "
                        f"`{chunk.get('source_type') or 'unknown'}` "
                        f"`{chunk.get('section_title') or 'untitled'}` "
                        f"`{chunk.get('chunk_id')}`"
                    )
            lines.extend(["", "Top evidence:"])
            for chunk in case.top_chunks[:5]:
                lines.append(
                    "- "
                    f"`{chunk.get('evidence_layer') or 'unknown'}` "
                    f"`{chunk.get('source_type') or 'unknown'}` "
                    f"`{chunk.get('section_title') or 'untitled'}` "
                    f"`{chunk.get('chunk_id')}`"
                )
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def default_quality_cases() -> list[QualityCase]:
    """Return the enterprise baseline suite for OCPP 2.1 Ed2 R/Q/K work."""
    return [
        QualityCase(
            case_id="R-SPEC-DER-CONTROL",
            topic="Section R DER control",
            mode="spec",
            query=(
                "In OCPP 2.1 Ed2 Section R, what are the DER control objectives, "
                "requirements, and implementation responsibilities?"
            ),
            evidence_layer="spec",
            required_layers=("spec",),
            required_terms=("DER", "control", "requirements"),
            optional_terms=("distributed energy resource", "setpoint", "curve"),
        ),
        QualityCase(
            case_id="R-DM-DER-COMPONENTS",
            topic="Section R DER control",
            mode="dm",
            query=(
                "Which Device Model components and variables are relevant for "
                "OCPP 2.1 Ed2 DER control implementation?"
            ),
            evidence_layer="device_model",
            required_layers=("device_model",),
            required_terms=("DER", "Component", "Variable"),
            optional_terms=("required", "datatype", "mutability"),
        ),
        QualityCase(
            case_id="R-SCHEMA-DER-MESSAGES",
            topic="Section R DER control",
            mode="schema",
            query=(
                "Which OCPP 2.1 JSON schemas define DER control request and "
                "response payload constraints?"
            ),
            evidence_layer="schema",
            required_layers=("schema",),
            required_terms=("DER", "Request", "Response"),
            optional_terms=("required", "properties", "enum"),
        ),
        QualityCase(
            case_id="R-FUSION-DER-IMPLEMENTATION",
            topic="Section R DER control",
            mode="fusion",
            query=(
                "Build senior backend implementation guidance for OCPP 2.1 Ed2 "
                "DER control using Part 2 spec behavior, Device Model components "
                "and variables, and JSON schema validation."
            ),
            required_layers=("spec", "device_model", "schema"),
            required_terms=("DER", "control", "Component", "Request"),
            optional_terms=("Response", "Variable", "requirements", "validation"),
            min_score=0.70,
        ),
        QualityCase(
            case_id="Q-SPEC-V2X-ENERGY",
            topic="Section Q V2X energy services",
            mode="spec",
            query=(
                "In OCPP 2.1 Ed2 Section Q, what V2X energy services behavior "
                "must a charging station backend implement?"
            ),
            evidence_layer="spec",
            required_layers=("spec",),
            required_terms=("V2X", "energy", "services"),
            optional_terms=("bidirectional", "EV", "grid"),
        ),
        QualityCase(
            case_id="Q-DM-V2X-COMPONENTS",
            topic="Section Q V2X energy services",
            mode="dm",
            query=(
                "Which Device Model components and variables support V2X energy "
                "services in OCPP 2.1 Ed2?"
            ),
            evidence_layer="device_model",
            required_layers=("device_model",),
            required_terms=("V2X", "Component", "Variable"),
            optional_terms=("EVSE", "required", "datatype"),
        ),
        QualityCase(
            case_id="Q-SCHEMA-V2X-PAYLOADS",
            topic="Section Q V2X energy services",
            mode="schema",
            query=(
                "Which OCPP 2.1 JSON schemas and payload fields are relevant to "
                "V2X energy services?"
            ),
            evidence_layer="schema",
            required_layers=("schema",),
            required_terms=("V2X", "schema", "field"),
            optional_terms=("required", "properties", "enum"),
            min_score=0.65,
        ),
        QualityCase(
            case_id="Q-FUSION-V2X-IMPLEMENTATION",
            topic="Section Q V2X energy services",
            mode="fusion",
            query=(
                "Build implementation guidance for OCPP 2.1 Ed2 V2X energy "
                "services using spec rules, Device Model configuration, and JSON schemas."
            ),
            required_layers=("spec", "device_model", "schema"),
            required_terms=("V2X", "energy", "Component", "schema"),
            optional_terms=("services", "Variable", "Request", "validation"),
            min_score=0.70,
        ),
        QualityCase(
            case_id="K-SPEC-SMART-CHARGING",
            topic="Section K smart charging",
            mode="spec",
            query=(
                "In OCPP 2.1 Ed2 Section K, what are the smart charging purposes, "
                "profiles, limits, and implementation responsibilities?"
            ),
            evidence_layer="spec",
            required_layers=("spec",),
            required_terms=("smart charging", "profile", "limit"),
            optional_terms=("ChargingProfile", "schedule", "transaction"),
        ),
        QualityCase(
            case_id="K-DM-SMART-CHARGING-COMPONENTS",
            topic="Section K smart charging",
            mode="dm",
            query=(
                "Which Device Model components and variables configure smart "
                "charging in OCPP 2.1 Ed2?"
            ),
            evidence_layer="device_model",
            required_layers=("device_model",),
            required_terms=("SmartCharging", "Component", "Variable"),
            optional_terms=("ChargingStation", "EVSE", "required"),
        ),
        QualityCase(
            case_id="K-SCHEMA-SMART-CHARGING",
            topic="Section K smart charging",
            mode="schema",
            query=(
                "Which JSON schemas define OCPP 2.1 smart charging messages such "
                "as SetChargingProfile and charging schedule payloads?"
            ),
            evidence_layer="schema",
            required_layers=("schema",),
            required_terms=("SetChargingProfile", "ChargingProfile", "schema"),
            optional_terms=("chargingSchedule", "required", "properties"),
        ),
        QualityCase(
            case_id="K-FUSION-SMART-CHARGING-IMPLEMENTATION",
            topic="Section K smart charging",
            mode="fusion",
            query=(
                "Build senior backend implementation guidance for OCPP 2.1 Ed2 "
                "smart charging using Section K spec behavior, Device Model "
                "variables, and JSON schema validation."
            ),
            required_layers=("spec", "device_model", "schema"),
            required_terms=("smart charging", "ChargingProfile", "Component", "schema"),
            optional_terms=("Variable", "SetChargingProfile", "limit", "validation"),
            min_score=0.70,
        ),
    ]


def filter_cases(
    cases: list[QualityCase], *, topics: list[str] | None = None, modes: list[str] | None = None
) -> list[QualityCase]:
    topic_set = {item.lower() for item in topics or []}
    mode_set = {item.lower() for item in modes or []}
    selected = []
    for case in cases:
        if topic_set and not any(item in case.topic.lower() for item in topic_set):
            continue
        if mode_set and case.mode.lower() not in mode_set:
            continue
        selected.append(case)
    return selected


def score_case(
    case: QualityCase,
    chunks: list[ScoredChunk],
    *,
    latency_ms: int = 0,
    strategy_breakdown: dict[str, int] | None = None,
    retrieval_ontology_metrics: dict[str, Any] | None = None,
) -> QualityCaseResult:
    layers = {_layer(chunk) for chunk in chunks}
    missing_layers = [layer for layer in case.required_layers if layer not in layers]

    haystack = "\n".join(_chunk_search_text(chunk) for chunk in chunks).lower()
    missing_terms = [term for term in case.required_terms if term.lower() not in haystack]
    matched_optional = [term for term in case.optional_terms if term.lower() in haystack]

    layer_score = _ratio(len(case.required_layers) - len(missing_layers), len(case.required_layers))
    required_term_score = _ratio(
        len(case.required_terms) - len(missing_terms), len(case.required_terms)
    )
    optional_term_score = _ratio(len(matched_optional), len(case.optional_terms))
    score = (layer_score * 0.45) + (required_term_score * 0.45) + (optional_term_score * 0.10)
    passed = not missing_layers and not missing_terms and score >= case.min_score

    top_chunks = [_chunk_summary(chunk) for chunk in chunks]
    final_metrics = _ontology_metrics(top_chunks)
    return QualityCaseResult(
        case_id=case.case_id,
        topic=case.topic,
        mode=case.mode,
        query=case.query,
        passed=passed,
        score=score,
        layer_score=layer_score,
        required_term_score=required_term_score,
        optional_term_score=optional_term_score,
        missing_layers=missing_layers,
        missing_required_terms=missing_terms,
        matched_optional_terms=matched_optional,
        top_chunks=top_chunks,
        latency_ms=latency_ms,
        strategy_breakdown=strategy_breakdown or {},
        ontology_metrics=_merge_retrieval_ontology_metrics(
            final_metrics,
            retrieval_ontology_metrics,
        ),
    )


def build_report(
    results: list[QualityCaseResult], *, suite: str, top_k: int, fail_under: float
) -> QualityReport:
    score = sum(case.score for case in results) / len(results) if results else 0.0
    passed = bool(results) and score >= fail_under and all(case.passed for case in results)
    return QualityReport(
        suite=suite,
        top_k=top_k,
        fail_under=fail_under,
        passed=passed,
        score=score,
        cases=results,
        ontology_metrics=_aggregate_ontology_metrics(
            [result.ontology_metrics for result in results]
        ),
    )


def write_report(report: QualityReport, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    else:
        path.write_text(report.to_markdown(), encoding="utf-8")


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return max(0.0, min(1.0, numerator / denominator))


def _layer(chunk: ScoredChunk) -> str:
    return str((chunk.metadata or {}).get("evidence_layer") or "unknown")


def _chunk_search_text(chunk: ScoredChunk) -> str:
    metadata = chunk.metadata or {}
    metadata_values = " ".join(str(value) for value in metadata.values() if value is not None)
    return " ".join(
        [
            chunk.content,
            chunk.section_title or "",
            metadata.get("source_path") or "",
            metadata.get("source_type") or "",
            metadata.get("record_type") or "",
            metadata_values,
        ]
    )


def _chunk_summary(chunk: ScoredChunk) -> dict[str, Any]:
    metadata = chunk.metadata or {}
    return {
        "chunk_id": str(chunk.chunk_id),
        "document_id": str(chunk.document_id),
        "section_title": chunk.section_title,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "strategy": chunk.strategy,
        "score": chunk.score,
        "evidence_layer": metadata.get("evidence_layer"),
        "source_type": metadata.get("source_type"),
        "source_path": metadata.get("source_path"),
        "record_type": metadata.get("record_type"),
        "entity_name": metadata.get("entity_name"),
        "graph_semantic_links": metadata.get("graph_semantic_links"),
        "graph_ontology_relations": metadata.get("graph_ontology_relations"),
        "graph_ontology_rules": metadata.get("graph_ontology_rules"),
        "graph_ontology_versions": metadata.get("graph_ontology_versions"),
        "graph_traversal_depth": metadata.get("graph_traversal_depth"),
    }


def _layer_coverage(chunks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    coverage: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        layer = str(chunk.get("evidence_layer") or "unknown")
        if layer in coverage:
            continue
        coverage[layer] = chunk
    return coverage


def _ontology_metrics(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    graph_chunks = [chunk for chunk in chunks if chunk.get("strategy") == "graph"]
    semantic_link_chunks = [
        chunk for chunk in graph_chunks if _positive_int(chunk.get("graph_semantic_links")) > 0
    ]
    semantic_links_total = sum(
        _positive_int(chunk.get("graph_semantic_links")) for chunk in graph_chunks
    )
    depths = [
        _positive_int(chunk.get("graph_traversal_depth"))
        for chunk in graph_chunks
        if chunk.get("graph_traversal_depth") is not None
    ]
    return {
        "graph_chunks": len(graph_chunks),
        "graph_chunks_with_semantic_links": len(semantic_link_chunks),
        "semantic_links_total": semantic_links_total,
        "max_traversal_depth": max(depths, default=0),
        "ontology_relations": _sorted_values(
            value
            for chunk in graph_chunks
            for value in _list_values(chunk.get("graph_ontology_relations"))
        ),
        "ontology_rules": _sorted_values(
            value
            for chunk in graph_chunks
            for value in _list_values(chunk.get("graph_ontology_rules"))
        ),
        "ontology_versions": _sorted_values(
            value
            for chunk in graph_chunks
            for value in _list_values(chunk.get("graph_ontology_versions"))
        ),
    }


def _aggregate_ontology_metrics(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "graph_chunks": sum(_positive_int(item.get("graph_chunks")) for item in metrics),
        "graph_chunks_with_semantic_links": sum(
            _positive_int(item.get("graph_chunks_with_semantic_links")) for item in metrics
        ),
        "semantic_links_total": sum(
            _positive_int(item.get("semantic_links_total")) for item in metrics
        ),
        "max_traversal_depth": max(
            (_positive_int(item.get("max_traversal_depth")) for item in metrics),
            default=0,
        ),
        "ontology_relations": _sorted_values(
            value for item in metrics for value in _list_values(item.get("ontology_relations"))
        ),
        "ontology_rules": _sorted_values(
            value for item in metrics for value in _list_values(item.get("ontology_rules"))
        ),
        "ontology_versions": _sorted_values(
            value for item in metrics for value in _list_values(item.get("ontology_versions"))
        ),
        "graph_candidate_chunks": sum(
            _positive_int(item.get("graph_candidate_chunks")) for item in metrics
        ),
        "graph_candidate_chunks_with_semantic_links": sum(
            _positive_int(item.get("graph_candidate_chunks_with_semantic_links"))
            for item in metrics
        ),
        "graph_candidate_semantic_links_total": sum(
            _positive_int(item.get("graph_candidate_semantic_links_total"))
            for item in metrics
        ),
        "graph_candidate_max_traversal_depth": max(
            (
                _positive_int(item.get("graph_candidate_max_traversal_depth"))
                for item in metrics
            ),
            default=0,
        ),
        "graph_candidate_ontology_relations": _sorted_values(
            value
            for item in metrics
            for value in _list_values(item.get("graph_candidate_ontology_relations"))
        ),
        "graph_candidate_ontology_rules": _sorted_values(
            value
            for item in metrics
            for value in _list_values(item.get("graph_candidate_ontology_rules"))
        ),
        "graph_candidate_ontology_versions": _sorted_values(
            value
            for item in metrics
            for value in _list_values(item.get("graph_candidate_ontology_versions"))
        ),
        "final_graph_chunks": sum(
            _positive_int(item.get("final_graph_chunks", item.get("graph_chunks")))
            for item in metrics
        ),
        "final_graph_chunks_with_semantic_links": sum(
            _positive_int(
                item.get(
                    "final_graph_chunks_with_semantic_links",
                    item.get("graph_chunks_with_semantic_links"),
                )
            )
            for item in metrics
        ),
        "final_semantic_links_total": sum(
            _positive_int(
                item.get("final_semantic_links_total", item.get("semantic_links_total"))
            )
            for item in metrics
        ),
        "final_max_traversal_depth": max(
            (
                _positive_int(
                    item.get("final_max_traversal_depth", item.get("max_traversal_depth"))
                )
                for item in metrics
            ),
            default=0,
        ),
        "final_ontology_relations": _sorted_values(
            value
            for item in metrics
            for value in _list_values(
                item.get("final_ontology_relations", item.get("ontology_relations"))
            )
        ),
        "final_ontology_rules": _sorted_values(
            value
            for item in metrics
            for value in _list_values(item.get("final_ontology_rules", item.get("ontology_rules")))
        ),
        "final_ontology_versions": _sorted_values(
            value
            for item in metrics
            for value in _list_values(
                item.get("final_ontology_versions", item.get("ontology_versions"))
            )
        ),
    }


def _merge_retrieval_ontology_metrics(
    final_metrics: dict[str, Any],
    retrieval_metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    metrics = dict(final_metrics)
    metrics.update(
        {
            "final_graph_chunks": final_metrics["graph_chunks"],
            "final_graph_chunks_with_semantic_links": final_metrics[
                "graph_chunks_with_semantic_links"
            ],
            "final_semantic_links_total": final_metrics["semantic_links_total"],
            "final_max_traversal_depth": final_metrics["max_traversal_depth"],
            "final_ontology_relations": final_metrics["ontology_relations"],
            "final_ontology_rules": final_metrics["ontology_rules"],
            "final_ontology_versions": final_metrics["ontology_versions"],
        }
    )
    if retrieval_metrics:
        metrics.update(retrieval_metrics)
    else:
        metrics.update(
            {
                "graph_candidate_chunks": final_metrics["graph_chunks"],
                "graph_candidate_chunks_with_semantic_links": final_metrics[
                    "graph_chunks_with_semantic_links"
                ],
                "graph_candidate_semantic_links_total": final_metrics[
                    "semantic_links_total"
                ],
                "graph_candidate_max_traversal_depth": final_metrics[
                    "max_traversal_depth"
                ],
                "graph_candidate_ontology_relations": final_metrics["ontology_relations"],
                "graph_candidate_ontology_rules": final_metrics["ontology_rules"],
                "graph_candidate_ontology_versions": final_metrics["ontology_versions"],
            }
        )
    return metrics


def _positive_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _list_values(value: Any) -> list[str]:
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value if item is not None and str(item)]
    if value is None or value == "":
        return []
    return [str(value)]


def _sorted_values(values: Any) -> list[str]:
    return sorted(set(_list_values(list(values))))
