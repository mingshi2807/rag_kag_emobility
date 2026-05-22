"""Typed configuration loader using OmegaConf with env-var interpolation."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from omegaconf import OmegaConf


# ── Configuration dataclasses ────────────────────────────

@dataclass
class PostgresConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "rag_kag"
    user: str = "rag_kag"
    password: str = "rag_kag"
    min_connections: int = 4
    max_connections: int = 20

    @property
    def dsn(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


@dataclass
class DeepSeekConfig:
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    temperature: float = 0.1
    max_tokens: int = 4096


@dataclass
class EmbeddingConfig:
    model_name: str = "BAAI/bge-base-en-v1.5"
    device: str = "cuda"
    dims: int = 768
    batch_size: int = 32
    normalize: bool = True
    query_prefix: str = "Represent this sentence for searching relevant passages: "


@dataclass
class RerankerConfig:
    model_name: str = "BAAI/bge-reranker-base"
    device: str = "cuda"
    max_length: int = 512
    batch_size: int = 16


@dataclass
class ChunkingStrategy:
    strategy: str = "semantic"
    chunk_size: int = 512
    chunk_overlap: int = 64
    min_sentences_per_chunk: int = 3
    threshold: float = 0.5


@dataclass
class ChunkingConfig:
    spec: ChunkingStrategy = field(default_factory=lambda: ChunkingStrategy())
    test_suite: ChunkingStrategy = field(
        default_factory=lambda: ChunkingStrategy(strategy="sentence", chunk_size=256, chunk_overlap=32)
    )
    fallback: ChunkingStrategy = field(
        default_factory=lambda: ChunkingStrategy(strategy="recursive", chunk_size=1024, chunk_overlap=128)
    )


@dataclass
class RetrievalWeights:
    vector: float = 0.5
    keyword: float = 0.3
    graph: float = 0.2


@dataclass
class RetrievalConfig:
    vector_top_k: int = 20
    keyword_top_k: int = 10
    graph_top_k: int = 10
    fusion_k: int = 60
    final_top_k: int = 5
    weights: RetrievalWeights = field(default_factory=RetrievalWeights)


@dataclass
class LoggingConfig:
    level: str = "INFO"


@dataclass
class AppConfig:
    postgres: PostgresConfig = field(default_factory=PostgresConfig)
    deepseek: DeepSeekConfig = field(default_factory=DeepSeekConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    reranker: RerankerConfig = field(default_factory=RerankerConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


# ── Loader ───────────────────────────────────────────────

_config: AppConfig | None = None


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """
    Load configuration from YAML, merging defaults with overrides.

    Resolution order (higher priority overrides lower):
        1. config/default.yaml  (shipped defaults)
        2. config_path           (user-specified override)
        3. Environment variables (prefixed, e.g. PG_HOST, DEEPSEEK_API_KEY)
    """
    global _config

    base = Path(__file__).resolve().parent.parent.parent / "config" / "default.yaml"
    cfg = OmegaConf.load(base)

    if config_path:
        override = OmegaConf.load(config_path)
        cfg = OmegaConf.merge(cfg, override)

    # Struct-flag ensures no extra keys slip through
    OmegaConf.resolve(cfg)
    raw = OmegaConf.to_object(cfg)
    _config = _dict_to_dataclass(raw, AppConfig)
    return _config


def get_config() -> AppConfig:
    """Return the currently loaded configuration (call load_config first)."""
    if _config is None:
        return load_config()
    return _config


def _dict_to_dataclass(raw: dict, cls: type) -> object:
    """Recursively convert a dict (from OmegaConf) to nested dataclass instances."""
    kwargs = {}
    for field_name, field_def in cls.__dataclass_fields__.items():
        value = raw.get(field_name)
        if isinstance(value, dict) and hasattr(field_def.type, "__dataclass_fields__"):
            kwargs[field_name] = _dict_to_dataclass(value, field_def.type)
        else:
            kwargs[field_name] = value
    return cls(**kwargs)
