from __future__ import annotations

from time import perf_counter
from typing import Any

from psycopg import Connection

from src.vector_retrieval.models import RetrievalConfig, RetrievalRequest, SearchResult
from src.vector_retrieval.runtime import elapsed_ms, normalize_text


def resolve_doc_ids(
    conn: Connection[Any],
    request: RetrievalRequest,
) -> tuple[list[str], float]:
    started_at = perf_counter()
    make = normalize_text(request.make)
    model = normalize_text(request.model)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT doc_id
            FROM documents
            WHERE make = %s
              AND model = %s
              AND year = %s
            ORDER BY doc_id
            """,
            (make, model, request.year),
        )
        rows = cur.fetchall()
    doc_ids = [str(row[0]) for row in rows]
    if not doc_ids:
        raise ValueError(
            f"No manuals found for make={request.make!r}, "
            f"model={request.model!r}, year={request.year}"
        )
    return doc_ids, elapsed_ms(started_at)


def keyword_search(
    conn: Connection[Any],
    retrieval_config: RetrievalConfig,
    request: RetrievalRequest,
    doc_ids: list[str],
) -> tuple[list[SearchResult], float]:
    started_at = perf_counter()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              c.chunk_id,
              c.doc_id,
              c.section_id,
              s.section_title,
              c.heading_path,
              c.page_start,
              c.page_end,
              c.chunk_text,
              c.chunk_index,
              c.content_type,
              ts_rank_cd(
                c.search_tsv,
                websearch_to_tsquery('english', %s)
              ) AS keyword_score
            FROM chunks AS c
            JOIN sections AS s
              ON s.section_id = c.section_id
            WHERE c.doc_id = ANY(%s)
              AND c.search_tsv @@ websearch_to_tsquery('english', %s)
            ORDER BY keyword_score DESC, c.chunk_index ASC
            LIMIT %s
            """,
            (
                request.question,
                doc_ids,
                request.question,
                retrieval_config.keyword_top_k,
            ),
        )
        rows = cur.fetchall()
    results: list[SearchResult] = []
    for rank, row in enumerate(rows, start=1):
        results.append(
            SearchResult(
                chunk_id=str(row[0]),
                doc_id=str(row[1]),
                section_id=str(row[2]),
                section_title=str(row[3]),
                heading_path=list(row[4]),
                page_start=row[5],
                page_end=row[6],
                chunk_text=str(row[7]),
                chunk_index=int(row[8]),
                content_type=str(row[9]),
                retrieval_source="keyword",
                score=float(row[10]),
                keyword_rank=rank,
                keyword_score=float(row[10]),
            )
        )
    return results, elapsed_ms(started_at)
