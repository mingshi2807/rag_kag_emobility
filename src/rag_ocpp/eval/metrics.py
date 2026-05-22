"""Evaluation metrics — MRR, Recall@k, NDCG@k."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class EvalQuery:
    query: str
    relevant_chunk_ids: list[str]


@dataclass
class EvalResult:
    mrr: float
    recall_at_5: float
    recall_at_10: float
    ndcg_at_10: float
    num_queries: int


def mean_reciprocal_rank(retrieved: list[list[str]], relevant: list[list[str]]) -> float:
    if not retrieved:
        return 0.0
    total = 0.0
    for ret, rel in zip(retrieved, relevant):
        rel_set = set(rel)
        for rank, cid in enumerate(ret, start=1):
            if cid in rel_set:
                total += 1.0 / rank
                break
    return total / len(retrieved)


def recall_at_k(retrieved: list[list[str]], relevant: list[list[str]], k: int) -> float:
    if not retrieved:
        return 0.0
    total = 0.0
    for ret, rel in zip(retrieved, relevant):
        rel_set = set(rel)
        hits = sum(1 for cid in ret[:k] if cid in rel_set)
        total += hits / len(rel_set) if rel_set else 0.0
    return total / len(retrieved)


def ndcg_at_k(retrieved: list[list[str]], relevant: list[list[str]], k: int) -> float:
    if not retrieved:
        return 0.0
    total = 0.0
    for ret, rel in zip(retrieved, relevant):
        rel_set = set(rel)
        dcg = sum(1.0 / math.log2(i + 2) for i, cid in enumerate(ret[:k]) if cid in rel_set)
        idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(rel_set), k)))
        total += dcg / idcg if idcg > 0 else 0.0
    return total / len(retrieved)


def evaluate(queries: list[EvalQuery], retrieved_ids: list[list[str]]) -> EvalResult:
    relevant = [q.relevant_chunk_ids for q in queries]
    return EvalResult(
        mrr=mean_reciprocal_rank(retrieved_ids, relevant),
        recall_at_5=recall_at_k(retrieved_ids, relevant, 5),
        recall_at_10=recall_at_k(retrieved_ids, relevant, 10),
        ndcg_at_10=ndcg_at_k(retrieved_ids, relevant, 10),
        num_queries=len(queries),
    )
