"""Prompt templates — Jinja2 system prompt and query template for OCPP RAG generation."""

from __future__ import annotations

import jinja2

SYSTEM_PROMPT = """You are an OCPP 2.1 protocol expert. Answer questions using ONLY
the provided context from the OCPP specification, Device Model tables, JSON schemas,
and test suites.
If the context does not contain sufficient information, say so clearly
and explain what is missing.

Guidelines:
- Return Markdown only. Use headings, bullets, and tables when useful. Do not
  wrap the whole answer in a code block.
- Cite the specific section title and page number for each claim.
- Include relevant command names, data types, and message flow details.
- Be precise about required fields, cardinality (required/optional),
  and data type constraints.
- If the exact definition is absent but the context gives enough operational
  evidence, provide an "Evidence-grounded synthesis" and explicitly say it is
  inferred from the provided context, not a quoted formal definition.
- When ontology metadata or semantic links are present, use them to connect
  specification behavior, Device Model components/variables, and JSON schema
  payloads. Keep this source-aware trace explicit and distinguish it from
  implementation synthesis.
- For protocol message purpose, implementation guideline, or conformance-test
  questions, answer in a specification-review style with these sections when
  supported by context: Purpose, Normative behavior, Implementation guidance,
  Conformance-test focus, and Evidence gaps.
- If the question spans multiple parts of the specification,
  organize the answer accordingly."""

QUERY_TEMPLATE_STR = """## Context from OCPP 2.1 Knowledge Base

{% for chunk in chunks %}
### [{{ chunk.section_title or 'Untitled Section' }}]
Source: {{ chunk.document_title or 'Unknown Document' }}
{% if chunk.page_start %}, page {{ chunk.page_start }}{% endif %}
{% if chunk.evidence_layer %}; Evidence layer: {{ chunk.evidence_layer }}{% endif %}
{% if chunk.source_type %}; Source type: {{ chunk.source_type }}{% endif %}
{% if chunk.graph_semantic_links %}
Ontology links: {{ chunk.graph_semantic_links }}
{% endif %}
{% if chunk.graph_ontology_relations %}
Ontology relations: {{ chunk.graph_ontology_relations|join(', ') }}
{% endif %}
{% if chunk.graph_ontology_rules %}
Ontology mapping rules: {{ chunk.graph_ontology_rules|join(', ') }}
{% endif %}
{% if chunk.graph_ontology_versions %}
Ontology versions: {{ chunk.graph_ontology_versions|join(', ') }}
{% endif %}

{% if chunk.semantic_links %}
Semantic links:
{% for link in chunk.semantic_links %}
- {{ link.entity }} --{{ link.relation }}--> {{ link.related_entity }}
  {% if link.mapping_rule %}rule: {{ link.mapping_rule }}{% endif %}
  {% if link.ontology_version %}ontology: {{ link.ontology_version }}{% endif %}
{% endfor %}
{% endif %}

{{ chunk.content }}

{% endfor %}
## Question
{{ query }}

## Instructions
Return Markdown only.
Answer with enough depth for implementation and conformance review; do not stop
at a one-sentence summary.
Cite sources in format: [Section Title](Document, page N) when a page is available,
or [Section Title](Document) when the source has no page number.
Include relevant entity names (commands, datatypes, variables, enums).
When evidence spans multiple layers, include a source-aware implementation trace:
spec behavior -> Device Model component/variable -> JSON schema payload.
If any trace link is missing from the retrieved context, state the missing link."""

QUERY_TEMPLATE = jinja2.Template(QUERY_TEMPLATE_STR, trim_blocks=True, lstrip_blocks=True)

QUERY_TEMPLATE_SHORT_STR = """## Context

{% for chunk in chunks %}
[{{ chunk.section_title or 'Section' }}] {{ chunk.content }}
{% endfor %}

## Question
{{ query }}

Return Markdown only. Answer concisely with source citations."""

QUERY_TEMPLATE_SHORT = jinja2.Template(
    QUERY_TEMPLATE_SHORT_STR, trim_blocks=True, lstrip_blocks=True,
)

GOLDEN_ANSWER_SYSTEM_PROMPT = """You are an OCPP 2.1 Ed2 implementation reviewer.
Generate a source-grounded Markdown answer using ONLY the provided context.

Hard output contract:
- Return Markdown only. Do not wrap the answer in a code block.
- Use exactly the requested H2 headings, in the requested order.
- Do not number, rename, skip, or add top-level H2 headings.
- If evidence is incomplete, keep the heading and state the gap there.
- Cite retrieved section titles for concrete protocol claims.
- When ontology metadata or semantic links are present, use them as traceability
  hints. Do not treat ontology links as new normative requirements.
- Do not invent fields, requirements, message names, or Device Model variables."""

GOLDEN_ANSWER_TEMPLATE_STR = """## Context from OCPP 2.1 Knowledge Base

{% for chunk in chunks %}
### [{{ chunk.section_title or 'Untitled Section' }}]
Source: {{ chunk.document_title or 'Unknown Document' }}
{% if chunk.page_start %}, page {{ chunk.page_start }}{% endif %}
{% if chunk.evidence_layer %}; Evidence layer: {{ chunk.evidence_layer }}{% endif %}
{% if chunk.source_type %}; Source type: {{ chunk.source_type }}{% endif %}
{% if chunk.graph_semantic_links %}
Ontology links: {{ chunk.graph_semantic_links }}
{% endif %}
{% if chunk.graph_ontology_relations %}
Ontology relations: {{ chunk.graph_ontology_relations|join(', ') }}
{% endif %}
{% if chunk.graph_ontology_rules %}
Ontology mapping rules: {{ chunk.graph_ontology_rules|join(', ') }}
{% endif %}
{% if chunk.graph_ontology_versions %}
Ontology versions: {{ chunk.graph_ontology_versions|join(', ') }}
{% endif %}
{% if chunk.semantic_links %}
Semantic links:
{% for link in chunk.semantic_links %}
- {{ link.entity }} --{{ link.relation }}--> {{ link.related_entity }}
  {% if link.mapping_rule %}rule: {{ link.mapping_rule }}{% endif %}
  {% if link.ontology_version %}ontology: {{ link.ontology_version }}{% endif %}
{% endfor %}
{% endif %}

{{ chunk.content }}

{% endfor %}
## Question
{{ query }}

## Required Markdown Answer Template
{% for heading in headings %}
## {{ heading }}
{% if heading == "Purpose" %}
Explain the protocol purpose and implementation boundary in 2-4 bullets.
{% elif heading == "Normative behavior" %}
Summarize source-grounded required behavior, message/schema constraints, and
Device Model dependencies.
{% elif heading == "Implementation guidance" %}
Give senior backend guidance for validation, persistence, state transitions,
error handling, and integration sequencing.
When supported by context, include an ontology-aware trace bullet in this section
using the shape: spec behavior -> Device Model component/variable -> JSON schema
payload. If one side of that trace is missing, state the missing link.
{% elif heading == "Conformance-test focus" %}
List concrete positive and negative tests, including schema validation and
unsupported-capability paths.
{% elif heading == "Evidence gaps" %}
List missing or weak evidence. If no important gap is visible, state that no
important gap was found in the retrieved evidence.
{% endif %}

{% endfor %}
Required terms to cover when supported by evidence: {{ required_terms }}.
Useful optional terms when supported by evidence: {{ optional_terms }}.

Final check before responding:
- The only H2 headings are exactly the required headings above.
- Every required heading has substantive content.
- The answer contains source citations such as [Section Title](Document, page N)
  or [Section Title](Document).
- If ontology metadata or semantic links are present, the Implementation
  guidance section uses them for traceability without adding unsupported
  normative claims.
"""

GOLDEN_ANSWER_TEMPLATE = jinja2.Template(
    GOLDEN_ANSWER_TEMPLATE_STR, trim_blocks=True, lstrip_blocks=True,
)


def render_query_prompt(
    query: str, chunks: list[dict], *, short: bool = False,
) -> tuple[str, str]:
    """Render (system_prompt, user_prompt) from context chunks.

    Args:
        query:  User query.
        chunks: List of dicts with content, section_title, document_title, page_start.
        short:  Use shorter template for streaming.
    """
    template = QUERY_TEMPLATE_SHORT if short else QUERY_TEMPLATE
    return SYSTEM_PROMPT, template.render(query=query, chunks=chunks)


def render_generation_messages(
    query: str, chunks: list[dict], *, short: bool = False,
) -> list[dict[str, str]]:
    """Render DeepSeek Chat API message list."""
    system, user = render_query_prompt(query, chunks, short=short)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def render_golden_answer_messages(
    query: str,
    chunks: list[dict],
    *,
    required_headings: tuple[str, ...],
    required_terms: tuple[str, ...],
    optional_terms: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    """Render strict generation messages for golden-answer evaluation."""
    user = GOLDEN_ANSWER_TEMPLATE.render(
        query=query,
        chunks=chunks,
        headings=required_headings,
        required_terms=", ".join(required_terms),
        optional_terms=", ".join(optional_terms) or "none",
    )
    return [
        {"role": "system", "content": GOLDEN_ANSWER_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
