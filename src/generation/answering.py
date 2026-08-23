from __future__ import annotations

import json
import os
from time import perf_counter
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from src.generation.context_models import AnswerContext, EvidenceChunk
from src.generation.models import (
    GeneratedAnswer,
    GeneratedCitation,
    GeneratedVehicle,
    GenerationConfig,
    ModelAnswerDraft,
    ModelAnswerDraftPayload,
)
from src.generation.prompting import build_system_prompt, build_user_prompt
from src.vector_retrieval.runtime import elapsed_ms

ALLOWED_ANSWERABILITY = {"answerable", "insufficient_evidence", "not_in_manual"}
ALLOWED_CONFIDENCE = {"low", "medium", "high"}


def build_generation_client() -> OpenAI:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=api_key)


def extract_response_text(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if not choices:
        raise ValueError("OpenAI response did not include any choices.")
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip()
    raise ValueError("OpenAI response content was not a text string.")


def extract_parsed_payload(response: Any) -> dict[str, Any] | None:
    choices = getattr(response, "choices", None)
    if not choices:
        return None
    message = getattr(choices[0], "message", None)
    if message is None:
        return None
    parsed = getattr(message, "parsed", None)
    if parsed is None:
        return None
    if hasattr(parsed, "model_dump"):
        return parsed.model_dump()
    if isinstance(parsed, dict):
        return parsed
    raise TypeError("Parsed model output was not an object.")


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            raise
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise TypeError("Model output was not a JSON object.")
    return payload


def normalize_string_list(raw_value: Any) -> list[str]:
    if not isinstance(raw_value, list):
        return []
    values: list[str] = []
    seen: set[str] = set()
    for item in raw_value:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def parse_draft(payload: dict[str, Any]) -> ModelAnswerDraft:
    answerability = str(payload.get("answerability", "")).strip().lower()
    if answerability not in ALLOWED_ANSWERABILITY:
        answerability = "insufficient_evidence"

    answer = str(payload.get("answer", "")).strip()
    confidence = str(payload.get("confidence", "")).strip().lower()
    if confidence not in ALLOWED_CONFIDENCE:
        confidence = "low"

    notes = str(payload.get("notes", "")).strip()
    return ModelAnswerDraft(
        answerability=answerability,
        answer=answer,
        confidence=confidence,
        citation_chunk_ids=normalize_string_list(payload.get("citation_chunk_ids")),
        used_chunk_ids=normalize_string_list(payload.get("used_chunk_ids")),
        notes=notes,
    )


def evidence_lookup(context: AnswerContext) -> dict[str, EvidenceChunk]:
    return {chunk.chunk_id: chunk for chunk in context.evidence}


def resolve_chunk_ids(
    raw_chunk_ids: list[str],
    *,
    available: dict[str, EvidenceChunk],
) -> list[str]:
    return [chunk_id for chunk_id in raw_chunk_ids if chunk_id in available]


def build_generated_citations(
    chunk_ids: list[str],
    *,
    available: dict[str, EvidenceChunk],
) -> list[GeneratedCitation]:
    citations: list[GeneratedCitation] = []
    for chunk_id in chunk_ids:
        evidence = available[chunk_id]
        citations.append(
            GeneratedCitation(
                chunk_id=evidence.chunk_id,
                doc_id=evidence.doc_id,
                section_title=evidence.section_title,
                page_start=evidence.page_start,
                page_end=evidence.page_end,
                citation_text=evidence.citation_text,
            )
        )
    return citations


def abstention_answer(
    *,
    context: AnswerContext,
    config: GenerationConfig,
    notes: str,
) -> GeneratedAnswer:
    return GeneratedAnswer(
        question=context.request.question,
        vehicle=GeneratedVehicle(
            make=context.request.make,
            model=context.request.model,
            year=context.request.year,
        ),
        answerability="insufficient_evidence",
        answer="I could not find enough evidence in the manual to answer this question confidently.",
        confidence="low",
        citations=[],
        used_chunk_ids=[],
        notes=notes,
        doc_ids=list(context.doc_ids),
        model_name=config.model_name,
        prompt_version=config.prompt_version,
        retrieval_mode=context.retrieval_mode,
        selected_stage=context.selected_stage,
        latency_ms={"generation_ms": 0.0, "total_ms": 0.0},
    )


def finalize_answer(
    *,
    context: AnswerContext,
    config: GenerationConfig,
    draft: ModelAnswerDraft,
    generation_ms: float,
) -> GeneratedAnswer:
    available = evidence_lookup(context)
    citation_chunk_ids = resolve_chunk_ids(draft.citation_chunk_ids, available=available)
    used_chunk_ids = resolve_chunk_ids(draft.used_chunk_ids, available=available)
    if not used_chunk_ids:
        used_chunk_ids = list(citation_chunk_ids)

    answerability = draft.answerability
    confidence = draft.confidence
    notes = draft.notes
    answer = draft.answer

    if answerability == "answerable" and not citation_chunk_ids:
        answerability = "insufficient_evidence"
        confidence = "low"
        notes = "Model did not return valid citations from the provided evidence."
        answer = (
            "I could not find enough evidence in the manual to answer this question "
            "confidently."
        )

    if not answer:
        answer = (
            "I could not find enough evidence in the manual to answer this question "
            "confidently."
        )
        if answerability == "answerable":
            answerability = "insufficient_evidence"
            confidence = "low"

    return GeneratedAnswer(
        question=context.request.question,
        vehicle=GeneratedVehicle(
            make=context.request.make,
            model=context.request.model,
            year=context.request.year,
        ),
        answerability=answerability,
        answer=answer,
        confidence=confidence,
        citations=build_generated_citations(citation_chunk_ids, available=available),
        used_chunk_ids=used_chunk_ids,
        notes=notes,
        doc_ids=list(context.doc_ids),
        model_name=config.model_name,
        prompt_version=config.prompt_version,
        retrieval_mode=context.retrieval_mode,
        selected_stage=context.selected_stage,
        latency_ms={"generation_ms": generation_ms, "total_ms": generation_ms},
    )


def generate_answer(
    context: AnswerContext,
    *,
    config: GenerationConfig,
    client: OpenAI | None = None,
) -> GeneratedAnswer:
    if not context.evidence:
        return abstention_answer(
            context=context,
            config=config,
            notes="No evidence chunks were available for answer generation.",
        )

    actual_client = client or build_generation_client()
    started_at = perf_counter()
    response = actual_client.beta.chat.completions.parse(
        model=config.model_name,
        messages=[
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": build_user_prompt(context)},
        ],
        temperature=config.temperature,
        max_completion_tokens=config.max_output_tokens,
        response_format=ModelAnswerDraftPayload,
    )
    parsed_payload = extract_parsed_payload(response)
    if parsed_payload is not None:
        draft = parse_draft(parsed_payload)
    else:
        text = extract_response_text(response)
        draft = parse_draft(parse_json_object(text))
    return finalize_answer(
        context=context, config=config, draft=draft, generation_ms=elapsed_ms(started_at)
    )
