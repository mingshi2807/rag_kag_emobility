"""Result fusion — Reciprocal Rank Fusion (RRF) merging multiple ranked lists."""

from __future__ import annotations

from collections import defaultdict

from rag_ocpp.retrieval.searchers import ScoredChunk


def reciprocal_rank_fusion(
    result_sets: list[list[ScoredChunk]], k: int = 60,
) -> list[tuple[ScoredChunk, float]]:
    """Merge multiple ranked result lists via RRF.

    RRF score = Σ (1 / (k + rank_in_list))

    Why RRF: no need to normalize scores across strategies
    (cosine in [0,1], ts_rank unbounded, confidence in [0,1]).
    Robust to outlier scores. Proven in TREC/BEIR benchmarks.
    """
    scores: dict[str, float] = defaultdict(float)
    items: dict[str, ScoredChunk] = {}

    for results in result_sets:
        for rank, chunk in enumerate(results):
            cid = str(chunk.chunk_id)
            scores[cid] += 1.0 / (k + rank + 1)
            if cid not in items:
                items[cid] = chunk

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [(items[cid], fused_score) for cid, fused_score in ranked]


def weighted_fusion(
    result_sets: list[list[ScoredChunk]], weights: list[float],
) -> list[tuple[ScoredChunk, float]]:
    """Weighted score sum (requires normalized scores across strategies)."""
    scores: dict[str, float] = defaultdict(float)
    items: dict[str, ScoredChunk] = {}

    for weight, results in zip(weights, result_sets):
        max_score = max((c.score for c in results), default=1.0)
        for chunk in results:
            cid = str(chunk.chunk_id)
            norm = chunk.score / max_score if max_score > 0 else 0.0
            scores[cid] += weight * norm
            if cid not in items:
                items[cid] = chunk

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [(items[cid], ws) for cid, ws in ranked]
