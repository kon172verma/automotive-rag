from __future__ import annotations

import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any

from dotenv import load_dotenv

from src.vector_retrieval.models import (
    DEFAULT_DB_HOST,
    DEFAULT_DB_NAME,
    DEFAULT_DB_PORT,
    DbConfig,
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)
        handle.write("\n")


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


def normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def elapsed_ms(start_time: float) -> float:
    return round((perf_counter() - start_time) * 1000.0, 3)


def build_db_config() -> DbConfig:
    load_dotenv()
    user = os.getenv("POSTGRES_USER", "")
    password = os.getenv("POSTGRES_PASSWORD", "")
    if not user:
        raise SystemExit("POSTGRES_USER is not set.")
    if not password:
        raise SystemExit("POSTGRES_PASSWORD is not set.")
    return DbConfig(
        host=os.getenv("POSTGRES_HOST", DEFAULT_DB_HOST),
        port=int(os.getenv("POSTGRES_PORT", str(DEFAULT_DB_PORT))),
        database=os.getenv("POSTGRES_DB", DEFAULT_DB_NAME),
        user=user,
        password=password,
    )
