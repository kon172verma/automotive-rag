from __future__ import annotations

# mypy: disable-error-code=import-not-found
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.transforms.chunker import (
    HierarchicalChunker,  # type: ignore[import-not-found]
)

from src.chunking.builder import build_chunks
from src.chunking.config import CHUNKING_STRATEGY, INGESTION_VERSION, ChunkConfig
from src.chunking.extraction import filename_metadata, sha256_file


def build_converter() -> DocumentConverter:
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
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )


def build_chunker() -> HierarchicalChunker:
    return HierarchicalChunker()


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
            (chunk["token_count_estimate"] for chunk in chunks),
            default=0,
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
