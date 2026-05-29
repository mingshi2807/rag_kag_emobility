"""CLI commands for the source-aware ontology catalog."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import asyncpg
import typer

from rag_ocpp.config import get_config, load_config
from rag_ocpp.ontology.store import DEFAULT_ONTOLOGY_PATH, OntologyStore


def ontology_load_command(
    path: Path = typer.Option(
        DEFAULT_ONTOLOGY_PATH,
        "--path",
        help="Ontology YAML seed to load.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate and summarize the seed without writing to the database.",
    ),
) -> None:
    """Load the source-aware ontology catalog."""
    asyncio.run(_ontology_load_async(path=path, dry_run=dry_run))


def ontology_status_command() -> None:
    """Show source-aware ontology catalog counts."""
    asyncio.run(_ontology_status_async())


async def _ontology_load_async(*, path: Path, dry_run: bool) -> None:
    load_config()
    cfg = get_config()
    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn)
    try:
        store = OntologyStore(pool)
        status = await store.load_seed(path=path, dry_run=dry_run)
    finally:
        await pool.close()
    verb = "Would load" if dry_run else "Loaded"
    typer.echo(f"{verb} ontology {status.version}:")
    typer.echo(_status_json(status))


async def _ontology_status_async() -> None:
    load_config()
    cfg = get_config()
    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn)
    try:
        store = OntologyStore(pool)
        status = await store.status()
    finally:
        await pool.close()
    typer.echo(_status_json(status))


def _status_json(status) -> str:
    return json.dumps(
        {
            "protocol_id": status.protocol_id,
            "version": status.version,
            "versions": status.versions,
            "entity_classes": status.entity_classes,
            "relation_types": status.relation_types,
            "evidence_layers": status.evidence_layers,
            "source_types": status.source_types,
            "mapping_rules": status.mapping_rules,
        },
        indent=2,
        sort_keys=True,
    )
