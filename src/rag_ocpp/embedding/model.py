"""Embedding model — HuggingFace sentence-transformers loader and inference."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from rag_ocpp.config import EmbeddingConfig, get_config

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """HuggingFace embedding model wrapper.

    Primary: BAAI/bge-base-en-v1.5
      - Dimensions: 768
      - Parameters: 109M
      - Max sequence length: 512 tokens
      - MTEB Retrieval: ~53% (top-3 for size class)

    Critical BGE detail: asymmetric encoding.
      Documents embedded WITHOUT prefix.
      Queries embedded WITH:
        "Represent this sentence for searching relevant passages: "

    Usage:
        model = EmbeddingModel()
        doc_embeddings = model.embed_documents(["text1", "text2"])
        query_embedding = model.embed_query("What is Authorize.req?")
    """

    def __init__(
        self,
        config: EmbeddingConfig | None = None,
        *,
        model_name: str | None = None,
        device: str | None = None,
    ) -> None:
        if config is None:
            config = get_config().embedding

        self._config = config
        self._model_name = model_name or config.model_name
        self._device = device or config.device
        self._dims = config.dims
        self._normalize = config.normalize
        self._query_prefix = config.query_prefix
        self._batch_size = config.batch_size
        self._model: SentenceTransformer | None = None

    @property
    def dims(self) -> int:
        return self._dims

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def model_name(self) -> str:
        return self._model_name

    def load(self) -> None:
        """Load from HuggingFace Hub or local cache."""
        if self._model is not None:
            return

        logger.info("Loading embedding model: %s on %s", self._model_name, self._device)

        cache_path = self._local_model_path()
        load_from = str(cache_path) if cache_path else self._model_name

        try:
            self._model = SentenceTransformer(
                load_from, device=self._device,
                trust_remote_code=True, local_files_only=True,
            )
        except (OSError, FileNotFoundError):
            logger.info("Model not cached; downloading from HuggingFace...")
            self._model = SentenceTransformer(
                load_from, device=self._device,
                trust_remote_code=True,
            )

        _ = self._model.encode(["warmup"], normalize_embeddings=self._normalize)

        logger.info(
            "Embedding model loaded. dims=%d",
            self._model.get_sentence_embedding_dimension(),
        )

    def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            import gc
            gc.collect()
            try:
                import torch
                torch.cuda.empty_cache()
            except ImportError:
                pass

    def embed_documents(
        self,
        texts: list[str],
        *,
        batch_size: int | None = None,
        show_progress: bool = False,
    ) -> np.ndarray:
        """Embed document texts WITHOUT query prefix."""
        self._ensure_loaded()
        if not texts:
            return np.empty((0, self._dims), dtype=np.float32)

        return self._model.encode(
            texts,
            batch_size=batch_size or self._batch_size,
            normalize_embeddings=self._normalize,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
        )

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a query WITH prefix (BGE asymmetry)."""
        self._ensure_loaded()
        prefixed = self._query_prefix + query
        result = self._model.encode(
            [prefixed],
            normalize_embeddings=self._normalize,
            convert_to_numpy=True,
        )
        return result[0]

    def embed_queries(
        self, queries: list[str], *, batch_size: int | None = None
    ) -> np.ndarray:
        """Embed multiple queries with prefix."""
        self._ensure_loaded()
        prefixed = [self._query_prefix + q for q in queries]
        return self._model.encode(
            prefixed,
            batch_size=batch_size or self._batch_size,
            normalize_embeddings=self._normalize,
            convert_to_numpy=True,
        )

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b))

    def top_k(
        self, query: np.ndarray, docs: np.ndarray, k: int = 5
    ) -> list[tuple[int, float]]:
        scores = np.dot(docs, query)
        indices = np.argsort(scores)[::-1][:k]
        return [(int(i), float(scores[i])) for i in indices]

    def _ensure_loaded(self) -> None:
        if self._model is None:
            self.load()

    def _local_model_path(self) -> Path | None:
        import os
        hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
        model_dir = hf_home / "hub" / "models--BAAI--bge-base-en-v1.5"
        if model_dir.exists():
            snapshots = sorted(model_dir.glob("snapshots/*"))
            if snapshots:
                return snapshots[-1]
        return None
