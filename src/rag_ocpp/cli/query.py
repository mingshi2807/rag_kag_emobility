"""CLI query — `rag query <text>` command."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

import asyncpg
import typer

from rag_ocpp.config import get_config, load_config
from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.generation.client import DeepSeekClient
from rag_ocpp.privacy import configure_redacted_logging, redact_value
from rag_ocpp.retrieval.hybrid import HybridRetriever, SearchFilters
from rag_ocpp.retrieval.reranker import CrossEncoderReranker
from rag_ocpp.storage.audit import AuditEvent, AuditStore, sensitive_text_ref



def query_command(
    query_text: str = typer.Argument(..., help="Your question about OCPP 2.1"),
    top_k: int = typer.Option(5, "--top-k", "-k"),
    stream: bool = typer.Option(False, "--stream", "-s"),
    doc_type: str = typer.Option(None, "--doc-type"),
    evidence_layer: str = typer.Option(
        None,
        "--evidence-layer",
        help="Restrict retrieval to one evidence layer: spec, device_model, schema.",
    ),
):
    """Query the OCPP 2.1 knowledge base."""
    asyncio.run(_query_async(query_text, top_k, stream, doc_type, evidence_layer))


async def _query_async(query_text, top_k, stream, doc_type, evidence_layer):
    load_config(); cfg = get_config()
    configure_redacted_logging(
        level=getattr(logging, cfg.logging.level),
        enabled=cfg.logging.redaction_enabled,
    )

    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn)
    assert pool
    audit = AuditStore(pool)
    correlation_id = str(uuid.uuid4())

    try:
        await _audit(
            audit,
            AuditEvent(
                event_type="query.requested",
                surface="cli",
                action="query",
                correlation_id=correlation_id,
                metadata={
                    "query": sensitive_text_ref(query_text),
                    "top_k": top_k,
                    "doc_type": doc_type,
                    "evidence_layer": evidence_layer,
                    "stream": stream,
                },
            ),
        )
        embedding = EmbeddingModel(cfg.embedding); embedding.load()
        reranker = CrossEncoderReranker(cfg.reranker); reranker.load()
        retriever = HybridRetriever(pool=pool, embedding_model=embedding, reranker=reranker, final_top_k=top_k)
        llm = DeepSeekClient(cfg.deepseek)

        t0 = time.monotonic()
        retrieval = await retriever.retrieve(
            query_text,
            filters=SearchFilters(doc_type=doc_type, evidence_layer=evidence_layer),
        )
        rms = int((time.monotonic() - t0) * 1000)
        await _audit(
            audit,
            AuditEvent(
                event_type="retrieval.completed",
                surface="cli",
                action="retrieve",
                correlation_id=correlation_id,
                latency_ms=retrieval.latency_ms,
                metadata={
                    "query": sensitive_text_ref(query_text),
                    "chunks": len(retrieval.chunks),
                    "strategy_breakdown": retrieval.strategy_breakdown,
                    "chunk_ids": [str(c.chunk_id) for c in retrieval.chunks],
                },
            ),
        )

        typer.echo(f"\n{len(retrieval.chunks)} chunks ({retrieval.strategy_breakdown}) in {rms}ms\n")
        typer.echo("─" * 60)
        for i, c in enumerate(retrieval.chunks):
            metadata = c.metadata or {}
            layer = metadata.get("evidence_layer") or "unknown"
            source_type = metadata.get("source_type") or "unknown"
            src = f"[{c.section_title or 'Section'}]"
            if c.page_start: src += f" p.{c.page_start}"
            typer.echo(
                f"  [{i+1}] {src} ({c.strategy}, {c.score:.3f}, "
                f"{layer}/{source_type})"
            )
            typer.echo(f"      {c.content[:120]}...")
        typer.echo("─" * 60)

        ctx = [
            {
                "content": c.content,
                "section_title": c.section_title or "Section",
                "document_title": (c.metadata or {}).get("source_path")
                or str(c.document_id)[:36],
                "page_start": c.page_start,
                "evidence_layer": (c.metadata or {}).get("evidence_layer"),
                "source_type": (c.metadata or {}).get("source_type"),
            }
            for c in retrieval.chunks
        ]

        if stream:
            typer.echo("\nAnswer:\n")
            token_count = 0
            try:
                async for token in llm.generate_stream(query_text, ctx):
                    token_count += 1
                    typer.echo(token, nl=False)
                typer.echo()
                await _audit(
                    audit,
                    AuditEvent(
                        event_type="generation.completed",
                        surface="cli",
                        action="generate_stream",
                        correlation_id=correlation_id,
                        metadata={
                            "query": sensitive_text_ref(query_text),
                            "model": llm.model,
                            "context_chunks": len(ctx),
                            "stream_tokens": token_count,
                        },
                    ),
                )
            except Exception as exc:
                await _audit(
                    audit,
                    AuditEvent(
                        event_type="generation.failed",
                        surface="cli",
                        action="generate_stream",
                        status="failure",
                        correlation_id=correlation_id,
                        metadata={
                            "query": sensitive_text_ref(query_text),
                            "model": llm.model,
                            "error": redact_value(exc, force=True),
                        },
                    ),
                )
                raise
        else:
            typer.echo("\nGenerating...")
            try:
                answer = await llm.generate(query_text, ctx)
                await _audit(
                    audit,
                    AuditEvent(
                        event_type="generation.completed",
                        surface="cli",
                        action="generate",
                        correlation_id=correlation_id,
                        metadata={
                            "query": sensitive_text_ref(query_text),
                            "model": llm.model,
                            "context_chunks": len(ctx),
                            "answer_length": len(answer),
                        },
                    ),
                )
            except Exception as exc:
                await _audit(
                    audit,
                    AuditEvent(
                        event_type="generation.failed",
                        surface="cli",
                        action="generate",
                        status="failure",
                        correlation_id=correlation_id,
                        metadata={
                            "query": sensitive_text_ref(query_text),
                            "model": llm.model,
                            "error": redact_value(exc, force=True),
                        },
                    ),
                )
                raise
            typer.echo(f"\n{answer}\n")

        typer.echo(f"(total: {int((time.monotonic()-t0)*1000)}ms)")
    finally:
        await pool.close()


async def _audit(audit: AuditStore, event: AuditEvent) -> None:
    try:
        await audit.record(event)
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Audit event write failed: %s",
            redact_value(exc),
        )
