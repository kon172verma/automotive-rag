from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import perf_counter
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from sentence_transformers import CrossEncoder

from src.vector_retrieval.models import DEFAULT_RERANKER_MODEL

DEFAULT_RERANKER_HOST = "127.0.0.1"
DEFAULT_RERANKER_PORT = 8001
DEFAULT_RERANKER_DEVICE = "auto"


def resolve_device(device_name: str) -> str:
    import torch

    if device_name != "auto":
        if device_name == "mps" and not torch.backends.mps.is_available():
            raise SystemExit("RERANKER_DEVICE is 'mps' but MPS is not available.")
        if device_name == "cuda" and not torch.cuda.is_available():
            raise SystemExit("RERANKER_DEVICE is 'cuda' but CUDA is not available.")
        if device_name not in {"cpu", "cuda", "mps"}:
            raise SystemExit("RERANKER_DEVICE must be one of auto, cpu, cuda, or mps.")
        return device_name
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class RerankerService:
    def __init__(self, *, model_name: str, device: str) -> None:
        self.model_name = model_name
        self.device = device
        self.model = CrossEncoder(model_name, device=device)

    def predict(self, *, question: str, documents: list[str]) -> list[float]:
        pairs = [(question, document) for document in documents]
        return [float(score) for score in self.model.predict(pairs)]

    def health_payload(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "model_name": self.model_name,
            "device": self.device,
        }


def write_json_response(
    handler: BaseHTTPRequestHandler,
    *,
    status_code: int,
    payload: dict[str, Any],
) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def log_event(message: str) -> None:
    print(message, flush=True)


def build_handler(service: RerankerService) -> type[BaseHTTPRequestHandler]:
    class RerankerHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            started_at = perf_counter()
            if self.path != "/health":
                write_json_response(
                    self,
                    status_code=404,
                    payload={"error": "Not found."},
                )
                log_event(
                    f"GET {self.path} -> 404 in "
                    f"{(perf_counter() - started_at) * 1000.0:.1f}ms"
                )
                return
            write_json_response(
                self,
                status_code=200,
                payload=service.health_payload(),
            )
            log_event(
                f"GET /health -> 200 in "
                f"{(perf_counter() - started_at) * 1000.0:.1f}ms "
                f"(model={service.model_name}, device={service.device})"
            )

        def do_POST(self) -> None:
            started_at = perf_counter()
            if self.path != "/rerank":
                write_json_response(
                    self,
                    status_code=404,
                    payload={"error": "Not found."},
                )
                log_event(
                    f"POST {self.path} -> 404 in "
                    f"{(perf_counter() - started_at) * 1000.0:.1f}ms"
                )
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                write_json_response(
                    self,
                    status_code=400,
                    payload={"error": "Request body must be valid JSON."},
                )
                log_event(
                    f"POST /rerank -> 400 in "
                    f"{(perf_counter() - started_at) * 1000.0:.1f}ms "
                    "(invalid_json)"
                )
                return

            model_name = payload.get("model_name")
            if model_name not in {None, service.model_name}:
                write_json_response(
                    self,
                    status_code=400,
                    payload={
                        "error": (
                            f"Service is running model '{service.model_name}', not "
                            f"'{model_name}'."
                        )
                    },
                )
                log_event(
                    f"POST /rerank -> 400 in "
                    f"{(perf_counter() - started_at) * 1000.0:.1f}ms "
                    f"(model_mismatch requested={model_name!r})"
                )
                return

            question = payload.get("question")
            documents = payload.get("documents")
            if not isinstance(question, str) or not question.strip():
                write_json_response(
                    self,
                    status_code=400,
                    payload={"error": "'question' must be a non-empty string."},
                )
                log_event(
                    f"POST /rerank -> 400 in "
                    f"{(perf_counter() - started_at) * 1000.0:.1f}ms "
                    "(invalid_question)"
                )
                return
            if not isinstance(documents, list) or not all(
                isinstance(document, str) for document in documents
            ):
                write_json_response(
                    self,
                    status_code=400,
                    payload={"error": "'documents' must be a list of strings."},
                )
                log_event(
                    f"POST /rerank -> 400 in "
                    f"{(perf_counter() - started_at) * 1000.0:.1f}ms "
                    "(invalid_documents)"
                )
                return

            log_event(
                f"POST /rerank <- question_chars={len(question)} "
                f"documents={len(documents)} model={service.model_name} "
                f"device={service.device}"
            )
            try:
                scores = service.predict(question=question, documents=documents)
            except (RuntimeError, TypeError, ValueError) as exc:
                write_json_response(
                    self,
                    status_code=500,
                    payload={"error": "Reranker prediction failed."},
                )
                log_event(
                    f"POST /rerank -> 500 in "
                    f"{(perf_counter() - started_at) * 1000.0:.1f}ms "
                    f"(documents={len(documents)} error={type(exc).__name__}: {exc})"
                )
                return
            write_json_response(
                self,
                status_code=200,
                payload={
                    "model_name": service.model_name,
                    "device": service.device,
                    "scores": scores,
                },
            )
            log_event(
                f"POST /rerank -> 200 in "
                f"{(perf_counter() - started_at) * 1000.0:.1f}ms "
                f"(documents={len(documents)} scores={len(scores)})"
            )

        def log_message(self, format: str, *args: object) -> None:
            return

    return RerankerHandler


def main() -> None:
    model_name = os.getenv("RERANKER_MODEL", DEFAULT_RERANKER_MODEL)
    host = os.getenv("RERANKER_HOST", DEFAULT_RERANKER_HOST)
    port = int(os.getenv("RERANKER_PORT", str(DEFAULT_RERANKER_PORT)))
    device_name = os.getenv("RERANKER_DEVICE", DEFAULT_RERANKER_DEVICE)
    device = resolve_device(device_name)
    service = RerankerService(model_name=model_name, device=device)
    server = ThreadingHTTPServer((host, port), build_handler(service))
    print(
        f"reranker service listening on http://{host}:{port} "
        f"(model={model_name}, device={device})"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
