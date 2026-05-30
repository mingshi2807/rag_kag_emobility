"""Quality eval scoring tests."""

from __future__ import annotations

from uuid import uuid4

from rag_ocpp.eval.quality import (
    QualityCase,
    build_report,
    default_quality_cases,
    filter_cases,
    score_case,
)
from rag_ocpp.retrieval.hybrid import (
    _ensure_evidence_layer_coverage,
    _topic_dm_query,
    _topic_spec_query,
)
from rag_ocpp.retrieval.searchers import ScoredChunk


def test_default_quality_cases_cover_r_q_k_and_all_modes():
    cases = default_quality_cases()
    assert len(cases) == 12
    for topic in ("Section R", "Section Q", "Section K"):
        topic_cases = [case for case in cases if case.topic.startswith(topic)]
        assert {case.mode for case in topic_cases} == {"spec", "dm", "schema", "fusion"}


def test_filter_cases_by_topic_and_mode():
    cases = filter_cases(default_quality_cases(), topics=["DER"], modes=["fusion"])
    assert [case.case_id for case in cases] == ["R-FUSION-DER-IMPLEMENTATION"]


def test_score_case_requires_layers_and_terms():
    case = QualityCase(
        case_id="X",
        topic="Section X",
        mode="fusion",
        query="demo",
        required_layers=("spec", "schema"),
        required_terms=("BootNotification", "Request"),
        optional_terms=("Response",),
    )
    result = score_case(
        case,
        [
            _chunk(
                "BootNotification Request behavior",
                layer="spec",
                section_title="BootNotification",
            )
        ],
    )
    assert not result.passed
    assert result.missing_layers == ["schema"]
    assert result.missing_required_terms == []


def test_score_case_passes_with_required_coverage():
    case = QualityCase(
        case_id="X",
        topic="Section X",
        mode="fusion",
        query="demo",
        required_layers=("spec", "schema"),
        required_terms=("BootNotification", "Request"),
        optional_terms=("Response",),
    )
    result = score_case(
        case,
        [
            _chunk("BootNotification Request objective", layer="spec"),
            _chunk("BootNotification Response schema", layer="schema"),
        ],
    )
    assert result.passed
    assert result.score == 1.0


def test_score_case_reports_ontology_metrics_for_graph_chunks():
    case = QualityCase(
        case_id="X",
        topic="Section X",
        mode="fusion",
        query="demo",
        required_layers=("device_model",),
        required_terms=("Component",),
    )

    result = score_case(
        case,
        [
            _chunk(
                "Component Variable",
                layer="device_model",
                strategy="graph",
                extra_metadata={
                    "graph_semantic_links": 2,
                    "graph_ontology_relations": ["component_has_variable"],
                    "graph_ontology_rules": ["dm_component_variable"],
                    "graph_ontology_versions": ["ocpp21-ed2-v1"],
                    "graph_traversal_depth": 1,
                },
            )
        ],
    )
    report = build_report([result], suite="test", top_k=1, fail_under=0.5)
    markdown = report.to_markdown()

    assert result.ontology_metrics["graph_chunks"] == 1
    assert result.ontology_metrics["graph_chunks_with_semantic_links"] == 1
    assert result.ontology_metrics["semantic_links_total"] == 2
    assert result.ontology_metrics["max_traversal_depth"] == 1
    assert result.ontology_metrics["ontology_relations"] == ["component_has_variable"]
    assert report.ontology_metrics["ontology_rules"] == ["dm_component_variable"]
    assert "## Ontology Metrics" in markdown
    assert "semantic_links=2" in markdown


def test_build_report_fails_if_any_case_fails():
    passed = score_case(
        QualityCase("A", "T", "spec", "q", ("spec",), ("DER",)),
        [_chunk("DER", layer="spec")],
    )
    failed = score_case(
        QualityCase("B", "T", "schema", "q", ("schema",), ("DER",)),
        [_chunk("DER", layer="spec")],
    )
    report = build_report([passed, failed], suite="test", top_k=5, fail_under=0.5)
    assert not report.passed
    assert report.num_cases == 2
    assert report.num_passed == 1


def test_fusion_layer_coverage_adds_missing_schema_candidate():
    spec = _chunk("DER control", layer="spec")
    dm = _chunk("DER Component Variable", layer="device_model")
    schema = _chunk("DER Request Response schema", layer="schema")

    result = _ensure_evidence_layer_coverage(
        "DER control implementation",
        [spec, dm],
        [spec, dm, schema],
        ("spec", "device_model", "schema"),
        3,
    )

    assert [(chunk.metadata or {}).get("evidence_layer") for chunk in result] == [
        "spec",
        "device_model",
        "schema",
    ]


def test_fusion_layer_coverage_prefers_query_relevant_layer_candidate():
    generic_dm = _chunk("Component Variable NetworkProfile", layer="device_model")
    der_dm = _chunk("ACDERCtrlr Component Variable DER control", layer="device_model")

    result = _ensure_evidence_layer_coverage(
        "DER control implementation",
        [_chunk("DER spec", layer="spec")],
        [generic_dm, der_dm],
        ("spec", "device_model"),
        2,
    )

    assert result[-1].content == "ACDERCtrlr Component Variable DER control"


def test_fusion_layer_coverage_replaces_weak_existing_layer_candidate():
    generic_dm = _chunk("Component Variable NetworkProfile", layer="device_model")
    der_dm = _chunk("ACDERCtrlr Component Variable DER control", layer="device_model")

    result = _ensure_evidence_layer_coverage(
        "DER control implementation",
        [_chunk("DER spec", layer="spec"), generic_dm],
        [_chunk("DER spec", layer="spec"), generic_dm, der_dm],
        ("spec", "device_model"),
        2,
    )

    assert result[-1].content == "ACDERCtrlr Component Variable DER control"


def test_fusion_layer_coverage_prefers_v2x_spec_anchor_over_generic_spec():
    reservation = _chunk(
        "V2X energy service generic mention",
        layer="spec",
        section_title="2.9. Reservation related",
    )
    q_section = _chunk(
        "Bidirectional Power Transfer V2X energy services",
        layer="spec",
        section_title="Q. Bidirectional Power Transfer",
    )

    result = _ensure_evidence_layer_coverage(
        "V2X energy services implementation",
        [reservation],
        [reservation, q_section],
        ("spec",),
        1,
    )

    assert result[0].section_title == "Q. Bidirectional Power Transfer"


def test_topic_spec_query_expands_v2x_to_section_q_anchors():
    query = _topic_spec_query("Build implementation guidance for V2X energy services")

    assert "Bidirectional Power Transfer" in query
    assert "operation modes" in query
    assert "central V2X control" in query


def test_topic_dm_query_expands_v2x_to_v2x_charging_controller():
    query = _topic_dm_query("Build implementation guidance for V2X energy services")

    assert "V2XChargingCtrlr" in query
    assert "SupportedEnergyTransferModes" in query


def test_fusion_layer_coverage_does_not_overwrite_inserted_required_layers():
    spec = _chunk("Q09 V2X control", layer="spec")
    dm = _chunk("V2XChargingCtrlr SupportedEnergyTransferModes", layer="device_model")
    schema = _chunk("NotifyEVChargingNeeds v2xChargingParameters", layer="schema")
    generic = _chunk("generic V2X mention", layer="unknown")

    result = _ensure_evidence_layer_coverage(
        "V2X energy services implementation",
        [spec, generic],
        [spec, generic, dm, schema],
        ("spec", "device_model", "schema"),
        3,
    )

    layers = {(chunk.metadata or {}).get("evidence_layer") for chunk in result}
    assert "device_model" in layers
    assert "schema" in layers


def _chunk(
    content: str,
    *,
    layer: str,
    section_title: str | None = None,
    strategy: str = "keyword",
    extra_metadata: dict | None = None,
) -> ScoredChunk:
    metadata = {
        "evidence_layer": layer,
        "source_type": "spec_pdf" if layer == "spec" else "json_schema",
        "source_path": f"{layer}.txt",
    }
    metadata.update(extra_metadata or {})
    return ScoredChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        content=content,
        section_title=section_title,
        page_start=1,
        page_end=1,
        score=1.0,
        strategy=strategy,
        metadata=metadata,
    )
