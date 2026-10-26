"""El servidor de la consola: `http.server` de la stdlib, sense dependències.

Rutes: `/` (la pàgina), `/api/meta`, `/api/llm`, `/api/render`, `/api/ask` (Simulació) i
`/api/design/{meta,load,check,view,export,ask}` + `/api/results` (Disseny i Resultats) i
`/api/campanya/{schema,defaults,yaml,comprova,compta}` (Definició de campanya).
Els errors d'un disseny o d'un resultat són un 400 amb el motiu (`{"error": …}`), no un
forat: el que la pàgina ha de dir és què falta.
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlsplit

from . import api
from .api import ask, llm_status, meta, render_all

PAGE = (Path(__file__).resolve().parent / "static" / "index.html").read_text()

#: Errors que són culpa de l'entrada (un disseny que no es pot llegir, un hash que no hi és…).
#: Tot el que no és d'aquesta llista és un forat de simphy i es retorna com a 500.
_ERRORS_D_ENTRADA = (ValueError, KeyError, RuntimeError)


class Handler(BaseHTTPRequestHandler):
    server_version = "simphy-ui"

    def _send(self, code: int, body: bytes, ctype: str, extra: Dict[str, str] | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: Any, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(),
                   "application/json; charset=utf-8")

    def _body(self) -> Dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _tracta(self, fn, *args) -> None:
        """Crida una funció de l'API i converteix els errors en una resposta llegible."""
        try:
            self._json(fn(*args))
        except _ERRORS_D_ENTRADA as exc:
            self._json({"error": str(exc) or type(exc).__name__}, 400)
        except Exception as exc:                              # noqa: BLE001
            self._json({"error": f"{type(exc).__name__}: {exc}", "forat": True}, 500)

    def do_GET(self) -> None:                                  # noqa: N802
        # La query (`/?ex=un_perp_detector`) la llegeix la pàgina, no el servidor.
        url = urlsplit(self.path)
        path = url.path
        if path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/api/meta":
            self._json(meta())
        elif path == "/api/llm":
            self._json(llm_status())
        elif path == "/api/design/meta":
            self._tracta(api.design_meta)
        elif path == "/api/campanya/schema":
            self._tracta(api.campanya_schema)
        elif path == "/api/campanya/defaults":
            self._tracta(api.campanya_defaults)
        elif path == "/api/results":
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            self._tracta(api.results, q.get("hash", ""), q.get("stage") or None, q.get("energia"))
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
        elif path == "/api/design/load":
            self._tracta(api.design_load, body)
        elif path == "/api/design/check":
            self._tracta(api.design_check, body)
        elif path == "/api/design/view":
            self._tracta(api.design_view, body)
        elif path == "/api/design/ask":
            self._tracta(api.design_ask, body)
        elif path == "/api/campanya/yaml":
            self._tracta(api.campanya_yaml, body)
        elif path == "/api/campanya/comprova":
            self._tracta(api.campanya_comprova, body)
        elif path == "/api/campanya/compta":
            self._tracta(api.campanya_compta, body)
        elif path == "/api/design/export":
            try:
                data, nom = api.design_export(body)
            except _ERRORS_D_ENTRADA as exc:
                self._json({"error": str(exc) or type(exc).__name__}, 400)
                return
            except Exception as exc:                          # noqa: BLE001
                self._json({"error": f"{type(exc).__name__}: {exc}", "forat": True}, 500)
                return
            self._send(200, data, "application/zip",
                       {"Content-Disposition": f'attachment; filename="{nom}.zip"'})
        else:
            self._json({"error": f"no hi ha {path}"}, 404)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"[ui] {self.address_string()} {fmt % args}\n")


def make_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)
