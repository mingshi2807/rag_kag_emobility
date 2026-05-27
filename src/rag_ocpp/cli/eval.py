"""CLI eval commands."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

import asyncpg
import typer

from rag_ocpp.config import get_config, load_config
from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.eval.metrics import EvalQuery, evaluate
from rag_ocpp.eval.quality import (
    build_report,
    default_quality_cases,
    filter_cases,
    score_case,
    write_report,
)
from rag_ocpp.retrieval.hybrid import HybridRetriever, SearchFilters
from rag_ocpp.retrieval.reranker import CrossEncoderReranker


def eval_retrieval(
    queries_path: str = typer.Argument(..., help="queries.jsonl"),
    top_k: int = typer.Option(10, "--top-k", "-k"),
):
    """Evaluate retrieval against ground-truth queries.

    queries.jsonl: {"query":"...","relevant":["uuid1","uuid2"]}
    """
    asyncio.run(_eval_async(queries_path, top_k))


async def _eval_async(queries_path: str, top_k: int):
    load_config()
    cfg = get_config()
    logging.basicConfig(level=getattr(logging, cfg.logging.level))

    path = Path(queries_path)
    if not path.exists():
        typer.echo(f"Not found: {path}")
        raise typer.Exit(1)

    queries: list[EvalQuery] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            queries.append(EvalQuery(query=obj["query"], relevant_chunk_ids=obj["relevant"]))

    typer.echo(f"Loaded {len(queries)} queries.\n")

    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn)
    assert pool
    try:
        emb = EmbeddingModel(cfg.embedding)
        emb.load()
        reranker = CrossEncoderReranker(cfg.reranker)
        reranker.load()
        retriever = HybridRetriever(
            pool=pool,
            embedding_model=emb,
            reranker=reranker,
            final_top_k=top_k,
        )

        retrieved: list[list[str]] = []
        t0 = time.monotonic()

        for i, q in enumerate(queries):
            result = await retriever.retrieve(q.query)
            cids = [str(c.chunk_id) for c in result.chunks]
            retrieved.append(cids)
            hits = sum(1 for c in cids if c in q.relevant_chunk_ids)
            typer.echo(
                f"[{i + 1}/{len(queries)}] {q.query[:60]} -> "
                f"{hits}/{len(q.relevant_chunk_ids)} hits"
            )

        elapsed = time.monotonic() - t0
        m = evaluate(queries, retrieved)

        typer.echo(f"\n{'='*50}")
        typer.echo(f"Queries:   {m.num_queries}")
        typer.echo(f"MRR:       {m.mrr:.4f}")
        typer.echo(f"Recall@5:  {m.recall_at_5:.4f}")
        typer.echo(f"Recall@10: {m.recall_at_10:.4f}")
        typer.echo(f"NDCG@10:   {m.ndcg_at_10:.4f}")
        typer.echo(f"Time:      {elapsed:.1f}s ({elapsed/len(queries):.1f}s/q)")

    finally:
        await pool.close()


def eval_quality_command(
    top_k: int = typer.Option(12, "--top-k", "-k", help="Retrieved chunks per case."),
    fail_under: float = typer.Option(0.80, "--fail-under", help="Minimum average score."),
    topic: list[str] | None = typer.Option(
        None,
        "--topic",
        help="Filter by topic text, e.g. R, Q, K, DER, V2X, smart.",
    ),
    mode: list[str] | None = typer.Option(
        None,
        "--mode",
        help="Filter by mode: spec, dm, schema, fusion.",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write Markdown or JSON report. Extension decides format.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print JSON instead of Markdown."),
    list_cases: bool = typer.Option(
        False,
        "--list-cases",
        help="List cases without running retrieval.",
    ),
):
    """Run OCPP 2.1 Ed2 query quality checks for R/Q/K implementation topics."""
    asyncio.run(
        _eval_quality_async(
            top_k=top_k,
            fail_under=fail_under,
            topic=topic or [],
            mode=mode or [],
            output=output,
            json_output=json_output,
            list_cases=list_cases,
        )
    )


async def _eval_quality_async(
    *,
    top_k: int,
    fail_under: float,
    topic: list[str],
    mode: list[str],
    output: str | None,
    json_output: bool,
    list_cases: bool,
) -> None:
    load_config()
    cfg = get_config()
    logging.basicConfig(level=getattr(logging, cfg.logging.level))

    cases = filter_cases(default_quality_cases(), topics=topic, modes=mode)
    if list_cases:
        for case in cases:
            typer.echo(f"{case.case_id}\t{case.topic}\t{case.mode}\t{case.query}")
        return
    if not cases:
        typer.echo("No quality cases selected.")
        raise typer.Exit(1)

    pool = await asyncpg.create_pool(dsn=cfg.postgres.dsn)
    assert pool
    try:
        emb = EmbeddingModel(cfg.embedding)
        emb.load()
        reranker = CrossEncoderReranker(cfg.reranker)
        reranker.load()
        retriever = HybridRetriever(
            pool=pool,
            embedding_model=emb,
            reranker=reranker,
            final_top_k=top_k,
        )

        results = []
        typer.echo(f"Running {len(cases)} OCPP quality cases...\n")
        for index, case in enumerate(cases, start=1):
            filters = None
            if case.evidence_layer:
                filters = SearchFilters(evidence_layer=case.evidence_layer)
            retrieval = await retriever.retrieve(case.query, filters=filters)
            result = score_case(
                case,
                retrieval.chunks[:top_k],
                latency_ms=retrieval.latency_ms,
                strategy_breakdown=retrieval.strategy_breakdown,
            )
            results.append(result)
            status = "PASS" if result.passed else "FAIL"
            typer.echo(
                f"[{index}/{len(cases)}] {status} {case.case_id} "
                f"score={result.score:.3f} missing_layers={result.missing_layers} "
                f"missing_terms={result.missing_required_terms}"
            )

        report = build_report(
            results,
            suite="ocpp21-ed2-rqk-source-aware",
            top_k=top_k,
            fail_under=fail_under,
        )
        rendered = report.to_json() if json_output else report.to_markdown()
        typer.echo("\n" + rendered)
        if output:
            write_report(report, output)
            typer.echo(f"Report written: {output}")
        if not report.passed:
            raise typer.Exit(2)
    finally:
        await pool.close()
