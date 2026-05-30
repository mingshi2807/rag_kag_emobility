"""Hybrid retriever — orchestrates vector, keyword, and graph search with fusion + rerank."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any

import asyncpg

from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.retrieval.fusion import reciprocal_rank_fusion
from rag_ocpp.retrieval.graph_search import GraphSearcher
from rag_ocpp.retrieval.reranker import CrossEncoderReranker
from rag_ocpp.retrieval.searchers import KeywordSearcher, ScoredChunk, VectorSearcher


@dataclass
class SearchFilters:
    protocol_id: int | None = None
    doc_type: str | None = None
    evidence_layer: str | None = None
    source_type: str | None = None


@dataclass
class RetrievalResult:
    chunks: list[ScoredChunk]
    strategy_breakdown: dict[str, int]
    latency_ms: int
    ontology_metrics: dict[str, Any] | None = None


class HybridRetriever:
    """Multi-strategy retrieval: vector + keyword + graph → RRF → rerank.

    Pipeline:
        1. Embed query
        2. Parallel: vector, keyword, graph searches
        3. RRF fusion (k=60)
        4. Cross-encoder rerank on top-30 fused
        5. Return top-k
    """

    def __init__(
        self, pool: asyncpg.Pool, embedding_model: EmbeddingModel,
        reranker: CrossEncoderReranker, *,
        vector_top_k: int = 20, keyword_top_k: int = 20,
        graph_top_k: int = 10, fusion_k: int = 60, final_top_k: int = 5,
        enable_graph: bool = True, enable_rerank: bool = True,
    ) -> None:
        self._vector = VectorSearcher(pool, embedding_model)
        self._keyword = KeywordSearcher(pool)
        self._graph = GraphSearcher(pool)
        self._reranker = reranker
        self._model = embedding_model
        self._vector_top_k = vector_top_k
        self._keyword_top_k = keyword_top_k
        self._graph_top_k = graph_top_k
        self._fusion_k = fusion_k
        self._final_top_k = final_top_k
        self._enable_graph = enable_graph
        self._enable_rerank = enable_rerank

    async def retrieve(
        self, query: str, *, filters: SearchFilters | None = None,
        top_k: int | None = None,
    ) -> RetrievalResult:
        save_k = self._final_top_k
        if top_k is not None:
            self._final_top_k = top_k

        t0 = time.monotonic()
        pid = filters.protocol_id if filters else None
        dt = filters.doc_type if filters else None
        evidence_layer = filters.evidence_layer if filters else None
        source_type = filters.source_type if filters else None
        search_query = _expand_query(query)
        is_dm_query = _is_device_model_query(query)
        is_dm_overview = _is_device_model_overview_query(query)
        message_terms = _extract_message_terms(query)
        is_message_overview = _is_message_overview_query(query, message_terms)
        is_schema_query = _is_schema_query(query)
        is_fusion_query = _is_evidence_fusion_query(query)

        self._model.embed_query(query)  # warm BGE cache

        tasks: list[asyncio.Task[list[ScoredChunk]]] = [
            asyncio.create_task(self._vector.search(
                search_query, top_k=self._vector_top_k, protocol_id=pid,
                doc_type=dt, evidence_layer=evidence_layer, source_type=source_type)),
            asyncio.create_task(self._keyword.search(
                search_query, top_k=self._keyword_top_k, protocol_id=pid,
                doc_type=dt, evidence_layer=evidence_layer, source_type=source_type)),
        ]
        extra_weights: list[float] = []
        if is_dm_query and evidence_layer is None:
            tasks.extend(
                [
                    asyncio.create_task(
                        self._keyword.search(
                            search_query,
                            top_k=self._keyword_top_k,
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer="device_model",
                        )
                    ),
                    asyncio.create_task(
                        self._keyword.search(
                            _DEVICE_MODEL_SPEC_QUERY,
                            top_k=max(10, self._keyword_top_k // 2),
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer="spec",
                        )
                    ),
                    asyncio.create_task(
                        self._vector.search(
                            search_query,
                            top_k=max(10, self._vector_top_k // 2),
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer="device_model",
                        )
                    ),
                ]
            )
            extra_weights.extend([4.0, 4.0, 2.0])
        if (is_schema_query or is_fusion_query) and evidence_layer is None:
            tasks.extend(
                [
                    asyncio.create_task(
                        self._keyword.search(
                            _schema_query(query),
                            top_k=max(12, self._keyword_top_k),
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer="schema",
                        )
                    ),
                    asyncio.create_task(
                        self._vector.search(
                            _schema_query(query),
                            top_k=max(10, self._vector_top_k // 2),
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer="schema",
                        )
                    ),
                ]
            )
            extra_weights.extend([5.0, 2.5])
        if is_fusion_query and evidence_layer is None:
            tasks.extend(
                [
                    asyncio.create_task(
                        self._keyword.search(
                            _topic_spec_query(query),
                            top_k=max(12, self._keyword_top_k),
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer="spec",
                        )
                    ),
                    asyncio.create_task(
                        self._keyword.search(
                            _topic_dm_query(query),
                            top_k=max(12, self._keyword_top_k),
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer="device_model",
                        )
                    )
                ]
            )
            extra_weights.extend([6.0, 6.0])
        if message_terms:
            for term in message_terms:
                tasks.append(
                    asyncio.create_task(
                        self._keyword.search(
                            _message_query(term),
                            top_k=max(12, self._keyword_top_k),
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer=evidence_layer,
                            source_type=source_type,
                        )
                    )
                )
                extra_weights.append(5.0)
        use_graph = (
            self._enable_graph
            and not is_dm_overview
            and not is_message_overview
            and evidence_layer is None
            and source_type is None
        )
        if use_graph:
            tasks.append(asyncio.create_task(self._graph.search(
                _graph_query(query), top_k=self._graph_top_k, protocol_id=pid or 1,
                expand_via_traversal=True)))

        import logging
        _log = logging.getLogger(__name__)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        vec = _search_result(results[0])
        kw = _search_result(results[1])
        extra_start = 2
        extra_end = extra_start + len(extra_weights)
        extra_sets = [_search_result(r) for r in results[extra_start:extra_end]]
        graph_index = extra_end
        gr = _search_result(results[graph_index]) if len(results) > graph_index else []
        labels = ["vec", "kw"] + [f"dm{i + 1}" for i in range(len(extra_weights))]
        if use_graph:
            labels.append("gr")
        for label, r in zip(labels, results):
            if isinstance(r, Exception):
                _log.warning("%s search failed: %s", label, r)
        _log.info(
            "vec=%d kw=%d dm=%d gr=%d",
            len(vec),
            len(kw),
            sum(len(r) for r in extra_sets),
            len(gr),
        )

        # Weighted RRF: keyword 3x (tech specs), graph 2x (entity-linked)
        result_sets = [vec, kw] + extra_sets + [gr]
        weights = [1.0, 3.0] + extra_weights + [2.0]
        fused = reciprocal_rank_fusion(result_sets, k=self._fusion_k, weights=weights)
        if is_dm_query:
            fused = _boost_device_model_candidates(query, fused)
        if message_terms:
            fused = _boost_message_candidates(query, message_terms, fused)
        top_fused_limit = max(
            60 if (is_dm_query or is_message_overview or is_fusion_query) else 30,
            self._final_top_k,
        )
        top_fused = fused[:top_fused_limit]

        if self._enable_rerank and not is_dm_overview and not is_message_overview:
            candidates = [c for c, _ in top_fused]
            final = self._reranker.rerank(query, candidates, top_k=self._final_top_k)
        else:
            final = [c for c, _ in top_fused[:self._final_top_k]]

        # Graph floor: ensure at least 1 entity-linked chunk if graph returned results
        if gr and not is_dm_query and not any(c.strategy == "graph" for c in final):
            best_gr = max(gr, key=lambda c: c.score)
            if final:
                final[-1] = best_gr
            else:
                final = [best_gr]

        if is_dm_query:
            final = _ensure_device_model_coverage(
                final,
                [c for c, _ in fused],
                self._final_top_k,
            )
        if is_fusion_query:
            final = _ensure_evidence_layer_coverage(
                query,
                final,
                [c for c, _ in fused],
                ("spec", "device_model", "schema"),
                self._final_top_k,
            )
            final = _ensure_ontology_graph_coverage(
                query,
                final,
                gr,
                ("spec", "device_model", "schema"),
                self._final_top_k,
            )
        if message_terms:
            final = _ensure_message_coverage(
                final,
                [c for c, _ in top_fused],
                message_terms,
                self._final_top_k,
            )
        ontology_metrics = _retrieval_ontology_metrics(gr, final)

        breakdown: dict[str, int] = {}
        for c in final:
            breakdown[c.strategy] = breakdown.get(c.strategy, 0) + 1

        result = RetrievalResult(
            chunks=final,
            strategy_breakdown=breakdown,
            latency_ms=int((time.monotonic() - t0) * 1000),
            ontology_metrics=ontology_metrics,
        )
        self._final_top_k = save_k
        return result

    async def search_only(
        self, query: str, *, filters: SearchFilters | None = None,
        top_k: int | None = None,
    ) -> RetrievalResult:
        """Retrieval without reranking (faster, for search-only endpoints)."""
        save_k = self._final_top_k
        if top_k is not None:
            self._final_top_k = top_k

        t0 = time.monotonic()
        pid = filters.protocol_id if filters else None
        dt = filters.doc_type if filters else None
        evidence_layer = filters.evidence_layer if filters else None
        source_type = filters.source_type if filters else None
        search_query = _expand_query(query)
        is_dm_query = _is_device_model_query(query)
        is_dm_overview = _is_device_model_overview_query(query)
        message_terms = _extract_message_terms(query)
        is_message_overview = _is_message_overview_query(query, message_terms)
        is_schema_query = _is_schema_query(query)
        is_fusion_query = _is_evidence_fusion_query(query)

        tasks = [
            asyncio.create_task(self._vector.search(
                search_query, top_k=self._vector_top_k, protocol_id=pid,
                doc_type=dt, evidence_layer=evidence_layer, source_type=source_type)),
            asyncio.create_task(self._keyword.search(
                search_query, top_k=self._keyword_top_k, protocol_id=pid,
                doc_type=dt, evidence_layer=evidence_layer, source_type=source_type)),
        ]
        extra_weights: list[float] = []
        if is_dm_query and evidence_layer is None:
            tasks.extend(
                [
                    asyncio.create_task(
                        self._keyword.search(
                            search_query,
                            top_k=self._keyword_top_k,
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer="device_model",
                        )
                    ),
                    asyncio.create_task(
                        self._keyword.search(
                            _DEVICE_MODEL_SPEC_QUERY,
                            top_k=max(10, self._keyword_top_k // 2),
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer="spec",
                        )
                    ),
                    asyncio.create_task(
                        self._vector.search(
                            search_query,
                            top_k=max(10, self._vector_top_k // 2),
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer="device_model",
                        )
                    ),
                ]
            )
            extra_weights.extend([4.0, 4.0, 2.0])
        if (is_schema_query or is_fusion_query) and evidence_layer is None:
            tasks.extend(
                [
                    asyncio.create_task(
                        self._keyword.search(
                            _schema_query(query),
                            top_k=max(12, self._keyword_top_k),
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer="schema",
                        )
                    ),
                    asyncio.create_task(
                        self._vector.search(
                            _schema_query(query),
                            top_k=max(10, self._vector_top_k // 2),
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer="schema",
                        )
                    ),
                ]
            )
            extra_weights.extend([5.0, 2.5])
        if is_fusion_query and evidence_layer is None:
            tasks.extend(
                [
                    asyncio.create_task(
                        self._keyword.search(
                            _topic_spec_query(query),
                            top_k=max(12, self._keyword_top_k),
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer="spec",
                        )
                    ),
                    asyncio.create_task(
                        self._keyword.search(
                            _topic_dm_query(query),
                            top_k=max(12, self._keyword_top_k),
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer="device_model",
                        )
                    )
                ]
            )
            extra_weights.extend([6.0, 6.0])
        if message_terms:
            for term in message_terms:
                tasks.append(
                    asyncio.create_task(
                        self._keyword.search(
                            _message_query(term),
                            top_k=max(12, self._keyword_top_k),
                            protocol_id=pid,
                            doc_type=dt,
                            evidence_layer=evidence_layer,
                            source_type=source_type,
                        )
                    )
                )
                extra_weights.append(5.0)
        use_graph = (
            self._enable_graph
            and not is_dm_overview
            and not is_message_overview
            and evidence_layer is None
            and source_type is None
        )
        if use_graph:
            tasks.append(asyncio.create_task(self._graph.search(
                _graph_query(query), top_k=self._graph_top_k, protocol_id=pid or 1,
                expand_via_traversal=True)))

        import logging
        _log = logging.getLogger(__name__)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        vec = _search_result(results[0])
        kw = _search_result(results[1])
        extra_start = 2
        extra_end = extra_start + len(extra_weights)
        extra_sets = [_search_result(r) for r in results[extra_start:extra_end]]
        graph_index = extra_end
        gr = _search_result(results[graph_index]) if len(results) > graph_index else []
        labels = ["vec", "kw"] + [f"dm{i + 1}" for i in range(len(extra_weights))]
        if use_graph:
            labels.append("gr")
        for label, r in zip(labels, results):
            if isinstance(r, Exception):
                _log.warning("%s search failed: %s", label, r)
        _log.info(
            "vec=%d kw=%d dm=%d gr=%d",
            len(vec),
            len(kw),
            sum(len(r) for r in extra_sets),
            len(gr),
        )

        fused = reciprocal_rank_fusion(
            [vec, kw] + extra_sets + [gr],
            k=self._fusion_k,
            weights=[1.0, 3.0] + extra_weights + [2.0],
        )
        if is_dm_query:
            fused = _boost_device_model_candidates(query, fused)
        if message_terms:
            fused = _boost_message_candidates(query, message_terms, fused)
        top = [c for c, _ in fused[:self._final_top_k]]
        if is_dm_query:
            top = _ensure_device_model_coverage(top, [c for c, _ in fused], self._final_top_k)
        if is_fusion_query:
            top = _ensure_evidence_layer_coverage(
                query,
                top,
                [c for c, _ in fused],
                ("spec", "device_model", "schema"),
                self._final_top_k,
            )
            top = _ensure_ontology_graph_coverage(
                query,
                top,
                gr,
                ("spec", "device_model", "schema"),
                self._final_top_k,
            )
        if message_terms:
            top = _ensure_message_coverage(
                top,
                [c for c, _ in fused],
                message_terms,
                self._final_top_k,
            )
        ontology_metrics = _retrieval_ontology_metrics(gr, top)
        self._final_top_k = save_k

        breakdown: dict[str, int] = {}
        for c in top:
            breakdown[c.strategy] = breakdown.get(c.strategy, 0) + 1

        return RetrievalResult(
            chunks=top,
            strategy_breakdown=breakdown,
            latency_ms=int((time.monotonic() - t0) * 1000),
            ontology_metrics=ontology_metrics,
        )


_DEVICE_MODEL_TERMS = (
    "device model",
    "dm",
    "component",
    "components",
    "variable",
    "variables",
    "variableattribute",
    "attribute",
    "attributes",
    "mutability",
)

_DEVICE_MODEL_EXPANSION = (
    "Device Model components variables variable attributes mutability persistence "
    "configuration monitoring reporting GetVariables SetVariables GetBaseReport "
    "GetCustomReport ReportBase ComponentVariable Referenced Components and Variables"
)

_DEVICE_MODEL_SPEC_QUERY = (
    "Device Model purpose components variables attributes CSMS retrieve report "
    "Get Variables Get Base Report Get Custom Report Referenced Components Variables "
    "Configuration Variables replace Configuration Keys"
)

_MESSAGE_OVERVIEW_TERMS = ("purpose", "what is", "overview", "explain", "role")

_SCHEMA_TERMS = (
    "schema",
    "json schema",
    "payload",
    "field",
    "fields",
    "properties",
    "validation",
    "request",
    "response",
)

_EVIDENCE_FUSION_TERMS = (
    "spec",
    "part 2",
    "device model",
    "components",
    "variables",
    "json schema",
    "schema validation",
)


def _is_device_model_query(query: str) -> bool:
    lowered = query.lower()
    return any(term in lowered for term in _DEVICE_MODEL_TERMS)


def _is_device_model_overview_query(query: str) -> bool:
    lowered = query.lower()
    return _is_device_model_query(query) and any(
        term in lowered for term in _MESSAGE_OVERVIEW_TERMS
    )


def _expand_query(query: str) -> str:
    if not _is_device_model_query(query):
        return query
    return f"{query} {_DEVICE_MODEL_EXPANSION}"


def _is_schema_query(query: str) -> bool:
    lowered = query.lower()
    return any(term in lowered for term in _SCHEMA_TERMS)


def _is_evidence_fusion_query(query: str) -> bool:
    lowered = query.lower()
    has_dm = "device model" in lowered or ("component" in lowered and "variable" in lowered)
    has_schema = "schema" in lowered or "json" in lowered or "validation" in lowered
    has_spec = "spec" in lowered or "part 2" in lowered or "section" in lowered
    if has_dm and has_schema and has_spec:
        return True
    return sum(term in lowered for term in _EVIDENCE_FUSION_TERMS) >= 3


def _schema_query(query: str) -> str:
    return (
        f"{query} JSON schema Request Response payload field properties required "
        "definitions enum validation constraints"
    )


def _topic_spec_query(query: str) -> str:
    lowered = query.lower()
    if "v2x" in lowered:
        return (
            "Q Bidirectional Power Transfer V2X energy services operation modes "
            "central V2X control dynamic CSMS setpoint frequency support load balancing "
            "generic smart charging rules for V2X"
        )
    if "smart charging" in lowered or "smartcharging" in lowered:
        return (
            "K Smart Charging related central smart charging ChargingProfile "
            "SetChargingProfile charging schedule limits profile purpose"
        )
    if "der" in lowered:
        return (
            "R DER Control related SetDERControl ReportDERControl NotifyDERStartStop "
            "DER control V2X session hybrid DER control setpoint curve"
        )
    return query


def _topic_dm_query(query: str) -> str:
    lowered = query.lower()
    if "v2x" in lowered:
        return (
            "V2XChargingCtrlr SupportedEnergyTransferModes SupportedOperationModes "
            "Enabled V2X Component Variable EVSE energy transfer services"
        )
    if "smart charging" in lowered or "smartcharging" in lowered:
        return (
            "SmartChargingCtrlr ChargingProfilePersistence SupportedAdditionalPurposes "
            "LimitChangeSignificance ProfileStackLevel Component Variable"
        )
    if "der" in lowered:
        return (
            "DCDERCtrlr ACDERCtrlr Enabled ModesSupported DER Component Variable "
            "control capabilities"
        )
    return query


def _graph_query(query: str) -> str:
    if not _is_evidence_fusion_query(query):
        return query
    return f"{query} {_topic_spec_query(query)} {_topic_dm_query(query)} {_schema_query(query)}"


def _extract_message_terms(query: str) -> list[str]:
    message_suffixes = (
        "Request|Response|Notification|Report|Event|Variables|Variable|"
        "Transaction|Certificate|Status"
    )
    candidates = re.findall(
        rf"\b[A-Z][A-Za-z0-9]*(?:{message_suffixes})\b",
        query,
    )
    terms: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        base = re.sub(r"(Request|Response)$", "", candidate)
        if base in seen:
            continue
        seen.add(base)
        terms.append(base)
    return terms[:3]


def _is_message_overview_query(query: str, message_terms: list[str]) -> bool:
    lowered = query.lower()
    return bool(message_terms) and any(term in lowered for term in _MESSAGE_OVERVIEW_TERMS)


def _message_query(message: str) -> str:
    return (
        f"{message} {message}Request {message}Response use case objective purpose "
        f"requirements sequence status interval precondition postcondition "
        f"implementation conformance test"
    )


def _boost_device_model_candidates(
    query: str, fused: list[tuple[ScoredChunk, float]]
) -> list[tuple[ScoredChunk, float]]:
    boosted = [(chunk, score + _device_model_boost(query, chunk)) for chunk, score in fused]
    return sorted(boosted, key=lambda item: item[1], reverse=True)


def _device_model_boost(query: str, chunk: ScoredChunk) -> float:
    metadata = chunk.metadata or {}
    layer = metadata.get("evidence_layer")
    title = (chunk.section_title or "").lower()
    content = chunk.content.lower()
    boost = 0.0
    if layer == "device_model":
        boost += 0.04
    if layer == "spec" and "referenced components and variables" in content:
        boost += 0.08
    if layer == "spec" and title.startswith(("b06", "b07", "b08")):
        boost += 0.07
    if "purpose" in query.lower() and "objective(s)" in content:
        boost += 0.05
    if "component" in content and "variable" in content:
        boost += 0.03
    return boost


def _boost_message_candidates(
    query: str,
    message_terms: list[str],
    fused: list[tuple[ScoredChunk, float]],
) -> list[tuple[ScoredChunk, float]]:
    boosted = [
        (chunk, score + _message_boost(query, message_terms, chunk))
        for chunk, score in fused
    ]
    return sorted(boosted, key=lambda item: item[1], reverse=True)


def _message_boost(query: str, message_terms: list[str], chunk: ScoredChunk) -> float:
    title = chunk.section_title or ""
    title_lower = title.lower()
    content_lower = chunk.content.lower()
    boost = 0.0
    for term in message_terms:
        term_lower = term.lower()
        if term_lower in title_lower:
            boost += 0.20
        if f"{term_lower}request" in content_lower or f"{term_lower}response" in content_lower:
            boost += 0.12
        if term_lower in content_lower:
            boost += 0.05
    if "objective(s)" in content_lower:
        boost += 0.08
    if "requirement definition" in content_lower:
        boost += 0.05
    if "messages, datatypes & enumerations" in content_lower:
        boost += 0.04
    if "table of contents" == title_lower:
        boost -= 0.50
    return boost


def _ensure_device_model_coverage(
    final: list[ScoredChunk],
    candidates: list[ScoredChunk],
    top_k: int,
) -> list[ScoredChunk]:
    final_by_id = {chunk.chunk_id for chunk in final}
    output = list(final)

    def has_layer(layer: str) -> bool:
        return any((chunk.metadata or {}).get("evidence_layer") == layer for chunk in output)

    def first_candidate(layer: str) -> ScoredChunk | None:
        for chunk in candidates:
            if chunk.chunk_id in final_by_id:
                continue
            if (chunk.metadata or {}).get("evidence_layer") == layer:
                return chunk
        return None

    for layer in ("spec", "device_model"):
        if has_layer(layer):
            continue
        candidate = first_candidate(layer)
        if candidate is None:
            continue
        if len(output) < top_k:
            output.append(candidate)
        else:
            output[-1] = candidate
        final_by_id.add(candidate.chunk_id)

    return output[:top_k]


def _coverage_replacement_position(
    chunks: list[ScoredChunk],
    required_layers: tuple[str, ...],
    coverage_terms: tuple[str, ...],
) -> int:
    required = set(required_layers)
    layer_counts: dict[str, int] = {}
    for chunk in chunks:
        layer = (chunk.metadata or {}).get("evidence_layer") or "unknown"
        layer_counts[layer] = layer_counts.get(layer, 0) + 1

    replaceable_positions = [
        index
        for index, chunk in enumerate(chunks)
        if (
            ((chunk.metadata or {}).get("evidence_layer") or "unknown") not in required
            or layer_counts[((chunk.metadata or {}).get("evidence_layer") or "unknown")] > 1
        )
    ]
    if not replaceable_positions:
        replaceable_positions = list(range(len(chunks)))
    return min(
        replaceable_positions,
        key=lambda index: _coverage_relevance_score(chunks[index], coverage_terms),
    )


def _ensure_evidence_layer_coverage(
    query: str,
    final: list[ScoredChunk],
    candidates: list[ScoredChunk],
    layers: tuple[str, ...],
    top_k: int,
) -> list[ScoredChunk]:
    output = list(final)
    final_by_id = {chunk.chunk_id for chunk in output}
    coverage_terms = _coverage_terms(query)

    def layer_positions(layer: str) -> list[int]:
        return [
            index
            for index, chunk in enumerate(output)
            if (chunk.metadata or {}).get("evidence_layer") == layer
        ]

    def first_candidate(layer: str) -> ScoredChunk | None:
        layer_candidates = []
        for chunk in candidates:
            if chunk.chunk_id in final_by_id:
                continue
            if (chunk.metadata or {}).get("evidence_layer") == layer:
                layer_candidates.append(chunk)
        if not layer_candidates:
            return None
        return max(
            layer_candidates,
            key=lambda chunk: _coverage_relevance_score(chunk, coverage_terms),
        )

    for layer in layers:
        positions = layer_positions(layer)
        candidate = first_candidate(layer)
        if positions:
            if candidate is None:
                continue
            weakest_position = min(
                positions,
                key=lambda index: _coverage_relevance_score(output[index], coverage_terms),
            )
            weakest_score = _coverage_relevance_score(output[weakest_position], coverage_terms)
            candidate_score = _coverage_relevance_score(candidate, coverage_terms)
            if candidate_score > weakest_score:
                final_by_id.discard(output[weakest_position].chunk_id)
                output[weakest_position] = candidate
                final_by_id.add(candidate.chunk_id)
            continue
        if candidate is None:
            continue
        if len(output) < top_k:
            output.append(candidate)
        else:
            replacement_position = _coverage_replacement_position(
                output,
                layers,
                coverage_terms,
            )
            final_by_id.discard(output[replacement_position].chunk_id)
            output[replacement_position] = candidate
        final_by_id.add(candidate.chunk_id)

    return output[:top_k]


def _ensure_ontology_graph_coverage(
    query: str,
    final: list[ScoredChunk],
    graph_candidates: list[ScoredChunk],
    required_layers: tuple[str, ...],
    top_k: int,
) -> list[ScoredChunk]:
    if not graph_candidates or any(_has_ontology_graph_evidence(chunk) for chunk in final):
        return final[:top_k]

    output = list(final[:top_k])
    final_by_id = {chunk.chunk_id for chunk in output}
    coverage_terms = _coverage_terms(query)
    candidates = [
        chunk
        for chunk in graph_candidates
        if chunk.chunk_id not in final_by_id
        and _has_ontology_graph_evidence(chunk)
        and _chunk_layer(chunk) in required_layers
    ]
    if not candidates:
        return output

    layer_counts = _layer_counts(output)
    ranked_candidates = sorted(
        candidates,
        key=lambda chunk: _ontology_graph_promotion_score(chunk, coverage_terms),
        reverse=True,
    )
    for candidate in ranked_candidates:
        candidate_layer = _chunk_layer(candidate)
        if len(output) < top_k:
            output.append(candidate)
            return output[:top_k]

        replacement_positions = [
            index
            for index, chunk in enumerate(output)
            if chunk.strategy != "graph"
            and _can_replace_without_losing_layer(
                chunk,
                candidate_layer,
                layer_counts,
                required_layers,
            )
        ]
        if not replacement_positions:
            continue
        replacement_position = min(
            replacement_positions,
            key=lambda index: _ontology_replacement_score(output[index], coverage_terms),
        )
        output[replacement_position] = candidate
        return output[:top_k]

    return output[:top_k]


def _has_ontology_graph_evidence(chunk: ScoredChunk) -> bool:
    metadata = chunk.metadata or {}
    return (
        chunk.strategy == "graph"
        and _positive_int(metadata.get("graph_semantic_links")) > 0
    )


def _layer_counts(chunks: list[ScoredChunk]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for chunk in chunks:
        layer = _chunk_layer(chunk)
        counts[layer] = counts.get(layer, 0) + 1
    return counts


def _chunk_layer(chunk: ScoredChunk) -> str:
    return str((chunk.metadata or {}).get("evidence_layer") or "unknown")


def _can_replace_without_losing_layer(
    chunk: ScoredChunk,
    candidate_layer: str,
    layer_counts: dict[str, int],
    required_layers: tuple[str, ...],
) -> bool:
    current_layer = _chunk_layer(chunk)
    if current_layer == candidate_layer:
        return True
    if current_layer not in required_layers:
        return True
    return layer_counts.get(current_layer, 0) > 1


def _ontology_graph_promotion_score(chunk: ScoredChunk, terms: tuple[str, ...]) -> float:
    metadata = chunk.metadata or {}
    semantic_links = min(_positive_int(metadata.get("graph_semantic_links")), 5)
    traversal_depth = _positive_int(metadata.get("graph_traversal_depth"))
    return (
        _coverage_relevance_score(chunk, terms)
        + (semantic_links * 0.75)
        - (traversal_depth * 0.25)
    )


def _ontology_replacement_score(chunk: ScoredChunk, terms: tuple[str, ...]) -> float:
    layer_bonus = 1.0 if _chunk_layer(chunk) in {"spec", "device_model", "schema"} else 0.0
    return _coverage_relevance_score(chunk, terms) + layer_bonus


def _coverage_terms(query: str) -> tuple[str, ...]:
    lowered = query.lower()
    terms: list[str] = []
    preferred = (
        "der",
        "v2x",
        "smartcharging",
        "smart charging",
        "chargingprofile",
        "setchargingprofile",
        "control",
        "energy",
        "services",
    )
    for term in preferred:
        if term in lowered:
            terms.append(term)
    for token in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", query):
        token_lower = token.lower()
        if token_lower in _STOP_QUERY_TERMS or token_lower in terms:
            continue
        terms.append(token_lower)
    return tuple(terms[:12])


_STOP_QUERY_TERMS = {
    "build",
    "senior",
    "backend",
    "implementation",
    "guidance",
    "ocpp",
    "ed2",
    "using",
    "part",
    "spec",
    "behavior",
    "device",
    "model",
    "components",
    "variables",
    "json",
    "schema",
    "validation",
}


def _coverage_relevance_score(chunk: ScoredChunk, terms: tuple[str, ...]) -> float:
    text = _coverage_text(chunk)
    title = (chunk.section_title or "").lower()
    score = 0.0
    for term in terms:
        if term in text:
            score += 1.0
        compact_term = term.replace(" ", "")
        if compact_term != term and compact_term in text.replace(" ", ""):
            score += 0.5
    for term in terms:
        if term in title:
            score += 1.5
    score += _topic_anchor_score(title, text, terms)
    score -= _off_topic_section_penalty(title, terms)
    return score


def _topic_anchor_score(title: str, text: str, terms: tuple[str, ...]) -> float:
    score = 0.0
    term_set = set(terms)
    if "v2x" in term_set:
        if title.startswith("q") or "bidirectional power transfer" in title:
            score += 4.0
        if "v2x" in title:
            score += 3.0
        if "v2xchargingctrlr" in text or "v2xchargingparameters" in text:
            score += 2.0
    if "smart charging" in term_set or "smartcharging" in term_set:
        if title.startswith("k") or "smart charging" in title:
            score += 4.0
        if "smartchargingctrlr" in text or "chargingprofile" in text:
            score += 2.0
    if "der" in term_set:
        if title.startswith("r") or "der control" in title:
            score += 4.0
        if "derctrlr" in text or "dercontrol" in text:
            score += 2.0
    return score


def _off_topic_section_penalty(title: str, terms: tuple[str, ...]) -> float:
    if "v2x" in terms and not (
        title.startswith("q")
        or "v2x" in title
        or "bidirectional power transfer" in title
    ):
        return 4.0
    if "v2x" in terms and "reservation" in title:
        return 3.0
    if "smart charging" in terms and "reservation" in title:
        return 2.0
    if "der" in terms and "reservation" in title:
        return 2.0
    return 0.0


def _coverage_text(chunk: ScoredChunk) -> str:
    metadata = chunk.metadata or {}
    metadata_text = " ".join(str(value) for value in metadata.values() if value is not None)
    return " ".join([chunk.content, chunk.section_title or "", metadata_text]).lower()


def _ensure_message_coverage(
    final: list[ScoredChunk],
    candidates: list[ScoredChunk],
    message_terms: list[str],
    top_k: int,
) -> list[ScoredChunk]:
    output = list(final)
    final_by_id = {chunk.chunk_id for chunk in output}

    def has_title_match() -> bool:
        return any(
            any(term.lower() in (chunk.section_title or "").lower() for term in message_terms)
            for chunk in output
        )

    def has_use_case_match() -> bool:
        return any(
            "objective(s)" in chunk.content.lower()
            and any(term.lower() in chunk.content.lower() for term in message_terms)
            for chunk in output
        )

    def append_or_replace(candidate: ScoredChunk) -> None:
        if candidate.chunk_id in final_by_id:
            return
        if len(output) < top_k:
            output.append(candidate)
        else:
            output[-1] = candidate
        final_by_id.add(candidate.chunk_id)

    if not has_use_case_match():
        for chunk in candidates:
            if (
                "objective(s)" in chunk.content.lower()
                and any(term.lower() in chunk.content.lower() for term in message_terms)
            ):
                append_or_replace(chunk)
                break

    if not has_title_match():
        for chunk in candidates:
            if any(term.lower() in (chunk.section_title or "").lower() for term in message_terms):
                append_or_replace(chunk)
                break

    return output[:top_k]


def _search_result(value: object) -> list[ScoredChunk]:
    if isinstance(value, BaseException):
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, ScoredChunk)]
    return []


def _retrieval_ontology_metrics(
    graph_candidates: list[ScoredChunk],
    final_chunks: list[ScoredChunk],
) -> dict[str, Any]:
    candidate = _graph_chunk_metrics(graph_candidates)
    final = _graph_chunk_metrics(final_chunks)
    return {
        "graph_candidate_chunks": candidate["graph_chunks"],
        "graph_candidate_chunks_with_semantic_links": candidate[
            "graph_chunks_with_semantic_links"
        ],
        "graph_candidate_semantic_links_total": candidate["semantic_links_total"],
        "graph_candidate_max_traversal_depth": candidate["max_traversal_depth"],
        "graph_candidate_ontology_relations": candidate["ontology_relations"],
        "graph_candidate_ontology_rules": candidate["ontology_rules"],
        "graph_candidate_ontology_versions": candidate["ontology_versions"],
        "final_graph_chunks": final["graph_chunks"],
        "final_graph_chunks_with_semantic_links": final["graph_chunks_with_semantic_links"],
        "final_semantic_links_total": final["semantic_links_total"],
        "final_max_traversal_depth": final["max_traversal_depth"],
        "final_ontology_relations": final["ontology_relations"],
        "final_ontology_rules": final["ontology_rules"],
        "final_ontology_versions": final["ontology_versions"],
    }


def _graph_chunk_metrics(chunks: list[ScoredChunk]) -> dict[str, Any]:
    graph_chunks = [chunk for chunk in chunks if chunk.strategy == "graph"]
    semantic_link_chunks = [
        chunk
        for chunk in graph_chunks
        if _positive_int((chunk.metadata or {}).get("graph_semantic_links")) > 0
    ]
    semantic_links_total = sum(
        _positive_int((chunk.metadata or {}).get("graph_semantic_links"))
        for chunk in graph_chunks
    )
    depths = [
        _positive_int((chunk.metadata or {}).get("graph_traversal_depth"))
        for chunk in graph_chunks
        if (chunk.metadata or {}).get("graph_traversal_depth") is not None
    ]
    return {
        "graph_chunks": len(graph_chunks),
        "graph_chunks_with_semantic_links": len(semantic_link_chunks),
        "semantic_links_total": semantic_links_total,
        "max_traversal_depth": max(depths, default=0),
        "ontology_relations": _sorted_metric_values(
            value
            for chunk in graph_chunks
            for value in _list_metric_values(
                (chunk.metadata or {}).get("graph_ontology_relations")
            )
        ),
        "ontology_rules": _sorted_metric_values(
            value
            for chunk in graph_chunks
            for value in _list_metric_values((chunk.metadata or {}).get("graph_ontology_rules"))
        ),
        "ontology_versions": _sorted_metric_values(
            value
            for chunk in graph_chunks
            for value in _list_metric_values(
                (chunk.metadata or {}).get("graph_ontology_versions")
            )
        ),
    }


def _positive_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _list_metric_values(value: Any) -> list[str]:
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value if item is not None and str(item)]
    if value is None or value == "":
        return []
    return [str(value)]


def _sorted_metric_values(values: Any) -> list[str]:
    return sorted(set(_list_metric_values(list(values))))
