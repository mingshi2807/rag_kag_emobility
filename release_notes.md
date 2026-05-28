# v0.2.0 - Enterprise Control Plane: Privacy, Audit, and DB Migrations

## Release Title

Enterprise Control Plane for OCPP 2.1 Ed2 Knowledge Backend

## Release Description

`v0.2.0` moves the OCPP 2.1 Ed2 RAG/KAG backend beyond evaluation baselines into enterprise-control foundations. This release adds configurable private-knowledge protections, privacy-preserving audit events, repaired storage/retrieval integration tests, and explicit PostgreSQL migrations with a migration ledger.

The release keeps the existing R/Q/K retrieval and golden-answer benchmarks from `v0.1.2`, then strengthens the operational substrate needed for private enterprise knowledge: safer logging, auditable access events, reproducible schema setup, and documented legacy database adoption.

## Highlights

- Added configurable redacted logging for private source text, prompts, answers, secrets, and long payloads.
- Added privacy-preserving audit events for:
  - query
  - retrieval
  - generation
  - corpus ingestion/indexing
  - MCP access
- Added `audit_events` storage and audit helpers that store hashes, lengths, IDs, counts, status, latency, and redacted metadata instead of raw private text.
- Repaired retrieval/storage integration tests with deterministic document IDs and 1024-dimensional embeddings.
- Added explicit SQL migration runner with `schema_migrations` ledger.
- Added migration CLI commands:
  - `rag migrate-status`
  - `rag migrate --dry-run`
  - `rag migrate`
  - `rag migrate --baseline`
- Added migration `001_initial_schema.sql` for fresh databases.
- Added migration `002_ensure_audit_events.sql` for legacy databases missing `audit_events`.
- Added `docs/db_migrations.md` with fresh DB setup and legacy baseline adoption flows.
- Updated `docs/HANDOFF.md` and `docs/AUDIT_REPORT.md` to reflect current enterprise-control status.

## Operator Guidance

For a fresh empty database:

```bash
docker compose up -d
.venv/bin/rag migrate --dry-run
.venv/bin/rag migrate
.venv/bin/rag migrate-status
```

For an existing local database created before migrations existed:

```bash
.venv/bin/rag migrate --baseline
.venv/bin/rag migrate --dry-run
.venv/bin/rag migrate
.venv/bin/rag migrate-status
```

Expected final migration state:

```text
001 initial_schema: applied at <timestamp>
002 ensure_audit_events: applied at <timestamp>
```

## Validation

Validated locally with:

- `.venv/bin/pytest tests/test_storage/test_migrations.py -q`
  - `2 passed`
- `.venv/bin/pytest tests/test_storage/test_migrations.py tests/test_storage/test_audit.py tests/test_privacy.py -q`
  - `10 passed`
- `.venv/bin/ruff check src/rag_ocpp/storage/migrations.py src/rag_ocpp/cli/db.py src/rag_ocpp/cli/main.py tests/test_storage/test_migrations.py`
- `.venv/bin/python -m compileall -q src/rag_ocpp`
- `.venv/bin/rag migrate --help`
- `git diff --check`

## Known Gaps

- Source-level ACLs, tenant isolation, retention/deletion policy, and secret-handling policy are still not complete.
- API, CLI, and MCP generated-answer behavior still need full alignment with the golden-answer Markdown and citation contract.
- Eval coverage is still concentrated on Section R DER, Section Q V2X, and Section K smart charging.
- CI wiring for migration tests, retrieval quality, and golden-answer gates remains pending.
- Migration rollback, backup, restore, and re-embedding operational runbooks still need to be formalized.
- `mypy` could not be used in the local Python environment because the interpreter build is missing `_sqlite3`, which causes mypy 2.1.0 to fail before checking project code.

## Recommended Tag

```text
v0.2.0
```

## Recommended Release Commit Message

```text
release: publish v0.2.0 enterprise controls
```

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
