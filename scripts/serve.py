#!/usr/bin/env python3
"""serve.py — consola web de simphy: un formulari (o un prompt) → els quatre codis.

    python scripts/ui/serve.py                 # http://127.0.0.1:8765
    python scripts/ui/serve.py --port 9000

El codi és al paquet `simphy.ui` (`api.py`, `server.py`, `static/index.html`);
aquest fitxer només l'arrenca. `tests/test_ui_serve.py` comprova, exemple per
exemple i codi per codi, que la pàgina i `gen.py` donen el mateix resultat.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from simphy.ui.api import EXAMPLES, ask, llm_status, meta, render_all, render_one  # noqa: E402,F401
from simphy.ui.server import PAGE, Handler, make_server                         # noqa: E402,F401


def main(argv=None) -> int:
    from simphy.mcgen.paths import load_env
    load_env()                  # MCGEN_LLM_* del `.env`, com `gen.py`
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1",
                    help="per defecte només aquesta màquina")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    srv = make_server(args.host, args.port)
    print(f"[ui] simphy a http://{args.host}:{srv.server_address[1]}  (Ctrl+C per aturar)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
