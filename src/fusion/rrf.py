from __future__ import annotations

from time import perf_counter

from src.vector_retrieval.models import RetrievalConfig, SearchResult
from src.vector_retrieval.runtime import elapsed_ms


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
