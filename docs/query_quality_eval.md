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

The command exits with status `2` when the suite fails. This is intended for CI and regression gating.
