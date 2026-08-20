from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.retrieval.common import (
    EmbeddingConfig,
    RerankerConfig,
    RetrievalConfig,
    RetrievalRequest,
    Retriever,
    SearchBundle,
    build_db_config,
)


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
        help="Top-k for fused retrieval output.",
    )
    parser.add_argument(
        "--rrf-k",
        type=int,
        default=60,
        help="RRF denominator offset for hybrid fusion.",
    )
    parser.add_argument(
        "--rerank-top-k",
        type=int,
        default=10,
        help="Top-k to keep after reranking.",
    )
    parser.add_argument(
        "--reranker-model",
        type=str,
        default="cross-encoder/ms-marco-MiniLM-L6-v2",
        help="Sentence Transformers cross-encoder model for reranking.",
    )
    return parser.parse_args()


def bundle_to_dict(bundle: SearchBundle) -> dict[str, Any]:
    return {
        "doc_ids": bundle.doc_ids,
        "keyword_results": [result.to_dict() for result in bundle.keyword_results],
        "vector_results": [result.to_dict() for result in bundle.vector_results],
        "fused_results": [result.to_dict() for result in bundle.fused_results],
        "reranked_results": [result.to_dict() for result in bundle.reranked_results],
    }


def main() -> None:
    args = parse_args()
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
        reranker_config=RerankerConfig(model_name=args.reranker_model),
    ) as retriever:
        if args.mode == "keyword":
            bundle = retriever.keyword_only(request)
        elif args.mode == "vector":
            bundle = retriever.vector_only(request)
        elif args.mode == "hybrid-rerank":
            bundle = retriever.hybrid_with_rerank(request)
        else:
            bundle = retriever.hybrid(request)
    print(json.dumps(bundle_to_dict(bundle), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
