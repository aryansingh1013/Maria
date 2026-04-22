from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from rag import build_fallback_llm, build_llm, hybrid_answer, load_env_file, load_vectorstore


import os
from http import HTTPStatus

BASE_DIR = Path(__file__).resolve().parent
VECTORSTORE_DIR = BASE_DIR / "vectorstore"
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 7860))

# Will be initialized in main()
VECTORSTORE = None
LLM = None
FALLBACK_LLM = None


class PlacementChatHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/api/chat":
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found.")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Invalid JSON payload."},
            )
            return

        query = str(payload.get("query", "")).strip()
        category = payload.get("category")
        if not query:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Query is required."},
            )
            return

        try:
            answer, sources, source_type = hybrid_answer(
                query=query,
                vectorstore=VECTORSTORE,
                rag_llm=LLM,
                fallback_llm=FALLBACK_LLM,
                category=category if isinstance(category, str) and category.strip() else None,
            )
        except Exception as exc:  # pragma: no cover
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Chat request failed: {exc}"},
            )
            return

        self._send_json(
            HTTPStatus.OK,
            {"answer": answer, "sources": sources, "source_type": source_type},
        )

    def end_headers(self) -> None:
        self.send_header("Cache-Control", self._get_cache_control())
        super().end_headers()

    def guess_type(self, path: str) -> str:
        if path.endswith(".js"):
            return "application/javascript"
        return mimetypes.guess_type(path)[0] or "application/octet-stream"

    def _send_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _get_cache_control(self) -> str:
        request_path = urlparse(self.path).path.lower()

        if request_path == "/api/chat":
            return "no-store"

        static_asset_suffixes = {
            ".js",
            ".css",
            ".glb",
            ".gltf",
            ".bin",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".webp",
            ".ico",
            ".woff",
            ".woff2",
        }
        if any(request_path.endswith(suffix) for suffix in static_asset_suffixes):
            return "public, max-age=604800, immutable"

        if request_path.endswith(".html") or request_path == "/":
            return "no-cache"

        return "public, max-age=3600"


def main() -> None:
    global VECTORSTORE, LLM, FALLBACK_LLM

    load_env_file(BASE_DIR / ".env")

    print("Loading vectorstore...")
    VECTORSTORE = load_vectorstore(VECTORSTORE_DIR)
    print("Vectorstore loaded. Building RAG LLM client...")
    LLM = build_llm(provider="huggingface", model_name="Qwen/Qwen2.5-7B-Instruct")
    print("RAG LLM ready. Building fallback LLM (Groq)...")
    FALLBACK_LLM = build_fallback_llm()
    if FALLBACK_LLM:
        print("Fallback LLM ready (Groq llama-3.3-70b).")
    else:
        print("Warning: Fallback LLM not available (GROQ_API_KEY missing).")

    server = ThreadingHTTPServer((HOST, PORT), PlacementChatHandler)
    print(f"Placement RAG app running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
