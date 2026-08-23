from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AnswerContextRequest:
    question: str
    make: str
    model: str
    year: int
    vehicle_label: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceChunk:
    rank: int
    chunk_id: str
    doc_id: str
    section_id: str
    section_title: str
    heading_path: list[str]
    page_start: int | None
    page_end: int | None
    page_label: str
    content_type: str
    retrieval_source: str
    score: float
    chunk_text: str
    citation_text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnswerContext:
    request: AnswerContextRequest
    retrieval_mode: str
    selected_stage: str
    doc_ids: list[str]
    latency_ms: dict[str, Any]
    evidence: list[EvidenceChunk]
    context_text: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["request"] = self.request.to_dict()
        payload["evidence"] = [chunk.to_dict() for chunk in self.evidence]
        return payload
