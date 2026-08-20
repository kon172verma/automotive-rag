from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.retrieval.common import (
    EmbeddingConfig,
    RetrievalConfig,
    RetrievalRequest,
    Retriever,
    SearchResult,
    build_db_config,
    load_json,
    write_json,
)

DEFAULT_K_VALUES = (1, 3, 5, 10)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval quality on the curated eval dataset."
    )
    parser.add_argument(
        "--eval-dir",
        type=Path,
        default=Path("data/eval"),
        help="Directory containing eval dataset JSON files.",
    )
    parser.add_argument(
        "--match",
        type=str,
        default="*.json",
        help="Glob for selecting eval files, e.g. 'eval-v1-camry.json'.",
    )
    parser.add_argument(
        "--mode",
        choices=("keyword", "vector", "hybrid", "all"),
        default="all",
        help="Which retrieval mode to evaluate.",
    )
    parser.add_argument(
        "--keyword-top-k",
        type=int,
        default=20,
        help="Top-k for keyword retrieval.",
    )
    parser.add_argument(
        "--vector-top-k",
        type=int,
        default=20,
        help="Top-k for vector retrieval.",
    )
    parser.add_argument(
        "--fused-top-k",
        type=int,
        default=20,
        help="Top-k for fused retrieval.",
    )
    parser.add_argument(
        "--rrf-k",
        type=int,
        default=60,
        help="RRF denominator offset.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("artifacts/retrieval-reports"),
        help="Directory for evaluation reports.",
    )
    return parser.parse_args()


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


def main() -> None:
    args = parse_args()
    dataset_files = sorted(args.eval_dir.glob(args.match))
    if not dataset_files:
        raise SystemExit(f"No eval files found in {args.eval_dir}")

    args.report_dir.mkdir(parents=True, exist_ok=True)
    retrieval_config = RetrievalConfig(
        keyword_top_k=args.keyword_top_k,
        vector_top_k=args.vector_top_k,
        fused_top_k=args.fused_top_k,
        rrf_k=args.rrf_k,
    )
    aggregate: dict[str, Any] = {}
    per_question: list[dict[str, Any]] = []
    k_values = DEFAULT_K_VALUES

    with Retriever(
        db_config=build_db_config(),
        retrieval_config=retrieval_config,
        embedding_config=EmbeddingConfig(),
    ) as retriever:
        for dataset_file in dataset_files:
            payload = load_json(dataset_file)
            examples = payload["examples"]
            for example in examples:
                request = RetrievalRequest(
                    question=str(example["question"]),
                    make=str(example["make"]),
                    model=str(example["model"]),
                    year=int(example["year"]),
                )
                expected_chunk_ids = {
                    str(chunk_id) for chunk_id in example.get("expected_chunk_ids", [])
                }
                expected_sections = {
                    normalize(section)
                    for section in example.get("expected_sections", [])
                    if isinstance(section, str)
                }
                expected_pages = parse_expected_pages(example.get("expected_pages", []))

                stages: dict[str, Any] = {}
                doc_ids: list[str] = []

                if args.mode in {"keyword", "all"}:
                    bundle = retriever.keyword_only(request)
                    doc_ids = bundle.doc_ids
                    stages["keyword"] = evaluate_stage(
                        bundle.keyword_results,
                        expected_chunk_ids=expected_chunk_ids,
                        expected_sections=expected_sections,
                        expected_pages=expected_pages,
                        k_values=k_values,
                    )
                    update_aggregate(aggregate, "keyword", stages["keyword"], k_values)

                if args.mode in {"vector", "all"}:
                    bundle = retriever.vector_only(request)
                    doc_ids = bundle.doc_ids
                    stages["vector"] = evaluate_stage(
                        bundle.vector_results,
                        expected_chunk_ids=expected_chunk_ids,
                        expected_sections=expected_sections,
                        expected_pages=expected_pages,
                        k_values=k_values,
                    )
                    update_aggregate(aggregate, "vector", stages["vector"], k_values)

                if args.mode in {"hybrid", "all"}:
                    bundle = retriever.hybrid(request)
                    doc_ids = bundle.doc_ids
                    stages["hybrid"] = evaluate_stage(
                        bundle.fused_results,
                        expected_chunk_ids=expected_chunk_ids,
                        expected_sections=expected_sections,
                        expected_pages=expected_pages,
                        k_values=k_values,
                    )
                    stages["keyword_candidates"] = {
                        "retrieved_chunk_ids": [
                            result.chunk_id for result in bundle.keyword_results
                        ]
                    }
                    stages["vector_candidates"] = {
                        "retrieved_chunk_ids": [
                            result.chunk_id for result in bundle.vector_results
                        ]
                    }
                    update_aggregate(aggregate, "hybrid", stages["hybrid"], k_values)

                per_question.append(
                    {
                        "dataset_file": str(dataset_file),
                        "question_id": example["question_id"],
                        "question": example["question"],
                        "make": example["make"],
                        "model": example["model"],
                        "year": example["year"],
                        "doc_ids": doc_ids,
                        "expected_chunk_ids": sorted(expected_chunk_ids),
                        "expected_sections": list(example.get("expected_sections", [])),
                        "expected_pages": example.get("expected_pages", []),
                        "stages": stages,
                    }
                )

    summary = {
        "dataset_files": [str(path) for path in dataset_files],
        "mode": args.mode,
        "retrieval_config": {
            "keyword_top_k": retrieval_config.keyword_top_k,
            "vector_top_k": retrieval_config.vector_top_k,
            "fused_top_k": retrieval_config.fused_top_k,
            "rrf_k": retrieval_config.rrf_k,
        },
        "aggregate_metrics": finalize_aggregate(aggregate, k_values),
        "per_question": per_question,
    }
    report_name = f"retrieval-eval-{args.mode}.json"
    report_path = args.report_dir / report_name
    write_json(report_path, summary)
    print(f"wrote report: {report_path}")
    for stage_name, metrics in summary["aggregate_metrics"].items():
        print(
            f"{stage_name}: "
            f"Recall@5={metrics['chunk_recall_at_k']['5']:.3f} "
            f"MRR={metrics['mrr']:.3f}"
        )


if __name__ == "__main__":
    main()
