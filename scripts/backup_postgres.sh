#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Backup the local PostgreSQL/pgvector database to a timestamped dump file.

Usage:
  scripts/backup_postgres.sh [--tag NAME] [--out-dir DIR] [--plain]

Defaults:
  --out-dir backups/postgres
  format    custom pg_dump format (.dump), suitable for pg_restore

Environment:
  Reads .env when present, then uses these values if exported:
    PG_DATABASE  default rag_kag
    PG_USER      default rag_kag
    PG_PASSWORD  default rag_kag

Examples:
  scripts/backup_postgres.sh
  scripts/backup_postgres.sh --tag before-v0.3.0
  scripts/backup_postgres.sh --plain --tag readable-sql

Restore examples:
  # Custom dump into an empty target database:
  docker compose exec -T postgres pg_restore \
    -U rag_kag -d rag_kag --clean --if-exists --no-owner --no-acl \
    < backups/postgres/<file>.dump

  # Plain SQL dump:
  docker compose exec -T postgres psql -U rag_kag -d rag_kag \
    < backups/postgres/<file>.sql
USAGE
}

tag=""
out_dir="backups/postgres"
format="custom"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)
      tag="${2:-}"
      if [[ -z "$tag" ]]; then
        echo "Missing value for --tag" >&2
        exit 2
      fi
      shift 2
      ;;
    --out-dir)
      out_dir="${2:-}"
      if [[ -z "$out_dir" ]]; then
        echo "Missing value for --out-dir" >&2
        exit 2
      fi
      shift 2
      ;;
    --plain)
      format="plain"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

pg_database="${PG_DATABASE:-rag_kag}"
pg_user="${PG_USER:-rag_kag}"
pg_password="${PG_PASSWORD:-rag_kag}"

mkdir -p "$out_dir"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
safe_tag=""
if [[ -n "$tag" ]]; then
  safe_tag="-$(printf '%s' "$tag" | tr -cs '[:alnum:]_.-' '-')"
fi

if [[ "$format" == "custom" ]]; then
  extension="dump"
  pg_dump_args=(-F c --no-owner --no-acl)
else
  extension="sql"
  pg_dump_args=(-F p --no-owner --no-acl)
fi

dump_file="${out_dir}/${pg_database}-${timestamp}${safe_tag}.${extension}"
sha_file="${dump_file}.sha256"
manifest_file="${dump_file}.manifest.json"

if ! docker compose ps postgres --status running >/dev/null 2>&1; then
  echo "PostgreSQL container is not running. Start it with: docker compose up -d" >&2
  exit 1
fi

echo "Creating PostgreSQL backup:"
echo "  database: ${pg_database}"
echo "  user:     ${pg_user}"
echo "  file:     ${dump_file}"
echo "  format:   ${format}"

docker compose exec -T \
  -e "PGPASSWORD=${pg_password}" \
  postgres \
  pg_dump \
  -U "$pg_user" \
  -d "$pg_database" \
  "${pg_dump_args[@]}" \
  > "$dump_file"

chmod 600 "$dump_file"
sha256sum "$dump_file" > "$sha_file"

bytes="$(wc -c < "$dump_file" | tr -d ' ')"
sha256="$(cut -d ' ' -f 1 "$sha_file")"

cat > "$manifest_file" <<EOF
{
  "created_at_utc": "${timestamp}",
  "database": "${pg_database}",
  "format": "${format}",
  "file": "${dump_file}",
  "bytes": ${bytes},
  "sha256": "${sha256}",
  "restore_hint": "Use pg_restore for .dump files, psql for .sql files. Restore only into a disposable or explicitly intended target database."
}
EOF
chmod 600 "$manifest_file" "$sha_file"

echo "Backup complete:"
echo "  dump:     ${dump_file}"
echo "  sha256:   ${sha_file}"
echo "  manifest: ${manifest_file}"
