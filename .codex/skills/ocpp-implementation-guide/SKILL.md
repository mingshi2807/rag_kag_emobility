---
name: ocpp-implementation-guide
description: Generate senior software developer implementation guides from OCPP 2.1 Ed2 RAG/KAG evidence. Use for how-to, know-how, backend handlers, persistence, validation, sequencing, DER, BootNotification, GetVariables, Device Model, and schema-guided implementation guidance.
---

# OCPP Implementation Guide

Use this skill to convert retrieved OCPP evidence into an implementation-ready
Markdown guide for a senior backend developer.

## Required Evidence

Prefer fusion evidence unless the user asks for one layer only:

- Part 2 spec behavior and requirements.
- Device Model components/variables when the feature uses configuration,
  monitoring, reporting, or component state.
- JSON schema request/response constraints for handler validation.

## Guide Template

Return Markdown only.

```markdown
# <Feature> Implementation Guide

## Purpose

## Normative Behavior

## Data Model and JSON Schema

## Device Model Mapping

## Backend Implementation Sequence

## Error Handling and State Rules

## Smoke Tests

## Conformance-Test Focus

## Evidence Gaps
```

Omit sections only when the retrieved context cannot support them. Mark
inferences explicitly as evidence-grounded synthesis.

## Implementation Rules

- Do not invent fields, enum values, state transitions, or test assertions.
- Distinguish Charging Station behavior from CSMS behavior.
- Include message names, request/response fields, cardinality, and enum values when available.
- If schema evidence is missing, say which schema should be retrieved next.
- If Device Model evidence is irrelevant, say why instead of forcing it.

## Useful Fusion Query Pattern

```bash
HF_HOME=./models .venv/bin/rag query "For <feature> implementation in OCPP 2.1 Ed2, combine Part 2 normative behavior, Device Model components/variables, and JSON schema validation. Provide a senior backend developer guide." --top-k 12
```

## Stop Condition

Stop when the guide is actionable for implementation, cites retrieved sources,
and lists evidence gaps instead of guessing.
