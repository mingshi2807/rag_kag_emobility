# OCPP Query Quality Evaluation

This project includes a source-aware retrieval quality suite for OCPP 2.1 Edition 2 implementation topics.

The initial enterprise baseline focuses on:

- Section R: DER control
- Section Q: V2X energy services
- Section K: smart charging

Each topic has four case modes:

- `spec`: Part 2 specification evidence
- `dm`: Device Model component and variable evidence
- `schema`: JSON schema evidence
- `fusion`: combined spec, Device Model, and schema evidence

## List Cases

```bash
HF_HOME=./models .venv/bin/rag eval-quality --list-cases
```

## Run Full Suite

```bash
HF_HOME=./models .venv/bin/rag eval-quality --top-k 12 --fail-under 0.80
```

## Run A Focused Topic

```bash
HF_HOME=./models .venv/bin/rag eval-quality --topic DER --top-k 12
HF_HOME=./models .venv/bin/rag eval-quality --topic V2X --top-k 12
HF_HOME=./models .venv/bin/rag eval-quality --topic smart --top-k 12
```

## Run One Evidence Mode

```bash
HF_HOME=./models .venv/bin/rag eval-quality --mode spec --top-k 10
HF_HOME=./models .venv/bin/rag eval-quality --mode dm --top-k 10
HF_HOME=./models .venv/bin/rag eval-quality --mode schema --top-k 10
HF_HOME=./models .venv/bin/rag eval-quality --mode fusion --top-k 12
```

## Save Reports

Markdown:

```bash
HF_HOME=./models .venv/bin/rag eval-quality \
  --top-k 12 \
  --fail-under 0.80 \
  --output reports/ocpp21-ed2-rqk-quality.md
```

JSON:

```bash
HF_HOME=./models .venv/bin/rag eval-quality \
  --top-k 12 \
  --fail-under 0.80 \
  --json \
  --output reports/ocpp21-ed2-rqk-quality.json
```

## Scoring

Each case checks:

- Required evidence layers are present in top-k.
- Required domain terms are present in retrieved evidence.
- Optional terms improve the score but do not define the core evidence contract.
- Top evidence includes chunk IDs, section titles, source type, evidence layer, and source path metadata.
- Ontology metrics summarize graph candidate chunks, semantic-link coverage,
  traversal depth, ontology relation types, and mapping rules.

The command exits with status `2` when the suite fails. This is intended for CI and regression gating.

## Ontology Metrics

`eval-quality` reports include candidate-level and final-top-k ontology metrics:

- `Graph candidate chunks`: graph retrieval candidates produced before final
  fusion/reranking.
- `Graph candidate chunks with semantic links`: graph candidates backed by
  ontology-provenance links.
- `Graph candidate semantic links`: total semantic links across graph
  candidates.
- `Final graph chunks`: graph chunks that survived into final top-k evidence.
- `Max traversal depth`: deepest ontology-aware traversal observed.
- `Ontology relation types` and `Ontology mapping rules`: governed graph
  semantics used by graph candidates.

Candidate metrics can be non-zero while final graph chunks are zero. That means
ontology-aware graph retrieval contributed candidates, but vector/keyword/rerank
evidence won the final top-k. When final graph chunks are present, generation
prompts receive ontology metadata so answers can build source-aware traces.

## Golden Answer Evaluation

Retrieval quality does not prove generated implementation guidance quality. Use `eval-answers` to generate and score Markdown answers for the fusion implementation cases.

List answer cases:

```bash
HF_HOME=./models .venv/bin/rag eval-answers --list-cases
```

Generate answers, save them, and write a report:

```bash
HF_HOME=./models .venv/bin/rag eval-answers \
  --top-k 12 \
  --fail-under 0.80 \
  --answers-dir reports/golden_answers \
  --output reports/ocpp21-ed2-rqk-golden-answers.md
```

Score existing generated answers without calling the LLM:

```bash
HF_HOME=./models .venv/bin/rag eval-answers \
  --from-answers-dir \
  --answers-dir reports/golden_answers \
  --output reports/ocpp21-ed2-rqk-golden-answers.md
```

Score the Codex-authored benchmark answers without calling DeepSeek:

```bash
HF_HOME=./models .venv/bin/rag eval-answers \
  --from-answers-dir \
  --answers-dir reports/golden_answers_codex-only \
  --output reports/ocpp21-ed2-rqk-golden-answers-codex-only.md
```

For Codex-assisted manual generation, Codex should first use MCP tools such as
`build_ocpp_implementation_brief` and `get_ocpp_evidence_pack`, then save the
Markdown answers in `reports/golden_answers_codex-only/`. The scoring command
above is offline-only and does not call DeepSeek or OpenAI.

The answer gate checks:

- Expected Markdown sections: Purpose, Normative behavior, Implementation guidance, Conformance-test focus, Evidence gaps.
- Required domain terms for DER, V2X, and Smart Charging implementation answers.
- Optional implementation-quality terms.
- Ontology trace quality: the answer must connect specification behavior,
  Device Model component/variable evidence, and JSON schema payload validation
  when the retrieved context supports that trace.
- Missing-link disclosure: if one side of the spec/DM/schema trace is absent,
  the Evidence gaps section should say what is missing instead of inventing it.
- Markdown structure and source-citation shape.
- Refusal or missing-context phrases that indicate the generated answer did not use the retrieved evidence.

Generation prompts now expose ontology link counts, relation types, mapping
rules, ontology versions, and semantic links when retrieval provides them. The
strict golden-answer prompt asks the Implementation guidance section to include
an ontology-aware trace when supported by context:

```text
spec behavior -> Device Model component/variable -> JSON schema payload
```

Ontology links are traceability hints, not standalone normative requirements.

Reports include an `Ontology trace score` per answer. Answers still need the
standard headings and required terms, but a low trace score now fails the case
even if the Markdown is otherwise well formed.
