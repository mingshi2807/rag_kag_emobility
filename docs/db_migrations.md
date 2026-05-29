# Database Migrations

This project uses explicit SQL migrations for the PostgreSQL and pgvector schema.
Migration files live in `src/rag_ocpp/storage/migrations/` and are tracked by the
database table `schema_migrations`.

## Commands

Start PostgreSQL:

```bash
docker compose up -d
```

Check migration state:

```bash
.venv/bin/rag migrate-status
```

Preview pending migrations:

```bash
.venv/bin/rag migrate --dry-run
```

Apply pending migrations:

```bash
.venv/bin/rag migrate
```

Adopt an existing database that was created from `schema.sql` before migrations
existed:

```bash
.venv/bin/rag migrate --baseline
.venv/bin/rag migrate
.venv/bin/rag migrate-status
```

Use `--baseline` only when the database already matches the current schema. The
command validates key baseline tables before recording the initial schema
migration, but it does not rebuild or diff the database. Running `rag migrate`
afterwards applies any follow-up repair migrations, such as creating
`audit_events` on older local databases and adding the source-aware ontology
catalog.

## Rules

- Do not edit a migration after it has been applied to any shared database.
- Create a new numbered SQL file for every schema change.
- Keep `src/rag_ocpp/storage/schema.sql` as the current bootstrap snapshot until
  Docker bootstrap is fully replaced by migration-driven setup.
- Any embedding dimension change requires a migration, re-embedding plan, and
  documentation update in the same branch.
- Docker Compose still mounts `schema.sql` for local first-run compatibility.
  The controlled enterprise setup path is `rag migrate`.

## Fresh Database Flow

For a controlled empty database:

```bash
docker compose up -d
.venv/bin/rag migrate-status
.venv/bin/rag migrate --dry-run
.venv/bin/rag migrate
```

Expected result after `rag migrate`:

```text
Applied 3 migration(s).
  + 001 initial_schema
  + 002 ensure_audit_events
  + 003 ontology_catalog
```

Expected result after a second `rag migrate`:

```text
Applied 0 migration(s).
Skipped 3 already-applied migration(s).
```

## Legacy Local Database Flow

If the database was initialized by Docker with `schema.sql` before migration
tracking existed, do not replay `001_initial_schema.sql`. Baseline it:

```bash
.venv/bin/rag migrate --baseline
.venv/bin/rag migrate
.venv/bin/rag migrate-status
```

Expected status:

```text
001 initial_schema: applied at <timestamp>
002 ensure_audit_events: applied at <timestamp>
003 ontology_catalog: applied at <timestamp>
```

## Ontology Catalog

Migration `003_ontology_catalog.sql` creates the lightweight ontology catalog
used to validate and explain graph relationship semantics. Load or refresh the
default OCPP 2.1 Ed2 ontology seed after migrations:

```bash
.venv/bin/rag ontology-load --dry-run
.venv/bin/rag ontology-load
.venv/bin/rag ontology-status
```

The corpus indexer also auto-loads the default seed when the ontology tables
exist but no active ontology version has been loaded yet.
