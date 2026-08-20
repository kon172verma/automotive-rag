from __future__ import annotations

# mypy: disable-error-code=import-not-found
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv  # type: ignore[import-not-found]
from openai import OpenAI
from psycopg import Connection, connect

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
class SearchBundle:
    doc_ids: list[str]
    keyword_results: list[SearchResult]
    vector_results: list[SearchResult]
    fused_results: list[SearchResult]
    reranked_results: list[SearchResult]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)
        handle.write("\n")


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


def normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def build_db_config() -> DbConfig:
    load_dotenv()
    user = os.getenv("POSTGRES_USER", "")
    password = os.getenv("POSTGRES_PASSWORD", "")
    if not user:
        raise SystemExit("POSTGRES_USER is not set.")
    if not password:
        raise SystemExit("POSTGRES_PASSWORD is not set.")
    return DbConfig(
        host=os.getenv("POSTGRES_HOST", DEFAULT_DB_HOST),
        port=int(os.getenv("POSTGRES_PORT", str(DEFAULT_DB_PORT))),
        database=os.getenv("POSTGRES_DB", DEFAULT_DB_NAME),
        user=user,
        password=password,
    )


class Retriever:
    def __init__(
        self,
        *,
        db_config: DbConfig,
        retrieval_config: RetrievalConfig,
        embedding_config: EmbeddingConfig,
        reranker_config: RerankerConfig,
    ) -> None:
        self.db_config = db_config
        self.retrieval_config = retrieval_config
        self.embedding_config = embedding_config
        self.reranker_config = reranker_config
        self._conn: Connection[Any] | None = None
        self._client: OpenAI | None = None
        self._reranker: Any | None = None
        self._query_cache: dict[tuple[str, str, int], list[float]] = {}

    def __enter__(self) -> Retriever:  # noqa: PYI034
        self._conn = connect(
            host=self.db_config.host,
            port=self.db_config.port,
            dbname=self.db_config.database,
            user=self.db_config.user,
            password=self.db_config.password,
        )
        return self

    def __exit__(self, *_: object) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> Connection[Any]:
        if self._conn is None:
            raise RuntimeError("Retriever is not connected.")
        return self._conn

    def resolve_doc_ids(self, request: RetrievalRequest) -> list[str]:
        make = normalize_text(request.make)
        model = normalize_text(request.model)
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT doc_id
                FROM documents
                WHERE make = %s
                  AND model = %s
                  AND year = %s
                ORDER BY doc_id
                """,
                (make, model, request.year),
            )
            rows = cur.fetchall()
        doc_ids = [str(row[0]) for row in rows]
        if not doc_ids:
            raise ValueError(
                f"No manuals found for make={request.make!r}, "
                f"model={request.model!r}, year={request.year}"
            )
        return doc_ids

    def keyword_search(
        self,
        *,
        request: RetrievalRequest,
        doc_ids: list[str],
    ) -> list[SearchResult]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  c.chunk_id,
                  c.doc_id,
                  c.section_id,
                  s.section_title,
                  c.heading_path,
                  c.page_start,
                  c.page_end,
                  c.chunk_text,
                  c.chunk_index,
                  c.content_type,
                  ts_rank_cd(
                    c.search_tsv,
                    websearch_to_tsquery('english', %s)
                  ) AS keyword_score
                FROM chunks AS c
                JOIN sections AS s
                  ON s.section_id = c.section_id
                WHERE c.doc_id = ANY(%s)
                  AND c.search_tsv @@ websearch_to_tsquery('english', %s)
                ORDER BY keyword_score DESC, c.chunk_index ASC
                LIMIT %s
                """,
                (
                    request.question,
                    doc_ids,
                    request.question,
                    self.retrieval_config.keyword_top_k,
                ),
            )
            rows = cur.fetchall()
        results: list[SearchResult] = []
        for rank, row in enumerate(rows, start=1):
            results.append(
                SearchResult(
                    chunk_id=str(row[0]),
                    doc_id=str(row[1]),
                    section_id=str(row[2]),
                    section_title=str(row[3]),
                    heading_path=list(row[4]),
                    page_start=row[5],
                    page_end=row[6],
                    chunk_text=str(row[7]),
                    chunk_index=int(row[8]),
                    content_type=str(row[9]),
                    retrieval_source="keyword",
                    score=float(row[10]),
                    keyword_rank=rank,
                    keyword_score=float(row[10]),
                )
            )
        return results

    def embed_query(self, question: str) -> list[float]:
        cache_key = (
            question,
            self.embedding_config.model,
            self.embedding_config.dimensions,
        )
        cached = self._query_cache.get(cache_key)
        if cached is not None:
            return cached
        if self._client is None:
            load_dotenv()
            if not os.getenv("OPENAI_API_KEY"):
                raise SystemExit("OPENAI_API_KEY is not set.")
            self._client = OpenAI()
        response = self._client.embeddings.create(
            model=self.embedding_config.model,
            input=question,
            dimensions=self.embedding_config.dimensions,
        )
        vector = list(response.data[0].embedding)
        self._query_cache[cache_key] = vector
        return vector

    def vector_search(
        self,
        *,
        request: RetrievalRequest,
        doc_ids: list[str],
    ) -> list[SearchResult]:
        query_vector = vector_literal(self.embed_query(request.question))
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  c.chunk_id,
                  c.doc_id,
                  c.section_id,
                  s.section_title,
                  c.heading_path,
                  c.page_start,
                  c.page_end,
                  c.chunk_text,
                  c.chunk_index,
                  c.content_type,
                  c.embedding <=> %s::vector AS distance
                FROM chunks AS c
                JOIN sections AS s
                  ON s.section_id = c.section_id
                WHERE c.doc_id = ANY(%s)
                ORDER BY distance ASC, c.chunk_index ASC
                LIMIT %s
                """,
                (
                    query_vector,
                    doc_ids,
                    self.retrieval_config.vector_top_k,
                ),
            )
            rows = cur.fetchall()
        results: list[SearchResult] = []
        for rank, row in enumerate(rows, start=1):
            distance = float(row[10])
            results.append(
                SearchResult(
                    chunk_id=str(row[0]),
                    doc_id=str(row[1]),
                    section_id=str(row[2]),
                    section_title=str(row[3]),
                    heading_path=list(row[4]),
                    page_start=row[5],
                    page_end=row[6],
                    chunk_text=str(row[7]),
                    chunk_index=int(row[8]),
                    content_type=str(row[9]),
                    retrieval_source="vector",
                    score=1.0 - distance,
                    vector_rank=rank,
                    vector_score=1.0 - distance,
                )
            )
        return results

    def fuse(
        self,
        *,
        keyword_results: list[SearchResult],
        vector_results: list[SearchResult],
    ) -> list[SearchResult]:
        combined: dict[str, SearchResult] = {}
        for result in keyword_results:
            combined[result.chunk_id] = SearchResult(**result.to_dict())
        for result in vector_results:
            existing = combined.get(result.chunk_id)
            if existing is None:
                combined[result.chunk_id] = SearchResult(**result.to_dict())
                continue
            existing.vector_rank = result.vector_rank
            existing.vector_score = result.vector_score

        for result in combined.values():
            fused_score = 0.0
            if result.keyword_rank is not None:
                fused_score += 1.0 / (self.retrieval_config.rrf_k + result.keyword_rank)
            if result.vector_rank is not None:
                fused_score += 1.0 / (self.retrieval_config.rrf_k + result.vector_rank)
            result.fused_score = fused_score
            result.retrieval_source = "fused"
            result.score = fused_score

        fused = sorted(
            combined.values(),
            key=lambda item: (
                -float(item.fused_score or 0.0),
                item.keyword_rank or 10**9,
                item.vector_rank or 10**9,
                item.chunk_index,
            ),
        )
        return fused[: self.retrieval_config.fused_top_k]

    def get_reranker(self) -> Any:
        if self._reranker is not None:
            return self._reranker
        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import-not-found]
        except ImportError as exc:
            raise SystemExit(
                "sentence-transformers is required for reranking. "
                "Install dependencies with '.venv/bin/pip install -r requirements.txt'."
            ) from exc
        self._reranker = CrossEncoder(self.reranker_config.model_name)
        return self._reranker

    def build_reranker_document(
        self,
        *,
        request: RetrievalRequest,
        result: SearchResult,
    ) -> str:
        heading_path = " > ".join(result.heading_path)
        vehicle = f"{request.year} {request.make} {request.model}"
        parts = [
            f"Vehicle: {vehicle}",
            f"Section: {result.section_title}",
            f"Headings: {heading_path}" if heading_path else "",
            f"Content type: {result.content_type}",
            f"Pages: {result.page_start}-{result.page_end}"
            if result.page_start is not None and result.page_end is not None
            else "",
            "",
            result.chunk_text,
        ]
        return "\n".join(part for part in parts if part)

    def rerank(
        self,
        *,
        request: RetrievalRequest,
        fused_results: list[SearchResult],
    ) -> list[SearchResult]:
        if not fused_results:
            return []
        reranker = self.get_reranker()
        pairs = [
            (request.question, self.build_reranker_document(request=request, result=result))
            for result in fused_results
        ]
        raw_scores = reranker.predict(pairs)
        reranked: list[SearchResult] = []
        for result, raw_score in zip(fused_results, raw_scores, strict=True):
            reranked_result = SearchResult(**result.to_dict())
            reranked_result.rerank_score = float(raw_score)
            reranked_result.retrieval_source = "reranked"
            reranked_result.score = reranked_result.rerank_score
            reranked.append(reranked_result)

        reranked.sort(
            key=lambda item: (
                -float(item.rerank_score or 0.0),
                -float(item.fused_score or 0.0),
                item.chunk_index,
            )
        )
        for rank, result in enumerate(reranked, start=1):
            result.rerank_rank = rank
        return reranked[: self.retrieval_config.rerank_top_k]

    def keyword_only(self, request: RetrievalRequest) -> SearchBundle:
        doc_ids = self.resolve_doc_ids(request)
        keyword_results = self.keyword_search(request=request, doc_ids=doc_ids)
        return SearchBundle(
            doc_ids=doc_ids,
            keyword_results=keyword_results,
            vector_results=[],
            fused_results=[],
            reranked_results=[],
        )

    def vector_only(self, request: RetrievalRequest) -> SearchBundle:
        doc_ids = self.resolve_doc_ids(request)
        vector_results = self.vector_search(request=request, doc_ids=doc_ids)
        return SearchBundle(
            doc_ids=doc_ids,
            keyword_results=[],
            vector_results=vector_results,
            fused_results=[],
            reranked_results=[],
        )

    def hybrid(self, request: RetrievalRequest) -> SearchBundle:
        doc_ids = self.resolve_doc_ids(request)
        keyword_results = self.keyword_search(request=request, doc_ids=doc_ids)
        vector_results = self.vector_search(request=request, doc_ids=doc_ids)
        fused_results = self.fuse(
            keyword_results=keyword_results,
            vector_results=vector_results,
        )
        return SearchBundle(
            doc_ids=doc_ids,
            keyword_results=keyword_results,
            vector_results=vector_results,
            fused_results=fused_results,
            reranked_results=[],
        )

    def hybrid_with_rerank(self, request: RetrievalRequest) -> SearchBundle:
        bundle = self.hybrid(request)
        reranked_results = self.rerank(
            request=request,
            fused_results=bundle.fused_results,
        )
        return SearchBundle(
            doc_ids=bundle.doc_ids,
            keyword_results=bundle.keyword_results,
            vector_results=bundle.vector_results,
            fused_results=bundle.fused_results,
            reranked_results=reranked_results,
        )
