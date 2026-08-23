from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any


def normalize_whitespace(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def filename_metadata(path: Path) -> dict[str, Any]:
    stem = path.stem.lower()
    parts = stem.split("-")
    year = int(parts[0]) if parts and parts[0].isdigit() else None
    make = parts[1] if len(parts) > 1 else None
    model = "-".join(parts[2:]) if len(parts) > 2 else None
    return {
        "doc_id": stem,
        "year": year,
        "make": make,
        "model": model,
        "trim": None,
        "manual_type": "owners_manual",
        "language": "en",
        "source_file": str(path),
    }


def safe_model_dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [safe_model_dump(item) for item in value]
    if isinstance(value, tuple):
        return [safe_model_dump(item) for item in value]
    if isinstance(value, dict):
        return {key: safe_model_dump(val) for key, val in value.items()}
    if hasattr(value, "__dict__"):
        return {
            key: safe_model_dump(val)
            for key, val in vars(value).items()
            if not key.startswith("_")
        }
    return value


def stringify_heading(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return normalize_whitespace(value)
    text = getattr(value, "text", None)
    if isinstance(text, str) and text.strip():
        return normalize_whitespace(text)
    dumped = safe_model_dump(value)
    if isinstance(dumped, dict):
        for key in ("text", "title", "label", "name"):
            maybe = dumped.get(key)
            if isinstance(maybe, str) and maybe.strip():
                return normalize_whitespace(maybe)
    return normalize_whitespace(str(value))


def extract_headings(chunk: Any) -> list[str]:
    meta = getattr(chunk, "meta", None)
    headings = getattr(meta, "headings", None)
    if headings is None:
        return []
    values = [stringify_heading(item) for item in headings]
    return [item for item in values if item]


def walk_for_page_numbers(value: Any) -> list[int]:
    pages: list[int] = []
    stack = [value]
    while stack:
        current = stack.pop()
        if current is None:
            continue
        if isinstance(current, dict):
            for key, val in current.items():
                lowered = str(key).lower()
                if lowered in {"page_no", "page", "page_number"} and isinstance(
                    val, int
                ):
                    pages.append(val)
                else:
                    stack.append(val)
            continue
        if isinstance(current, list):
            stack.extend(current)
            continue
        if hasattr(current, "model_dump"):
            stack.append(current.model_dump())
            continue
        if hasattr(current, "__dict__"):
            stack.append(vars(current))
    return sorted({page for page in pages if isinstance(page, int)})


def extract_page_span(chunk: Any) -> tuple[int | None, int | None]:
    dumped = safe_model_dump(getattr(chunk, "meta", None))
    pages = walk_for_page_numbers(dumped)
    if not pages:
        return None, None
    return min(pages), max(pages)
