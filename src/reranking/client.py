from __future__ import annotations

import json
from urllib import error, parse, request

from src.vector_retrieval.models import RerankerConfig


def build_reranker_url(base_url: str, path: str) -> str:
    normalized_base = base_url.rstrip("/") + "/"
    normalized_path = path.lstrip("/")
    return parse.urljoin(normalized_base, normalized_path)


def rerank_scores(
    *,
    config: RerankerConfig,
    question: str,
    documents: list[str],
) -> list[float]:
    endpoint = build_reranker_url(config.service_url, "/rerank")
    payload = {
        "model_name": config.model_name,
        "question": question,
        "documents": documents,
    }
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=config.timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Reranker service request failed with HTTP {exc.code}: {detail}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(
            f"Could not reach reranker service at {config.service_url}: {exc.reason}"
        ) from exc

    scores = response_payload.get("scores")
    if not isinstance(scores, list):
        raise RuntimeError("Reranker service returned an invalid 'scores' payload.")
    if len(scores) != len(documents):
        raise RuntimeError(
            "Reranker service returned a score count that does not match candidates."
        )
    try:
        return [float(score) for score in scores]
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Reranker service returned a non-numeric score.") from exc
