from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.chunking.config import ChunkConfig
from src.chunking.extraction import (
    estimate_tokens,
    extract_headings,
    extract_page_span,
    normalize_whitespace,
)
from src.chunking.splitting import infer_content_type, merge_section_elements


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
            all_chunks.append(
                serialize_chunk(
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
            )

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
