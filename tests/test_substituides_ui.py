"""test_substituides_ui.py — SUBST (decisió de l'Albert 2026-11-24, sobre l'anunci CON-API del neudet `91aaf7c5`).

Què es fixa
-----------
- **Per defecte, fora del llistat**: una campanya amb `substituïda_per` al `campanya.yaml` no surt a
  `llista()`; amb `llista(True)` sí, i porta `substituïda` (a qui, data i motiu, text de neudet). Filtra
  l'API —la pàgina no amaga res pel seu compte—, i «mostra les substituïdes» és el camí per tornar-les a veure.
- **L'`estat` no canvia** (mesura del neudet: el cicle `confirmacio.py:42` no té valor de substitució i un
  text lliure amb `confirmacio` present **bloqueja**): la campanya continua sent `executada`. El bessó
  llegeix el seu yaml i ho verifica a la llista.
- **Oberta, diu a quina ha passat**: `vista()` dona el mateix camp i la pàgina el pinta amb un enllaç a la
  campanya nova; si el yaml no en diu el motiu, ho diu — no l'inventa.
- **L'adreça directa no cau en una altra campanya**: si la ruta en nomena una que no és a la llista, la
  pàgina la torna a llegir amb les substituïdes i marca la casella.
Sense neudet, els tests amb dades reals es salten.
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simui import campanya_vista as V  # noqa: E402
from simui import server  # noqa: E402

SRC = ROOT / "src" / "simui"
INDEX = (SRC / "static" / "index.html").read_text(encoding="utf-8")

CAMP = "mb10b_cd_openmc"       # l'única que porta les claus (mesura del neudet 24-11: 1 de 17)


def _neudet_o_skip() -> Path:
    try:
        return V.neudet_root()
    except Exception as e:
        pytest.skip(f"neudet no és present: {e}")


# ── la llista: per defecte fora, amb la casella dins ─────────────────────────

def test_la_llista_per_defecte_no_porta_substituïdes_i_amb_la_casella_sí():
    _neudet_o_skip()
    sense, amb = V.llista(), V.llista(True)
    assert all(c["substituïda"] is None for c in sense)
    subs = [c for c in amb if c["substituïda"]]
    assert subs and len(amb) - len(sense) == len(subs)        # el que surt és exactament el que filtra
    for c in subs:
        assert c["substituïda"]["per"] and c["substituïda"]["per"] != c["id"]
        assert c["id"] not in [x["id"] for x in sense]


def test_besso_la_declaració_de_neudet_i_lestat_que_no_canvia():
    root = _neudet_o_skip()
    f = root / "disseny" / "campanyes" / CAMP / "campanya.yaml"
    if not f.is_file():
        pytest.skip(f"{CAMP} no és a l'arbre de neudet")
    y = V._yaml(f)
    assert y["substituïda_per"] == "mb10b_cd" and str(y["substituïda_data"]) == "2026-11-24"
    assert y["estat"] == "executada"                          # l'anunci: l'estat NO canvia, és una clau a part
    c = next(c for c in V.llista(True) if c["id"] == CAMP)
    assert c["substituïda"] == {"per": "mb10b_cd", "data": "2026-11-24", "motiu": y["substituïda_motiu"]}
    assert c["estat_yaml"] == "executada"                     # a la llista, tal com és: no «substituïda»


def test_la_vista_dona_a_quina_campanya_s_ha_passat():
    _neudet_o_skip()
    try:
        v = V.vista(V.dir_de(CAMP))
    except V.CampanyaError as e:
        pytest.skip(f"{CAMP} no és a l'arbre: {e}")
    assert v["substituïda"] and v["substituïda"]["per"] == "mb10b_cd"
    assert v["substituïda"]["motiu"]                          # el motiu que hi va escriure neudet
    assert V.vista(V.dir_de("mb10b_cd"))["substituïda"] is None   # la que substitueix, res


# ── per HTTP: el mateix filtre a l'endpoint que fa servir la pàgina ───────────

@pytest.fixture(scope="module")
def url():
    srv = server.make_server("127.0.0.1", 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _camps(base: str, query: str = ""):
    with urllib.request.urlopen(base + "/api/campanyes" + query, timeout=60) as r:
        return json.loads(r.read())["campanyes"]


def test_l_endpoint_filtra_i_el_parametre_les_torna(url):
    _neudet_o_skip()
    ids = {c["id"] for c in _camps(url)}
    amb = _camps(url, "?substituides=1")
    subs = [c for c in amb if c["substituïda"]]
    assert subs and ids.isdisjoint({c["id"] for c in subs})
    assert {c["id"] for c in amb} == ids | {c["id"] for c in subs}
    for c in _camps(url):                                     # el camp hi és sempre: la pàgina no hi ha de endevinar
        assert c["substituïda"] is None


# ── la pàgina: la casella, el retol, la franja i l'adreça directa ────────────

def test_la_pagina_té_la_casella_el_retol_i_la_franja_de_substitució():
    assert '<input type="checkbox" id="n-subst"> mostra les substituïdes' in INDEX
    assert "Q('#n-subst').onchange = e => { NZ_SUBST = e.target.checked; nzLlegeixLlista()" in INDEX
    assert "api('/api/campanyes' + (NZ_SUBST ? '?substituides=1' : ''))" in INDEX
    assert 'data-subst-a>substituïda → ' in INDEX              # a la llista, amb el nom de la nova
    assert 'data-subst>Substituïda per <a href="#neudet/' in INDEX
    assert "el yaml no en diu el motiu" in INDEX               # sense motiu escrit, ho diu: mai inventat
    # qui filtra és l'API: a la pàgina el camp només es pinta, no descarta cap campanya pel seu compte
    assert "filter(c => c.substituïda" not in INDEX and "!c.substituïda" not in INDEX
    assert "if(s[0] && !KC.lista.some(c => c.id === s[0]) && !NZ_SUBST){" in INDEX
    assert "NZ_SUBST = true; await nzLlegeixLlista();" in INDEX
