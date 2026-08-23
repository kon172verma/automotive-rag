from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from pydantic import BaseModel, Field

DEFAULT_ANSWER_MODEL = "gpt-5-mini"
DEFAULT_ANSWER_TEMPERATURE = 1.0
DEFAULT_MAX_OUTPUT_TOKENS = 2048
DEFAULT_PROMPT_VERSION = "answer_generation_v1"


@dataclass(frozen=True)
class GenerationConfig:
    model_name: str = DEFAULT_ANSWER_MODEL
    temperature: float = DEFAULT_ANSWER_TEMPERATURE
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    prompt_version: str = DEFAULT_PROMPT_VERSION


@dataclass(frozen=True)
class GeneratedVehicle:
    make: str
    model: str
    year: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GeneratedCitation:
    chunk_id: str
    doc_id: str
    section_title: str
    page_start: int | None
    page_end: int | None
    citation_text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelAnswerDraft:
    answerability: str
    answer: str
    confidence: str
    citation_chunk_ids: list[str]
    used_chunk_ids: list[str]
    notes: str


class ModelAnswerDraftPayload(BaseModel):
    answerability: str
    answer: str
    confidence: str
    citation_chunk_ids: list[str] = Field(default_factory=list)
    used_chunk_ids: list[str] = Field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class GeneratedAnswer:
    question: str
    vehicle: GeneratedVehicle
    answerability: str
    answer: str
    confidence: str
    citations: list[GeneratedCitation]
    used_chunk_ids: list[str]
    notes: str
    doc_ids: list[str]
    model_name: str
    prompt_version: str
    retrieval_mode: str
    selected_stage: str
    latency_ms: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["vehicle"] = self.vehicle.to_dict()
        payload["citations"] = [citation.to_dict() for citation in self.citations]
        return payload
