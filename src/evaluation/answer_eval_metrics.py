from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.evaluation.latency_metrics import percentile
from src.evaluation.retrieval_metrics import normalize, parse_expected_pages
from src.generation.models import GeneratedAnswer

BOOL_KEYS = (
    "answerability_match",
    "has_citations",
    "citation_chunk_hit",
    "citation_section_hit",
    "citation_page_hit",
    "used_chunk_hit",
    "abstention_correct",
)


def page_span_overlap(
    *,
    page_start: int | None,
    page_end: int | None,
    expected_pages: list[tuple[int, int]],
) -> bool:
    if page_start is None or page_end is None:
        return False
    for start, end in expected_pages:
        if max(page_start, start) <= min(page_end, end):
            return True
    return False


def evaluate_answer_metadata(
    *,
    answer: GeneratedAnswer,
    example: dict[str, Any],
) -> dict[str, Any]:
    expected_answerability = str(example.get("answerability", "answerable"))
    expected_chunk_ids = {
        str(chunk_id) for chunk_id in example.get("expected_chunk_ids", [])
    }
    expected_sections = {
        normalize(section)
        for section in example.get("expected_sections", [])
        if isinstance(section, str)
    }
    expected_pages = parse_expected_pages(example.get("expected_pages", []))

    has_citations = bool(answer.citations)
    citation_chunk_hit = any(
        citation.chunk_id in expected_chunk_ids for citation in answer.citations
    )
    citation_section_hit = any(
        normalize(citation.section_title) in expected_sections
        for citation in answer.citations
    )
    citation_page_hit = any(
        page_span_overlap(
            page_start=citation.page_start,
            page_end=citation.page_end,
            expected_pages=expected_pages,
        )
        for citation in answer.citations
    )
    used_chunk_hit = any(
        chunk_id in expected_chunk_ids for chunk_id in answer.used_chunk_ids
    )

    should_abstain = expected_answerability != "answerable"
    abstention_correct: bool | None = None
    if should_abstain:
        abstention_correct = answer.answerability == expected_answerability

    return {
        "expected_answerability": expected_answerability,
        "answerability_match": answer.answerability == expected_answerability,
        "has_citations": has_citations,
        "citation_chunk_hit": citation_chunk_hit,
        "citation_section_hit": citation_section_hit,
        "citation_page_hit": citation_page_hit,
        "used_chunk_hit": used_chunk_hit,
        "citation_count": len(answer.citations),
        "abstention_correct": abstention_correct,
        "insufficient_evidence_case": should_abstain,
    }


def init_answer_eval_aggregate() -> dict[str, Any]:
    return {
        "ragas": defaultdict(list),
        "structured": {
            key: {"true_count": 0, "sample_count": 0} for key in BOOL_KEYS
        },
        "citation_count": [],
        "insufficient_evidence_case_count": 0,
    }


def update_answer_eval_aggregate(
    aggregate: dict[str, Any],
    *,
    ragas_scores: dict[str, float | None],
    structured_scores: dict[str, Any],
) -> None:
    for key, value in ragas_scores.items():
        if value is not None:
            aggregate["ragas"][key].append(float(value))

    for key in BOOL_KEYS:
        value = structured_scores.get(key)
        if value is None:
            continue
        aggregate["structured"][key]["sample_count"] += 1
        if bool(value):
            aggregate["structured"][key]["true_count"] += 1

    aggregate["citation_count"].append(int(structured_scores["citation_count"]))
    if structured_scores["insufficient_evidence_case"]:
        aggregate["insufficient_evidence_case_count"] += 1


def summarize_numeric_values(values: list[float]) -> dict[str, Any] | None:
    if not values:
        return None
    return {
        "sample_count": len(values),
        "avg": round(sum(values) / len(values), 4),
        "p50": round(percentile(values, 0.50) or 0.0, 4),
        "p95": round(percentile(values, 0.95) or 0.0, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def finalize_answer_eval_aggregate(aggregate: dict[str, Any]) -> dict[str, Any]:
    ragas_summary = {
        key: summarize_numeric_values(list(values))
        for key, values in aggregate["ragas"].items()
    }
    structured_summary = {}
    for key, counts in aggregate["structured"].items():
        sample_count = int(counts["sample_count"])
        structured_summary[key] = {
            "sample_count": sample_count,
            "rate": (
                None
                if sample_count == 0
                else round(counts["true_count"] / sample_count, 4)
            ),
        }
    return {
        "ragas": ragas_summary,
        "structured": structured_summary,
        "citation_count": summarize_numeric_values(
            [float(value) for value in aggregate["citation_count"]]
        ),
        "insufficient_evidence_case_count": int(
            aggregate["insufficient_evidence_case_count"]
        ),
    }
