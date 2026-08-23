from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, LiteralString, cast

from psycopg import Cursor, sql


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
    return rows


def vector_literal(values: Iterable[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


def build_search_document(chunk: dict[str, Any]) -> str:
    heading_path = chunk.get("heading_path", [])
    headings = " ".join(heading_path) if isinstance(heading_path, list) else ""
    keyword_text = str(chunk.get("chunk_text_for_keyword_search", "") or "")
    content_type = str(chunk.get("content_type", "") or "")
    return f"{keyword_text} {headings} {content_type}".strip()


def apply_schema(cur: Cursor[Any], schema_path: Path) -> None:
    schema_sql = schema_path.read_text(encoding="utf-8")
    cur.execute(sql.SQL(cast(LiteralString, schema_sql)))


def upsert_document(cur: Cursor[Any], document: dict[str, Any]) -> None:
    cur.execute(
        """
        INSERT INTO documents (
          doc_id,
          make,
          model,
          year,
          trim,
          manual_type,
          language,
          source_file,
          source_hash,
          page_count,
          ingestion_version,
          chunking_strategy,
          ingested_at
        )
        VALUES (
          %(doc_id)s,
          %(make)s,
          %(model)s,
          %(year)s,
          %(trim)s,
          %(manual_type)s,
          %(language)s,
          %(source_file)s,
          %(source_hash)s,
          %(page_count)s,
          %(ingestion_version)s,
          %(chunking_strategy)s,
          %(ingested_at)s
        )
        ON CONFLICT (doc_id) DO UPDATE SET
          make = EXCLUDED.make,
          model = EXCLUDED.model,
          year = EXCLUDED.year,
          trim = EXCLUDED.trim,
          manual_type = EXCLUDED.manual_type,
          language = EXCLUDED.language,
          source_file = EXCLUDED.source_file,
          source_hash = EXCLUDED.source_hash,
          page_count = EXCLUDED.page_count,
          ingestion_version = EXCLUDED.ingestion_version,
          chunking_strategy = EXCLUDED.chunking_strategy,
          ingested_at = EXCLUDED.ingested_at
        """,
        document,
    )


def replace_sections(
    cur: Cursor[Any],
    doc_id: str,
    sections: list[dict[str, Any]],
) -> None:
    cur.execute("DELETE FROM sections WHERE doc_id = %s", (doc_id,))
    ordered_sections = sorted(
        sections,
        key=lambda section: (
            int(section.get("section_level", 0) or 0),
            str(section.get("section_id", "")),
        ),
    )
    for section in ordered_sections:
        cur.execute(
            """
            INSERT INTO sections (
              section_id,
              doc_id,
              parent_section_id,
              section_title,
              section_path,
              section_level,
              toc_label,
              page_start,
              page_end
            )
            VALUES (
              %(section_id)s,
              %(doc_id)s,
              %(parent_section_id)s,
              %(section_title)s,
              %(section_path)s,
              %(section_level)s,
              %(toc_label)s,
              %(page_start)s,
              %(page_end)s
            )
            """,
            section,
        )


def replace_chunks(
    cur: Cursor[Any],
    doc_id: str,
    chunks: list[dict[str, Any]],
    embedding_map: dict[str, dict[str, Any]],
) -> None:
    cur.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
    for chunk in chunks:
        chunk_id = str(chunk["chunk_id"])
        embedding_row = embedding_map.get(chunk_id)
        if embedding_row is None:
            raise ValueError(f"Missing embedding for chunk {chunk_id}")

        embedding_values = embedding_row["embedding"]
        if len(embedding_values) != 1536:
            raise ValueError(
                f"Unexpected embedding dimension for {chunk_id}: "
                f"{len(embedding_values)}"
            )

        payload = {
            **chunk,
            "embedding_text_sha256": embedding_row["embedding_text_sha256"],
            "embedding_model": embedding_row["embedding_model"],
            "embedding_dimensions": embedding_row["embedding_dimensions"],
            "embedding_literal": vector_literal(embedding_values),
            "search_document": build_search_document(chunk),
        }
        cur.execute(
            """
            INSERT INTO chunks (
              chunk_id,
              doc_id,
              section_id,
              chunk_index,
              chunk_index_within_parent,
              sibling_count,
              prev_chunk_id,
              next_chunk_id,
              page_start,
              page_end,
              content_type,
              contains_table,
              contains_image_ref,
              ocr_used,
              char_count,
              token_count_estimate,
              heading_path,
              chunk_text,
              chunk_text_for_keyword_search,
              embedding_text,
              embedding_text_sha256,
              embedding_model,
              embedding_dimensions,
              embedding,
              search_tsv
            )
            VALUES (
              %(chunk_id)s,
              %(doc_id)s,
              %(section_id)s,
              %(chunk_index)s,
              %(chunk_index_within_parent)s,
              %(sibling_count)s,
              %(prev_chunk_id)s,
              %(next_chunk_id)s,
              %(page_start)s,
              %(page_end)s,
              %(content_type)s,
              %(contains_table)s,
              %(contains_image_ref)s,
              %(ocr_used)s,
              %(char_count)s,
              %(token_count_estimate)s,
              %(heading_path)s,
              %(chunk_text)s,
              %(chunk_text_for_keyword_search)s,
              %(embedding_text)s,
              %(embedding_text_sha256)s,
              %(embedding_model)s,
              %(embedding_dimensions)s,
              %(embedding_literal)s::vector,
              to_tsvector('english', %(search_document)s)
            )
            """,
            payload,
        )


def load_one_document(
    cur: Cursor[Any],
    *,
    chunk_file: Path,
    embeddings_dir: Path,
) -> tuple[str, int]:
    payload = load_json(chunk_file)
    document = payload["document"]
    sections = payload["sections"]
    chunks = payload["chunks"]
    doc_id = str(document["doc_id"])
    embedding_file = embeddings_dir / f"{doc_id}.jsonl"
    if not embedding_file.exists():
        raise FileNotFoundError(f"Missing embedding artifact: {embedding_file}")

    embedding_rows = load_jsonl(embedding_file)
    embedding_map = {str(row["chunk_id"]): row for row in embedding_rows}
    if len(embedding_map) != len(chunks):
        raise ValueError(
            f"Embedding count mismatch for {doc_id}: "
            f"{len(embedding_map)} embeddings vs {len(chunks)} chunks"
        )

    upsert_document(cur, document)
    replace_sections(cur, doc_id, sections)
    replace_chunks(cur, doc_id, chunks, embedding_map)
    return doc_id, len(chunks)
