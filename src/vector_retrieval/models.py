from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

DEFAULT_DB_HOST = "127.0.0.1"
DEFAULT_DB_NAME = "automotive_rag"
DEFAULT_DB_PORT = 5432
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIMENSIONS = 1536
DEFAULT_KEYWORD_TOP_K = 20
DEFAULT_VECTOR_TOP_K = 20
DEFAULT_FUSED_TOP_K = 20
DEFAULT_RERANK_TOP_K = 10
DEFAULT_RRF_K = 60
DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    database: str
    user: str
    password: str


@dataclass(frozen=True)
class EmbeddingConfig:
    model: str = DEFAULT_EMBEDDING_MODEL
    dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS


@dataclass(frozen=True)
class RetrievalConfig:
    keyword_top_k: int = DEFAULT_KEYWORD_TOP_K
    vector_top_k: int = DEFAULT_VECTOR_TOP_K
    fused_top_k: int = DEFAULT_FUSED_TOP_K
    rerank_top_k: int = DEFAULT_RERANK_TOP_K
    rrf_k: int = DEFAULT_RRF_K


@dataclass(frozen=True)
class RerankerConfig:
    model_name: str = DEFAULT_RERANKER_MODEL


@dataclass(frozen=True)
class RetrievalRequest:
    question: str
    make: str
    model: str
    year: int


@dataclass
class SearchResult:
    chunk_id: str
    doc_id: str
    section_id: str
    section_title: str
    heading_path: list[str]
    page_start: int | None
    page_end: int | None
    chunk_text: str
    chunk_index: int
    content_type: str
    retrieval_source: str
    score: float
    keyword_rank: int | None = None
    keyword_score: float | None = None
    vector_rank: int | None = None
    vector_score: float | None = None
    fused_score: float | None = None
    rerank_rank: int | None = None
    rerank_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalLatency:
    total_ms: float
    doc_resolution_ms: float | None = None
    keyword_search_ms: float | None = None
    query_embedding_ms: float | None = None
    vector_search_ms: float | None = None
    fusion_ms: float | None = None
    rerank_ms: float | None = None
    embedding_cache_hit: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SearchBundle:
    doc_ids: list[str]
    keyword_results: list[SearchResult]
    vector_results: list[SearchResult]
    fused_results: list[SearchResult]
    reranked_results: list[SearchResult]
    latency: RetrievalLatency
