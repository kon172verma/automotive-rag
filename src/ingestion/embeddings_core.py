from __future__ import annotations

# mypy: disable-error-code=import-not-found
import hashlib
import json
import sys
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, RateLimitError

DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSIONS = 1536
DEFAULT_BATCH_SIZE = 32
DEFAULT_MAX_RETRIES = 5
EMBEDDING_VERSION = "v0.1.0"


@dataclass(frozen=True)
class EmbeddingConfig:
    model: str = DEFAULT_MODEL
    dimensions: int = DEFAULT_DIMENSIONS
    batch_size: int = DEFAULT_BATCH_SIZE
    max_retries: int = DEFAULT_MAX_RETRIES


def ensure_dirs(base_dir: Path) -> dict[str, Path]:
    paths = {
        "embeddings": base_dir / "embeddings",
        "reports": base_dir / "embedding-reports",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)
        handle.write("\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            json.dump(row, handle, ensure_ascii=True)
            handle.write("\n")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def batched(
    items: Sequence[dict[str, Any]],
    batch_size: int,
) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(items), batch_size):
        yield list(items[start : start + batch_size])


def validate_chunk(chunk: dict[str, Any], chunk_file: Path) -> str:
    embedding_text = chunk.get("embedding_text")
    if not isinstance(embedding_text, str) or not embedding_text.strip():
        raise ValueError(
            f"Chunk {chunk.get('chunk_id')} in {chunk_file} is missing embedding_text"
        )
    return embedding_text.strip()


def embed_batch(
    *,
    client: OpenAI,
    texts: list[str],
    config: EmbeddingConfig,
) -> tuple[list[list[float]], int]:
    for attempt in range(config.max_retries + 1):
        try:
            response = client.embeddings.create(
                model=config.model,
                input=texts,
                dimensions=config.dimensions,
            )
            vectors = [list(item.embedding) for item in response.data]
            prompt_tokens = int(getattr(response.usage, "prompt_tokens", 0) or 0)
            return vectors, prompt_tokens
        except RateLimitError as exc:
            error_code = getattr(exc, "code", None)
            message = str(exc).lower()
            if error_code in {"insufficient_quota", "credit_balance_exhausted"}:
                raise
            if "no credits remaining" in message or "insufficient_quota" in message:
                raise
            if attempt >= config.max_retries:
                raise
            _sleep_after_retry(exc, attempt)
        except (APIConnectionError, APIError, APITimeoutError) as exc:
            if attempt >= config.max_retries:
                raise
            _sleep_after_retry(exc, attempt)

    raise RuntimeError("Unreachable retry state while creating embeddings")


def _sleep_after_retry(exc: Exception, attempt: int) -> None:
    sleep_seconds = min(30.0, 2**attempt)
    print(
        f"Retrying batch after API error ({exc.__class__.__name__}) in "
        f"{sleep_seconds:.1f}s...",
        file=sys.stderr,
    )
    time.sleep(sleep_seconds)


def build_embedding_record(
    *,
    doc_id: str,
    chunk: dict[str, Any],
    text: str,
    vector: list[float],
    config: EmbeddingConfig,
) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "chunk_id": chunk["chunk_id"],
        "chunk_index": chunk["chunk_index"],
        "section_id": chunk["section_id"],
        "page_start": chunk["page_start"],
        "page_end": chunk["page_end"],
        "content_type": chunk["content_type"],
        "token_count_estimate": chunk["token_count_estimate"],
        "embedding_model": config.model,
        "embedding_dimensions": len(vector),
        "embedding_text_sha256": sha256_text(text),
        "embedding": vector,
    }


def process_chunk_file(
    *,
    chunk_file: Path,
    client: OpenAI,
    config: EmbeddingConfig,
    output_paths: dict[str, Path],
    overwrite: bool,
) -> dict[str, Any]:
    payload = load_json(chunk_file)
    document = payload["document"]
    chunks = payload["chunks"]
    doc_id = document["doc_id"]
    embedding_path = output_paths["embeddings"] / f"{doc_id}.jsonl"
    report_path = output_paths["reports"] / f"{doc_id}.json"

    if embedding_path.exists() and report_path.exists() and not overwrite:
        report = load_json(report_path)
        print(f"{doc_id}: skipped existing embeddings")
        return report

    records: list[dict[str, Any]] = []
    total_prompt_tokens = 0

    for batch in batched(chunks, config.batch_size):
        texts = [validate_chunk(chunk, chunk_file) for chunk in batch]
        vectors, prompt_tokens = embed_batch(
            client=client,
            texts=texts,
            config=config,
        )
        if len(vectors) != len(batch):
            raise RuntimeError(
                f"Embedding count mismatch for {chunk_file}: "
                f"expected {len(batch)}, got {len(vectors)}"
            )

        total_prompt_tokens += prompt_tokens
        for chunk, text, vector in zip(batch, texts, vectors, strict=True):
            records.append(
                build_embedding_record(
                    doc_id=doc_id,
                    chunk=chunk,
                    text=text,
                    vector=vector,
                    config=config,
                )
            )

    write_jsonl(embedding_path, records)
    report = {
        "doc_id": doc_id,
        "source_chunk_file": str(chunk_file),
        "embedding_file": str(embedding_path),
        "chunk_count": len(records),
        "embedding_model": config.model,
        "embedding_dimensions": config.dimensions,
        "embedding_version": EMBEDDING_VERSION,
        "prompt_tokens_total": total_prompt_tokens,
        "embedded_at": datetime.now(UTC).isoformat(),
        "source_hash": document["source_hash"],
        "chunking_strategy": document["chunking_strategy"],
        "ingestion_version": document["ingestion_version"],
    }
    write_json(report_path, report)
    print(
        f"{doc_id}: chunks={report['chunk_count']} "
        f"prompt_tokens={report['prompt_tokens_total']}"
    )
    return report


def collect_existing_reports(report_dir: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in sorted(report_dir.glob("*.json")):
        if path.name == "summary.json":
            continue
        reports.append(load_json(path))
    return reports
