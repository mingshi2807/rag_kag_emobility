"""Cross-encoder reranker — BAAI/bge-reranker-base for precision-boosting top candidates."""

from __future__ import annotations

import logging

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from rag_ocpp.config import RerankerConfig, get_config
from rag_ocpp.retrieval.searchers import ScoredChunk

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Cross-encoder reranker — BAAI/bge-reranker-base.

    More accurate than embedding cosine: attends across query AND passage
    simultaneously. 270M params. ~10-20ms per pair on GPU.
    """

    def __init__(
        self, config: RerankerConfig | None = None,
        *, model_name: str | None = None, device: str | None = None,
    ) -> None:
        if config is None:
            config = get_config().reranker
        self._model_name = model_name or config.model_name
        self._device = device or config.device
        self._max_length = config.max_length
        self._batch_size = config.batch_size
        self._tokenizer: AutoTokenizer | None = None
        self._model: AutoModelForSequenceClassification | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self._model is not None:
            return
        logger.info("Loading reranker: %s on %s", self._model_name, self._device)
        self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(self._model_name)
        self._model.to(self._device)
        self._model.eval()
        logger.info("Reranker loaded.")

    def unload(self) -> None:
        if self._model:
            del self._model; del self._tokenizer
            self._model = None; self._tokenizer = None
            import gc; gc.collect()
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass

    @torch.no_grad()
    def rerank(
        self, query: str, candidates: list[ScoredChunk], *, top_k: int = 5,
    ) -> list[ScoredChunk]:
        if not candidates or len(candidates) <= top_k:
            return candidates

        self._ensure_loaded()
        pairs = [[query, c.content] for c in candidates]
        inputs = self._tokenizer(
            pairs, padding=True, truncation=True,
            max_length=self._max_length, return_tensors="pt",
        )
        inputs = {k: v.to(self._device) for k, v in inputs.items()}
        scores = self._model(**inputs).logits.squeeze(-1)
        top_indices = scores.argsort(descending=True)[:top_k].tolist()
        return [candidates[i] for i in top_indices]

    def _ensure_loaded(self) -> None:
        if self._model is None:
            self.load()
