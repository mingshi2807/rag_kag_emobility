"""Plain-SQL database migration runner."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncpg

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
BASELINE_VERSIONS = {"001"}


@dataclass(frozen=True)
class Migration:
    """A discovered SQL migration file."""

    version: str
    name: str
    path: Path
    checksum: str
    sql: str


@dataclass(frozen=True)
class MigrationStatus:
    """Migration state for reporting."""

    version: str
    name: str
    checksum: str
    applied: bool
    applied_at: str | None = None


@dataclass(frozen=True)
class MigrationResult:
    """Migration execution summary."""

    applied: list[Migration]
    skipped: list[Migration]
    dry_run: bool = False


class MigrationError(RuntimeError):
    """Raised when the database migration ledger is inconsistent."""


class MigrationRunner:
    """Apply versioned SQL migrations exactly once."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        migrations_dir: Path | None = None,
    ) -> None:
        self._pool = pool
        self._migrations_dir = migrations_dir or MIGRATIONS_DIR

    def discover(self) -> list[Migration]:
        """Return migrations sorted by versioned filename."""
        migrations = []
        for path in sorted(self._migrations_dir.glob("*.sql")):
            version, name = _parse_migration_filename(path)
            sql = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            migrations.append(
                Migration(
                    version=version,
                    name=name,
                    path=path,
                    checksum=checksum,
                    sql=sql,
                )
            )
        return migrations

    async def apply(self, *, dry_run: bool = False) -> MigrationResult:
        """Apply all pending migrations."""
        migrations = self.discover()
        applied: list[Migration] = []
        skipped: list[Migration] = []

        async with self._pool.acquire() as conn:
            await self._ensure_ledger(conn)
            ledger = await self._ledger(conn)

            for migration in migrations:
                existing = ledger.get(migration.version)
                if existing is not None:
                    if existing["checksum"] != migration.checksum:
                        raise MigrationError(
                            f"Migration {migration.version} checksum mismatch. "
                            "Create a new migration instead of editing applied SQL."
                        )
                    skipped.append(migration)
                    continue

                if dry_run:
                    applied.append(migration)
                    continue

                async with conn.transaction():
                    await conn.execute(migration.sql)
                    await conn.execute(
                        """
                        INSERT INTO schema_migrations (version, name, checksum)
                        VALUES ($1,$2,$3)
                        """,
                        migration.version,
                        migration.name,
                        migration.checksum,
                    )
                applied.append(migration)

        return MigrationResult(applied=applied, skipped=skipped, dry_run=dry_run)

    async def baseline(self) -> MigrationResult:
        """Record baseline migrations as applied for a validated existing schema."""
        migrations = [
            migration
            for migration in self.discover()
            if migration.version in BASELINE_VERSIONS
        ]
        applied: list[Migration] = []
        skipped: list[Migration] = []

        async with self._pool.acquire() as conn:
            await self._ensure_baseline_schema(conn)
            await self._ensure_ledger(conn)
            ledger = await self._ledger(conn)

            async with conn.transaction():
                for migration in migrations:
                    existing = ledger.get(migration.version)
                    if existing is not None:
                        if existing["checksum"] != migration.checksum:
                            raise MigrationError(
                                f"Migration {migration.version} checksum mismatch. "
                                "Create a new migration instead of editing applied SQL."
                            )
                        skipped.append(migration)
                        continue

                    await conn.execute(
                        """
                        INSERT INTO schema_migrations (version, name, checksum)
                        VALUES ($1,$2,$3)
                        """,
                        migration.version,
                        migration.name,
                        migration.checksum,
                    )
                    applied.append(migration)

        return MigrationResult(applied=applied, skipped=skipped, dry_run=False)

    async def status(self) -> list[MigrationStatus]:
        """Return applied/pending status for discovered migrations."""
        migrations = self.discover()
        async with self._pool.acquire() as conn:
            await self._ensure_ledger(conn)
            ledger = await self._ledger(conn)

        return [
            MigrationStatus(
                version=migration.version,
                name=migration.name,
                checksum=migration.checksum,
                applied=migration.version in ledger,
                applied_at=(
                    str(ledger[migration.version]["applied_at"])
                    if migration.version in ledger
                    else None
                ),
            )
            for migration in migrations
        ]

    async def _ensure_ledger(self, conn: asyncpg.Connection) -> None:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version     TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                checksum    TEXT NOT NULL,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )

    async def _ledger(self, conn: asyncpg.Connection) -> dict[str, dict[str, Any]]:
        rows = await conn.fetch(
            "SELECT version, name, checksum, applied_at FROM schema_migrations"
        )
        return {row["version"]: dict(row) for row in rows}

    async def _ensure_baseline_schema(self, conn: asyncpg.Connection) -> None:
        required_tables = {
            "chunks",
            "corpus_records",
            "documents",
            "entities",
            "source_documents",
        }
        rows = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY($1::text[])
            """,
            sorted(required_tables),
        )
        existing = {row["table_name"] for row in rows}
        missing = sorted(required_tables - existing)
        if missing:
            missing_list = ", ".join(missing)
            raise MigrationError(
                "Cannot baseline database; missing required table(s): "
                f"{missing_list}. Run migrations on a fresh database instead."
            )


def _parse_migration_filename(path: Path) -> tuple[str, str]:
    stem = path.stem
    if "_" not in stem:
        raise MigrationError(
            f"Invalid migration filename {path.name}; expected '<version>_<name>.sql'."
        )
    version, name = stem.split("_", 1)
    if not version.isdigit():
        raise MigrationError(
            f"Invalid migration filename {path.name}; version must be numeric."
        )
    return version, name
