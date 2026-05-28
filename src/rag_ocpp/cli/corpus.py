"""CLI for source-aware OCPP 2.1 Ed2 corpus records."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import asyncpg
import typer
from rich.progress import Progress

from rag_ocpp.config import get_config, load_config
from rag_ocpp.corpus.indexer import CorpusIndexer
from rag_ocpp.corpus.models import SourceDocument
from rag_ocpp.corpus.ocpp21 import (
    OCPP21_ED2_DM_DIR,
    OCPP21_ED2_JSON_SCHEMA_DIR,
    OCPP21_ED2_PART2_SPEC_PDF,
    parse_device_model_csv,
    parse_device_model_xlsx,
    parse_json_schema_file,
    parse_spec_pdf_sections,
)
from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.privacy import configure_redacted_logging
from rag_ocpp.storage.corpus import (
    CorpusRecordInsert,
    CorpusStore,
    SourceDocumentInsert,
)


def corpus_command(
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--store",
        help="Preview records by default. Use --store to write source/corpus records.",
    ),
    spec_pdf: Path = typer.Option(
        OCPP21_ED2_PART2_SPEC_PDF,
        help="OCPP 2.1 Ed2 Part 2 specification PDF.",
    ),
    dm_dir: Path = typer.Option(
        OCPP21_ED2_DM_DIR,
        help="OCPP 2.1 Ed2 appendices CSV/XLSX directory.",
    ),
    schema_dir: Path = typer.Option(
        OCPP21_ED2_JSON_SCHEMA_DIR,
        help="OCPP 2.1 Part 3 JSON schema directory.",
    ),
    include_pdf: bool = typer.Option(True, help="Parse the Part 2 PDF sections."),
    include_dm: bool = typer.Option(True, help="Parse Device Model and appendix tables."),
    include_schemas: bool = typer.Option(True, help="Parse JSON schema files."),
) -> None:
    """Build source-aware corpus records for OCPP 2.1 Ed2 Part 2."""
    asyncio.run(
        _corpus_async(
            dry_run=dry_run,
            spec_pdf=spec_pdf,
            dm_dir=dm_dir,
            schema_dir=schema_dir,
            include_pdf=include_pdf,
            include_dm=include_dm,
            include_schemas=include_schemas,
        )
    )


async def _corpus_async(
    *,
    dry_run: bool,
    spec_pdf: Path,
    dm_dir: Path,
    schema_dir: Path,
    include_pdf: bool,
    include_dm: bool,
    include_schemas: bool,
) -> None:
    load_config()
    cfg = get_config()
    configure_redacted_logging(level=getattr(logging, cfg.logging.level))

    planned = _planned_sources(
        spec_pdf=spec_pdf,
        dm_dir=dm_dir,
        schema_dir=schema_dir,
        include_pdf=include_pdf,
        include_dm=include_dm,
        include_schemas=include_schemas,
    )
    if not planned:
        typer.echo("No source files selected.")
        raise typer.Exit(1)

    pool: asyncpg.Pool | None = None
    store: CorpusStore | None = None
    if not dry_run:
        pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn)
        store = CorpusStore(pool)

    total_records = 0
    try:
        with Progress() as progress:
            task = progress.add_task("Building corpus...", total=len(planned))
            for source_path, parser_name in planned:
                progress.console.print(f"[bold]{source_path.name}[/bold]")
                records = _parse_source(source_path, parser_name)
                total_records += len(records)
                progress.console.print(f"  {len(records)} records")
                if store is not None:
                    source = _source_document_for(source_path, parser_name)
                    source_id = await store.upsert_source_document(
                        SourceDocumentInsert.from_source_document(source)
                    )
                    inserts = [
                        CorpusRecordInsert.from_evidence_record(source_id, record)
                        for record in records
                    ]
                    await store.upsert_corpus_records(inserts)
                progress.advance(task)
    finally:
        if pool is not None:
            await pool.close()

    mode = "Previewed" if dry_run else "Stored"
    typer.echo(f"{mode} {total_records} corpus records from {len(planned)} sources.")


def index_corpus_command(
    no_embed: bool = typer.Option(False, "--no-embed", help="Create chunks/graph only."),
    batch_size: int = typer.Option(128, help="Embedding batch size."),
    limit: int | None = typer.Option(None, help="Optional record limit for smoke tests."),
) -> None:
    """Index stored corpus records into chunks, embeddings, and graph links."""
    asyncio.run(
        _index_corpus_async(no_embed=no_embed, batch_size=batch_size, limit=limit)
    )


async def _index_corpus_async(
    *, no_embed: bool, batch_size: int, limit: int | None,
) -> None:
    load_config()
    cfg = get_config()
    configure_redacted_logging(level=getattr(logging, cfg.logging.level))

    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn)
    try:
        model = None if no_embed else EmbeddingModel(cfg.embedding)
        indexer = CorpusIndexer(pool, model)
        result = await indexer.index_all(
            embed=not no_embed,
            batch_size=batch_size,
            limit=limit,
        )
    finally:
        await pool.close()

    typer.echo(
        "Indexed corpus: "
        f"{result.sources_indexed} sources, "
        f"{result.records_indexed} records, "
        f"{result.chunks_upserted} chunks, "
        f"{result.chunks_embedded} embeddings, "
        f"{result.entities_linked} entity links, "
        f"{result.relationships_created} relationships."
    )


def _planned_sources(
    *,
    spec_pdf: Path,
    dm_dir: Path,
    schema_dir: Path,
    include_pdf: bool,
    include_dm: bool,
    include_schemas: bool,
) -> list[tuple[Path, str]]:
    planned: list[tuple[Path, str]] = []
    if include_pdf:
        planned.append((spec_pdf, "spec_pdf"))
    if include_dm:
        for path in sorted(dm_dir.glob("*.csv")):
            planned.append((path, "dm_csv"))
        for path in sorted(dm_dir.glob("*.xlsx")):
            planned.append((path, "dm_xlsx"))
    if include_schemas:
        for path in sorted(schema_dir.glob("*.json")):
            planned.append((path, "json_schema"))
    return [(path, parser) for path, parser in planned if path.exists()]


def _parse_source(path: Path, parser_name: str):
    match parser_name:
        case "spec_pdf":
            return parse_spec_pdf_sections(path)
        case "dm_csv":
            return parse_device_model_csv(path)
        case "dm_xlsx":
            return parse_device_model_xlsx(path)
        case "json_schema":
            return parse_json_schema_file(path)
        case _:
            raise ValueError(f"Unsupported source parser: {parser_name}")


def _source_document_for(path: Path, parser_name: str) -> SourceDocument:
    if parser_name == "spec_pdf":
        return SourceDocument.from_file(
            path,
            source_type="spec_pdf",
            evidence_layer="spec",
            title="OCPP 2.1 Edition 2 Part 2 Specification",
            document_date="2025-12-03",
        )
    if parser_name == "json_schema":
        return SourceDocument.from_file(
            path,
            source_type="json_schema",
            evidence_layer="schema",
            title=path.stem,
            document_date="2025-01-23",
        )
    return SourceDocument.from_file(
        path,
        source_type="device_model_table"
        if path.name in {"dm_components_vars.csv", "dm_components_vars.xlsx"}
        else "appendix_csv",
        evidence_layer="device_model",
        title=path.stem,
        document_date="2025-12-03",
    )
