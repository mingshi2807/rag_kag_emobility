"""DeepSeek Chat API client — streaming and non-streaming generation."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from rag_ocpp.config import DeepSeekConfig, get_config
from rag_ocpp.generation.prompt import render_generation_messages

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """Async DeepSeek Chat API client.

    Supports non-streaming and SSE streaming generation.

    Usage:
        client = DeepSeekClient()
        answer = await client.generate(query, chunks)
        async for token in client.generate_stream(query, chunks):
            print(token, end="")
    """

    def __init__(
        self,
        config: DeepSeekConfig | None = None,
        *,
        api_key: str | None = None, base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        if config is None:
            config = get_config().deepseek
        self._api_key = api_key or config.api_key
        self._base_url = (base_url or config.base_url).rstrip("/")
        self._model = model or config.model
        self._temperature = config.temperature
        self._max_tokens = config.max_tokens

    @property
    def chat_url(self) -> str:
        return f"{self._base_url}/chat/completions"

    @property
    def model(self) -> str:
        return self._model

    # ── Non-streaming ────────────────────────────────────

    async def generate(
        self, query: str, chunks: list[dict], *,
        temperature: float | None = None, max_tokens: int | None = None,
    ) -> str:
        """Generate answer from context (non-streaming)."""
        messages = render_generation_messages(query, chunks)
        return await self.generate_from_messages(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def generate_from_messages(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate answer from a pre-rendered Chat API message list."""
        self._check_api_key()
        logger.info("DeepSeek generation request: model=%s url=%s", self._model, self.chat_url)

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                self.chat_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": messages,
                    "temperature": temperature or self._temperature,
                    "max_tokens": max_tokens or self._max_tokens,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"]

    # ── Streaming (SSE) ──────────────────────────────────

    async def generate_stream(
        self, query: str, chunks: list[dict], *,
        temperature: float | None = None, max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream answer via Server-Sent Events."""
        self._check_api_key()
        messages = render_generation_messages(query, chunks, short=True)
        logger.info(
            "DeepSeek streaming generation request: model=%s url=%s",
            self._model,
            self.chat_url,
        )

        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST", self.chat_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": messages,
                    "temperature": temperature or self._temperature,
                    "max_tokens": max_tokens or self._max_tokens,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data_str)
                        choices = chunk_data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    # ── Utility ──────────────────────────────────────────

    def chunks_to_dicts(self, retrieval_result) -> list[dict]:
        """Convert retrieval ScoredChunks to prompt-friendly dicts."""
        return [
            {
                "content": c.content,
                "section_title": c.section_title or "Section",
                "document_title": (c.metadata or {}).get("source_path")
                or str(c.document_id)[:36],
                "page_start": c.page_start,
                "page_end": c.page_end,
                "evidence_layer": (c.metadata or {}).get("evidence_layer"),
                "source_type": (c.metadata or {}).get("source_type"),
            }
            for c in retrieval_result.chunks
        ]

    def _check_api_key(self) -> None:
        if not self._api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY not set. Set in .env or config/default.yaml."
            )
