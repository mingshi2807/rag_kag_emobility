"""Entity and relationship extractor — two-pass: regex (free) + LLM DeepSeek (deep)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from rag_ocpp.config import get_config
from rag_ocpp.knowledge.entities import extract_pattern_matches

logger = logging.getLogger(__name__)


# ── Data types ────────────────────────────────────────────

@dataclass
class EntityMention:
    type_id: int
    name: str
    confidence: float = 1.0
    span_start: int | None = None
    span_end: int | None = None
    source: str = "regex"


@dataclass
class RelationMention:
    source_name: str
    source_type_id: int
    target_name: str
    target_type_id: int
    rel_type: str
    confidence: float = 0.8


@dataclass
class ExtractionResult:
    entities: list[EntityMention]
    relations: list[RelationMention]
    source: str


# ── LLM prompt ────────────────────────────────────────────

_EXTRACTION_SYSTEM_PROMPT = """You are an OCPP 2.1 protocol expert. Extract entities and relationships
from technical specification text.

Entity types: command, datatype, component, variable, enum, functional_block, error_code.
Relationships: uses, responds_to, requires, extends, belongs_to.

Return ONLY JSON:
{"entities":[{"type":"command","name":"Authorize"}],"relations":[{"source":"Authorize","source_type":"command","target":"IdToken","target_type":"datatype","relation":"uses"}]}"""


# ── Extractor ─────────────────────────────────────────────

class EntityExtractor:
    """Two-pass extraction: regex (free) + LLM (DeepSeek, batched, cached)."""

    def __init__(
        self,
        *,
        enable_llm: bool = True,
        cache: dict[str, ExtractionResult] | None = None,
    ) -> None:
        self._enable_llm = enable_llm
        self._cache: dict[str, ExtractionResult] = cache or {}

    # ── Pass 1: Regex ───────────────────────────────────

    def extract_regex(self, text: str) -> list[EntityMention]:
        """Regex-based extraction — synchronous, zero API cost."""
        matches = extract_pattern_matches(text)
        seen: set[tuple[int, str]] = set()
        entities: list[EntityMention] = []

        for m in matches:
            key = (m.entity_type.type_id, m.name)
            if key in seen:
                continue
            seen.add(key)
            entities.append(EntityMention(
                type_id=m.entity_type.type_id,
                name=m.name,
                confidence=1.0,
                span_start=m.span_start,
                span_end=m.span_end,
                source="regex",
            ))
        return entities

    # ── Pass 2: LLM ─────────────────────────────────────

    async def extract_llm(
        self, text: str
    ) -> tuple[list[EntityMention], list[RelationMention]]:
        """LLM-based extraction via DeepSeek API."""
        cfg = get_config()
        api_key = cfg.deepseek.api_key

        if not api_key:
            logger.warning("No DeepSeek API key; skipping LLM extraction")
            return [], []

        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{cfg.deepseek.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": cfg.deepseek.model,
                    "messages": [
                        {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": text[:8000]},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 2048,
                },
            )
            data = response.json()
            content = data["choices"][0]["message"]["content"]

        return self._parse_llm_response(content)

    # ── Full extraction ─────────────────────────────────

    async def extract(
        self,
        text: str,
        content_hash: str | None = None,
        *,
        force: bool = False,
    ) -> ExtractionResult:
        """Two-pass extraction with caching."""
        cache_key = content_hash or ""
        if cache_key and cache_key in self._cache and not force:
            return self._cache[cache_key]

        entities = self.extract_regex(text)
        relations: list[RelationMention] = []

        if self._enable_llm and self._needs_llm_pass(entities, text):
            try:
                llm_entities, llm_relations = await self.extract_llm(text)
                entities = self._merge_entities(entities, llm_entities)
                relations = llm_relations
            except Exception as exc:
                logger.warning("LLM extraction failed: %s", exc)

        result = ExtractionResult(
            entities=entities,
            relations=relations,
            source="regex+llm" if relations else "regex_only",
        )

        if cache_key:
            self._cache[cache_key] = result

        return result

    # ── Internal ────────────────────────────────────────

    def _needs_llm_pass(self, entities: list[EntityMention], text: str) -> bool:
        if len(entities) < 2 or len(text) < 100:
            return False
        return len({e.type_id for e in entities}) >= 2

    def _merge_entities(
        self,
        regex_entities: list[EntityMention],
        llm_entities: list[EntityMention],
    ) -> list[EntityMention]:
        seen = {(e.type_id, e.name) for e in regex_entities}
        merged = list(regex_entities)
        for e in llm_entities:
            if (e.type_id, e.name) not in seen:
                seen.add((e.type_id, e.name))
                e.source = "llm"
                merged.append(e)
        return merged

    def _parse_llm_response(
        self, content: str
    ) -> tuple[list[EntityMention], list[RelationMention]]:
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON: %.200s", content)
            return [], []

        type_map = {
            "command": 1, "datatype": 2, "component": 3,
            "variable": 4, "enum": 5, "message_flow": 6,
            "functional_block": 7, "error_code": 8, "test_case": 9,
        }

        entities = [
            EntityMention(
                type_id=type_map[e["type"].lower()],
                name=e["name"], confidence=0.8, source="llm",
            )
            for e in data.get("entities", [])
            if e.get("type", "").lower() in type_map and e.get("name")
        ]

        relations = [
            RelationMention(
                source_name=r["source"],
                source_type_id=type_map[r["source_type"].lower()],
                target_name=r["target"],
                target_type_id=type_map[r["target_type"].lower()],
                rel_type=r.get("relation", "uses"),
                confidence=0.7,
            )
            for r in data.get("relations", [])
            if r.get("source_type", "").lower() in type_map
            and r.get("target_type", "").lower() in type_map
            and r.get("source") and r.get("target")
        ]

        return entities, relations
