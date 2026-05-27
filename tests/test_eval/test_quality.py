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
from rag_ocpp.retrieval.hybrid import _ensure_evidence_layer_coverage
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


def _chunk(
    content: str,
    *,
    layer: str,
    section_title: str | None = None,
) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        content=content,
        section_title=section_title,
        page_start=1,
        page_end=1,
        score=1.0,
        strategy="keyword",
        metadata={
            "evidence_layer": layer,
            "source_type": "spec_pdf" if layer == "spec" else "json_schema",
            "source_path": f"{layer}.txt",
        },
    )
