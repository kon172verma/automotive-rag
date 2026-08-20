from __future__ import annotations

# mypy: disable-error-code=import-not-found
import argparse
import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
)
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
)
from docling_core.transforms.chunker import (
    HierarchicalChunker,  # type: ignore[import-not-found]
)

DEFAULT_TARGET_TOKENS = 450
DEFAULT_SOFT_MAX_TOKENS = 650
DEFAULT_HARD_MAX_TOKENS = 800
INGESTION_VERSION = "v0.1.0"
CHUNKING_STRATEGY = "parent_child_semantic_split_v1"


@dataclass
class ChunkConfig:
    target_tokens: int = DEFAULT_TARGET_TOKENS
    soft_max_tokens: int = DEFAULT_SOFT_MAX_TOKENS
    hard_max_tokens: int = DEFAULT_HARD_MAX_TOKENS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert PDF manuals into file-first chunk artifacts."
    )
    parser.add_argument(
        "--manuals-dir",
        type=Path,
        default=Path("manuals"),
        help="Directory containing PDF manuals.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts"),
        help="Base directory for generated artifacts.",
    )
    parser.add_argument(
        "--target-tokens",
        type=int,
        default=DEFAULT_TARGET_TOKENS,
        help="Preferred target size for a child chunk.",
    )
    parser.add_argument(
        "--soft-max-tokens",
        type=int,
        default=DEFAULT_SOFT_MAX_TOKENS,
        help="Preferred ceiling before a chunk gets split.",
    )
    parser.add_argument(
        "--hard-max-tokens",
        type=int,
        default=DEFAULT_HARD_MAX_TOKENS,
        help="Absolute ceiling before we force smaller splits.",
    )
    parser.add_argument(
        "--match",
        type=str,
        default="*.pdf",
        help="Glob for selecting a subset of manuals, e.g. '2020-*.pdf'.",
    )
    return parser.parse_args()


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


def serialize_chunk(
    *,
    doc_id: str,
    parent_id: str,
    parent_index: int,
    child_index: int,
    sibling_count: int,
    text: str,
    headings: list[str],
    page_start: int | None,
    page_end: int | None,
    content_type: str,
) -> dict[str, Any]:
    chunk_id = f"{doc_id}::p{parent_index:04d}::c{child_index:04d}"
    return {
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "section_id": parent_id,
        "chunk_index": None,
        "chunk_index_within_parent": child_index,
        "sibling_count": sibling_count,
        "prev_chunk_id": None,
        "next_chunk_id": None,
        "chunk_text": text,
        "embedding_text": "\n".join(headings + [text]) if headings else text,
        "chunk_text_for_keyword_search": text,
        "page_start": page_start,
        "page_end": page_end,
        "heading_path": headings,
        "content_type": content_type,
        "contains_table": "table" in content_type,
        "contains_image_ref": "<!-- image -->" in text.lower(),
        "ocr_used": False,
        "char_count": len(text),
        "token_count_estimate": estimate_tokens(text),
    }


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
    section_elements: list[dict[str, Any]], config: ChunkConfig
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


def build_chunks(
    *,
    hierarchical_chunks: list[Any],
    doc_id: str,
    config: ChunkConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    section_lookup: dict[tuple[str, ...], dict[str, Any]] = {}
    section_order: list[tuple[str, ...]] = []
    section_elements: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    all_chunks: list[dict[str, Any]] = []

    for raw_chunk in hierarchical_chunks:
        headings = extract_headings(raw_chunk)
        heading_path = tuple(headings) if headings else ("_root",)
        if heading_path not in section_lookup:
            parent_index = len(section_order)
            parent_id = f"{doc_id}::section::{parent_index:04d}"
            section_lookup[heading_path] = {
                "section_id": parent_id,
                "doc_id": doc_id,
                "section_title": headings[-1] if headings else "_root",
                "section_path": list(headings),
                "section_level": len(headings),
                "toc_label": headings[-1] if headings else None,
                "page_start": None,
                "page_end": None,
                "parent_section_id": None,
            }
            section_order.append(heading_path)

        section = section_lookup[heading_path]
        parent_id = section["section_id"]
        parent_index = int(parent_id.rsplit("::", 1)[-1])

        base_text = normalize_whitespace(getattr(raw_chunk, "text", "") or "")
        if not base_text:
            continue

        page_start, page_end = extract_page_span(raw_chunk)
        if section["page_start"] is None or (
            page_start is not None and page_start < section["page_start"]
        ):
            section["page_start"] = page_start
        if section["page_end"] is None or (
            page_end is not None and page_end > section["page_end"]
        ):
            section["page_end"] = page_end

        section_elements[parent_id].append(
            {
                "text": base_text,
                "page_start": page_start,
                "page_end": page_end,
            }
        )

    for heading_path in section_order:
        section = section_lookup[heading_path]
        parent_id = section["section_id"]
        parent_index = int(parent_id.rsplit("::", 1)[-1])
        headings = [] if list(heading_path) == ["_root"] else list(heading_path)
        merged_children = merge_section_elements(section_elements[parent_id], config)
        sibling_count = len(merged_children)
        for child_offset, child_data in enumerate(merged_children):
            child_text = child_data["text"]
            content_type = infer_content_type(child_text, headings)
            child = serialize_chunk(
                doc_id=doc_id,
                parent_id=parent_id,
                parent_index=parent_index,
                child_index=child_offset,
                sibling_count=sibling_count,
                text=child_text,
                headings=headings,
                page_start=child_data["page_start"],
                page_end=child_data["page_end"],
                content_type=content_type,
            )
            all_chunks.append(child)

    for global_index, chunk in enumerate(all_chunks):
        chunk["chunk_index"] = global_index

    chunks_by_parent: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for chunk in all_chunks:
        chunks_by_parent[chunk["section_id"]].append(chunk)
    for siblings in chunks_by_parent.values():
        siblings.sort(key=lambda item: item["chunk_index_within_parent"])
        for idx, chunk in enumerate(siblings):
            chunk["sibling_count"] = len(siblings)
            if idx > 0:
                chunk["prev_chunk_id"] = siblings[idx - 1]["chunk_id"]
            if idx < len(siblings) - 1:
                chunk["next_chunk_id"] = siblings[idx + 1]["chunk_id"]

    sections: list[dict[str, Any]] = []
    for heading_path in section_order:
        section = section_lookup[heading_path]
        path = list(heading_path)
        if path != ["_root"] and len(path) > 1:
            parent_path = tuple(path[:-1])
            parent = section_lookup.get(parent_path)
            if parent is not None:
                section["parent_section_id"] = parent["section_id"]
        sections.append(section)

    return sections, all_chunks


def ensure_dirs(base_dir: Path) -> dict[str, Path]:
    paths = {
        "documents": base_dir / "documents",
        "chunks": base_dir / "chunks",
        "reports": base_dir / "reports",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)
        handle.write("\n")


def collect_existing_reports(report_dir: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in sorted(report_dir.glob("*.json")):
        if path.name == "summary.json":
            continue
        with path.open("r", encoding="utf-8") as handle:
            reports.append(json.load(handle))
    return reports


def process_manual(
    *,
    pdf_path: Path,
    converter: DocumentConverter,
    chunker: HierarchicalChunker,
    config: ChunkConfig,
    output_paths: dict[str, Path],
) -> dict[str, Any]:
    metadata = filename_metadata(pdf_path)
    doc_id = metadata["doc_id"]
    source_hash = sha256_file(pdf_path)

    conversion = converter.convert(pdf_path)
    document = conversion.document
    document_json_path = output_paths["documents"] / f"{doc_id}.json"
    document.save_as_json(filename=document_json_path)

    hierarchical_chunks = list(chunker.chunk(dl_doc=document))
    sections, chunks = build_chunks(
        hierarchical_chunks=hierarchical_chunks,
        doc_id=doc_id,
        config=config,
    )

    page_count = len(getattr(document, "pages", {}) or {})
    chunk_payload = {
        "document": {
            **metadata,
            "source_hash": source_hash,
            "ingestion_version": INGESTION_VERSION,
            "chunking_strategy": CHUNKING_STRATEGY,
            "ingested_at": datetime.now(UTC).isoformat(),
            "page_count": page_count,
        },
        "sections": sections,
        "chunks": chunks,
    }
    report_payload = {
        "doc_id": doc_id,
        "source_file": str(pdf_path),
        "document_json": str(document_json_path),
        "section_count": len(sections),
        "chunk_count": len(chunks),
        "page_count": page_count,
        "source_hash": source_hash,
        "ingestion_version": INGESTION_VERSION,
        "chunking_strategy": CHUNKING_STRATEGY,
        "max_chunk_tokens": max(
            (chunk["token_count_estimate"] for chunk in chunks), default=0
        ),
        "avg_chunk_tokens": (
            round(
                sum(chunk["token_count_estimate"] for chunk in chunks) / len(chunks),
                2,
            )
            if chunks
            else 0
        ),
    }

    write_json(output_paths["chunks"] / f"{doc_id}.json", chunk_payload)
    write_json(output_paths["reports"] / f"{doc_id}.json", report_payload)
    return report_payload


def main() -> None:
    args = parse_args()
    config = ChunkConfig(
        target_tokens=args.target_tokens,
        soft_max_tokens=args.soft_max_tokens,
        hard_max_tokens=args.hard_max_tokens,
    )
    output_paths = ensure_dirs(args.output_dir)
    pipeline_options = PdfPipelineOptions(
        do_ocr=False,
        do_table_structure=False,
        do_code_enrichment=False,
        do_formula_enrichment=False,
        do_picture_classification=False,
        do_picture_description=False,
        do_chart_extraction=False,
        force_backend_text=True,
        enable_remote_services=False,
    )
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    chunker = HierarchicalChunker()

    manuals = sorted(args.manuals_dir.glob(args.match))
    if not manuals:
        raise SystemExit(f"No PDF manuals found in {args.manuals_dir}")

    reports = []
    for pdf_path in manuals:
        report = process_manual(
            pdf_path=pdf_path,
            converter=converter,
            chunker=chunker,
            config=config,
            output_paths=output_paths,
        )
        reports.append(report)
        print(
            f"{pdf_path.name}: pages={report['page_count']} "
            f"sections={report['section_count']} chunks={report['chunk_count']}"
        )

    all_reports = collect_existing_reports(output_paths["reports"])
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "manual_count": len(all_reports),
        "ingestion_version": INGESTION_VERSION,
        "chunking_strategy": CHUNKING_STRATEGY,
        "reports": all_reports,
    }
    write_json(output_paths["reports"] / "summary.json", summary)


if __name__ == "__main__":
    main()
