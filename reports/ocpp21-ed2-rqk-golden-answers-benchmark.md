# OCPP Golden Answer Benchmark: DeepSeek vs Codex-only

- Date: 2026-05-27
- Scope: OCPP 2.1 Ed2 R/Q/K fusion implementation guidance
- DeepSeek answer directory: `reports/golden_answers/`
- Codex-only answer directory: `reports/golden_answers_codex-only/`
- DeepSeek score report: `reports/ocpp21-ed2-rqk-golden-answers.md`
- Codex-only score report: `reports/ocpp21-ed2-rqk-golden-answers-codex-only.md`

## What The Golden-Answer Steps Mean

1. Retrieval quality gate: `rag eval-quality`

This checks whether the RAG backend retrieves the right evidence layers and terms:
specification, Device Model, and JSON schema. It does not judge the final generated
implementation answer.

2. Golden answer generation and scoring gate: `rag eval-answers`

This checks whether a Markdown implementation answer has the required enterprise
shape: required sections, required terms, optional implementation terms, citation
shape, and no refusal/missing-context failure. It can run in two modes:

- Generation mode: calls the configured LLM, currently DeepSeek, then scores the answer.
- Offline scoring mode: uses `--from-answers-dir`, reads existing Markdown answers,
  and scores them without calling any LLM.

The Codex-only benchmark uses offline scoring. Codex authored the Markdown files in
the repo, and `rag eval-answers --from-answers-dir` only scored those saved files.
It did not call DeepSeek.

## Reproduction Commands

DeepSeek generated-answer baseline:

```bash
HF_HOME=./models .venv/bin/rag eval-answers \
  --top-k 12 \
  --fail-under 0.80 \
  --answers-dir reports/golden_answers \
  --output reports/ocpp21-ed2-rqk-golden-answers.md
```

Codex-only offline benchmark:

```bash
HF_HOME=./models .venv/bin/rag eval-answers \
  --from-answers-dir \
  --answers-dir reports/golden_answers_codex-only \
  --output reports/ocpp21-ed2-rqk-golden-answers-codex-only.md
```

## Automated Score Comparison

| Topic | DeepSeek score | Codex-only score | DeepSeek chars | Codex-only chars | DeepSeek citations | Codex-only citations |
|---|---:|---:|---:|---:|---:|---:|
| Section R DER control | 1.000 | 1.000 | 7,761 | 5,260 | 10 | 3 |
| Section Q V2X energy services | 1.000 | 1.000 | 8,710 | 4,509 | 19 | 3 |
| Section K smart charging | 1.000 | 1.000 | 11,629 | 4,564 | 21 | 3 |
| **Total / average** | **1.000** | **1.000** | **28,100** | **14,333** | **50** | **9** |

## Qualitative Comparison

| Dimension | DeepSeek generated answers | Codex-only answers |
|---|---|---|
| Generation path | Generated through `DeepSeekClient` from retrieved chunks. | Authored by Codex in repo files, then scored offline. |
| LLM call during benchmark | Yes for generation mode. | No; `--from-answers-dir` only reads Markdown files. |
| Detail level | Much deeper and more verbose. | Shorter and more implementation-checklist oriented. |
| Citation density | Higher, with many section/page/schema references. | Lower, with broad source references. |
| Structure | Passes required H2 structure; Smart Charging includes many H3 subsections. | Passes required H2 structure; no H3 subsections. |
| Best use | Source-rich implementation guidance and traceable review packs. | Fast model-to-model benchmark baseline and concise guidance. |
| Main risk | More detail can include more claims that need expert review. | Lower citation density means weaker audit traceability. |

## Interpretation

Both versions pass the current automated golden-answer gate. That means both satisfy
the current structural and term-coverage contract, not that they are equally strong
as enterprise knowledge artifacts.

DeepSeek is stronger for traceability because it produced longer answers with more
citations and more field-level protocol detail. Codex-only is useful as a benchmark
control because it proves the evaluator can score non-DeepSeek answers and compare
answer sets without calling the DeepSeek API.

## Recommendation

Keep both baselines:

- Use DeepSeek answers as the current source-rich generated-answer baseline.
- Use Codex-only answers as the provider-neutral benchmark/control baseline.
- Add a next scorer layer for expert-grade quality: exact schema paths, exact
  requirement IDs, citation precision, unsupported-claim detection, and human
  expert approval status.

The current automated score is intentionally necessary but not sufficient. For
enterprise granted knowledge, the next gate should distinguish shallow passable
answers from deeply source-supported implementation guidance.
