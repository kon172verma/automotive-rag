from __future__ import annotations

from time import perf_counter
from typing import Any

from src.vector_retrieval.models import RetrievalRequest, SearchResult
from src.vector_retrieval.runtime import elapsed_ms


def build_reranker_document(
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
        (
            f"Pages: {result.page_start}-{result.page_end}"
            if result.page_start is not None and result.page_end is not None
            else ""
        ),
        "",
        result.chunk_text,
    ]
    return "\n".join(part for part in parts if part)


def rerank_results(
    *,
    reranker: Any,
    request: RetrievalRequest,
    fused_results: list[SearchResult],
    rerank_top_k: int,
) -> tuple[list[SearchResult], float]:
    started_at = perf_counter()
    if not fused_results:
        return [], elapsed_ms(started_at)
    pairs = [
        (
            request.question,
            build_reranker_document(request=request, result=result),
        )
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
    return reranked[:rerank_top_k], elapsed_ms(started_at)
