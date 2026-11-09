"""simui — el frontend de simphy: una consola web prima sobre el paquet.

    api.py      el que la pàgina demana (meta, render, ask): IMPORTA de `mcgen`, no implementa
    server.py   `http.server` de la stdlib: rutes `/`, `/api/*`; sense dependències
    static/     la pàgina (`index.html`), servida tal qual

Arrencada: `python scripts/serve.py` (http://127.0.0.1:8765). Història i regles:
`docs/ui.md`.
"""
