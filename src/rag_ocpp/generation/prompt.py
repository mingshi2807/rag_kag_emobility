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
- For protocol message purpose, implementation guideline, or conformance-test
  questions, answer in a specification-review style with these sections when
  supported by context: Purpose, Normative behavior, Implementation guidance,
  Conformance-test focus, and Evidence gaps.
- If the question spans multiple parts of the specification,
  organize the answer accordingly."""

QUERY_TEMPLATE_STR = """## Context from OCPP 2.1 Knowledge Base

{% for chunk in chunks %}
### [{{ chunk.section_title or 'Untitled Section' }}]
Source: {{ chunk.document_title or 'Unknown Document' }}{% if chunk.page_start %}, page {{ chunk.page_start }}{% endif %}{% if chunk.evidence_layer %}; Evidence layer: {{ chunk.evidence_layer }}{% endif %}{% if chunk.source_type %}; Source type: {{ chunk.source_type }}{% endif %}

{{ chunk.content }}

{% endfor %}
## Question
{{ query }}

## Instructions
Return Markdown only.
Answer with enough depth for implementation and conformance review; do not stop at a one-sentence summary.
Cite sources in format: [Section Title](Document, page N) when a page is available,
or [Section Title](Document) when the source has no page number.
Include relevant entity names (commands, datatypes, variables, enums)."""

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
