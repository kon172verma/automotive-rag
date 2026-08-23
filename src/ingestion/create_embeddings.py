from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.ingestion.embeddings_core import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_DIMENSIONS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MODEL,
    EMBEDDING_VERSION,
    EmbeddingConfig,
    collect_existing_reports,
    ensure_dirs,
    process_chunk_file,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate embedding artifacts from chunk JSON files."
    )
    parser.add_argument(
        "--chunks-dir",
        type=Path,
        default=Path("artifacts/chunks"),
        help="Directory containing chunk artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts"),
        help="Base directory for generated embedding artifacts.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help="Embedding model to use.",
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        default=DEFAULT_DIMENSIONS,
        help="Embedding dimensions to request from the API.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Number of chunks to embed in one API call.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help="Maximum retries for transient OpenAI API errors.",
    )
    parser.add_argument(
        "--match",
        type=str,
        default="*.json",
        help="Glob for selecting chunk files, e.g. '2020-*.json'.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate embeddings even if artifacts already exist.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "OPENAI_API_KEY is not set. Add it to the environment or .env."
        )
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be greater than 0")
    if args.dimensions <= 0:
        raise SystemExit("--dimensions must be greater than 0")
    if args.max_retries < 0:
        raise SystemExit("--max-retries must be 0 or greater")

    chunk_files = sorted(args.chunks_dir.glob(args.match))
    if not chunk_files:
        raise SystemExit(f"No chunk files found in {args.chunks_dir}")

    config = EmbeddingConfig(
        model=args.model,
        dimensions=args.dimensions,
        batch_size=args.batch_size,
        max_retries=args.max_retries,
    )
    output_paths = ensure_dirs(args.output_dir)
    client = OpenAI(api_key=api_key, max_retries=0, timeout=60.0)

    reports = [
        process_chunk_file(
            chunk_file=chunk_file,
            client=client,
            config=config,
            output_paths=output_paths,
            overwrite=args.overwrite,
        )
        for chunk_file in chunk_files
    ]
    all_reports = collect_existing_reports(output_paths["reports"])
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "manual_count": len(all_reports),
        "embedding_model": config.model,
        "embedding_dimensions": config.dimensions,
        "embedding_version": EMBEDDING_VERSION,
        "reports": all_reports,
    }
    write_json(output_paths["reports"] / "summary.json", summary)
    total_chunks = sum(int(report["chunk_count"]) for report in reports)
    total_tokens = sum(int(report["prompt_tokens_total"]) for report in reports)
    print(
        f"summary: manuals={len(reports)} chunks={total_chunks} "
        f"prompt_tokens={total_tokens}"
    )


if __name__ == "__main__":
    main()
