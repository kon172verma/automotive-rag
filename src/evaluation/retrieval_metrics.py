from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.vector_retrieval.models import SearchResult


def normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())


def parse_expected_pages(raw_pages: list[Any]) -> list[tuple[int, int]]:
    pages: list[tuple[int, int]] = []
    for raw_page in raw_pages:
        if isinstance(raw_page, int):
            pages.append((raw_page, raw_page))
            continue
        if isinstance(raw_page, dict):
            start = int(raw_page["start"])
            end = int(raw_page["end"])
            pages.append((start, end))
    return pages


def page_overlap(
    result: SearchResult,
    expected_pages: list[tuple[int, int]],
) -> bool:
    if result.page_start is None or result.page_end is None:
        return False
    for start, end in expected_pages:
        if max(result.page_start, start) <= min(result.page_end, end):
            return True
    return False


def section_match(result: SearchResult, expected_sections: set[str]) -> bool:
    if normalize(result.section_title) in expected_sections:
        return True
    return any(normalize(heading) in expected_sections for heading in result.heading_path)


def evaluate_stage(
    results: list[SearchResult],
    *,
    expected_chunk_ids: set[str],
    expected_sections: set[str],
    expected_pages: list[tuple[int, int]],
    k_values: tuple[int, ...],
) -> dict[str, Any]:
    chunk_rank: int | None = None
    section_rank: int | None = None
    page_rank: int | None = None

    for rank, result in enumerate(results, start=1):
        if chunk_rank is None and result.chunk_id in expected_chunk_ids:
            chunk_rank = rank
        if section_rank is None and section_match(result, expected_sections):
            section_rank = rank
        if page_rank is None and page_overlap(result, expected_pages):
            page_rank = rank

    return {
        "retrieved_chunk_ids": [result.chunk_id for result in results],
        "results": [result.to_dict() for result in results],
        "chunk_hit_rank": chunk_rank,
        "section_hit_rank": section_rank,
        "page_hit_rank": page_rank,
        "chunk_hits_at_k": {
            str(k): bool(chunk_rank is not None and chunk_rank <= k) for k in k_values
        },
        "section_hits_at_k": {
            str(k): bool(section_rank is not None and section_rank <= k) for k in k_values
        },
        "page_hits_at_k": {
            str(k): bool(page_rank is not None and page_rank <= k) for k in k_values
        },
        "mrr_contribution": 0.0 if chunk_rank is None else 1.0 / chunk_rank,
    }


def update_aggregate(
    aggregate: dict[str, Any],
    stage_name: str,
    stage_eval: dict[str, Any],
    k_values: tuple[int, ...],
) -> None:
    stage = aggregate.setdefault(
        stage_name,
        {
            "question_count": 0,
            "chunk_hits_at_k": defaultdict(int),
            "section_hits_at_k": defaultdict(int),
            "page_hits_at_k": defaultdict(int),
            "mrr_sum": 0.0,
        },
    )
    stage["question_count"] += 1
    stage["mrr_sum"] += stage_eval["mrr_contribution"]
    for k in k_values:
        k_str = str(k)
        if stage_eval["chunk_hits_at_k"][k_str]:
            stage["chunk_hits_at_k"][k_str] += 1
        if stage_eval["section_hits_at_k"][k_str]:
            stage["section_hits_at_k"][k_str] += 1
        if stage_eval["page_hits_at_k"][k_str]:
            stage["page_hits_at_k"][k_str] += 1


def finalize_aggregate(
    aggregate: dict[str, Any],
    k_values: tuple[int, ...],
) -> dict[str, Any]:
    finalized: dict[str, Any] = {}
    for stage_name, stage in aggregate.items():
        question_count = int(stage["question_count"])
        finalized[stage_name] = {
            "question_count": question_count,
            "chunk_recall_at_k": {
                str(k): (
                    0.0
                    if question_count == 0
                    else stage["chunk_hits_at_k"][str(k)] / question_count
                )
                for k in k_values
            },
            "section_hit_rate_at_k": {
                str(k): (
                    0.0
                    if question_count == 0
                    else stage["section_hits_at_k"][str(k)] / question_count
                )
                for k in k_values
            },
            "page_hit_rate_at_k": {
                str(k): (
                    0.0
                    if question_count == 0
                    else stage["page_hits_at_k"][str(k)] / question_count
                )
                for k in k_values
            },
            "mrr": 0.0 if question_count == 0 else stage["mrr_sum"] / question_count,
        }
    return finalized
