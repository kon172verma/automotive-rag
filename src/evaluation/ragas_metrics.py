from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

DEFAULT_RAGAS_EVALUATOR_MODEL = "gpt-4o-mini"
DEFAULT_RAGAS_EMBEDDING_MODEL = "text-embedding-3-small"

CITATION_QUALITY_PROMPT = """
Rate the citation quality of the response on a scale of 0-5.
0 = Missing citations or citations clearly do not support the response.
1 = Very weak support; citations are mostly irrelevant or too broad.
2 = Partial support; some cited evidence is helpful but important support is missing.
3 = Adequate support; citations are relevant but could be more specific or complete.
4 = Strong support; citations are relevant and mostly sufficient for the response.
5 = Excellent support; citations are specific, directly relevant, and sufficient.

Question: {user_input}
Reference Answer: {reference}
Response: {response}
Citations: {citations}
Retrieved Contexts: {retrieved_contexts_text}

Respond with only a number from 0 to 5.
""".strip()


@dataclass(frozen=True)
class RagasEvaluatorConfig:
    model_name: str = DEFAULT_RAGAS_EVALUATOR_MODEL
    embedding_model: str = DEFAULT_RAGAS_EMBEDDING_MODEL


@dataclass(frozen=True)
class RagasAnswerEvaluator:
    llm: Any
    factual_correctness: Any
    faithfulness: Any
    answer_relevancy: Any
    citation_quality: Any


def ensure_ragas_langchain_compatibility() -> None:
    if importlib.util.find_spec("langchain_community.chat_models.vertexai") is not None:
        return

    from langchain_community.llms import VertexAI

    shim = types.ModuleType("langchain_community.chat_models.vertexai")

    class ChatVertexAI(VertexAI):
        """Compatibility shim for ragas imports on OpenAI-only usage."""

    shim.__dict__["ChatVertexAI"] = ChatVertexAI
    sys.modules["langchain_community.chat_models.vertexai"] = shim


def build_ragas_answer_evaluator(
    *,
    client: OpenAI,
    config: RagasEvaluatorConfig,
) -> RagasAnswerEvaluator:
    ensure_ragas_langchain_compatibility()
    try:
        from ragas.embeddings import OpenAIEmbeddings
        from ragas.llms import llm_factory
        from ragas.metrics import DiscreteMetric
        from ragas.metrics.collections import (
            AnswerRelevancy,
            FactualCorrectness,
            Faithfulness,
        )
    except ImportError as exc:
        raise SystemExit(
            "ragas is required for answer evaluation. "
            "Install dependencies with '.venv/bin/pip install -r requirements.txt'."
        ) from exc

    llm = llm_factory(config.model_name, client=client)
    embeddings = OpenAIEmbeddings(client=client, model=config.embedding_model)
    return RagasAnswerEvaluator(
        llm=llm,
        factual_correctness=FactualCorrectness(llm=llm),
        faithfulness=Faithfulness(llm=llm),
        answer_relevancy=AnswerRelevancy(llm=llm, embeddings=embeddings),
        citation_quality=DiscreteMetric(
            name="citation_quality",
            allowed_values=["0", "1", "2", "3", "4", "5"],
            prompt=CITATION_QUALITY_PROMPT,
        ),
    )


def extract_metric_value(result: Any) -> float:
    value = getattr(result, "value", result)
    return float(str(value))


def evaluate_with_ragas(
    *,
    evaluator: RagasAnswerEvaluator,
    question: str,
    response: str,
    reference: str,
    retrieved_contexts: list[str],
    citations_text: str,
) -> tuple[dict[str, float | None], dict[str, str]]:
    scores: dict[str, float | None] = {
        "factual_correctness": None,
        "faithfulness": None,
        "answer_relevancy": None,
        "citation_quality": None,
    }
    errors: dict[str, str] = {}

    metric_calls = {
        "factual_correctness": lambda: evaluator.factual_correctness.score(
            response=response,
            reference=reference,
        ),
        "faithfulness": lambda: evaluator.faithfulness.score(
            user_input=question,
            response=response,
            retrieved_contexts=retrieved_contexts,
        ),
        "answer_relevancy": lambda: evaluator.answer_relevancy.score(
            user_input=question,
            response=response,
        ),
        "citation_quality": lambda: evaluator.citation_quality.score(
            user_input=question,
            response=response,
            reference=reference,
            citations=citations_text,
            retrieved_contexts_text="\n\n".join(retrieved_contexts),
            llm=evaluator.llm,
        ),
    }

    for metric_name, score_call in metric_calls.items():
        try:
            raw_value = extract_metric_value(score_call())
            if metric_name == "citation_quality":
                scores[metric_name] = round(raw_value / 5.0, 4)
            else:
                scores[metric_name] = round(raw_value, 4)
        except Exception as exc:  # noqa: BLE001
            errors[metric_name] = f"{type(exc).__name__}: {exc}"

    return scores, errors
