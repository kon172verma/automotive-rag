from __future__ import annotations

# mypy: disable-error-code=import-not-found
import os
from time import perf_counter
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from psycopg import Connection, connect

from src.keyword_retrieval.service import keyword_search, resolve_doc_ids
from src.vector_retrieval.models import (
    DbConfig,
    EmbeddingConfig,
    RetrievalConfig,
    RetrievalLatency,
    RetrievalRequest,
    RerankerConfig,
    SearchBundle,
    SearchResult,
)
from src.vector_retrieval.reranking import rerank_results
from src.vector_retrieval.runtime import elapsed_ms
from src.vector_retrieval.vector_search import embed_query, fuse_results, vector_search


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

    def get_client(self) -> OpenAI:
        if self._client is not None:
            return self._client
        load_dotenv()
        if not os.getenv("OPENAI_API_KEY"):
            raise SystemExit("OPENAI_API_KEY is not set.")
        self._client = OpenAI()
        return self._client

    def get_reranker(self) -> Any:
        if self._reranker is not None:
            return self._reranker
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise SystemExit(
                "sentence-transformers is required for reranking. "
                "Install dependencies with '.venv/bin/pip install -r requirements.txt'."
            ) from exc
        self._reranker = CrossEncoder(self.reranker_config.model_name)
        return self._reranker

    def resolve_doc_ids(self, request: RetrievalRequest) -> list[str]:
        doc_ids, _ = resolve_doc_ids(self.conn, request)
        return doc_ids

    def keyword_search(
        self,
        *,
        request: RetrievalRequest,
        doc_ids: list[str],
    ) -> list[SearchResult]:
        results, _ = keyword_search(self.conn, self.retrieval_config, request, doc_ids)
        return results

    def vector_search(
        self,
        *,
        request: RetrievalRequest,
        doc_ids: list[str],
    ) -> list[SearchResult]:
        embedding, _, _ = embed_query(
            client=self.get_client(),
            question=request.question,
            config=self.embedding_config,
            query_cache=self._query_cache,
        )
        results, _ = vector_search(
            self.conn,
            self.retrieval_config,
            request,
            doc_ids,
            embedding,
        )
        return results

    def fuse(
        self,
        *,
        keyword_results: list[SearchResult],
        vector_results: list[SearchResult],
    ) -> list[SearchResult]:
        fused, _ = fuse_results(
            retrieval_config=self.retrieval_config,
            keyword_results=keyword_results,
            vector_results=vector_results,
        )
        return fused

    def rerank(
        self,
        *,
        request: RetrievalRequest,
        fused_results: list[SearchResult],
    ) -> list[SearchResult]:
        reranked, _ = rerank_results(
            reranker=self.get_reranker(),
            request=request,
            fused_results=fused_results,
            rerank_top_k=self.retrieval_config.rerank_top_k,
        )
        return reranked

    def keyword_only(self, request: RetrievalRequest) -> SearchBundle:
        started_at = perf_counter()
        doc_ids, doc_resolution_ms = resolve_doc_ids(self.conn, request)
        keyword_results, keyword_search_ms = keyword_search(
            self.conn,
            self.retrieval_config,
            request,
            doc_ids,
        )
        return SearchBundle(
            doc_ids=doc_ids,
            keyword_results=keyword_results,
            vector_results=[],
            fused_results=[],
            reranked_results=[],
            latency=RetrievalLatency(
                total_ms=elapsed_ms(started_at),
                doc_resolution_ms=doc_resolution_ms,
                keyword_search_ms=keyword_search_ms,
            ),
        )

    def vector_only(self, request: RetrievalRequest) -> SearchBundle:
        started_at = perf_counter()
        doc_ids, doc_resolution_ms = resolve_doc_ids(self.conn, request)
        embedding, query_embedding_ms, embedding_cache_hit = embed_query(
            client=self.get_client(),
            question=request.question,
            config=self.embedding_config,
            query_cache=self._query_cache,
        )
        vector_results, vector_search_ms = vector_search(
            self.conn,
            self.retrieval_config,
            request,
            doc_ids,
            embedding,
        )
        return SearchBundle(
            doc_ids=doc_ids,
            keyword_results=[],
            vector_results=vector_results,
            fused_results=[],
            reranked_results=[],
            latency=RetrievalLatency(
                total_ms=elapsed_ms(started_at),
                doc_resolution_ms=doc_resolution_ms,
                query_embedding_ms=query_embedding_ms,
                vector_search_ms=vector_search_ms,
                embedding_cache_hit=embedding_cache_hit,
            ),
        )

    def hybrid(self, request: RetrievalRequest) -> SearchBundle:
        started_at = perf_counter()
        doc_ids, doc_resolution_ms = resolve_doc_ids(self.conn, request)
        keyword_results, keyword_search_ms = keyword_search(
            self.conn,
            self.retrieval_config,
            request,
            doc_ids,
        )
        embedding, query_embedding_ms, embedding_cache_hit = embed_query(
            client=self.get_client(),
            question=request.question,
            config=self.embedding_config,
            query_cache=self._query_cache,
        )
        vector_results, vector_search_ms = vector_search(
            self.conn,
            self.retrieval_config,
            request,
            doc_ids,
            embedding,
        )
        fused_results, fusion_ms = fuse_results(
            retrieval_config=self.retrieval_config,
            keyword_results=keyword_results,
            vector_results=vector_results,
        )
        return SearchBundle(
            doc_ids=doc_ids,
            keyword_results=keyword_results,
            vector_results=vector_results,
            fused_results=fused_results,
            reranked_results=[],
            latency=RetrievalLatency(
                total_ms=elapsed_ms(started_at),
                doc_resolution_ms=doc_resolution_ms,
                keyword_search_ms=keyword_search_ms,
                query_embedding_ms=query_embedding_ms,
                vector_search_ms=vector_search_ms,
                fusion_ms=fusion_ms,
                embedding_cache_hit=embedding_cache_hit,
            ),
        )

    def hybrid_with_rerank(self, request: RetrievalRequest) -> SearchBundle:
        started_at = perf_counter()
        bundle = self.hybrid(request)
        reranked_results, rerank_ms = rerank_results(
            reranker=self.get_reranker(),
            request=request,
            fused_results=bundle.fused_results,
            rerank_top_k=self.retrieval_config.rerank_top_k,
        )
        return SearchBundle(
            doc_ids=bundle.doc_ids,
            keyword_results=bundle.keyword_results,
            vector_results=bundle.vector_results,
            fused_results=bundle.fused_results,
            reranked_results=reranked_results,
            latency=RetrievalLatency(
                total_ms=elapsed_ms(started_at),
                doc_resolution_ms=bundle.latency.doc_resolution_ms,
                keyword_search_ms=bundle.latency.keyword_search_ms,
                query_embedding_ms=bundle.latency.query_embedding_ms,
                vector_search_ms=bundle.latency.vector_search_ms,
                fusion_ms=bundle.latency.fusion_ms,
                rerank_ms=rerank_ms,
                embedding_cache_hit=bundle.latency.embedding_cache_hit,
            ),
        )
