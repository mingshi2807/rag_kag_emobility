"""Golden answer evaluation for generated Markdown implementation guidance."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from rag_ocpp.eval.quality import QualityCase, default_quality_cases


@dataclass(frozen=True)
class GoldenAnswerCase:
    """Expected generated-answer contract for one implementation guidance query."""

    case_id: str
    quality_case_id: str
    topic: str
    query: str
    required_headings: tuple[str, ...]
    required_terms: tuple[str, ...]
    optional_terms: tuple[str, ...] = ()
    forbidden_terms: tuple[str, ...] = (
        "provided context does not contain",
        "i cannot answer",
        "not enough information",
    )
    min_score: float = 0.80


@dataclass
class GoldenAnswerResult:
    case_id: str
    topic: str
    query: str
    passed: bool
    score: float
    heading_score: float
    required_term_score: float
    optional_term_score: float
    markdown_score: float
    grounding_score: float
    ontology_trace_score: float
    missing_headings: list[str] = field(default_factory=list)
    missing_required_terms: list[str] = field(default_factory=list)
    missing_ontology_trace_items: list[str] = field(default_factory=list)
    matched_optional_terms: list[str] = field(default_factory=list)
    forbidden_matches: list[str] = field(default_factory=list)
    answer_chars: int = 0
    answer_excerpt: str = ""
    answer_path: str | None = None


@dataclass
class GoldenAnswerReport:
    suite: str
    fail_under: float
    passed: bool
    score: float
    cases: list[GoldenAnswerResult]

    @property
    def num_cases(self) -> int:
        return len(self.cases)

    @property
    def num_passed(self) -> int:
        return sum(1 for case in self.cases if case.passed)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        lines = [
            f"# OCPP Golden Answer Evaluation: {self.suite}",
            "",
            f"- Cases: `{self.num_cases}`",
            f"- Passed: `{self.num_passed}/{self.num_cases}`",
            f"- Score: `{self.score:.3f}`",
            f"- Fail-under: `{self.fail_under:.3f}`",
            f"- Status: `{'PASS' if self.passed else 'FAIL'}`",
            "",
            "## Cases",
            "",
        ]
        for case in self.cases:
            lines.extend(
                [
                    f"### {case.case_id} - {'PASS' if case.passed else 'FAIL'}",
                    "",
                    f"- Topic: `{case.topic}`",
                    f"- Score: `{case.score:.3f}`",
                    f"- Heading score: `{case.heading_score:.3f}`",
                    f"- Required term score: `{case.required_term_score:.3f}`",
                    f"- Optional term score: `{case.optional_term_score:.3f}`",
                    f"- Markdown score: `{case.markdown_score:.3f}`",
                    f"- Grounding score: `{case.grounding_score:.3f}`",
                    f"- Ontology trace score: `{case.ontology_trace_score:.3f}`",
                    f"- Answer chars: `{case.answer_chars}`",
                    f"- Query: {case.query}",
                ]
            )
            if case.answer_path:
                lines.append(f"- Answer: `{case.answer_path}`")
            if case.missing_headings:
                lines.append(f"- Missing headings: `{', '.join(case.missing_headings)}`")
            if case.missing_required_terms:
                lines.append(
                    f"- Missing required terms: `{', '.join(case.missing_required_terms)}`"
                )
            if case.missing_ontology_trace_items:
                lines.append(
                    "- Missing ontology trace items: "
                    f"`{', '.join(case.missing_ontology_trace_items)}`"
                )
            if case.matched_optional_terms:
                lines.append(
                    f"- Matched optional terms: `{', '.join(case.matched_optional_terms)}`"
                )
            if case.forbidden_matches:
                lines.append(f"- Forbidden matches: `{', '.join(case.forbidden_matches)}`")
            if case.answer_excerpt:
                lines.extend(["", "Answer excerpt:", "", case.answer_excerpt, ""])
        return "\n".join(lines).rstrip() + "\n"


def default_golden_answer_cases() -> list[GoldenAnswerCase]:
    quality_cases = {case.case_id: case for case in default_quality_cases()}
    return [
        _case(
            quality_cases["R-FUSION-DER-IMPLEMENTATION"],
            required_terms=(
                "DER",
                "control",
                "Device Model",
                "schema",
                "Request",
            ),
            optional_terms=(
                "DCDERCtrlr",
                "SetDERControl",
                "ReportDERControl",
                "validation",
            ),
        ),
        _case(
            quality_cases["Q-FUSION-V2X-IMPLEMENTATION"],
            required_terms=(
                "V2X",
                "energy",
                "Device Model",
                "schema",
                "Request",
            ),
            optional_terms=(
                "V2XChargingCtrlr",
                "NotifyEVChargingNeeds",
                "SupportedEnergyTransferModes",
                "validation",
            ),
        ),
        _case(
            quality_cases["K-FUSION-SMART-CHARGING-IMPLEMENTATION"],
            required_terms=(
                "smart charging",
                "ChargingProfile",
                "Device Model",
                "schema",
                "SetChargingProfile",
            ),
            optional_terms=(
                "SmartChargingCtrlr",
                "charging schedule",
                "limit",
                "validation",
            ),
        ),
    ]


def filter_answer_cases(
    cases: list[GoldenAnswerCase],
    *,
    topics: list[str] | None = None,
    case_ids: list[str] | None = None,
) -> list[GoldenAnswerCase]:
    topic_set = {item.lower() for item in topics or []}
    case_id_set = {item.lower() for item in case_ids or []}
    selected = []
    for case in cases:
        if topic_set and not any(item in case.topic.lower() for item in topic_set):
            continue
        if case_id_set and case.case_id.lower() not in case_id_set:
            continue
        selected.append(case)
    return selected


def score_answer(
    case: GoldenAnswerCase,
    answer: str,
    *,
    answer_path: str | None = None,
) -> GoldenAnswerResult:
    answer_lower = answer.lower()
    headings = _markdown_headings(answer)
    missing_headings = [
        heading
        for heading in case.required_headings
        if not _has_heading(heading, headings)
    ]
    missing_required_terms = [
        term for term in case.required_terms if term.lower() not in answer_lower
    ]
    matched_optional_terms = [
        term for term in case.optional_terms if term.lower() in answer_lower
    ]
    forbidden_matches = [
        term for term in case.forbidden_terms if term.lower() in answer_lower
    ]

    heading_score = _ratio(
        len(case.required_headings) - len(missing_headings),
        len(case.required_headings),
    )
    required_term_score = _ratio(
        len(case.required_terms) - len(missing_required_terms),
        len(case.required_terms),
    )
    optional_term_score = _ratio(len(matched_optional_terms), len(case.optional_terms))
    markdown_score = _markdown_score(answer)
    grounding_score = _grounding_score(answer, forbidden_matches)
    ontology_trace_score, missing_ontology_trace_items = _ontology_trace_score(
        answer,
        matched_optional_terms,
    )
    score = (
        heading_score * 0.22
        + required_term_score * 0.30
        + optional_term_score * 0.12
        + markdown_score * 0.10
        + grounding_score * 0.14
        + ontology_trace_score * 0.12
    )
    passed = (
        not missing_headings
        and not missing_required_terms
        and ontology_trace_score >= 0.60
        and not forbidden_matches
        and score >= case.min_score
    )

    return GoldenAnswerResult(
        case_id=case.case_id,
        topic=case.topic,
        query=case.query,
        passed=passed,
        score=score,
        heading_score=heading_score,
        required_term_score=required_term_score,
        optional_term_score=optional_term_score,
        markdown_score=markdown_score,
        grounding_score=grounding_score,
        ontology_trace_score=ontology_trace_score,
        missing_headings=missing_headings,
        missing_required_terms=missing_required_terms,
        missing_ontology_trace_items=missing_ontology_trace_items,
        matched_optional_terms=matched_optional_terms,
        forbidden_matches=forbidden_matches,
        answer_chars=len(answer),
        answer_excerpt=_excerpt(answer),
        answer_path=answer_path,
    )


def build_answer_report(
    results: list[GoldenAnswerResult], *, suite: str, fail_under: float
) -> GoldenAnswerReport:
    score = sum(result.score for result in results) / len(results) if results else 0.0
    passed = bool(results) and score >= fail_under and all(result.passed for result in results)
    return GoldenAnswerReport(
        suite=suite,
        fail_under=fail_under,
        passed=passed,
        score=score,
        cases=results,
    )


def write_answer_report(report: GoldenAnswerReport, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    else:
        path.write_text(report.to_markdown(), encoding="utf-8")


def answer_path_for(case: GoldenAnswerCase, answers_dir: str | Path) -> Path:
    return Path(answers_dir) / f"{case.case_id}.md"


def generation_query_for(case: GoldenAnswerCase) -> str:
    """Return a stricter generation query for golden-answer production."""
    headings = "\n".join(f"## {heading}" for heading in case.required_headings)
    required_terms = ", ".join(case.required_terms)
    optional_terms = ", ".join(case.optional_terms)
    return (
        f"{case.query}\n\n"
        "Return Markdown only. Use exactly these top-level section headings, in this order:\n"
        f"{headings}\n\n"
        "Each section must be substantive and source-grounded. Include source citations "
        "using the retrieved section titles. Include implementation and conformance-test "
        "guidance for a senior backend developer. Do not invent fields or requirements.\n\n"
        "When evidence supports it, include an ontology-aware implementation trace that "
        "connects specification behavior, Device Model component/variable evidence, and "
        "JSON schema payload validation. If one side of that trace is missing, disclose "
        "the missing link in Evidence gaps.\n\n"
        f"Required answer terms: {required_terms}.\n"
        f"Useful optional answer terms when supported by evidence: {optional_terms}."
    )


def _case(
    quality_case: QualityCase,
    *,
    required_terms: tuple[str, ...],
    optional_terms: tuple[str, ...],
) -> GoldenAnswerCase:
    return GoldenAnswerCase(
        case_id=f"{quality_case.case_id}-ANSWER",
        quality_case_id=quality_case.case_id,
        topic=quality_case.topic,
        query=quality_case.query,
        required_headings=(
            "Purpose",
            "Normative behavior",
            "Implementation guidance",
            "Conformance-test focus",
            "Evidence gaps",
        ),
        required_terms=required_terms,
        optional_terms=optional_terms,
    )


def _markdown_headings(answer: str) -> list[str]:
    return [
        _normalize_heading(match.group(1))
        for match in re.finditer(r"^#{1,6}\s+(.+)$", answer, flags=re.MULTILINE)
    ]


_HEADING_ALIASES = {
    "purpose": ("purpose", "purpose and scope"),
    "normative behavior": (
        "normative behavior",
        "normative behaviour",
        "normative foundations",
        "normative requirements",
    ),
    "implementation guidance": (
        "implementation guidance",
        "backend implementation logic",
        "implementation logic",
        "implementation impact",
    ),
    "conformance-test focus": (
        "conformance-test focus",
        "conformance test focus",
        "conformance focus",
        "test focus",
        "testing focus",
        "smoke tests",
    ),
    "evidence gaps": (
        "evidence gaps",
        "evidence gap",
        "gaps",
        "limitations",
        "missing information",
    ),
}


def _has_heading(required_heading: str, headings: list[str]) -> bool:
    aliases = _HEADING_ALIASES.get(required_heading.lower(), (required_heading.lower(),))
    return any(any(alias in heading for alias in aliases) for heading in headings)


def _normalize_heading(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"^\d+(?:\.\d+)*\.\s*", "", value)
    value = value.replace("behaviour", "behavior")
    return value


def _markdown_score(answer: str) -> float:
    score = 0.0
    if _markdown_headings(answer):
        score += 0.45
    if re.search(r"^\s*[-*]\s+", answer, flags=re.MULTILINE):
        score += 0.25
    if _has_citation(answer):
        score += 0.20
    if not answer.strip().startswith("```") and not answer.strip().endswith("```"):
        score += 0.10
    return min(score, 1.0)


def _grounding_score(answer: str, forbidden_matches: list[str]) -> float:
    if forbidden_matches:
        return 0.0
    score = 0.0
    if "evidence" in answer.lower():
        score += 0.30
    if _has_citation(answer):
        score += 0.45
    if "missing" in answer.lower() or "gap" in answer.lower():
        score += 0.25
    return min(score, 1.0)


def _ontology_trace_score(
    answer: str,
    matched_optional_terms: list[str],
) -> tuple[float, list[str]]:
    answer_lower = answer.lower()
    implementation = _section_text(answer, "implementation guidance")
    evidence_gaps = _section_text(answer, "evidence gaps")
    score = 0.0
    missing: list[str] = []

    layer_hits = {
        "spec": _has_any(
            answer_lower,
            ("spec", "section", "part 2", ".fr.", "requirement", "normative"),
        ),
        "Device Model": _has_any(answer_lower, ("device model", "ctrlr", "component")),
        "schema": _has_any(answer_lower, ("schema", "json", ".req", "request")),
    }
    score += _ratio(sum(1 for matched in layer_hits.values() if matched), len(layer_hits)) * 0.35
    missing.extend(layer for layer, matched in layer_hits.items() if not matched)

    implementation_layers = sum(
        1
        for marker in (
            ("spec", "section", "requirement", "normative"),
            ("device model", "ctrlr", "component", "variable"),
            ("schema", "json", ".req", "request", "validation"),
        )
        if _has_any(implementation, marker)
    )
    if implementation_layers >= 2:
        score += 0.25
    else:
        missing.append("implementation trace")

    if len(matched_optional_terms) >= 2:
        score += 0.20
    else:
        missing.append("concrete protocol entities")

    if _has_missing_link_disclosure(evidence_gaps or answer_lower):
        score += 0.20
    else:
        missing.append("missing-link disclosure")

    return min(score, 1.0), missing


def _section_text(answer: str, heading: str) -> str:
    pattern = re.compile(r"^#{1,6}\s+(.+)$", flags=re.MULTILINE)
    matches = list(pattern.finditer(answer))
    for index, match in enumerate(matches):
        if _has_heading(heading, [_normalize_heading(match.group(1))]):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(answer)
            return answer[start:end].lower()
    return ""


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _has_missing_link_disclosure(text: str) -> bool:
    return _has_any(
        text,
        (
            "missing",
            "gap",
            "not supplied",
            "not provided",
            "not included",
            "lacks",
            "lack",
            "cannot be",
            "could not be",
            "not enumerate",
            "not detailed",
            "no important gap",
        ),
    )


def _has_citation(answer: str) -> bool:
    return bool(re.search(r"\[[^\]]+\](?:\([^)]+\))?", answer))


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return max(0.0, min(1.0, numerator / denominator))


def _excerpt(answer: str, max_chars: int = 900) -> str:
    normalized = answer.strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars].rstrip() + "\n..."
