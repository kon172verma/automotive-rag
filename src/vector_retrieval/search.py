from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.generation.context_builder import package_answer_context
from src.vector_retrieval.models import (
    DEFAULT_RERANKER_SERVICE_URL,
    EmbeddingConfig,
    RerankerConfig,
    RetrievalConfig,
    RetrievalRequest,
    SearchBundle,
)
from src.vector_retrieval.retriever import Retriever
from src.vector_retrieval.runtime import build_db_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run keyword, vector, or hybrid retrieval for one question."
    )
    parser.add_argument("--question", type=str, required=True, help="User question.")
    parser.add_argument("--make", type=str, required=True, help="Vehicle make.")
    parser.add_argument("--model", type=str, required=True, help="Vehicle model.")
    parser.add_argument("--year", type=int, required=True, help="Vehicle year.")
    parser.add_argument(
        "--mode",
        choices=("keyword", "vector", "hybrid", "hybrid-rerank"),
        default="hybrid",
        help="Retrieval mode to run.",
    )
    parser.add_argument(
        "--keyword-top-k", type=int, default=20, help="Top-k for keyword retrieval."
    )
    parser.add_argument(
        "--vector-top-k", type=int, default=20, help="Top-k for vector retrieval."
    )
    parser.add_argument(
        "--fused-top-k", type=int, default=20, help="Top-k for fused retrieval output."
    )
    parser.add_argument(
        "--rrf-k",
        type=int,
        default=60,
        help="RRF denominator offset for hybrid fusion.",
    )
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
        "--package-answer-context",
        action="store_true",
        help="Include QA-ready answer context in the JSON output.",
    )
    parser.add_argument(
        "--max-evidence-chunks",
        type=int,
        default=None,
        help="Optional limit for packaged evidence chunks.",
    )
    return parser.parse_args()


def bundle_to_dict(bundle: SearchBundle) -> dict[str, Any]:
    return {
        "doc_ids": bundle.doc_ids,
        "keyword_results": [result.to_dict() for result in bundle.keyword_results],
        "vector_results": [result.to_dict() for result in bundle.vector_results],
        "fused_results": [result.to_dict() for result in bundle.fused_results],
        "reranked_results": [result.to_dict() for result in bundle.reranked_results],
        "latency_ms": bundle.latency.to_dict(),
    }


def main() -> None:
    args = parse_args()
    if args.max_evidence_chunks is not None and args.max_evidence_chunks <= 0:
        raise SystemExit("--max-evidence-chunks must be greater than 0")
    retrieval_config = RetrievalConfig(
        keyword_top_k=args.keyword_top_k,
        vector_top_k=args.vector_top_k,
        fused_top_k=args.fused_top_k,
        rerank_top_k=args.rerank_top_k,
        rrf_k=args.rrf_k,
    )
    request = RetrievalRequest(
        question=args.question,
        make=args.make,
        model=args.model,
        year=args.year,
    )
    with Retriever(
        db_config=build_db_config(),
        retrieval_config=retrieval_config,
        embedding_config=EmbeddingConfig(),
        reranker_config=RerankerConfig(
            model_name=args.reranker_model,
            service_url=args.reranker_url,
        ),
    ) as retriever:
        if args.mode == "keyword":
            bundle = retriever.keyword_only(request)
        elif args.mode == "vector":
            bundle = retriever.vector_only(request)
        elif args.mode == "hybrid-rerank":
            bundle = retriever.hybrid_with_rerank(request)
        else:
            bundle = retriever.hybrid(request)
    payload = bundle_to_dict(bundle)
    if args.package_answer_context:
        payload["answer_context"] = package_answer_context(
            request=request,
            bundle=bundle,
            mode=args.mode,
            max_evidence_chunks=args.max_evidence_chunks,
        ).to_dict()
    print(json.dumps(payload, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
