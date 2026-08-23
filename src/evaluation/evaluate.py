from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.evaluation.latency_metrics import (
    finalize_latency_aggregate,
    hybrid_latency_without_rerank,
    update_latency_aggregate,
)
from src.evaluation.retrieval_metrics import (
    evaluate_stage,
    finalize_aggregate,
    normalize,
    parse_expected_pages,
    update_aggregate,
)
from src.retrieval.retriever import Retriever
from src.vector_retrieval.models import (
    DEFAULT_RERANKER_SERVICE_URL,
    EmbeddingConfig,
    RerankerConfig,
    RetrievalConfig,
    RetrievalRequest,
)
from src.vector_retrieval.runtime import build_db_config, load_json, write_json

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
        choices=("keyword", "vector", "hybrid", "hybrid-rerank", "all"),
        default="all",
        help="Which retrieval mode to evaluate.",
    )
    parser.add_argument(
        "--keyword-top-k", type=int, default=20, help="Top-k for keyword retrieval."
    )
    parser.add_argument(
        "--vector-top-k", type=int, default=20, help="Top-k for vector retrieval."
    )
    parser.add_argument(
        "--fused-top-k", type=int, default=20, help="Top-k for fused retrieval."
    )
    parser.add_argument("--rrf-k", type=int, default=60, help="RRF denominator offset.")
    parser.add_argument(
        "--rerank-top-k", type=int, default=10, help="Top-k to keep after reranking."
    )
    parser.add_argument(
        "--reranker-model",
        type=str,
        default="cross-encoder/ms-marco-MiniLM-L6-v2",
        help="Reranker model name expected by the reranker service.",
    )
    parser.add_argument(
        "--reranker-url",
        type=str,
        default=os.getenv("RERANKER_URL", DEFAULT_RERANKER_SERVICE_URL),
        help="Base URL for the host reranker service.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("artifacts/retrieval-reports"),
        help="Directory for evaluation reports.",
    )
    return parser.parse_args()


def evaluate_example(
    *,
    retriever: Retriever,
    example: dict[str, Any],
    mode: str,
    k_values: tuple[int, ...],
    aggregate: dict[str, Any],
    latency_aggregate: dict[str, Any],
) -> dict[str, Any]:
    latency_by_mode: dict[str, Any] = {}
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

    if mode in {"keyword", "all"}:
        bundle = retriever.keyword_only(request)
        doc_ids = bundle.doc_ids
        stages["keyword"] = evaluate_stage(
            bundle.keyword_results,
            expected_chunk_ids=expected_chunk_ids,
            expected_sections=expected_sections,
            expected_pages=expected_pages,
            k_values=k_values,
        )
        update_latency_aggregate(latency_aggregate, "keyword", bundle.latency.to_dict())
        latency_by_mode["keyword"] = bundle.latency.to_dict()
        update_aggregate(aggregate, "keyword", stages["keyword"], k_values)

    if mode in {"vector", "all"}:
        bundle = retriever.vector_only(request)
        doc_ids = bundle.doc_ids
        stages["vector"] = evaluate_stage(
            bundle.vector_results,
            expected_chunk_ids=expected_chunk_ids,
            expected_sections=expected_sections,
            expected_pages=expected_pages,
            k_values=k_values,
        )
        update_latency_aggregate(latency_aggregate, "vector", bundle.latency.to_dict())
        latency_by_mode["vector"] = bundle.latency.to_dict()
        update_aggregate(aggregate, "vector", stages["vector"], k_values)

    hybrid_bundle = None
    if mode in {"hybrid-rerank", "all"}:
        hybrid_bundle = retriever.hybrid_with_rerank(request)
    elif mode == "hybrid":
        hybrid_bundle = retriever.hybrid(request)

    if mode == "hybrid" and hybrid_bundle is not None:
        bundle = hybrid_bundle
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
            "retrieved_chunk_ids": [result.chunk_id for result in bundle.vector_results]
        }
        update_latency_aggregate(latency_aggregate, "hybrid", bundle.latency.to_dict())
        latency_by_mode["hybrid"] = bundle.latency.to_dict()
        update_aggregate(aggregate, "hybrid", stages["hybrid"], k_values)

    if mode in {"hybrid-rerank", "all"} and hybrid_bundle is not None:
        bundle = hybrid_bundle
        doc_ids = bundle.doc_ids
        hybrid_latency = hybrid_latency_without_rerank(bundle.latency.to_dict())
        stages["hybrid"] = evaluate_stage(
            bundle.fused_results,
            expected_chunk_ids=expected_chunk_ids,
            expected_sections=expected_sections,
            expected_pages=expected_pages,
            k_values=k_values,
        )
        stages["hybrid_rerank"] = evaluate_stage(
            bundle.reranked_results,
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
            "retrieved_chunk_ids": [result.chunk_id for result in bundle.vector_results]
        }
        stages["fused_candidates"] = {
            "retrieved_chunk_ids": [result.chunk_id for result in bundle.fused_results]
        }
        update_latency_aggregate(latency_aggregate, "hybrid", hybrid_latency)
        update_latency_aggregate(
            latency_aggregate,
            "hybrid_rerank",
            bundle.latency.to_dict(),
        )
        latency_by_mode["hybrid"] = hybrid_latency
        latency_by_mode["hybrid_rerank"] = bundle.latency.to_dict()
        update_aggregate(aggregate, "hybrid", stages["hybrid"], k_values)
        update_aggregate(aggregate, "hybrid_rerank", stages["hybrid_rerank"], k_values)

    return {
        "question_id": example["question_id"],
        "question": example["question"],
        "make": example["make"],
        "model": example["model"],
        "year": example["year"],
        "doc_ids": doc_ids,
        "expected_chunk_ids": sorted(expected_chunk_ids),
        "expected_sections": list(example.get("expected_sections", [])),
        "expected_pages": example.get("expected_pages", []),
        "latency_ms": latency_by_mode,
        "stages": stages,
    }


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
        rerank_top_k=args.rerank_top_k,
        rrf_k=args.rrf_k,
    )
    aggregate: dict[str, Any] = {}
    latency_aggregate: dict[str, Any] = {}
    per_question: list[dict[str, Any]] = []

    with Retriever(
        db_config=build_db_config(),
        retrieval_config=retrieval_config,
        embedding_config=EmbeddingConfig(),
        reranker_config=RerankerConfig(
            model_name=args.reranker_model,
            service_url=args.reranker_url,
        ),
    ) as retriever:
        for dataset_file in dataset_files:
            payload = load_json(dataset_file)
            for example in payload["examples"]:
                result = evaluate_example(
                    retriever=retriever,
                    example=example,
                    mode=args.mode,
                    k_values=DEFAULT_K_VALUES,
                    aggregate=aggregate,
                    latency_aggregate=latency_aggregate,
                )
                result["dataset_file"] = str(dataset_file)
                per_question.append(result)

    summary = {
        "dataset_files": [str(path) for path in dataset_files],
        "mode": args.mode,
        "retrieval_config": {
            "keyword_top_k": retrieval_config.keyword_top_k,
            "vector_top_k": retrieval_config.vector_top_k,
            "fused_top_k": retrieval_config.fused_top_k,
            "rerank_top_k": retrieval_config.rerank_top_k,
            "rrf_k": retrieval_config.rrf_k,
        },
        "reranker_config": {
            "model_name": args.reranker_model,
            "service_url": args.reranker_url,
        },
        "aggregate_metrics": finalize_aggregate(aggregate, DEFAULT_K_VALUES),
        "aggregate_latency_ms": finalize_latency_aggregate(latency_aggregate),
        "per_question": per_question,
    }
    report_path = args.report_dir / f"retrieval-eval-{args.mode}.json"
    write_json(report_path, summary)
    print(f"wrote report: {report_path}")

    for stage_name, metrics in summary["aggregate_metrics"].items():
        print(
            f"{stage_name}: "
            f"Recall@5={metrics['chunk_recall_at_k']['5']:.3f} "
            f"MRR={metrics['mrr']:.3f}"
        )
    for mode_name, latency in summary["aggregate_latency_ms"].items():
        total_metrics = latency["metrics"].get("total_ms")
        if total_metrics is None:
            continue
        print(
            f"{mode_name} latency: "
            f"p50={total_metrics['p50_ms']:.3f}ms "
            f"p95={total_metrics['p95_ms']:.3f}ms "
            f"avg={total_metrics['avg_ms']:.3f}ms"
        )


if __name__ == "__main__":
    main()
