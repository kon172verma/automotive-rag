from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from psycopg import connect

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.ingestion.postgres_loader import apply_schema, load_one_document

DEFAULT_DB_HOST = "127.0.0.1"
DEFAULT_DB_NAME = "automotive_rag"
DEFAULT_DB_PORT = 5432
SCHEMA_FILE = Path("db/init/002-create-schema.sql")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load chunk and embedding artifacts into PostgreSQL."
    )
    parser.add_argument(
        "--chunks-dir",
        type=Path,
        default=Path("artifacts/chunks"),
        help="Directory containing chunk JSON artifacts.",
    )
    parser.add_argument(
        "--embeddings-dir",
        type=Path,
        default=Path("artifacts/embeddings"),
        help="Directory containing embedding JSONL artifacts.",
    )
    parser.add_argument(
        "--match",
        type=str,
        default="*.json",
        help="Glob for selecting chunk files, e.g. '2020-*.json'.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("POSTGRES_HOST", DEFAULT_DB_HOST),
        help="PostgreSQL host.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("POSTGRES_PORT", str(DEFAULT_DB_PORT))),
        help="PostgreSQL port.",
    )
    parser.add_argument(
        "--database",
        type=str,
        default=os.getenv("POSTGRES_DB", DEFAULT_DB_NAME),
        help="PostgreSQL database name.",
    )
    parser.add_argument(
        "--user",
        type=str,
        default=os.getenv("POSTGRES_USER", ""),
        help="PostgreSQL user.",
    )
    parser.add_argument(
        "--password",
        type=str,
        default=os.getenv("POSTGRES_PASSWORD", ""),
        help="PostgreSQL password.",
    )
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="Skip applying the schema file before loading data.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    if not args.user:
        raise SystemExit("POSTGRES_USER is not set.")
    if not args.password:
        raise SystemExit("POSTGRES_PASSWORD is not set.")

    chunk_files = sorted(args.chunks_dir.glob(args.match))
    if not chunk_files:
        raise SystemExit(f"No chunk files found in {args.chunks_dir}")

    conn = connect(
        host=args.host,
        port=args.port,
        dbname=args.database,
        user=args.user,
        password=args.password,
    )
    with conn, conn.cursor() as cur:
        if not args.skip_schema:
            apply_schema(cur, SCHEMA_FILE)

        total_chunks = 0
        loaded_docs = 0
        for chunk_file in chunk_files:
            doc_id, chunk_count = load_one_document(
                cur,
                chunk_file=chunk_file,
                embeddings_dir=args.embeddings_dir,
            )
            loaded_docs += 1
            total_chunks += chunk_count
            print(f"{doc_id}: loaded {chunk_count} chunks")

        print(f"summary: documents={loaded_docs} chunks={total_chunks}")


if __name__ == "__main__":
    main()
