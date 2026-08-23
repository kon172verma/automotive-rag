from __future__ import annotations

from dataclasses import dataclass

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
