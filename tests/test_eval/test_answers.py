"""Golden answer scoring tests."""

from __future__ import annotations

from rag_ocpp.eval.answers import (
    build_answer_report,
    default_golden_answer_cases,
    filter_answer_cases,
    generation_query_for,
    score_answer,
)
from rag_ocpp.generation.prompt import render_golden_answer_messages


def test_default_golden_answer_cases_cover_fusion_topics():
    cases = default_golden_answer_cases()
    assert len(cases) == 3
    assert {case.quality_case_id for case in cases} == {
        "R-FUSION-DER-IMPLEMENTATION",
        "Q-FUSION-V2X-IMPLEMENTATION",
        "K-FUSION-SMART-CHARGING-IMPLEMENTATION",
    }


def test_filter_answer_cases_by_topic():
    cases = filter_answer_cases(default_golden_answer_cases(), topics=["V2X"])
    assert [case.quality_case_id for case in cases] == ["Q-FUSION-V2X-IMPLEMENTATION"]


def test_score_answer_passes_markdown_implementation_contract():
    case = filter_answer_cases(default_golden_answer_cases(), topics=["DER"])[0]
    answer = """
## Purpose
DER control coordinates OCPP control behavior for implementation teams.

## Normative behavior
- The backend uses DER control Request and Response evidence from the schema.
- The Device Model exposes DER control capability through DCDERCtrlr.

## Implementation guidance
- Validate schema payloads before applying DER control.
- Persist Device Model state and reject unsupported control modes.

## Conformance-test focus
- Test Request validation, Response handling, and control state transitions.

## Evidence gaps
No additional evidence gap was found in the retrieved evidence.

[2.18. DER Control related](spec, page 10)
"""

    result = score_answer(case, answer)

    assert result.passed
    assert result.score >= 0.90


def test_score_answer_fails_when_required_sections_are_missing():
    case = filter_answer_cases(default_golden_answer_cases(), topics=["V2X"])[0]
    result = score_answer(case, "V2X energy Device Model schema Request")

    assert not result.passed
    assert result.missing_headings


def test_score_answer_accepts_numbered_and_british_heading_variants():
    case = filter_answer_cases(default_golden_answer_cases(), topics=["DER"])[0]
    answer = """
# Guide
## 1. Purpose and Scope
DER control Device Model schema Request.
## 2. Normative Behaviour
Evidence.
## 3. Backend Implementation Logic
DCDERCtrlr SetDERControl ReportDERControl.
## 4. Testing Focus
Conformance tests.
## 5. Limitations
Evidence gaps.
[2.18. DER Control related, page 10]
"""

    result = score_answer(case, answer)

    assert result.missing_headings == []


def test_generation_query_requires_exact_golden_headings():
    case = filter_answer_cases(default_golden_answer_cases(), topics=["smart"])[0]
    query = generation_query_for(case)

    assert "Use exactly these top-level section headings" in query
    assert "## Purpose" in query
    assert "## Evidence gaps" in query


def test_render_golden_answer_messages_enforces_template_contract():
    case = filter_answer_cases(default_golden_answer_cases(), topics=["DER"])[0]
    messages = render_golden_answer_messages(
        case.query,
        [
            {
                "content": "DER control schema Request evidence.",
                "section_title": "2.18. DER Control related",
                "document_title": "OCPP-2.1_edition2_part2_specification.pdf",
                "page_start": 10,
                "evidence_layer": "spec",
                "source_type": "spec_pdf",
            }
        ],
        required_headings=case.required_headings,
        required_terms=case.required_terms,
        optional_terms=case.optional_terms,
    )

    assert messages[0]["role"] == "system"
    assert "Use exactly the requested H2 headings" in messages[0]["content"]
    assert "Do not number, rename, skip" in messages[0]["content"]
    assert messages[1]["content"].count("## Purpose") == 1
    assert messages[1]["content"].count("## Evidence gaps") == 1
    assert "The only H2 headings are exactly" in messages[1]["content"]


def test_build_answer_report_fails_if_any_case_fails():
    case = filter_answer_cases(default_golden_answer_cases(), topics=["smart"])[0]
    passed = score_answer(
        case,
        """
## Purpose
smart charging ChargingProfile Device Model schema SetChargingProfile
## Normative behavior
Evidence.
## Implementation guidance
validation limit SmartChargingCtrlr charging schedule
## Conformance-test focus
tests
## Evidence gaps
none
[2.10. Smart Charging related](spec, page 1)
""",
    )
    failed = score_answer(case, "smart charging ChargingProfile Device Model")

    report = build_answer_report([passed, failed], suite="test", fail_under=0.5)

    assert not report.passed
    assert report.num_cases == 2
    assert report.num_passed == 1
