from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.chunking.config import (
    CHUNKING_STRATEGY,
    DEFAULT_HARD_MAX_TOKENS,
    DEFAULT_SOFT_MAX_TOKENS,
    DEFAULT_TARGET_TOKENS,
    INGESTION_VERSION,
    ChunkConfig,
)
from src.chunking.pipeline import (
    build_chunker,
    build_converter,
    collect_existing_reports,
    ensure_dirs,
    process_manual,
    write_json,
)


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


def main() -> None:
    args = parse_args()
    config = ChunkConfig(
        target_tokens=args.target_tokens,
        soft_max_tokens=args.soft_max_tokens,
        hard_max_tokens=args.hard_max_tokens,
    )
    output_paths = ensure_dirs(args.output_dir)
    converter = build_converter()
    chunker = build_chunker()

    manuals = sorted(args.manuals_dir.glob(args.match))
    if not manuals:
        raise SystemExit(f"No PDF manuals found in {args.manuals_dir}")

    for pdf_path in manuals:
        report = process_manual(
            pdf_path=pdf_path,
            converter=converter,
            chunker=chunker,
            config=config,
            output_paths=output_paths,
        )
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
