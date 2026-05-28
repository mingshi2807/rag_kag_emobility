"""Database migration CLI commands."""

from __future__ import annotations

import asyncio
import logging

import asyncpg
import typer

from rag_ocpp.config import get_config, load_config
from rag_ocpp.privacy import configure_redacted_logging
from rag_ocpp.storage.migrations import MigrationRunner


def migrate_command(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show pending migrations without applying them.",
    ),
    baseline: bool = typer.Option(
        False,
        "--baseline",
        help=(
            "Record migrations as applied for an existing schema-managed database. "
            "Use only after verifying the schema matches the current code."
        ),
    ),
) -> None:
    """Apply pending database migrations."""
    asyncio.run(_migrate_async(dry_run=dry_run, baseline=baseline))


def migrate_status_command() -> None:
    """Show migration status."""
    asyncio.run(_migrate_status_async())


async def _migrate_async(*, dry_run: bool, baseline: bool) -> None:
    if dry_run and baseline:
        raise typer.BadParameter("--dry-run and --baseline cannot be used together.")

    load_config()
    cfg = get_config()
    configure_redacted_logging(
        level=getattr(logging, cfg.logging.level),
        enabled=cfg.logging.redaction_enabled,
    )

    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn)
    try:
        runner = MigrationRunner(pool)
        if baseline:
            result = await runner.baseline()
        else:
            result = await runner.apply(dry_run=dry_run)
    finally:
        await pool.close()

    action = "Baselined" if baseline else "Would apply" if dry_run else "Applied"
    typer.echo(f"{action} {len(result.applied)} migration(s).")
    for migration in result.applied:
        typer.echo(f"  + {migration.version} {migration.name}")
    if result.skipped:
        typer.echo(f"Skipped {len(result.skipped)} already-applied migration(s).")


async def _migrate_status_async() -> None:
    load_config()
    cfg = get_config()
    configure_redacted_logging(
        level=getattr(logging, cfg.logging.level),
        enabled=cfg.logging.redaction_enabled,
    )

    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn)
    try:
        statuses = await MigrationRunner(pool).status()
    finally:
        await pool.close()

    if not statuses:
        typer.echo("No migrations found.")
        return

    for status in statuses:
        marker = "applied" if status.applied else "pending"
        suffix = f" at {status.applied_at}" if status.applied_at else ""
        typer.echo(f"{status.version} {status.name}: {marker}{suffix}")
