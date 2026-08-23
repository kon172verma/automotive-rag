from __future__ import annotations

from time import perf_counter
from typing import Any

from openai import OpenAI
from psycopg import Connection

from src.vector_retrieval.models import (
    EmbeddingConfig,
    RetrievalConfig,
    RetrievalRequest,
    SearchResult,
)
from src.vector_retrieval.runtime import elapsed_ms, vector_literal


def embed_query(
    *,
    client: OpenAI,
    question: str,
    config: EmbeddingConfig,
    query_cache: dict[tuple[str, str, int], list[float]],
) -> tuple[list[float], float, bool]:
    started_at = perf_counter()
    cache_key = (question, config.model, config.dimensions)
    cached = query_cache.get(cache_key)
    if cached is not None:
        return cached, elapsed_ms(started_at), True
    response = client.embeddings.create(
        model=config.model,
        input=question,
        dimensions=config.dimensions,
    )
    vector = list(response.data[0].embedding)
    query_cache[cache_key] = vector
    return vector, elapsed_ms(started_at), False


def vector_search(
    conn: Connection[Any],
    retrieval_config: RetrievalConfig,
    request: RetrievalRequest,
    doc_ids: list[str],
    embedding: list[float],
) -> tuple[list[SearchResult], float]:
    started_at = perf_counter()
    query_vector = vector_literal(embedding)
    with conn.cursor() as cur:
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
                retrieval_config.vector_top_k,
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
    return results, elapsed_ms(started_at)


def fuse_results(
    *,
    retrieval_config: RetrievalConfig,
    keyword_results: list[SearchResult],
    vector_results: list[SearchResult],
) -> tuple[list[SearchResult], float]:
    started_at = perf_counter()
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
            fused_score += 1.0 / (retrieval_config.rrf_k + result.keyword_rank)
        if result.vector_rank is not None:
            fused_score += 1.0 / (retrieval_config.rrf_k + result.vector_rank)
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
    return fused[: retrieval_config.fused_top_k], elapsed_ms(started_at)
