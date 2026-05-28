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
`audit_events` on older local databases.

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
Applied 2 migration(s).
  + 001 initial_schema
  + 002 ensure_audit_events
```

Expected result after a second `rag migrate`:

```text
Applied 0 migration(s).
Skipped 2 already-applied migration(s).
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
```
