"""El servidor de la consola: `http.server` de la stdlib, sense dependències."""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlsplit

from .api import ask, llm_status, meta, render_all

PAGE = (Path(__file__).resolve().parent / "static" / "index.html").read_text()


class Handler(BaseHTTPRequestHandler):
    server_version = "simphy-ui"

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: Any, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(),
                   "application/json; charset=utf-8")

    def _body(self) -> Dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self) -> None:                                  # noqa: N802
        # La query (`/?ex=un_perp_detector`) la llegeix la pàgina, no el servidor.
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/api/meta":
            self._json(meta())
        elif path == "/api/llm":
            self._json(llm_status())
        else:
            self._json({"error": f"no hi ha {path}"}, 404)

    def do_POST(self) -> None:                                 # noqa: N802
        try:
            body = self._body()
        except json.JSONDecodeError as exc:
            self._json({"error": f"el cos no és JSON: {exc}"}, 400)
            return
        path = urlsplit(self.path).path
        if path == "/api/render":
            self._json({"results": render_all(body.get("spec") or {})})
        elif path == "/api/ask":
            self._json(ask(str(body.get("prompt") or ""), body.get("backend")))
        else:
            self._json({"error": f"no hi ha {path}"}, 404)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"[ui] {self.address_string()} {fmt % args}\n")


def make_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)
