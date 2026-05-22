"""CLI ingest — `rag ingest <file|dir>` command."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

import asyncpg
import typer
from rich.progress import Progress

from rag_ocpp.chunking.engine import ChunkingEngine
from rag_ocpp.config import get_config, load_config
from rag_ocpp.embedding.batch import BatchEmbedder
from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.ingestion.cleaner import TextCleaner
from rag_ocpp.ingestion.metadata import OCPPMetadataExtractor
from rag_ocpp.ingestion.parser import DocumentParser
from rag_ocpp.knowledge.extractor import EntityExtractor
from rag_ocpp.knowledge.linker import EntityLinker
from rag_ocpp.storage.vector import ChunkInsert, VectorStore

ingest_app = typer.Typer(no_args_is_help=True)


@ingest_app.command()
def ingest(
    path: str = typer.Argument(..., help="PDF or JSON file, or directory"),
    doc_type: str = typer.Option("spec", help="spec, test_suite, json_config, other"),
    protocol: str = typer.Option("ocpp21"),
    version: str = typer.Option("2.1"),
    no_entities: bool = typer.Option(False, "--no-entities", help="Skip entity extraction"),
    no_embed: bool = typer.Option(False, "--no-embed", help="Skip embedding"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse+chunk only, no DB"),
):
    """Ingest PDF/JSON into the knowledge base."""
    asyncio.run(_ingest_async(
        Path(path), doc_type, protocol, version, no_entities, no_embed, dry_run,
    ))


async def _ingest_async(
    path: Path, doc_type: str, protocol: str, version: str,
    no_entities: bool, no_embed: bool, dry_run: bool,
) -> None:
    load_config()
    cfg = get_config()

    logging.basicConfig(level=getattr(logging, cfg.logging.level))

    files = sorted(path.rglob("*")) if path.is_dir() else [path]
    files = [f for f in files if f.suffix.lower() in (".pdf", ".json")]
    if not files:
        typer.echo("No .pdf or .json files found."); raise typer.Exit(1)

    typer.echo(f"Found {len(files)} file(s).\n")

    if dry_run:
        await _dry_run(files, doc_type); return

    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn)
    assert pool

    try:
        vs = VectorStore(pool)
        model = EmbeddingModel(cfg.embedding)
        embedder = BatchEmbedder(pool, model, vs)
        linker = EntityLinker(pool)
        extractor = EntityExtractor(enable_llm=not no_entities)
        total_c, total_e = 0, 0

        with Progress() as progress:
            task = progress.add_task("Ingesting...", total=len(files))
            for fp in files:
                progress.console.print(f"[bold]{fp.name}[/bold]")
                try:
                    cc, ce = await _one(fp, vs, pool, model, embedder, linker, extractor,
                                        doc_type, protocol, version, no_embed, no_entities)
                    total_c += cc; total_e += ce
                    progress.console.print(f"  OK {cc} chunks, {ce} entities\n")
                except Exception as exc:
                    progress.console.print(f"  [red]FAIL: {exc}[/red]\n")
                progress.advance(task)

        typer.echo(f"Done. {total_c} chunks, {total_e} entities from {len(files)} docs.")
    finally:
        await pool.close()


async def _one(fp, vs, pool, model, embedder, linker, extractor,
              doc_type, protocol, version, no_embed, no_entities):
    parsed = DocumentParser().parse(fp); parsed.doc_type = doc_type
    cleaner = TextCleaner()
    for p in parsed.pages: p.text = cleaner.clean(p.text)
    meta = OCPPMetadataExtractor().extract(fp, parsed, protocol=protocol, version=version, doc_type=doc_type)

    doc_id = await vs.insert_document(
        protocol_id=1, source_path=fp.name, doc_type=doc_type,
        title=meta.part or fp.name, version=meta.version,
        part=meta.part, page_count=parsed.metadata.page_count, raw_bytes=fp.stat().st_size)

    chunks = ChunkingEngine().chunk(parsed, doc_type)
    inserts = [ChunkInsert(id=uuid.uuid4(), document_id=doc_id, chunk_index=i,
                           content=c.content, content_hash=c.content_hash,
                           strategy=c.strategy, section_title=c.section_title,
                           page_start=c.page_start, page_end=c.page_end, token_count=c.token_count)
               for i, c in enumerate(chunks)]
    await vs.insert_chunks(inserts)

    if not no_embed:
        await embedder.embed_batch([ci.id for ci in inserts], [ci.content for ci in inserts])

    ec = 0
    if not no_entities:
        for ci in inserts:
            r = await extractor.extract(ci.content, ci.content_hash)
            if r.entities: await linker.resolve_and_link(ci.id, r.entities); ec += len(r.entities)
            if r.relations: await linker.resolve_relations(r.relations)

    return len(chunks), ec


async def _dry_run(files, doc_type):
    parser, engine, cleaner = DocumentParser(), ChunkingEngine(), TextCleaner()
    tp, tc = 0, 0
    for fp in files:
        parsed = parser.parse(fp)
        for p in parsed.pages: p.text = cleaner.clean(p.text)
        chunks = engine.chunk(parsed, doc_type)
        tp += parsed.metadata.page_count; tc += len(chunks)
        typer.echo(f"  {fp.name}: {parsed.metadata.page_count}p → {len(chunks)} chunks")
    typer.echo(f"\nTotal: {tp}p → {tc} chunks (dry run)")
