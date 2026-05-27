---
name: ocpp-query-eval
description: Evaluate OCPP 2.1 Ed2 RAG query quality across specification, Device Model, JSON schema, and fusion retrieval. Use for query-set design, before/after retrieval comparison, DER/BootNotification/GetVariables examples, and answer-quality scoring.
---

# OCPP Query Evaluation

Use this skill to evaluate retrieval and answer quality for OCPP 2.1 Ed2 queries.
The goal is to turn ad hoc prompts into repeatable eval evidence.

## Evaluation Lanes

- `spec`: Part 2 use cases, requirements, messages, datatypes, enumerations.
- `device_model`: components, variables, attributes, mutability, persistence.
- `schema`: JSON request/response fields, required fields, enums, nested types.
- `fusion`: combined senior-developer guidance across all evidence layers.

## Workflow

1. Classify each query by lane and expected evidence layers.
2. Run isolated retrieval first when diagnosing:

```bash
HF_HOME=./models .venv/bin/rag query "..." --top-k 8 --evidence-layer spec
HF_HOME=./models .venv/bin/rag query "..." --top-k 8 --evidence-layer device_model
HF_HOME=./models .venv/bin/rag query "..." --top-k 8 --evidence-layer schema
```

3. Run fusion retrieval without an evidence-layer filter:

```bash
HF_HOME=./models .venv/bin/rag query "..." --top-k 12
```

4. Record retrieved anchors, evidence-layer mix, citation quality, and answer defects.
5. Recommend query rewrites or retrieval-code fixes only when evidence shows the need.

## Scoring Rubric

Use `Pass`, `Watch`, or `Fail`.

- `Pass`: correct evidence layers, relevant anchors, cited answer, no unsupported claims.
- `Watch`: useful answer but missing one expected layer or has weak citation precision.
- `Fail`: wrong anchors, absent core evidence, hallucinated claim, or refusal despite sufficient context.

## Output Contract

```markdown
## Query Eval

| Query | Expected Layers | Retrieved Anchors | Verdict | Notes |
|---|---|---|---|---|

## Recommended Query Set

## Retrieval Defects

## Next Fixes
```

## Stop Condition

Stop when each query has a verdict, evidence-layer diagnosis, and a concrete
next action if quality is below `Pass`.
