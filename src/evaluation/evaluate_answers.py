from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter
from typing import Any

from src.evaluation.answer_eval_metrics import (
    evaluate_answer_metadata,
    finalize_answer_eval_aggregate,
    init_answer_eval_aggregate,
    summarize_numeric_values,
    update_answer_eval_aggregate,
)
from src.evaluation.ragas_metrics import (
    DEFAULT_RAGAS_EMBEDDING_MODEL,
    DEFAULT_RAGAS_EVALUATOR_MODEL,
    RagasEvaluatorConfig,
    build_ragas_answer_evaluator,
    evaluate_with_ragas,
)
from src.generation.answering import build_generation_client, generate_answer
from src.generation.context_builder import package_answer_context
from src.generation.models import (
    DEFAULT_ANSWER_MODEL,
    DEFAULT_ANSWER_TEMPERATURE,
    DEFAULT_MAX_OUTPUT_TOKENS,
    GenerationConfig,
)
from src.retrieval.retriever import Retriever
from src.vector_retrieval.models import (
    DEFAULT_RERANKER_SERVICE_URL,
    EmbeddingConfig,
    RerankerConfig,
    RetrievalConfig,
    RetrievalRequest,
    SearchBundle,
)
from src.vector_retrieval.runtime import build_db_config, load_json, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate final grounded answers on the curated eval dataset."
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
        choices=("keyword", "vector", "hybrid", "hybrid-rerank"),
        default="hybrid-rerank",
        help="Retrieval mode to use before answer generation.",
    )
    parser.add_argument("--keyword-top-k", type=int, default=20)
    parser.add_argument("--vector-top-k", type=int, default=20)
    parser.add_argument("--fused-top-k", type=int, default=20)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--rerank-top-k", type=int, default=10)
    parser.add_argument(
        "--reranker-model",
        type=str,
        default="cross-encoder/ms-marco-MiniLM-L6-v2",
    )
    parser.add_argument(
        "--reranker-url",
        type=str,
        default=DEFAULT_RERANKER_SERVICE_URL,
    )
    parser.add_argument(
        "--answer-model",
        type=str,
        default=DEFAULT_ANSWER_MODEL,
        help="OpenAI model used to generate answers.",
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
        "--judge-model",
        type=str,
        default=DEFAULT_RAGAS_EVALUATOR_MODEL,
        help="OpenAI model used by Ragas for answer evaluation.",
    )
    parser.add_argument(
        "--judge-embedding-model",
        type=str,
        default=DEFAULT_RAGAS_EMBEDDING_MODEL,
        help="Embedding model used by Ragas metrics that require embeddings.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("artifacts/answer-eval-reports"),
        help="Directory for answer evaluation reports.",
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


def format_citations_text(answer: dict[str, Any]) -> str:
    citations = answer.get("citations", [])
    if not citations:
        return "none"
    parts: list[str] = []
    for citation in citations:
        parts.append(
            " | ".join(
                [
                    str(citation["chunk_id"]),
                    str(citation["doc_id"]),
                    f"section: {citation['section_title']}",
                    f"pages: {citation['page_start']}-{citation['page_end']}",
                ]
            )
        )
    return "\n".join(parts)


def evaluate_example(
    *,
    retriever: Retriever,
    example: dict[str, Any],
    mode: str,
    generation_config: GenerationConfig,
    answer_client: Any,
    ragas_evaluator: Any,
    max_evidence_chunks: int,
) -> dict[str, Any]:
    started_at = perf_counter()
    request = RetrievalRequest(
        question=str(example["question"]),
        make=str(example["make"]),
        model=str(example["model"]),
        year=int(example["year"]),
    )
    bundle = run_retrieval_mode(retriever, request=request, mode=mode)
    answer_context = package_answer_context(
        request=request,
        bundle=bundle,
        mode=mode,
        max_evidence_chunks=max_evidence_chunks,
    )
    answer = generate_answer(
        answer_context,
        config=generation_config,
        client=answer_client,
    )
    answer_dict = answer.to_dict()
    structured_scores = evaluate_answer_metadata(answer=answer, example=example)
    ragas_scores, ragas_errors = evaluate_with_ragas(
        evaluator=ragas_evaluator,
        question=request.question,
        response=answer.answer,
        reference=str(example["reference_answer"]),
        retrieved_contexts=[chunk.chunk_text for chunk in answer_context.evidence],
        citations_text=format_citations_text(answer_dict),
    )
    retrieval_total_ms = float(answer_context.latency_ms.get("total_ms") or 0.0)
    generation_total_ms = float(answer.latency_ms.get("total_ms") or 0.0)
    return {
        "question_id": example["question_id"],
        "question": request.question,
        "make": request.make,
        "model": request.model,
        "year": request.year,
        "category": example.get("category"),
        "reference_answer": example["reference_answer"],
        "expected_answerability": example.get("answerability", "answerable"),
        "answer": answer_dict,
        "selected_stage": answer_context.selected_stage,
        "doc_ids": list(answer.doc_ids),
        "metrics": {
            "ragas": ragas_scores,
            "structured": structured_scores,
        },
        "metric_errors": ragas_errors,
        "latency_ms": {
            "retrieval_total_ms": round(retrieval_total_ms, 3),
            "generation_total_ms": round(generation_total_ms, 3),
            "end_to_end_ms": round(retrieval_total_ms + generation_total_ms, 3),
            "wall_clock_ms": round((perf_counter() - started_at) * 1000.0, 3),
        },
    }


def summarize_latency(per_question: list[dict[str, Any]]) -> dict[str, Any]:
    latency_keys = (
        "retrieval_total_ms",
        "generation_total_ms",
        "end_to_end_ms",
        "wall_clock_ms",
    )
    summary: dict[str, Any] = {}
    for key in latency_keys:
        values = [
            float(item["latency_ms"][key])
            for item in per_question
            if item["latency_ms"].get(key) is not None
        ]
        summary[key] = summarize_numeric_values(values)
    return summary


def main() -> None:
    args = parse_args()
    if args.max_evidence_chunks <= 0:
        raise SystemExit("--max-evidence-chunks must be greater than 0")
    if args.max_output_tokens <= 0:
        raise SystemExit("--max-output-tokens must be greater than 0")
    if not 0.0 <= args.temperature <= 2.0:
        raise SystemExit("--temperature must be between 0.0 and 2.0")

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
    generation_config = GenerationConfig(
        model_name=args.answer_model,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
    )
    answer_client = build_generation_client()
    ragas_evaluator = build_ragas_answer_evaluator(
        client=answer_client,
        config=RagasEvaluatorConfig(
            model_name=args.judge_model,
            embedding_model=args.judge_embedding_model,
        ),
    )
    aggregate = init_answer_eval_aggregate()
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
                    generation_config=generation_config,
                    answer_client=answer_client,
                    ragas_evaluator=ragas_evaluator,
                    max_evidence_chunks=args.max_evidence_chunks,
                )
                result["dataset_file"] = str(dataset_file)
                per_question.append(result)
                update_answer_eval_aggregate(
                    aggregate,
                    ragas_scores=result["metrics"]["ragas"],
                    structured_scores=result["metrics"]["structured"],
                )

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
        "generation_config": {
            "answer_model": args.answer_model,
            "temperature": args.temperature,
            "max_output_tokens": args.max_output_tokens,
            "max_evidence_chunks": args.max_evidence_chunks,
        },
        "ragas_config": {
            "judge_model": args.judge_model,
            "judge_embedding_model": args.judge_embedding_model,
        },
        "aggregate_metrics": finalize_answer_eval_aggregate(aggregate),
        "aggregate_latency_ms": summarize_latency(per_question),
        "per_question": per_question,
    }
    report_path = args.report_dir / f"answer-eval-{args.mode}.json"
    write_json(report_path, summary)
    print(f"wrote report: {report_path}")

    for metric_name, metrics in summary["aggregate_metrics"]["ragas"].items():
        if metrics is None:
            continue
        print(f"{metric_name}: avg={metrics['avg']:.4f}")
    answerability = summary["aggregate_metrics"]["structured"]["answerability_match"]
    if answerability["rate"] is not None:
        print(f"answerability_match: rate={answerability['rate']:.4f}")


if __name__ == "__main__":
    main()
