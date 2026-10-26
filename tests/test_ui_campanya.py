"""test_ui_campanya.py — les rutes de Definició de campanya (C1, C2), amb un servidor real.

Què es fixa
-----------
- `/api/campanya/{schema,defaults,yaml,comprova}` responen, i els errors d'entrada són un 400 amb el motiu.
- La pàgina té la pestanya «Campanya» i els identificadors que el JS usa.
- `POST /api/campanya/yaml` amb `desa` escriu a `data/campanyes_esborrany/<id>/` (aquí, a un directori
  temporal) i mai dins de neudet.
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

def test_pagina_te_la_pestanya_campanya(url):
    code, raw = _req(url, "/")
    html = raw.decode()
    assert code == 200
    assert 'data-tab="campanya"' in html and 'id="pg-campanya"' in html
    assert html.index('data-tab="campanya"') < html.index('data-tab="disseny"'), "Campanya va abans de Disseny"
    for ident in ('id="c-form"', 'id="c-yaml"', 'id="c-res"', 'id="c-comprova"', 'id="c-desa"', 'id="c-baixa"'):
        assert ident in html, ident


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
    assert "anells" in [g["tipus"] for g in s["generadors"]]
    assert s["cd"]["fraccions"] == [0, 0.25, 0.5, 0.75, 1]
    code, d = _json(url, "/api/campanya/defaults")
    assert code == 200 and d["id"] == "c04_draft"


def test_yaml_en_viu_no_escriu_res(url, tmp_path, monkeypatch):
    _neudet_o_skip()
    monkeypatch.setattr(api, "esborranys_root", lambda: tmp_path / "esborranys")
    _, d = _json(url, "/api/campanya/defaults")
    code, r = _json(url, "/api/campanya/yaml", {"form": d, "desa": False})
    assert code == 200 and r["desat"] is None
    assert r["yaml"].startswith("# Esborrany generat per simphy")
    assert not (tmp_path / "esborranys").exists()


def test_desa_escriu_al_directori_d_esborranys_i_no_a_neudet(url, tmp_path, monkeypatch):
    neudet = _neudet_o_skip()
    monkeypatch.setattr(api, "esborranys_root", lambda: tmp_path / "esborranys")
    _, d = _json(url, "/api/campanya/defaults")
    code, r = _json(url, "/api/campanya/yaml", {"form": d, "desa": True})
    assert code == 200
    desat = Path(r["desat"])
    assert desat == (tmp_path / "esborranys" / "c04_draft" / "campanya.yaml").resolve()
    assert desat.read_text() == r["yaml"]
    assert neudet not in desat.parents


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
