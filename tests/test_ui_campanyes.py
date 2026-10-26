"""test_ui_campanyes.py — les rutes de la pestanya Campanyes, amb un servidor real.

Què es fixa
-----------
- `/api/campanyes`, `/api/campanya/vista` i `/api/campanya/carrega` responen per a c04_draft, amb el provisional.
- `/api/campanya/fitxer` serveix el PDF com a `application/pdf`, el `.md` i les figures; i rebutja amb 403
  els traversals, els camins absoluts, els reports que el manifest no llista i els ids que no són campanyes.
- La pàgina té la pestanya «Campanyes» i els identificadors que el JS usa.
Sense neudet, els tests amb dades reals es salten.
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simphy.mcgen import design as D  # noqa: E402
from simphy.ui import server  # noqa: E402


@pytest.fixture(scope="module")
def url():
    try:
        D.neudet_root()
    except D.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")
    srv = server.make_server("127.0.0.1", 0)              # port efímer
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _get(base: str, path: str):
    try:
        with urllib.request.urlopen(base + path, timeout=60) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read()


def _fitxer(base: str, id_: str, rel: str):
    q = urllib.parse.urlencode({"id": id_, "rel": rel})
    return _get(base, "/api/campanya/fitxer?" + q)


def test_la_pagina_te_la_pestanya_i_els_identificadors(url):
    code, _, body = _get(url, "/")
    html = body.decode()
    assert code == 200
    assert 'data-tab="campanyes"' in html
    assert 'id="pg-campanyes"' in html
    assert 'id="k-out"' in html and 'id="k-camp"' in html
    # la pestanya és després de Campanya
    assert html.index('data-tab="campanya"') < html.index('data-tab="campanyes"') < html.index('data-tab="disseny"')


def test_llista_inclou_c04_com_a_provisional(url):
    code, _, body = _get(url, "/api/campanyes")
    d = json.loads(body)
    assert code == 200
    c04 = next(c for c in d["campanyes"] if c["id"] == "c04_draft")
    assert c04["estat_manifest"] == "draft" and c04["estat_yaml"] == "jutjada"   # dos estats, no un
    assert c04["grup"] == "principal"                                              # flux nou (fitxa: 1), manifest provisional
    assert c04["manifest"] is True and c04["provisional"] is False          # neudet 711addf: ja hi és


def test_vista_de_c04_ve_del_manifest_i_te_les_dues_etapes(url):
    code, _, body = _get(url, "/api/campanya/vista?id=c04_draft")
    v = json.loads(body)
    assert code == 200
    assert v["provisional"] is False                                     # campanya_ui.json de neudet
    assert [e["nom"] for e in v["etapes"]] == ["S1_draft", "S1_draft_g4"]
    assert v["pareto"]["eixos"][0] == {"metrica": "eps_mitja", "sentit": "max"}
    assert v["judici"]


def test_carrega_torna_el_yaml_com_a_formulari(url):
    code, _, body = _get(url, "/api/campanya/carrega?id=c04_draft")
    d = json.loads(body)
    assert code == 200
    assert d["form"]["id"] == "c04_draft"
    assert "S1" in d["form"]["etapes"]


def test_el_pdf_es_serveix_com_a_pdf(url):
    code, ctype, body = _fitxer(url, "c04_draft", "docs/site/report/2026-10-26_c04_draft.pdf")
    assert code == 200
    assert ctype == "application/pdf"
    assert body.startswith(b"%PDF")


def test_el_md_i_les_figures_es_serveixen(url):
    code, ctype, body = _fitxer(url, "c04_draft", "docs/site/report/2026-10-26_c04_draft.md")
    assert code == 200 and ctype.startswith("text/plain") and body
    code, ctype, body = _fitxer(url, "c04_draft", "etapes/S1_draft/figures/pareto.png")
    assert code == 200 and ctype == "image/png" and body.startswith(b"\x89PNG")


@pytest.mark.parametrize("rel", [
    "../../../../../etc/passwd",
    "etapes/../../../../../../etc/passwd",
    "/etc/passwd",
    "..%2F..%2Fetc%2Fpasswd",                              # ja decodificat, sempre traversal
    "docs/site/report/2026-10-25_cataleg_tubs.pdf",         # report que el manifest no llista
    "campanya.py",                                          # tipus no servible
    "C:\\Windows\\win.ini",
    "",
])
def test_traversal_i_camins_fora_donen_403(url, rel):
    code, _, body = _fitxer(url, "c04_draft", rel)
    assert code == 403, body


def test_id_que_no_es_una_campanya_dona_403(url):
    assert _fitxer(url, "../../simphy", "x.pdf")[0] == 403
    assert _fitxer(url, "no_existeix", "x.pdf")[0] == 403


def test_vista_amb_id_no_valid_es_400(url):
    code, _, body = _get(url, "/api/campanya/vista?id=..%2Fx")
    assert code == 400
    assert "id de campanya" in json.loads(body)["error"]
