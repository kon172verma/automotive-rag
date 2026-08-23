from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.generation.answering import generate_answer
from src.generation.context_builder import package_answer_context
from src.generation.models import (
    DEFAULT_ANSWER_MODEL,
    DEFAULT_ANSWER_TEMPERATURE,
    DEFAULT_MAX_OUTPUT_TOKENS,
    GenerationConfig,
)
from src.vector_retrieval.models import (
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
        description="Run retrieval plus grounded answer generation for one question."
    )
    parser.add_argument("--question", type=str, required=True, help="User question.")
    parser.add_argument("--make", type=str, required=True, help="Vehicle make.")
    parser.add_argument("--model", type=str, required=True, help="Vehicle model.")
    parser.add_argument("--year", type=int, required=True, help="Vehicle year.")
    parser.add_argument(
        "--mode",
        choices=("keyword", "vector", "hybrid", "hybrid-rerank"),
        default="hybrid-rerank",
        help="Retrieval mode to run before answer generation.",
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
        help="Sentence Transformers cross-encoder model for reranking.",
    )
    parser.add_argument(
        "--answer-model",
        type=str,
        default=DEFAULT_ANSWER_MODEL,
        help="OpenAI model to use for answer generation.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_ANSWER_TEMPERATURE,
        help="Sampling temperature for answer generation.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
        help="Maximum answer-generation output tokens.",
    )
    parser.add_argument(
        "--max-evidence-chunks",
        type=int,
        default=5,
        help="Maximum evidence chunks to package for the answer model.",
    )
    parser.add_argument(
        "--include-answer-context",
        action="store_true",
        help="Include the packaged answer context in the JSON output.",
    )
    return parser.parse_args()


def run_retrieval_mode(
    retriever: Retriever,
    *,
    request: RetrievalRequest,
    mode: str,
) -> SearchBundle:
    if mode == "keyword":
        return retriever.keyword_only(request)
    if mode == "vector":
        return retriever.vector_only(request)
    if mode == "hybrid-rerank":
        return retriever.hybrid_with_rerank(request)
    return retriever.hybrid(request)


def build_payload(
    *,
    answer: dict[str, Any],
    answer_context: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = {"answer": answer}
    if answer_context is not None:
        payload["answer_context"] = answer_context
    return payload


def main() -> None:
    args = parse_args()
    if args.max_evidence_chunks <= 0:
        raise SystemExit("--max-evidence-chunks must be greater than 0")
    if args.max_output_tokens <= 0:
        raise SystemExit("--max-output-tokens must be greater than 0")
    if not 0.0 <= args.temperature <= 2.0:
        raise SystemExit("--temperature must be between 0.0 and 2.0")

    retrieval_config = RetrievalConfig(
        keyword_top_k=args.keyword_top_k,
        vector_top_k=args.vector_top_k,
        fused_top_k=args.fused_top_k,
        rerank_top_k=args.rerank_top_k,
        rrf_k=args.rrf_k,
    )
    generation_config = GenerationConfig(
        model_name=args.answer_model,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
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
        bundle = run_retrieval_mode(
            retriever,
            request=request,
            mode=args.mode,
        )
        answer_context = package_answer_context(
            request=request,
            bundle=bundle,
            mode=args.mode,
            max_evidence_chunks=args.max_evidence_chunks,
        )
        answer = generate_answer(
            answer_context,
            config=generation_config,
        )

    payload = build_payload(
        answer=answer.to_dict(),
        answer_context=answer_context.to_dict()
        if args.include_answer_context
        else None,
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
