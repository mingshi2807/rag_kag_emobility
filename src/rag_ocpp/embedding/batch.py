"""Batch embedding — async backfill loop for chunks without embeddings."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import asyncpg
from tqdm import tqdm

from rag_ocpp.embedding.model import EmbeddingModel
from rag_ocpp.privacy import configure_redacted_logging
from rag_ocpp.storage.vector import VectorStore

logger = logging.getLogger(__name__)


class BatchEmbedder:
    """Asynchronous backfill: embed all chunks without vectors.

    Streams chunks from PostgreSQL, GPU inference, writes back.
    Checkpoint-safe: re-running picks up remaining NULL-embedding rows.

    Usage:
        embedder = BatchEmbedder(pool, model)
        total = await embedder.embed_all_pending(batch_size=256)
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        model: EmbeddingModel,
        vector_store: VectorStore | None = None,
    ) -> None:
        self._pool = pool
        self._model = model
        self._vector_store = vector_store or VectorStore(pool)
        self._model.load()

    async def embed_all_pending(
        self,
        *,
        batch_size: int = 256,
        show_progress: bool = True,
    ) -> int:
        """Embed all chunks that have NULL embedding vector.

        Args:
            batch_size:    Chunks per iteration.
            show_progress: Show tqdm progress bar.

        Returns:
            Total number of chunks embedded.
        """
        total_embedded = 0
        total_pending = await self._count_pending()

        if total_pending == 0:
            logger.info("No pending chunks to embed.")
            return 0

        logger.info(
            "Embedding %d pending chunks (batch_size=%d)...",
            total_pending, batch_size,
        )
        pbar = tqdm(
            total=total_pending, desc="Embedding chunks",
            disable=not show_progress,
        )

        while True:
            batch = await self._vector_store.get_pending_chunks(batch_size)
            if not batch:
                break

            chunk_ids, texts = zip(*batch) if batch else ([], [])

            embeddings = self._model.embed_documents(list(texts))

            updates = [
                (chunk_ids[i], embeddings[i].tolist())
                for i in range(len(chunk_ids))
            ]
            await self._vector_store.update_embeddings(updates)

            count = len(updates)
            total_embedded += count
            pbar.update(count)
            await asyncio.sleep(0)

        pbar.close()
        logger.info("Embedding complete: %d chunks embedded.", total_embedded)
        return total_embedded

    async def embed_batch(
        self, chunk_ids: list[UUID], texts: list[str]
    ) -> int:
        """Embed a specific batch of chunks (for real-time ingest)."""
        if not texts:
            return 0

        embeddings = self._model.embed_documents(texts)
        updates = [
            (chunk_ids[i], embeddings[i].tolist())
            for i in range(len(chunk_ids))
        ]
        await self._vector_store.update_embeddings(updates)
        return len(updates)

    async def _count_pending(self) -> int:
        row = await self._pool.fetchrow(
            "SELECT COUNT(*) FROM chunks WHERE embedding IS NULL"
        )
        return row["count"] if row else 0


# ── Standalone entry point ──────────────────────────────

async def _main() -> None:
    from rag_ocpp.config import get_config, load_config

    load_config()
    cfg = get_config()

    configure_redacted_logging(
        level=getattr(logging, cfg.logging.level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    pool = await asyncpg.create_pool(
        dsn=cfg.postgres.dsn,
        min_size=cfg.postgres.min_connections,
        max_size=cfg.postgres.max_connections,
    )
    assert pool is not None

    try:
        model = EmbeddingModel(cfg.embedding)
        vector_store = VectorStore(pool)
        embedder = BatchEmbedder(pool, model, vector_store)

        total = await embedder.embed_all_pending(show_progress=True)
        print(f"\nDone. {total} chunks embedded.")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(_main())
