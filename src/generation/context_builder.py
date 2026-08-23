from __future__ import annotations

from src.generation.context_models import (
    AnswerContext,
    AnswerContextRequest,
    EvidenceChunk,
)
from src.vector_retrieval.models import RetrievalRequest, SearchBundle, SearchResult


def format_page_label(
    page_start: int | None,
    page_end: int | None,
) -> str:
    if page_start is None and page_end is None:
        return "page unknown"
    if page_start == page_end:
        return f"page {page_start}"
    if page_start is None:
        return f"through page {page_end}"
    if page_end is None:
        return f"from page {page_start}"
    return f"pages {page_start}-{page_end}"


def build_citation_text(result: SearchResult) -> str:
    parts = [
        result.doc_id,
        f"section: {result.section_title}",
        format_page_label(result.page_start, result.page_end),
    ]
    if result.heading_path:
        parts.append(f"headings: {' > '.join(result.heading_path)}")
    parts.append(f"chunk: {result.chunk_id}")
    return " | ".join(parts)


def select_answer_results(
    bundle: SearchBundle,
    mode: str,
) -> tuple[str, list[SearchResult]]:
    if bundle.reranked_results:
        return "reranked", bundle.reranked_results
    if bundle.fused_results:
        return "fused", bundle.fused_results
    if mode == "vector" and bundle.vector_results:
        return "vector", bundle.vector_results
    if bundle.keyword_results:
        return "keyword", bundle.keyword_results
    if bundle.vector_results:
        return "vector", bundle.vector_results
    return "empty", []


def build_evidence_chunk(
    *,
    result: SearchResult,
    rank: int,
) -> EvidenceChunk:
    return EvidenceChunk(
        rank=rank,
        chunk_id=result.chunk_id,
        doc_id=result.doc_id,
        section_id=result.section_id,
        section_title=result.section_title,
        heading_path=list(result.heading_path),
        page_start=result.page_start,
        page_end=result.page_end,
        page_label=format_page_label(result.page_start, result.page_end),
        content_type=result.content_type,
        retrieval_source=result.retrieval_source,
        score=result.score,
        chunk_text=result.chunk_text,
        citation_text=build_citation_text(result),
    )


def render_evidence_block(evidence: EvidenceChunk) -> str:
    lines = [
        f"[Evidence {evidence.rank}] {evidence.citation_text}",
        f"Content type: {evidence.content_type}",
        evidence.chunk_text,
    ]
    return "\n".join(lines)


def build_context_text(evidence_chunks: list[EvidenceChunk]) -> str:
    if not evidence_chunks:
        return ""
    return "\n\n".join(render_evidence_block(chunk) for chunk in evidence_chunks)


def package_answer_context(
    *,
    request: RetrievalRequest,
    bundle: SearchBundle,
    mode: str,
    max_evidence_chunks: int | None = None,
) -> AnswerContext:
    selected_stage, results = select_answer_results(bundle, mode)
    if max_evidence_chunks is not None:
        results = results[:max_evidence_chunks]

    evidence = [
        build_evidence_chunk(result=result, rank=rank)
        for rank, result in enumerate(results, start=1)
    ]
    vehicle_label = f"{request.year} {request.make} {request.model}"
    return AnswerContext(
        request=AnswerContextRequest(
            question=request.question,
            make=request.make,
            model=request.model,
            year=request.year,
            vehicle_label=vehicle_label,
        ),
        retrieval_mode=mode,
        selected_stage=selected_stage,
        doc_ids=list(bundle.doc_ids),
        latency_ms=bundle.latency.to_dict(),
        evidence=evidence,
        context_text=build_context_text(evidence),
    )
