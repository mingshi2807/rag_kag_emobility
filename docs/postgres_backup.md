# PostgreSQL Backup And Restore

This project stores private OCPP corpus records, chunks, embeddings, graph
links, audit events, and API/CLI/MCP state in PostgreSQL/pgvector. Backups are
private artifacts and must not be committed.

## Create A Versioned Dump

Start PostgreSQL if needed:

```bash
docker compose up -d
```

Create a timestamped custom-format dump:

```bash
scripts/backup_postgres.sh --tag before-v0.3.0
```

Default output directory:

```text
backups/postgres/
```

The script creates three files:

- `<database>-<timestamp>-<tag>.dump`: custom `pg_dump` archive.
- `<database>-<timestamp>-<tag>.dump.sha256`: checksum.
- `<database>-<timestamp>-<tag>.dump.manifest.json`: metadata for traceability.

`backups/` is ignored by git because dumps contain private enterprise
knowledge.

## Plain SQL Dump

Use this only when a readable SQL dump is needed:

```bash
scripts/backup_postgres.sh --plain --tag readable-sql
```

The custom `.dump` format is preferred for normal backup and restore because it
is smaller and works with `pg_restore`.

## Verify A Dump

```bash
sha256sum -c backups/postgres/<file>.sha256
```

## Restore A Custom Dump

Restoring can destroy or overwrite data. Use a disposable database first unless
you explicitly intend to replace the current local database.

For a custom `.dump` file:

```bash
docker compose exec -T postgres pg_restore \
  -U rag_kag \
  -d rag_kag \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  < backups/postgres/<file>.dump
```

For a plain `.sql` file:

```bash
docker compose exec -T postgres psql \
  -U rag_kag \
  -d rag_kag \
  < backups/postgres/<file>.sql
```

## Operational Notes

- The script sources `.env` when present and falls back to the repository
  defaults: `PG_DATABASE=rag_kag`, `PG_USER=rag_kag`, and
  `PG_PASSWORD=rag_kag`.
- The script uses `docker compose exec -T postgres pg_dump`, so the host does
  not need a local `pg_dump` binary.
- The dump includes schema and data. It does not include Docker volume metadata
  or local model files under `models/`.
- Keep dumps encrypted or inside an approved private backup location when moved
  outside the workstation.
