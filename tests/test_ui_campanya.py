"""test_ui_campanya.py — les rutes de Definició de campanya (C1, C2), amb un servidor real.

Què es fixa
-----------
- `/api/campanya/{schema,defaults,yaml,comprova}` responen, i els errors d'entrada són un 400 amb el motiu.
- La pàgina té la pestanya «Campanya» i els identificadors que el JS usa.
- `POST /api/campanya/yaml` no escriu res: la proposta es desa a neudet amb `/api/campanya/desa`
  (vegeu tests/test_ui_campanya_desa.py).
- `POST /api/campanya/comprova` sobre c04 dona 259 vàlids (DEFINICIO.md), i un candidat de la llista
  es pot tornar a carregar al Disseny (`/api/design/load`) amb el seu parell `.dat`/`.json`.
- Un yaml trencat o una etapa que no hi és arriba com a missatge de neudet, no com a un forat.
Sense neudet, els tests amb dades reals es salten.
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simphy.mcgen import design as D  # noqa: E402
from simphy.ui import api, server  # noqa: E402


def _neudet_o_skip() -> Path:
    try:
        return D.neudet_root()
    except D.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")


@pytest.fixture(scope="module")
def url():
    srv = server.make_server("127.0.0.1", 0)           # port efímer
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _req(url_base: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url_base + path, data=data, method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _json(url_base, path, body=None):
    code, raw = _req(url_base, path, body)
    return code, json.loads(raw)


# ── la pàgina ───────────────────────────────────────────────────────────────

def test_pagina_te_el_formulari_de_proposta_dins_de_neudet(url):
    """El formulari de la proposta és al nivell 1 de Neudet, a la dreta de la llista, amb «+ Nova»."""
    code, raw = _req(url, "/")
    html = raw.decode()
    assert code == 200
    assert 'data-tab="neudet"' in html and 'id="pg-neudet"' in html
    for ident in ('id="n-bread"', 'id="n-camp"', 'id="n-form"', 'id="c-form"', 'id="c-yaml"',
                  'id="c-desa"', 'id="c-baixa"', 'id="c-flux"'):
        assert ident in html, ident
    assert '+ Nova campanya' in html and 'data-k="nova"' in html
    # el flux després de desar és explícit, i no hi ha cap botó «Comprova» que sembli un pas del flux
    assert "Comprova amb neudet" not in html and 'id="c-comprova"' not in html
    for pas in ("planificador de neudet", "runbook-run", "executada", "jutjada", "no corre cap simulació"):
        assert pas in html, pas


# ── rutes d'entrada ─────────────────────────────────────────────────────────

def test_yaml_formulari_invalid_es_400_amb_el_motiu(url):
    code, body = _json(url, "/api/campanya/yaml", {"form": {"id": "x y"}})
    assert code == 400
    assert "formulari no vàlid" in body["error"] and "id:" in body["error"]


def test_comprova_sense_yaml_es_400(url):
    code, body = _json(url, "/api/campanya/comprova", {"yaml_text": "  "})
    assert code == 400 and "buit" in body["error"]


# ── amb neudet: c04 ─────────────────────────────────────────────────────────

def test_schema_i_defaults(url):
    _neudet_o_skip()
    code, s = _json(url, "/api/campanya/schema")
    assert code == 200
    assert [f["valor"] for f in s["tongades"]["fonts"]] == ["punts", "malla", "anells", "dat"]
    assert s["cd"]["exemples_contracte"] == [0, 0.25, 0.5, 0.75, 1]   # exemples del contracte, no llista de neudet
    code, d = _json(url, "/api/campanya/defaults")
    assert code == 200 and d["id"] == "c04_draft"


def test_yaml_en_viu_no_escriu_res(url, tmp_path, monkeypatch):
    """El yaml en viu i «Descarrega» no escriuen res: desar és `/api/campanya/desa` (vegeu test_ui_campanya_desa)."""
    _neudet_o_skip()
    _, d = _json(url, "/api/campanya/defaults")
    code, r = _json(url, "/api/campanya/yaml", {"form": d})
    assert code == 200 and r["yaml"].startswith("# Esborrany generat per simphy")
    assert set(r) == {"yaml"}


def test_comprova_c04_dona_259_valids(url):
    _neudet_o_skip()
    _, d = _json(url, "/api/campanya/defaults")
    _, y = _json(url, "/api/campanya/yaml", {"form": d, "desa": False})
    code, r = _json(url, "/api/campanya/comprova", {"yaml_text": y["yaml"], "etapa": "S1"})
    assert code == 200
    assert r["n_valids"] == 259, f"neudet diu {r['n_valids']} vàlids (DEFINICIO.md: 259)"
    assert len(r["candidats"]) == 50
    assert all(c["xy_svg"].lstrip().startswith("<svg") for c in r["candidats"])
    c = r["certificacio"]
    # amb torch (railab) neudet certifica; sense (núvol) la UI ha de dir per què no, amb l'error de neudet
    if c["disponible"]:
        assert c["atura"] is False and any(e["element"] == "tub lnd_252285" for e in c["elements"])
    else:
        assert c["motiu"] and (c.get("error_sortida") or "comprova_campanya.py" in c["motiu"])


def test_candidat_de_la_llista_es_obre_al_disseny(url):
    """El que fa clic la llista de C2 és un parell .dat/.json de neudet: el Disseny l'ha de carregar."""
    _neudet_o_skip()
    _, d = _json(url, "/api/campanya/defaults")
    _, y = _json(url, "/api/campanya/yaml", {"form": d, "desa": False})
    _, r = _json(url, "/api/campanya/comprova", {"yaml_text": y["yaml"], "etapa": "S1"})
    c = r["candidats"][0]
    code, load = _json(url, "/api/design/load", {"dat_text": c["dat_text"], "json_text": c["json_text"]})
    assert code == 200, load
    assert load["design"]["nom"] == c["nom"] or load["origen"]["nom"] == c["nom"]


def test_yaml_trencat_mostra_l_error_de_neudet(url):
    _neudet_o_skip()
    code, body = _json(url, "/api/campanya/comprova", {"yaml_text": "id: [sense_tancar\n", "etapa": "S1"})
    assert code == 400
    assert "Error" in body["error"], body


def test_etapa_inexistent_mostra_el_missatge_de_neudet(url):
    _neudet_o_skip()
    _, d = _json(url, "/api/campanya/defaults")
    _, y = _json(url, "/api/campanya/yaml", {"form": d, "desa": False})
    code, body = _json(url, "/api/campanya/comprova", {"yaml_text": y["yaml"], "etapa": "S9"})
    assert code == 400
    assert "no és a campanya.yaml" in body["error"]


# ── el recompte en viu: /api/campanya/compta ─────────────────────────────────

def test_compta_c04_s1_per_la_ruta(url):
    """El recompte de la ruta és el de neudet (`recompte_etapa`) per a c04 S1: una tongada, abans de treure repetits."""
    _neudet_o_skip()
    _, d = _json(url, "/api/campanya/defaults")
    code, r = _json(url, "/api/campanya/compta", {"form": d, "etapa": "S1"})
    assert code == 200, r
    assert r["etapa"] == "S1" and r["n"] == sum(t["recompte"] for t in r["tongades"]) and r["n"] >= 287
    assert [t["nom"] for t in r["tongades"]] == ["anells"]


def test_compta_error_de_neudet_arriba_verbatim(url):
    """Una regla que neudet no pot generar: el missatge és el de neudet, tal com és (no reescrit)."""
    _neudet_o_skip()
    from simphy.mcgen import campanya_check as CC, campanya_form as CF
    _, d = _json(url, "/api/campanya/defaults")
    d["etapes"]["S1"]["tongades"] = [{"nom": "t", "posicions": {"font": "anells", "anells": [{"r": 3, "n": 2, "phi": 0}]},
                                      "tipus": ["lnd_252285", "lnd_252248"], "cd": {"fraction": 0}, "eix": "z",
                                      "seleccio": "exhaustiu"}]       # un ventall sense `lligam`: neudet (fitxa) ho diu
    code, body = _json(url, "/api/campanya/compta", {"form": d, "etapa": "S1"})
    assert code == 400
    with pytest.raises(ValueError) as exc:
        CC.compta(CF.to_yaml(d), "S1")
    import re
    net = lambda m: re.sub(r"simphy_campanya_\w+", "simphy_campanya_X", m)      # el directori temporal canvia a cada crida
    assert net(body["error"]) == net(str(exc.value))
    assert body["error"].startswith("⛔") and "lligam" in body["error"]


def test_compta_formulari_invalid_es_400_amb_el_motiu(url):
    code, body = _json(url, "/api/campanya/compta", {"form": {"id": "x y"}, "etapa": "S1"})
    assert code == 400 and "formulari no vàlid" in body["error"]


def test_compta_d_una_llista_tancada_fora_de_neudet_es_400(url):
    _neudet_o_skip()
    _, d = _json(url, "/api/campanya/defaults")
    d["objectius"]["metriques"] = ["inventada"]
    code, body = _json(url, "/api/campanya/compta", {"form": d, "etapa": "S1"})
    assert code == 400 and "objectius.metriques" in body["error"]


# ── la pàgina: estructura i llistes ──────────────────────────────────────────

def _bloc_campanya(html: str) -> str:
    a = html.index("// ── Definició de campanya (C1, C2)")
    return html[a:html.index("function cPintaCert(c){")]


def test_pagina_campanya_nota_i_recompte_i_candidat_nomes_a_llista(url):
    code, raw = _req(url, "/")
    html = raw.decode()
    assert code == 200
    assert "nota (no afecta res)" in html and "què fa l'etapa" not in html
    assert 'id="c-compta"' in html and "/api/campanya/compta" in html
    assert "aquesta etapa genera" in html
    # les tongades: «+ tongada» i els editors de cada font
    assert html.count('data-act="tg+"') == 1 and "function cTongadaHtml" in html
    for f in ("cPuntsHtml", "cMallaHtml", "cAnellsHtml"):
        assert f"function {f}" in html, f


def test_pagina_campanya_sense_textarea_ni_text_lliure_de_camps(url):
    """La pantalla de campanya no té textarea ni JSON editable: cada camp és una llista tancada, un número
    o una lectura amb la línia de neudet. El text lliure és només la nota de l'etapa."""
    code, raw = _req(url, "/")
    bloc = _bloc_campanya(raw.decode())
    assert "<textarea" not in bloc
    assert 'data-t="json"' not in bloc
    assert 'data-t="pairs"' not in bloc and 'data-t="slist"' not in bloc


# ── el candidat d'una campanya de neudet té .dat (el genera neudet) ───────────

def test_candidat_de_campanya_porta_el_dat_de_neudet(url):
    """Un candidat de la llista d'una campanya no és a `export/`: `/api/campanya/candidat` el genera amb
    `Candidat.to_dat` i el Disseny el pot carregar (visor i inputs)."""
    root = _neudet_o_skip()
    from simphy.mcgen import campanya_check as CC
    if not (root / "disseny/campanyes/c04_draft/campanya.yaml").exists():
        pytest.skip("neudet no té c04_draft")
    _, d = _json(url, "/api/campanya/defaults")
    _, y = _json(url, "/api/campanya/yaml", {"form": d, "desa": False})
    _, r = _json(url, "/api/campanya/comprova", {"yaml_text": y["yaml"], "etapa": "S1"})
    h = r["candidats"][0]["hash"]
    code, g = _json(url, f"/api/campanya/candidat?id=c04_draft&hash={h}")
    if code == 400 and "cap candidat vàlid" in g.get("error", ""):
        pytest.skip(f"c04_draft de neudet ja no genera el candidat per defecte: {g['error']}")
    assert code == 200, g
    assert g["hash"] == h and g["dat_text"].strip() and g["json_text"].strip()
    code, load = _json(url, "/api/design/load", {"dat_text": g["dat_text"], "json_text": g["json_text"]})
    assert code == 200, load


def test_candidat_de_campanya_hash_desconegut_es_un_400(url):
    root = _neudet_o_skip()
    if not (root / "disseny/campanyes/c04_draft/campanya.yaml").exists():
        pytest.skip("neudet no té c04_draft")
    code, g = _json(url, "/api/campanya/candidat?id=c04_draft&hash=no_existeix")
    assert code == 400 and "cap candidat vàlid" in g["error"], g
