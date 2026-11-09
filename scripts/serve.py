#!/usr/bin/env python3
"""serve.py — consola web de simphy: un formulari (o un prompt) → els quatre codis.

    python scripts/serve.py                 # http://127.0.0.1:8765
    python scripts/serve.py --port 9000
    python scripts/serve.py --host 127.0.0.1,192.168.31.118,192.168.192.66   # diverses adreces (una per interfície)
    python scripts/serve.py --host ... --port 8765 --restart   # si ja hi ha un servidor en aquest port, l'atura i arrenca el nou

El codi és al paquet `simui` (`api.py`, `server.py`, `static/index.html`);
aquest fitxer només l'arrenca. `tests/test_ui_serve.py` comprova, exemple per
exemple i codi per codi, que la pàgina i `gen.py` donen el mateix resultat.
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simui.api import EXAMPLES, ask, llm_status, meta, render_all, render_one  # noqa: E402,F401
from simui.server import PAGE, Handler, make_server                         # noqa: E402,F401


def _pidfile(port: int) -> Path:
    return Path("/tmp") / f"simphy-ui-{port}.pid"      # fix: el mateix lloc des de qualsevol terminal


def _es_serve(pid: int) -> bool:
    """Un pid és d'un serve.py nostre (no d'un altre procés que n'hagi heretat el número)."""
    try:
        return b"serve.py" in Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return False


def atura_anterior(port: int, espera: float = 10.0) -> bool:
    """`--restart`: atura el serve.py que va arrencar aquest port (SIGTERM; SIGKILL si no hi respon). → si n'hi havia cap."""
    pf = _pidfile(port)
    try:
        pid = int(pf.read_text().strip())
    except (OSError, ValueError):
        return False
    if pid == os.getpid() or not _es_serve(pid):
        return False
    os.kill(pid, signal.SIGTERM)
    fi = time.time() + espera
    while time.time() < fi and _es_serve(pid):
        time.sleep(0.1)
    if _es_serve(pid):
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.3)
    return True


def main(argv=None) -> int:
    from simphy.mcgen.paths import load_env
    load_env()                  # MCGEN_LLM_* del `.env`, com `gen.py`
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1",
                    help="una adreça o diverses separades per comes; per defecte només aquesta màquina. "
                         "No hi ha autenticació: escolta només les adreces que demanis (mai 0.0.0.0 sense voler)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--restart", action="store_true",
                    help="si ja hi ha un serve.py corrent en aquest port (el recorda un fitxer a /tmp), l'atura abans d'arrencar")
    args = ap.parse_args(argv)
    if args.restart and atura_anterior(args.port):
        print(f"[ui] aturat el servidor anterior del port {args.port}", flush=True)
    hosts = [h.strip() for h in args.host.split(",") if h.strip()]
    srvs = [make_server(h, args.port) for h in hosts]     # si una adreça no existeix, peta abans d'escoltar-ne cap
    _pidfile(args.port).write_text(str(os.getpid()))
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))     # SIGTERM = Ctrl+C
    for h, srv in zip(hosts, srvs):
        print(f"[ui] simphy a http://{h}:{srv.server_address[1]}  (Ctrl+C per aturar)", flush=True)
    for srv in srvs[1:]:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        srvs[0].serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if _pidfile(args.port).read_text().strip() == str(os.getpid()):
                _pidfile(args.port).unlink()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
