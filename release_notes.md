# v0.1.2 - OCPP 2.1 Ed2 Evaluation and Golden Answer Benchmarks

## Release Title

OCPP 2.1 Ed2 Evaluation and Golden Answer Benchmarks

## Release Description

`v0.1.2` promotes the OCPP 2.1 Ed2 knowledge backend from an indexed RAG/KAG foundation to a measurable evaluation baseline. It adds repeatable retrieval quality gates for Section R DER control, Section Q V2X energy services, and Section K smart charging, then adds golden Markdown answer evaluation to verify generated implementation guidance quality beyond retrieval coverage.

This release also introduces provider-neutral answer benchmarking. DeepSeek-generated answers remain the source-rich baseline, while Codex-assisted answers are generated from MCP evidence tools and scored offline without DeepSeek or OpenAI API calls from the repo CLI.

## Highlights

- Added `rag eval-quality` source-aware retrieval evaluation for 12 R/Q/K cases:
  - `spec`
  - `dm`
  - `schema`
  - `fusion`
- Added `rag eval-answers` golden Markdown answer evaluation for fusion implementation guidance.
- Added strict generated-answer sections:
  - Purpose
  - Normative behavior
  - Implementation guidance
  - Conformance-test focus
  - Evidence gaps
- Added strict golden-answer prompting for generated Markdown answers.
- Added cached/offline answer scoring with `--from-answers-dir`.
- Added DeepSeek golden answer baseline reports.
- Added Codex-assisted MCP-evidence benchmark answers and offline scoring reports.
- Added DeepSeek vs Codex-only benchmark comparison.
- Documented the MCP-assisted manual benchmark workflow for Codex and other coding agents.

## Reports

- `reports/ocpp21-ed2-rqk-quality-baseline.md`
  - Retrieval suite: `12/12` passed
  - Score: `0.976`
- `reports/ocpp21-ed2-rqk-golden-answers.md`
  - DeepSeek generated-answer suite: `3/3` passed
  - Score: `1.000`
- `reports/ocpp21-ed2-rqk-golden-answers-codex-only.md`
  - Codex-assisted MCP-evidence answer suite: `3/3` passed
  - Score: `1.000`
- `reports/ocpp21-ed2-rqk-golden-answers-benchmark.md`
  - DeepSeek vs Codex-only comparison
  - DeepSeek citations: `50`
  - Codex-only citations: `28`

## Validation

Validated locally with:

- `HF_HOME=./models .venv/bin/rag eval-quality --top-k 12 --fail-under 0.80`
- `HF_HOME=./models .venv/bin/rag eval-answers --from-answers-dir --answers-dir reports/golden_answers --output reports/ocpp21-ed2-rqk-golden-answers.md`
- `HF_HOME=./models .venv/bin/rag eval-answers --from-answers-dir --answers-dir reports/golden_answers_codex-only --output reports/ocpp21-ed2-rqk-golden-answers-codex-only.md`
- Targeted eval tests for golden-answer scoring and query quality.
- Python compile checks for `src/rag_ocpp`.

## Known Gaps

- Automated scoring still checks structure, required terms, citation shape, and grounding signals; it does not yet prove full protocol correctness.
- Expert validation status is not yet modeled as a first-class approval field.
- Citation precision scoring needs to become stricter: exact requirement IDs, schema paths, and unsupported-claim detection.
- OpenAI/Codex generation is currently a Codex-assisted manual MCP workflow, not a repo CLI provider.
- CI wiring for retrieval and golden-answer gates is still pending.

## Recommended Tag

```text
v0.1.2
```

## Recommended Release Commit Message

```text
release: publish v0.1.2 evaluation baseline
```
