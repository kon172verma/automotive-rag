from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

LATENCY_KEYS = (
    "total_ms",
    "doc_resolution_ms",
    "keyword_search_ms",
    "query_embedding_ms",
    "vector_search_ms",
    "fusion_ms",
    "rerank_ms",
)


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    position = (len(sorted_values) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    lower_value = sorted_values[lower]
    upper_value = sorted_values[upper]
    weight = position - lower
    return float(lower_value + (upper_value - lower_value) * weight)


def update_latency_aggregate(
    aggregate: dict[str, Any],
    mode_name: str,
    latency: dict[str, Any],
) -> None:
    stage = aggregate.setdefault(
        mode_name,
        {
            "metrics": defaultdict(list),
            "embedding_cache_hits": 0,
            "embedding_cache_observations": 0,
        },
    )
    for key in LATENCY_KEYS:
        value = latency.get(key)
        if value is not None:
            stage["metrics"][key].append(float(value))
    cache_hit = latency.get("embedding_cache_hit")
    if cache_hit is not None:
        stage["embedding_cache_observations"] += 1
        if bool(cache_hit):
            stage["embedding_cache_hits"] += 1


def finalize_latency_aggregate(aggregate: dict[str, Any]) -> dict[str, Any]:
    finalized: dict[str, Any] = {}
    for mode_name, stage in aggregate.items():
        metrics_summary: dict[str, Any] = {}
        for key in LATENCY_KEYS:
            values = list(stage["metrics"].get(key, []))
            if not values:
                continue
            metrics_summary[key] = {
                "sample_count": len(values),
                "avg_ms": round(sum(values) / len(values), 3),
                "p50_ms": round(percentile(values, 0.50) or 0.0, 3),
                "p95_ms": round(percentile(values, 0.95) or 0.0, 3),
                "min_ms": round(min(values), 3),
                "max_ms": round(max(values), 3),
            }
        cache_observations = int(stage["embedding_cache_observations"])
        finalized[mode_name] = {
            "metrics": metrics_summary,
            "embedding_cache_hit_rate": (
                None
                if cache_observations == 0
                else round(stage["embedding_cache_hits"] / cache_observations, 4)
            ),
        }
    return finalized


def hybrid_latency_without_rerank(latency: dict[str, Any]) -> dict[str, Any]:
    rerank_ms = float(latency.get("rerank_ms") or 0.0)
    hybrid_latency = dict(latency)
    hybrid_latency["total_ms"] = round(
        max(0.0, float(latency["total_ms"]) - rerank_ms),
        3,
    )
    hybrid_latency["rerank_ms"] = None
    return hybrid_latency
