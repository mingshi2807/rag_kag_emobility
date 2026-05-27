---
name: ocpp-expert-review
description: Expert-review OCPP 2.1 Ed2 RAG answers, backend implementation guidance, retrieval changes, or protocol claims for correctness, source support, implementation risk, and conformance-test relevance.
---

# OCPP Expert Review

Use this skill for strict senior review of OCPP 2.1 Ed2 answers or implementation
guidance. The review should protect protocol correctness and source traceability.

## Required Context

Prefer evidence from:

- Retrieved answer text and cited chunks supplied by the user.
- `data/pdf/`, `data/csv/`, and `data/json/` through the indexed corpus or local inspection.
- `docs/HANDOFF.md` and `docs/AUDIT_REPORT.md` for current known risks.

## Review Method

1. Identify the claim surface:
   - protocol purpose or behavior
   - message fields and cardinality
   - Device Model component/variable semantics
   - JSON schema validation
   - implementation or conformance-test advice
2. Separate direct evidence from inference.
3. Check that citations match the claim and the correct evidence layer.
4. Flag missing evidence, overreach, hallucinated requirements, or weak conformance claims.
5. Recommend concrete fixes to the answer, retrieval query, or implementation plan.

## Output Contract

Lead with findings.

```markdown
## Findings

| Severity | Finding | Evidence | Fix |
|---|---|---|---|

## Evidence vs Inference

## Implementation Risks

## Conformance-Test Implications

## Recommended Next Action
```

Severity levels:

- `Blocker`: likely protocol error or unsupported mandatory behavior.
- `High`: misleading implementation or validation guidance.
- `Medium`: weak citation, missing layer, or ambiguous inference.
- `Low`: wording or structure improvement.

## Stop Condition

Stop when each material claim is either supported, corrected, or marked as an
evidence gap.
