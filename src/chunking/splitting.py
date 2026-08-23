from __future__ import annotations

import re
from typing import Any

from src.chunking.config import ChunkConfig
from src.chunking.extraction import estimate_tokens, normalize_whitespace


def sentence_split(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\-])", text)
    values = [normalize_whitespace(piece) for piece in pieces]
    return [value for value in values if value]


def paragraph_split(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text)
    values = [normalize_whitespace(paragraph) for paragraph in paragraphs]
    return [value for value in values if value]


def semantic_split(text: str, config: ChunkConfig) -> list[str]:
    text = normalize_whitespace(text)
    if not text:
        return []
    if estimate_tokens(text) <= config.soft_max_tokens:
        return [text]

    segments = paragraph_split(text)
    if len(segments) == 1:
        segments = sentence_split(text)
    if len(segments) == 1:
        words = text.split()
        step = max(1, config.target_tokens * 3)
        return [
            normalize_whitespace(" ".join(words[idx : idx + step]))
            for idx in range(0, len(words), step)
            if words[idx : idx + step]
        ]

    out: list[str] = []
    current_parts: list[str] = []

    def flush() -> None:
        if current_parts:
            out.append(normalize_whitespace("\n\n".join(current_parts)))
            current_parts.clear()

    for segment in segments:
        seg_tokens = estimate_tokens(segment)
        if seg_tokens > config.hard_max_tokens:
            flush()
            out.extend(semantic_split(segment, config))
            continue

        candidate = "\n\n".join(current_parts + [segment]) if current_parts else segment
        if estimate_tokens(candidate) <= config.soft_max_tokens:
            current_parts.append(segment)
        else:
            flush()
            current_parts.append(segment)

    flush()
    return out


def infer_content_type(text: str, headings: list[str]) -> str:
    haystack = f"{' '.join(headings)} {text}".lower()
    if "warning" in haystack or "caution" in haystack:
        return "warning"
    if "maintenance" in haystack and "schedule" in haystack:
        return "maintenance_schedule"
    if "|" in text or "\t" in text:
        return "table"
    if re.search(r"\bstep\b|\b1\.", haystack):
        return "procedure"
    if "specification" in haystack or "capacity" in haystack:
        return "specification"
    return "overview"


def merge_section_elements(
    section_elements: list[dict[str, Any]],
    config: ChunkConfig,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    current_texts: list[str] = []
    current_pages: list[tuple[int | None, int | None]] = []

    def flush() -> None:
        if not current_texts:
            return
        merged_text = normalize_whitespace("\n\n".join(current_texts))
        page_values = [
            value
            for page_pair in current_pages
            for value in page_pair
            if value is not None
        ]
        merged.append(
            {
                "text": merged_text,
                "page_start": min(page_values) if page_values else None,
                "page_end": max(page_values) if page_values else None,
            }
        )
        current_texts.clear()
        current_pages.clear()

    for element in section_elements:
        text = normalize_whitespace(element["text"])
        if not text:
            continue
        tokens = estimate_tokens(text)
        page_pair = (element["page_start"], element["page_end"])

        if tokens > config.hard_max_tokens:
            flush()
            for split_text in semantic_split(text, config):
                merged.append(
                    {
                        "text": split_text,
                        "page_start": element["page_start"],
                        "page_end": element["page_end"],
                    }
                )
            continue

        candidate = "\n\n".join(current_texts + [text]) if current_texts else text
        if current_texts and estimate_tokens(candidate) > config.soft_max_tokens:
            flush()
        current_texts.append(text)
        current_pages.append(page_pair)

    flush()
    return merged
